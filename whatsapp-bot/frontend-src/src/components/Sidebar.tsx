import {
  Bot, CalendarDays, ChevronDown, Clock, LayoutDashboard, ListChecks,
  MessageSquare, Plus, Settings, Users, UsersRound, Workflow,
} from 'lucide-react'
import { NavLink } from 'react-router-dom'
import { useBusinesses } from '../lib/BusinessContext'
import { useI18n } from '../lib/i18n'

const items = [
  { to: '/', icon: LayoutDashboard, key: 'nav_overview' as const, end: true },
  { to: '/conversations', icon: MessageSquare, key: 'nav_conversations' as const },
  { to: '/appointments', icon: CalendarDays, key: 'nav_appointments' as const },
  { to: '/customers', icon: Users, key: 'nav_customers' as const },
  { to: '/services', icon: ListChecks, key: 'nav_services' as const },
  { to: '/team', icon: UsersRound, key: 'nav_team' as const },
  { to: '/availability', icon: Clock, key: 'nav_availability' as const },
  { to: '/whatsapp', icon: Bot, key: 'nav_whatsapp' as const },
  { to: '/automations', icon: Workflow, key: 'nav_automations' as const },
  { to: '/settings', icon: Settings, key: 'nav_settings' as const },
]

export function Sidebar({ onAddBusiness }: { onAddBusiness: () => void }) {
  const { t, lang } = useI18n()
  const { businesses, selectedId, select } = useBusinesses()
  return (
    <aside className="flex h-full w-72 shrink-0 flex-col border-e border-ink-100 bg-surface">
      <div className="flex items-center gap-3 px-5 py-5">
        <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-moss-700 text-sm font-bold text-white">{lang === 'ar' ? 'م' : 'M'}</div>
        <div>
          <p className="text-sm font-semibold text-ink-900">{t('appName')}</p>
          <p className="text-xs text-ink-500">{t('tagline')}</p>
        </div>
      </div>
      <div className="px-4 pb-4">
        <label className="mb-1.5 block text-xs font-medium uppercase tracking-wide text-ink-300">{t('switchBusiness')}</label>
        <div className="relative">
          <select value={selectedId ?? ''} onChange={(e) => select(e.target.value)}
            className="w-full appearance-none rounded-lg border border-ink-200 bg-canvas py-2.5 ps-3 pe-9 text-sm font-medium text-ink-900 focus:border-moss-500 focus:outline-none focus:ring-2 focus:ring-moss-100">
            {businesses.length === 0 && <option value="">—</option>}
            {businesses.map((b) => <option key={b.businessId} value={b.businessId}>{lang === 'ar' ? b.name_ar : b.name_en}</option>)}
          </select>
          <ChevronDown className="pointer-events-none absolute end-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-300" />
        </div>
        <button onClick={onAddBusiness}
          className="mt-2 flex w-full items-center justify-center gap-1.5 rounded-lg border border-dashed border-ink-200 py-2 text-xs font-medium text-ink-500 transition hover:border-moss-400 hover:text-moss-700">
          <Plus className="h-3.5 w-3.5" /> {t('addBusiness')}
        </button>
      </div>
      <nav className="scrollbar-thin flex-1 overflow-y-auto px-3 py-2">
        {items.map(({ to, icon: Icon, key, end }) => (
          <NavLink key={to} to={to} end={end} className={({ isActive }) =>
            `mb-1 flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition ${isActive ? 'bg-moss-50 text-moss-700' : 'text-ink-500 hover:bg-ink-100 hover:text-ink-900'}`}>
            <Icon className="h-4 w-4 shrink-0" strokeWidth={1.75} />{t(key)}
          </NavLink>
        ))}
      </nav>
    </aside>
  )
}
