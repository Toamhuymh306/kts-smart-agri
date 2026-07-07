# KTs Smart Agriculture — Cloud Backend

Cloud backend cho hệ thống AI chẩn đoán bệnh cây trồng, xây dựng trên AWS SAM.

## Architecture

```
User → API Gateway (JWT Auth) → Lambda functions → DynamoDB
                                       ↓
                              S3 → AI Inference → DynamoDB
                                       ↓
                              CloudWatch → SNS → Email
```

## Prerequisites

- [AWS CLI](https://aws.amazon.com/cli/) đã configured (`aws configure`)
- [AWS SAM CLI](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html)
- [Docker](https://www.docker.com/) (để build AI Inference image)
- Python 3.11

## Project Structure

```
cloud-backend/
├── template.yaml              # SAM infrastructure definition
├── samconfig.toml             # SAM deploy config
├── .gitignore
├── README.md
└── functions/
    ├── presign-url/           # POST /images/presign
    │   ├── app.py
    │   └── requirements.txt
    ├── ai-inference/          # S3-triggered, Docker/ECR
    │   ├── app.py
    │   ├── Dockerfile
    │   └── requirements.txt
    ├── get-result/            # GET /images & GET /images/{imageId}/result
    │   ├── app.py
    │   └── requirements.txt
    └── data-maintenance/      # EventBridge weekly cleanup
        ├── app.py
        └── requirements.txt
```

## Build

```bash
cd cloud-backend
sam build
```

## Validate

```bash
sam validate --lint
```

## Deploy

Lần đầu deploy (guided):

```bash
sam deploy --guided
```

Các lần sau:

```bash
sam deploy
```

Khi deploy sẽ cần nhập `AdminEmail` — địa chỉ email nhận alert CloudWatch.

## API Endpoints

Sau khi deploy, lấy `ApiEndpoint` từ Outputs của stack.

| Method | Path | Mô tả | Auth |
|--------|------|--------|------|
| POST | `/images/presign` | Lấy pre-signed URL để upload ảnh | JWT |
| GET | `/images` | Liệt kê tất cả kết quả chẩn đoán | JWT |
| GET | `/images/{imageId}/result` | Lấy kết quả chẩn đoán theo imageId | JWT |

## Authentication

Hệ thống dùng Amazon Cognito. Để lấy JWT token:

```bash
# Đăng ký user
aws cognito-idp sign-up \
  --client-id <UserPoolClientId> \
  --username your@email.com \
  --password YourPassword1

# Xác nhận email (lấy code từ email)
aws cognito-idp confirm-sign-up \
  --client-id <UserPoolClientId> \
  --username your@email.com \
  --confirmation-code 123456

# Đăng nhập lấy token
aws cognito-idp initiate-auth \
  --client-id <UserPoolClientId> \
  --auth-flow USER_PASSWORD_AUTH \
  --auth-parameters USERNAME=your@email.com,PASSWORD=YourPassword1
```

## Upload Flow

```bash
# 1. Lấy pre-signed URL
curl -X POST https://<ApiEndpoint>/prod/images/presign \
  -H "Authorization: Bearer <JWT_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"fileName": "plant.jpg"}'

# 2. Upload ảnh trực tiếp lên S3
curl -X PUT "<uploadUrl>" \
  -H "Content-Type: image/*" \
  --upload-file plant.jpg

# 3. Lấy kết quả chẩn đoán
curl https://<ApiEndpoint>/prod/images/<imageId>/result \
  -H "Authorization: Bearer <JWT_TOKEN>"
```

## ECR — Build và Push AI Inference Image

```bash
# Login ECR
aws ecr get-login-password --region ap-southeast-1 | \
  docker login --username AWS --password-stdin <AccountId>.dkr.ecr.ap-southeast-1.amazonaws.com

# Build image
docker build -t kts-smart-agri-ai-inference ./functions/ai-inference

# Tag và push
docker tag kts-smart-agri-ai-inference:latest \
  <AccountId>.dkr.ecr.ap-southeast-1.amazonaws.com/kts-smart-agri-ai-inference-prod:latest

docker push \
  <AccountId>.dkr.ecr.ap-southeast-1.amazonaws.com/kts-smart-agri-ai-inference-prod:latest
```

## Stack Outputs

| Output | Mô tả |
|--------|--------|
| `UserPoolId` | Cognito User Pool ID |
| `UserPoolClientId` | Cognito App Client ID |
| `ApiEndpoint` | API Gateway URL |
| `ImagesBucketName` | S3 bucket tên |
| `DiagnosisTableName` | DynamoDB table tên |
| `EcrRepositoryUri` | ECR repo URI cho AI image |

## Monitoring

- **CloudWatch Logs**: `/aws/lambda/kts-smart-agri-*` — retention 30 ngày
- **CloudWatch Alarms**: Lambda errors & DynamoDB system errors → SNS email
- **CloudTrail**: Audit log API calls + S3 PutObject/DeleteObject events
