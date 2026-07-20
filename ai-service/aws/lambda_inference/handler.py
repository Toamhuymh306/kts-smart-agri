import json
import re
from urllib.parse import unquote_plus
from typing import Any

from runtime import PlantDiseaseRuntime


RUNTIME = PlantDiseaseRuntime()


REQUEST_ID_PATTERN = re.compile(r"([0-9a-fA-F-]{8,})")


def _extract_request_id_from_key(input_key: str) -> str | None:
    filename = input_key.rsplit("/", 1)[-1]
    head = filename.split("_", 1)[0]
    if REQUEST_ID_PATTERN.fullmatch(head):
        return head
    return None


def _decode_record_body(record: dict[str, Any]) -> dict[str, Any]:
    body = record.get("body")
    if body is None:
        raise ValueError("SQS record missing body.")

    if isinstance(body, str):
        return json.loads(body)
    if isinstance(body, dict):
        return body
    raise TypeError(f"Unsupported record body type: {type(body)}")


def _payloads_from_s3_event(event_payload: dict[str, Any]) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    for s3_record in event_payload.get("Records", []):
        if s3_record.get("eventSource") != "aws:s3":
            continue
        bucket = s3_record["s3"]["bucket"]["name"]
        key = unquote_plus(s3_record["s3"]["object"]["key"])
        payloads.append(
            {
                "input_bucket": bucket,
                "input_key": key,
                "request_id": _extract_request_id_from_key(key),
            }
        )
    return payloads


def _parse_record_to_payloads(record: dict[str, Any]) -> list[dict[str, Any]]:
    payload = _decode_record_body(record)
    if isinstance(payload, dict) and isinstance(payload.get("Records"), list):
        return _payloads_from_s3_event(payload)
    return [payload]


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    if not event.get("Records"):
        return RUNTIME.process_inference_message(event)

    records = event.get("Records", [])
    results = []
    for record in records:
        payloads = _parse_record_to_payloads(record)
        for payload in payloads:
            result = RUNTIME.process_inference_message(payload)
            results.append(result)

    return {"processed": len(results), "results": results}
