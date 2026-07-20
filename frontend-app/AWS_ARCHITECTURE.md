# AWS Architecture - KTs Smart Agriculture

# AWS Architecture - KTs Smart Agriculture

## 📊 System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        Frontend (React/Vanilla)                  │
│  ├─ Login/Register (Cognito)                                    │
│  ├─ Upload Images (Drag & Drop)                                 │
│  └─ Display Results (PlantVillage Classification)               │
└────────────────┬──────────────────────────────────────────────┘
                 │
                 ▼ HTTPS
┌─────────────────────────────────────────────────────────────────┐
│               AWS Cognito (User Authentication)                  │
│  ├─ User Pool: User Registration & Login                        │
│  ├─ Identity Pool: Temporary AWS Credentials                    │
│  └─ Issue JWT Tokens (ID Token + Access Token)                  │
└────────────────┬──────────────────────────────────────────────┘
                 │
                 ▼ Bearer Token
┌─────────────────────────────────────────────────────────────────┐
│           API Gateway (REST API Endpoints)                       │
│  ├─ POST /presign - Get S3 Pre-signed URLs                      │
│  ├─ POST /inference - Trigger Image Analysis                    │
│  └─ GET /results/{id} - Fetch Analysis Results                  │
└──┬──────────────────────────────┬─────────────────────────────┘
   │                              │
   ▼                              ▼
┌──────────────────┐       ┌──────────────────────────┐
│   S3 Bucket      │       │  Lambda Container        │
│  (Raw Images)    │       │  ├─ PyTorch Model        │
│kts-smartagri-    │       │  ├─ PlantVillage CNN     │
│dev-raw-images    │       │  └─ Docker (2.2GB)       │
│ ├─ uploads/      │       └──────────────────────────┘
│ └─ processed/    │              ▲
│                  │              │ S3 Event
│ Lifecycle Policy:│              │ Trigger
│ Delete after 30d │              │
└──────────────────┘              │
        │                         │
        │ (direct upload)  (trigger inference)
        │                         │
        └─────────────┬───────────┘
                      │
                      ▼
         ┌────────────────────────┐
         │  Lambda Orchestrator   │
         │  (Trigger Handler)     │
         └────────────────────────┘
                      │
                      ▼
┌──────────────────────────────────┐
│     DynamoDB Results Table       │
│  Table: kts-smartagri-dev-       │
│         inference-results        │
│  ├─ image_id (PK)                │
│  ├─ user_id                      │
│  ├─ predictions (crop, disease)  │
│  ├─ confidence_score              │
│  ├─ processed_at (TTL: 90 days)  │
│  └─ s3_key                       │
└──────────────────────────────────┘
        │
        │ SNS Topic
        ▼
┌──────────────────────────────────┐
│    Email Notification (SNS)      │
│  "Analysis Complete" Email        │
└──────────────────────────────────┘
```

## 🔧 AWS Services Used

| Service              | Purpose                         | Why Not SageMaker?                                       |
| -------------------- | ------------------------------- | -------------------------------------------------------- |
| **Cognito**          | User Authentication             | Free (up to 50K users)                                   |
| **API Gateway**      | REST API Endpoint               | $3.50/million requests                                   |
| **Lambda Container** | ✅ ML Model Inference (PyTorch) | **Serverless + Cost-effective** (vs SageMaker $50+/hour) |
| **S3**               | Image Storage                   | $0.023/GB stored                                         |
| **DynamoDB**         | Results Database                | On-demand: $1.25/M reads                                 |
| **SNS**              | Email Notifications             | $0.50/million emails                                     |
| **CloudWatch**       | Monitoring & Logs               | Free (5GB logs)                                          |

### Why Lambda Container instead of SageMaker?

| Criteria    | Lambda Container          | SageMaker                |
| ----------- | ------------------------- | ------------------------ |
| Cost        | Pay per invocation        | $50+/hour always running |
| Startup     | Cold start ~10-30s        | Always running           |
| Model Size  | ✅ Supports 2.2GB Docker  | Limited                  |
| Flexibility | ✅ Full control, PyTorch  | Limited frameworks       |
| Use Case    | ✅ **Batch/Event-driven** | Real-time endpoints      |

**KTs Choice: Lambda Container** = Tối ưu cho bài toán batch inference từ S3 events.

## 📝 Setup Steps

### 1. Create Cognito User Pool

```bash
# AWS CLI
aws cognito-idp create-user-pool \
  --pool-name KtsSmartAgriPool \
  --policies '{
    "PasswordPolicy": {
      "MinimumLength": 8,
      "RequireUppercase": true,
      "RequireLowercase": true,
      "RequireNumbers": true,
      "RequireSymbols": true
    }
  }' \
  --region ap-southeast-1
```

### 2. Create API Gateway

```bash
# Create REST API
aws apigateway create-rest-api \
  --name KtsSmartAgriAPI \
  --description "API for crop disease detection" \
  --region ap-southeast-1

# Create /presign resource & POST method
# Create /inference resource & POST method
# Create /results resource & GET method
```

### 3. Create S3 Buckets

```bash
# ✅ Raw images bucket (sửa lại đúng tên thực tế)
aws s3 mb s3://kts-smartagri-dev-raw-images --region ap-southeast-1

# ✅ Results bucket
aws s3 mb s3://kts-smartagri-dev-results --region ap-southeast-1

# Enable CORS
aws s3api put-bucket-cors \
  --bucket kts-smartagri-dev-raw-images \
  --cors-configuration file://cors.json
