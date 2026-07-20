# 🌾 KTs Smart Agriculture - AI Image Analysis Platform v2.0

**Nền tảng AI chuyên nghiệp cho phân tích bệnh cây trồng sử dụng PlantVillage Dataset**

## ✨ Tính Năng Chính v2.0

- ✅ **Đăng Ký & Đăng Nhập** - Xác thực an toàn với AWS Cognito
- 📸 **Upload Ảnh** - Drag & drop, multiple images, real-time preview
- 🤖 **AI Phân Tích** - PlantVillage CNN classification (38 classes)
- 📊 **Dashboard Kết Quả** - Hiển thị chi tiết bệnh/sức khỏe cây
- 📜 **Lịch Sử** - Track tất cả phân tích (lưu trữ vĩnh viễn)
- 🔔 **Email Alerts** - Thông báo khi phân tích hoàn tất
- 🎨 **Giao Diện Chuyên Nghiệp** - Responsive, modern design
- 🔐 **Enterprise Security** - JWT tokens, pre-signed URLs, encryption

## 🏗️ Architecture

```
Frontend (Vanilla JS/HTML/CSS)
    ↓
AWS Cognito (Auth)
    ↓
API Gateway (REST)
    ├→ Lambda Presign Handler
    ├→ Lambda Container (PyTorch Inference)
    └→ Lambda Results Handler
    ↓
S3 (Raw Images) → Lambda Container (PlantVillage Model)
    ↓
DynamoDB (kts-smartagri-dev-inference-results) + SNS (Email)
```

**Key Difference**: Uses **Lambda Container** (PyTorch 2.2GB Docker) instead of SageMaker for cost efficiency.

Chi tiết: [AWS_ARCHITECTURE.md](./AWS_ARCHITECTURE.md)

## 📋 PlantVillage Dataset Support

**14 loại cây, 38 lớp bệnh:**

| Cây | Số Bệnh | Ví Dụ |
|-----|---------|------|
| Apple | 4 | Healthy, Scab, Black Rot, Cedar Rust |
| Tomato | 9 | Healthy, Late Blight, Early Blight, Mosaic Virus |
| Potato | 3 | Healthy, Early Blight, Late Blight |
| Corn | 4 | Healthy, Cercospora, Common Rust, Northern Leaf Blight |
| Pepper | 2 | Healthy, Bacterial Spot |
| *13 loại khác* | 16+ | *Chi tiết xem config.js* |

## 🚀 Quick Start

### Frontend Setup

```bash
# Clone repo
git clone <repo_url> kts-smart-agri
cd kts-smart-agri/frontend-app

# Cập nhật AWS credentials
vim js/config.js
# Sửa: userPoolId, clientId, apiGateway endpoint

# Chạy server (Python)
python -m http.server 8000

# Hoặc Node.js
npx http-server

# Mở: http://localhost:8000
```

### Backend Deployment

Xem: [backend/README.md](./backend/README.md)

## 📁 Project Structure

```
frontend-app/
├── index.html              # UI chính (Login/Signup/Upload)
├── css/style.css           # Styling hiện đại
├── js/
│   ├── config.js           # AWS config (cần update)
│   ├── auth.js             # Cognito authentication
│   └── app.js              # Logic chính ứng dụng
├── backend/
│   ├── lambda/
│   │   ├── presign_handler.py      # Pre-signed URL
│   │   ├── inference_handler.py    # SageMaker trigger
│   │   ├── results_handler.py      # Get results
│   │   └── requirements.txt
│   └── README.md           # Backend setup guide
├── AWS_ARCHITECTURE.md     # Kiến trúc AWS chi tiết
├── README.md              # File này
└── .gitignore
```

## ⚙️ Configuration

### 1. Cập nhật `js/config.js`

```javascript
const AWS_CONFIG = {
  cognito: {
    userPoolId: "ap-southeast-1_YOUR_POOL_ID",  // ← Update
    clientId: "YOUR_CLIENT_ID",                  // ← Update
  },
  apiGateway: {
    endpoint: "https://YOUR_API_ID.execute-api.ap-southeast-1.amazonaws.com/dev",
  },
  s3: {
    bucket: "your-bucket-name",
  }
};
```

### 2. Deploy Backend Lambda Functions

```bash
cd backend/lambda

# Package & deploy (xem backend/README.md)
aws lambda create-function ...
```

