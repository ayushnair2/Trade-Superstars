import { COOLDOWN_PRESETS, type Settings } from '../useSettings'

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

  return (
    // the backdrop is the click-outside target; the panel stops propagation
    <div className="settings-backdrop" onClick={onClose}>
      <div className="settings-panel" onClick={(e) => e.stopPropagation()}>
        <button className="settings-close" onClick={onClose} aria-label="Close">
          X
        </button>
        <div className="panel-title">SETTINGS</div>

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
      </div>
    </div>
  )
}
