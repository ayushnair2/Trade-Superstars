import { useState } from 'react'

import { authFetch } from '../api'
import { evaluateTrade, muteWarnings, mutedWarnings, type Warning } from '../riskRules'
import type { Portfolio, PriceRow, Selection } from '../types'
import RiskDialog from './RiskDialog'

type Props = {
  /** the asset being traded; funds and athletes share these controls */
  asset: Selection
  /** PriceRow shape for the risk rules -- a fund is adapted into one */
  athlete: PriceRow
  held: number
  signedIn: boolean
  portfolio: Portfolio | null
  rows: PriceRow[]
  onRequireLogin: () => void
  onTraded: (tradeId: number) => void
}

export default function TradeControls({
  asset,
  athlete,
  held,
  signedIn,
  portfolio,
  rows,
  onRequireLogin,
  onTraded,
}: Props) {
  // the backend takes exactly one of athlete_id or fund_id
  const assetParam =
    asset.kind === 'fund' ? `fund_id=${asset.id}` : `athlete_id=${asset.id}`
  const [quantity, setQuantity] = useState('1')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  // a trade held back by warnings until the user decides
  const [pending, setPending] = useState<
    { side: 'buy' | 'sell'; warnings: Warning[] } | null
  >(null)

  const qty = Number(quantity)
  const valid = Number.isInteger(qty) && qty > 0

  function trade(side: 'buy' | 'sell') {
    if (!signedIn) {
      // never fire a request we know will 401; ask them to sign in instead
      onRequireLogin()
      return
    }
    if (!valid) {
      setError('quantity must be a positive whole number')
      return
    }
    // rules are templated and local, so this costs nothing and blocks nothing
    const muted = mutedWarnings()
    const warnings = evaluateTrade(side, athlete, qty, portfolio, rows).filter(
      (warning) => !muted.has(warning.id),
    )
    if (warnings.length) {
      setPending({ side, warnings })
      return
    }
    execute(side)
  }

  async function execute(side: 'buy' | 'sell') {
    setBusy(true)
    try {
      const res = await authFetch(
        `/portfolio/${side}?${assetParam}&quantity=${qty}`,
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

      {pending && (
        <RiskDialog
          warnings={pending.warnings}
          onCancel={() => setPending(null)}
          onProceed={(muteTypes) => {
            if (muteTypes) muteWarnings(pending.warnings.map((w) => w.id))
            const { side } = pending
            setPending(null)
            execute(side)
          }}
        />
      )}
    </>
  )
}
