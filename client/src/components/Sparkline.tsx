const WIDTH = 60
const HEIGHT = 20
const STROKE = 2

type Props = {
  values: number[]
  stroke: string
}

// Maps values onto the box, inset by the stroke so the line never clips.
export function plot(values: number[], width: number, height: number, inset: number) {
  const min = Math.min(...values)
  const max = Math.max(...values)
  const span = max - min
  const usable = height - inset * 2
  const stepX = values.length > 1 ? width / (values.length - 1) : 0

  return values.map((value, i) => {
    // A flat series has no range to scale against, so it sits mid-box.
    const t = span === 0 ? 0.5 : (value - min) / span
    return [i * stepX, inset + (1 - t) * usable] as const
  })
}

export default function Sparkline({ values, stroke }: Props) {
  if (values.length === 0) return <svg className="spark" width={WIDTH} height={HEIGHT} />

  const points = plot(values, WIDTH, HEIGHT, STROKE)
    .map(([x, y]) => `${x.toFixed(0)},${y.toFixed(0)}`)
    .join(' ')

  return (
    <svg
      className="spark"
      width={WIDTH}
      height={HEIGHT}
      shapeRendering="crispEdges"
      aria-hidden="true"
    >
      <polyline points={points} fill="none" stroke={stroke} strokeWidth={STROKE} />
    </svg>
  )
}
