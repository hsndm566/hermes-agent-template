import { useEffect, useState } from 'react'
import { MessageSquare } from 'lucide-react'
import { api, type Conversation, type Message } from '../lib/api'
import { useBusinesses } from '../lib/BusinessContext'
import { useI18n } from '../lib/i18n'
export default function Conversations() {
  const { lang } = useI18n(); const { selectedId } = useBusinesses()
  const [rows,setRows] = useState<Conversation[]>([]); const [phone,setPhone] = useState('')
  const [messages,setMessages] = useState<Message[]>([]); const [error,setError] = useState(''); const [loading,setLoading] = useState(false)
  useEffect(() => {
    let active = true; setRows([]); setPhone(''); setMessages([]); setError('')
    if (!selectedId) return
    async function load() { try { const data = await api.conversations(selectedId!); if(active) {setRows(data);setError('')} } catch(e) { if(active) setError(e instanceof Error ? e.message : 'Unavailable') } }
    void load(); const timer = setInterval(load,5000)
    return () => { active = false; clearInterval(timer) }
  },[selectedId])
  useEffect(() => {
    let active = true; setMessages([])
    if(!selectedId || !phone) return
    setLoading(true)
    async function load() { try { const data = await api.messages(selectedId!,phone); if(active) {setMessages(data);setError('')} } catch(e) {if(active) setError(e instanceof Error ? e.message : 'Unavailable')} finally {if(active) setLoading(false)} }
    void load(); const timer = setInterval(load,5000)
    return () => {active=false; clearInterval(timer)}
  },[selectedId,phone])
  if(!selectedId) return <p>{lang==='ar'?'اختر منشأة أولاً':'Select a business first'}</p>
  return <div className="space-y-4">
    {error && <p role="alert" className="rounded-lg bg-rose-50 p-3 text-rose-700">{error}</p>}
    <div className="grid min-h-[420px] overflow-hidden rounded-xl2 border border-ink-100 bg-surface shadow-card md:grid-cols-[260px_1fr]">
      <aside className="border-e border-ink-100 p-3"><h2 className="mb-3 flex items-center gap-2 font-semibold"><MessageSquare className="h-4 w-4"/>{lang==='ar'?'المحادثات':'Conversations'}</h2>
        {!rows.length && <p className="p-4 text-sm text-ink-400">{lang==='ar'?'ستظهر رسائل العملاء هنا بعد ربط واتساب.':'Customer messages will appear here after WhatsApp is connected.'}</p>}
        {rows.map(row=><button key={row.phone} onClick={()=>setPhone(row.phone)} className={`mb-1 block w-full rounded-lg p-3 text-start ${phone===row.phone?'bg-moss-50':'hover:bg-canvas'}`}><p dir="ltr" className="text-sm font-semibold">{row.phone}</p><p className="mt-1 truncate text-xs text-ink-500">{row.body}</p></button>)}
      </aside>
      <section className="max-h-[65vh] space-y-3 overflow-y-auto p-5" aria-live="polite">
        {!phone && <p className="text-sm text-ink-400">{lang==='ar'?'اختر محادثة لعرض الرسائل':'Select a conversation to view messages'}</p>}
        {loading && <p>{lang==='ar'?'جارٍ التحميل…':'Loading…'}</p>}
        {messages.map(msg=><div key={msg.id} className={`max-w-[90%] rounded-xl p-3 ${msg.direction==='outbound'?'ms-auto bg-moss-50':'bg-canvas'}`}><p className="mb-1 text-xs font-semibold text-ink-400">{msg.direction==='outbound'?(lang==='ar'?'المساعد':'Assistant'):(lang==='ar'?'العميل':'Customer')}</p><p dir="auto" className="whitespace-pre-wrap text-sm">{msg.body}</p><time className="mt-2 block text-xs text-ink-400">{new Date(msg.created_at).toLocaleString(lang==='ar'?'ar-SA':'en-GB',{timeZone:'Asia/Riyadh'})}</time></div>)}
      </section>
    </div>
  </div>
}
