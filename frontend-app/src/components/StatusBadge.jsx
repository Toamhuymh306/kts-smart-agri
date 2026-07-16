/**
 * Badge hiển thị trạng thái chẩn đoán: PROCESSING | COMPLETED | ARCHIVED
 */
const CONFIG = {
  PROCESSING: {
    label: 'Đang xử lý',
    className: 'bg-yellow-100 text-yellow-800 border-yellow-200',
    dot: 'bg-yellow-400 animate-pulse',
  },
  COMPLETED: {
    label: 'Hoàn thành',
    className: 'bg-green-100 text-green-800 border-green-200',
    dot: 'bg-green-500',
  },
  ARCHIVED: {
    label: 'Đã lưu trữ',
    className: 'bg-gray-100 text-gray-600 border-gray-200',
    dot: 'bg-gray-400',
  },
}

export default function StatusBadge({ status }) {
  const cfg = CONFIG[status] ?? CONFIG.PROCESSING
  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium border ${cfg.className}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${cfg.dot}`} />
      {cfg.label}
    </span>
  )
}
