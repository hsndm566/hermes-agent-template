import { CalendarCheck, MessageCircle, Users, Wallet } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../lib/api'
import { useBusinesses } from '../lib/BusinessContext'
import { useI18n } from '../lib/i18n'
import { useInterval } from '../lib/useInterval'
import type { AppointmentRow, BusinessDetail, ConversationTestStatus } from '../lib/types'

export default function Overview() {
  const { lang } = useI18n()
  const { selectedId, selected } = useBusinesses()
  const [detail, setDetail] = useState<BusinessDetail | null>(null)
  const [appointments, setAppointments] = useState<AppointmentRow[]>([])
  const [connState, setConnState] = useState<string | null>(null)
  const [testStatus, setTestStatus] = useState<ConversationTestStatus | null>(null)
  async function load() {
    if (!selectedId) return
    const [d, appts, conn, ts] = await Promise.all([
      api.getBusiness(selectedId), api.getAppointments(selectedId),
      api.getConnection(selectedId).catch(() => null),
      api.getConversationTestStatus(selectedId).catch(() => null),
    ])
    setDetail(d); setAppointments(appts); setConnState(conn?.instance?.state ?? conn?.state ?? null); setTestStatus(ts)
  }
  useEffect(() => { load() }, [selectedId])
  useInterval(load, 15000, !!selectedId)
  if (!selectedId) return <EmptyBusinessState />
  if (!detail) return <div className="text-sm text-ink-400">…</div>
  const connected = connState === 'open' || connState === 'connected'
  const ready = connected && !!testStatus?.ok
  const today = new Date().toDateString()
  const upcoming = appointments.filter((a) => a.status === 'confirmed' || a.status === 'rescheduled')
  const todayCount = upcoming.filter((a) => new Date(a.start_time).toDateString() === today).length
  const upcomingCount = upcoming.filter((a) => new Date(a.start_time) > new Date()).length
  const uniqueCustomers = new Set(appointments.map((a) => a.customer_phone)).size
  const onboardingSteps = [
    { done: true, label: lang === 'ar' ? 'تمت إضافة المنشأة' : 'Business created' },
    { done: connected, label: lang === 'ar' ? 'ربط واتساب' : 'WhatsApp connected' },
    { done: !!testStatus?.ok, label: lang === 'ar' ? 'اختبار حقيقي ناجح' : 'Real test verified' },
  ]
  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 rounded-xl2 border border-ink-100 bg-surface p-6 shadow-card sm:flex-row sm:items-center sm:justify-between">
        <div><p className="text-xs font-medium uppercase tracking-wide text-ink-300">{lang === 'ar' ? 'الحالة' : 'Status'}</p><h2 className="text-xl font-semibold text-ink-900">{lang === 'ar' ? selected?.name_ar : selected?.name_en}</h2></div>
        <div className={`inline-flex items-center gap-2 self-start rounded-full px-4 py-2 text-sm font-semibold ${ready ? 'bg-moss-100 text-moss-700' : connected ? 'bg-amber-100 text-amber-700' : 'bg-rose-100 text-rose-600'}`}>
          <span className={`h-2 w-2 rounded-full ${ready ? 'bg-moss-600' : connected ? 'bg-amber-600' : 'bg-rose-600'}`} />
          {ready ? (lang === 'ar' ? 'جاهز لاستقبال العملاء' : 'Ready for customers') : connected ? (lang === 'ar' ? 'متصل — بانتظار اختبار حقيقي' : 'Connected — real test pending') : (lang === 'ar' ? 'واتساب غير متصل' : 'WhatsApp not connected')}
        </div>
      </div>
      {!ready && (
        <div className="rounded-xl2 border border-amber-200 bg-amber-100/60 p-5">
          <p className="mb-3 text-sm font-semibold text-amber-800">{lang === 'ar' ? 'أكمل الإعداد للوصول لأول عميل' : 'Finish setup to go live'}</p>
          <div className="flex flex-wrap gap-3">{onboardingSteps.map((s, i) => <div key={i} className={`flex items-center gap-2 rounded-full px-3 py-1.5 text-xs font-medium ${s.done ? 'bg-moss-600 text-white' : 'bg-white text-ink-500'}`}>{s.done ? '✓' : i + 1} {s.label}</div>)}</div>
          <Link to="/whatsapp" className="mt-3 inline-block text-sm font-semibold text-moss-700 underline">{lang === 'ar' ? 'اذهب إلى صفحة واتساب' : 'Go to WhatsApp page'}</Link>
        </div>
      )}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard icon={CalendarCheck} label={lang === 'ar' ? 'حجوزات اليوم' : "Today's appointments"} value={todayCount} />
        <StatCard icon={CalendarCheck} label={lang === 'ar' ? 'الحجوزات القادمة' : 'Upcoming'} value={upcomingCount} />
        <StatCard icon={Users} label={lang === 'ar' ? 'العملاء' : 'Customers'} value={uniqueCustomers} />
        <StatCard icon={Wallet} label={lang === 'ar' ? 'الخدمات' : 'Services'} value={detail.services.length} />
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <div className="rounded-xl2 border border-ink-100 bg-surface p-5 shadow-card">
          <h3 className="mb-3 text-sm font-semibold text-ink-900">{lang === 'ar' ? 'أقرب الحجوزات' : 'Upcoming appointments'}</h3>
          {upcoming.slice(0, 6).length === 0 ? <p className="text-sm text-ink-400">{lang === 'ar' ? 'لا توجد حجوزات بعد' : 'No appointments yet'}</p> :
            <ul className="divide-y divide-ink-100">{upcoming.slice(0, 6).map((a) => <li key={a.id} className="flex items-center justify-between py-2.5 text-sm"><div><p className="font-medium text-ink-900">{a.customer_name || a.customer_phone}</p><p className="text-xs text-ink-400">{lang === 'ar' ? a.name_ar : a.name_en}</p></div><span className="text-xs text-ink-500">{new Date(a.start_time).toLocaleString(lang === 'ar' ? 'ar-SA' : 'en-US')}</span></li>)}</ul>}
        </div>
        <div className="rounded-xl2 border border-ink-100 bg-surface p-5 shadow-card">
          <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold text-ink-900"><MessageCircle className="h-4 w-4 text-moss-600" /> {lang === 'ar' ? 'آخر تفاعل من عميل' : 'Latest customer activity'}</h3>
          {testStatus?.last_inbound_text ? <div className="rounded-lg bg-canvas p-3 text-sm"><p className="font-medium text-ink-900">{testStatus.last_inbound_phone}</p><p className="mt-1 text-ink-600">{testStatus.last_inbound_text}</p>{testStatus.last_inbound_at && <p className="mt-1 text-xs text-ink-400">{new Date(testStatus.last_inbound_at).toLocaleString(lang === 'ar' ? 'ar-SA' : 'en-US')}</p>}</div> : <p className="text-sm text-ink-400">{lang === 'ar' ? 'لا يوجد نشاط بعد' : 'No activity yet'}</p>}
        </div>
      </div>
    </div>
  )
}
function StatCard({ icon: Icon, label, value }: { icon: typeof Users; label: string; value: number }) { return <div className="rounded-xl2 border border-ink-100 bg-surface p-4 shadow-card"><Icon className="mb-2 h-4 w-4 text-moss-600" strokeWidth={1.75} /><p className="text-2xl font-semibold text-ink-900">{value}</p><p className="text-xs text-ink-500">{label}</p></div> }
function EmptyBusinessState() { const { lang } = useI18n(); return <div className="flex h-full flex-col items-center justify-center gap-3 rounded-xl2 border border-dashed border-ink-200 bg-surface py-24 text-center"><div className="flex h-14 w-14 items-center justify-center rounded-full bg-moss-100 text-xl font-bold text-moss-700">1</div><h2 className="text-lg font-semibold text-ink-900">{lang === 'ar' ? 'أضف أول منشأة' : 'Add your first business'}</h2><p className="max-w-sm text-sm text-ink-500">{lang === 'ar' ? 'استخدم زر "+ منشأة جديدة" في الشريط الجانبي للبدء.' : 'Use "+ New business" in the sidebar to get started.'}</p></div> }
