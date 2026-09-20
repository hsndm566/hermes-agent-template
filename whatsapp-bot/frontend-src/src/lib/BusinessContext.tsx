import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { api } from './api'
import type { BusinessRow } from './types'

interface BusinessContextValue {
  businesses: BusinessRow[]
  selectedId: string | null
  selected: BusinessRow | null
  loading: boolean
  select: (id: string) => void
  refresh: () => Promise<void>
}

const BusinessContext = createContext<BusinessContextValue | null>(null)

export function BusinessProvider({ children }: { children: ReactNode }) {
  const [businesses, setBusinesses] = useState<BusinessRow[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(() => localStorage.getItem('maw3idi.business') || null)
  const [loading, setLoading] = useState(true)

  const refresh = useCallback(async () => {
    setLoading(true)
    try {
      const list = await api.listBusinesses()
      setBusinesses(list)
      setSelectedId((prev) => {
        if (prev && list.some((b) => b.businessId === prev)) return prev
        return list[0]?.businessId ?? null
      })
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { refresh() }, [refresh])

  useEffect(() => {
    if (selectedId) localStorage.setItem('maw3idi.business', selectedId)
  }, [selectedId])

  const select = useCallback((id: string) => setSelectedId(id), [])

  const value = useMemo<BusinessContextValue>(
    () => ({
      businesses,
      selectedId,
      selected: businesses.find((b) => b.businessId === selectedId) ?? null,
      loading,
      select,
      refresh,
    }),
    [businesses, selectedId, loading, select, refresh],
  )

  return <BusinessContext.Provider value={value}>{children}</BusinessContext.Provider>
}

export function useBusinesses() {
  const ctx = useContext(BusinessContext)
  if (!ctx) throw new Error('useBusinesses must be used within BusinessProvider')
  return ctx
}
