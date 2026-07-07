"""
Lambda: presign-url
Generate S3 Pre-signed PUT URL for direct image upload.

Route: POST /images/presign
Body:  { "fileName": "image.jpg" }
Auth:  Cognito JWT (userId extracted from claims)
"""

import json
import logging
import os
import uuid

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

s3_client = boto3.client("s3")

BUCKET_NAME = os.environ["IMAGES_BUCKET_NAME"]
PRESIGN_TTL_SECONDS = 300  # 5 minutes


def lambda_handler(event, context):
    logger.info("presign-url invoked")

    # --- Extract userId from Cognito JWT claims ---
    try:
        claims = event["requestContext"]["authorizer"]["claims"]
        user_id = claims["sub"]
    except (KeyError, TypeError) as e:
        logger.error("Failed to extract userId from JWT claims: %s", e)
        return _response(401, {"message": "Unauthorized"})

    # --- Parse request body ---
    try:
        body = json.loads(event.get("body") or "{}")
        file_name = body["fileName"]
        if not file_name:
            raise ValueError("fileName is empty")
    except (KeyError, ValueError, json.JSONDecodeError) as e:
        logger.error("Invalid request body: %s", e)
        return _response(400, {"message": "Bad Request: 'fileName' is required"})

    # --- Generate imageId and S3 key ---
    image_id = str(uuid.uuid4())
    s3_key = f"uploads/{user_id}/{image_id}/{file_name}"

    # --- Create pre-signed PUT URL ---
    try:
        upload_url = s3_client.generate_presigned_url(
            ClientMethod="put_object",
            Params={
                "Bucket": BUCKET_NAME,
                "Key": s3_key,
                "ContentType": "image/*",
            },
            ExpiresIn=PRESIGN_TTL_SECONDS,
        )
    except ClientError as e:
        logger.error("Failed to generate pre-signed URL: %s", e)
        return _response(500, {"message": "Internal Server Error"})

    logger.info("Pre-signed URL generated: userId=%s imageId=%s key=%s", user_id, image_id, s3_key)

    return _response(200, {
        "uploadUrl": upload_url,
        "imageId": image_id,
        "s3Key": s3_key,
    })


def _response(status_code: int, body: dict) -> dict:
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
        },
        "body": json.dumps(body),
    }
