import { FUND_COLOR } from '../sportColors'

/** The counterpart to SportTag: marks a row as a basket, not a player. */
export default function FundTag() {
  return (
    <span className="tag" style={{ color: FUND_COLOR, borderColor: FUND_COLOR }}>
      FUND
    </span>
  )
}
