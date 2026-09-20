import { CheckCircle2, RefreshCw, Smartphone, TriangleAlert } from 'lucide-react'
import { useI18n } from '../../lib/i18n'
import type { ConnectionPhase } from './useWhatsAppConnection'

interface Props {
  phase: ConnectionPhase
  qr: string | null
  onRefresh: () => void
}

export function ConnectionCard({ phase, qr, onRefresh }: Props) {
  const { t } = useI18n()
  return (
    <div className="rounded-xl2 border border-ink-100 bg-surface p-6 shadow-card sm:p-8">
      <div className="flex flex-col items-center gap-6 text-center">
        {phase === 'connected' && (
          <>
            <div className="flex h-24 w-24 items-center justify-center rounded-full bg-moss-100">
              <CheckCircle2 className="h-12 w-12 text-moss-600" strokeWidth={1.75} />
            </div>
            <p className="text-lg font-semibold text-ink-900">{t('qr_connected')}</p>
          </>
        )}
        {phase === 'test' && (
          <>
            <div className="flex h-24 w-24 items-center justify-center rounded-full bg-amber-100">
              <Smartphone className="h-12 w-12 text-amber-600" strokeWidth={1.75} />
            </div>
            <p className="text-sm text-ink-500">Test-mode business — no real WhatsApp number to connect.</p>
          </>
        )}
        {phase === 'failed' && (
          <>
            <div className="flex h-24 w-24 items-center justify-center rounded-full bg-rose-100">
              <TriangleAlert className="h-12 w-12 text-rose-600" strokeWidth={1.75} />
            </div>
            <p className="text-sm font-medium text-rose-600">{t('qr_failed')}</p>
            <button onClick={onRefresh} className="inline-flex items-center gap-2 rounded-lg bg-ink-900 px-5 py-2.5 text-sm font-medium text-white transition hover:bg-ink-700">
              <RefreshCw className="h-4 w-4" /> {t('retry')}
            </button>
          </>
        )}
        {(phase === 'qr' || phase === 'creating') && (
          <>
            <div className="relative flex h-64 w-64 items-center justify-center rounded-2xl border-2 border-dashed border-moss-400 bg-moss-50 p-4 sm:h-72 sm:w-72">
              {phase === 'creating' || !qr ? (
                <div className="flex flex-col items-center gap-3">
                  <div className="pulse-ring h-14 w-14 animate-spin rounded-full border-4 border-moss-500 border-t-transparent" />
                  <p className="text-xs font-medium text-moss-700">{t('qr_creating')}</p>
                </div>
              ) : (
                <img src={qr.startsWith('data:') ? qr : `data:image/png;base64,${qr}`} alt="WhatsApp QR" className="h-full w-full rounded-lg object-contain" />
              )}
              {qr && (
                <span className="absolute -bottom-3 left-1/2 -translate-x-1/2 rounded-full bg-moss-600 px-3 py-1 text-xs font-medium text-white shadow-pop">
                  {t('qr_waiting')}
                </span>
              )}
            </div>
            <div className="max-w-sm space-y-3">
              <p className="text-sm font-medium text-ink-700">{t('qr_instructions')}</p>
              <button onClick={onRefresh} className="inline-flex items-center gap-2 rounded-lg border border-ink-200 bg-surface px-4 py-2 text-sm font-medium text-ink-700 transition hover:border-moss-400 hover:text-moss-700">
                <RefreshCw className="h-4 w-4" /> {t('qr_refresh')}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
