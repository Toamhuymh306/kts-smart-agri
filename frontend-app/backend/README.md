# Backend - KTs Smart Agriculture Lambda Functions

## 📋 Overview

This folder contains AWS Lambda functions for the KTs Smart Agriculture platform.

## 📁 File Structure

```
backend/
├── lambda/
│   ├── presign_handler.py      # Generate S3 pre-signed URLs
│   ├── inference_handler.py    # Trigger SageMaker inference
│   ├── results_handler.py      # Fetch analysis results
│   └── requirements.txt         # Python dependencies
├── templates/
│   └── cloudformation.yaml     # Infrastructure as Code
└── README.md
```

## 🚀 Deployment

### 1. Install Dependencies

```bash
cd backend/lambda
pip install -r requirements.txt -t ./layer/python/
```

### 2. Create Lambda Layer (for dependencies)

```bash
cd layer
zip -r ../lambda-layer.zip .
aws lambda publish-layer-version \
  --layer-name kts-smartagri-dependencies \
  --zip-file fileb://../lambda-layer.zip \
  --compatible-runtimes python3.11 \
  --region ap-southeast-1
```

### 3. Deploy Lambda Functions

```bash
# Package presign_handler
zip presign_handler.zip presign_handler.py

# Create Lambda function
aws lambda create-function \
  --function-name kts-smartagri-presign \
  --runtime python3.11 \
  --role arn:aws:iam::YOUR_ACCOUNT:role/lambda-execution-role \
  --handler presign_handler.lambda_handler \
  --zip-file fileb://presign_handler.zip \
  --timeout 30 \
  --memory-size 256 \
  --environment Variables="{S3_BUCKET=kts-smartagri-dev-raw-images}" \
  --region ap-southeast-1
```

### 4. Repeat for other functions

```bash
# inference_handler
aws lambda create-function \
  --function-name kts-smartagri-inference \
  --runtime python3.11 \
  --role arn:aws:iam::YOUR_ACCOUNT:role/lambda-execution-role \
  --handler inference_handler.lambda_handler \
  --zip-file fileb://inference_handler.zip \
  --timeout 120 \
  --memory-size 3008 \
  --environment Variables="{SAGEMAKER_ENDPOINT=plantvillage-inference-endpoint,RESULTS_TABLE=crop-analysis-results,RESULTS_BUCKET=kts-smartagri-dev-results,SNS_TOPIC_ARN=arn:aws:sns:ap-southeast-1:YOUR_ACCOUNT:crop-analysis-results}" \
  --region ap-southeast-1

# results_handler
aws lambda create-function \
  --function-name kts-smartagri-results \
  --runtime python3.11 \
  --role arn:aws:iam::YOUR_ACCOUNT:role/lambda-execution-role \
  --handler results_handler.lambda_handler \
  --zip-file fileb://results_handler.zip \
  --timeout 30 \
  --memory-size 256 \
  --environment Variables="{RESULTS_TABLE=crop-analysis-results,RESULTS_BUCKET=kts-smartagri-dev-results}" \
  --region ap-southeast-1
```

## 🔗 API Gateway Integration

### Create REST API

```bash
# Create API
API_ID=$(aws apigateway create-rest-api \
  --name KtsSmartAgriAPI \
  --description "Crop Disease Detection API" \
  --region ap-southeast-1 \
  --query 'id' --output text)

# Get root resource ID
ROOT_ID=$(aws apigateway get-resources \
  --rest-api-id $API_ID \
  --region ap-southeast-1 \
  --query 'items[0].id' --output text)

# Create /presign resource
PRESIGN_ID=$(aws apigateway create-resource \
  --rest-api-id $API_ID \
  --parent-id $ROOT_ID \
  --path-part presign \
  --region ap-southeast-1 \
  --query 'id' --output text)

# Create POST method
aws apigateway put-method \
  --rest-api-id $API_ID \
  --resource-id $PRESIGN_ID \
  --http-method POST \
  --authorization-type AWS_IAM \
  --region ap-southeast-1

# Create Lambda integration
aws apigateway put-integration \
  --rest-api-id $API_ID \
  --resource-id $PRESIGN_ID \
  --http-method POST \
  --type AWS_PROXY \
  --integration-http-method POST \
  --uri "arn:aws:apigateway:ap-southeast-1:lambda:path/2015-03-31/functions/arn:aws:lambda:ap-southeast-1:YOUR_ACCOUNT:function:kts-smartagri-presign/invocations" \
  --region ap-southeast-1

# Give API Gateway permission to invoke Lambda
aws lambda add-permission \
  --function-name kts-smartagri-presign \
  --statement-id AllowAPIGatewayInvoke \
  --action lambda:InvokeFunction \
  --principal apigateway.amazonaws.com \
  --region ap-southeast-1

# Deploy API
aws apigateway create-deployment \
  --rest-api-id $API_ID \
  --stage-name dev \
  --region ap-southeast-1
```

## 🔐 Cognito Authorization

### Create Authorizer in API Gateway

