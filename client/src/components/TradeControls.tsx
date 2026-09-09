import { useState } from 'react'

import { api } from '../api'

type Props = {
  athleteId: number
  held: number
  onTraded: (tradeId: number) => void
}

export default function TradeControls({ athleteId, held, onTraded }: Props) {
  const [quantity, setQuantity] = useState('1')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const qty = Number(quantity)
  const valid = Number.isInteger(qty) && qty > 0

  async function trade(side: 'buy' | 'sell') {
    if (!valid) {
      setError('quantity must be a positive whole number')
      return
    }
    setBusy(true)
    try {
      const res = await fetch(
        api(`/portfolio/${side}?athlete_id=${athleteId}&quantity=${qty}`),
        { method: 'POST' },
      )
      if (!res.ok) {
        // FastAPI puts the reason in `detail`.
        const body = await res.json().catch(() => null)
        setError(body?.detail ?? `HTTP ${res.status}`)
        return
      }
      setError(null)
      const body = await res.json().catch(() => null)
      onTraded(body?.trade_id)
    } catch (err) {
      setError(String(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <div className="kv">
        <span>HELD</span>
        <span className="kv-value">{held}</span>
      </div>

      <div className="kv">
        <span>QTY</span>
        <input
          className="qty-input"
          type="number"
          min="1"
          step="1"
          value={quantity}
          onChange={(e) => setQuantity(e.target.value)}
        />
      </div>

      <div className="btn-row">
        <button
          className="btn buy"
          disabled={busy}
          onClick={() => trade('buy')}
        >
          BUY
        </button>
        <button
          className="btn sell"
          disabled={busy}
          onClick={() => trade('sell')}
        >
          SELL
        </button>
      </div>

      {error && <div className="trade-error">{error}</div>}
    </>
  )
}
