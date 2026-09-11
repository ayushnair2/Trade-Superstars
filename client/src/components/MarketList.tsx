import { useMemo, useState } from 'react'

import type { PriceRow } from '../types'
import MarketRow from './MarketRow'

const ALL = 'ALL'
// Known sports lead in this order; anything new in the data is appended, so a
// sixth sport shows up without touching this file.
const SPORT_ORDER = ['NBA', 'NFL', 'NHL', 'MLB', 'SOC']

type Props = {
  rows: PriceRow[]
  selectedId: number | null
  onSelect: (athleteId: number) => void
}

export default function MarketList({ rows, selectedId, onSelect }: Props) {
  const [sport, setSport] = useState(ALL)
  const [query, setQuery] = useState('')

  const sports = useMemo(() => {
    const present = new Set(rows.map((row) => row.sport))
    const known = SPORT_ORDER.filter((s) => present.has(s))
    const extra = [...present].filter((s) => !SPORT_ORDER.includes(s)).sort()
    return [ALL, ...known, ...extra]
  }, [rows])

  const visible = useMemo(() => {
    const needle = query.trim().toLowerCase()
    return rows.filter(
      (row) =>
        (sport === ALL || row.sport === sport) &&
        (needle === '' || row.name.toLowerCase().includes(needle)),
    )
  }, [rows, sport, query])

  return (
    <div className="panel">
      <div className="panel-title">MARKET</div>

      <div className="market-filters">
        {sports.map((option) => (
          <button
            key={option}
            className={option === sport ? 'tab tab-on' : 'tab'}
            onClick={() => setSport(option)}
          >
            {option}
          </button>
        ))}
      </div>

      <div className="market-search-row">
        <input
          className="search-input"
          type="text"
          placeholder="SEARCH PLAYER"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <span className="market-count">
          showing {visible.length} of {rows.length}
        </span>
      </div>

      <div className="market-scroll">
        {visible.length === 0 ? (
          <div className="market-empty">NO PLAYERS</div>
        ) : (
          visible.map((row) => (
            <MarketRow
              key={row.athlete_id}
              row={row}
              selected={row.athlete_id === selectedId}
              onSelect={onSelect}
            />
          ))
        )}
      </div>
    </div>
  )
}
