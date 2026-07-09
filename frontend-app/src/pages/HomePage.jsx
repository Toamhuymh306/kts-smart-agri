import { Link } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

const STEPS = [
  { icon: '📤', title: 'Upload ảnh', desc: 'Chụp hoặc chọn ảnh lá/cây bị nghi ngờ mắc bệnh.' },
  { icon: '🤖', title: 'AI phân tích', desc: 'Mô hình AI tự động chẩn đoán loại bệnh từ ảnh.' },
  { icon: '📋', title: 'Xem kết quả', desc: 'Nhận kết quả chẩn đoán với tên bệnh và độ tin cậy.' },
]

const DISEASES = [
  { name: 'Cháy lá', emoji: '🍂', key: 'leaf_blight' },
  { name: 'Gỉ sắt', emoji: '🦠', key: 'rust' },
  { name: 'Phấn trắng', emoji: '💨', key: 'powdery_mildew' },
  { name: 'Đốm vi khuẩn', emoji: '🔴', key: 'bacterial_spot' },
  { name: 'Cây khỏe mạnh', emoji: '✅', key: 'healthy' },
]

export default function HomePage() {
  const { user } = useAuth()
  const displayName = user?.signInDetails?.loginId ?? user?.username ?? 'bạn'

  return (
    <div className="space-y-10">
      {/* Hero */}
      <section className="bg-gradient-to-br from-green-600 to-emerald-700 rounded-2xl p-8 text-white">
        <div className="max-w-xl">
          <p className="text-green-200 text-sm font-medium mb-2">Xin chào, {displayName} 👋</p>
          <h1 className="text-3xl font-bold leading-tight mb-3">
            Chẩn đoán bệnh cây trồng<br />bằng AI — nhanh & chính xác
          </h1>
          <p className="text-green-100 text-sm mb-6 leading-relaxed">
            Upload ảnh cây của bạn, hệ thống sẽ tự động nhận diện bệnh và trả kết quả trong vài giây.
          </p>
          <div className="flex flex-wrap gap-3">
            <Link
              to="/upload"
              className="px-5 py-2.5 bg-white text-green-700 font-semibold rounded-xl hover:bg-green-50 transition-colors"
            >
              📤 Upload ảnh ngay
            </Link>
            <Link
              to="/results"
              className="px-5 py-2.5 bg-green-500/40 text-white font-semibold rounded-xl hover:bg-green-500/60 transition-colors border border-green-400/50"
            >
              📋 Xem kết quả
            </Link>
          </div>
        </div>
      </section>

      {/* How it works */}
      <section>
        <h2 className="text-xl font-bold text-gray-800 mb-4">Cách hoạt động</h2>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          {STEPS.map((step, i) => (
            <div key={i} className="bg-white rounded-xl border border-gray-200 p-5 flex gap-4 items-start">
              <span className="text-3xl">{step.icon}</span>
              <div>
                <p className="font-semibold text-gray-800 text-sm">{step.title}</p>
                <p className="text-gray-500 text-xs mt-1 leading-relaxed">{step.desc}</p>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Supported diseases */}
      <section>
        <h2 className="text-xl font-bold text-gray-800 mb-4">Bệnh được hỗ trợ chẩn đoán</h2>
        <div className="flex flex-wrap gap-3">
          {DISEASES.map((d) => (
            <div
              key={d.key}
              className="flex items-center gap-2 bg-white border border-gray-200 rounded-full px-4 py-2 text-sm text-gray-700"
            >
              <span>{d.emoji}</span>
              <span>{d.name}</span>
            </div>
          ))}
        </div>
      </section>

      {/* Quick actions */}
      <section className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <Link
          to="/upload"
          className="group bg-white border-2 border-dashed border-green-300 hover:border-green-500 rounded-2xl p-6 text-center transition-colors"
        >
          <div className="text-4xl mb-3">📷</div>
          <p className="font-semibold text-gray-800 group-hover:text-green-700">Upload ảnh mới</p>
          <p className="text-xs text-gray-500 mt-1">JPG, PNG, WEBP — tối đa 10MB</p>
        </Link>
        <Link
          to="/results"
          className="group bg-white border border-gray-200 hover:border-green-400 rounded-2xl p-6 text-center transition-colors"
        >
          <div className="text-4xl mb-3">📊</div>
          <p className="font-semibold text-gray-800 group-hover:text-green-700">Lịch sử chẩn đoán</p>
          <p className="text-xs text-gray-500 mt-1">Xem tất cả kết quả trước đây</p>
        </Link>
      </section>
    </div>
  )
}
