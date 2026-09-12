import { money } from '../format'
import type { Portfolio } from '../types'

export type Tab = 'market' | 'portfolio'

type Props = {
  tab: Tab
  onTab: (tab: Tab) => void
  portfolio: Portfolio | null
  stale: boolean
  user: { email: string } | null
  onLogin: () => void
  onLogout: () => void
  onOpenSettings: () => void
}

export default function Header({
  tab,
  onTab,
  portfolio,
  stale,
  user,
  onLogin,
  onLogout,
  onOpenSettings,
}: Props) {
  return (
    <div className="header">
      <div className="header-left">
        <div className="h1">TRADE SUPERSTARS</div>
        <nav className="view-tabs" aria-label="View">
          <button
            className={`view-tab${tab === 'market' ? ' on' : ''}`}
            aria-current={tab === 'market'}
            onClick={() => onTab('market')}
          >
            MARKET
          </button>
          <button
            className={`view-tab${tab === 'portfolio' ? ' on' : ''}`}
            aria-current={tab === 'portfolio'}
            onClick={() => onTab('portfolio')}
          >
            PORTFOLIO
          </button>
        </nav>
      </div>
      <div className="header-stats">
        {stale && <div className="reconnecting">RECONNECTING…</div>}
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
        {user ? (
          <div className="account">
            <div className="status-label">{user.email}</div>
            <button className="account-btn" onClick={onLogout}>
              LOG OUT
            </button>
          </div>
        ) : (
          <button className="account-btn account-login" onClick={onLogin}>
            LOG IN
          </button>
        )}
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
