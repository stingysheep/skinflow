import { useCallback, useEffect, useRef, useState } from 'react'

import { getJson, putJson } from '../api/client'

type PreferenceResponse<T> = { found: boolean; value: T | null }

export function usePersistentState<T>(key: string, initial: T): [T, (value: T | ((current: T) => T)) => void] {
  const [value, setValue] = useState<T>(() => {
    try {
      const stored = window.localStorage.getItem(key)
      return stored === null ? initial : JSON.parse(stored) as T
    } catch {
      return initial
    }
  })
  const valueRef = useRef(value)
  const serverHydrated = useRef(false)
  const changedBeforeHydration = useRef(false)

  useEffect(() => {
    valueRef.current = value
  }, [value])

  useEffect(() => {
    let cancelled = false
    void getJson<PreferenceResponse<T>>(`/api/preferences/${encodeURIComponent(key)}`)
      .then((response) => {
        if (cancelled) return
        serverHydrated.current = true
        if (response.found && response.value !== null && !changedBeforeHydration.current) {
          valueRef.current = response.value
          setValue(response.value)
          try { window.localStorage.setItem(key, JSON.stringify(response.value)) } catch { /* storage is optional */ }
          return
        }
        void putJson(`/api/preferences/${encodeURIComponent(key)}`, { value: valueRef.current }).catch(() => undefined)
      })
      .catch(() => {
        if (!cancelled) {
          serverHydrated.current = true
          // Keep the local value when the API is still starting, then retry once.
          void putJson(`/api/preferences/${encodeURIComponent(key)}`, { value: valueRef.current }).catch(() => undefined)
        }
      })
    return () => { cancelled = true }
  }, [key])

  // Write in the state setter as well as in the effect so a desktop window
  // closed immediately after a filter change still leaves the latest value.
  const setPersistentValue = useCallback((next: T | ((current: T) => T)) => {
    setValue((current) => {
      const resolved = typeof next === 'function'
        ? (next as (current: T) => T)(current)
        : next
      changedBeforeHydration.current = true
      valueRef.current = resolved
      try { window.localStorage.setItem(key, JSON.stringify(resolved)) } catch { /* storage is optional */ }
      if (serverHydrated.current) {
        void putJson(`/api/preferences/${encodeURIComponent(key)}`, { value: resolved }).catch(() => undefined)
      }
      return resolved
    })
  }, [key])

  useEffect(() => {
    try { window.localStorage.setItem(key, JSON.stringify(value)) } catch { /* storage is optional */ }
  }, [key, value])
  return [value, setPersistentValue]
}
