import { useState, useEffect, useRef, useCallback } from 'react'
import { useParams, Link } from 'react-router-dom'
import { getDiagnosisResult } from '../services/imageService'
import StatusBadge from '../components/StatusBadge'
import DiseaseCard from '../components/DiseaseCard'

const POLL_INTERVAL_MS = 3000   // polling mỗi 3 giây khi status = PROCESSING
const MAX_POLLS = 30            // tối đa 90 giây polling

export default function ResultDetailPage() {
  const { imageId } = useParams()
  const [record, setRecord] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const pollCount = useRef(0)
  const timerRef = useRef(null)

  const fetchResult = useCallback(async () => {
    setError('')
    try {
      const data = await getDiagnosisResult(imageId)
      setRecord(data)

      // Nếu vẫn đang PROCESSING → tiếp tục poll
      if (data.status === 'PROCESSING' && pollCount.current < MAX_POLLS) {
        pollCount.current += 1
        timerRef.current = setTimeout(fetchResult, POLL_INTERVAL_MS)
      }
    } catch (err) {
      const status = err?.response?.status
      if (status === 202) {
        // Backend trả 202 → PROCESSING
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
  // fetchResult phụ thuộc vào imageId — khi imageId thay đổi sẽ tạo instance mới
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
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Chi tiết chẩn đoán</h1>
          <p className="text-xs text-gray-400 font-mono mt-0.5 truncate max-w-xs">
            ID: {imageId}
          </p>
        </div>
        <button
          onClick={handleRefresh}
          className="flex items-center gap-1.5 px-3 py-2 text-sm text-gray-600 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
        >
          🔄 Làm mới
        </button>
      </div>

      {/* Error */}
      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-xl px-4 py-3">
          ⚠️ {error}
        </div>
      )}

      {/* Record details */}
      {record && (
        <div className="space-y-4">
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

          {/* S3 key info */}
          {record.imageS3Key && (
            <div className="bg-white rounded-xl border border-gray-200 p-4">
              <p className="text-xs text-gray-500 mb-1">S3 Key</p>
              <p className="text-xs font-mono text-gray-600 break-all">{record.imageS3Key}</p>
            </div>
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
