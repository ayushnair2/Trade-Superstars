import type { HoldingRow, Portfolio, PriceRow } from './types'

/** Every threshold in one place, so tuning risk advice is a single edit. */
export const RISK_THRESHOLDS = {
  /** one athlete above this share of total portfolio value */
  playerConcentrationPct: 40,
  /** one sport above this share of total portfolio value */
  sportConcentrationPct: 60,
  /** a single buy costing more than this share of current cash */
  cashSpendPct: 75,
  /** buying after the price has run up at least this much */
  chasingChangePct: 15,
}

export type RiskId =
  | 'PLAYER_CONCENTRATION'
  | 'SPORT_CONCENTRATION'
  | 'HIGH_CASH_SPEND'
  | 'CHASING_BUY'
  | 'PANIC_SELL'

/**
 * Three parts so the dialog can style them differently: the concept being
 * taught, why it matters in general, and what it means for this trade.
 */
export type Warning = {
  id: RiskId
  /** the concept's name, shown prominently */
  title: string
  /** one line on why this is risky, in general */
  body: string
  /** this trade's actual number */
  detail: string
}

const pct = (value: number) => `${Math.round(value)}%`

function holdingValue(holdings: HoldingRow[], athleteId: number): number {
  return holdings.find((h) => h.athlete_id === athleteId)?.market_value ?? 0
}

/** Advisory only -- the backend still decides whether a trade is allowed. */
export function evaluateTrade(
  side: 'buy' | 'sell',
  athlete: PriceRow,
  quantity: number,
  portfolio: Portfolio | null,
  rows: PriceRow[],
): Warning[] {
  if (!portfolio || athlete.price === null || quantity <= 0) return []

  const warnings: Warning[] = []
  const price = athlete.price
  const cost = price * quantity
  const total = portfolio.total_value

  if (side === 'buy') {
    // buying moves cash into holdings at the same price, so the total is unchanged
    if (total > 0) {
      const after = holdingValue(portfolio.holdings, athlete.athlete_id) + cost
      const share = (after / total) * 100
      if (share > RISK_THRESHOLDS.playerConcentrationPct) {
        warnings.push({
          id: 'PLAYER_CONCENTRATION',
          title: 'Concentration risk',
          body: 'Putting too much into one player means one bad stretch hits your whole portfolio.',
          detail: `This would put ${pct(share)} of your portfolio in ${athlete.name}.`,
        })
      }

      const sportOf = new Map(rows.map((row) => [row.athlete_id, row.sport]))
      const sameSport = portfolio.holdings
        .filter((h) => sportOf.get(h.athlete_id) === athlete.sport)
        .reduce((sum, h) => sum + h.market_value, 0)
      const sportShare = ((sameSport + cost) / total) * 100
      if (sportShare > RISK_THRESHOLDS.sportConcentrationPct) {
        warnings.push({
          id: 'SPORT_CONCENTRATION',
          title: 'Lack of diversification',
          body: 'Leaning on one sport ties your fortunes to it. Spreading across sports smooths the ride.',
          detail: `This would put ${pct(sportShare)} of your portfolio in ${athlete.sport}.`,
        })
      }
    }

    if (portfolio.cash > 0) {
      const spend = (cost / portfolio.cash) * 100
      if (spend > RISK_THRESHOLDS.cashSpendPct) {
        warnings.push({
          id: 'HIGH_CASH_SPEND',
          title: 'Over-committing capital',
          body: 'Spending most of your cash at once leaves nothing to react with or buy dips. Traders usually keep some in reserve.',
          detail: `This uses ${pct(spend)} of your cash.`,
        })
      }
    }

    if ((athlete.change_pct ?? 0) >= RISK_THRESHOLDS.chasingChangePct) {
      warnings.push({
        id: 'CHASING_BUY',
        title: 'Chasing / buying the top',
        body: 'Buying right after a sharp run-up often means paying a peak price, just before it cools.',
        detail: `${athlete.name} is up sharply recently.`,
      })
    }
  }

  if (side === 'sell') {
    const holding = portfolio.holdings.find(
      (h) => h.athlete_id === athlete.athlete_id,
    )
    const atLoss = holding !== undefined && price < holding.avg_cost
    if (atLoss && (athlete.change_pct ?? 0) < 0) {
      warnings.push({
        id: 'PANIC_SELL',
        title: 'Panic selling',
        body: 'Selling into a dip locks in the loss and misses a possible rebound.',
        detail: `You'd be selling ${athlete.name} at a loss during a downswing.`,
      })
    }
  }

  return warnings
}

const MUTED_KEY = 'ts.mutedWarnings'

/** Muting is per warning type: silencing concentration leaves panic-sell alone. */
export function mutedWarnings(): Set<RiskId> {
  try {
    const raw = localStorage.getItem(MUTED_KEY)
    return new Set(raw ? (JSON.parse(raw) as RiskId[]) : [])
  } catch {
    return new Set()
  }
}

export function muteWarnings(ids: RiskId[]) {
  try {
    const next = mutedWarnings()
    ids.forEach((id) => next.add(id))
    localStorage.setItem(MUTED_KEY, JSON.stringify([...next]))
  } catch {
    // not persisting is survivable; the warning simply shows again
  }
}
