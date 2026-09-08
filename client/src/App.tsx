import { useEffect, useState } from 'react'

import Header from './components/Header'
import MarketList from './components/MarketList'
import './styles/pixel.css'
import type { MarketPrices } from './types'

const POLL_MS = 2000

export default function App() {
  const [market, setMarket] = useState<MarketPrices | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false

    async function load() {
      try {
        const res = await fetch('/market/prices')
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        const data: MarketPrices = await res.json()
        if (!cancelled) {
          setMarket(data)
          setError(null)
        }
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

  if (error) return <p className="state">ERROR: {error}</p>
  if (!market) return <p className="state">LOADING…</p>

  return (
    <>
      <Header step={market.current_step} />
      <MarketList rows={market.prices} />
    </>
  )
}
