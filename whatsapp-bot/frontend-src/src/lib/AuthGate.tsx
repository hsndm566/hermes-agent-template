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

export function AuthGate({ children, loginScreen }: { children: ReactNode; loginScreen: (onSuccess: () => void) => ReactNode }) {
  const [status, setStatus] = useState<'checking' | 'authed' | 'anon'>('checking')
  const [username, setUsername] = useState<string | null>(null)

  async function check() {
    try {
      const res = await api.session()
      setUsername(res.username)
      setStatus('authed')
    } catch {
      setStatus('anon')
    }
  }

  useEffect(() => { check() }, [])

  if (status === 'checking') return null
  if (status === 'anon') return <>{loginScreen(check)}</>

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
