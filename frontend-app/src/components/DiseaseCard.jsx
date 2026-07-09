/**
 * Hiển thị kết quả chẩn đoán bệnh cây — disease name + confidence bar
 */

const DISEASE_LABELS = {
  leaf_blight:      { label: 'Cháy lá (Leaf Blight)',          emoji: '🍂', color: 'text-orange-700' },
  rust:             { label: 'Gỉ sắt (Rust)',                   emoji: '🦠', color: 'text-red-700' },
  powdery_mildew:   { label: 'Phấn trắng (Powdery Mildew)',     emoji: '💨', color: 'text-purple-700' },
  bacterial_spot:   { label: 'Đốm vi khuẩn (Bacterial Spot)',  emoji: '🔴', color: 'text-rose-700' },
  healthy:          { label: 'Cây khỏe mạnh (Healthy)',         emoji: '✅', color: 'text-green-700' },
}

export default function DiseaseCard({ disease, confidence }) {
  const info = DISEASE_LABELS[disease] ?? { label: disease, emoji: '🌿', color: 'text-gray-700' }
  const pct = Math.round((confidence ?? 0) * 100)
  const barColor = disease === 'healthy' ? 'bg-green-500' : pct >= 85 ? 'bg-red-500' : 'bg-yellow-500'

  return (
    <div className="bg-white rounded-2xl border border-gray-200 shadow-sm p-6">
      <div className="flex items-center gap-3 mb-4">
        <span className="text-4xl">{info.emoji}</span>
        <div>
          <p className="text-xs text-gray-500 uppercase tracking-wide">Kết quả chẩn đoán</p>
          <p className={`text-xl font-bold ${info.color}`}>{info.label}</p>
        </div>
      </div>

      <div>
        <div className="flex justify-between text-sm mb-1">
          <span className="text-gray-600">Độ tin cậy</span>
          <span className="font-semibold text-gray-800">{pct}%</span>
        </div>
        <div className="w-full bg-gray-100 rounded-full h-3 overflow-hidden">
          <div
            className={`h-3 rounded-full transition-all duration-700 ${barColor}`}
            style={{ width: `${pct}%` }}
          />
        </div>
      </div>
    </div>
  )
}
