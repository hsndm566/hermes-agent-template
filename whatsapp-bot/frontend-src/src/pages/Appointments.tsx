import { useEffect, useState } from 'react'
import { api, ApiError } from '../lib/api'
import { useBusinesses } from '../lib/BusinessContext'
import { useI18n } from '../lib/i18n'
import type { AppointmentRow } from '../lib/types'

const FILTERS = ['all', 'upcoming', 'completed', 'cancelled', 'no_show'] as const
const UPCOMING_STATUSES = new Set(['confirmed', 'rescheduled'])

export default function Appointments() {
  const { lang } = useI18n()
  const { selectedId } = useBusinesses()
  const [rows, setRows] = useState<AppointmentRow[]>([])
  const [filter, setFilter] = useState<(typeof FILTERS)[number]>('all')
  const [busyId, setBusyId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function load() { if (selectedId) setRows(await api.getAppointments(selectedId)) }
  useEffect(() => { load() }, [selectedId])
  if (!selectedId) return <p className="text-sm text-ink-400">{lang === 'ar' ? 'اختر منشأة أولاً' : 'Select a business first'}</p>

  const filtered = rows.filter((r) => filter === 'all' ? true : filter === 'upcoming' ? UPCOMING_STATUSES.has(r.status) : r.status === filter)
  const filterLabel: Record<(typeof FILTERS)[number], { ar: string; en: string }> = {
    all: { ar: 'الكل', en: 'All' }, upcoming: { ar: 'قادمة', en: 'Upcoming' }, completed: { ar: 'مكتملة', en: 'Completed' }, cancelled: { ar: 'ملغاة', en: 'Cancelled' }, no_show: { ar: 'لم يحضر', en: 'No-show' },
  }
  async function act(id: string, action: 'cancel' | 'complete' | 'no_show') {
    setBusyId(id); setError(null)
    try { await api.updateAppointment(selectedId!, id, action); await load() }
    catch (e) { setError(e instanceof ApiError ? e.message : lang === 'ar' ? 'حدث خطأ' : 'Something went wrong') }
    finally { setBusyId(null) }
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-2">{FILTERS.map((f) => <button key={f} onClick={() => setFilter(f)} className={`rounded-full px-3.5 py-1.5 text-xs font-medium ${filter === f ? 'bg-moss-600 text-white' : 'bg-ink-100 text-ink-600'}`}>{lang === 'ar' ? filterLabel[f].ar : filterLabel[f].en}</button>)}</div>
      {error && <p className="text-sm text-rose-600">{error}</p>}
      <div className="overflow-hidden rounded-xl2 border border-ink-100 bg-surface shadow-card">
        <table className="w-full text-sm">
          <thead className="bg-canvas text-xs text-ink-400"><tr><Th>{lang === 'ar' ? 'العميل' : 'Customer'}</Th><Th>{lang === 'ar' ? 'الخدمة' : 'Service'}</Th><Th>{lang === 'ar' ? 'الموظف' : 'Staff'}</Th><Th>{lang === 'ar' ? 'الوقت' : 'Time'}</Th><Th>{lang === 'ar' ? 'الحالة' : 'Status'}</Th><Th>{lang === 'ar' ? 'إجراء' : 'Action'}</Th></tr></thead>
          <tbody className="divide-y divide-ink-100">
            {filtered.map((r) => <tr key={r.id}>
              <Td><p className="font-medium text-ink-900">{r.customer_name || '—'}</p><p dir="ltr" className="text-xs text-ink-400">{r.customer_phone}</p></Td>
              <Td>{lang === 'ar' ? r.name_ar : r.name_en}</Td><Td>{lang === 'ar' ? r.staff_ar : r.staff_en}</Td><Td dir="ltr">{new Date(r.start_time).toLocaleString(lang === 'ar' ? 'ar-SA' : 'en-US')}</Td><Td><StatusPill status={r.status} lang={lang} /></Td>
              <Td>{UPCOMING_STATUSES.has(r.status) ? <div className="flex flex-wrap gap-1.5"><ActionBtn onClick={() => act(r.id, 'complete')} busy={busyId === r.id} label={lang === 'ar' ? 'إتمام' : 'Complete'} /><ActionBtn onClick={() => act(r.id, 'no_show')} busy={busyId === r.id} label={lang === 'ar' ? 'لم يحضر' : 'No-show'} tone="amber" /><ActionBtn onClick={() => act(r.id, 'cancel')} busy={busyId === r.id} label={lang === 'ar' ? 'إلغاء' : 'Cancel'} tone="rose" /></div> : <span className="text-xs text-ink-300">—</span>}</Td>
            </tr>)}
            {filtered.length === 0 && <tr><td colSpan={6} className="px-4 py-10 text-center text-sm text-ink-400">{lang === 'ar' ? 'لا توجد حجوزات' : 'No appointments'}</td></tr>}
          </tbody>
        </table>
      </div>
      <p className="text-xs text-ink-400">{lang === 'ar' ? 'إعادة الجدولة من لوحة التحكم (باختيار موعد جديد) غير متاحة بعد — يمكن للعميل إعادة الجدولة عبر واتساب مباشرة.' : "Reschedule-with-a-new-slot from the dashboard isn't available yet — customers can still reschedule directly over WhatsApp."}</p>
    </div>
  )
}
function Th({ children }: { children: React.ReactNode }) { return <th className="px-4 py-2.5 text-start font-medium">{children}</th> }
function Td({ children, dir }: { children: React.ReactNode; dir?: 'ltr' }) { return <td dir={dir} className="px-4 py-3">{children}</td> }
function StatusPill({ status, lang }: { status: string; lang: 'ar' | 'en' }) {
  const map: Record<string, { ar: string; en: string; cls: string }> = {
    confirmed: { ar: 'قادم', en: 'Upcoming', cls: 'bg-moss-100 text-moss-700' }, rescheduled: { ar: 'أُعيدت جدولته', en: 'Rescheduled', cls: 'bg-moss-100 text-moss-700' }, completed: { ar: 'مكتمل', en: 'Completed', cls: 'bg-ink-100 text-ink-600' }, cancelled: { ar: 'ملغى', en: 'Cancelled', cls: 'bg-rose-100 text-rose-600' }, no_show: { ar: 'لم يحضر', en: 'No-show', cls: 'bg-amber-100 text-amber-700' },
  }
  const m = map[status] ?? { ar: status, en: status, cls: 'bg-ink-100 text-ink-600' }
  return <span className={`rounded-full px-2.5 py-1 text-xs font-medium ${m.cls}`}>{lang === 'ar' ? m.ar : m.en}</span>
}
function ActionBtn({ onClick, busy, label, tone }: { onClick: () => void; busy: boolean; label: string; tone?: 'amber' | 'rose' }) {
  const cls = tone === 'rose' ? 'border-rose-200 text-rose-600 hover:bg-rose-50' : tone === 'amber' ? 'border-amber-200 text-amber-700 hover:bg-amber-50' : 'border-moss-200 text-moss-700 hover:bg-moss-50'
  return <button onClick={onClick} disabled={busy} className={`rounded-md border px-2 py-1 text-xs font-medium transition disabled:opacity-40 ${cls}`}>{label}</button>
}
