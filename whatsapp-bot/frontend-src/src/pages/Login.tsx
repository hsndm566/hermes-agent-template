import { useState } from 'react'
import { api } from '../lib/api'
import { useI18n } from '../lib/i18n'

export default function Login({ onSuccess }: { onSuccess: () => void }) {
  const { t, lang, toggle } = useI18n()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  async function submit(e: React.FormEvent) {
    e.preventDefault(); setLoading(true); setError(null)
    try { await api.login(username, password); onSuccess() }
    catch (e) { setError(e instanceof Error ? e.message : 'error') }
    finally { setLoading(false) }
  }
  return (
    <div className="flex min-h-screen items-center justify-center bg-canvas px-4">
      <button onClick={toggle} className="fixed top-4 end-4 rounded-full border border-ink-200 bg-surface px-3 py-1.5 text-xs font-semibold text-ink-700">{lang === 'ar' ? 'EN' : 'ع'}</button>
      <form onSubmit={submit} className="w-full max-w-sm space-y-5 rounded-xl2 border border-ink-100 bg-surface p-8 shadow-card">
        <div className="text-center">
          <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-xl bg-moss-700 text-lg font-bold text-white">{lang === 'ar' ? 'م' : 'M'}</div>
          <h1 className="text-lg font-semibold text-ink-900">{t('appName')}</h1>
          <p className="mt-1 text-sm text-ink-500">{t('loginHelp')}</p>
        </div>
        <label className="block"><span className="mb-1.5 block text-xs font-medium text-ink-500">{t('username')}</span><input className="input" value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username" /></label>
        <label className="block"><span className="mb-1.5 block text-xs font-medium text-ink-500">{t('password')}</span><input type="password" className="input" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" /></label>
        {error && <p className="text-sm text-rose-600">{error}</p>}
        <button type="submit" disabled={loading} className="w-full rounded-lg bg-moss-600 py-2.5 text-sm font-semibold text-white hover:bg-moss-700 disabled:opacity-60">{loading ? t('saving') : t('login')}</button>
      </form>
    </div>
  )
}
