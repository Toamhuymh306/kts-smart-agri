"""
Lambda: get-result
Return diagnosis results from DynamoDB for authenticated users.

Routes:
  GET /images/{imageId}/result  → single result by imageId
  GET /images                   → list all results for userId

Auth: Cognito JWT (userId extracted from claims, never from request)
"""

import json
import logging
import os

import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb = boto3.resource("dynamodb")

TABLE_NAME = os.environ["DYNAMODB_TABLE_NAME"]
table = dynamodb.Table(TABLE_NAME)


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
        return _list_results(user_id)


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


def _list_results(user_id: str) -> dict:
    """GET /images"""
    logger.info("Listing results for userId=%s", user_id)

    try:
        response = table.query(
            KeyConditionExpression=Key("userId").eq(user_id)
        )
    except ClientError as e:
        logger.error("DynamoDB Query failed: %s", e)
        return _response(500, {"message": "Internal Server Error"})

    items = [_format_item(item) for item in response.get("Items", [])]
    logger.info("Found %d records for userId=%s", len(items), user_id)

    return _response(200, {"items": items, "count": len(items)})


def _format_item(item: dict) -> dict:
    return {
        "imageId":    item.get("imageId"),
        "imageS3Key": item.get("imageS3Key"),
        "disease":    item.get("disease"),
        "confidence": item.get("confidence"),
        "status":     item.get("status"),
        "timestamp":  item.get("timestamp"),
    }


def _response(status_code: int, body: dict) -> dict:
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
        },
        "body": json.dumps(body),
    }
