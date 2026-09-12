import { arrow, changeClass, money } from '../format'
import { sportColor } from '../sportColors'
import type {
  FundDetail,
  HistoryPoint,
  Portfolio,
  PriceRow,
  Selection,
} from '../types'
import FundTag from './FundTag'
import PriceChart from './PriceChart'
import SportTag from './SportTag'
import TradeControls from './TradeControls'

type Props = {
  selection: Selection | null
  athlete: PriceRow | null
  fund: FundDetail | null
  history: HistoryPoint[]
  held: number
  signedIn: boolean
  portfolio: Portfolio | null
  rows: PriceRow[]
  onRequireLogin: () => void
  onTraded: (tradeId: number) => void
}

/** A fund wearing a PriceRow's shape, so the risk rules can read it without
 *  knowing about funds. asset_type is what exempts it from the single-player
 *  concentration rule. */
function asPriceRow(fund: FundDetail): PriceRow & { asset_type: 'fund' } {
  return {
    athlete_id: -fund.fund_id, // never collides with a real athlete id
    name: fund.name,
    sport: 'FUND',
    price: fund.price,
    change_pct: fund.change_pct,
    spark: fund.spark,
    asset_type: 'fund',
  }
}

export default function TradePanel({
  selection,
  athlete,
  fund,
  history,
  held,
  signedIn,
  portfolio,
  rows,
  onRequireLogin,
  onTraded,
}: Props) {
  const isFund = selection?.kind === 'fund'
  const subject = isFund ? (fund ? asPriceRow(fund) : null) : athlete

  if (!selection || !subject) {
    return (
      <div className="panel trade">
        <div className="panel-title">TRADE</div>
        <div className="state">{selection ? 'LOADING…' : 'NOTHING SELECTED'}</div>
      </div>
    )
  }

  const pct = subject.change_pct
  const price = subject.price ?? 0
  // The payload carries % but not the dollar move, and its baseline sits one row
  // behind `spark`. Deriving it from the % keeps the two figures consistent.
  const delta = pct === null ? 0 : price - price / (1 + pct / 100)

  return (
    <div className="panel trade">
      <div className="trade-id">
        {isFund ? <FundTag /> : <SportTag sport={subject.sport} />}
        <span className="trade-name">{subject.name}</span>
      </div>

      <div>
        <div className="trade-price">{money(price)}</div>
        <div className={`trade-change ${changeClass(pct)}`}>
          {pct === null
            ? '--'
            : `${arrow(pct)} ${delta >= 0 ? '+' : '-'}${money(Math.abs(delta))}  (${
                pct >= 0 ? '+' : '-'
              }${Math.abs(pct).toFixed(1)}%)`}
        </div>
      </div>

      <PriceChart points={history} />

      {isFund && fund && (
        <div className="fund-basket">
          <div className="fund-basket-note">{fund.description}</div>
          <div className="fund-basket-title">
            HOLDS {fund.member_count} PLAYERS
          </div>
          <ul className="fund-members">
            {fund.members.map((member) => (
              <li key={member.athlete_id} className="fund-member">
                <span
                  className="fund-member-dot"
                  style={{ background: sportColor(member.sport) }}
                />
                <span className="fund-member-name">{member.name}</span>
                <span
                  className="fund-member-sport"
                  style={{ color: sportColor(member.sport) }}
                >
                  {member.sport}
                </span>
                <span className="fund-member-price">
                  {member.price === null ? '--' : money(member.price)}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      <TradeControls
        asset={selection}
        athlete={subject}
        held={held}
        signedIn={signedIn}
        portfolio={portfolio}
        rows={rows}
        onRequireLogin={onRequireLogin}
        onTraded={onTraded}
      />
    </div>
  )
}
