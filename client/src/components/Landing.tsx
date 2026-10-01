import { useEffect } from 'react'

import AthleteSprite, { spriteAsset } from './AthleteSprite'
import Ticker from './Ticker'

// 3x the 48px art: a whole multiple keeps every pixel the same size. 4x
// crowds the title just above the 900px breakpoint, where it drops to 96px.
const SPRITE_HEIGHT = 144
// AthleteSprite times the whole loop, so these are 6 frames at ~120ms and
// ~140ms each -- the dribble a touch slower than the swing.
const BATTER_LOOP_MS = 6 * 120
const HOOPER_LOOP_MS = 6 * 140

// Named so it is obvious which asset backs which slot.
const batterSprite = spriteAsset('batter-sprite.png')
const hooperSprite = spriteAsset('hooper-sprite.png')

type Props = {
  onPlay: () => void
}

export default function Landing({ onPlay }: Props) {
  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault()
        onPlay()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onPlay])

  return (
    <div className="landing">
      <div className="landing-stage">
        <div className="landing-sprite">
          <AthleteSprite
            src={batterSprite}
            alt="Pixel baseball player swinging"
            label="BATTER"
            frameCount={6}
            frameDurationMs={BATTER_LOOP_MS}
            height={SPRITE_HEIGHT}
          />
        </div>

        <div className="landing-center">
          <h1 className="landing-title">
            TRADE
            <br />
            SUPER<span className="landing-title-alt">STARS</span>
          </h1>
          <p className="landing-tagline">Buy low, sell high, learn as you trade.</p>
          <button className="landing-prompt" onClick={onPlay}>
            PRESS PLAY TO START
          </button>
        </div>

        <div className="landing-sprite">
          <AthleteSprite
            src={hooperSprite}
            alt="Pixel basketball player dribbling"
            label="HOOPER"
            frameCount={6}
            frameDurationMs={HOOPER_LOOP_MS}
            height={SPRITE_HEIGHT}
          />
        </div>
      </div>

      <Ticker />
    </div>
  )
}
