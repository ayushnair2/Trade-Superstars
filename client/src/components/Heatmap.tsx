import { hierarchy, treemap, treemapSquarify } from 'd3-hierarchy'
import { useEffect, useMemo, useRef, useState } from 'react'

import { heatColor, HEAT_STEPS } from '../heatColors'
import { FUND_COLOR, sportColor } from '../sportColors'
import type { FundRow, PriceRow, Selection } from '../types'

type Props = {
  rows: PriceRow[]
  funds: FundRow[]
  onSelect: (selection: Selection) => void
}

const FUNDS_GROUP = 'FUNDS'
const GROUP_ORDER = ['NBA', 'NFL', 'NHL', 'MLB', 'FUT', FUNDS_GROUP]
/** Height of a group's label strip; d3 reserves it with paddingTop. */
const HEADER = 18
const GUTTER = 2
const NARROW = 760
/** Stacked group height on narrow screens, where one treemap per group keeps
 *  the sports in separate rows instead of letting d3 pack them side by side. */
const STACK_HEIGHT = 240

type Cell = {
  key: string
  selection: Selection
  group: string
  x: number
  y: number
  w: number
  h: number
}

type GroupBox = { group: string; x: number; y: number; w: number; h: number }

type Layout = { cells: Cell[]; groups: GroupBox[]; height: number }

type Leaf = {
  key: string
  selection: Selection
  group: string
  name: string
  short: string
  price: number
  changePct: number | null
}

/** Surname for a player, code for a fund -- what fits in a small block. */
function shortLabel(name: string, isFund: boolean): string {
  if (isFund) return name.replace(/\s*Index$/i, '').toUpperCase()
  const parts = name.split(' ')
  return parts[parts.length - 1]
}

function buildLeaves(rows: PriceRow[], funds: FundRow[]): Leaf[] {
  const out: Leaf[] = []
  for (const row of rows) {
    // a block's area is its price, so an unpriced athlete has no area to draw
    if (row.price === null || row.price <= 0) continue
    out.push({
      key: `athlete-${row.athlete_id}`,
      selection: { kind: 'athlete', id: row.athlete_id },
      group: row.sport,
      name: row.name,
      short: shortLabel(row.name, false),
      price: row.price,
      changePct: row.change_pct,
    })
  }
  for (const fund of funds) {
    if (fund.price === null || fund.price <= 0) continue
    out.push({
      key: `fund-${fund.fund_id}`,
      selection: { kind: 'fund', id: fund.fund_id, code: fund.code },
      group: FUNDS_GROUP,
      name: fund.name,
      short: shortLabel(fund.name, true),
      price: fund.price,
      changePct: fund.change_pct,
    })
  }
  return out
}

function groupsOf(leaves: Leaf[]): string[] {
  const present = new Set(leaves.map((leaf) => leaf.group))
  const known = GROUP_ORDER.filter((g) => present.has(g))
  const extra = [...present].filter((g) => !GROUP_ORDER.includes(g)).sort()
  return [...known, ...extra]
}

/** d3-hierarchy computes the rectangles; everything else here is plain divs. */
function packGroup(leaves: Leaf[], w: number, h: number) {
  const root = hierarchy<{ children?: Leaf[]; leaf?: Leaf }>(
    { children: leaves.map((leaf) => ({ leaf })) },
    (d) => d.children,
  ).sum((d) => d.leaf?.price ?? 0)
  treemap<{ children?: Leaf[]; leaf?: Leaf }>()
    .tile(treemapSquarify)
    .size([w, h])
    .paddingInner(GUTTER)
    .round(true)(root)
  return root.leaves()
}

function computeLayout(
  leaves: Leaf[],
  width: number,
  height: number,
  narrow: boolean,
): Layout {
  const order = groupsOf(leaves)
  if (width <= 0 || order.length === 0) return { cells: [], groups: [], height: 0 }

  const cells: Cell[] = []
  const groups: GroupBox[] = []

  if (narrow) {
    // one treemap per group, stacked: the sports must not share a row here
    let y = 0
    for (const group of order) {
      const members = leaves.filter((leaf) => leaf.group === group)
      groups.push({ group, x: 0, y, w: width, h: STACK_HEIGHT })
      for (const node of packGroup(members, width, STACK_HEIGHT - HEADER)) {
        const leaf = node.data.leaf!
        cells.push({
          key: leaf.key,
          selection: leaf.selection,
          group,
          x: node.x0,
          y: y + HEADER + node.y0,
          w: node.x1 - node.x0,
          h: node.y1 - node.y0,
        })
      }
      y += STACK_HEIGHT + GUTTER
    }
    return { cells, groups, height: Math.max(0, y - GUTTER) }
  }

  // desktop: one hierarchy, so d3 packs the groups against each other too
  const root = hierarchy<{ group?: string; children?: unknown[]; leaf?: Leaf }>(
    {
      children: order.map((group) => ({
        group,
        children: leaves
          .filter((leaf) => leaf.group === group)
          .map((leaf) => ({ leaf })),
      })),
    },
    (d) => d.children as { group?: string; leaf?: Leaf }[] | undefined,
  ).sum((d) => d.leaf?.price ?? 0)

  treemap<{ group?: string; children?: unknown[]; leaf?: Leaf }>()
    .tile(treemapSquarify)
    .size([width, height])
    .paddingOuter(GUTTER)
    .paddingTop(HEADER)
    .paddingInner(GUTTER)
    .round(true)(root)

  for (const node of root.children ?? []) {
    groups.push({
      group: node.data.group!,
      x: node.x0,
      y: node.y0,
      w: node.x1 - node.x0,
      h: node.y1 - node.y0,
    })
  }
  for (const node of root.leaves()) {
    const leaf = node.data.leaf
    if (!leaf) continue
    cells.push({
      key: leaf.key,
      selection: leaf.selection,
      group: leaf.group,
      x: node.x0,
      y: node.y0,
      w: node.x1 - node.x0,
      h: node.y1 - node.y0,
    })
  }
  return { cells, groups, height }
}

