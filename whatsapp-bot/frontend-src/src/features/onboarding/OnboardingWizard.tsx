import { Plus, Trash2, X } from 'lucide-react'
import { useMemo, useState } from 'react'
import { api } from '../../lib/api'
import { useI18n } from '../../lib/i18n'
import type { BotTone, BusinessCreatePayload, HoursIn, ServiceIn } from '../../lib/types'
import { ConnectionCard } from '../whatsapp/ConnectionCard'
import { LiveTestCard } from '../whatsapp/LiveTestCard'
import { useWhatsAppConnection } from '../whatsapp/useWhatsAppConnection'

type Step = 1 | 2 | 3 | 4 | 5 | 6

const DAY_LABELS_AR = ['الأحد', 'الإثنين', 'الثلاثاء', 'الأربعاء', 'الخميس', 'الجمعة', 'السبت']
const DAY_LABELS_EN = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']

const TONES: { value: BotTone; ar: string; en: string }[] = [
  { value: 'friendly', ar: 'ودود', en: 'Friendly' },
  { value: 'professional', ar: 'احترافي', en: 'Professional' },
  { value: 'luxury', ar: 'راقي', en: 'Premium' },
  { value: 'concise', ar: 'مختصر', en: 'Concise' },
]

function defaultHours(): HoursIn[] {
  return Array.from({ length: 7 }, (_, day_of_week) => ({
    day_of_week,
    open_time: '10:00',
    close_time: '22:00',
    is_closed: false,
    is_ramadan: false,
  }))
}

interface Props {
  onClose: () => void
  onCreated: (businessId: string) => void
}

