# 🚀 KTs Smart Agriculture - Deployment Guide

## ⚡ Quick Start (5 phút)

### 1️⃣ Chạy Frontend Locally

```bash
# Cách 1: Python (nhanh nhất)
cd /d/kts-smart-agri/frontend-app
python -m http.server 8000

# Cách 2: Node.js
npx http-server

# Cách 3: Live Server (VS Code)
# Install extension "Live Server"
# Right click index.html → Open with Live Server
```

**Mở browser:** `http://localhost:8000`

### 2️⃣ Thực Hiện Flow End-to-End

#### Test Signup

```
1. Click tab "Đăng ký"
2. Nhập:
   - Họ tên: Test User
   - Email: testuser@gmail.com (hoặc email thật để nhận confirmation)
   - Password: TestPass123!
3. Click "Tạo tài khoản"
✅ Nếu không lỗi → Cognito hoạt động
```

#### Test Login

```
1. Click tab "Đăng nhập"
2. Nhập email + password vừa tạo
3. Click "Đăng nhập"
✅ Nếu không lỗi → Frontend kết nối Cognito ✓
```

#### Test Upload

```
1. Click "Kéo thả ảnh hoặc click để chọn"
2. Chọn ảnh (ảnh cây trồng hoặc ảnh gì cũng được test)
3. Click "Tải lên & Phân tích"
✅ Nếu upload thành công → Frontend kết nối API Gateway ✓
✅ Nếu có kết quả → Backend Lambda hoạt động ✓
```

---

## 🌐 Deploy Frontend to Production

### Option A: Deploy to S3 + CloudFront (Recommended)

```bash
# 1. Tạo S3 bucket cho frontend
aws s3 mb s3://kts-smartagri-frontend --region ap-southeast-1

# 2. Upload files
aws s3 sync . s3://kts-smartagri-frontend \
  --exclude ".git/*" \
  --exclude ".gitignore" \
  --exclude "README.md" \
  --exclude "backend/*" \
  --region ap-southeast-1

# 3. Enable static website hosting
aws s3 website s3://kts-smartagri-frontend \
  --index-document index.html \
  --error-document index.html

# 4. Cập nhật CORS policy
aws s3api put-bucket-cors \
  --bucket kts-smartagri-frontend \
  --cors-configuration '{
    "CORSRules": [{
      "AllowedHeaders": ["*"],
      "AllowedMethods": ["GET"],
      "AllowedOrigins": ["*"],
      "MaxAgeSeconds": 3000
    }]
  }'

# 5. (Optional) Create CloudFront distribution
aws cloudfront create-distribution \
  --origin-domain-name kts-smartagri-frontend.s3.ap-southeast-1.amazonaws.com \
  --default-root-object index.html
```

**URL:** `http://kts-smartagri-frontend.s3-website.ap-southeast-1.amazonaws.com`

### Option B: Docker Container (Enterprise)

```dockerfile
# Dockerfile
FROM node:18-alpine AS build
WORKDIR /app
COPY . .
RUN npm install -g http-server

FROM nginx:alpine
COPY --from=build /app /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

```bash
# Build & push
docker build -t kts-smartagri-frontend:latest .
docker tag kts-smartagri-frontend:latest YOUR_ACCOUNT.dkr.ecr.ap-southeast-1.amazonaws.com/kts-smartagri-frontend:latest
docker push YOUR_ACCOUNT.dkr.ecr.ap-southeast-1.amazonaws.com/kts-smartagri-frontend:latest
```

---

## 🔍 Troubleshooting

### Error: "Lỗi đăng nhập. Vui lòng thử lại"

**Nguyên nhân:** Cognito chưa configure hoặc email chưa confirm

**Giải pháp:**

Sử dụng form nhập mã xác nhận và nút **Gửi lại mã**. Không dùng quyền admin
confirm trong luồng đăng ký thông thường. Xem `COGNITO_SIGNUP.md` để cấu hình
email verification và app client SPA không có client secret.

### Error: "CORS policy blocked"

**Nguyên nhân:** API Gateway CORS chưa enable

**Giải pháp:**

```bash
# Enable CORS on API Gateway
aws apigateway put-integration-response \
  --rest-api-id zmdoxc27gg \
  --resource-id YOUR_RESOURCE_ID \
  --http-method POST \
  --status-code 200 \
  --response-parameters 'method.response.header.Access-Control-Allow-Origin='"'"'*'"'"'' \
  --region ap-southeast-1
```

### Error: "Cannot upload image"

**Nguyên nhân:** S3 bucket CORS policy chưa set

**Giải pháp:** (Đã làm ở AWS_ARCHITECTURE.md)

### Upload thành công nhưng không thấy kết quả

**Nguyên nhân:** Lambda inference chưa trigger hoặc DynamoDB query lỗi

**Giải pháp:**

```bash
# Check Lambda logs
aws logs tail /aws/lambda/kts-smartagri-inference --follow

# Check DynamoDB
aws dynamodb scan \
  --table-name kts-smartagri-dev-inference-results \
  --region ap-southeast-1
```

---

## ✅ Checklist Before Going Live

- [ ] Frontend chạy local được (step 1)
- [ ] Signup/Login hoạt động (Cognito working)
- [ ] Upload thành công (API Gateway + S3 working)
- [ ] Kết quả hiển thị (Lambda + DynamoDB working)
- [ ] Email notification nhận được (SNS working)
- [ ] Deploy to S3/CloudFront
- [ ] Test end-to-end trên prod URL
- [ ] Check CloudWatch logs không có error

---

## 📊 Monitoring Dashboard

```bash
# Real-time Lambda logs
aws logs tail /aws/lambda/kts-smartagri-presign --follow
aws logs tail /aws/lambda/kts-smartagri-inference --follow
aws logs tail /aws/lambda/kts-smartagri-results --follow

# Monitor DynamoDB
aws cloudwatch get-metric-statistics \
  --namespace AWS/DynamoDB \
  --metric-name ConsumedReadCapacityUnits \
  --dimensions Name=TableName,Value=kts-smartagri-dev-inference-results \
  --start-time 2024-01-01T00:00:00Z \
  --end-time 2024-01-02T00:00:00Z \
  --period 3600 \
  --statistics Sum
```

---

## 🎯 Next Steps

1. **Local testing** → Chạy Step 1 & 2
2. **Production** → Deploy Step 3 (S3 + CloudFront)
3. **Monitoring** → Setup CloudWatch dashboards
4. **Scaling** → Thêm caching, CDN, auto-scaling

---

**Support:** Hỏi gì có issue thì report lại 🚀
