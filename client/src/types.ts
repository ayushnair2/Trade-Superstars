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
  bonds?: { active_principal: number }
  total_value: number
}

export type HistoryPoint = {
  recorded_at: string
  price: number
}

export type LeaderboardEntry = {
  rank: number
  display_name: string
  total_value: number
  return_pct: number
}

export type LeaderboardBody = {
  top: LeaderboardEntry[]
  total_players: number
  /** present only when the caller is signed in and ranked outside `top` */
  me?: LeaderboardEntry
}

export type BondTerm = {
  term_days: number
  coupon_rate: number
  face: number
  total_return_pct: number
  early_penalty_pct: number
}

export type BondPosition = {
  position_id: number
  term_days: number
  quantity: number
  principal: number
  coupon_rate: number
  bought_day: number
  maturity_day: number
  status: 'active' | 'matured' | 'redeemed'
  coupons_received: number
  days_to_maturity: number
}

export type BondPositions = {
  current_day: number
  active_principal: number
  positions: BondPosition[]
}
