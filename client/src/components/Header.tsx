import { money } from '../format'
import type { Portfolio } from '../types'

type Props = {
  portfolio: Portfolio | null
}

export default function Header({ portfolio }: Props) {
  return (
    <div className="header">
      <div className="h1">TRADE SUPERSTARS</div>
      <div className="header-stats">
        <div>
          <div className="status-label">CASH</div>
          <div className="status-value">{portfolio ? money(portfolio.cash) : '--'}</div>
        </div>
        <div>
          <div className="status-label">PORTFOLIO</div>
          <div className="status-value">
            {portfolio ? money(portfolio.total_value) : '--'}
          </div>
        </div>
      </div>
    </div>
  )
}
