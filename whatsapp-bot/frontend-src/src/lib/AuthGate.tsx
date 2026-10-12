import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import { api } from './api'

interface AuthContextValue {
  username: string | null
  logout: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthGate')
  return ctx
}

export function AuthGate({ children }: { children: ReactNode; loginScreen?: (onSuccess: () => void) => ReactNode }) {
  const [status, setStatus] = useState<'checking' | 'authed' | 'anon'>('checking')
  const [username, setUsername] = useState<string | null>(null)

  async function check() {
    try {
      const res = await api.setup()
      setUsername(res.username)
      setStatus('authed')
    } catch {
      setStatus('anon')
    }
  }

  useEffect(() => { check() }, [])

  if (status === 'checking') return <div className="flex min-h-screen items-center justify-center">جارٍ تجهيز واتساب…</div>
  if (status === 'anon') return <div className="flex min-h-screen flex-col items-center justify-center gap-4"><p>تعذر الاتصال بالخادم / Connection unavailable</p><button onClick={check}>إعادة المحاولة / Retry</button></div>

  return (
    <AuthContext.Provider
      value={{
        username,
        logout: async () => {
          await api.logout().catch(() => {})
          setStatus('anon')
        },
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}
