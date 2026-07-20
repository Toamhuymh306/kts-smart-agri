import argparse
import json
from pathlib import Path

import boto3


def main() -> None:
    parser = argparse.ArgumentParser(description="Assign explicitly mapped legacy results to Cognito owners.")
    parser.add_argument("--table", required=True)
    parser.add_argument("--mapping", type=Path, required=True, help="JSON object mapping image_id to Cognito sub")
    parser.add_argument("--region", default="ap-southeast-1")
    parser.add_argument("--apply", action="store_true", help="Apply updates; the default is a dry run")
    args = parser.parse_args()

    mapping = json.loads(args.mapping.read_text(encoding="utf-8"))
    table = boto3.resource("dynamodb", region_name=args.region).Table(args.table)
    scan = {"ProjectionExpression": "image_id, user_id"}
    legacy_ids = []
    while True:
        response = table.scan(**scan)
        legacy_ids.extend(item["image_id"] for item in response.get("Items", []) if not item.get("user_id"))
        if not response.get("LastEvaluatedKey"):
            break
        scan["ExclusiveStartKey"] = response["LastEvaluatedKey"]

    for image_id in legacy_ids:
        owner_id = mapping.get(image_id)
        if not owner_id:
            print(f"UNOWNED {image_id}")
            continue
        print(f"{'APPLY' if args.apply else 'DRY-RUN'} {image_id} -> {owner_id}")
        if args.apply:
            table.update_item(
                Key={"image_id": image_id},
                UpdateExpression="SET user_id = :owner, ownerId = :owner",
                ConditionExpression="attribute_not_exists(user_id)",
                ExpressionAttributeValues={":owner": owner_id},
            )


if __name__ == "__main__":
    main()
