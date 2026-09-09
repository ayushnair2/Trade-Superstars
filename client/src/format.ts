export const money = (value: number) =>
  `$${value.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`

export const changeClass = (pct: number | null) => {
  if (pct === null || pct === 0) return 'flat'
  return pct > 0 ? 'up' : 'down'
}

export const arrow = (pct: number | null) => {
  if (pct === null || pct === 0) return ''
  return pct > 0 ? '▲' : '▼'
}

export const sparkStroke = (pct: number | null) => {
  if (pct === null || pct === 0) return 'var(--muted)'
  return pct > 0 ? 'var(--up-hi)' : 'var(--down-hi)'
}
