import { PowerOff } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useBusinesses } from '../lib/BusinessContext'
import { useI18n } from '../lib/i18n'
import { api, ApiError } from '../lib/api'
import { ConnectionCard } from '../features/whatsapp/ConnectionCard'
import { LiveTestCard } from '../features/whatsapp/LiveTestCard'
import { useWhatsAppConnection } from '../features/whatsapp/useWhatsAppConnection'
import type { ClientDefaults } from '../lib/types'

export default function BotWhatsApp() {
  const { lang } = useI18n()
  const { selectedId, selected } = useBusinesses()
  const conn = useWhatsAppConnection(selectedId)
  const [defaults, setDefaults] = useState<ClientDefaults | null>(null)
  const [confirmingDisconnect, setConfirmingDisconnect] = useState(false)
  const [disconnecting, setDisconnecting] = useState(false)
  const [disconnectError, setDisconnectError] = useState<string | null>(null)
  useEffect(() => { api.clientDefaults().then(setDefaults).catch(() => {}) }, [])
  if (!selectedId) return <p className="text-sm text-ink-400">{lang === 'ar' ? 'اختر منشأة أولاً' : 'Select a business first'}</p>
  async function disconnect() {
    setDisconnecting(true); setDisconnectError(null)
    try { await api.disconnectWhatsApp(selectedId!); setConfirmingDisconnect(false); conn.refreshQr() }
    catch (e) { setDisconnectError(e instanceof ApiError ? e.message : lang === 'ar' ? 'تعذر قطع الاتصال' : 'Could not disconnect') }
    finally { setDisconnecting(false) }
  }
  return (
    <div className="space-y-6">
      <div className="grid gap-6 lg:grid-cols-[1.1fr_0.9fr]">
        <div className="space-y-3"><h3 className="text-sm font-semibold text-ink-900">{lang === 'ar' ? 'الاتصال' : 'Connection'}</h3><ConnectionCard phase={conn.phase} qr={conn.qr} onRefresh={conn.refreshQr} /></div>
        <div className="space-y-4">
          <div className="rounded-xl2 border border-ink-100 bg-surface p-5 shadow-card">
            <h3 className="mb-3 text-sm font-semibold text-ink-900">{lang === 'ar' ? 'رقم المنشأة المرتبط' : 'Linked business number'}</h3>
            <dl className="space-y-2 text-sm">
              <Row label={lang === 'ar' ? 'الاسم' : 'Name'} value={lang === 'ar' ? selected?.name_ar : selected?.name_en} />
              <Row label={lang === 'ar' ? 'الهاتف' : 'Phone'} value={selected?.phone} dir="ltr" />
              <Row label={lang === 'ar' ? 'معرّف الجلسة' : 'Session ID'} value={selected?.whatsapp_session_id} dir="ltr" mono />
              <Row label={lang === 'ar' ? 'الحالة' : 'State'} value={conn.phase === 'connected' ? (lang === 'ar' ? 'متصل' : 'Connected') : conn.phase === 'test' ? (lang === 'ar' ? 'وضع اختبار' : 'Test mode') : lang === 'ar' ? 'غير متصل' : 'Not connected'} />
            </dl>
          </div>
          {conn.phase === 'connected' && (
            <div className="rounded-xl2 border border-rose-100 bg-rose-50/60 p-5">
              {!confirmingDisconnect ? <button onClick={() => setConfirmingDisconnect(true)} className="inline-flex items-center gap-2 rounded-lg border border-rose-200 px-4 py-2 text-sm font-medium text-rose-600 hover:bg-rose-100"><PowerOff className="h-4 w-4" /> {lang === 'ar' ? 'قطع اتصال واتساب' : 'Disconnect WhatsApp'}</button> :
                <div className="space-y-3"><p className="text-sm font-medium text-rose-700">{lang === 'ar' ? 'سيتوقف البوت عن استقبال الرسائل حتى تعيد الربط بمسح QR جديد. متأكد؟' : "The bot will stop receiving messages until you reconnect with a new QR scan. Are you sure?"}</p><div className="flex gap-2"><button onClick={disconnect} disabled={disconnecting} className="rounded-lg bg-rose-600 px-4 py-2 text-sm font-semibold text-white hover:bg-rose-700 disabled:opacity-60">{disconnecting ? (lang === 'ar' ? 'جاري القطع...' : 'Disconnecting…') : lang === 'ar' ? 'نعم، اقطع الاتصال' : 'Yes, disconnect'}</button><button onClick={() => setConfirmingDisconnect(false)} className="rounded-lg px-4 py-2 text-sm font-medium text-ink-500 hover:bg-ink-100">{lang === 'ar' ? 'إلغاء' : 'Cancel'}</button></div>{disconnectError && <p className="text-sm text-rose-600">{disconnectError}</p>}</div>}
            </div>
          )}
        </div>
      </div>
      <div className="space-y-3"><h3 className="text-sm font-semibold text-ink-900">{lang === 'ar' ? 'اختبار حقيقي' : 'Real test'}</h3><LiveTestCard businessId={selectedId} defaultPhone={defaults?.test_phone} /></div>
    </div>
  )
}
function Row({ label, value, dir, mono }: { label: string; value?: string | null; dir?: 'ltr' | 'rtl'; mono?: boolean }) {
  return <div className="flex items-center justify-between gap-3"><dt className="text-ink-400">{label}</dt><dd dir={dir} className={`truncate text-ink-900 ${mono ? 'font-mono text-xs' : 'font-medium'}`}>{value || '—'}</dd></div>
}
