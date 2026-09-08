export type PriceRow = {
  athlete_id: number
  name: string
  sport: string
  price: number | null
}

export type MarketPrices = {
  current_step: number
  prices: PriceRow[]
}
