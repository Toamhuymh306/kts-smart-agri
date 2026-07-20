import json
import logging
import os
from typing import Any

import boto3
from boto3.dynamodb.conditions import Key


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
dynamodb = boto3.resource("dynamodb")
s3_client = boto3.client("s3")

RESULTS_TABLE = os.environ.get("RESULTS_TABLE", "kts-smartagri-dev-inference-results")
USER_INDEX = os.environ.get("USER_INDEX", "user_id-index")
RAW_IMAGES_BUCKET = os.environ.get("RAW_IMAGES_BUCKET", "kts-smartagri-dev-raw-images")
RESULTS_BUCKET = os.environ.get("RESULTS_BUCKET", "kts-smartagri-dev-results")
CORS_ORIGIN = os.environ.get("CORS_ORIGIN", "*")


def _owner_id(event: dict[str, Any]) -> str:
    claims = event["requestContext"]["authorizer"]["claims"]
    owner_id = claims.get("sub")
    if not owner_id:
        raise KeyError("Cognito sub claim is missing")
    return owner_id


def _scan_id(event: dict[str, Any]) -> str | None:
    path_parameters = event.get("pathParameters") or {}
    query_parameters = event.get("queryStringParameters") or {}
    return path_parameters.get("scanId") or path_parameters.get("image_id") or query_parameters.get("image_id")


def _response(status_code: int, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": CORS_ORIGIN,
            "Access-Control-Allow-Headers": "Authorization,Content-Type",
            "Access-Control-Allow-Methods": "GET,DELETE,OPTIONS",
        },
        "body": json.dumps(payload, default=str),
    }


def _error(status_code: int, message: str) -> dict[str, Any]:
    return _response(status_code, {"error": message})


def _get_owned_item(table: Any, scan_id: str, owner_id: str) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    item = table.get_item(Key={"image_id": scan_id}, ConsistentRead=True).get("Item")
    if not item:
        return None, _error(404, "Scan result not found")
    record_owner = item.get("user_id") or item.get("ownerId")
    if record_owner != owner_id:
        return None, _error(403, "You cannot access another user's scan result")
    return item, None


def _list_results(table: Any, owner_id: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    query: dict[str, Any] = {
        "IndexName": USER_INDEX,
        "KeyConditionExpression": Key("user_id").eq(owner_id),
    }
    while True:
        response = table.query(**query)
        items.extend(item for item in response.get("Items", []) if item.get("user_id") == owner_id)
        last_key = response.get("LastEvaluatedKey")
        if not last_key:
            break
        query["ExclusiveStartKey"] = last_key
    return sorted(items, key=lambda item: item.get("createdAt") or item.get("processed_at") or "", reverse=True)


def _delete_s3_objects(item: dict[str, Any]) -> None:
    objects = [
        (item.get("rawImageBucket") or RAW_IMAGES_BUCKET, item.get("rawImageKey") or item.get("s3_key")),
        (item.get("processedImageBucket") or RESULTS_BUCKET, item.get("processedImageKey") or item.get("processed_key")),
    ]
    allowed_buckets = {RAW_IMAGES_BUCKET, RESULTS_BUCKET}
    for bucket, key in objects:
        if not key:
            continue
        if bucket not in allowed_buckets:
            raise ValueError(f"Refusing to delete object from unconfigured bucket: {bucket}")
        s3_client.delete_object(Bucket=bucket, Key=key)


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    method = event.get("httpMethod", "GET").upper()
    if method == "OPTIONS":
        return _response(204, {})
    try:
        owner_id = _owner_id(event)
        table = dynamodb.Table(RESULTS_TABLE)
        scan_id = _scan_id(event)

        if method == "GET":
            if scan_id:
                item, error = _get_owned_item(table, scan_id, owner_id)
                return error or _response(200, {"results": item, "count": 1})
            items = _list_results(table, owner_id)
            return _response(200, {"results": items, "count": len(items)})

        if method == "DELETE":
            if not scan_id:
                return _error(400, "scanId is required")
            item, error = _get_owned_item(table, scan_id, owner_id)
            if error:
                return error
            _delete_s3_objects(item)
            table.delete_item(
                Key={"image_id": scan_id},
                ConditionExpression="user_id = :owner_id",
                ExpressionAttributeValues={":owner_id": owner_id},
            )
            logger.info("Deleted scan result scan_id=%s owner_id=%s", scan_id, owner_id)
            return _response(200, {"message": "Scan history deleted", "scanId": scan_id})

        return _error(405, f"Method {method} is not allowed")
    except KeyError:
        return _error(401, "Unauthorized: valid Cognito claims are required")
    except Exception as error:
        logger.exception("Results request failed")
        return _error(500, "Unable to process scan history")
