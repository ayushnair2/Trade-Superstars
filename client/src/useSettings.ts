import { useCallback, useEffect, useState } from 'react'

export const COOLDOWN_PRESETS = [
  { label: 'Every trade', ms: 0 },
  { label: '10s', ms: 10000 },
  { label: '30s', ms: 30000 },
  { label: '60s', ms: 60000 },
]

const ENABLED_KEY = 'ts.lessonsEnabled'
const COOLDOWN_KEY = 'ts.lessonCooldownMs'

const DEFAULT_ENABLED = true
const DEFAULT_COOLDOWN_MS = 30000

// localStorage throws in some contexts (private mode, blocked site data), so
// every read and write is guarded and falls back to the default.
function read<T>(key: string, fallback: T, parse: (raw: string) => T): T {
  try {
    const raw = localStorage.getItem(key)
    return raw === null ? fallback : parse(raw)
  } catch {
    return fallback
  }
}

function write(key: string, value: string) {
  try {
    localStorage.setItem(key, value)
  } catch {
    // not persisting is survivable; the session still works
  }
}

export type Settings = {
  lessonsEnabled: boolean
  lessonCooldownMs: number
  setLessonsEnabled: (value: boolean) => void
  setLessonCooldownMs: (value: number) => void
}

export function useSettings(): Settings {
  const [lessonsEnabled, setEnabled] = useState(() =>
    read(ENABLED_KEY, DEFAULT_ENABLED, (raw) => raw === 'true'),
  )
  const [lessonCooldownMs, setCooldown] = useState(() =>
    read(COOLDOWN_KEY, DEFAULT_COOLDOWN_MS, (raw) => {
      const n = Number(raw)
      return Number.isFinite(n) && n >= 0 ? n : DEFAULT_COOLDOWN_MS
    }),
  )

  useEffect(() => write(ENABLED_KEY, String(lessonsEnabled)), [lessonsEnabled])
  useEffect(() => write(COOLDOWN_KEY, String(lessonCooldownMs)), [lessonCooldownMs])

  return {
    lessonsEnabled,
    lessonCooldownMs,
    setLessonsEnabled: useCallback((v: boolean) => setEnabled(v), []),
    setLessonCooldownMs: useCallback((v: number) => setCooldown(v), []),
  }
}
