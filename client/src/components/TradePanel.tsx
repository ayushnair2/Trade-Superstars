import { arrow, changeClass, money } from '../format'
import type { HistoryPoint, Portfolio, PriceRow } from '../types'
import PriceChart from './PriceChart'
import SportTag from './SportTag'
import TradeControls from './TradeControls'

type Props = {
  athlete: PriceRow | null
  history: HistoryPoint[]
  held: number
  signedIn: boolean
  portfolio: Portfolio | null
  rows: PriceRow[]
  onRequireLogin: () => void
  onTraded: (tradeId: number) => void
}

export default function TradePanel({
  athlete,
  history,
  held,
  signedIn,
  portfolio,
  rows,
  onRequireLogin,
  onTraded,
}: Props) {
  if (!athlete) {
    return (
      <div className="panel trade">
        <div className="panel-title">TRADE</div>
        <div className="state">NO ATHLETE SELECTED</div>
      </div>
    )
  }

  const pct = athlete.change_pct
  const price = athlete.price ?? 0
  // The payload carries % but not the dollar move, and its baseline sits one row
  // behind `spark`. Deriving it from the % keeps the two figures consistent.
  const delta = pct === null ? 0 : price - price / (1 + pct / 100)

  return (
    <div className="panel trade">
      <div className="trade-id">
        <SportTag sport={athlete.sport} />
        <span className="trade-name">{athlete.name}</span>
      </div>

      <div>
        <div className="trade-price">{money(price)}</div>
        <div className={`trade-change ${changeClass(pct)}`}>
          {pct === null
            ? '--'
            : `${arrow(pct)} ${delta >= 0 ? '+' : '-'}${money(Math.abs(delta))}  (${
                pct >= 0 ? '+' : '-'
              }${Math.abs(pct).toFixed(1)}%)`}
        </div>
      </div>

      <PriceChart points={history} />

      <TradeControls
        athlete={athlete}
        held={held}
        signedIn={signedIn}
        portfolio={portfolio}
        rows={rows}
        onRequireLogin={onRequireLogin}
        onTraded={onTraded}
      />
    </div>
  )
}
