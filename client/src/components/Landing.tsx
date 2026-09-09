import Ticker from './Ticker'

type Props = {
  onPlay: () => void
}

export default function Landing({ onPlay }: Props) {
  return (
    <div className="landing">
      <div className="landing-title">
        TRADE
        <br />
        SUPERSTARS
      </div>
      <div className="landing-tagline">Buy low, sell high, learn as you trade.</div>
      <button className="landing-play" onClick={onPlay}>
        PLAY
      </button>
      <div className="landing-prompt">CLICK TO START</div>
      <Ticker />
    </div>
  )
}
