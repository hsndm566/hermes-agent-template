import { LogOut, Menu } from 'lucide-react'
import { useAuth } from '../lib/AuthGate'
import { useI18n } from '../lib/i18n'

export function Topbar({ title, onMenu }: { title: string; onMenu: () => void }) {
  const { lang, toggle, t } = useI18n()
  const { logout } = useAuth()
  return (
    <header className="flex items-center justify-between border-b border-ink-100 bg-surface/80 px-4 py-3.5 backdrop-blur sm:px-6">
      <div className="flex items-center gap-3">
        <button onClick={onMenu} className="rounded-lg p-2 text-ink-500 hover:bg-ink-100 lg:hidden" aria-label="Menu">
          <Menu className="h-5 w-5" />
        </button>
        <h1 className="text-base font-semibold text-ink-900 sm:text-lg">{title}</h1>
      </div>
      <div className="flex items-center gap-2">
        <button
          onClick={toggle}
          className="rounded-full border border-ink-200 px-3 py-1.5 text-xs font-semibold text-ink-700 transition hover:border-moss-400 hover:text-moss-700"
        >
          {lang === 'ar' ? 'EN' : 'ع'}
        </button>
        <button
          onClick={logout}
          className="inline-flex items-center gap-1.5 rounded-full border border-ink-200 px-3 py-1.5 text-xs font-semibold text-ink-500 transition hover:border-rose-300 hover:text-rose-600"
        >
          <LogOut className="h-3.5 w-3.5" /> {t('logout')}
        </button>
      </div>
    </header>
  )
}
