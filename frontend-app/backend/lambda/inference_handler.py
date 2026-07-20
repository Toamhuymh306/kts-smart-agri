import json
import logging
import os
from urllib.parse import unquote_plus

import boto3


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
lambda_client = boto3.client("lambda")
INFERENCE_LAMBDA = os.environ.get("INFERENCE_LAMBDA", "kts-smartagri-inference")


def lambda_handler(event, context):
    """Forward an S3 event to the container without embedding image bytes."""
    results = []
    for record in event.get("Records", []):
        bucket = record["s3"]["bucket"]["name"]
        key = unquote_plus(record["s3"]["object"]["key"])
        scan_id = key.rsplit("/", 1)[-1].split("_", 1)[0]
        response = lambda_client.invoke(
            FunctionName=INFERENCE_LAMBDA,
            InvocationType="RequestResponse",
            Payload=json.dumps({"bucket": bucket, "s3_key": key, "image_id": scan_id}),
        )
        payload = json.loads(response["Payload"].read().decode("utf-8"))
        if response.get("FunctionError"):
            raise RuntimeError(f"Inference Lambda failed for scan {scan_id}: {payload.get('errorMessage', 'unknown error')}")
        results.append(payload)
    logger.info("Forwarded %d image(s) to %s", len(results), INFERENCE_LAMBDA)
    return {"processed": len(results), "results": results}
