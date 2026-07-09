"""
Lambda: get-result
Return diagnosis results from DynamoDB for authenticated users.

Routes:
  GET /images/{imageId}/result  -> single result by imageId
  GET /images                   -> paginated list for userId, sorted newest first

Auth: Cognito JWT (userId extracted from claims, never from request)

Fix #4: Added pagination via limit + nextToken query params.
Fix #8: Uses GSI userId-createdAt-index with ScanIndexForward=False (newest first).
"""

import base64
import json
import logging
import os
from decimal import Decimal

import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb = boto3.resource("dynamodb")

TABLE_NAME = os.environ["DYNAMODB_TABLE_NAME"]
table = dynamodb.Table(TABLE_NAME)

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


def lambda_handler(event, context):
    logger.info("get-result invoked. Path: %s", event.get("path"))

    # --- Extract userId from JWT claims ---
    try:
        claims = event["requestContext"]["authorizer"]["claims"]
        user_id = claims["sub"]
    except (KeyError, TypeError) as e:
        logger.error("Failed to extract userId from JWT claims: %s", e)
        return _response(401, {"message": "Unauthorized"})

    path_params = event.get("pathParameters") or {}
    image_id = path_params.get("imageId")

    if image_id:
        return _get_single_result(user_id, image_id)
    else:
        return _list_results(user_id, event.get("queryStringParameters") or {})


def _get_single_result(user_id: str, image_id: str) -> dict:
    """GET /images/{imageId}/result"""
    logger.info("Getting result: userId=%s imageId=%s", user_id, image_id)

    try:
        response = table.get_item(
            Key={"userId": user_id, "imageId": image_id}
        )
    except ClientError as e:
        logger.error("DynamoDB GetItem failed: %s", e)
        return _response(500, {"message": "Internal Server Error"})

    item = response.get("Item")
    if not item:
        logger.info("Record not found: userId=%s imageId=%s", user_id, image_id)
        return _response(404, {"message": "Diagnosis not found"})

    status = item.get("status")
    if status == "PROCESSING":
        return _response(202, {
            "message": "Diagnosis is still processing",
            "imageId": image_id,
            "status": status,
        })

    return _response(200, _format_item(item))


def _list_results(user_id: str, query_params: dict) -> dict:
    """GET /images — paginated, sorted newest first via GSI createdAt."""
    logger.info("Listing results for userId=%s params=%s", user_id, query_params)

    # Parse pagination params
    try:
        limit = min(int(query_params.get("limit", DEFAULT_PAGE_SIZE)), MAX_PAGE_SIZE)
    except (ValueError, TypeError):
        limit = DEFAULT_PAGE_SIZE

    next_token = query_params.get("nextToken")

    query_kwargs = {
        "IndexName": "userId-createdAt-index",
        "KeyConditionExpression": Key("userId").eq(user_id),
        "ScanIndexForward": False,  # newest first
        "Limit": limit,
    }

    # Decode pagination token (base64-encoded JSON of LastEvaluatedKey)
    if next_token:
        import base64
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
    logger.info("Found %d records for userId=%s", len(items), user_id)

    result = {"items": items, "count": len(items)}

    # Encode next page token if more results exist
    last_evaluated = response.get("LastEvaluatedKey")
    if last_evaluated:
        import base64
        result["nextToken"] = base64.b64encode(
            json.dumps(last_evaluated, default=str).encode()
        ).decode()

    return _response(200, result)


def _format_item(item: dict) -> dict:
    return {
        "imageId":      item.get("imageId"),
        "imageS3Key":   item.get("imageS3Key"),
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