export function OnboardingWizard({ onClose, onCreated }: Props) {
  const { t, lang } = useI18n()
  const [step, setStep] = useState<Step>(1)
  const [creating, setCreating] = useState(false)
  const [createError, setCreateError] = useState<string | null>(null)
  const [businessId, setBusinessId] = useState<string | null>(null)
  const [initialQr, setInitialQr] = useState<string | null>(null)

  const [business, setBusiness] = useState({
    name_ar: '',
    name_en: '',
    phone: '',
    maps_url: '',
    vat_number: '',
    cr_number: '',
  })
  const [bot, setBot] = useState({
    bot_name_ar: '',
    bot_name_en: '',
    bot_tone: 'friendly' as BotTone,
    welcome_ar: '',
    welcome_en: '',
  })
  const [services, setServices] = useState<ServiceIn[]>([{ name_ar: '', name_en: '', duration_min: 30, price: 0, buffer_min: 0 }])
  const [hours, setHours] = useState<HoursIn[]>(defaultHours())
  const [ramadanMode, setRamadanMode] = useState(false)

  const conn = useWhatsAppConnection(businessId, initialQr)

  const businessValid = business.name_ar.trim() && business.name_en.trim() && business.phone.trim() && business.maps_url.trim()
  const servicesValid = services.length > 0 && services.every((s) => s.name_ar.trim() && s.name_en.trim() && s.duration_min > 0)

  const stepLabel = useMemo(() => {
    const labels = [
      t('ob_business_title'),
      t('ob_bot_title'),
      t('ob_services_title'),
      t('ob_hours_title'),
      t('ob_connect_title'),
      t('ob_test_title'),
    ]
    return labels[step - 1]
  }, [step, t])

  async function handleCreate() {
    setCreating(true)
    setCreateError(null)
    const activeHours = ramadanMode ? hours.map((h) => ({ ...h, is_ramadan: true })) : hours
    const payload: BusinessCreatePayload = {
      name_ar: business.name_ar,
      name_en: business.name_en,
      phone: business.phone,
      maps_url: business.maps_url,
      vat_number: business.vat_number || null,
      cr_number: business.cr_number || null,
      bot_name_ar: bot.bot_name_ar || null,
      bot_name_en: bot.bot_name_en || null,
      bot_tone: bot.bot_tone,
      welcome_ar: bot.welcome_ar || null,
      welcome_en: bot.welcome_en || null,
      services,
      hours: activeHours,
    }
    try {
      const res = await api.createBusiness(payload)
      setBusinessId(res.id)
      setInitialQr(res.qr)
      setStep(5)
    } catch (e) {
      setCreateError(e instanceof Error ? e.message : 'Failed to create business')
    } finally {
      setCreating(false)
    }
  }

  function finishLater() {
    if (businessId) onCreated(businessId)
    onClose()
  }

  function finishReady() {
    if (businessId) onCreated(businessId)
    onClose()
  }

  return (
    <div className="fixed inset-0 z-50 flex items-stretch justify-end bg-ink-900/50 sm:items-center sm:justify-center sm:p-6">
      <div className="flex h-full w-full flex-col bg-canvas sm:h-auto sm:max-h-[92vh] sm:w-full sm:max-w-3xl sm:rounded-2xl sm:shadow-pop">
        <div className="flex items-center justify-between border-b border-ink-100 bg-surface px-5 py-4 sm:rounded-t-2xl">
          <div>
            <p className="text-xs font-medium uppercase tracking-wide text-moss-600">
              {t('step')} {step} {t('of')} 6
            </p>
            <h2 className="text-lg font-semibold text-ink-900">{stepLabel}</h2>
          </div>
          {step < 5 && (
            <button onClick={onClose} className="rounded-lg p-2 text-ink-400 hover:bg-ink-100" aria-label="Close">
              <X className="h-5 w-5" />
            </button>
          )}
        </div>

        <div className="flex gap-1.5 bg-surface px-5 pb-4">
          {[1, 2, 3, 4, 5, 6].map((n) => (
            <div key={n} className={`h-1.5 flex-1 rounded-full ${n <= step ? 'bg-moss-600' : 'bg-ink-100'}`} />
          ))}
        </div>

        <div className="scrollbar-thin flex-1 overflow-y-auto px-5 py-6 sm:px-8">
          {step === 1 && (
            <div className="space-y-5">
              <p className="text-sm text-ink-500">{t('ob_business_sub')}</p>
              <div className="grid gap-4 sm:grid-cols-2">
                <Field label={lang === 'ar' ? 'اسم المنشأة بالعربي' : 'Business name (Arabic)'}>
                  <input className="input" value={business.name_ar} onChange={(e) => setBusiness({ ...business, name_ar: e.target.value })} />
                </Field>
                <Field label={lang === 'ar' ? 'اسم المنشأة بالإنجليزي' : 'Business name (English)'}>
                  <input dir="ltr" className="input" value={business.name_en} onChange={(e) => setBusiness({ ...business, name_en: e.target.value })} />
                </Field>
                <Field label={lang === 'ar' ? 'رقم واتساب' : 'WhatsApp number'}>
                  <input dir="ltr" placeholder="9665XXXXXXXX" className="input" value={business.phone} onChange={(e) => setBusiness({ ...business, phone: e.target.value })} />
                </Field>
                <Field label={lang === 'ar' ? 'رابط Google Maps' : 'Google Maps link'}>
                  <input dir="ltr" className="input" value={business.maps_url} onChange={(e) => setBusiness({ ...business, maps_url: e.target.value })} />
                </Field>
                <Field label={lang === 'ar' ? 'الرقم الضريبي (اختياري)' : 'VAT number (optional)'}>
                  <input className="input" value={business.vat_number} onChange={(e) => setBusiness({ ...business, vat_number: e.target.value })} />
                </Field>
                <Field label={lang === 'ar' ? 'السجل التجاري (اختياري)' : 'CR number (optional)'}>
                  <input className="input" value={business.cr_number} onChange={(e) => setBusiness({ ...business, cr_number: e.target.value })} />
                </Field>
              </div>
            </div>
          )}

          {step === 2 && (
            <div className="grid gap-6 lg:grid-cols-2">
              <div className="space-y-5">
                <p className="text-sm text-ink-500">{t('ob_bot_sub')}</p>
                <div className="grid gap-4 sm:grid-cols-2">
                  <Field label={lang === 'ar' ? 'اسم البوت بالعربي' : 'Bot name (Arabic)'}>
                    <input className="input" placeholder="موعدي" value={bot.bot_name_ar} onChange={(e) => setBot({ ...bot, bot_name_ar: e.target.value })} />
                  </Field>
                  <Field label={lang === 'ar' ? 'اسم البوت بالإنجليزي' : 'Bot name (English)'}>
                    <input dir="ltr" className="input" placeholder="Maw3idi" value={bot.bot_name_en} onChange={(e) => setBot({ ...bot, bot_name_en: e.target.value })} />
                  </Field>
                </div>
                <Field label={lang === 'ar' ? 'الأسلوب' : 'Tone'}>
                  <div className="flex flex-wrap gap-2">
                    {TONES.map((tone) => (
                      <button
                        key={tone.value}
                        onClick={() => setBot({ ...bot, bot_tone: tone.value })}
                        className={`rounded-full border px-4 py-1.5 text-sm font-medium transition ${bot.bot_tone === tone.value ? 'border-moss-600 bg-moss-600 text-white' : 'border-ink-200 text-ink-600 hover:border-moss-400'}`}
                      >
                        {lang === 'ar' ? tone.ar : tone.en}
                      </button>
                    ))}
                  </div>
                </Field>
                <Field label={lang === 'ar' ? 'رسالة ترحيب عربية (اختياري)' : 'Arabic welcome (optional)'}>
                  <textarea rows={2} className="input" value={bot.welcome_ar} onChange={(e) => setBot({ ...bot, welcome_ar: e.target.value })} />
                </Field>
                <Field label={lang === 'ar' ? 'رسالة ترحيب إنجليزية (اختياري)' : 'English welcome (optional)'}>
                  <textarea dir="ltr" rows={2} className="input" value={bot.welcome_en} onChange={(e) => setBot({ ...bot, welcome_en: e.target.value })} />
                </Field>
              </div>
              <ChatPreview business={business} bot={bot} lang={lang} />
            </div>
          )}

          {step === 3 && (
            <div className="space-y-4">
              <p className="text-sm text-ink-500">{t('ob_services_sub')}</p>
              {services.map((s, i) => (
                <div key={i} className="grid gap-3 rounded-xl2 border border-ink-100 bg-surface p-4 sm:grid-cols-[1fr_1fr_90px_100px_90px_auto]">
                  <input placeholder={lang === 'ar' ? 'الاسم بالعربي' : 'Name (Arabic)'} className="input" value={s.name_ar} onChange={(e) => updateService(i, { name_ar: e.target.value })} />
                  <input dir="ltr" placeholder="Name (English)" className="input" value={s.name_en} onChange={(e) => updateService(i, { name_en: e.target.value })} />
                  <input type="number" min={5} className="input" value={s.duration_min} onChange={(e) => updateService(i, { duration_min: Number(e.target.value) })} title={lang === 'ar' ? 'المدة (دقيقة)' : 'Duration (min)'} />
                  <input type="number" min={0} className="input" value={s.price} onChange={(e) => updateService(i, { price: Number(e.target.value) })} title={lang === 'ar' ? 'السعر (ريال)' : 'Price (SAR)'} />
                  <input type="number" min={0} className="input" value={s.buffer_min} onChange={(e) => updateService(i, { buffer_min: Number(e.target.value) })} title={lang === 'ar' ? 'وقت تجهيز' : 'Buffer (min)'} />
                  <button onClick={() => setServices(services.filter((_, idx) => idx !== i))} disabled={services.length === 1} className="rounded-lg p-2 text-ink-400 hover:bg-rose-100 hover:text-rose-600 disabled:opacity-30">
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
              ))}
              <button onClick={() => setServices([...services, { name_ar: '', name_en: '', duration_min: 30, price: 0, buffer_min: 0 }])}
                className="inline-flex items-center gap-1.5 rounded-lg border border-dashed border-ink-200 px-4 py-2 text-sm font-medium text-ink-500 hover:border-moss-400 hover:text-moss-700">
                <Plus className="h-4 w-4" /> {lang === 'ar' ? 'إضافة خدمة' : 'Add service'}
              </button>
            </div>
          )}

          {step === 4 && (
            <div className="space-y-4">
              <p className="text-sm text-ink-500">{t('ob_hours_sub')}</p>
              <label className="flex items-center gap-2 text-sm font-medium text-ink-700">
                <input type="checkbox" checked={ramadanMode} onChange={(e) => setRamadanMode(e.target.checked)} className="h-4 w-4 rounded border-ink-300 text-moss-600" />
                {lang === 'ar' ? 'استخدم جدول رمضان لهذه الساعات' : 'Mark these hours as Ramadan schedule'}
              </label>
              <div className="space-y-2">
                {hours.map((h, i) => (
                  <div key={i} className="grid grid-cols-[70px_1fr_1fr_auto] items-center gap-3 rounded-lg border border-ink-100 bg-surface px-3 py-2.5">
                    <span className="text-sm font-medium text-ink-700">{lang === 'ar' ? DAY_LABELS_AR[i] : DAY_LABELS_EN[i]}</span>
                    <input type="time" disabled={h.is_closed} value={h.open_time ?? ''} onChange={(e) => updateHour(i, { open_time: e.target.value })} className="input disabled:opacity-40" />
                    <input type="time" disabled={h.is_closed} value={h.close_time ?? ''} onChange={(e) => updateHour(i, { close_time: e.target.value })} className="input disabled:opacity-40" />
                    <label className="flex items-center gap-1.5 text-xs text-ink-500">
                      <input type="checkbox" checked={h.is_closed} onChange={(e) => updateHour(i, { is_closed: e.target.checked })} className="h-3.5 w-3.5 rounded border-ink-300" />
                      {lang === 'ar' ? 'مغلق' : 'Closed'}
                    </label>
                  </div>
                ))}
              </div>
            </div>
          )}

          {step === 5 && (
            <div className="space-y-4">
              <p className="text-sm text-ink-500">{t('ob_connect_sub')}</p>
              <ConnectionCard phase={conn.phase} qr={conn.qr} onRefresh={conn.refreshQr} />
              {conn.phase === 'connected' && (
                <div className="flex justify-center">
                  <button onClick={() => setStep(6)} className="rounded-lg bg-moss-600 px-6 py-2.5 text-sm font-semibold text-white hover:bg-moss-700">
                    {t('next')}
                  </button>
                </div>
              )}
            </div>
          )}

          {step === 6 && businessId && (
            <div className="space-y-4">
              <p className="text-sm text-ink-500">{t('ob_test_sub')}</p>
              <LiveTestCard businessId={businessId} onReady={() => {}} />
            </div>
          )}
        </div>

        <div className="flex items-center justify-between border-t border-ink-100 bg-surface px-5 py-4 sm:rounded-b-2xl">
          {step <= 4 ? (
            <>
              <button onClick={() => setStep((s) => (s > 1 ? ((s - 1) as Step) : s))} disabled={step === 1}
                className="rounded-lg px-4 py-2.5 text-sm font-medium text-ink-500 hover:bg-ink-100 disabled:opacity-30">
                {t('back')}
              </button>
              {step < 4 ? (
                <button onClick={() => setStep((s) => ((s + 1) as Step))}
                  disabled={(step === 1 && !businessValid) || (step === 3 && !servicesValid)}
                  className="rounded-lg bg-moss-600 px-6 py-2.5 text-sm font-semibold text-white hover:bg-moss-700 disabled:opacity-40">
                  {t('next')}
                </button>
              ) : (
                <button onClick={handleCreate} disabled={creating}
                  className="rounded-lg bg-moss-600 px-6 py-2.5 text-sm font-semibold text-white shadow-pop hover:bg-moss-700 disabled:opacity-60">
                  {creating ? t('saving') : t('createConnect')}
                </button>
              )}
            </>
          ) : step === 5 ? (
            <button onClick={finishLater} className="ms-auto rounded-lg px-4 py-2.5 text-sm font-medium text-ink-400 hover:bg-ink-100">
              {t('finishLater')}
            </button>
          ) : (
            <button onClick={finishReady} className="ms-auto rounded-lg bg-ink-900 px-6 py-2.5 text-sm font-semibold text-white hover:bg-ink-700">
              {t('goToDashboard')}
            </button>
          )}
        </div>
        {createError && <p className="bg-rose-50 px-5 py-2 text-center text-sm text-rose-600">{createError}</p>}
      </div>
    </div>
  )

  function updateService(index: number, patch: Partial<ServiceIn>) {
    setServices((prev) => prev.map((s, i) => (i === index ? { ...s, ...patch } : s)))
  }
  function updateHour(index: number, patch: Partial<HoursIn>) {
    setHours((prev) => prev.map((h, i) => (i === index ? { ...h, ...patch } : h)))
  }
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-xs font-medium text-ink-500">{label}</span>
      {children}
    </label>
  )
}

