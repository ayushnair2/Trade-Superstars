import { useEffect } from 'react'

import AthleteSprite, { spriteAsset } from './AthleteSprite'
import Ticker from './Ticker'

const SPRITE_HEIGHT = 176

// Named so it is obvious which asset backs which slot.
const ohtaniSprite = spriteAsset('ohtani-sprite.png')
const lebronSprite = spriteAsset('lebron-sprite.png')

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
            src={ohtaniSprite}
            alt="Shohei Ohtani pixel sprite"
            label="OHTANI"
            frameCount={4}
            frameDurationMs={900}
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
            src={lebronSprite}
            alt="LeBron James pixel sprite"
            label="LEBRON"
            frameCount={4}
            frameDurationMs={1200}
            height={SPRITE_HEIGHT}
          />
        </div>
      </div>

      <Ticker />
    </div>
  )
}
