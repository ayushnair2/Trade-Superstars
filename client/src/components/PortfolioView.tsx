import { useMemo, useState } from 'react'

import { changeClass, money } from '../format'
import type { HoldingRow, Portfolio, PriceRow } from '../types'
import { FUND_COLOR } from '../sportColors'
import FundTag from './FundTag'
import PortfolioPie, { type Slice } from './PortfolioPie'
import SportBreakdown, { type SportSlice } from './SportBreakdown'
import SportTag from './SportTag'

type Props = {
  portfolio: Portfolio | null
  rows: PriceRow[]
  signedIn: boolean
  onRequireLogin: () => void
  onGoToMarket: () => void
}

type SortKey = 'market_value' | 'unrealized_pl'

/* Sweetie-16 hues that clear the dark panel, cycled so each holding gets its
   own slice. Sport colour is carried by the legend's tag instead: two NBA
   holdings need to be told apart here, which one shared colour cannot do. */
const SLICE_COLORS = [
  '#41a6f6',
  '#ffcd75',
  '#a7f070',
  '#ef7d57',
  '#cf8ef4',
  '#73eff7',
  '#38b764',
  '#b13e53',
]
const CASH_COLOR = '#566c86'
const OTHER_COLOR = '#94b0c2'
/** beyond this the legend stops being readable, so the tail is pooled */
const MAX_SLICES = 8

const pct = (value: number) => `${value >= 0 ? '+' : ''}${value.toFixed(2)}%`

const isFund = (holding: HoldingRow) =>
  holding.asset_type === 'fund' || holding.fund_id != null

