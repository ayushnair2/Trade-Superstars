import { useCallback, useEffect, useState } from 'react'

import { authFetch } from './api'
import AuthScreen from './components/AuthScreen'
import Header, { type Tab } from './components/Header'
import Landing from './components/Landing'
import LessonBox from './components/LessonBox'
import Mascot from './components/Mascot'
import SettingsPanel from './components/SettingsPanel'
import MarketList from './components/MarketList'
import PortfolioView from './components/PortfolioView'
import TradePanel from './components/TradePanel'
import './styles/pixel.css'
import type {
  FundDetail,
  HistoryPoint,
  MarketPrices,
  Portfolio,
  Selection,
} from './types'
import { useAuth } from './useAuth'
import { useLesson } from './useLesson'
import { useSettings } from './useSettings'

const POLL_MS = 2000

/** Stable identity for a selection, so cached data is never shown for the
 *  wrong asset -- athlete 3 and fund 3 are different things. */
const selectionKey = (selection: Selection) => `${selection.kind}:${selection.id}`
const HISTORY_LIMIT = 60

type View = 'landing' | 'game'

export default function App() {
  const [view, setView] = useState<View>('landing')
  const [tab, setTab] = useState<Tab>('market')
  const [market, setMarket] = useState<MarketPrices | null>(null)
  const [portfolio, setPortfolio] = useState<Portfolio | null>(null)
  const [selection, setSelection] = useState<Selection | null>(null)
  // cached per code, so flicking between funds does not refetch or flash
  const [fundCache, setFundCache] = useState<Record<string, FundDetail>>({})
  // keyed by asset: reading points only when the key matches means a stale
  // chart never flashes under a newly selected name
  const [history, setHistory] = useState<{ key: string; points: HistoryPoint[] }>({
    key: '',
    points: [],
  })
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
        setSelection((current) => {
          if (current) return current
          const top = data.prices[0]
          return top ? { kind: 'athlete', id: top.athlete_id } : null
        })
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
    if (view !== 'game' || selection === null) return
    let cancelled = false

    // funds are addressed by code, athletes by id, but both answer the same shape
    const key = selectionKey(selection)
    const path =
      selection.kind === 'fund'
        ? `/funds/${selection.code}/history?limit=${HISTORY_LIMIT}`
        : `/athletes/${selection.id}/history?limit=${HISTORY_LIMIT}`

    authFetch(path)
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (!cancelled && data) setHistory({ key, points: data.history })
      })
      .catch(() => undefined)

    return () => {
      cancelled = true
    }
  }, [view, selection])

  // the member list, so a buyer sees what the basket actually holds
  useEffect(() => {
    if (view !== 'game' || selection?.kind !== 'fund') return
    const code = selection.code
    let cancelled = false
    authFetch(`/funds/${code}`)
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (!cancelled && data) setFundCache((prev) => ({ ...prev, [code]: data }))
      })
      .catch(() => undefined)

    return () => {
      cancelled = true
    }
  }, [view, selection])

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

  const selected =
    selection?.kind === 'athlete'
      ? (market.prices.find((row) => row.athlete_id === selection.id) ?? null)
      : null
  const held =
    portfolio?.holdings.find((h) =>
      selection?.kind === 'fund'
        ? h.fund_id === selection.id
        : h.athlete_id === selection?.id,
    )?.quantity ?? 0

  return (
    <>
      <Header
        tab={tab}
        onTab={setTab}
        portfolio={portfolio}
        stale={stale}
        user={auth.user}
        onLogin={() => setAuthOpen(true)}
        onLogout={auth.logout}
        onOpenSettings={() => setSettingsOpen(true)}
      />
      {tab === 'market' ? (
        <div className="layout">
          <MarketList
            rows={market.prices}
            funds={market.funds ?? []}
            selection={selection}
            onSelect={setSelection}
          />
          <TradePanel
            selection={selection}
            athlete={selected}
            fund={
              selection?.kind === 'fund' ? (fundCache[selection.code] ?? null) : null
            }
            history={
              selection && history.key === selectionKey(selection)
                ? history.points
                : []
            }
            held={held}
            signedIn={signedIn}
            portfolio={portfolio}
            rows={market.prices}
            onRequireLogin={() => setAuthOpen(true)}
            onTraded={handleTraded}
          />
        </div>
      ) : (
        <PortfolioView
          portfolio={portfolio}
          rows={market.prices}
          signedIn={signedIn}
          onRequireLogin={() => setAuthOpen(true)}
          onGoToMarket={() => setTab('market')}
        />
      )}
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
