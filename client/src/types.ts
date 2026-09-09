export type PriceRow = {
  athlete_id: number
  name: string
  sport: string
  price: number | null
  change_pct: number | null
  spark: number[]
}

export type MarketPrices = {
  current_step: number
  prices: PriceRow[]
}

export type HoldingRow = {
  athlete_id: number
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
