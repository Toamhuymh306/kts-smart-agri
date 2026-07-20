# Deployment guide for AI, history, and email verification

## AI Lambda container

The build context is `ai-service`. Both state-dict checkpoints are copied into
`${LAMBDA_TASK_ROOT}/model`; `.dockerignore` intentionally does not exclude `.pth`.

```powershell
cd ai-service
docker build -t kts-smartagri-inference:local -f aws/lambda_inference/Dockerfile .
docker run --rm --entrypoint python -e MODEL_NAME=resnet kts-smartagri-inference:local -c "from runtime import load_assets; a=load_assets(); print(a.model_name, len(a.class_names))"
```

Deploy through the checked-in script:

```powershell
./aws/deploy_lambda_container.ps1 -AwsRegion ap-southeast-1 -AccountId <ACCOUNT_ID> -EcrRepository <ECR_REPOSITORY> -LambdaFunctionName kts-smartagri-inference -ProcessedBucket kts-smartagri-dev-results -ResultTable kts-smartagri-dev-inference-results -ModelName resnet
```

Set `MODEL_NAME` to `resnet` (default) or `lenet`. The Lambda also requires
`PROCESSED_BUCKET` and `RESULT_TABLE`. Its role needs `s3:GetObject`,
`s3:PutObject`, `dynamodb:PutItem`, SQS permissions when SQS is used, and logs.

## Results Lambda and API Gateway

Package `frontend-app/backend/lambda/results_handler.py` as the ZIP Lambda. Set:

- `RESULTS_TABLE=kts-smartagri-dev-inference-results`
- `USER_INDEX=user_id-index`
- `RAW_IMAGES_BUCKET=kts-smartagri-dev-raw-images`
- `RESULTS_BUCKET=kts-smartagri-dev-results`
- `CORS_ORIGIN=<frontend origin>` (use `*` only for local development)

The existing table remains keyed by `image_id`. It must have the existing
`user_id-index` GSI with `user_id` as its partition key. The Lambda role needs
`dynamodb:GetItem`, `dynamodb:Query`, `dynamodb:DeleteItem`, and `s3:DeleteObject`
for the two configured buckets.

Configure Cognito-authorized routes using Lambda proxy integration:

- `GET /results`
- `GET /results/{scanId}` (optional; query `?image_id=` is also supported)
- `DELETE /results/{scanId}`
- `OPTIONS /results` and `OPTIONS /results/{scanId}`

Deploy the API stage after adding `DELETE`. The Cognito authorizer must validate
the bearer ID token and make the `sub` claim available to the Lambda.

## Legacy DynamoDB records

Records without `user_id` are not returned by the GSI query and cannot be deleted
through the user API. Do not assign them automatically. First create a reviewed
JSON mapping such as `{"image-id": "cognito-sub"}`, then run:

```powershell
python frontend-app/backend/migrate_legacy_results.py --table kts-smartagri-dev-inference-results --mapping owner-map.json
```

That command is a dry run. Add `--apply` only after reviewing every mapping and
backing up the table. No schema migration is needed.

## Cognito

Follow `frontend-app/COGNITO_SIGNUP.md`. In particular, enable self-registration,
auto-verify email, configure email delivery, and use an SPA app client without a
secret.

## Post-deployment checklist

- Cold-start both `MODEL_NAME` values and confirm model load/inference logs.
- Upload JPEG, PNG, and WebP images and confirm a DynamoDB result is created.
- Verify User A cannot list or delete User B's scan; verify User A can delete its
  own DynamoDB record and both S3 objects.
- Log out User A, log in User B, and verify no User A history remains in the UI.
- Register a new user, confirm delivery, wrong/expired-code messages, resend
  cooldown, successful confirmation, and login.
- Inspect browser CORS preflights for `Authorization`, `GET`, `POST`, and `DELETE`.
