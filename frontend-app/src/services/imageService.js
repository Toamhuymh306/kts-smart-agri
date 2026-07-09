/**
 * Image service — tất cả API calls liên quan đến upload và kết quả chẩn đoán
 */
import axios from 'axios'
import apiClient from './api'

/**
 * Bước 1: Lấy pre-signed URL từ backend để upload ảnh lên S3
 * @param {string} fileName - tên file ảnh
 * @returns {{ uploadUrl: string, imageId: string, s3Key: string }}
 */
export async function getPresignedUrl(fileName) {
  const response = await apiClient.post('/images/presign', { fileName })
  return response.data
}

/**
 * Bước 2: Upload ảnh trực tiếp lên S3 bằng pre-signed PUT URL
 * Dùng axios thuần (không qua apiClient) vì S3 không cần JWT
 * @param {string} uploadUrl - pre-signed PUT URL từ backend
 * @param {File} file - file object từ input
 * @param {function} onProgress - callback(percent: number)
 */
export async function uploadToS3(uploadUrl, file, onProgress) {
  await axios.put(uploadUrl, file, {
    headers: {
      'Content-Type': file.type,
    },
    onUploadProgress: (progressEvent) => {
      if (onProgress && progressEvent.total) {
        const percent = Math.round((progressEvent.loaded * 100) / progressEvent.total)
        onProgress(percent)
      }
    },
  })
}

/**
 * Lấy kết quả chẩn đoán theo imageId
 * @param {string} imageId
 * @returns {object} diagnosis record
 * @throws {AxiosError} 202 nếu đang xử lý, 404 nếu không tìm thấy
 */
export async function getDiagnosisResult(imageId) {
  const response = await apiClient.get(`/images/${imageId}/result`)
  return response.data
}

/**
 * Lấy danh sách tất cả ảnh đã upload của user hiện tại
 * @returns {object[]} mảng các diagnosis records
 */
export async function listDiagnoses() {
  const response = await apiClient.get('/images')
  return response.data
}
