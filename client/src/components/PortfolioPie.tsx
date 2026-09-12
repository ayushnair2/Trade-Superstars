import { money } from '../format'

export type Slice = {
  key: string
  label: string
  value: number
  color: string
  /** shown in the legend next to the label, e.g. a sport tag */
  badge?: React.ReactNode
}

type Props = {
  slices: Slice[]
  total: number
}

const SIZE = 190
const R = 88
const CX = SIZE / 2
const CY = SIZE / 2
/** start at 12 o'clock so the biggest slice reads first, clockwise */
const START = -Math.PI / 2

function wedge(start: number, end: number): string {
  const x1 = CX + R * Math.cos(start)
  const y1 = CY + R * Math.sin(start)
  const x2 = CX + R * Math.cos(end)
  const y2 = CY + R * Math.sin(end)
  const large = end - start > Math.PI ? 1 : 0
  return `M ${CX} ${CY} L ${x1.toFixed(2)} ${y1.toFixed(2)} A ${R} ${R} 0 ${large} 1 ${x2.toFixed(2)} ${y2.toFixed(2)} Z`
}

export default function PortfolioPie({ slices, total }: Props) {
  if (total <= 0) return null
  const share = (value: number) => (value / total) * 100

  let angle = START
  const wedges = slices.map((slice) => {
    const start = angle
    angle += (slice.value / total) * Math.PI * 2
    return { slice, start, end: angle }
  })

  // a lone slice is the whole circle, and an arc whose ends coincide draws nothing
  const whole = slices.length === 1 ? slices[0] : null

  return (
    <div className="pie-wrap">
      {/* crispEdges keeps the curve stair-stepped, which is the point */}
      <svg
        width={SIZE}
        height={SIZE}
        viewBox={`0 0 ${SIZE} ${SIZE}`}
        shapeRendering="crispEdges"
        className="pie"
        role="img"
        aria-label="Portfolio allocation by holding"
      >
        {whole ? (
          <circle cx={CX} cy={CY} r={R} fill={whole.color} stroke="var(--bg)" strokeWidth="3" />
        ) : (
          wedges.map(({ slice, start, end }) => (
            <path
              key={slice.key}
              d={wedge(start, end)}
              fill={slice.color}
              stroke="var(--bg)"
              strokeWidth="3"
            >
              <title>{`${slice.label} — ${money(slice.value)} (${share(slice.value).toFixed(1)}%)`}</title>
            </path>
          ))
        )}
      </svg>

      <ul className="pie-legend">
        {slices.map((slice) => (
          <li key={slice.key} className="pie-legend-row">
            <span className="pie-swatch" style={{ background: slice.color }} />
            <span className="pie-legend-name">{slice.label}</span>
            {slice.badge}
            <span className="pie-legend-pct">{share(slice.value).toFixed(1)}%</span>
          </li>
        ))}
      </ul>
    </div>
  )
}
