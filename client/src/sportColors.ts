/** One colour per sport, used everywhere a sport is shown.
 *
 * Single source of truth: adding a sport is one line here, and its tag and
 * filter tab pick the colour up automatically. All chosen to read on the dark
 * --bg (#1a1c2c) and on the --panel2 (#29366f) chip fill.
 */
export const SPORT_COLORS: Record<string, string> = {
  NBA: '#41a6f6', // blue
  NFL: '#ffcd75', // yellow
  NHL: '#ef7d57', // red
  MLB: '#a7f070', // green
  // Sweetie-16's purple (#5d275d) sits at 1.5:1 against the background, far too
  // dark to read; this lighter orchid clears 4.5:1 on both surfaces.
  FUT: '#cf8ef4', // purple
}

/** Anything not in the map falls back to the muted text colour. */
export const sportColor = (sport: string) => SPORT_COLORS[sport] ?? 'var(--muted)'