export default function PortfolioView({
  portfolio,
  rows,
  signedIn,
  onRequireLogin,
  onGoToMarket,
}: Props) {
  const [sortKey, setSortKey] = useState<SortKey>('market_value')

  const sportOf = useMemo(
    () => new Map(rows.map((row) => [row.athlete_id, row.sport])),
    [rows],
  )

  const stats = useMemo(() => {
    const holdings = portfolio?.holdings ?? []
    const invested = holdings.reduce((sum, h) => sum + h.market_value, 0)
    const costBasis = holdings.reduce((sum, h) => sum + h.quantity * h.avg_cost, 0)
    const totalPl = holdings.reduce((sum, h) => sum + h.unrealized_pl, 0)
    return {
      invested,
      costBasis,
      totalPl,
      // against what was paid, not against total value -- cash never gained
      plPct: costBasis > 0 ? (totalPl / costBasis) * 100 : 0,
    }
  }, [portfolio])

  const sorted = useMemo(() => {
    const holdings = [...(portfolio?.holdings ?? [])]
    return holdings.sort((a, b) => b[sortKey] - a[sortKey])
  }, [portfolio, sortKey])

  const slices = useMemo<Slice[]>(() => {
    if (!portfolio) return []
    const byValue = [...portfolio.holdings].sort(
      (a, b) => b.market_value - a.market_value,
    )
    const head = byValue.slice(0, MAX_SLICES)
    const tail = byValue.slice(MAX_SLICES)

    const out: Slice[] = head.map((holding, index) => {
      const fund = isFund(holding)
      const sport = holding.athlete_id === null ? undefined : sportOf.get(holding.athlete_id)
      return {
        key: fund ? `fund-${holding.fund_id}` : `athlete-${holding.athlete_id}`,
        label: holding.name,
        value: holding.market_value,
        // funds keep their own accent wherever they land in the order, so a
        // basket never reads as just another player
        color: fund ? FUND_COLOR : SLICE_COLORS[index % SLICE_COLORS.length],
        badge: fund ? <FundTag /> : sport ? <SportTag sport={sport} /> : undefined,
      }
    })
    if (tail.length > 0) {
      out.push({
        key: 'other',
        label: `${tail.length} more`,
        value: tail.reduce((sum, h) => sum + h.market_value, 0),
        color: OTHER_COLOR,
      })
    }
    if (portfolio.cash > 0) {
      out.push({ key: 'cash', label: 'Cash', value: portfolio.cash, color: CASH_COLOR })
    }
    return out
  }, [portfolio, sportOf])

  const sportSlices = useMemo<SportSlice[]>(() => {
    const totals = new Map<string, number>()
    for (const holding of portfolio?.holdings ?? []) {
      // a fund spans several sports; counting it under one would misreport
      // concentration, so the breakdown is of directly-held players only
      if (isFund(holding) || holding.athlete_id === null) continue
      const sport = sportOf.get(holding.athlete_id) ?? '—'
      totals.set(sport, (totals.get(sport) ?? 0) + holding.market_value)
    }
    return [...totals.entries()]
      .map(([sport, value]) => ({ sport, value }))
      .sort((a, b) => b.value - a.value)
  }, [portfolio, sportOf])

  if (!signedIn || !portfolio) {
    return (
      <div className="panel pf-gate">
        <div className="panel-title">PORTFOLIO</div>
        <div className="pf-gate-msg">Log in to see your portfolio.</div>
        <button className="btn buy pf-cta" onClick={onRequireLogin}>
          LOG IN
        </button>
      </div>
    )
  }

  const empty = portfolio.holdings.length === 0

  return (
    <div className="pf">
      <div className="pf-summary">
        <Stat label="TOTAL VALUE" value={money(portfolio.total_value)} />
        <Stat label="CASH" value={money(portfolio.cash)} />
        <Stat label="INVESTED" value={money(stats.invested)} />
        <Stat
          label="TOTAL P&L"
          value={`${stats.totalPl >= 0 ? '+' : '-'}${money(Math.abs(stats.totalPl))}`}
          sub={pct(stats.plPct)}
          tone={changeClass(stats.totalPl)}
        />
        <Stat label="HOLDINGS" value={String(portfolio.holdings.length)} />
      </div>

      {empty ? (
        <div className="panel pf-empty">
          <div className="pf-empty-art">▤</div>
          <div className="pf-empty-title">You don't own anything yet</div>
          <div className="pf-empty-note">
            Head to the market and buy your first player.
          </div>
          <button className="btn buy pf-cta" onClick={onGoToMarket}>
            GO TO MARKET
          </button>
        </div>
      ) : (
        <>
          <div className="pf-charts">
            <div className="panel">
              <div className="panel-title">ALLOCATION</div>
              <PortfolioPie slices={slices} total={portfolio.total_value} />
            </div>
            <div className="panel">
              <div className="panel-title">BY SPORT</div>
              {sportSlices.length === 0 ? (
                <div className="pf-sport-empty">
                  You only hold funds. A fund already spreads across sports, so
                  there is no single-sport concentration to show.
                </div>
              ) : (
                <SportBreakdown
                  slices={sportSlices}
                  invested={sportSlices.reduce((sum, s) => sum + s.value, 0)}
                />
              )}
            </div>
          </div>

          <div className="panel">
            <div className="panel-title">HOLDINGS</div>
            <div className="pf-sort">
              <span className="pf-sort-label">SORT</span>
              <button
                className={`pf-sort-btn${sortKey === 'market_value' ? ' on' : ''}`}
                onClick={() => setSortKey('market_value')}
              >
                VALUE
              </button>
              <button
                className={`pf-sort-btn${sortKey === 'unrealized_pl' ? ' on' : ''}`}
                onClick={() => setSortKey('unrealized_pl')}
              >
                P&L
              </button>
            </div>

            <div className="pf-table-scroll">
              <table className="pf-table">
                <thead>
                  <tr>
                    <th>PLAYER</th>
                    <th>SPORT</th>
                    <th className="num">QTY</th>
                    <th className="num">AVG COST</th>
                    <th className="num">PRICE</th>
                    <th className="num">VALUE</th>
                    <th className="num">P&L</th>
                  </tr>
                </thead>
                <tbody>
                  {sorted.map((holding) => {
                    const fund = isFund(holding)
                    const sport =
                      holding.athlete_id === null
                        ? undefined
                        : sportOf.get(holding.athlete_id)
                    return (
                      <tr
                        key={fund ? `fund-${holding.fund_id}` : `athlete-${holding.athlete_id}`}
                      >
                        <td className="pf-name">{holding.name}</td>
                        <td>
                          {fund ? (
                            <FundTag />
                          ) : sport ? (
                            <SportTag sport={sport} />
                          ) : (
                            <span className="pf-dim">—</span>
                          )}
                        </td>
                        <td className="num">{holding.quantity}</td>
                        <td className="num">{money(holding.avg_cost)}</td>
                        <td className="num">{money(holding.current_price)}</td>
                        <td className="num">{money(holding.market_value)}</td>
                        <td className={`num ${changeClass(holding.unrealized_pl || 0)}`}>
                          {holding.unrealized_pl >= 0 ? '+' : '-'}
                          {money(Math.abs(holding.unrealized_pl))}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </div>
  )
}

function Stat({
  label,
  value,
  sub,
  tone,
}: {
  label: string
  value: string
  sub?: string
  tone?: string
}) {
  return (
    <div className="panel pf-stat">
      <div className="pf-stat-label">{label}</div>
      <div className={`pf-stat-value${tone ? ` ${tone}` : ''}`}>{value}</div>
      {sub && <div className={`pf-stat-sub${tone ? ` ${tone}` : ''}`}>{sub}</div>}
    </div>
  )
}
