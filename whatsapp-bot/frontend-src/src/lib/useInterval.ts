import { useEffect, useRef } from 'react'

export function useInterval(callback: () => void, delayMs: number | null, active = true) {
  const savedCallback = useRef(callback)
  useEffect(() => { savedCallback.current = callback }, [callback])

  useEffect(() => {
    if (delayMs === null || !active) return
    const id = setInterval(() => savedCallback.current(), delayMs)
    return () => clearInterval(id)
  }, [delayMs, active])
}
