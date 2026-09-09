import type { PriceRow } from '../types'
import MarketRow from './MarketRow'

type Props = {
  rows: PriceRow[]
  selectedId: number | null
  onSelect: (athleteId: number) => void
}

export default function MarketList({ rows, selectedId, onSelect }: Props) {
  return (
    <div className="panel">
      <div className="panel-title">MARKET</div>
      <div className="market-scroll">
        {rows.map((row) => (
          <MarketRow
            key={row.athlete_id}
            row={row}
            selected={row.athlete_id === selectedId}
            onSelect={onSelect}
          />
        ))}
      </div>
    </div>
  )
}
