import { COOLDOWN_PRESETS, type Settings } from '../useSettings'
import {
  DAY_LENGTH_PRESETS,
  TICKS_PER_DAY_PRESETS,
  useMarketSettings,
} from '../useMarketSettings'

type Props = {
  settings: Settings
  onClose: () => void
}

export default function SettingsPanel({ settings, onClose }: Props) {
  const {
    lessonsEnabled,
    lessonCooldownMs,
    setLessonsEnabled,
    setLessonCooldownMs,
  } = settings
  const market = useMarketSettings()

  return (
    // the backdrop is the click-outside target; the panel stops propagation
    <div className="settings-backdrop" onClick={onClose}>
      <div className="settings-panel" onClick={(e) => e.stopPropagation()}>
        <button className="settings-close" onClick={onClose} aria-label="Close">
          X
        </button>
        <div className="panel-title">SETTINGS</div>

        <div className="settings-section">Trading tips</div>

        <div className="settings-row">
          <span className="settings-label">Trading tips</span>
          <button
            className={lessonsEnabled ? 'toggle toggle-on' : 'toggle toggle-off'}
            onClick={() => setLessonsEnabled(!lessonsEnabled)}
          >
            {lessonsEnabled ? 'ON' : 'OFF'}
          </button>
        </div>

        <div className="settings-label settings-sub">Show a tip at most</div>
        <div className="settings-presets">
          {COOLDOWN_PRESETS.map((preset) => (
            <button
              key={preset.ms}
              className={
                preset.ms === lessonCooldownMs ? 'preset preset-on' : 'preset'
              }
              onClick={() => setLessonCooldownMs(preset.ms)}
            >
              {preset.label}
            </button>
          ))}
        </div>

        <div className="settings-section">Market clock</div>

        {market.settings === null ? (
          <div className="settings-sub settings-label">
            {market.error ?? 'Loading…'}
          </div>
        ) : (
          <>
            <div className="settings-label settings-sub">Game-day length</div>
            <div className="settings-presets settings-presets-3">
              {DAY_LENGTH_PRESETS.map((minutes) => (
                <button
                  key={minutes}
                  disabled={market.saving}
                  className={
                    minutes === market.settings!.day_length_minutes
                      ? 'preset preset-on'
                      : 'preset'
                  }
                  onClick={() => market.update({ day_length_minutes: minutes })}
                >
                  {minutes} min
                </button>
              ))}
            </div>

            <div className="settings-label settings-sub">Price updates per day</div>
            <div className="settings-presets">
              {TICKS_PER_DAY_PRESETS.map((ticks) => (
                <button
                  key={ticks}
                  disabled={market.saving}
                  className={
                    ticks === market.settings!.ticks_per_day
                      ? 'preset preset-on'
                      : 'preset'
                  }
                  onClick={() => market.update({ ticks_per_day: ticks })}
                >
                  {ticks}
                </button>
              ))}
            </div>

            <div className="settings-note">
              Prices update at random moments — the gaps between them vary.
            </div>
          </>
        )}

        {market.error && market.settings !== null && (
          <div className="settings-error">{market.error}</div>
        )}
      </div>
    </div>
  )
}