### 3. Setup Cognito User Pool

```bash
aws cognito-idp create-user-pool --pool-name KtsSmartAgriPool ...
```

Chi tiết: [AWS_ARCHITECTURE.md](./AWS_ARCHITECTURE.md)

## 🔐 Authentication Flow

```
1. User đăng ký/đăng nhập
   ↓
2. Cognito xác thực & cấp ID Token
   ↓
3. Token được lưu localStorage
   ↓
4. Mỗi request gửi token trong Authorization header
   ↓
5. Lambda validate token từ API Gateway
```

## 📸 Upload Flow

```
1. User chọn ảnh (drag & drop hoặc click)
   ↓
2. Preview ảnh trong browser
   ↓
3. Click "Tải lên & Phân tích"
   ↓
4. Request /presign API → nhận pre-signed URL
   ↓
5. Upload ảnh trực tiếp lên S3 (không qua backend)
   ↓
6. S3 trigger Lambda inference
   ↓
7. SageMaker phân tích → lưu results DynamoDB
   ↓
8. Frontend poll /results API → hiển thị kết quả
```

## 🎨 Tuỳ Chỉnh

### Thay đổi màu theme

```css
/* css/style.css */
:root {
  --primary-color: #2ecc71;      /* Xanh */
  --secondary-color: #3498db;    /* Xanh dương */
  --danger-color: #e74c3c;       /* Đỏ */
}
```

### Thêm crop/disease mới

```javascript
// js/config.js
plantVillage: {
  crops: ["Apple", "Tomato", "YourCrop"],  // ← Add
  diseaseClasses: {
    YourCrop: ["Healthy", "Disease1", "Disease2"]  // ← Add
  }
}
```

## 📊 Monitoring

### CloudWatch Logs

```bash
# Xem Lambda logs
aws logs tail /aws/lambda/kts-smartagri-presign --follow
aws logs tail /aws/lambda/kts-smartagri-inference --follow
```

### DynamoDB Metrics

```bash
# Query results
aws dynamodb query \
  --table-name crop-analysis-results \
  --key-condition-expression "user_id = :uid" \
  --expression-attribute-values "{\":uid\":{\"S\":\"user-123\"}}"
```

## 💰 Cost Estimation

| Component | Dev | Prod (1K/day) |
|-----------|-----|---------------|
| Cognito | $0 | $25 |
| API Gateway | $0.35 | $3.50 |
| Lambda | $0 | $15 |
| S3 | $0.50 | $5 |
| SageMaker | $50 | $500 |
| DynamoDB | $1 | $10 |
| SNS | $0 | $0.50 |
| **Total** | **~$52** | **~$559** |

## 🐛 Troubleshooting

| Problem | Solution |
|---------|----------|
| CORS Error | Enable S3 CORS policy |
| 401 Unauthorized | Check Cognito token, verify API Gateway authorizer |
| SageMaker timeout | Increase Lambda timeout (up to 900s) |
| DynamoDB throttling | Switch to on-demand billing |
| Email not received | Check SNS subscription confirmed |

## 📞 Support

- 📧 Liên hệ: team@ktssmartag.com
- 🐛 Report bugs: GitHub Issues
- 💡 Feature requests: GitHub Discussions

## 📚 References

