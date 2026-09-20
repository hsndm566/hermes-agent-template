import { CheckCircle2, Send } from 'lucide-react'
import { useEffect, useState } from 'react'
import { api } from '../../lib/api'
import { useI18n } from '../../lib/i18n'
import { useInterval } from '../../lib/useInterval'
import type { Lang } from '../../lib/types'

interface Props {
  businessId: string
  defaultPhone?: string
  onReady?: () => void
}

export function LiveTestCard({ businessId, defaultPhone, onReady }: Props) {
  const { t, lang } = useI18n()
  const [phone, setPhone] = useState(defaultPhone ?? '')
  const [testLang, setTestLang] = useState<Lang>(lang)
  const [sending, setSending] = useState(false)
  const [started, setStarted] = useState(false)
  const [ok, setOk] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => { if (defaultPhone) setPhone(defaultPhone) }, [defaultPhone])

  const send = async () => {
    setError(null)
    setSending(true)
    try {
      await api.sendTestMessage(businessId, phone, testLang)
      setStarted(true)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'error')
    } finally {
      setSending(false)
    }
  }

  const poll = async () => {
    if (!started || ok) return
    try {
      const status = await api.getConversationTestStatus(businessId)
      if (status.ok) {
        setOk(true)
        onReady?.()
      }
    } catch {}
  }
  useInterval(poll, 3000, started && !ok)

  if (ok) {
    return (
      <div className="flex flex-col items-center gap-3 rounded-xl2 border border-moss-200 bg-moss-50 p-8 text-center">
        <CheckCircle2 className="h-10 w-10 text-moss-600" />
        <p className="font-semibold text-moss-900">{t('ready_title')}</p>
        <p className="text-sm text-moss-700">{t('ready_sub')}</p>
      </div>
    )
  }

  return (
    <div className="space-y-4 rounded-xl2 border border-ink-100 bg-surface p-6 shadow-card">
      <div className="grid gap-3 sm:grid-cols-[1fr_auto_auto]">
        <input value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="9665XXXXXXXX" dir="ltr"
          className="rounded-lg border border-ink-200 px-3 py-2.5 text-sm focus:border-moss-500 focus:outline-none focus:ring-2 focus:ring-moss-100" />
        <select value={testLang} onChange={(e) => setTestLang(e.target.value as Lang)}
          className="rounded-lg border border-ink-200 px-3 py-2.5 text-sm focus:border-moss-500 focus:outline-none focus:ring-2 focus:ring-moss-100">
          <option value="ar">العربية</option>
          <option value="en">English</option>
        </select>
        <button onClick={send} disabled={sending || !phone}
          className="inline-flex items-center justify-center gap-2 rounded-lg bg-moss-600 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-moss-700 disabled:opacity-50">
          <Send className="h-4 w-4" /> {t('send_test')}
        </button>
      </div>
      {error && <p className="text-sm text-rose-600">{error}</p>}
      {started && !ok && (
        <div className="flex items-center gap-2 rounded-lg bg-amber-100 px-4 py-3 text-sm text-amber-700">
          <span className="h-2 w-2 animate-pulse rounded-full bg-amber-600" />
          Reply from that phone now — checking automatically…
        </div>
      )}
    </div>
  )
}
