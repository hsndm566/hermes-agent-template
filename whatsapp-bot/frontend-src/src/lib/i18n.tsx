import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import type { Lang } from './types'

const dict = {
  ar: {
    appName: 'موعدي',
    tagline: 'استقبال حجوزات واتساب بالذكاء الاصطناعي',
    nav_overview: 'الرئيسية',
    nav_conversations: 'المحادثات',
    nav_appointments: 'الحجوزات',
    nav_customers: 'العملاء',
    nav_services: 'الخدمات',
    nav_team: 'الفريق',
    nav_availability: 'أوقات العمل',
    nav_whatsapp: 'البوت وواتساب',
    nav_automations: 'الأتمتة',
    nav_settings: 'الإعدادات',
    switchBusiness: 'المنشأة',
    addBusiness: '+ منشأة جديدة',
    login: 'دخول',
    username: 'اسم المستخدم',
    password: 'كلمة المرور',
    logout: 'تسجيل الخروج',
    loginHelp: 'ادخل لوحة التحكم لإدارة الحجوزات وربط واتساب.',
    back: 'السابق',
    next: 'التالي',
    cancel: 'إلغاء',
    save: 'حفظ',
    saving: 'جاري الحفظ...',
    step: 'خطوة',
    of: 'من',
    ob_business_title: 'بيانات المنشأة',
    ob_business_sub: 'المعلومات الأساسية التي يراها عملاؤك في الحجز والتأكيد.',
    ob_bot_title: 'شخصية البوت',
    ob_bot_sub: 'اختر كيف يتحدث البوت مع عملاء هذه المنشأة، وشاهد معاينة حية.',
    ob_services_title: 'الخدمات',
    ob_services_sub: 'أضف خدمة واحدة على الأقل. يمكنك تعديلها لاحقاً في أي وقت.',
    ob_hours_title: 'أوقات العمل',
    ob_hours_sub: 'حدد ساعات العمل الأسبوعية، ووضع رمضان إن رغبت.',
    ob_connect_title: 'ربط واتساب',
    ob_connect_sub: 'هذه الخطوة الأهم — بدون ربط واتساب لن يستقبل البوت أي رسائل.',
    ob_test_title: 'اختبار حقيقي',
    ob_test_sub: 'أرسل رسالة اختبار حقيقية وتأكد من وصول الرد قبل الإطلاق.',
    createConnect: 'إنشاء المنشأة والمتابعة لربط واتساب',
    finishLater: 'إنهاء لاحقاً',
    qr_instructions: 'واتساب ← الإعدادات ← الأجهزة المرتبطة ← ربط جهاز',
    qr_refresh: 'تحديث رمز QR',
    qr_waiting: 'بانتظار المسح…',
    qr_connected: 'تم الربط بنجاح',
    qr_creating: 'جاري إنشاء الاتصال…',
    qr_failed: 'تعذّر إنشاء الاتصال',
    retry: 'إعادة المحاولة',
    send_test: 'إرسال رسالة اختبار',
    check_reply: 'التحقق من الرد',
    ready_title: 'بوت واتساب الخاص بك جاهز الآن',
    ready_sub: 'تم التحقق من الاتصال والرد الحقيقي. يمكنك استقبال العملاء الآن.',
    goToDashboard: 'الانتقال إلى لوحة التحكم',
    recipientPhone: 'رقم المستلم للاختبار',
    testLanguage: 'لغة الاختبار',
  },
  en: {
    appName: 'Maw3idi',
    tagline: 'AI WhatsApp booking receptionist',
    nav_overview: 'Overview',
    nav_conversations: 'Conversations',
    nav_appointments: 'Appointments',
    nav_customers: 'Customers',
    nav_services: 'Services',
    nav_team: 'Team',
    nav_availability: 'Availability',
    nav_whatsapp: 'Bot & WhatsApp',
    nav_automations: 'Automations',
    nav_settings: 'Settings',
    switchBusiness: 'Business',
    addBusiness: '+ New business',
    login: 'Sign in',
    username: 'Username',
    password: 'Password',
    logout: 'Log out',
    loginHelp: 'Sign in to manage bookings and connect WhatsApp.',
    back: 'Back',
    next: 'Next',
    cancel: 'Cancel',
    save: 'Save',
    saving: 'Saving…',
    step: 'Step',
    of: 'of',
    ob_business_title: 'Business details',
    ob_business_sub: 'The basics your customers see in booking confirmations.',
    ob_bot_title: 'Bot personality',
    ob_bot_sub: "Choose how the bot talks to this business's customers, with a live preview.",
    ob_services_title: 'Services',
    ob_services_sub: 'Add at least one service. You can edit these anytime later.',
    ob_hours_title: 'Working hours',
    ob_hours_sub: 'Set your weekly schedule, plus an optional Ramadan mode.',
    ob_connect_title: 'Connect WhatsApp',
    ob_connect_sub: "The most important step — without this the bot can't receive messages.",
    ob_test_title: 'Real test',
    ob_test_sub: 'Send a real test message and confirm a reply arrives before going live.',
    createConnect: 'Create business & connect WhatsApp',
    finishLater: 'Finish later',
    qr_instructions: 'WhatsApp → Settings → Linked Devices → Link a Device',
    qr_refresh: 'Refresh QR code',
    qr_waiting: 'Waiting for scan…',
    qr_connected: 'Connected successfully',
    qr_creating: 'Creating connection…',
    qr_failed: 'Could not create the connection',
    retry: 'Retry',
    send_test: 'Send test message',
    check_reply: 'Check for reply',
    ready_title: 'Your WhatsApp receptionist is live',
    ready_sub: 'Connection and a real reply were verified. You can start receiving customers now.',
    goToDashboard: 'Go to dashboard',
    recipientPhone: 'Recipient phone for the test',
    testLanguage: 'Test language',
  },
} as const

type DictKey = keyof typeof dict.ar
interface I18nContextValue {
  lang: Lang
  dir: 'rtl' | 'ltr'
  t: (key: DictKey) => string
  toggle: () => void
  setLang: (l: Lang) => void
}
const I18nContext = createContext<I18nContextValue | null>(null)

export function I18nProvider({ children }: { children: ReactNode }) {
  const [lang, setLang] = useState<Lang>(() => (localStorage.getItem('maw3idi.lang') as Lang) || 'ar')
  const dir = lang === 'ar' ? 'rtl' : 'ltr'
  useEffect(() => {
    document.documentElement.lang = lang
    document.documentElement.dir = dir
    localStorage.setItem('maw3idi.lang', lang)
  }, [lang, dir])
  const value = useMemo<I18nContextValue>(() => ({
    lang,
    dir,
    t: (key: DictKey) => dict[lang][key] ?? dict.ar[key],
    toggle: () => setLang((l) => (l === 'ar' ? 'en' : 'ar')),
    setLang,
  }), [lang, dir])
  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>
}
export function useI18n() {
  const ctx = useContext(I18nContext)
  if (!ctx) throw new Error('useI18n must be used within I18nProvider')
  return ctx
}
