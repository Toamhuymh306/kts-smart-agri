/**
 * API service layer — Axios instance với JWT interceptor tự động
 * Tất cả request đều attach Bearer token từ Cognito session
 */
import axios from 'axios'
import { fetchAuthSession } from 'aws-amplify/auth'

const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Request interceptor — đính kèm JWT token vào mọi request
// API Gateway Cognito Authorizer expect raw JWT (không có prefix "Bearer ")
apiClient.interceptors.request.use(
  async (config) => {
    try {
      const session = await fetchAuthSession()
      const token = session.tokens?.idToken?.toString()
      if (token) {
        config.headers.Authorization = token
      }
    } catch (err) {
      console.warn('Could not get auth session:', err)
    }
    return config
  },
  (error) => Promise.reject(error),
)

// Response interceptor — normalize lỗi
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Token hết hạn hoặc không hợp lệ — redirect về login
      window.location.href = '/login'
    }
    return Promise.reject(error)
  },
)

export default apiClient
