import { money } from '../format'
import type { Portfolio } from '../types'

type Props = {
  portfolio: Portfolio | null
  onOpenSettings: () => void
}

export default function Header({ portfolio, onOpenSettings }: Props) {
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
        <button
          className="gear"
          onClick={onOpenSettings}
          aria-label="Settings"
          title="Settings"
        >
          <svg width="18" height="18" viewBox="0 0 9 9" shapeRendering="crispEdges">
            <rect x="3" y="0" width="3" height="9" fill="currentColor" />
            <rect x="0" y="3" width="9" height="3" fill="currentColor" />
            <rect x="1" y="1" width="7" height="7" fill="currentColor" />
            <rect x="3" y="3" width="3" height="3" fill="var(--panel)" />
          </svg>
        </button>
      </div>
    </div>
  )
}
