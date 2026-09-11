import { useCallback, useEffect, useState } from 'react'

import { authFetch } from './api'

export const DAY_LENGTH_PRESETS = [5, 10, 30]
export const TICKS_PER_DAY_PRESETS = [1, 5, 10, 30]

export type MarketSettings = {
  day_length_minutes: number
  ticks_per_day: number
  randomness: string
}

/** Market clock settings, which live on the backend rather than localStorage. */
export function useMarketSettings() {
  const [settings, setSettings] = useState<MarketSettings | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    let cancelled = false
    authFetch('/settings')
      .then((res) => (res.ok ? res.json() : Promise.reject(new Error(`HTTP ${res.status}`))))
      .then((data) => {
        if (!cancelled) setSettings(data)
      })
      .catch(() => {
        if (!cancelled) setError('could not load market clock')
      })
    return () => {
      cancelled = true
    }
  }, [])

  const update = useCallback(
    async (patch: Partial<MarketSettings>) => {
      if (!settings) return
      const next = { ...settings, ...patch }
      setSaving(true)
      try {
        const res = await authFetch('/settings', {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(next),
        })
        if (!res.ok) {
          const body = await res.json().catch(() => null)
          setError(typeof body?.detail === 'string' ? body.detail : `HTTP ${res.status}`)
          return
        }
        // reflect what the backend actually stored, not what we sent
        setSettings(await res.json())
        setError(null)
      } catch {
        setError('could not save')
      } finally {
        setSaving(false)
      }
    },
    [settings],
  )

  return { settings, error, saving, update }
}
