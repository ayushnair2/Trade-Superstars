import { plot } from './Sparkline'

const WIDTH = 290
const HEIGHT = 96
const INSET = 3

type Props = {
  values: number[]
}

export default function PriceChart({ values }: Props) {
  if (values.length < 2) {
    return <svg width="100%" height={HEIGHT} shapeRendering="crispEdges" />
  }

  const points = plot(values, WIDTH, HEIGHT, INSET)
  const line = points.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(' ')
  // Close the path down the sides to fill the area beneath the line.
  const area = `${line} ${WIDTH},${HEIGHT} 0,${HEIGHT}`

  return (
    <svg
      width="100%"
      height={HEIGHT}
      viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
      shapeRendering="crispEdges"
      preserveAspectRatio="none"
      aria-hidden="true"
    >
      <polyline points={area} fill="var(--cyan)" opacity="0.14" stroke="none" />
      <polyline points={line} fill="none" stroke="var(--cyan)" strokeWidth={3} />
    </svg>
  )
}
