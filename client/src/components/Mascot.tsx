import type { LessonState } from '../useLesson'

type Props = {
  state: LessonState
  onDismiss: () => void
}

// Placeholder figure: flat rects only, no character art. The real sprite is a
// deliberate later swap, so this stays obviously provisional.
function Figure() {
  return (
    <svg
      width="48"
      height="56"
      viewBox="0 0 12 14"
      shapeRendering="crispEdges"
      aria-hidden="true"
    >
      {/* antenna */}
      <rect x="5" y="0" width="2" height="2" fill="var(--cyan-hi)" />
      {/* head */}
      <rect x="2" y="2" width="8" height="5" fill="var(--cyan)" />
      <rect x="3" y="4" width="2" height="1" fill="var(--bg)" />
      <rect x="7" y="4" width="2" height="1" fill="var(--bg)" />
      {/* body */}
      <rect x="3" y="8" width="6" height="4" fill="var(--panel2)" />
      <rect x="1" y="8" width="2" height="3" fill="var(--cyan)" />
      <rect x="9" y="8" width="2" height="3" fill="var(--cyan)" />
      {/* feet */}
      <rect x="3" y="12" width="2" height="2" fill="var(--line)" />
      <rect x="7" y="12" width="2" height="2" fill="var(--line)" />
    </svg>
  )
}

export default function Mascot({ state, onDismiss }: Props) {
  if (!state.visible) return null

  return (
    <div className="mascot">
      <div className="mascot-bubble">
        <button className="mascot-close" onClick={onDismiss} aria-label="Dismiss">
          X
        </button>
        <div className="mascot-title">LESSON</div>
        <div className="mascot-text">
          {state.loading ? <span className="mascot-dots">...</span> : state.text}
        </div>
      </div>
      <div className="mascot-figure">
        <Figure />
      </div>
    </div>
  )
}
