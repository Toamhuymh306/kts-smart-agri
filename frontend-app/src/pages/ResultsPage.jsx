import { useState, useEffect, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { listDiagnoses } from '../services/imageService'
import StatusBadge from '../components/StatusBadge'

const DISEASE_LABELS = {
  leaf_blight:    'Cháy lá',
  rust:           'Gỉ sắt',
  powdery_mildew: 'Phấn trắng',
  bacterial_spot: 'Đốm vi khuẩn',
  healthy:        'Khỏe mạnh',
}

export default function ResultsPage() {
  const [records, setRecords] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [refreshing, setRefreshing] = useState(false)

  const fetchRecords = useCallback(async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true)
    else setLoading(true)
    setError('')
    try {
      const data = await listDiagnoses()
      // Sắp xếp mới nhất lên đầu
      const sorted = [...(data?.items ?? data ?? [])].sort(
        (a, b) => new Date(b.timestamp) - new Date(a.timestamp),
      )
      setRecords(sorted)
    } catch (err) {
      setError(err?.response?.data?.message ?? 'Không thể tải danh sách. Vui lòng thử lại.')
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }, [])

  useEffect(() => {
    fetchRecords()
  }, [fetchRecords])

  if (loading) {
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
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Lịch sử chẩn đoán</h1>
          <p className="text-gray-500 text-sm mt-0.5">
            {records.length > 0 ? `${records.length} ảnh đã phân tích` : 'Chưa có ảnh nào'}
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => fetchRecords(true)}
            disabled={refreshing}
            className="flex items-center gap-1.5 px-3 py-2 text-sm text-gray-600 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors disabled:opacity-50"
          >
            <span className={refreshing ? 'animate-spin' : ''}>🔄</span>
            Làm mới
          </button>
          <Link
            to="/upload"
            className="flex items-center gap-1.5 px-3 py-2 text-sm text-white bg-green-600 rounded-lg hover:bg-green-700 transition-colors"
          >
            <span>📤</span> Upload mới
          </Link>
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-xl px-4 py-3">
          ⚠️ {error}
        </div>
      )}

      {/* Empty state */}
      {records.length === 0 && !error && (
        <div className="text-center py-20 bg-white rounded-2xl border border-dashed border-gray-300">
          <div className="text-5xl mb-4">🌱</div>
          <p className="text-gray-700 font-semibold">Chưa có ảnh nào được phân tích</p>
          <p className="text-gray-400 text-sm mt-1 mb-5">Upload ảnh cây để bắt đầu chẩn đoán</p>
          <Link
            to="/upload"
            className="inline-flex items-center gap-2 px-5 py-2.5 bg-green-600 text-white font-semibold rounded-xl hover:bg-green-700 transition-colors"
          >
            📤 Upload ảnh ngay
          </Link>
        </div>
      )}

      {/* Records list */}
      {records.length > 0 && (
        <div className="space-y-3">
          {records.map((record) => (
            <Link
              key={record.imageId}
              to={`/results/${record.imageId}`}
              className="block bg-white rounded-xl border border-gray-200 hover:border-green-400 hover:shadow-sm transition-all p-4"
            >
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1 min-w-0">
                  {/* Image ID & timestamp */}
                  <div className="flex items-center gap-2 mb-2">
                    <StatusBadge status={record.status} />
                    <span className="text-xs text-gray-400">
                      {formatDate(record.timestamp)}
                    </span>
                  </div>

                  {/* Disease result */}
                  {record.status === 'COMPLETED' && record.disease ? (
                    <div className="flex items-center gap-3">
                      <div>
                        <p className="font-semibold text-gray-800">
                          {DISEASE_LABELS[record.disease] ?? record.disease}
                        </p>
                        <div className="flex items-center gap-2 mt-1">
                          <div className="w-24 bg-gray-100 rounded-full h-1.5 overflow-hidden">
                            <div
                              className="h-1.5 bg-green-500 rounded-full"
                              style={{ width: `${Math.round((record.confidence ?? 0) * 100)}%` }}
                            />
                          </div>
                          <span className="text-xs text-gray-500">
                            {Math.round((record.confidence ?? 0) * 100)}% tin cậy
                          </span>
                        </div>
                      </div>
                    </div>
                  ) : record.status === 'PROCESSING' ? (
                    <p className="text-sm text-yellow-600">⏳ Đang xử lý...</p>
                  ) : (
                    <p className="text-sm text-gray-400 italic">Đã lưu trữ</p>
                  )}

                  {/* S3 key (short) */}
                  <p className="text-xs text-gray-400 mt-2 truncate font-mono">
                    ID: {record.imageId}
                  </p>
                </div>

                <span className="text-gray-400 text-lg flex-shrink-0">›</span>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}

function formatDate(iso) {
  if (!iso) return ''
  try {
    return new Intl.DateTimeFormat('vi-VN', {
      year: 'numeric', month: '2-digit', day: '2-digit',
      hour: '2-digit', minute: '2-digit',
    }).format(new Date(iso))
  } catch {
    return iso
  }
}
