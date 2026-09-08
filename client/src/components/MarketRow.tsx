import type { PriceRow } from '../types'
import SportTag from './SportTag'

type Props = {
  row: PriceRow
}

export default function MarketRow({ row }: Props) {
  return (
    <div className="row">
      <div className="row-left">
        <SportTag sport={row.sport} />
        <span className="row-name">{row.name}</span>
      </div>
      {row.price === null ? (
        <span className="row-price row-price-empty">--</span>
      ) : (
        <span className="row-price">${row.price.toFixed(2)}</span>
      )}
    </div>
  )
}
