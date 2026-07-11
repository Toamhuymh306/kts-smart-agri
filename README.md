# KTS Smart Agriculture AI Platform

Plant disease diagnosis system using ensemble ResNet50 + LeNet models, built on AWS serverless architecture.

---

## Prerequisites

- AWS CLI v2 configured (`aws configure`)
- SAM CLI
- Docker Desktop (must be running before `sam build`)
- Python 3.11+
- Node.js v20+ and npm

---

## Run Locally (frontend dev server)

```bash
cd frontend-app
npm install
npm run dev
```

Open http://localhost:5173. The `.env` file must exist with valid AWS backend values (see Deploy section below).

---

## Deploy

### Step 1 — Copy model files

```bash
# Windows CMD
copy ai-service\best_resnet_model.pth cloud-backend\functions\ai-inference\
copy ai-service\best_lenet_model.pth  cloud-backend\functions\ai-inference\
```

### Step 2 — Deploy WAF stack (us-east-1, required for CloudFront)

```bash
cd cloud-backend
aws cloudformation deploy \
  --template-file waf-stack.yaml \
  --stack-name kts-smart-agri-waf \
  --parameter-overrides Environment=prod \
  --region us-east-1
```

Get the WAF ARN:

```bash
aws cloudformation describe-stacks \
  --stack-name kts-smart-agri-waf \
  --region us-east-1 \
  --query "Stacks[0].Outputs[?OutputKey=='WafWebAclArn'].OutputValue" \
  --output text
```

### Step 3 — Update samconfig.toml

Open `cloud-backend/samconfig.toml` and fill in your values:

```toml
parameter_overrides = "AdminEmail=<YOUR_EMAIL> Environment=prod WafAclArn=<WAF_ARN_FROM_STEP_2>"
```

### Step 4 — Build and deploy backend

```bash
cd cloud-backend
sam build
sam deploy
```

At the end of `sam deploy`, note the **Outputs** table — you need `UserPoolId`, `UserPoolClientId`, and `ApiEndpoint`.

### Step 5 — Configure and build frontend

Create `frontend-app/.env`:

```env
VITE_COGNITO_USER_POOL_ID=<UserPoolId>
VITE_COGNITO_USER_POOL_CLIENT_ID=<UserPoolClientId>
VITE_API_BASE_URL=https://<ApiEndpoint>
```

```bash
cd frontend-app
npm install
npm run build
```

### Step 6 — Confirm SNS email subscription

Check the inbox for `AdminEmail` and click **Confirm subscription** in the email from AWS SNS. Without this, CloudWatch Alarms will not send email notifications.

---

## Clean Up

Empty S3 buckets first (CloudFormation cannot delete non-empty buckets), then delete the stacks.

```bash
# Replace <ACCOUNT_ID> with your AWS Account ID

# 1. Empty S3 buckets
aws s3 rm s3://kts-smart-agri-images-<ACCOUNT_ID>-prod     --recursive --region ap-southeast-1
aws s3 rm s3://kts-smart-agri-archive-<ACCOUNT_ID>-prod    --recursive --region ap-southeast-1
aws s3 rm s3://kts-smart-agri-cloudtrail-<ACCOUNT_ID>-prod --recursive --region ap-southeast-1

# 2. Delete SAM backend stack
aws cloudformation delete-stack \
  --stack-name kts-smart-agri-cloud-backend \
  --region ap-southeast-1

# 3. Delete WAF stack
aws cloudformation delete-stack \
  --stack-name kts-smart-agri-waf \
  --region us-east-1
```

Wait for both stacks to finish deleting before verifying in the AWS Console under CloudFormation.

---

## Project Structure

```
kts-smart-agri/
├── ai-service/                  # Pre-trained model weights (.pth files)
├── cloud-backend/
│   ├── functions/
│   │   ├── presign-url/         # Lambda: generate S3 pre-signed PUT URL
│   │   ├── ai-inference/        # Lambda: Docker image, ResNet50 + LeNet ensemble
│   │   ├── get-result/          # Lambda: read diagnosis result from DynamoDB
│   │   └── data-maintenance/    # Lambda: weekly cleanup of old images
│   ├── template.yaml            # SAM template (all AWS resources)
│   ├── waf-stack.yaml           # CloudFormation WAF stack (us-east-1)
│   └── samconfig.toml           # SAM deploy configuration
└── frontend-app/                # React + Vite frontend
    ├── src/
    ├── .env                     # Runtime config (not committed)
    └── .env.example             # Template for .env
```
