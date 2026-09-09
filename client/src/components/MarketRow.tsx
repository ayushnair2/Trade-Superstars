import { arrow, changeClass, sparkStroke } from '../format'
import type { PriceRow } from '../types'
import Sparkline from './Sparkline'
import SportTag from './SportTag'

type Props = {
  row: PriceRow
  selected: boolean
  onSelect: (athleteId: number) => void
}

export default function MarketRow({ row, selected, onSelect }: Props) {
  return (
    <div
      className={selected ? 'row sel' : 'row'}
      onClick={() => onSelect(row.athlete_id)}
    >
      <div className="row-left">
        <SportTag sport={row.sport} />
        <span className="row-name">{row.name}</span>
      </div>
      <div className="row-right">
        <Sparkline values={row.spark} stroke={sparkStroke(row.change_pct)} />
        <span className="row-price">
          {row.price === null ? '--' : `$${row.price.toFixed(2)}`}
        </span>
        <span className={`row-change ${changeClass(row.change_pct)}`}>
          {row.change_pct === null
            ? '--'
            : `${arrow(row.change_pct)}${Math.abs(row.change_pct).toFixed(1)}%`}
        </span>
      </div>
    </div>
  )
}
