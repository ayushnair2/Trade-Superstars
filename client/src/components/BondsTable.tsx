import { useCallback, useEffect, useState } from 'react'

import { authFetch } from '../api'
import { money } from '../format'
import { BOND_COLOR } from '../sportColors'
import type { BondPositions } from '../types'

type Props = { onChanged: () => void }

export default function BondsTable({ onChanged }: Props) {
  const [data, setData] = useState<BondPositions | null>(null)
  const [confirming, setConfirming] = useState<number | null>(null)
  const [busy, setBusy] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    try {
      const res = await authFetch('/bonds/positions')
      if (res.ok) setData(await res.json())
    } catch {
      // leave the last good view in place
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  async function redeem(positionId: number) {
    setBusy(positionId)
    setError(null)
    try {
      const res = await authFetch(`/bonds/${positionId}/redeem`, { method: 'POST' })
      if (!res.ok) {
        const body = await res.json().catch(() => null)
        setError(typeof body?.detail === 'string' ? body.detail : 'redeem failed')
        return
      }
      setConfirming(null)
      await load()
      onChanged()
    } catch {
      setError('could not reach the server')
    } finally {
      setBusy(null)
    }
  }

  if (!data || data.positions.length === 0) return null

  return (
    <div className="panel">
      <div className="panel-title" style={{ color: BOND_COLOR }}>
        BONDS
      </div>
      <div className="bonds-summary">
        {money(data.active_principal)} active principal · game-day{' '}
        {data.current_day}
      </div>
      {error && <div className="auth-error bond-error">{error}</div>}

      <div className="pf-table-scroll">
        <table className="pf-table">
          <thead>
            <tr>
              <th>TERM</th>
              <th className="num">QTY</th>
              <th className="num">PRINCIPAL</th>
              <th className="num">COUPONS</th>
              <th className="num">TO MATURITY</th>
              <th>STATUS</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {data.positions.map((p) => (
              <tr key={p.position_id}>
                <td>{p.term_days}d</td>
                <td className="num">{p.quantity}</td>
                <td className="num">{money(p.principal)}</td>
                <td className="num up">{money(p.coupons_received)}</td>
                <td className="num">
                  {p.status === 'active' ? `${p.days_to_maturity}d` : '—'}
                </td>
                <td>
                  <span className={`bond-status ${p.status}`}>{p.status}</span>
                </td>
                <td className="num">
                  {p.status === 'active' &&
                    (confirming === p.position_id ? (
                      <span className="bond-confirm">
                        {/* the penalty is named before it is charged */}
                        <span className="bond-confirm-text">
                          Redeem early for {money(p.principal * 0.98)}? That is a
                          2% penalty on {money(p.principal)}.
                        </span>
                        <button
                          className="btn sell bond-confirm-yes"
                          disabled={busy === p.position_id}
                          onClick={() => redeem(p.position_id)}
                        >
                          REDEEM
                        </button>
                        <button
                          className="btn bond-confirm-no"
                          onClick={() => setConfirming(null)}
                        >
                          KEEP
                        </button>
                      </span>
                    ) : (
                      <button
                        className="bond-redeem-btn"
                        onClick={() => {
                          setError(null)
                          setConfirming(p.position_id)
                        }}
                      >
                        REDEEM
                      </button>
                    ))}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
