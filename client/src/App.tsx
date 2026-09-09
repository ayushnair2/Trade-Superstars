import { useCallback, useEffect, useState } from 'react'

import Header from './components/Header'
import LessonBox from './components/LessonBox'
import MarketList from './components/MarketList'
import TradePanel from './components/TradePanel'
import './styles/pixel.css'
import type { HistoryPoint, MarketPrices, Portfolio } from './types'

const POLL_MS = 2000
const HISTORY_LIMIT = 60

export default function App() {
  const [market, setMarket] = useState<MarketPrices | null>(null)
  const [portfolio, setPortfolio] = useState<Portfolio | null>(null)
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [history, setHistory] = useState<HistoryPoint[]>([])
  const [error, setError] = useState<string | null>(null)

  const loadPortfolio = useCallback(async () => {
    const res = await fetch('/portfolio')
    if (res.ok) setPortfolio(await res.json())
  }, [])

  useEffect(() => {
    let cancelled = false

    async function load() {
      try {
        const [pricesRes, portfolioRes] = await Promise.all([
          fetch('/market/prices'),
          fetch('/portfolio'),
        ])
        if (!pricesRes.ok) throw new Error(`HTTP ${pricesRes.status}`)
        const prices: MarketPrices = await pricesRes.json()
        if (cancelled) return

        setMarket(prices)
        setError(null)
        // Default the selection to whoever tops the market on first load.
        setSelectedId((current) => current ?? prices.prices[0]?.athlete_id ?? null)
        if (portfolioRes.ok) setPortfolio(await portfolioRes.json())
      } catch (err) {
        if (!cancelled) setError(String(err))
      }
    }

    load()
    const id = setInterval(load, POLL_MS)
    return () => {
      cancelled = true
      clearInterval(id)
    }
  }, [])

  useEffect(() => {
    if (selectedId === null) return
    let cancelled = false

    fetch(`/athletes/${selectedId}/history?limit=${HISTORY_LIMIT}`)
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (!cancelled && data) setHistory(data.history)
      })
      .catch(() => undefined)

    return () => {
      cancelled = true
    }
  }, [selectedId])

  if (error) return <p className="state">ERROR: {error}</p>
  if (!market) return <p className="state">LOADING…</p>

  const selected = market.prices.find((row) => row.athlete_id === selectedId) ?? null
  const held =
    portfolio?.holdings.find((h) => h.athlete_id === selectedId)?.quantity ?? 0

  return (
    <>
      <Header portfolio={portfolio} />
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
          onTraded={loadPortfolio}
        />
      </div>
      <LessonBox />
    </>
  )
}