```

**cors.json:**

```json
{
  "CORSRules": [
    {
      "AllowedHeaders": ["*"],
      "AllowedMethods": ["PUT", "POST", "GET"],
      "AllowedOrigins": ["*"],
      "MaxAgeSeconds": 3000,
      "ExposeHeaders": ["ETag"]
    }
  ]
}
```

### 4. Create DynamoDB Table

```bash
# ✅ Table name: kts-smartagri-dev-inference-results
# ✅ Partition Key: image_id
aws dynamodb create-table \
  --table-name kts-smartagri-dev-inference-results \
  --attribute-definitions \
    AttributeName=image_id,AttributeType=S \
    AttributeName=user_id,AttributeType=S \
  --key-schema \
    AttributeName=image_id,KeyType=HASH \
  --global-secondary-indexes \
    'IndexName=user_id-index,Keys=[{AttributeName=user_id,KeyType=HASH}],Projection={ProjectionType=ALL},BillingMode=PAY_PER_REQUEST' \
  --billing-mode PAY_PER_REQUEST \
  --region ap-southeast-1

# Enable TTL (auto-delete after 90 days)
aws dynamodb update-time-to-live \
  --table-name kts-smartagri-dev-inference-results \
  --time-to-live-specification 'Enabled=true,AttributeName=expires_at' \
  --region ap-southeast-1
```

### 5. Deploy Lambda Functions

```bash
# ✅ Presign handler
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

# ✅ Inference handler (Lambda Container - PyTorch)
aws lambda create-function \
  --function-name kts-smartagri-inference \
  --role arn:aws:iam::YOUR_ACCOUNT:role/lambda-execution-role \
  --code ImageUri=YOUR_ACCOUNT.dkr.ecr.ap-southeast-1.amazonaws.com/kts-smartagri-inference:latest \
  --timeout 300 \
  --memory-size 3008 \
  --ephemeral-storage Size=10240 \
  --environment Variables="{RAW_IMAGES_BUCKET=kts-smartagri-dev-raw-images,RESULTS_TABLE=kts-smartagri-dev-inference-results,SNS_TOPIC_ARN=arn:aws:sns:ap-southeast-1:YOUR_ACCOUNT:crop-analysis-results}" \
  --region ap-southeast-1

# ✅ Results handler
aws lambda create-function \
  --function-name kts-smartagri-results \
  --runtime python3.11 \
  --role arn:aws:iam::YOUR_ACCOUNT:role/lambda-execution-role \
  --handler results_handler.lambda_handler \
  --zip-file fileb://results_handler.zip \
  --timeout 30 \
  --memory-size 256 \
  --environment Variables="{RESULTS_TABLE=kts-smartagri-dev-inference-results,RESULTS_BUCKET=kts-smartagri-dev-results}" \
  --region ap-southeast-1
```

## 🔐 IAM Permissions

### Lambda Execution Role Policy

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["s3:GetObject", "s3:PutObject", "s3:PutObjectAcl"],
      "Resource": [
        "arn:aws:s3:::kts-smartagri-dev-raw-images/*",
        "arn:aws:s3:::kts-smartagri-dev-results/*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "dynamodb:PutItem",
        "dynamodb:GetItem",
        "dynamodb:Query",
        "dynamodb:UpdateItem"
      ],
      "Resource": "arn:aws:dynamodb:ap-southeast-1:*:table/crop-analysis-results"
    },
    {
      "Effect": "Allow",
      "Action": ["sagemaker:InvokeEndpoint"],
      "Resource": "arn:aws:sagemaker:ap-southeast-1:*:endpoint/plantvillage-inference-endpoint"
    },
    {
      "Effect": "Allow",
      "Action": ["sns:Publish"],
      "Resource": "arn:aws:sns:ap-southeast-1:*:crop-analysis-results"
    },
    {
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "arn:aws:logs:ap-southeast-1:*:*"
    }
  ]
}
```

## 💰 Cost Estimation (Monthly)

- **Dev Environment**: ~$50-100/month
- **Production (1000 analyses/day)**: ~$200-300/month
- **Production (10000 analyses/day)**: ~$1500-2000/month

## 📚 References

- [AWS Cognito Documentation](https://docs.aws.amazon.com/cognito/)
- [AWS Lambda Container Images](https://docs.aws.amazon.com/lambda/latest/dg/images-create.html)
- [PlantVillage Dataset](https://www.kaggle.com/datasets/arjuntejaswi/plant-village)
- [AWS Well-Architected Framework](https://aws.amazon.com/architecture/well-architected/)

## 🔍 Troubleshooting

### Lambda Container Deployment

```bash
# 1. Build Docker image
docker build -t kts-smartagri-inference:latest .

# 2. Push to ECR
aws ecr get-login-password --region ap-southeast-1 | docker login --username AWS --password-stdin YOUR_ACCOUNT.dkr.ecr.ap-southeast-1.amazonaws.com
docker tag kts-smartagri-inference:latest YOUR_ACCOUNT.dkr.ecr.ap-southeast-1.amazonaws.com/kts-smartagri-inference:latest
docker push YOUR_ACCOUNT.dkr.ecr.ap-southeast-1.amazonaws.com/kts-smartagri-inference:latest

# 3. Verify function
aws lambda invoke \
  --function-name kts-smartagri-inference \
  --payload file://test-payload.json \
  --region ap-southeast-1 \
  response.json
```

### Query DynamoDB (✅ Updated)

```bash
# Query by image_id (Partition Key)
aws dynamodb get-item \
  --table-name kts-smartagri-dev-inference-results \
  --key '{"image_id":{"S":"abc12345"}}' \
  --region ap-southeast-1

# Query by user_id (GSI)
aws dynamodb query \
  --table-name kts-smartagri-dev-inference-results \
  --index-name user_id-index \
  --key-condition-expression "user_id = :uid" \
  --expression-attribute-values '{":uid":{"S":"user-123"}}' \
  --region ap-southeast-1
```
