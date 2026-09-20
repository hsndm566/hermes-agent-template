import { Bell, Globe, ShieldCheck } from 'lucide-react'
import { useI18n } from '../lib/i18n'
export default function Automations(){
  const {lang}=useI18n()
  const items=[
    {icon:Bell,title:lang==='ar'?'تذكيرات المواعيد':'Appointment reminders',body:lang==='ar'?'يرسل النظام تذكيراً تلقائياً قبل كل موعد عبر واتساب.':'The system automatically sends a WhatsApp reminder before each appointment.'},
    {icon:Globe,title:lang==='ar'?'حفظ لغة العميل':'Customer language memory',body:lang==='ar'?'يسأل البوت عن اللغة في أول رسالة فقط، ثم يتذكرها لكل المحادثات القادمة.':'The bot asks for language only on the first message, then remembers it for every future conversation.'},
    {icon:ShieldCheck,title:lang==='ar'?'منع الرسائل المكررة':'Duplicate-message protection',body:lang==='ar'?'كل حدث واتساب له معرف فريد يُمنع من المعالجة مرتين.':'Every WhatsApp event has a unique ID that is prevented from being processed twice.'},
  ]
  return <div className="space-y-4"><p className="text-sm text-ink-500">{lang==='ar'?'هذه الأتمتة تعمل بالفعل في الخادم. منشئ أتمتة مخصص (قواعد قابلة للتحرير) غير موجود بعد.':'These automations already run in the backend today. A custom automation builder (editable rules) does not exist yet.'}</p><div className="grid gap-4 sm:grid-cols-3">{items.map((it)=><div key={it.title} className="rounded-xl2 border border-ink-100 bg-surface p-5 shadow-card"><it.icon className="mb-3 h-5 w-5 text-moss-600" strokeWidth={1.75}/><h3 className="mb-1.5 text-sm font-semibold text-ink-900">{it.title}</h3><p className="text-xs text-ink-500">{it.body}</p></div>)}</div></div>
}
