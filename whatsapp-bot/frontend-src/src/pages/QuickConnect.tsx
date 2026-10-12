import { useState } from 'react'
import { Smartphone, ArrowLeft } from 'lucide-react'
import { api } from '../lib/api'
import { useBusinesses } from '../lib/BusinessContext'
import { useI18n } from '../lib/i18n'
import { ConnectionCard } from '../features/whatsapp/ConnectionCard'
import { useWhatsAppConnection } from '../features/whatsapp/useWhatsAppConnection'
import { LiveTestCard } from '../features/whatsapp/LiveTestCard'
export default function QuickConnect() {
  const { selectedId, refresh, select, loading } = useBusinesses(); const { lang }=useI18n()
  const [busy,setBusy]=useState(false);const [error,setError]=useState('')
  const conn=useWhatsAppConnection(selectedId)
  async function connect() {
    setBusy(true);setError('')
    try {
      const res=await api.createBusiness({name_ar:'مساعد واتساب',name_en:'WhatsApp Assistant',phone:'',maps_url:'',bot_name_ar:'مساعدك',bot_name_en:'Your assistant',bot_tone:'friendly',services:[{name_ar:'موعد تجريبي',name_en:'Test appointment',duration_min:30,price:0,buffer_min:0}],hours:Array.from({length:7},(_,day_of_week)=>({day_of_week,open_time:'09:00',close_time:'22:00',is_closed:false,is_ramadan:false}))})
      await refresh();select(res.id)
    } catch(e) {setError(e instanceof Error?e.message:'Connection unavailable')}
    finally {setBusy(false)}
  }
  return <div className="mx-auto max-w-2xl space-y-6">
    <div className="text-center"><div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-moss-100 text-moss-700"><Smartphone className="h-8 w-8"/></div><h2 className="text-3xl font-semibold">{lang==='ar'?'اربط واتساب. جرّب البوت.':'Connect WhatsApp. Try your bot.'}</h2><p className="mt-3 text-ink-500">{lang==='ar'?'بدون تسجيل. امسح الرمز، ثم أرسل رسالة من رقم آخر.':'No signup. Scan the code, then message from another number.'}</p></div>
    <div className="flex justify-center gap-3 text-sm text-ink-500"><span>1. {lang==='ar'?'اربط':'Connect'}</span><ArrowLeft className="h-4 w-4"/><span>2. {lang==='ar'?'امسح الرمز':'Scan QR'}</span><ArrowLeft className="h-4 w-4"/><span>3. {lang==='ar'?'جرّب الرد':'Get a reply'}</span></div>
    {(error||conn.error) && <p role="alert" className="rounded-xl bg-rose-50 p-4 text-rose-700">{error||conn.error}</p>}
    {!selectedId ? <button disabled={busy||loading} onClick={connect} className="w-full rounded-xl bg-moss-600 p-5 text-lg font-semibold text-white disabled:opacity-50">{busy?(lang==='ar'?'جارٍ تجهيز الرمز…':'Preparing QR…'):(lang==='ar'?'اربط واتساب الآن':'Connect WhatsApp now')}</button> : <>
      <ConnectionCard phase={conn.phase} qr={conn.qr} onRefresh={conn.refreshQr}/>
      {conn.phase==='connected' && <><div className="rounded-xl bg-moss-50 p-5"><h3 className="font-semibold">{lang==='ar'?'متصل! جرّب الآن':'Connected! Try it now'}</h3><p className="mt-2">{lang==='ar'?'من رقم واتساب آخر، أرسل «مرحبا» إلى الرقم الذي ربطته. سيرد البوت ويتيح لك تجربة حجز موعد.':'From another WhatsApp number, send “Hi” to the number you connected. The bot will reply and offer a test booking.'}</p></div><LiveTestCard businessId={selectedId}/></>}
    </>}
    <p className="text-center text-xs text-ink-400">{lang==='ar'?'هذا المتصفح يحتفظ بربطك. استخدم نفس المتصفح للعودة.':'This browser remembers your workspace. Return using the same browser.'}</p>
  </div>
}
