# KTS Smart Agriculture — Frontend App

Web app chẩn đoán bệnh cây trồng bằng AI. Người dùng upload ảnh, hệ thống AI tự động phân tích và trả kết quả.

## Tech Stack

- **React 19** + **Vite 8**
- **Tailwind CSS v4** (via `@tailwindcss/vite`)
- **AWS Amplify v6** — xác thực Cognito
- **React Router v7** — routing
- **Axios** — HTTP client với JWT interceptor tự động

## Cài đặt

```bash
# 1. Cài dependencies
npm install

# 2. Tạo file .env từ template
copy .env.example .env
```

Sau đó điền các giá trị vào `.env`:

| Biến | Mô tả | Lấy từ đâu |
|------|-------|------------|
| `VITE_COGNITO_USER_POOL_ID` | Cognito User Pool ID | SAM Output: `UserPoolId` |
| `VITE_COGNITO_USER_POOL_CLIENT_ID` | Cognito App Client ID | SAM Output: `UserPoolClientId` |
| `VITE_API_BASE_URL` | Base URL API | SAM Output: `CloudFrontDomain` |

## Chạy development

```bash
npm run dev
```

## Build production

```bash
npm run build
```

## Cấu trúc project

```
src/
├── amplifyconfiguration.js   # Cấu hình AWS Amplify (đọc từ .env)
├── main.jsx                  # Entry point
├── App.jsx                   # Router & layout wrapper
├── index.css                 # Tailwind CSS import
│
├── context/
│   └── AuthContext.jsx       # Auth state + Cognito hooks
│
├── components/
│   ├── Layout.jsx            # Navbar + footer wrapper
│   ├── ProtectedRoute.jsx    # Route guard (redirect nếu chưa login)
│   ├── StatusBadge.jsx       # Badge: PROCESSING / COMPLETED / ARCHIVED
│   └── DiseaseCard.jsx       # Card hiển thị kết quả bệnh + confidence
│
├── pages/
│   ├── LoginPage.jsx         # Đăng nhập
│   ├── RegisterPage.jsx      # Đăng ký tài khoản
│   ├── ConfirmEmailPage.jsx  # Xác nhận email OTP
│   ├── HomePage.jsx          # Dashboard / trang chủ
│   ├── UploadPage.jsx        # Upload ảnh (drag & drop + presign + S3 PUT)
│   ├── ResultsPage.jsx       # Danh sách lịch sử chẩn đoán
│   └── ResultDetailPage.jsx  # Chi tiết 1 kết quả (auto-polling khi PROCESSING)
│
└── services/
    ├── api.js                # Axios instance với JWT interceptor
    └── imageService.js       # getPresignedUrl, uploadToS3, getDiagnosisResult, listDiagnoses
```

## Luồng hoạt động

```
1. Đăng ký → Xác nhận email → Đăng nhập (Cognito)
2. Upload ảnh
   a. POST /images/presign → nhận { uploadUrl, imageId, s3Key }
   b. PUT ảnh thẳng lên S3 (không qua API Gateway)
3. S3 trigger Lambda AI inference → ghi DynamoDB
4. GET /images/{imageId}/result → polling mỗi 3s cho đến khi COMPLETED
5. Xem danh sách: GET /images
```

## Responsive

App hỗ trợ cả mobile và desktop. Navbar tự ẩn label text trên màn hình nhỏ, chỉ hiển thị icon.
