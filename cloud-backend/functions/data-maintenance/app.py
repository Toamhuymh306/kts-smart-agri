"""
Lambda: data-maintenance
Triggered by EventBridge Scheduler every Sunday at 00:00 UTC.
Deletes S3 images older than RETENTION_DAYS and archives DynamoDB records.

Flow:
  1. List all S3 objects under prefix uploads/
  2. Filter objects with LastModified > RETENTION_DAYS ago
  3. Batch delete qualifying S3 objects
  4. Update corresponding DynamoDB records to status=ARCHIVED
  5. Log cleaned count to CloudWatch Logs
"""

import logging
import os
from datetime import datetime, timedelta, timezone

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

s3_client = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")

BUCKET_NAME = os.environ["IMAGES_BUCKET_NAME"]
TABLE_NAME = os.environ["DYNAMODB_TABLE_NAME"]
RETENTION_DAYS = int(os.environ.get("RETENTION_DAYS", "30"))

table = dynamodb.Table(TABLE_NAME)


def lambda_handler(event, context):
    logger.info(
        "data-maintenance started. Bucket=%s Table=%s RetentionDays=%d",
        BUCKET_NAME, TABLE_NAME, RETENTION_DAYS
    )

    cutoff_date = datetime.now(timezone.utc) - timedelta(days=RETENTION_DAYS)
    logger.info("Cutoff date: %s", cutoff_date.isoformat())

    old_objects = _list_old_objects(cutoff_date)
    logger.info("Found %d objects to clean", len(old_objects))

    if not old_objects:
        logger.info("Nothing to clean. Exiting.")
        return {"cleaned": 0}

    deleted_count = _delete_s3_objects(old_objects)
    archived_count = _archive_dynamodb_records(old_objects)

    logger.info(
        "Maintenance complete. Deleted S3 objects: %d, Archived DynamoDB records: %d",
        deleted_count, archived_count
    )

    return {"cleaned": deleted_count, "archived": archived_count}


def _list_old_objects(cutoff_date: datetime) -> list:
    """List S3 objects under uploads/ older than cutoff_date."""
    old_objects = []
    paginator = s3_client.get_paginator("list_objects_v2")

    try:
        pages = paginator.paginate(Bucket=BUCKET_NAME, Prefix="uploads/")
        for page in pages:
            for obj in page.get("Contents", []):
                if obj["LastModified"] < cutoff_date:
                    old_objects.append(obj)
    except ClientError as e:
        logger.error("Failed to list S3 objects: %s", e)
        raise

    return old_objects


def _delete_s3_objects(objects: list) -> int:
    """Batch delete S3 objects (max 1000 per request)."""
    deleted_count = 0
    batch_size = 1000

    for i in range(0, len(objects), batch_size):
        batch = objects[i : i + batch_size]
        delete_payload = {
            "Objects": [{"Key": obj["Key"]} for obj in batch]
        }

        try:
            response = s3_client.delete_objects(
                Bucket=BUCKET_NAME,
                Delete=delete_payload
            )
            deleted = len(response.get("Deleted", []))
            errors = response.get("Errors", [])
            deleted_count += deleted

            if errors:
                logger.warning("S3 delete errors: %s", errors)

            logger.info("Deleted batch of %d S3 objects", deleted)
        except ClientError as e:
            logger.error("Failed to delete S3 objects batch: %s", e)

    return deleted_count


def _archive_dynamodb_records(objects: list) -> int:
    """
    Update DynamoDB records to status=ARCHIVED for deleted S3 objects.
    Key format: uploads/{userId}/{imageId}/{fileName}
    """
    archived_count = 0

    for obj in objects:
        parts = obj["Key"].split("/")
        # Expected: uploads / userId / imageId / fileName
        if len(parts) < 4 or parts[0] != "uploads":
            logger.warning("Skipping unexpected key format: %s", obj["Key"])
            continue

        user_id = parts[1]
        image_id = parts[2]

        try:
            table.update_item(
                Key={"userId": user_id, "imageId": image_id},
                UpdateExpression="SET #status = :status",
                ExpressionAttributeNames={"#status": "status"},
                ExpressionAttributeValues={":status": "ARCHIVED"},
                ConditionExpression="attribute_exists(userId)",
            )
            archived_count += 1
        except table.meta.client.exceptions.ConditionalCheckFailedException:
            logger.warning(
                "DynamoDB record not found, skipping: userId=%s imageId=%s",
                user_id, image_id
            )
        except ClientError as e:
            logger.error(
                "Failed to archive DynamoDB record userId=%s imageId=%s: %s",
                user_id, image_id, e
            )

    return archived_count
