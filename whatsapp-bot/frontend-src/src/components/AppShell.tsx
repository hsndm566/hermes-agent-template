import { useState } from 'react'
import { Outlet, useLocation } from 'react-router-dom'
import { useI18n } from '../lib/i18n'
import { Sidebar } from './Sidebar'
import { Topbar } from './Topbar'
import { OnboardingWizard } from '../features/onboarding/OnboardingWizard'
import { useBusinesses } from '../lib/BusinessContext'

const titleByPath: Record<string, { ar: string; en: string }> = {
  '/': { ar: 'الرئيسية', en: 'Overview' },
  '/conversations': { ar: 'المحادثات', en: 'Conversations' },
  '/appointments': { ar: 'الحجوزات', en: 'Appointments' },
  '/customers': { ar: 'العملاء', en: 'Customers' },
  '/services': { ar: 'الخدمات', en: 'Services' },
  '/team': { ar: 'الفريق', en: 'Team' },
  '/availability': { ar: 'أوقات العمل', en: 'Availability' },
  '/whatsapp': { ar: 'البوت وواتساب', en: 'Bot & WhatsApp' },
  '/automations': { ar: 'الأتمتة', en: 'Automations' },
  '/settings': { ar: 'الإعدادات', en: 'Settings' },
}

export function AppShell() {
  const { lang } = useI18n()
  const { pathname } = useLocation()
  const [mobileOpen, setMobileOpen] = useState(false)
  const [wizardOpen, setWizardOpen] = useState(false)
  const { refresh, select } = useBusinesses()

  const title = titleByPath[pathname]?.[lang] ?? titleByPath['/'][lang]

  return (
    <div className="flex h-screen overflow-hidden bg-canvas">
      <div className="hidden lg:block">
        <Sidebar onAddBusiness={() => setWizardOpen(true)} />
      </div>

      {mobileOpen && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div className="absolute inset-0 bg-ink-900/40" onClick={() => setMobileOpen(false)} />
          <div className="absolute inset-y-0 start-0 w-72 max-w-[85%]">
            <Sidebar
              onAddBusiness={() => {
                setMobileOpen(false)
                setWizardOpen(true)
              }}
            />
          </div>
        </div>
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        <Topbar title={title} onMenu={() => setMobileOpen(true)} />
        <main className="scrollbar-thin flex-1 overflow-y-auto p-4 sm:p-6 lg:p-8">
          <Outlet />
        </main>
      </div>

      {wizardOpen && (
        <OnboardingWizard
          onClose={() => setWizardOpen(false)}
          onCreated={async (id) => {
            await refresh()
            select(id)
          }}
        />
      )}
    </div>
  )
}
