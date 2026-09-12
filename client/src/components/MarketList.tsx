import { useMemo, useState } from 'react'

import { FUND_COLOR, sportColor } from '../sportColors'
import type { FundRow, PriceRow, Selection } from '../types'
import FundTag from './FundTag'
import MarketRow from './MarketRow'
import SportTag from './SportTag'

const ALL = 'ALL'
const FUNDS = 'FUNDS'
// Known sports lead in this order; anything new in the data is appended, so a
// sixth sport shows up without touching this file.
const SPORT_ORDER = ['NBA', 'NFL', 'NHL', 'MLB', 'FUT']

type Props = {
  rows: PriceRow[]
  funds: FundRow[]
  selection: Selection | null
  onSelect: (selection: Selection) => void
}

export default function MarketList({ rows, funds, selection, onSelect }: Props) {
  const [filter, setFilter] = useState(ALL)
  const [query, setQuery] = useState('')

  const tabs = useMemo(() => {
    const present = new Set(rows.map((row) => row.sport))
    const known = SPORT_ORDER.filter((s) => present.has(s))
    const extra = [...present].filter((s) => !SPORT_ORDER.includes(s)).sort()
    // funds sit next to ALL, ahead of the sports: they span all of them
    return [ALL, ...(funds.length ? [FUNDS] : []), ...known, ...extra]
  }, [rows, funds])

  const needle = query.trim().toLowerCase()

  // funds show under ALL and their own tab, never under a single sport
  const visibleFunds = useMemo(() => {
    if (filter !== ALL && filter !== FUNDS) return []
    if (needle === '') return funds
    return funds.filter(
      (fund) =>
        fund.name.toLowerCase().includes(needle) ||
        fund.code.toLowerCase().includes(needle),
    )
  }, [funds, filter, needle])

  const visibleAthletes = useMemo(() => {
    if (filter === FUNDS) return []
    return rows.filter(
      (row) =>
        (filter === ALL || row.sport === filter) &&
        (needle === '' || row.name.toLowerCase().includes(needle)),
    )
  }, [rows, filter, needle])

  const total = rows.length + funds.length
  const shown = visibleAthletes.length + visibleFunds.length

  return (
    <div className="panel">
      <div className="panel-title">MARKET</div>

      <div className="market-filters">
        {tabs.map((option) => {
          const accent = option === FUNDS ? FUND_COLOR : sportColor(option)
          return (
            <button
              key={option}
              className={option === filter ? 'tab tab-on' : 'tab'}
              // the selected tab wears its own colour; ALL keeps the amber accent
              style={
                option === filter && option !== ALL
                  ? { background: accent, borderColor: accent }
                  : undefined
              }
              onClick={() => setFilter(option)}
            >
              {option}
            </button>
          )
        })}
      </div>

      <div className="market-search-row">
        <input
          className="search-input"
          type="text"
          placeholder="SEARCH PLAYER OR FUND"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <span className="market-count">
          showing {shown} of {total}
        </span>
      </div>

      <div className="market-scroll">
        {shown === 0 ? (
          <div className="market-empty">NOTHING TO SHOW</div>
        ) : (
          <>
            {visibleFunds.map((fund) => (
              <MarketRow
                key={`fund-${fund.fund_id}`}
                tag={<FundTag />}
                name={fund.name}
                price={fund.price}
                changePct={fund.change_pct}
                spark={fund.spark}
                selected={
                  selection?.kind === 'fund' && selection.id === fund.fund_id
                }
                onSelect={() =>
                  onSelect({ kind: 'fund', id: fund.fund_id, code: fund.code })
                }
              />
            ))}
            {visibleAthletes.map((row) => (
              <MarketRow
                key={`athlete-${row.athlete_id}`}
                tag={<SportTag sport={row.sport} />}
                name={row.name}
                price={row.price}
                changePct={row.change_pct}
                spark={row.spark}
                selected={
                  selection?.kind === 'athlete' && selection.id === row.athlete_id
                }
                onSelect={() => onSelect({ kind: 'athlete', id: row.athlete_id })}
              />
            ))}
          </>
        )}
      </div>
    </div>
  )
}
