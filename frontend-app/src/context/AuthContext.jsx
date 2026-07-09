import { createContext, useContext, useEffect, useState } from 'react'
import {
  getCurrentUser,
  signIn,
  signOut,
  signUp,
  confirmSignUp,
  resendSignUpCode,
  fetchAuthSession,
  autoSignIn,
} from 'aws-amplify/auth'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)

  // Kiểm tra session khi app khởi động
  useEffect(() => {
    checkCurrentUser()
  }, [])

  async function checkCurrentUser() {
    try {
      const currentUser = await getCurrentUser()
      setUser(currentUser)
    } catch {
      setUser(null)
    } finally {
      setLoading(false)
    }
  }

  async function login(email, password) {
    const result = await signIn({ username: email, password })
    if (result.isSignedIn) {
      const currentUser = await getCurrentUser()
      setUser(currentUser)
    }
    return result
  }

  async function logout() {
    await signOut()
    setUser(null)
  }

  async function register(email, password) {
    return await signUp({
      username: email,
      password,
      options: {
        userAttributes: { email },
        // Sau confirmSignUp, Amplify v6 có thể auto sign-in
        autoSignIn: true,
      },
    })
  }

  async function confirmEmail(email, code) {
    const result = await confirmSignUp({ username: email, confirmationCode: code })
    // Amplify v6: nếu autoSignIn được bật, nextStep có thể là COMPLETE_AUTO_SIGN_IN
    if (result.nextStep?.signUpStep === 'COMPLETE_AUTO_SIGN_IN') {
      try {
        const signInResult = await autoSignIn()
        if (signInResult.isSignedIn) {
          const currentUser = await getCurrentUser()
          setUser(currentUser)
        }
      } catch {
        // auto sign-in thất bại — người dùng sẽ tự login thủ công, không phải lỗi nghiêm trọng
      }
    }
    return result
  }

  async function resendCode(email) {
    return await resendSignUpCode({ username: email })
  }

  async function getIdToken() {
    const session = await fetchAuthSession()
    return session.tokens?.idToken?.toString()
  }

  return (
    <AuthContext.Provider
      value={{
        user,
        loading,
        login,
        logout,
        register,
        confirmEmail,
        resendCode,
        getIdToken,
        isAuthenticated: !!user,
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