function ChatPreview({ business, bot, lang }: {
  business: { name_ar: string; name_en: string }
  bot: { bot_name_ar: string; bot_name_en: string; welcome_ar: string; welcome_en: string }
  lang: 'ar' | 'en'
}) {
  const botName = (lang === 'ar' ? bot.bot_name_ar : bot.bot_name_en) || (lang === 'ar' ? 'موعدي' : 'Maw3idi')
  const welcome = (lang === 'ar' ? bot.welcome_ar : bot.welcome_en) ||
    (lang === 'ar'
      ? `أهلاً بك في ${business.name_ar || 'منشأتك'} 👋 أنا ${botName}، كيف أقدر أساعدك اليوم؟`
      : `Welcome to ${business.name_en || 'your business'} 👋 I'm ${botName}, how can I help today?`)
  return (
    <div className="rounded-xl2 bg-ink-900 p-4 sm:sticky sm:top-0">
      <div className="mb-3 flex items-center gap-2 text-white/70">
        <div className="h-2 w-2 rounded-full bg-moss-400" />
        <span className="text-xs font-medium">{lang === 'ar' ? 'معاينة محادثة العميل' : 'Customer chat preview'}</span>
      </div>
      <div className="space-y-2">
        <Bubble text={'اختر اللغة / Choose your language\n\n1. العربية\n2. English'} />
        <Bubble text={lang === 'ar' ? '1' : '2'} outgoing />
        <Bubble text={welcome} />
      </div>
    </div>
  )
}

function Bubble({ text, outgoing }: { text: string; outgoing?: boolean }) {
  return (
    <div className={`flex ${outgoing ? 'justify-end' : 'justify-start'}`}>
      <div className={`max-w-[85%] whitespace-pre-line rounded-2xl px-3.5 py-2.5 text-sm ${outgoing ? 'bg-moss-500 text-white' : 'bg-white/95 text-ink-900'}`}>
        {text}
      </div>
    </div>
  )
}
