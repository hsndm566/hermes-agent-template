import { MessageSquare } from 'lucide-react'
import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import { useBusinesses } from '../lib/BusinessContext'
import { useI18n } from '../lib/i18n'
import type { ConversationTestStatus } from '../lib/types'
export default function Conversations(){
  const {lang}=useI18n(); const {selectedId}=useBusinesses(); const [status,setStatus]=useState<ConversationTestStatus|null>(null)
  useEffect(()=>{if(selectedId) api.getConversationTestStatus(selectedId).then(setStatus)},[selectedId])
  if(!selectedId) return <p className="text-sm text-ink-400">{lang==='ar'?'اختر منشأة أولاً':'Select a business first'}</p>
  return <div className="space-y-4"><div className="rounded-xl2 border border-dashed border-ink-200 bg-canvas p-4 text-xs text-ink-400">{lang==='ar'?'الخادم الحالي يحفظ فقط آخر رسالة واردة (لا يوجد جدول محادثات كامل). صندوق وارد حقيقي بسجل كامل يحتاج جدول messages جديد مرتبط بالمنشأة — مقترح في المرحلة القادمة.':'The backend today only stores the single latest inbound message (no full history table). A real inbox with history needs a new tenant-scoped messages table — planned for the next phase.'}</div>{status?.last_inbound_phone?<div className="max-w-md rounded-xl2 border border-ink-100 bg-surface p-5 shadow-card"><div className="mb-3 flex items-center gap-2"><div className="flex h-9 w-9 items-center justify-center rounded-full bg-moss-100 text-moss-700"><MessageSquare className="h-4 w-4"/></div><div><p dir="ltr" className="text-sm font-semibold text-ink-900">{status.last_inbound_phone}</p>{status.last_inbound_at&&<p className="text-xs text-ink-400">{new Date(status.last_inbound_at).toLocaleString(lang==='ar'?'ar-SA':'en-US')}</p>}</div></div><p className="rounded-lg bg-canvas p-3 text-sm text-ink-700">{status.last_inbound_text}</p></div>:<p className="text-sm text-ink-400">{lang==='ar'?'لا توجد محادثات بعد':'No conversations yet'}</p>}</div>
}
