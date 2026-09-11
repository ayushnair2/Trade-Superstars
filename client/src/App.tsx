import { useCallback, useEffect, useState } from 'react'

import { authFetch } from './api'
import AuthScreen from './components/AuthScreen'
import Header from './components/Header'
import Landing from './components/Landing'
import LessonBox from './components/LessonBox'
import Mascot from './components/Mascot'
import SettingsPanel from './components/SettingsPanel'
import MarketList from './components/MarketList'
import TradePanel from './components/TradePanel'
import './styles/pixel.css'
import type { HistoryPoint, MarketPrices, Portfolio } from './types'
import { useAuth } from './useAuth'
import { useLesson } from './useLesson'
import { useSettings } from './useSettings'

const POLL_MS = 2000
const HISTORY_LIMIT = 60

type View = 'landing' | 'game'

export default function App() {
  const [view, setView] = useState<View>('landing')
  const [market, setMarket] = useState<MarketPrices | null>(null)
  const [portfolio, setPortfolio] = useState<Portfolio | null>(null)
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [history, setHistory] = useState<HistoryPoint[]>([])
  // true once a poll cycle fails; cleared as soon as one succeeds
  const [stale, setStale] = useState(false)
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [authOpen, setAuthOpen] = useState(false)
  const auth = useAuth()
  const settings = useSettings()
  const { state: lessonState, showForTrade, dismiss: dismissLesson } = useLesson({
    enabled: settings.lessonsEnabled,
    cooldownMs: settings.lessonCooldownMs,
  })

  const loadPortfolio = useCallback(async () => {
    const res = await authFetch('/portfolio')
    if (res.ok) setPortfolio(await res.json())
    else if (res.status === 401) setPortfolio(null)
  }, [])

  const handleTraded = useCallback(
    (tradeId: number) => {
      loadPortfolio()
      // fire-and-forget: the lesson never gates the trade
      if (tradeId) showForTrade(tradeId)
    },
    [loadPortfolio, showForTrade],
  )

  const signedIn = auth.user !== null

  useEffect(() => {
    if (view !== 'game') return
    let cancelled = false

    async function fetchJson(path: string) {
      const res = await authFetch(path)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      return res.json()
    }

    async function load() {
      // settled, not all: one endpoint failing must not discard the other
      const [prices, portfolioResult] = await Promise.allSettled([
        fetchJson('/market/prices'),
        // /portfolio is 401 when signed out, which is not a connection problem
        signedIn ? fetchJson('/portfolio') : Promise.resolve(null),
      ])
      if (cancelled) return

      if (prices.status === 'fulfilled') {
        const data: MarketPrices = prices.value
        setMarket(data)
        // Default the selection to whoever tops the market on first load.
        setSelectedId((current) => current ?? data.prices[0]?.athlete_id ?? null)
      }
      if (!signedIn) setPortfolio(null)
      else if (portfolioResult.status === 'fulfilled') {
        setPortfolio(portfolioResult.value)
      }

      // keep the last good data on failure; just flag that we are behind
      setStale(prices.status === 'rejected' || portfolioResult.status === 'rejected')
    }

    load()
    const id = setInterval(load, POLL_MS)
    return () => {
      cancelled = true
      clearInterval(id)
    }
    // re-runs on sign in/out so the header reflects the right account
  }, [view, signedIn])

  useEffect(() => {
    if (view !== 'game' || selectedId === null) return
    let cancelled = false

    authFetch(`/athletes/${selectedId}/history?limit=${HISTORY_LIMIT}`)
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (!cancelled && data) setHistory(data.history)
      })
      .catch(() => undefined)

    return () => {
      cancelled = true
    }
  }, [view, selectedId])

  if (view === 'landing') return <Landing onPlay={() => setView('game')} />

  // only a first load with nothing to show gets a full-screen state; the
  // deployed backend can be cold-starting, so this is patience, not failure
  if (!market) {
    return (
      <div className="booting">
        <div className="booting-box">CONNECTING TO MARKET…</div>
        <div className="booting-note">the market may be waking up</div>
      </div>
    )
  }

  const selected = market.prices.find((row) => row.athlete_id === selectedId) ?? null
  const held =
    portfolio?.holdings.find((h) => h.athlete_id === selectedId)?.quantity ?? 0

  return (
    <>
      <Header
        portfolio={portfolio}
        stale={stale}
        user={auth.user}
        onLogin={() => setAuthOpen(true)}
        onLogout={auth.logout}
        onOpenSettings={() => setSettingsOpen(true)}
      />
      <div className="layout">
        <MarketList
          rows={market.prices}
          selectedId={selectedId}
          onSelect={setSelectedId}
        />
        <TradePanel
          athlete={selected}
          history={history}
          held={held}
          signedIn={signedIn}
          portfolio={portfolio}
          rows={market.prices}
          onRequireLogin={() => setAuthOpen(true)}
          onTraded={handleTraded}
        />
      </div>
      <LessonBox />
      <Mascot state={lessonState} onDismiss={dismissLesson} />
      {settingsOpen && (
        <SettingsPanel settings={settings} onClose={() => setSettingsOpen(false)} />
      )}
      {authOpen && (
        <AuthScreen
          auth={auth}
          onClose={() => setAuthOpen(false)}
          onSuccess={() => setAuthOpen(false)}
        />
      )}
    </>
  )
}
