"""
Lambda: presign-url
Generate S3 Pre-signed PUT URL for direct image upload.

Route: POST /images/presign
Body:  { "fileName": "plant.jpg", "contentType": "image/jpeg" }
Auth:  Cognito JWT (userId extracted from claims)

Fix #2: Validate fileName extension, path traversal, and contentType.
"""

import json
import logging
import os
import re
import uuid

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

s3_client = boto3.client("s3")

BUCKET_NAME = os.environ["IMAGES_BUCKET_NAME"]
PRESIGN_TTL_SECONDS = 300  # 5 minutes

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
ALLOWED_CONTENT_TYPES = {
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/webp",
}
# Block path traversal and special characters
UNSAFE_FILENAME_PATTERN = re.compile(r"[/\\\.]{2,}|[^\w.\-]")


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
        file_name = body.get("fileName", "").strip()
        content_type = body.get("contentType", "").strip().lower()
        if not file_name:
            raise ValueError("fileName is required")
        if not content_type:
            raise ValueError("contentType is required")
    except (ValueError, json.JSONDecodeError) as e:
        logger.error("Invalid request body: %s", e)
        return _response(400, {"message": f"Bad Request: {e}"})

    # --- Validate fileName ---
    validation_error = _validate_file_name(file_name)
    if validation_error:
        return _response(400, {"message": validation_error})

    # --- Validate contentType ---
    if content_type not in ALLOWED_CONTENT_TYPES:
        return _response(400, {
            "message": f"Bad Request: contentType must be one of {sorted(ALLOWED_CONTENT_TYPES)}"
        })

    # --- Generate imageId and S3 key ---
    image_id = str(uuid.uuid4())
    # Use only the sanitized base filename (no directory parts)
    safe_name = os.path.basename(file_name)
    s3_key = f"uploads/{user_id}/{image_id}/{safe_name}"

    # --- Create pre-signed PUT URL with exact content type ---
    try:
        upload_url = s3_client.generate_presigned_url(
            ClientMethod="put_object",
            Params={
                "Bucket": BUCKET_NAME,
                "Key": s3_key,
                "ContentType": content_type,
            },
            ExpiresIn=PRESIGN_TTL_SECONDS,
        )
    except ClientError as e:
        logger.error("Failed to generate pre-signed URL: %s", e)
        return _response(500, {"message": "Internal Server Error"})

    logger.info(
        "Pre-signed URL generated: userId=%s imageId=%s key=%s contentType=%s",
        user_id, image_id, s3_key, content_type
    )

    return _response(200, {
        "uploadUrl": upload_url,
        "imageId": image_id,
        "s3Key": s3_key,
        "contentType": content_type,
    })


def _validate_file_name(file_name: str) -> str | None:
    """Return error message if fileName is invalid, else None."""
    # Check extension
    _, ext = os.path.splitext(file_name.lower())
    if ext not in ALLOWED_EXTENSIONS:
        return f"Bad Request: file extension must be one of {sorted(ALLOWED_EXTENSIONS)}"

    # Block path traversal: .., /, \
    if ".." in file_name or "/" in file_name or "\\" in file_name:
        return "Bad Request: fileName must not contain path separators or '..'"

    # Block other unsafe characters (allow word chars, dot, dash)
    base_name = os.path.basename(file_name)
    if not re.match(r"^[\w.\-]+$", base_name):
        return "Bad Request: fileName contains invalid characters"

    # Length limit
    if len(file_name) > 255:
        return "Bad Request: fileName too long (max 255 characters)"

    return None


def _response(status_code: int, body: dict) -> dict:
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type,Authorization",
        },
        "body": json.dumps(body),
    }
