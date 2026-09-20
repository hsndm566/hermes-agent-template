import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import { useBusinesses } from '../lib/BusinessContext'
import { useI18n } from '../lib/i18n'
import type { CustomerRow } from '../lib/types'
export default function Customers() {
  const { lang } = useI18n(); const { selectedId } = useBusinesses(); const [customers, setCustomers] = useState<CustomerRow[]>([])
  useEffect(() => { if (selectedId) api.getCustomers(selectedId).then(setCustomers) }, [selectedId])
  if (!selectedId) return <p className="text-sm text-ink-400">{lang === 'ar' ? 'اختر منشأة أولاً' : 'Select a business first'}</p>
  return <div className="space-y-4"><div className="overflow-hidden rounded-xl2 border border-ink-100 bg-surface shadow-card"><table className="w-full text-sm"><thead className="bg-canvas text-xs text-ink-400"><tr><th className="px-4 py-2.5 text-start font-medium">{lang === 'ar' ? 'العميل' : 'Customer'}</th><th className="px-4 py-2.5 text-start font-medium">{lang === 'ar' ? 'اللغة المفضلة' : 'Preferred language'}</th><th className="px-4 py-2.5 text-start font-medium">{lang === 'ar' ? 'مرات عدم الحضور' : 'No-shows'}</th><th className="px-4 py-2.5 text-start font-medium">{lang === 'ar' ? 'آخر زيارة' : 'Last visit'}</th></tr></thead><tbody className="divide-y divide-ink-100">{customers.map((c) => <tr key={c.id}><td className="px-4 py-3"><p className="font-medium text-ink-900">{c.name || '—'}</p><p dir="ltr" className="text-xs text-ink-400">{c.phone}</p></td><td className="px-4 py-3">{c.preferred_language === 'ar' ? 'العربية' : c.preferred_language === 'en' ? 'English' : '—'}</td><td className="px-4 py-3">{c.no_show_count > 0 ? <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-700">{c.no_show_count}</span> : '—'}</td><td dir="ltr" className="px-4 py-3">{c.last_visit ? new Date(c.last_visit).toLocaleDateString() : '—'}</td></tr>)}{customers.length === 0 && <tr><td colSpan={4} className="px-4 py-10 text-center text-sm text-ink-400">{lang === 'ar' ? 'لا يوجد عملاء بعد' : 'No customers yet'}</td></tr>}</tbody></table></div></div>
}
