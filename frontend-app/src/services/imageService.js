/**
 * Image service — tất cả API calls liên quan đến upload và kết quả chẩn đoán
 */
import apiClient from './api'

/**
 * Bước 1: Lấy pre-signed URL từ backend để upload ảnh lên S3
 * @param {string} fileName - tên file ảnh
 * @param {string} contentType - MIME type của file (vd: "image/jpeg")
 * @returns {{ uploadUrl: string, imageId: string, s3Key: string }}
 */
export async function getPresignedUrl(fileName, contentType) {
  const response = await apiClient.post('/images/presign', { fileName, contentType })
  return response.data
}

/**
 * Bước 2: Upload ảnh trực tiếp lên S3 bằng pre-signed PUT URL.
 * Dùng fetch thay vì axios để tránh axios default headers (Accept, Content-Type: application/json)
 * bị thêm vào và trigger CORS preflight với headers S3 không chấp nhận.
 * @param {string} uploadUrl - pre-signed PUT URL từ backend
 * @param {File} file - file object từ input
 * @param {string} contentType - MIME type đã được sign (từ presign response)
 * @param {function} onProgress - callback(percent: number) — không hỗ trợ với fetch, dùng XMLHttpRequest nếu cần
 */
export async function uploadToS3(uploadUrl, file, contentType, onProgress) {
  // Use XMLHttpRequest to support upload progress + avoid axios default headers
  await new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    xhr.open('PUT', uploadUrl)
    xhr.setRequestHeader('Content-Type', contentType)

    if (onProgress) {
      xhr.upload.onprogress = (e) => {
        if (e.lengthComputable) {
          onProgress(Math.round((e.loaded * 100) / e.total))
        }
      }
    }

    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve()
      } else {
        reject(new Error(`S3 upload failed: ${xhr.status} ${xhr.responseText}`))
      }
    }

    xhr.onerror = () => reject(new Error('S3 upload network error'))
    xhr.send(file)
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

/**
 * Xóa một kết quả chẩn đoán (DynamoDB record + S3 object)
 * @param {string} imageId
 */
export async function deleteImage(imageId) {
  const response = await apiClient.delete(`/images/${imageId}/result`)
  return response.data
}
