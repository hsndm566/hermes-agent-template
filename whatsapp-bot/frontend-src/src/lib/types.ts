export type BotTone = 'friendly' | 'professional' | 'luxury' | 'concise'
export type Lang = 'ar' | 'en'

export interface ServiceIn {
  id?: string
  name_ar: string
  name_en: string
  duration_min: number
  price: number
  buffer_min: number
}
export interface HoursIn {
  day_of_week: number
  open_time: string | null
  close_time: string | null
  is_closed: boolean
  is_ramadan: boolean
}
export interface StaffIn {
  id?: string
  name_ar: string
  name_en: string
  is_active: boolean
}
export interface BusinessCreatePayload {
  name_ar: string
  name_en: string
  phone: string
  maps_url: string
  latitude?: number | null
  longitude?: number | null
  vat_number?: string | null
  cr_number?: string | null
  bot_name_ar?: string | null
  bot_name_en?: string | null
  bot_tone: BotTone
  welcome_ar?: string | null
  welcome_en?: string | null
  services: ServiceIn[]
  hours: HoursIn[]
  test_mode?: boolean
}
export interface BusinessProfilePayload {
  name_ar: string
  name_en: string
  phone: string
  maps_url: string
  latitude?: number | null
  longitude?: number | null
  vat_number?: string | null
  cr_number?: string | null
}
export interface BusinessRow {
  id: string
  businessId: string
  name_ar: string
  name_en: string
  phone: string
  whatsapp_session_id: string
  maps_url: string
  latitude: number | null
  longitude: number | null
  vat_number: string | null
  cr_number: string | null
}
export interface BusinessDetail {
  business: BusinessRow
  services: (ServiceIn & { id: string })[]
  hours: (HoursIn & { id: string })[]
  staff: (StaffIn & { id: string })[]
  settings: Record<string, string>
}
export interface AppointmentRow {
  id: string
  businessId: string
  customer_phone: string
  customer_name: string | null
  service_id: string
  staff_id: string
  start_time: string
  end_time: string
  status: 'confirmed' | 'rescheduled' | 'completed' | 'cancelled' | 'no_show' | string
  name_ar: string
  name_en: string
  staff_ar: string
  staff_en: string
}
export interface CustomerRow {
  id: string
  businessId: string
  phone: string
  name: string | null
  no_show_count: number
  last_visit: string | null
  preferred_language: 'ar' | 'en' | null
}
export interface AppointmentSlot { start: string; end: string; staff_id: string }
export type AppointmentAction = 'cancel' | 'reschedule' | 'complete' | 'no_show'
export type EvolutionState = 'open' | 'connected' | 'connecting' | 'close' | 'test' | string
export interface ConnectionResponse { instance?: { state: EvolutionState }; state?: EvolutionState }
export interface QrResponse { qr: string | null; state?: 'test'; raw?: unknown }
export interface TestMessageResponse { ok: boolean; phone: string; language: Lang; state: string; started_at: string }
export interface ConversationTestStatus {
  ok: boolean
  started_at: string | null
  last_inbound_at: string | null
  last_inbound_phone: string | null
  last_inbound_text: string | null
}
export interface ClientDefaults { test_phone: string }
