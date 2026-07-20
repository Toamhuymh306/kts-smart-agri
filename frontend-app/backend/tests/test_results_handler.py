import importlib.util
import json
import sys
import types
import unittest
from pathlib import Path


class Key:
    def __init__(self, name):
        self.name = name

    def eq(self, value):
        return self.name, value


class BootstrapBoto3(types.ModuleType):
    def resource(self, name):
        return None

    def client(self, name):
        return None


boto3 = BootstrapBoto3("boto3")
conditions = types.ModuleType("boto3.dynamodb.conditions")
conditions.Key = Key
sys.modules.setdefault("boto3", boto3)
sys.modules.setdefault("boto3.dynamodb", types.ModuleType("boto3.dynamodb"))
sys.modules.setdefault("boto3.dynamodb.conditions", conditions)

HANDLER_PATH = Path(__file__).resolve().parents[1] / "lambda" / "results_handler.py"
spec = importlib.util.spec_from_file_location("results_handler", HANDLER_PATH)
handler = importlib.util.module_from_spec(spec)
spec.loader.exec_module(handler)


class FakeTable:
    def __init__(self, items):
        self.items = {item["image_id"]: dict(item) for item in items}
        self.deleted = []

    def query(self, **kwargs):
        _, owner_id = kwargs["KeyConditionExpression"]
        return {"Items": [item for item in self.items.values() if item.get("user_id") == owner_id]}

    def get_item(self, Key, **kwargs):
        item = self.items.get(Key["image_id"])
        return {"Item": item} if item else {}

    def delete_item(self, Key, **kwargs):
        self.deleted.append(Key["image_id"])
        self.items.pop(Key["image_id"], None)


class FakeDynamoDB:
    def __init__(self, table):
        self.table = table

    def Table(self, name):
        return self.table


class FakeS3:
    def __init__(self):
        self.deleted = []

    def delete_object(self, **kwargs):
        self.deleted.append((kwargs["Bucket"], kwargs["Key"]))


def event(owner_id, method="GET", scan_id=None):
    payload = {
        "httpMethod": method,
        "requestContext": {"authorizer": {"claims": {"sub": owner_id}}},
    }
    if scan_id:
        payload["pathParameters"] = {"scanId": scan_id}
    return payload


class ResultsAuthorizationTests(unittest.TestCase):
    def setUp(self):
        self.table = FakeTable(
            [
                {
                    "image_id": "a1",
                    "user_id": "user-a",
                    "s3_key": "uploads/user-a/a1.jpg",
                    "processedImageKey": "processed/user-a/a1.jpg",
                },
                {"image_id": "b1", "user_id": "user-b", "s3_key": "uploads/user-b/b1.jpg"},
                {"image_id": "legacy", "s3_key": "uploads/legacy.jpg"},
            ]
        )
        self.s3 = FakeS3()
        handler.dynamodb = FakeDynamoDB(self.table)
        handler.s3_client = self.s3

    def invoke(self, payload):
        response = handler.lambda_handler(payload, None)
        return response["statusCode"], json.loads(response["body"])

    def test_user_a_cannot_see_user_b_or_legacy_results(self):
        status, body = self.invoke(event("user-a"))
        self.assertEqual(status, 200)
        self.assertEqual([item["image_id"] for item in body["results"]], ["a1"])

    def test_user_a_cannot_delete_user_b_result(self):
        status, _ = self.invoke(event("user-a", "DELETE", "b1"))
        self.assertEqual(status, 403)
        self.assertEqual(self.table.deleted, [])
        self.assertEqual(self.s3.deleted, [])

    def test_user_a_can_delete_own_result_and_raw_image(self):
        status, _ = self.invoke(event("user-a", "DELETE", "a1"))
        self.assertEqual(status, 200)
        self.assertEqual(self.table.deleted, ["a1"])
        self.assertEqual(
            self.s3.deleted,
            [
                (handler.RAW_IMAGES_BUCKET, "uploads/user-a/a1.jpg"),
                (handler.RESULTS_BUCKET, "processed/user-a/a1.jpg"),
            ],
        )


if __name__ == "__main__":
    unittest.main()
