import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

import boto3


s3_client = boto3.client("s3")
BUCKET_NAME = os.environ.get("S3_BUCKET", "kts-smartagri-dev-raw-images")
PRESIGN_EXPIRATION = 900
CORS_ORIGIN = os.environ.get("CORS_ORIGIN", "*")
ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}


def _response(status_code, payload):
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": CORS_ORIGIN,
            "Access-Control-Allow-Headers": "Authorization,Content-Type",
            "Access-Control-Allow-Methods": "POST,OPTIONS",
        },
        "body": json.dumps(payload),
    }


def lambda_handler(event, context):
    if event.get("httpMethod", "POST").upper() == "OPTIONS":
        return _response(204, {})
    try:
        owner_id = event["requestContext"]["authorizer"]["claims"]["sub"]
        body = json.loads(event.get("body") or "{}")
        filename = Path(body.get("filename", "")).name
        content_type = body.get("contentType")
        if not filename or content_type not in ALLOWED_CONTENT_TYPES:
            return _response(400, {"error": "A valid image filename and contentType are required"})

        scan_id = str(uuid.uuid4())
        date_path = datetime.now(timezone.utc).strftime("%Y/%m/%d")
        s3_key = f"uploads/{owner_id}/{date_path}/{scan_id}_{filename}"
        metadata = {
            "user-id": owner_id,
            "upload-time": datetime.now(timezone.utc).isoformat(),
            "original-name": filename,
        }
        upload_url = s3_client.generate_presigned_url(
            "put_object",
            Params={"Bucket": BUCKET_NAME, "Key": s3_key, "ContentType": content_type, "Metadata": metadata},
            ExpiresIn=PRESIGN_EXPIRATION,
        )
        return _response(
            200,
            {"upload_url": upload_url, "s3_key": s3_key, "image_id": scan_id, "metadata": metadata, "expiration": PRESIGN_EXPIRATION},
        )
    except (KeyError, TypeError):
        return _response(401, {"error": "Unauthorized: valid Cognito claims are required"})
    except (ValueError, json.JSONDecodeError):
        return _response(400, {"error": "Invalid request body"})
