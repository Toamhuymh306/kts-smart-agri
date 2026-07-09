import { useState } from 'react'
import { useNavigate, useLocation, Link } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

export default function ConfirmEmailPage() {
  const { confirmEmail, resendCode } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const email = location.state?.email ?? ''

  const [code, setCode] = useState('')
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [loading, setLoading] = useState(false)
  const [resending, setResending] = useState(false)

  async function handleSubmit(e) {
    e.preventDefault()
    setLoading(true)
    setError('')
    try {
      await confirmEmail(email, code.trim())
      navigate('/login', { state: { confirmed: true } })
    } catch (err) {
      setError(getFriendlyError(err))
    } finally {
      setLoading(false)
    }
  }

  async function handleResend() {
    setResending(true)
    setError('')
    setSuccess('')
    try {
      await resendCode(email)
      setSuccess('Mã xác nhận mới đã được gửi đến email của bạn.')
    } catch (err) {
      setError(err?.message ?? 'Không thể gửi lại mã.')
    } finally {
      setResending(false)
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-green-50 to-emerald-100 flex items-center justify-center px-4">
      <div className="bg-white w-full max-w-md rounded-2xl shadow-lg p-8">
        <div className="text-center mb-8">
          <span className="text-5xl">📧</span>
          <h1 className="mt-3 text-2xl font-bold text-gray-900">Xác nhận email</h1>
          <p className="text-gray-500 text-sm mt-1">
            Mã xác nhận đã được gửi đến{' '}
            <span className="font-medium text-gray-700">{email || 'email của bạn'}</span>
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-5">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Mã xác nhận (6 chữ số)</label>
            <input
              type="text"
              inputMode="numeric"
              maxLength={6}
              value={code}
              onChange={(e) => { setCode(e.target.value.replace(/\D/g, '')); setError('') }}
              required
              placeholder="123456"
              className="w-full px-4 py-3 border border-gray-300 rounded-lg text-center text-2xl tracking-[0.5em] font-mono focus:outline-none focus:ring-2 focus:ring-green-400 focus:border-transparent"
            />
          </div>

          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg px-4 py-3">
              {error}
            </div>
          )}
          {success && (
            <div className="bg-green-50 border border-green-200 text-green-700 text-sm rounded-lg px-4 py-3">
              {success}
            </div>
          )}

          <button
            type="submit"
            disabled={loading || code.length !== 6}
            className="w-full py-2.5 bg-green-600 hover:bg-green-700 disabled:bg-green-400 text-white font-semibold rounded-lg transition-colors flex items-center justify-center gap-2"
          >
            {loading && <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />}
            {loading ? 'Đang xác nhận...' : 'Xác nhận'}
          </button>
        </form>

        <div className="mt-5 text-center space-y-2">
          <button
            onClick={handleResend}
            disabled={resending}
            className="text-sm text-green-600 hover:underline disabled:text-gray-400"
          >
            {resending ? 'Đang gửi...' : 'Gửi lại mã'}
          </button>
          <div>
            <Link to="/login" className="text-sm text-gray-500 hover:underline">
              ← Quay lại đăng nhập
            </Link>
          </div>
        </div>
      </div>
    </div>
  )
}

function getFriendlyError(err) {
  const code = err?.name ?? err?.code
  switch (code) {
    case 'CodeMismatchException':
      return 'Mã xác nhận không đúng. Vui lòng thử lại.'
    case 'ExpiredCodeException':
      return 'Mã xác nhận đã hết hạn. Vui lòng gửi lại mã.'
    default:
      return err?.message ?? 'Đã có lỗi xảy ra.'
  }
}