- [AWS Cognito Docs](https://docs.aws.amazon.com/cognito/)
- [PlantVillage Dataset](https://www.kaggle.com/datasets/arjuntejaswi/plant-village)
- [SageMaker Inference](https://docs.aws.amazon.com/sagemaker/)
- [API Gateway](https://docs.aws.amazon.com/apigateway/)

## 📄 License

Proprietary - KTs Smart Agriculture © 2024-2025

---

**Version:** 2.0.0  
**Last Updated:** 2026-07-10  
**Maintained by:** Team KTs


## 📋 Tính Năng

- ✅ **Xác thực Cognito** - Đăng nhập an toàn với AWS Cognito
- 📸 **Upload Ảnh** - Hỗ trợ drag & drop và chọn file
- 👁️ **Preview Ảnh** - Xem trước trước khi tải lên
- 📊 **Thanh tiến trình** - Theo dõi tiến độ upload
- 📜 **Lịch sử** - Giữ lưu các lần tải lên
- 🎨 **Giao diện đẹp** - Thiết kế hiện đại, responsive
- 🔔 **Thông báo** - Toast notifications cho mọi hành động

## 🚀 Cài Đặt

### 1. Cấu hình AWS

Cập nhật file `js/config.js` với thông tin của nhóm KTs:

```javascript
const AWS_CONFIG = {
  cognito: {
    userPoolId: "ap-southeast-1_YOUR_POOL_ID",
    clientId: "YOUR_CLIENT_ID",
  },
  apiGateway: {
    endpoint: "https://YOUR_API_ENDPOINT/dev",
  },
  s3: {
    bucket: "your-bucket-name",
  },
};
```

### 2. Yêu cầu Backend (Lambda + API Gateway)

Backend cần cung cấp endpoint `/presign` để tạo pre-signed URL cho S3:

```python
# Lambda Function - Python
import json
import boto3
from datetime import datetime, timedelta

s3 = boto3.client('s3')

def lambda_handler(event, context):
    try:
        body = json.loads(event['body'])
        filename = body.get('filename')
        content_type = body.get('contentType')

        # Tạo unique key
        s3_key = f"uploads/{datetime.now().strftime('%Y/%m/%d')}/{filename}"

        # Tạo pre-signed URL (valid 15 phút)
        presigned_url = s3.generate_presigned_url(
            'put_object',
            Params={
                'Bucket': 'kts-smart-agri-uploads',
                'Key': s3_key,
                'ContentType': content_type
            },
            ExpiresIn=900
        )

        return {
            'statusCode': 200,
            'body': json.dumps({
                'upload_url': presigned_url,
                's3_key': s3_key
            })
        }
    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }
```

### 3. Chạy Ứng Dụng

Đơn giản mở `index.html` trong trình duyệt:

```bash
# Nếu dùng Python
python -m http.server 8000

# Hoặc dùng Node.js
npx http-server

# Hoặc mở trực tiếp: file:///path/to/index.html
```

## 📁 Cấu Trúc Thư Mục

```
frontend-app/
├── index.html          # Main HTML
├── css/
│   └── style.css       # Styling (Tailwind-like)
├── js/
│   ├── config.js       # Cấu hình AWS
│   ├── auth.js         # Xác thực Cognito
│   └── app.js          # Logic chính
└── README.md
```

## 🔐 Quy Trình Upload

1. **Đăng nhập** → Cognito xác thực → Nhận ID Token
2. **Chọn ảnh** → Preview trước khi tải
3. **Gọi API** → Lấy pre-signed URL từ Backend
4. **Upload S3** → Tải file trực tiếp lên S3
5. **Phân tích** → Gợi ý gọi AI service để xử lý

```
User → Cognito Login → Get ID Token
  ↓
Select Images → Preview in Browser
  ↓
POST /presign (with ID Token) → Get Pre-signed URL from API Gateway
  ↓
PUT /presigned_url (Direct to S3) → Upload Image
  ↓
Display Results + Save to History
```

## 🎯 Tuỳ Chỉnh

### Thay Đổi Theme

Edit biến CSS trong `css/style.css`:

```css
:root {
  --primary-color: #2ecc71; /* Màu xanh chính */
  --secondary-color: #3498db; /* Màu phụ */
  --danger-color: #e74c3c; /* Màu lỗi */
}
```

### Thêm Tính Năng

Mở `js/app.js` và thêm method vào class `ImageUploadApp`:

```javascript
async myNewFeature() {
    // Thêm code ở đây
}
```

## 🐛 Troubleshooting

### CORS Error

Đảm bảo S3 bucket có CORS policy:

```json
[
  {
    "AllowedHeaders": ["*"],
    "AllowedMethods": ["PUT", "POST", "GET"],
    "AllowedOrigins": ["*"],
    "MaxAgeSeconds": 3000
  }
]
```

### Cognito Login Fails

- Kiểm tra User Pool ID và Client ID đúng
- Đảm bảo user account đã được confirm
- Kiểm tra region (ap-southeast-1)

### Upload Fails

- Kiểm tra S3 bucket tồn tại
- Kiểm tra IAM permissions
- Kiểm tra pre-signed URL còn hiệu lực

## 📞 Support

Liên hệ nhóm KTs Smart Agriculture để:

- Cập nhật cấu hình AWS
- Tích hợp AI service
- Báo cáo lỗi hoặc tính năng mới

---

**Version:** 1.0.0  
**Last Updated:** 2026-07-10  
**License:** Private - KTs Smart Agriculture
