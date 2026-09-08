type Props = {
  step: number
}

export default function Header({ step }: Props) {
  return (
    <div className="header">
      <div className="h1">TRADE SUPERSTARS</div>
      <div>
        <div className="status-label">STEP</div>
        <div className="status-value">{step}</div>
      </div>
    </div>
  )
}
