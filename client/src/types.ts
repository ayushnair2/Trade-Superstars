export type PriceRow = {
  athlete_id: number
  name: string
  sport: string
  price: number | null
  change_pct: number | null
  spark: number[]
}

export type FundRow = {
  fund_id: number
  code: string
  name: string
  description: string
  member_count: number
  price: number | null
  change_pct: number | null
  spark: number[]
}

export type FundMemberRow = {
  athlete_id: number
  name: string
  sport: string
  position: string | null
  weight: number
  price: number | null
}

export type FundDetail = FundRow & { members: FundMemberRow[] }

/** What the market list has selected. Athletes and funds share the panel, so
 *  the id alone is ambiguous -- both number from 1. */
export type Selection =
  | { kind: 'athlete'; id: number }
  | { kind: 'fund'; id: number; code: string }

export type MarketPrices = {
  current_step: number
  prices: PriceRow[]
  funds: FundRow[]
}

export type HoldingRow = {
  asset_type?: 'athlete' | 'fund'
  athlete_id: number | null
  fund_id?: number | null
  name: string
  quantity: number
  avg_cost: number
  current_price: number
  market_value: number
  unrealized_pl: number
}

export type Portfolio = {
  cash: number
  holdings: HoldingRow[]
  total_value: number
}

export type HistoryPoint = {
  recorded_at: string
  price: number
}
