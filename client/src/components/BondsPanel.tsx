import { useCallback, useEffect, useState } from 'react'

import { authFetch } from '../api'
import { money } from '../format'
import { evaluateBondBuy, muteWarnings, mutedWarnings, type Warning } from '../riskRules'
import { BOND_COLOR } from '../sportColors'
import type { BondTerm, Portfolio } from '../types'
import RiskDialog from './RiskDialog'

type Props = {
  portfolio: Portfolio | null
  signedIn: boolean
  onRequireLogin: () => void
  /** a bond buy is not a trade, so the lesson is asked for by concept */
  onBought: () => void
}

const FACE = 100

export default function BondsPanel({
  portfolio,
  signedIn,
  onRequireLogin,
  onBought,
}: Props) {
  const [terms, setTerms] = useState<BondTerm[] | null>(null)
  const [qty, setQty] = useState<Record<number, string>>({})
  const [busy, setBusy] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [pending, setPending] = useState<
    { term: number; quantity: number; warnings: Warning[] } | null
  >(null)

  useEffect(() => {
    authFetch('/bonds/terms')
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => data && setTerms(data.terms))
      .catch(() => undefined)
  }, [])

  const execute = useCallback(
    async (term: number, quantity: number) => {
      setBusy(term)
      setError(null)
      try {
        const res = await authFetch('/bonds/buy', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ term_days: term, quantity }),
        })
        if (!res.ok) {
          const body = await res.json().catch(() => null)
          setError(typeof body?.detail === 'string' ? body.detail : 'buy failed')
          return
        }
        setQty((prev) => ({ ...prev, [term]: '1' }))
        onBought()
      } catch {
        setError('could not reach the server')
      } finally {
        setBusy(null)
        setPending(null)
      }
    },
    [onBought],
  )

  function attempt(term: number) {
    if (!signedIn) {
      onRequireLogin()
      return
    }
    const quantity = Number(qty[term] ?? '1')
    if (!Number.isInteger(quantity) || quantity <= 0) {
      setError('quantity must be a positive whole number')
      return
    }
    const muted = mutedWarnings()
    const warnings = evaluateBondBuy(quantity * FACE, portfolio).filter(
      (w) => !muted.has(w.id),
    )
    if (warnings.length) {
      setPending({ term, quantity, warnings })
      return
    }
    execute(term, quantity)
  }

  if (!terms) return <div className="state">LOADING BONDS…</div>

  return (
    <div className="bonds">
      <div className="bonds-note">
        A bond pays a fixed coupon every game-day and returns your stake at
        maturity. It does not move with any player's price.
      </div>

      {terms.map((term) => {
        const quantity = Number(qty[term.term_days] ?? '1')
        const cost = (Number.isFinite(quantity) ? quantity : 0) * term.face
        return (
          <div key={term.term_days} className="bond-card">
            <div className="bond-head">
              <span className="bond-term" style={{ color: BOND_COLOR }}>
                {term.term_days} GAME-DAYS
              </span>
              <span className="bond-total">+{term.total_return_pct}% to maturity</span>
            </div>
            <div className="bond-facts">
              <span>{(term.coupon_rate * 100).toFixed(2)}% per game-day</span>
              <span>{money(term.face)} each</span>
              <span className="bond-penalty">
                {term.early_penalty_pct}% early-exit penalty
              </span>
            </div>
            <div className="bond-buy">
              <label className="bond-qty-label" htmlFor={`bond-qty-${term.term_days}`}>
                QTY
              </label>
              <input
                id={`bond-qty-${term.term_days}`}
                className="qty-input bond-qty"
                type="number"
                min={1}
                value={qty[term.term_days] ?? '1'}
                onChange={(e) =>
                  setQty((prev) => ({ ...prev, [term.term_days]: e.target.value }))
                }
              />
              <span className="bond-cost">{money(cost)}</span>
              <button
                className="btn buy bond-btn"
                disabled={busy === term.term_days}
                onClick={() => attempt(term.term_days)}
              >
                BUY
              </button>
            </div>
          </div>
        )
      })}

      {error && <div className="auth-error bond-error">{error}</div>}

      {pending && (
        <RiskDialog
          warnings={pending.warnings}
          onCancel={() => setPending(null)}
          onProceed={(muteTypes) => {
            if (muteTypes) muteWarnings(pending.warnings.map((w) => w.id))
            execute(pending.term, pending.quantity)
          }}
        />
      )}
    </div>
  )
}
