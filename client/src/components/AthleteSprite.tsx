// Resolved at build time. Files that do not exist simply are not in the map,
// which is what lets a missing sprite fall back to a placeholder instead of
// breaking the build.
const SPRITE_ASSETS = import.meta.glob('../assets/*.png', {
  eager: true,
  query: '?url',
  import: 'default',
}) as Record<string, string>

/** Look up a sprite by file name, e.g. "ohtani-sprite.png". */
export function spriteAsset(fileName: string): string | undefined {
  return SPRITE_ASSETS[`../assets/${fileName}`]
}

type Props = {
  src: string | undefined
  alt: string
  /** Frames in the horizontal strip. 1 = a still image. */
  frameCount: number
  /** Time for one full loop through every frame. */
  frameDurationMs: number
  height: number
  /** Shown in the placeholder while the asset is missing. */
  label: string
  /** Frame width; defaults to a square frame. */
  width?: number
}

export default function AthleteSprite({
  src,
  alt,
  frameCount,
  frameDurationMs,
  height,
  label,
  width,
}: Props) {
  const frameWidth = width ?? height

  if (!src) {
    return (
      <div
        className="sprite sprite-placeholder"
        style={{ width: frameWidth, height }}
        role="img"
        aria-label={`${alt} (placeholder)`}
      >
        <span>{label}</span>
      </div>
    )
  }

  return (
    <div
      className="sprite"
      role="img"
      aria-label={alt}
      style={{
        width: frameWidth,
        height,
        backgroundImage: `url(${src})`,
        // one frame fills the box; stepping background-position walks the strip
        backgroundSize: `${frameCount * 100}% 100%`,
        animation:
          frameCount > 1
            ? `sprite-frames ${frameDurationMs}ms steps(${frameCount}) infinite, sprite-bob 1.8s steps(2) infinite`
            : 'sprite-bob 1.8s steps(2) infinite',
      }}
    />
  )
}
