import type {
  AppointmentAction,
  AppointmentRow,
  AppointmentSlot,
  BusinessCreatePayload,
  BusinessDetail,
  BusinessProfilePayload,
  BusinessRow,
  ClientDefaults,
  ConnectionResponse,
  ConversationTestStatus,
  CustomerRow,
  HoursIn,
  Lang,
  QrResponse,
  ServiceIn,
  StaffIn,
  TestMessageResponse,
} from './types'

class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const res = await fetch(path, {
    method,
    credentials: 'include',
    headers: body !== undefined ? { 'Content-Type': 'application/json' } : undefined,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) {
    let message = res.statusText
    try {
      const data = await res.json()
      message = data?.detail || message
    } catch {}
    throw new ApiError(res.status, message)
  }
  if (res.status === 204) return undefined as T
  return (await res.json()) as T
}

export const api = {
  login: (username: string, password: string) => request<{ ok: boolean }>('POST', '/api/login', { username, password }),
  logout: () => request<{ ok: boolean }>('POST', '/api/logout'),
  session: () => request<{ ok: boolean; username: string }>('GET', '/api/session'),
  clientDefaults: () => request<ClientDefaults>('GET', '/api/client-defaults'),
  listBusinesses: () => request<BusinessRow[]>('GET', '/api/businesses'),
  createBusiness: (body: BusinessCreatePayload) => request<{ id: string; instance: string; qr: string | null }>('POST', '/api/businesses', body),
  getBusiness: (id: string) => request<BusinessDetail>('GET', `/api/businesses/${id}`),
  getQr: (id: string) => request<QrResponse>('GET', `/api/businesses/${id}/qr`),
  getConnection: (id: string) => request<ConnectionResponse>('GET', `/api/businesses/${id}/connection`),
  putServices: (id: string, items: ServiceIn[]) => request<{ ok: boolean }>('PUT', `/api/businesses/${id}/services`, items),
  putHours: (id: string, items: HoursIn[]) => request<{ ok: boolean }>('PUT', `/api/businesses/${id}/hours`, items),
  putSettings: (id: string, values: Record<string, string>) => request<{ ok: boolean }>('PUT', `/api/businesses/${id}/settings`, { values }),
  putStaff: (id: string, items: StaffIn[]) => request<{ ok: boolean }>('PUT', `/api/businesses/${id}/staff`, items),
  putProfile: (id: string, body: BusinessProfilePayload) => request<BusinessRow>('PUT', `/api/businesses/${id}/profile`, body),
  getAppointments: (id: string) => request<AppointmentRow[]>('GET', `/api/businesses/${id}/appointments`),
  updateAppointment: (id: string, appointmentId: string, action: AppointmentAction, slot?: AppointmentSlot) =>
    request<AppointmentRow>('PATCH', `/api/businesses/${id}/appointments/${appointmentId}`, { action, slot }),
  getCustomers: (id: string) => request<CustomerRow[]>('GET', `/api/businesses/${id}/customers`),
  disconnectWhatsApp: (id: string) => request<{ ok: boolean }>('DELETE', `/api/businesses/${id}/connection`),
  sendTestMessage: (id: string, phone: string, language: Lang) =>
    request<TestMessageResponse>('POST', `/api/businesses/${id}/test-message`, { phone, language }),
  getConversationTestStatus: (id: string) => request<ConversationTestStatus>('GET', `/api/businesses/${id}/conversation-test-status`),
}
export { ApiError }
