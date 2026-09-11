import { useState } from 'react'

import type { Warning } from '../riskRules'

type Props = {
  warnings: Warning[]
  onCancel: () => void
  /** muteTypes is true when the user ticked "don't warn me again" */
  onProceed: (muteTypes: boolean) => void
}

export default function RiskDialog({ warnings, onCancel, onProceed }: Props) {
  const [mute, setMute] = useState(false)

  return (
    <div className="settings-backdrop" onClick={onCancel}>
      <div className="settings-panel risk-panel" onClick={(e) => e.stopPropagation()}>
        <div className="panel-title risk-title">HEADS UP</div>

        <ul className="risk-list">
          {warnings.map((warning) => (
            <li key={warning.id} className="risk-item">
              {warning.message}
            </li>
          ))}
        </ul>

        <label className="risk-mute">
          <input
            type="checkbox"
            checked={mute}
            onChange={(e) => setMute(e.target.checked)}
          />
          <span>Don't warn me again</span>
        </label>

        <div className="btn-row risk-actions">
          <button className="btn risk-cancel" onClick={onCancel}>
            CANCEL
          </button>
          <button className="btn buy" onClick={() => onProceed(mute)}>
            PROCEED
          </button>
        </div>
      </div>
    </div>
  )
}
