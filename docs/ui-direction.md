# Trade Superstars — UI direction

Text companion to `ui-direction.html`. That file is the reference mockup; this file is the
source of truth for building the client. Palette is Sweetie 16.

## Palette

Every hex in the mockup, with its role.

### Core surfaces

| Token | Hex | Role |
|---|---|---|
| `--bg` | `#1a1c2c` | Page background. The darkest surface; everything sits on it. |
| `--panel` | `#333c57` | Default panel fill. |
| `--panel2` | `#29366f` | Recessed/selected fill — selected market row, tag chips. Reads as "this one". |
| `--line` | `#566c86` | All borders and row dividers. |
| `#000` | `#000000` | Offset shadow under panels/buttons, and button borders. Not a surface. |

### Text

| Token | Hex | Role |
|---|---|---|
| `--white` | `#f4f4f4` | Primary text. Off-white, never pure `#fff`. |
| `--muted` | `#94b0c2` | Secondary text — field labels (CASH, PORTFOLIO, QTY), axis text, flat/0.0% values. |
| — | `#0d2a17` | Text on the green BUY button only. Dark green so the button reads as a lit surface. |

### Semantic — direction

| Token | Hex | Role |
|---|---|---|
| `--up` | `#38b764` | Green, up. Fills — BUY button background. |
| `--up-hi` | `#a7f070` | Green, up. Text and strokes — % change, up sparklines. Brighter for contrast on dark panels. |
| `--down` | `#b13e53` | Red, down. Fills — SELL button background. |
| `--down-hi` | `#ef7d57` | Red, down. Text and strokes — % change, down sparklines. |

Pattern: the `--up`/`--down` base is for **fills**, the `-hi` variant is for **text and 1–3px strokes**.
Thin marks need the brighter value to hold up against `--panel`.

### Accent and data

| Token | Hex | Role |
|---|---|---|
| `--amber` | `#ffcd75` | The single accent. Section titles, app title, lesson-box border and star. Use sparingly — it marks what matters, so it stops working if it's everywhere. |
| `--cyan` | `#41a6f6` | Chart line — the detail price chart stroke, plus its fill at `opacity: 0.14`. |
| `--cyan-hi` | `#73eff7` | Highlighted inline terms (e.g. "volatility" in lesson text) and tag chip text. |

Flat/no-change is `--muted`, not green or red.

## Fonts

Both loaded from Google Fonts. Split by role, not by size:

- **Press Start 2P** — titles and large prices. Section headers, the app title, the detail
  price, button labels, tag chips, the cash/portfolio figures.
- **Silkscreen** (400/700) — data and body text. Market-list prices, quantities, lesson
  copy, labels.

Why the split: Press Start 2P is a wide, blocky, low-density face. It carries authority at
large sizes and short strings, but it is close to unreadable in a paragraph or a dense
column of numbers — the glyphs are too wide and the letterspacing too loose to scan. Silkscreen
is narrower and taller-x-height, so rows of prices align and stay legible at 11–15px, and
body text can actually be read. So: Press Start 2P for anything you *look at*, Silkscreen
for anything you *read* or *compare*.

Both fall back to `monospace`.

### Type sizes in the mockup

| Use | Font | Size |
|---|---|---|
| App title | Press Start 2P | 16px |
| Detail price | Press Start 2P | 22px |
| Panel section title | Press Start 2P | 11px |
| Cash / portfolio figure | Press Start 2P | 13px |
| Button label | Press Start 2P | 10px |
| Lesson header | Press Start 2P | 9px |
| Tag chip | Press Start 2P | 8px |
| Market row name / price | Silkscreen | 15px |
| % change, qty value | Silkscreen | 13–14px |
| Body / lesson copy | Silkscreen | 14px, line-height 1.7 |
| Field label | Silkscreen | 11px |

## Panel style

Non-negotiable, and the reason the whole thing reads as pixel art:

- **3px solid borders** (`--line`), 2px on smaller chrome — tag chips, row dividers.
- **`6px 6px 0 #000`** offset shadow on panels. Hard offset, zero blur radius.
  Buttons use `4px 4px 0 #000`.
- **No `border-radius`.** Every corner is square.
- **No gradients.** Flat fills only. The one exception is the chart area fill, which is a
  flat `--cyan` at `opacity: 0.14` — still flat, just transparent.
- **No blur.** No `filter: blur`, no soft shadows, no glow.

Supporting details:

- `-webkit-font-smoothing: none` and `image-rendering: pixelated` — keep edges hard.
- SVGs use `shape-rendering="crispEdges"` so chart lines don't antialias.
- Sparkline strokes 2px; detail chart stroke 3px.
- Spacing is on even/multiple-of-2 values (padding 14px, gaps 10–22px). Keep to whole even
  pixels; no fractional or `rem`-derived values that land off-grid.

## Semantic colors

One rule, applied everywhere:

- **Green = up.** Price rising, positive % change, gains, BUY.
- **Red = down.** Price falling, negative % change, losses, SELL.
- **Amber = the single accent.** It is not semantic — it doesn't mean good or bad. It marks
  structure and attention: titles, the lesson box. Exactly one accent color; resist adding a
  second.
- **Muted = flat.** Zero change is `--muted`, so unchanged never gets misread as directional.

Direction is also carried by glyph, not color alone: ▲ (`&#9650;`) up, ▼ (`&#9660;`) down.
Keep that — it's the accessibility fallback for red/green colorblindness, which is the common one.

## Animation intent (later)

Not built yet. Recorded so the client is built with room for it.

The governing principle: **snap and tween, not smooth easing.** Pixel-art UI reads as
mechanical. Transitions should feel like a scoreboard flipping, not like a modern web app
sliding. That means stepped/discrete motion, short durations, and `steps()` or linear
timing over `ease-in-out`. Nothing should feel like it glides.

- **Numbers tick up digit by digit.** Value changes count from old to new rather than
  swapping instantly — like a mechanical counter rolling. Discrete integer steps, not an
  interpolated float. Implies number displays need a component that owns its own animated
  value, not a raw text node.
- **Prices flash on change.** A brief background or text-color flash — green on tick up, red
  on tick down — that decays back to rest. Short (~150–300ms), hard on, stepped off.
- **Buttons depress on click.** Translate the button down/right by its shadow offset and
  shrink the shadow to match, so it looks physically pressed into the panel. Instant on
  press, instant on release — no transition curve.

Implication for the client: prices and portfolio values need to be components that can
observe their previous value, so all three effects have something to fire on.