```bash
# Create Cognito Authorizer
aws apigateway create-authorizer \
  --rest-api-id $API_ID \
  --name KtsSmartAgriAuthorizer \
  --type COGNITO_USER_POOLS \
  --provider-arn "arn:aws:cognito-idp:ap-southeast-1:YOUR_ACCOUNT:userpool/ap-southeast-1_YOUR_POOL_ID" \
  --identity-source "method.request.header.Authorization" \
  --region ap-southeast-1
```

## 📊 S3 Event Trigger

### Configure S3 to trigger inference Lambda

```bash
# Add S3 permission to Lambda
aws lambda add-permission \
  --function-name kts-smartagri-inference \
  --statement-id AllowS3Invoke \
  --action lambda:InvokeFunction \
  --principal s3.amazonaws.com \
  --source-arn "arn:aws:s3:::kts-smartagri-dev-raw-images" \
  --region ap-southeast-1

# Create S3 notification
aws s3api put-bucket-notification-configuration \
  --bucket kts-smartagri-dev-raw-images \
  --notification-configuration '{
    "LambdaFunctionConfigurations": [
      {
        "LambdaFunctionArn": "arn:aws:lambda:ap-southeast-1:YOUR_ACCOUNT:function:kts-smartagri-inference",
        "Events": ["s3:ObjectCreated:*"],
        "Filter": {
          "Key": {
            "FilterRules": [
              {
                "Name": "prefix",
                "Value": "uploads/"
              }
            ]
          }
        }
      }
    ]
  }' \
  --region ap-southeast-1
```

## 🧪 Testing

### Test presign_handler

```bash
aws lambda invoke \
  --function-name kts-smartagri-presign \
  --payload '{"requestContext":{"authorizer":{"claims":{"sub":"user-123"}}}, "body":"{\"filename\":\"test.jpg\",\"contentType\":\"image/jpeg\"}"}' \
  --region ap-southeast-1 \
  response.json

cat response.json
```

### Test with curl

```bash
# Get presigned URL
curl -X POST https://YOUR_API_ID.execute-api.ap-southeast-1.amazonaws.com/dev/presign \
  -H "Authorization: YOUR_ID_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"filename":"tomato.jpg","contentType":"image/jpeg"}'

# Upload image
curl -X PUT "PRESIGNED_URL" \
  --data-binary @tomato.jpg \
  -H "Content-Type: image/jpeg"

# Get results
curl -X GET "https://YOUR_API_ID.execute-api.ap-southeast-1.amazonaws.com/dev/results" \
  -H "Authorization: YOUR_ID_TOKEN"
```

## 📝 Environment Variables

| Variable                          | Purpose                        | Example                                              |
| --------------------------------- | ------------------------------ | ---------------------------------------------------- |
| `S3_BUCKET` / `RAW_IMAGES_BUCKET` | Raw images bucket              | `kts-smartagri-dev-raw-images`                       |
| `RESULTS_BUCKET`                  | Results storage bucket         | `kts-smartagri-dev-results`                          |
| `RESULTS_TABLE`                   | DynamoDB results table         | `kts-smartagri-dev-inference-results`                |
| `INFERENCE_LAMBDA`                | Lambda function name (PyTorch) | `kts-smartagri-inference`                            |
| `SNS_TOPIC_ARN`                   | SNS topic for notifications    | `arn:aws:sns:ap-southeast-1:*:crop-analysis-results` |

## 🐛 Troubleshooting

### Lambda timeout errors

Increase timeout in Lambda configuration (especially for inference):

```bash
aws lambda update-function-configuration \
  --function-name kts-smartagri-inference \
  --timeout 300 \
  --region ap-southeast-1
```

### Lambda Container Cold Start

Cold start ~10-30s is normal for 2.2GB Docker container. To optimize:

```bash
# Increase memory (faster CPU)
aws lambda update-function-configuration \
  --function-name kts-smartagri-inference \
  --memory-size 3008 \
  --region ap-southeast-1

# Or use Provisioned Concurrency for always-warm instances
aws lambda put-provisioned-concurrency-config \
  --function-name kts-smartagri-inference \
  --provisioned-concurrent-executions 1 \
  --qualifier LIVE \
  --region ap-southeast-1
```

### DynamoDB throttling

Switch to on-demand billing:

```bash
aws dynamodb update-billing-mode \
  --table-name kts-smartagri-dev-inference-results \
  --billing-mode PAY_PER_REQUEST \
  --region ap-southeast-1
```

### Query DynamoDB (✅ Updated)

```bash
# Get specific result by image_id
aws dynamodb get-item \
  --table-name kts-smartagri-dev-inference-results \
  --key '{"image_id":{"S":"abc12345"}}' \
  --region ap-southeast-1

# Query all results for a user (using GSI)
aws dynamodb query \
  --table-name kts-smartagri-dev-inference-results \
  --index-name user_id-index \
  --key-condition-expression "user_id = :uid" \
  --expression-attribute-values '{":uid":{"S":"user-123"}}' \
  --region ap-southeast-1
```

## 📚 References

- [AWS Lambda Python Runtime](https://docs.aws.amazon.com/lambda/latest/dg/python-handler.html)
- [Boto3 Documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/index.html)
- [AWS Lambda Best Practices](https://docs.aws.amazon.com/lambda/latest/dg/best-practices.html)
