import { useState } from 'react'

import type { HistoryPoint } from '../types'
import { plot } from './Sparkline'

const WIDTH = 290
const HEIGHT = 96
const INSET = 3
const MARKER_PX = 6
const TOOLTIP_PX = 108

type Props = {
  points: HistoryPoint[]
}

type Hover = {
  index: number
  /** Rendered width, needed because preserveAspectRatio="none" stretches x. */
  renderedWidth: number
}

const timeLabel = (iso: string) =>
  new Date(iso).toLocaleTimeString([], {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })

export default function PriceChart({ points }: Props) {
  const [hover, setHover] = useState<Hover | null>(null)

  if (points.length < 2) {
    return <svg width="100%" height={HEIGHT} shapeRendering="crispEdges" />
  }

  const values = points.map((point) => point.price)
  const plotted = plot(values, WIDTH, HEIGHT, INSET)
  const line = plotted.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(' ')
  // Close the path down the sides to fill the area beneath the line.
  const area = `${line} ${WIDTH},${HEIGHT} 0,${HEIGHT}`

  function pick(clientX: number, target: HTMLElement) {
    const rect = target.getBoundingClientRect()
    const ratio = (clientX - rect.left) / rect.width
    const index = Math.round(ratio * (values.length - 1))
    setHover({
      index: Math.min(values.length - 1, Math.max(0, index)),
      renderedWidth: rect.width,
    })
  }

  // y is 1:1 (viewBox height matches the rendered height); only x is stretched.
  const xScale = hover ? hover.renderedWidth / WIDTH : 1
  const active = hover ? plotted[hover.index] : null
  const markerWidth = MARKER_PX / xScale
  const pixelX = active ? active[0] * xScale : 0
  // flip the tooltip to the left of the cursor when it would overflow the right
  const flip = hover ? pixelX + TOOLTIP_PX > hover.renderedWidth : false

  return (
    <div
      className="chart"
      onMouseMove={(e) => pick(e.clientX, e.currentTarget)}
      onMouseLeave={() => setHover(null)}
      onTouchStart={(e) => pick(e.touches[0].clientX, e.currentTarget)}
      onTouchMove={(e) => pick(e.touches[0].clientX, e.currentTarget)}
      onTouchEnd={() => setHover(null)}
    >
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

        {active && (
          <>
            <line
              x1={active[0]}
              y1={0}
              x2={active[0]}
              y2={HEIGHT}
              stroke="var(--line)"
              strokeWidth={1}
              /* keeps the crosshair 1px on screen despite the x stretch */
              vectorEffect="non-scaling-stroke"
            />
            <rect
              x={active[0] - markerWidth / 2}
              y={active[1] - MARKER_PX / 2}
              width={markerWidth}
              height={MARKER_PX}
              fill="var(--cyan-hi)"
            />
          </>
        )}
      </svg>

      {hover && active && (
        <div
          className="chart-tip"
          style={
            flip
              ? { right: hover.renderedWidth - pixelX + 8 }
              : { left: pixelX + 8 }
          }
        >
          <div className="chart-tip-price">${values[hover.index].toFixed(2)}</div>
          <div className="chart-tip-time">
            {timeLabel(points[hover.index].recorded_at)}
          </div>
        </div>
      )}
    </div>
  )
}
