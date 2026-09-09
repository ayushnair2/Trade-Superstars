import { useEffect, useState } from 'react'

import { api } from '../api'
import { changeClass } from '../format'
import type { PriceRow } from '../types'

const POLL_MS = 2000

export default function Ticker() {
  const [rows, setRows] = useState<PriceRow[]>([])

  useEffect(() => {
    let cancelled = false

    async function load() {
      try {
        const res = await fetch(api('/market/prices'))
        if (!res.ok) return
        const data = await res.json()
        if (!cancelled) setRows(data.prices)
      } catch {
        // the landing strip is decorative -- a failed poll just leaves it as-is
      }
    }

    load()
    const id = setInterval(load, POLL_MS)
    return () => {
      cancelled = true
      clearInterval(id)
    }
  }, [])

  if (rows.length === 0) return null

  const item = (row: PriceRow, key: string) => (
    <span className="ticker-item" key={key}>
      {row.name.toUpperCase()}{' '}
      <span className="ticker-price">
        {row.price === null ? '--' : `$${row.price.toFixed(2)}`}
      </span>{' '}
      <span className={changeClass(row.change_pct)}>
        {row.change_pct === null ? '' : `${row.change_pct >= 0 ? '+' : ''}${row.change_pct.toFixed(1)}%`}
      </span>
    </span>
  )

  return (
    <div className="ticker">
      {/* the list is rendered twice so the -50% scroll loops seamlessly */}
      <div className="ticker-track">
        {rows.map((row) => item(row, `a-${row.athlete_id}`))}
        {rows.map((row) => item(row, `b-${row.athlete_id}`))}
      </div>
    </div>
  )
}
