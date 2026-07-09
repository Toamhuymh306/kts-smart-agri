"""
Lambda: data-maintenance
Triggered by EventBridge Scheduler every Sunday at 00:00 UTC.
Deletes S3 images older than RETENTION_DAYS and archives DynamoDB records.

Flow:
  1. List all S3 objects under prefix uploads/
  2. Filter objects with LastModified > RETENTION_DAYS ago
  3. Batch delete qualifying S3 objects
  4. Archive DynamoDB records ONLY for successfully deleted objects
  5. Log cleaned count to CloudWatch Logs

Fix #7: Archive only records whose S3 object was actually deleted successfully.
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
try:
    RETENTION_DAYS = int(os.environ.get("RETENTION_DAYS", "30"))
except ValueError:
    logger.warning("Invalid RETENTION_DAYS value, using default 30")
    RETENTION_DAYS = 30

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
        return {"cleaned": 0, "archived": 0}

    # Delete S3 objects and get back only the ones successfully deleted
    successfully_deleted = _delete_s3_objects(old_objects)
    logger.info("Successfully deleted %d S3 objects", len(successfully_deleted))

    # Archive DynamoDB records only for successfully deleted objects
    archived_count = _archive_dynamodb_records(successfully_deleted)

    logger.info(
        "Maintenance complete. Deleted S3 objects: %d, Archived DynamoDB records: %d",
        len(successfully_deleted), archived_count
    )

    return {"cleaned": len(successfully_deleted), "archived": archived_count}


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


def _delete_s3_objects(objects: list) -> list:
    """
    Batch delete S3 objects (max 1000 per request).
    Returns list of objects that were SUCCESSFULLY deleted.
    Fix #7: Only return confirmed-deleted objects for archiving.
    """
    successfully_deleted = []
    batch_size = 1000

    for i in range(0, len(objects), batch_size):
        batch = objects[i: i + batch_size]
        key_map = {obj["Key"]: obj for obj in batch}

        delete_payload = {
            "Objects": [{"Key": key} for key in key_map]
        }

        try:
            response = s3_client.delete_objects(
                Bucket=BUCKET_NAME,
                Delete=delete_payload
            )

            # Only track confirmed Deleted keys
            for deleted in response.get("Deleted", []):
                key = deleted["Key"]
                if key in key_map:
                    successfully_deleted.append(key_map[key])

            errors = response.get("Errors", [])
            if errors:
                logger.warning(
                    "S3 delete errors for %d objects: %s",
                    len(errors), errors
                )

            logger.info(
                "Batch result: %d deleted, %d errors",
                len(response.get("Deleted", [])), len(errors)
            )

        except ClientError as e:
            logger.error("Failed to delete S3 objects batch: %s", e)

    return successfully_deleted


def _archive_dynamodb_records(successfully_deleted_objects: list) -> int:
    """
    Update DynamoDB records to status=ARCHIVED.
    Only called with objects confirmed deleted from S3.
    Key format: uploads/{userId}/{imageId}/{fileName}
    """
    archived_count = 0
    updated_at = datetime.now(timezone.utc).isoformat()

    for obj in successfully_deleted_objects:
        parts = obj["Key"].split("/")
        if len(parts) < 4 or parts[0] != "uploads":
            logger.warning("Skipping unexpected key format: %s", obj["Key"])
            continue

        user_id = parts[1]
        image_id = parts[2]

        try:
            table.update_item(
                Key={"userId": user_id, "imageId": image_id},
                UpdateExpression="SET #status = :status, updatedAt = :updatedAt",
                ExpressionAttributeNames={"#status": "status"},
                ExpressionAttributeValues={
                    ":status":    "ARCHIVED",
                    ":updatedAt": updated_at,
                },
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
