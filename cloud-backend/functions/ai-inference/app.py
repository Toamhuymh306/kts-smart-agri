"""
Lambda: ai-inference
Triggered by SQS (S3 → SQS → Lambda pipeline).
S3 ObjectCreated event được wrap trong SQS message body.
Runs mock plant disease inference and stores result in DynamoDB.
Copies processed image key to Archive bucket.

Flow:
  1. Parse SQS record → unwrap S3 event from message body
  2. Extract userId, imageId, s3Key from S3 key pattern
  3. Write DynamoDB record: status=PROCESSING
  4. Mock inference: random disease + confidence
  5. Update DynamoDB record: status=COMPLETED
  6. Copy S3 key reference to Archive bucket (Store Processed Image)
  7. On any error after PROCESSING: update status=FAILED with errorMessage
  8. Log all input/output to CloudWatch Logs
"""

import json
import logging
import os
import random
import urllib.parse
from datetime import datetime, timezone
from decimal import Decimal

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb = boto3.resource("dynamodb")
s3_client = boto3.client("s3")

TABLE_NAME = os.environ["DYNAMODB_TABLE_NAME"]
ARCHIVE_BUCKET = os.environ.get("ARCHIVE_BUCKET_NAME", "")

table = dynamodb.Table(TABLE_NAME)

# Mock disease list for inference
DISEASES = [
    {"disease": "leaf_blight",    "confidence": Decimal("0.92")},
    {"disease": "rust",           "confidence": Decimal("0.87")},
    {"disease": "powdery_mildew", "confidence": Decimal("0.78")},
    {"disease": "bacterial_spot", "confidence": Decimal("0.85")},
    {"disease": "healthy",        "confidence": Decimal("0.95")},
    {"disease": "early_blight",   "confidence": Decimal("0.81")},
    {"disease": "late_blight",    "confidence": Decimal("0.76")},
]


def lambda_handler(event, context):
    logger.info("ai-inference triggered via SQS. Records: %d", len(event.get("Records", [])))

    failed_message_ids = []

    for sqs_record in event.get("Records", []):
        message_id = sqs_record.get("messageId", "unknown")
        try:
            _process_sqs_record(sqs_record)
        except Exception as e:
            logger.error("Failed to process SQS messageId=%s: %s", message_id, e)
            # ReportBatchItemFailures: trả về messageId thất bại để SQS retry riêng lẻ
            failed_message_ids.append({"itemIdentifier": message_id})

    if failed_message_ids:
        return {"batchItemFailures": failed_message_ids}

    return {}


def _process_sqs_record(sqs_record: dict):
    """
    SQS record chứa S3 event trong field 'body' (JSON string).
    Một SQS message có thể chứa nhiều S3 Records (thường là 1).
    """
    body = sqs_record.get("body", "{}")
    try:
        s3_event = json.loads(body)
    except json.JSONDecodeError as e:
        logger.error("Failed to parse SQS message body as JSON: %s | body=%s", e, body)
        raise

    s3_records = s3_event.get("Records", [])
    if not s3_records:
        logger.warning("No S3 Records in SQS message body, skipping")
        return

    for s3_record in s3_records:
        _process_s3_record(s3_record)


def _process_s3_record(record: dict):
    """Xử lý một S3 ObjectCreated record."""
    bucket = record["s3"]["bucket"]["name"]
    raw_key = record["s3"]["object"]["key"]
    s3_key = urllib.parse.unquote_plus(raw_key)

    logger.info("Processing S3 object: bucket=%s key=%s", bucket, s3_key)

    # Expected key pattern: uploads/{userId}/{imageId}/{fileName}
    parts = s3_key.split("/")
    if len(parts) < 4 or parts[0] != "uploads":
        logger.warning("Unexpected S3 key format, skipping: %s", s3_key)
        return

    user_id = parts[1]
    image_id = parts[2]
    now = datetime.now(timezone.utc).isoformat()

    # --- Step 1: Write PROCESSING record to DynamoDB ---
    try:
        table.put_item(Item={
            "userId":     user_id,
            "imageId":    image_id,
            "imageS3Key": s3_key,
            "status":     "PROCESSING",
            "timestamp":  now,
            "createdAt":  now,
            "disease":    None,
            "confidence": None,
        })
        logger.info(
            "DynamoDB record created: userId=%s imageId=%s status=PROCESSING",
            user_id, image_id
        )
    except ClientError as e:
        logger.error("Failed to write PROCESSING record: %s", e)
        raise

    # --- Step 2: Mock inference ---
    try:
        result = random.choice(DISEASES)
        disease = result["disease"]
        confidence = result["confidence"]  # Decimal
        logger.info(
            "Inference result: userId=%s imageId=%s disease=%s confidence=%s",
            user_id, image_id, disease, confidence
        )

        updated_at = datetime.now(timezone.utc).isoformat()

        # --- Step 3: Update DynamoDB to COMPLETED ---
        table.update_item(
            Key={"userId": user_id, "imageId": image_id},
            UpdateExpression=(
                "SET #status = :status, disease = :disease, "
                "confidence = :confidence, updatedAt = :updatedAt"
            ),
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={
                ":status":     "COMPLETED",
                ":disease":    disease,
                ":confidence": confidence,
                ":updatedAt":  updated_at,
            },
        )
        logger.info(
            "DynamoDB record updated: userId=%s imageId=%s status=COMPLETED",
            user_id, image_id
        )

        # --- Step 4: Copy key reference to Archive bucket (Store Processed Image) ---
        if ARCHIVE_BUCKET:
            archive_key = s3_key.replace("uploads/", "processed/", 1)
            try:
                s3_client.copy_object(
                    CopySource={"Bucket": bucket, "Key": s3_key},
                    Bucket=ARCHIVE_BUCKET,
                    Key=archive_key,
                )
                logger.info(
                    "Image archived: src=%s/%s dest=%s/%s",
                    bucket, s3_key, ARCHIVE_BUCKET, archive_key
                )
            except ClientError as e:
                # Archive failure không được block kết quả chẩn đoán
                logger.warning("Failed to archive image (non-fatal): %s", e)

    except Exception as e:
        # --- Step 5: Mark as FAILED ---
        error_message = str(e)
        logger.error(
            "Inference failed: userId=%s imageId=%s error=%s",
            user_id, image_id, error_message
        )
        failed_at = datetime.now(timezone.utc).isoformat()
        try:
            table.update_item(
                Key={"userId": user_id, "imageId": image_id},
                UpdateExpression=(
                    "SET #status = :status, errorMessage = :error, updatedAt = :updatedAt"
                ),
                ExpressionAttributeNames={"#status": "status"},
                ExpressionAttributeValues={
                    ":status":    "FAILED",
                    ":error":     error_message,
                    ":updatedAt": failed_at,
                },
            )
            logger.info(
                "DynamoDB record marked FAILED: userId=%s imageId=%s",
                user_id, image_id
            )
        except ClientError as ddb_err:
            logger.error("Failed to mark record as FAILED: %s", ddb_err)
        raise
