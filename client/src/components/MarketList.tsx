import type { PriceRow } from '../types'
import MarketRow from './MarketRow'

type Props = {
  rows: PriceRow[]
}

export default function MarketList({ rows }: Props) {
  return (
    <div className="panel">
      <div className="panel-title">MARKET</div>
      <div className="market-scroll">
        {rows.map((row) => (
          <MarketRow key={row.athlete_id} row={row} />
        ))}
      </div>
    </div>
  )
}
