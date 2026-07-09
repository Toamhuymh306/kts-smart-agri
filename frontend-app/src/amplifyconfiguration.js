// Amplify configuration — giá trị thực đọc từ .env
// Sau khi deploy backend, lấy UserPoolId và UserPoolClientId từ SAM Outputs
// rồi điền vào file .env (xem .env.example)

const amplifyConfig = {
  Auth: {
    Cognito: {
      userPoolId: import.meta.env.VITE_COGNITO_USER_POOL_ID,
      userPoolClientId: import.meta.env.VITE_COGNITO_USER_POOL_CLIENT_ID,
      loginWith: {
        email: true,
      },
      signUpVerificationMethod: 'code',
    },
  },
}

export default amplifyConfig