export default function Heatmap({ rows, funds, onSelect }: Props) {
  const boxRef = useRef<HTMLDivElement | null>(null)
  const [size, setSize] = useState({ width: 0, height: 0 })
  const [hover, setHover] = useState<{ leaf: Leaf; x: number; y: number } | null>(null)

  const leaves = useMemo(() => buildLeaves(rows, funds), [rows, funds])
  // live values, looked up at render so colour and label follow every poll
  const byKey = useMemo(
    () => new Map(leaves.map((leaf) => [leaf.key, leaf])),
    [leaves],
  )
  // the set of assets, not their prices: this is what a relayout depends on
  const idsKey = useMemo(
    () => leaves.map((leaf) => leaf.key).sort().join(','),
    [leaves],
  )

  useEffect(() => {
    const node = boxRef.current
    if (!node) return
    const observer = new ResizeObserver(([entry]) => {
      setSize({
        width: Math.floor(entry.contentRect.width),
        height: Math.floor(entry.contentRect.height),
      })
    })
    observer.observe(node)
    return () => observer.disconnect()
  }, [])

  const narrow = size.width > 0 && size.width < NARROW

  // The leaves the layout was sized from, frozen until the asset set changes.
  // Prices move every two seconds; re-running the treemap on each of those
  // would make every block jump, so sizing is pinned to this snapshot and only
  // the colours and labels below follow the poll.
  const [sizing, setSizing] = useState({ key: idsKey, leaves })
  if (sizing.key !== idsKey) setSizing({ key: idsKey, leaves })

  const layout = useMemo(
    () => computeLayout(sizing.leaves, size.width, size.height, narrow),
    [sizing, size.width, size.height, narrow],
  )

  return (
    <div className="panel heat-panel">
      <div className="heat-top">
        <div className="panel-title">HEATMAP</div>
        <div className="heat-legend">
          {HEAT_STEPS.map((step) => (
            <span key={step.label} className="heat-key">
              <span className="heat-swatch" style={{ background: step.color }} />
              {step.label}
            </span>
          ))}
        </div>
      </div>

      <div
        ref={boxRef}
        className={`heat-box${narrow ? ' stacked' : ''}`}
        onMouseLeave={() => setHover(null)}
      >
        <div
          className="heat-canvas"
          style={narrow ? { height: layout.height } : undefined}
        >
          {layout.groups.map((box) => {
            const color = box.group === FUNDS_GROUP ? FUND_COLOR : sportColor(box.group)
            return (
              <div
                key={`g-${box.group}`}
                className="heat-group"
                style={{ left: box.x, top: box.y, width: box.w, height: box.h }}
              >
                <div className="heat-group-label" style={{ color }}>
                  {box.group}
                </div>
              </div>
            )
          })}

          {layout.cells.map((cell) => {
            const leaf = byKey.get(cell.key)
            if (!leaf) return null
            const large = cell.w >= 62 && cell.h >= 46
            const medium = !large && cell.w >= 40 && cell.h >= 26
            const change =
              leaf.changePct === null
                ? '--'
                : `${leaf.changePct >= 0 ? '+' : ''}${leaf.changePct.toFixed(1)}%`
            return (
              <div
                key={cell.key}
                className="heat-cell"
                style={{
                  left: cell.x,
                  top: cell.y,
                  width: cell.w,
                  height: cell.h,
                  background: heatColor(leaf.changePct),
                }}
                onMouseMove={(e) =>
                  setHover({ leaf, x: e.clientX, y: e.clientY })
                }
                onMouseLeave={() => setHover(null)}
                onClick={() => onSelect(leaf.selection)}
              >
                {large && (
                  <>
                    <span className="heat-name">{leaf.short}</span>
                    <span className="heat-price">${leaf.price.toFixed(0)}</span>
                    <span className="heat-change">{change}</span>
                  </>
                )}
                {medium && (
                  <>
                    <span className="heat-name sm">{leaf.short}</span>
                    <span className="heat-change sm">{change}</span>
                  </>
                )}
              </div>
            )
          })}
        </div>
      </div>

      {hover && (
        <div
          className="heat-tip"
          style={{ left: hover.x + 14, top: hover.y + 14 }}
          role="tooltip"
        >
          <div className="heat-tip-name">{hover.leaf.name}</div>
          <div className="heat-tip-row">
            <span
              style={{
                color:
                  hover.leaf.group === FUNDS_GROUP
                    ? FUND_COLOR
                    : sportColor(hover.leaf.group),
              }}
            >
              {hover.leaf.group}
            </span>
            <span>${hover.leaf.price.toFixed(2)}</span>
            <span>
              {hover.leaf.changePct === null
                ? '--'
                : `${hover.leaf.changePct >= 0 ? '+' : ''}${hover.leaf.changePct.toFixed(1)}%`}
            </span>
          </div>
        </div>
      )}
    </div>
  )
}
