import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '../../lib/api'
import { useInterval } from '../../lib/useInterval'

export type ConnectionPhase = 'creating' | 'qr' | 'connected' | 'test' | 'failed'

interface State {
  phase: ConnectionPhase
  qr: string | null
  error: string | null
  lastCheckedAt: number | null
}

const CONNECTED_STATES = new Set(['open', 'connected'])

export function useWhatsAppConnection(businessId: string | null, initialQr?: string | null) {
  const [state, setState] = useState<State>({
    phase: initialQr ? 'qr' : 'creating',
    qr: initialQr ?? null,
    error: null,
    lastCheckedAt: null,
  })
  const pollingRef = useRef(true)

  const fetchQr = useCallback(async () => {
    if (!businessId) return
    try {
      const res = await api.getQr(businessId)
      if (res.state === 'test') {
        setState((s) => ({ ...s, phase: 'test', qr: null, error: null }))
        return
      }
      setState((s) => ({ ...s, phase: 'qr', qr: res.qr, error: null }))
    } catch (e) {
      setState((s) => ({ ...s, phase: 'failed', error: e instanceof Error ? e.message : 'error' }))
    }
  }, [businessId])

  const checkConnection = useCallback(async () => {
    if (!businessId || !pollingRef.current) return
    try {
      const res = await api.getConnection(businessId)
      const raw = res.instance?.state ?? res.state
      setState((s) => {
        if (raw && CONNECTED_STATES.has(raw)) {
          return { ...s, phase: 'connected', error: null, lastCheckedAt: Date.now() }
        }
        if (raw === 'test') {
          return { ...s, phase: 'test', error: null, lastCheckedAt: Date.now() }
        }
        return { ...s, lastCheckedAt: Date.now() }
      })
    } catch {
      setState((s) => ({ ...s, lastCheckedAt: Date.now() }))
    }
  }, [businessId])

  useEffect(() => {
    if (!initialQr && businessId) fetchQr()
  }, [businessId, initialQr, fetchQr])

  useInterval(checkConnection, 3000, state.phase === 'qr' || state.phase === 'creating')
  useInterval(fetchQr, 45000, state.phase === 'qr')

  const refreshQr = useCallback(() => {
    setState((s) => ({ ...s, phase: 'creating' }))
    fetchQr()
  }, [fetchQr])

  const stopPolling = useCallback(() => {
    pollingRef.current = false
  }, [])

  return { ...state, refreshQr, stopPolling }
}
