import { Link, useNavigate, useLocation } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

const NAV_LINKS = [
  { to: '/',        label: 'Trang chủ',    icon: '🏠' },
  { to: '/upload',  label: 'Upload ảnh',   icon: '📤' },
  { to: '/results', label: 'Kết quả',      icon: '📋' },
]

export default function Layout({ children }) {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()

  async function handleLogout() {
    await logout()
    navigate('/login')
  }

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      {/* Top navbar */}
      <header className="bg-white shadow-sm sticky top-0 z-30">
        <div className="max-w-5xl mx-auto px-4 h-16 flex items-center justify-between">
          {/* Brand */}
          <Link to="/" className="flex items-center gap-2 font-bold text-green-700 text-lg">
            <span className="text-2xl">🌿</span>
            <span className="hidden sm:block">KTS Smart Agri</span>
          </Link>

          {/* Nav links */}
          <nav className="flex items-center gap-1">
            {NAV_LINKS.map(({ to, label, icon }) => {
              const active = location.pathname === to
              return (
                <Link
                  key={to}
                  to={to}
                  className={`flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium transition-colors
                    ${active
                      ? 'bg-green-100 text-green-800'
                      : 'text-gray-600 hover:bg-gray-100'
                    }`}
                >
                  <span>{icon}</span>
                  <span className="hidden sm:block">{label}</span>
                </Link>
              )
            })}
          </nav>

          {/* User menu */}
          <div className="flex items-center gap-2">
            <span className="hidden md:block text-xs text-gray-500 max-w-[120px] truncate">
              {user?.signInDetails?.loginId ?? user?.username}
            </span>
            <button
              onClick={handleLogout}
              className="text-sm text-gray-600 hover:text-red-600 px-3 py-1.5 rounded-lg hover:bg-red-50 transition-colors"
            >
              Đăng xuất
            </button>
          </div>
        </div>
      </header>

      {/* Page content */}
      <main className="flex-1 max-w-5xl mx-auto w-full px-4 py-8">
        {children}
      </main>

      {/* Footer */}
      <footer className="bg-white border-t text-center text-xs text-gray-400 py-4">
        KTS Smart Agriculture © {new Date().getFullYear()}
      </footer>
    </div>
  )
}
