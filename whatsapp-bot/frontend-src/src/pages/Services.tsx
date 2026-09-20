import { Plus, Trash2 } from 'lucide-react'
import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import { useBusinesses } from '../lib/BusinessContext'
import { useI18n } from '../lib/i18n'
import type { ServiceIn } from '../lib/types'
export default function Services() {
  const { lang } = useI18n(); const { selectedId } = useBusinesses(); const [services, setServices] = useState<ServiceIn[]>([]); const [saving, setSaving] = useState(false); const [savedAt, setSavedAt] = useState<number | null>(null)
  useEffect(() => { if (selectedId) api.getBusiness(selectedId).then((d) => setServices(d.services)) }, [selectedId])
  if (!selectedId) return <p className="text-sm text-ink-400">{lang === 'ar' ? 'اختر منشأة أولاً' : 'Select a business first'}</p>
  async function save() { if (!selectedId) return; setSaving(true); try { await api.putServices(selectedId, services); const fresh = await api.getBusiness(selectedId); setServices(fresh.services); setSavedAt(Date.now()) } finally { setSaving(false) } }
  return <div className="space-y-4">
    <p className="text-sm text-ink-500">{lang === 'ar' ? 'وقت التجهيز يمنع حجز موعد آخر مباشرة بعد الخدمة.' : 'Buffer time blocks another booking right after this service.'}</p>
    {services.map((s, i) => <div key={i} className="grid gap-3 rounded-xl2 border border-ink-100 bg-surface p-4 sm:grid-cols-[1fr_1fr_90px_100px_90px_auto]"><input placeholder={lang === 'ar' ? 'الاسم بالعربي' : 'Name (Arabic)'} className="input" value={s.name_ar} onChange={(e) => update(i, { name_ar: e.target.value })} /><input dir="ltr" placeholder="Name (English)" className="input" value={s.name_en} onChange={(e) => update(i, { name_en: e.target.value })} /><input type="number" min={5} className="input" value={s.duration_min} onChange={(e) => update(i, { duration_min: Number(e.target.value) })} title="Duration (min)" /><input type="number" min={0} className="input" value={s.price} onChange={(e) => update(i, { price: Number(e.target.value) })} title="Price (SAR)" /><input type="number" min={0} className="input" value={s.buffer_min} onChange={(e) => update(i, { buffer_min: Number(e.target.value) })} title="Buffer (min)" /><button onClick={() => setServices(services.filter((_, idx) => idx !== i))} className="rounded-lg p-2 text-ink-400 hover:bg-rose-100 hover:text-rose-600"><Trash2 className="h-4 w-4" /></button></div>)}
    <div className="flex items-center justify-between"><button onClick={() => setServices([...services, { name_ar: '', name_en: '', duration_min: 30, price: 0, buffer_min: 0 }])} className="inline-flex items-center gap-1.5 rounded-lg border border-dashed border-ink-200 px-4 py-2 text-sm font-medium text-ink-500 hover:border-moss-400 hover:text-moss-700"><Plus className="h-4 w-4" /> {lang === 'ar' ? 'إضافة خدمة' : 'Add service'}</button><div className="flex items-center gap-3">{savedAt && Date.now() - savedAt < 4000 && <span className="text-xs text-moss-600">{lang === 'ar' ? 'تم الحفظ' : 'Saved'}</span>}<button onClick={save} disabled={saving} className="rounded-lg bg-moss-600 px-5 py-2.5 text-sm font-semibold text-white hover:bg-moss-700 disabled:opacity-60">{saving ? (lang === 'ar' ? 'جاري الحفظ...' : 'Saving…') : lang === 'ar' ? 'حفظ التغييرات' : 'Save changes'}</button></div></div>
  </div>
  function update(index: number, patch: Partial<ServiceIn>) { setServices((prev) => prev.map((s, i) => (i === index ? { ...s, ...patch } : s))) }
}
