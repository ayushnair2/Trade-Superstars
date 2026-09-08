import { useEffect, useState } from 'react'

type PriceRow = {
  athlete_id: number
  name: string
  sport: string
  price: number | null
}

type MarketPrices = {
  current_step: number
  prices: PriceRow[]
}

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

  if (error) return <p>Error: {error}</p>
  if (!market) return <p>Loading…</p>

  return (
    <div>
      <h1>Trade Superstars</h1>
      <p>Step: {market.current_step}</p>
      <ul>
        {market.prices.map((row) => (
          <li key={row.athlete_id}>
            {row.name} — {row.price === null ? 'no price' : `$${row.price.toFixed(2)}`}
          </li>
        ))}
      </ul>
    </div>
  )
}
