"""
Lambda: get-result
Return diagnosis results from DynamoDB for authenticated users.

Routes:
  GET    /images/{imageId}/result  -> single result by imageId
  GET    /images                   -> paginated list for userId, sorted newest first
  DELETE /images/{imageId}         -> delete diagnosis record + S3 object

Auth: Cognito JWT (userId extracted from claims, never from request)
"""

import base64
import json
import logging
import os
from decimal import Decimal

import boto3
from boto3.dynamodb.conditions import Key
from botocore.config import Config
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb = boto3.resource("dynamodb")

_region = os.environ.get("AWS_REGION", "ap-southeast-1")
s3_client = boto3.client(
    "s3",
    region_name=_region,
    config=Config(signature_version="s3v4", s3={"addressing_style": "virtual"}),
)

TABLE_NAME      = os.environ["DYNAMODB_TABLE_NAME"]
IMAGES_BUCKET   = os.environ.get("IMAGES_BUCKET_NAME", "")
ARCHIVE_BUCKET  = os.environ.get("ARCHIVE_BUCKET_NAME", "")
IMAGE_URL_TTL   = 900  # 15 minutes

table = dynamodb.Table(TABLE_NAME)

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE     = 100


def lambda_handler(event, context):
    logger.info("get-result invoked. Path: %s Method: %s", event.get("path"), event.get("httpMethod"))

    # --- Extract userId from JWT claims ---
    try:
        claims = event["requestContext"]["authorizer"]["claims"]
        user_id = claims["sub"]
    except (KeyError, TypeError) as e:
        logger.error("Failed to extract userId from JWT claims: %s", e)
        return _response(401, {"message": "Unauthorized"})

    http_method = event.get("httpMethod", "GET")
    path_params = event.get("pathParameters") or {}
    image_id    = path_params.get("imageId")

    if http_method == "DELETE" and image_id:
        return _delete_result(user_id, image_id)
    elif image_id:
        return _get_single_result(user_id, image_id)
    else:
        return _list_results(user_id, event.get("queryStringParameters") or {})


# ============================================================
# GET /images/{imageId}/result
# ============================================================
def _get_single_result(user_id: str, image_id: str) -> dict:
    logger.info("Getting result: userId=%s imageId=%s", user_id, image_id)

    try:
        response = table.get_item(Key={"userId": user_id, "imageId": image_id})
    except ClientError as e:
        logger.error("DynamoDB GetItem failed: %s", e)
        return _response(500, {"message": "Internal Server Error"})

    item = response.get("Item")
    if not item:
        return _response(404, {"message": "Diagnosis not found"})

    if item.get("status") == "PROCESSING":
        return _response(202, {
            "message": "Diagnosis is still processing",
            "imageId": image_id,
            "status": "PROCESSING",
        })

    return _response(200, _format_item(item))


# ============================================================
# GET /images
# ============================================================
def _list_results(user_id: str, query_params: dict) -> dict:
    logger.info("Listing results for userId=%s", user_id)

    try:
        limit = min(int(query_params.get("limit", DEFAULT_PAGE_SIZE)), MAX_PAGE_SIZE)
    except (ValueError, TypeError):
        limit = DEFAULT_PAGE_SIZE

    query_kwargs = {
        "IndexName": "userId-createdAt-index",
        "KeyConditionExpression": Key("userId").eq(user_id),
        "ScanIndexForward": False,
        "Limit": limit,
    }

    next_token = query_params.get("nextToken")
    if next_token:
        try:
            last_key = json.loads(base64.b64decode(next_token).decode())
            query_kwargs["ExclusiveStartKey"] = last_key
        except Exception:
            return _response(400, {"message": "Bad Request: invalid nextToken"})

    try:
        response = table.query(**query_kwargs)
    except ClientError as e:
        logger.error("DynamoDB Query failed: %s", e)
        return _response(500, {"message": "Internal Server Error"})

    items = [_format_item(item) for item in response.get("Items", [])]
    result = {"items": items, "count": len(items)}

    last_evaluated = response.get("LastEvaluatedKey")
    if last_evaluated:
        result["nextToken"] = base64.b64encode(
            json.dumps(last_evaluated, default=str).encode()
        ).decode()

    return _response(200, result)


# ============================================================
# DELETE /images/{imageId}
# ============================================================
def _delete_result(user_id: str, image_id: str) -> dict:
    logger.info("Deleting result: userId=%s imageId=%s", user_id, image_id)

    # 1. Get item to find s3Key before deleting
    try:
        response = table.get_item(Key={"userId": user_id, "imageId": image_id})
    except ClientError as e:
        logger.error("DynamoDB GetItem failed: %s", e)
        return _response(500, {"message": "Internal Server Error"})

    item = response.get("Item")
    if not item:
        return _response(404, {"message": "Diagnosis not found"})

    s3_key = item.get("imageS3Key")

    # 2. Delete from DynamoDB
    try:
        table.delete_item(Key={"userId": user_id, "imageId": image_id})
    except ClientError as e:
        logger.error("DynamoDB DeleteItem failed: %s", e)
        return _response(500, {"message": "Internal Server Error"})

    # 3. Delete S3 objects (best effort — don't fail if already gone)
    if s3_key:
        _delete_s3_object(IMAGES_BUCKET, s3_key)
        # Archive bucket uses "processed/" prefix instead of "uploads/"
        archive_key = s3_key.replace("uploads/", "processed/", 1)
        _delete_s3_object(ARCHIVE_BUCKET, archive_key)

    logger.info("Deleted: userId=%s imageId=%s", user_id, image_id)
    return _response(200, {"message": "Deleted successfully", "imageId": image_id})


def _delete_s3_object(bucket: str, key: str):
    if not bucket or not key:
        return
    try:
        s3_client.delete_object(Bucket=bucket, Key=key)
        logger.info("Deleted S3 object: s3://%s/%s", bucket, key)
    except ClientError as e:
        logger.warning("Could not delete S3 object s3://%s/%s: %s", bucket, key, e)


# ============================================================
# Helpers
# ============================================================
def _get_image_url(s3_key: str) -> str | None:
    """Generate presigned GET URL — try archive bucket first, then images bucket."""
    if not s3_key:
        return None
    archive_key = s3_key.replace("uploads/", "processed/", 1)
    for bucket, key in [(ARCHIVE_BUCKET, archive_key), (IMAGES_BUCKET, s3_key)]:
        if not bucket:
            continue
        try:
            return s3_client.generate_presigned_url(
                ClientMethod="get_object",
                Params={"Bucket": bucket, "Key": key},
                ExpiresIn=IMAGE_URL_TTL,
            )
        except ClientError:
            continue
    return None


def _format_item(item: dict) -> dict:
    s3_key = item.get("imageS3Key")
    return {
        "imageId":      item.get("imageId"),
        "imageS3Key":   s3_key,
        "imageUrl":     _get_image_url(s3_key),
        "disease":      item.get("disease"),
        "confidence":   float(item["confidence"]) if item.get("confidence") is not None else None,
        "status":       item.get("status"),
        "timestamp":    item.get("timestamp"),
        "createdAt":    item.get("createdAt"),
        "updatedAt":    item.get("updatedAt"),
        "errorMessage": item.get("errorMessage"),
    }


def _response(status_code: int, body: dict) -> dict:
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type,Authorization",
        },
        "body": json.dumps(body, default=str),
    }
