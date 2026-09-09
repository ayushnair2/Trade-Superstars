import { useCallback, useEffect, useRef, useState } from 'react'

import { api } from './api'

const VISIBLE_MS = 14000

export type LessonState = {
  visible: boolean
  loading: boolean
  text: string | null
}

const HIDDEN: LessonState = { visible: false, loading: false, text: null }

type Options = {
  enabled: boolean
  cooldownMs: number
}

export function useLesson({ enabled, cooldownMs }: Options) {
  const [state, setState] = useState<LessonState>(HIDDEN)
  const lastShownAt = useRef(0)
  const hideTimer = useRef<number | undefined>(undefined)

  const clearHideTimer = () => {
    if (hideTimer.current !== undefined) {
      clearTimeout(hideTimer.current)
      hideTimer.current = undefined
    }
  }

  useEffect(() => clearHideTimer, [])

  const dismiss = useCallback(() => {
    clearHideTimer()
    setState(HIDDEN)
  }, [])

  // Turning tips off mid-flight should take the mascot away too.
  useEffect(() => {
    if (!enabled) {
      clearHideTimer()
      setState(HIDDEN)
    }
  }, [enabled])

  const showForTrade = useCallback(
    (tradeId: number) => {
      if (!enabled) return
      const now = Date.now()
      if (now - lastShownAt.current < cooldownMs) return
      lastShownAt.current = now

      clearHideTimer()
      setState({ visible: true, loading: true, text: null })

      // Deliberately not awaited by the caller: a slow or failing lesson must
      // never affect the trade that triggered it.
      fetch(api('/lessons/for-trade'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ trade_id: tradeId }),
      })
        .then((res) => (res.ok ? res.json() : null))
        .then((data) => {
          if (!data?.text) {
            setState(HIDDEN)
            return
          }
          setState({ visible: true, loading: false, text: data.text })
          hideTimer.current = window.setTimeout(() => setState(HIDDEN), VISIBLE_MS)
        })
        .catch(() => setState(HIDDEN))
    },
    [enabled, cooldownMs],
  )

  return { state, showForTrade, dismiss }
}
