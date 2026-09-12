import { money } from '../format'
import { sportColor } from '../sportColors'

export type SportSlice = { sport: string; value: number }

type Props = {
  /** invested value per sport, largest first */
  slices: SportSlice[]
  /** total invested, i.e. excluding cash -- this asks how concentrated the
      holdings are, which cash would only dilute */
  invested: number
}

export default function SportBreakdown({ slices, invested }: Props) {
  if (invested <= 0 || slices.length === 0) return null
  const share = (value: number) => (value / invested) * 100
  const top = slices[0]

  return (
    <div className="sport-breakdown">
      <div className="sport-bar">
        {slices.map((slice) => (
          <div
            key={slice.sport}
            className="sport-bar-seg"
            style={{
              width: `${share(slice.value)}%`,
              background: sportColor(slice.sport),
            }}
            title={`${slice.sport} — ${money(slice.value)} (${share(slice.value).toFixed(1)}%)`}
          />
        ))}
      </div>

      <ul className="sport-rows">
        {slices.map((slice) => (
          <li key={slice.sport} className="sport-row">
            <span
              className="pie-swatch"
              style={{ background: sportColor(slice.sport) }}
            />
            <span className="sport-row-name" style={{ color: sportColor(slice.sport) }}>
              {slice.sport}
            </span>
            <span className="sport-row-value">{money(slice.value)}</span>
            <span className="sport-row-pct">{share(slice.value).toFixed(1)}%</span>
          </li>
        ))}
      </ul>

      <div className="sport-note">
        {slices.length === 1
          ? `All of your invested value is in ${top.sport}.`
          : `Most concentrated: ${top.sport} at ${share(top.value).toFixed(0)}% of invested value.`}
      </div>
    </div>
  )
}
