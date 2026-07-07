"""
Lambda: ai-inference
Triggered by S3 ObjectCreated event on prefix uploads/.
Runs mock plant disease inference and stores result in DynamoDB.

Flow:
  1. Parse S3 event → extract userId, imageId, s3Key
  2. Write DynamoDB record: status=PROCESSING
  3. Mock inference: random disease + confidence
  4. Update DynamoDB record: status=COMPLETED
  5. Log all input/output to CloudWatch Logs
"""

import json
import logging
import os
import random
import urllib.parse
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb = boto3.resource("dynamodb")

TABLE_NAME = os.environ["DYNAMODB_TABLE_NAME"]
table = dynamodb.Table(TABLE_NAME)

# Mock disease list for inference
DISEASES = [
    {"disease": "leaf_blight",      "confidence": 0.92},
    {"disease": "rust",             "confidence": 0.87},
    {"disease": "powdery_mildew",   "confidence": 0.78},
    {"disease": "bacterial_spot",   "confidence": 0.85},
    {"disease": "healthy",          "confidence": 0.95},
    {"disease": "early_blight",     "confidence": 0.81},
    {"disease": "late_blight",      "confidence": 0.76},
]


def lambda_handler(event, context):
    logger.info("ai-inference triggered. Event: %s", json.dumps(event))

    for record in event.get("Records", []):
        _process_record(record)

    return {"statusCode": 200, "body": "OK"}


def _process_record(record: dict):
    # --- Parse S3 key from event ---
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
    timestamp = datetime.now(timezone.utc).isoformat()

    # --- Step 1: Write PROCESSING record to DynamoDB ---
    try:
        table.put_item(Item={
            "userId":     user_id,
            "imageId":    image_id,
            "imageS3Key": s3_key,
            "status":     "PROCESSING",
            "timestamp":  timestamp,
            "disease":    None,
            "confidence": None,
        })
        logger.info("DynamoDB record created: userId=%s imageId=%s status=PROCESSING", user_id, image_id)
    except ClientError as e:
        logger.error("Failed to write PROCESSING record: %s", e)
        raise

    # --- Step 2: Mock inference ---
    result = random.choice(DISEASES)
    disease = result["disease"]
    confidence = result["confidence"]
    logger.info(
        "Inference result: userId=%s imageId=%s disease=%s confidence=%s",
        user_id, image_id, disease, confidence
    )

    # --- Step 3: Update DynamoDB to COMPLETED ---
    try:
        table.update_item(
            Key={"userId": user_id, "imageId": image_id},
            UpdateExpression=(
                "SET #status = :status, disease = :disease, confidence = :confidence"
            ),
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={
                ":status":     "COMPLETED",
                ":disease":    disease,
                ":confidence": str(confidence),
            },
        )
        logger.info("DynamoDB record updated: userId=%s imageId=%s status=COMPLETED", user_id, image_id)
    except ClientError as e:
        logger.error("Failed to update COMPLETED record: %s", e)
        raise
