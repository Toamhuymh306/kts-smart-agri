import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

const PASSWORD_RULES = [
  { test: (p) => p.length >= 8,         label: 'Ít nhất 8 ký tự' },
  { test: (p) => /[A-Z]/.test(p),       label: 'Có chữ hoa' },
  { test: (p) => /[a-z]/.test(p),       label: 'Có chữ thường' },
  { test: (p) => /[0-9]/.test(p),       label: 'Có chữ số' },
]

export default function RegisterPage() {
  const { register } = useAuth()
  const navigate = useNavigate()

  const [form, setForm] = useState({ email: '', password: '', confirmPassword: '' })
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  function handleChange(e) {
    setForm((f) => ({ ...f, [e.target.name]: e.target.value }))
    setError('')
  }

  async function handleSubmit(e) {
    e.preventDefault()
    if (form.password !== form.confirmPassword) {
      setError('Mật khẩu xác nhận không khớp.')
      return
    }
    const failedRule = PASSWORD_RULES.find((r) => !r.test(form.password))
    if (failedRule) {
      setError(`Mật khẩu phải: ${failedRule.label.toLowerCase()}.`)
      return
    }

    setLoading(true)
    setError('')
    try {
      await register(form.email.trim(), form.password)
      navigate('/confirm-email', { state: { email: form.email.trim() } })
    } catch (err) {
      setError(getFriendlyError(err))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-green-50 to-emerald-100 flex items-center justify-center px-4">
      <div className="bg-white w-full max-w-md rounded-2xl shadow-lg p-8">
        {/* Header */}
        <div className="text-center mb-8">
          <span className="text-5xl">🌿</span>
          <h1 className="mt-3 text-2xl font-bold text-gray-900">Tạo tài khoản</h1>
          <p className="text-gray-500 text-sm mt-1">Tham gia KTS Smart Agriculture</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-5">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Email</label>
            <input
              type="email"
              name="email"
              value={form.email}
              onChange={handleChange}
              required
              autoComplete="email"
              placeholder="email@example.com"
              className="w-full px-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-green-400 focus:border-transparent"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Mật khẩu</label>
            <input
              type="password"
              name="password"
              value={form.password}
              onChange={handleChange}
              required
              autoComplete="new-password"
              placeholder="••••••••"
              className="w-full px-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-green-400 focus:border-transparent"
            />
            {/* Password strength hints */}
            {form.password && (
              <div className="mt-2 grid grid-cols-2 gap-1">
                {PASSWORD_RULES.map((rule) => (
                  <div key={rule.label} className={`flex items-center gap-1 text-xs ${rule.test(form.password) ? 'text-green-600' : 'text-gray-400'}`}>
                    <span>{rule.test(form.password) ? '✓' : '○'}</span>
                    {rule.label}
                  </div>
                ))}
              </div>
            )}
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Xác nhận mật khẩu</label>
            <input
              type="password"
              name="confirmPassword"
              value={form.confirmPassword}
              onChange={handleChange}
              required
              autoComplete="new-password"
              placeholder="••••••••"
              className="w-full px-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-green-400 focus:border-transparent"
            />
          </div>

          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg px-4 py-3">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full py-2.5 bg-green-600 hover:bg-green-700 disabled:bg-green-400 text-white font-semibold rounded-lg transition-colors flex items-center justify-center gap-2"
          >
            {loading && <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />}
            {loading ? 'Đang tạo tài khoản...' : 'Đăng ký'}
          </button>
        </form>

        <p className="text-center text-sm text-gray-500 mt-6">
          Đã có tài khoản?{' '}
          <Link to="/login" className="text-green-600 font-medium hover:underline">
            Đăng nhập
          </Link>
        </p>
      </div>
    </div>
  )
}

function getFriendlyError(err) {
  const code = err?.name ?? err?.code
  switch (code) {
    case 'UsernameExistsException':
      return 'Email này đã được đăng ký.'
    case 'InvalidPasswordException':
      return 'Mật khẩu không đáp ứng yêu cầu bảo mật.'
    default:
      return err?.message ?? 'Đã có lỗi xảy ra, vui lòng thử lại.'
  }
}
