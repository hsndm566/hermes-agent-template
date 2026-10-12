import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '../../lib/api'
import { useInterval } from '../../lib/useInterval'
export type ConnectionPhase = 'creating' | 'qr' | 'connected' | 'test' | 'failed'
interface State { phase: ConnectionPhase; qr: string | null; error: string | null; lastCheckedAt: number | null }
const CONNECTED = new Set(['open', 'connected'])
export function useWhatsAppConnection(businessId: string | null, initialQr?: string | null) {
  const [state, setState] = useState<State>({ phase: 'creating', qr: null, error: null, lastCheckedAt: null })
  const current = useRef(businessId)
  const active = useRef(true)
  const generation = useRef(0)
  const busy = useRef(false)
  const lastQr = useRef(0)
  const check = useCallback(async (forceQr = false) => {
    if (!businessId || !active.current || busy.current) return
    const version = generation.current
    const valid = () => active.current && current.current === businessId && generation.current === version
    busy.current = true
    try {
      const res = await api.getConnection(businessId)
      if (!valid()) return
      const raw = (res.instance?.state ?? res.state ?? '').toLowerCase()
      if (CONNECTED.has(raw) || raw === 'test') {
        setState({ phase: raw === 'test' ? 'test' : 'connected', qr: null, error: null, lastCheckedAt: Date.now() })
        lastQr.current = 0
        return
      }
      setState(s => ({ ...s, phase: 'qr', error: null, lastCheckedAt: Date.now() }))
      if (forceQr || Date.now() - lastQr.current > 35000) {
        const qr = await api.getQr(businessId)
        if (!valid()) return
        lastQr.current = Date.now()
        setState(s => ({ ...s, qr: qr.qr, phase: 'qr', error: null }))
      }
    } catch (e) {
      if (valid()) setState({ phase: 'failed', qr: null, error: e instanceof Error ? e.message : 'Connection unavailable', lastCheckedAt: Date.now() })
    } finally { if (valid()) busy.current = false }
  }, [businessId])
  useEffect(() => {
    generation.current += 1; current.current = businessId; active.current = true; busy.current = false; lastQr.current = 0
    setState({ phase: initialQr ? 'qr' : 'creating', qr: initialQr ?? null, error: null, lastCheckedAt: null })
    void check()
    return () => { active.current = false; generation.current += 1 }
  }, [businessId, initialQr, check])
  useInterval(() => check(), 3000, !!businessId)
  const refreshQr = useCallback(() => { lastQr.current = 0; void check(true) }, [check])
  const stopPolling = useCallback(() => { active.current = false }, [])
  return { ...state, refreshQr, stopPolling }
}
