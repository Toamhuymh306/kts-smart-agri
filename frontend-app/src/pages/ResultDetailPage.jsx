import { useState, useEffect, useRef, useCallback } from 'react'
import { useParams, useLocation, Link, useNavigate } from 'react-router-dom'
import { getDiagnosisResult, deleteImage } from '../services/imageService'
import StatusBadge from '../components/StatusBadge'
import DiseaseCard from '../components/DiseaseCard'

const POLL_INTERVAL_MS = 3000
const MAX_POLLS = 30

export default function ResultDetailPage() {
  const { imageId } = useParams()
  const location = useLocation()
  const navigate = useNavigate()
  const previewUrl = location.state?.previewUrl ?? null

  const [record, setRecord] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [deleting, setDeleting] = useState(false)
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)
  const pollCount = useRef(0)
  const timerRef = useRef(null)

  const fetchResult = useCallback(async () => {
    setError('')
    try {
      const data = await getDiagnosisResult(imageId)
      setRecord(data)
      if (data.status === 'PROCESSING' && pollCount.current < MAX_POLLS) {
        pollCount.current += 1
        timerRef.current = setTimeout(fetchResult, POLL_INTERVAL_MS)
      }
    } catch (err) {
      const status = err?.response?.status
      if (status === 202) {
        setRecord({ imageId, status: 'PROCESSING' })
        if (pollCount.current < MAX_POLLS) {
          pollCount.current += 1
          timerRef.current = setTimeout(fetchResult, POLL_INTERVAL_MS)
        }
      } else if (status === 404) {
        setError('Không tìm thấy kết quả cho ảnh này.')
      } else {
        setError(err?.response?.data?.message ?? err?.message ?? 'Đã có lỗi xảy ra.')
      }
    } finally {
      setLoading(false)
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [imageId])

  useEffect(() => {
    pollCount.current = 0
    setLoading(true)
    setRecord(null)
    fetchResult()
    return () => clearTimeout(timerRef.current)
  }, [fetchResult])

  function handleRefresh() {
    clearTimeout(timerRef.current)
    pollCount.current = 0
    setLoading(true)
    fetchResult()
  }

  async function handleDelete() {
    setDeleting(true)
    try {
      await deleteImage(imageId)
      navigate('/results', { replace: true })
    } catch (err) {
      setError(err?.response?.data?.message ?? 'Xóa thất bại, vui lòng thử lại.')
      setDeleting(false)
      setShowDeleteConfirm(false)
    }
  }

  // Ảnh hiển thị: ưu tiên imageUrl từ backend (presigned S3), fallback về previewUrl từ navigate state
  const imageToShow = record?.imageUrl ?? previewUrl

  if (loading && !record) {
    return (
      <div className="flex justify-center items-center py-20">
        <div className="flex flex-col items-center gap-3">
          <div className="w-10 h-10 border-4 border-green-500 border-t-transparent rounded-full animate-spin" />
          <p className="text-gray-500 text-sm">Đang tải kết quả...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="max-w-xl mx-auto space-y-6">
      {/* Back button */}
      <Link to="/results" className="inline-flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-700">
        ← Quay lại danh sách
      </Link>

      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Chi tiết chẩn đoán</h1>
        <div className="flex gap-2">
          <button
            onClick={handleRefresh}
            className="flex items-center gap-1.5 px-3 py-2 text-sm text-gray-600 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
          >
            🔄 Làm mới
          </button>
          <button
            onClick={() => setShowDeleteConfirm(true)}
            className="flex items-center gap-1.5 px-3 py-2 text-sm text-red-600 bg-white border border-red-300 rounded-lg hover:bg-red-50 transition-colors"
          >
            🗑️ Xóa
          </button>
        </div>
      </div>

      {/* Delete confirmation */}
      {showDeleteConfirm && (
        <div className="bg-red-50 border border-red-200 rounded-xl p-4 space-y-3">
          <p className="text-sm font-semibold text-red-800">Xác nhận xóa kết quả này?</p>
          <p className="text-xs text-red-600">Hành động này sẽ xóa vĩnh viễn kết quả chẩn đoán và ảnh khỏi hệ thống.</p>
          <div className="flex gap-3">
            <button
              onClick={handleDelete}
              disabled={deleting}
              className="flex-1 py-2 bg-red-600 hover:bg-red-700 disabled:bg-red-400 text-white text-sm font-semibold rounded-lg transition-colors"
            >
              {deleting ? 'Đang xóa...' : 'Xác nhận xóa'}
            </button>
            <button
              onClick={() => setShowDeleteConfirm(false)}
              disabled={deleting}
              className="flex-1 py-2 bg-white border border-gray-300 hover:bg-gray-50 text-gray-700 text-sm font-semibold rounded-lg transition-colors"
            >
              Hủy
            </button>
          </div>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-xl px-4 py-3">
          ⚠️ {error}
        </div>
      )}

      {/* Record details */}
      {record && (
        <div className="space-y-4">
          {/* Uploaded image */}
          {imageToShow && (
            <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
              <img
                src={imageToShow}
                alt="Ảnh cây trồng"
                className="w-full object-cover max-h-72"
              />
            </div>
          )}

          {/* Status + timestamp */}
          <div className="bg-white rounded-xl border border-gray-200 p-4 flex items-center justify-between">
            <div>
              <p className="text-xs text-gray-500 mb-1">Trạng thái</p>
              <StatusBadge status={record.status} />
            </div>
            {record.timestamp && (
              <div className="text-right">
                <p className="text-xs text-gray-500 mb-1">Thời gian</p>
                <p className="text-sm text-gray-700">{formatDate(record.timestamp)}</p>
              </div>
            )}
          </div>

          {/* Processing state */}
          {record.status === 'PROCESSING' && (
            <div className="bg-yellow-50 border border-yellow-200 rounded-xl p-5 text-center">
              <div className="w-10 h-10 border-4 border-yellow-400 border-t-transparent rounded-full animate-spin mx-auto mb-3" />
              <p className="font-semibold text-yellow-800">AI đang phân tích ảnh của bạn</p>
              <p className="text-xs text-yellow-600 mt-1">
                Tự động cập nhật sau mỗi {POLL_INTERVAL_MS / 1000} giây...
              </p>
            </div>
          )}

          {/* Diagnosis result */}
          {record.status === 'COMPLETED' && record.disease && (
            <DiseaseCard disease={record.disease} confidence={record.confidence} />
          )}

          {/* Archived notice */}
          {record.status === 'ARCHIVED' && (
            <div className="bg-gray-50 border border-gray-200 rounded-xl p-4 text-center">
              <p className="text-gray-500 text-sm">
                📦 Ảnh này đã được lưu trữ và xóa khỏi S3 sau 30 ngày.
              </p>
            </div>
          )}
        </div>
      )}

      {/* Actions */}
      <div className="flex gap-3 pt-2">
        <Link
          to="/upload"
          className="flex-1 text-center py-2.5 bg-green-600 hover:bg-green-700 text-white text-sm font-semibold rounded-xl transition-colors"
        >
          📤 Upload ảnh mới
        </Link>
        <Link
          to="/results"
          className="flex-1 text-center py-2.5 bg-white border border-gray-300 hover:bg-gray-50 text-gray-700 text-sm font-semibold rounded-xl transition-colors"
        >
          📋 Xem tất cả
        </Link>
      </div>
    </div>
  )
}

function formatDate(iso) {
  if (!iso) return ''
  try {
    return new Intl.DateTimeFormat('vi-VN', {
      year: 'numeric', month: '2-digit', day: '2-digit',
      hour: '2-digit', minute: '2-digit', second: '2-digit',
    }).format(new Date(iso))
  } catch {
    return iso
  }
}
