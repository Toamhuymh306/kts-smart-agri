import { useState, useRef, useCallback, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { getPresignedUrl, uploadToS3 } from '../services/imageService'

const ACCEPTED_TYPES = ['image/jpeg', 'image/png', 'image/webp']
const MAX_SIZE_MB = 10

export default function UploadPage() {
  const navigate = useNavigate()
  const fileInputRef = useRef(null)
  const previewUrlRef = useRef(null) // track object URL để revoke tránh memory leak

  const [file, setFile] = useState(null)
  const [preview, setPreview] = useState(null)
  const [dragging, setDragging] = useState(false)
  const [stage, setStage] = useState('idle') // idle | uploading | done | error
  const [progress, setProgress] = useState(0)
  const [error, setError] = useState('')
  const [resultImageId, setResultImageId] = useState(null)

  // Revoke object URL khi component unmount để tránh memory leak
  useEffect(() => {
    return () => {
      if (previewUrlRef.current) {
        URL.revokeObjectURL(previewUrlRef.current)
      }
    }
  }, [])

  function pickFile(selected) {
    setError('')
    if (!selected) return

    if (!ACCEPTED_TYPES.includes(selected.type)) {
      setError('Chỉ chấp nhận định dạng JPG, PNG hoặc WEBP.')
      return
    }
    if (selected.size > MAX_SIZE_MB * 1024 * 1024) {
      setError(`File quá lớn. Tối đa ${MAX_SIZE_MB}MB.`)
      return
    }

    // Revoke URL cũ trước khi tạo URL mới
    if (previewUrlRef.current) {
      URL.revokeObjectURL(previewUrlRef.current)
    }
    const objectUrl = URL.createObjectURL(selected)
    previewUrlRef.current = objectUrl

    setFile(selected)
    setPreview(objectUrl)
    setStage('idle')
    setProgress(0)
  }

  function handleFileInput(e) {
    pickFile(e.target.files?.[0])
  }

  // Drag & drop handlers
  const handleDragOver = useCallback((e) => { e.preventDefault(); setDragging(true) }, [])
  const handleDragLeave = useCallback(() => setDragging(false), [])
  const handleDrop = useCallback((e) => {
    e.preventDefault()
    setDragging(false)
    pickFile(e.dataTransfer.files?.[0])
  }, [])

  function handleReset() {
    // Revoke object URL khi reset
    if (previewUrlRef.current) {
      URL.revokeObjectURL(previewUrlRef.current)
      previewUrlRef.current = null
    }
    setFile(null)
    setPreview(null)
    setStage('idle')
    setProgress(0)
    setError('')
    setResultImageId(null)
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  async function handleUpload() {
    if (!file) return
    setStage('uploading')
    setError('')
    setProgress(0)

    try {
      // Bước 1: Lấy pre-signed URL
      const { uploadUrl, imageId } = await getPresignedUrl(file.name)

      // Bước 2: PUT ảnh thẳng lên S3
      await uploadToS3(uploadUrl, file, (pct) => setProgress(pct))

      setResultImageId(imageId)
      setStage('done')
    } catch (err) {
      console.error('Upload error:', err)
      setError(err?.response?.data?.message ?? err?.message ?? 'Upload thất bại, vui lòng thử lại.')
      setStage('error')
    }
  }

  return (
    <div className="max-w-xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Upload ảnh cây trồng</h1>
        <p className="text-gray-500 text-sm mt-1">
          Chọn ảnh lá hoặc cây nghi ngờ mắc bệnh để AI phân tích.
        </p>
      </div>

      {/* Drop zone */}
      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={() => !file && fileInputRef.current?.click()}
        className={`relative rounded-2xl border-2 border-dashed transition-colors cursor-pointer overflow-hidden
          ${dragging ? 'border-green-500 bg-green-50' : 'border-gray-300 hover:border-green-400 bg-white'}
          ${file ? 'cursor-default' : ''}`}
        style={{ minHeight: 260 }}
      >
        {preview ? (
          // Preview ảnh đã chọn
          <div className="relative">
            <img src={preview} alt="preview" className="w-full object-cover max-h-72" />
            <div className="absolute bottom-0 left-0 right-0 bg-black/50 text-white text-xs px-4 py-2 flex justify-between items-center">
              <span className="truncate">{file.name}</span>
              <span>{(file.size / 1024 / 1024).toFixed(2)} MB</span>
            </div>
          </div>
        ) : (
          // Placeholder
          <div className="flex flex-col items-center justify-center py-16 px-6 text-center">
            <span className="text-5xl mb-4">{dragging ? '📂' : '🖼️'}</span>
            <p className="font-semibold text-gray-700">Kéo thả ảnh vào đây</p>
            <p className="text-sm text-gray-400 mt-1">hoặc click để chọn file</p>
            <p className="text-xs text-gray-400 mt-3">JPG · PNG · WEBP — Tối đa {MAX_SIZE_MB}MB</p>
          </div>
        )}

        <input
          ref={fileInputRef}
          type="file"
          accept={ACCEPTED_TYPES.join(',')}
          onChange={handleFileInput}
          className="sr-only"
          aria-label="Chọn ảnh cây trồng"
        />
      </div>

      {/* Progress bar */}
      {stage === 'uploading' && (
        <div>
          <div className="flex justify-between text-sm text-gray-600 mb-1">
            <span>Đang upload...</span>
            <span>{progress}%</span>
          </div>
          <div className="w-full bg-gray-100 rounded-full h-2.5 overflow-hidden">
            <div
              className="h-2.5 bg-green-500 rounded-full transition-all duration-300"
              style={{ width: `${progress}%` }}
            />
          </div>
        </div>
      )}

      {/* Error message */}
      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-xl px-4 py-3">
          ⚠️ {error}
        </div>
      )}

      {/* Success state */}
      {stage === 'done' && (
        <div className="bg-green-50 border border-green-200 rounded-xl px-4 py-4 space-y-3">
          <div className="flex items-center gap-2 text-green-700 font-semibold">
            <span>✅</span> Upload thành công! AI đang phân tích ảnh...
          </div>
          <p className="text-xs text-green-600">
            Kết quả sẽ sẵn sàng trong vài giây. Bạn có thể theo dõi tiến trình tại trang kết quả.
          </p>
          <div className="flex gap-3">
            <button
              onClick={() => navigate(`/results/${resultImageId}`)}
              className="flex-1 py-2 bg-green-600 hover:bg-green-700 text-white text-sm font-semibold rounded-lg transition-colors"
            >
              Xem kết quả →
            </button>
            <button
              onClick={handleReset}
              className="flex-1 py-2 bg-white border border-gray-300 hover:bg-gray-50 text-gray-700 text-sm font-semibold rounded-lg transition-colors"
            >
              Upload ảnh khác
            </button>
          </div>
        </div>
      )}

      {/* Action buttons (idle / error state) */}
      {(stage === 'idle' || stage === 'error') && (
        <div className="flex gap-3">
          <button
            onClick={handleUpload}
            disabled={!file}
            className="flex-1 py-2.5 bg-green-600 hover:bg-green-700 disabled:bg-gray-300 disabled:cursor-not-allowed text-white font-semibold rounded-xl transition-colors flex items-center justify-center gap-2"
          >
            📤 Bắt đầu phân tích
          </button>
          {file && (
            <button
              onClick={handleReset}
              className="px-4 py-2.5 bg-white border border-gray-300 hover:bg-gray-50 text-gray-700 rounded-xl transition-colors"
            >
              ✕
            </button>
          )}
        </div>
      )}
    </div>
  )
}
