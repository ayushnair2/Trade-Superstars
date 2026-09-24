/** Seven discrete colours for the heatmap, stepped rather than a gradient.
 *
 * The extremes are Sweetie-16's own --down (#b13e53) and --up (#38b764); the
 * milder steps are those two mixed toward --bg (#1a1c2c), so a small move
 * reads as a dark block and a big one as a bright block -- the Finviz idiom,
 * kept inside the existing palette. Neutral is --panel, the same surface the
 * rest of the UI sits on.
 */
export const HEAT_STEPS = [
  { max: -5, color: '#b13e53', label: '-5%+' },
  { max: -2, color: '#7c3245', label: '-5..-2' },
  { max: -0.5, color: '#562a3c', label: '-2..-0.5' },
  { max: 0.5, color: '#333c57', label: 'flat' },
  { max: 2, color: '#265a42', label: '0.5..2' },
  { max: 5, color: '#2e8150', label: '2..5' },
  { max: Infinity, color: '#38b764', label: '+5%+' },
] as const

/** A missing change_pct is not a flat move -- it is no reading, so it gets the
 *  neutral surface rather than being bucketed as unchanged. */
export function heatColor(changePct: number | null): string {
  if (changePct === null) return '#333c57'
  return (HEAT_STEPS.find((step) => changePct < step.max) ?? HEAT_STEPS[6]).color
}
