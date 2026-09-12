import type { ReactNode } from 'react'

import { arrow, changeClass, sparkStroke } from '../format'
import Sparkline from './Sparkline'

type Props = {
  /** SportTag for an athlete, FundTag for a fund */
  tag: ReactNode
  name: string
  price: number | null
  changePct: number | null
  spark: number[]
  selected: boolean
  onSelect: () => void
}

export default function MarketRow({
  tag,
  name,
  price,
  changePct,
  spark,
  selected,
  onSelect,
}: Props) {
  return (
    <div className={selected ? 'row sel' : 'row'} onClick={onSelect}>
      <div className="row-left">
        {tag}
        <span className="row-name">{name}</span>
      </div>
      <div className="row-right">
        <Sparkline values={spark} stroke={sparkStroke(changePct)} />
        <span className="row-price">
          {price === null ? '--' : `$${price.toFixed(2)}`}
        </span>
        <span className={`row-change ${changeClass(changePct)}`}>
          {changePct === null
            ? '--'
            : `${arrow(changePct)}${Math.abs(changePct).toFixed(1)}%`}
        </span>
      </div>
    </div>
  )
}
