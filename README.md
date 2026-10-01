# Trade Superstars

A solo sports-trading simulator. Buy and sell shares in 250 real athletes
across five leagues, on a market that moves on its own and is anchored to
how those athletes actually perform.

**Live:** [trade-superstars.vercel.app](https://trade-superstars.vercel.app)
(the backend is on Render's free tier, so the first load can take a minute)

React · TypeScript · FastAPI · SQLAlchemy · PostgreSQL · Alembic · Redis · Groq

---

## What's in it

- **250 athletes, 5 sports** — 50 each from the NBA, NFL, NHL, MLB and
  Europe's top five football leagues, with per-game stats pulled from public
  sources (see [Data](#data)).
- **A live market** — prices move continuously in the background; the client
  polls every 2 seconds.
- **Index funds** — three 10-athlete baskets (Blue Chip, Consistency,
  Momentum), priced every tick from their members.
- **League bonds** — 5, 20 and 50 game-day terms that pay a fixed coupon each
  game-day and return the stake at maturity, with a penalty for early exit.
- **Limit and stop orders** — all four types, with cash and shares reserved at
  placement so nothing can be promised twice. *API only for now; there's no UI
  for them yet.*
- **Portfolio view** — holdings, allocation by sport, P/L, bonds.
- **Heatmap** — a treemap of the whole market, sized by price and coloured by
  move.
- **Leaderboard** — ranked by total portfolio value.
- **Lessons and risk warnings** — after a trade, a mascot explains the concept
  you just ran into (AI-generated); before a risky one, rule-based warnings
  flag putting too much in one player or sport, spending most of your cash,
  chasing a price run-up, and panic-selling a dip.

## How the market works

Prices come from two layers running at different speeds.

**Game-days** (every 10 minutes by default) play one game per athlete and
set a price *target*:

```
target = baseline + overreaction × form_gap × 30
```

- **baseline** is the athlete's standing within their own sport, as a
  z-score: how many standard deviations their production sits from the sport's
  average. That's what lets a star point guard and a star goalie trade on the
  same scale. Football is the exception — its free per-game data only counts
  attacking stats, so footballers are anchored on transfer market value
  instead.
- **form_gap** is their last 5 games against their own average, divided by
  their own volatility — a hot streak for a steady player counts for more than
  the same streak for an erratic one.

**Price ticks** (~10 per game-day, Poisson-timed) walk each price toward its
target:

```
price += 0.3 × (target − price)      momentum
       + 0.05 × (baseline − price)   mean reversion
       + 1% noise
```

**Where the games come from:** each athlete first replays their real season,
game by game. Once that runs out, each new game is drawn at random from the
athlete's own real games, so the market keeps their true shape — the zeros,
the skew, the ceiling. Athletes with fewer than 10 real games fall back to a
normal distribution fitted to their stats. Every draw is seeded per
(athlete, game), so a given seed reproduces the whole market exactly.

## Engineering notes

- **One trade path.** Manual trades, fund trades and order fills all go
  through a single `execute_trade` function, under a Postgres row lock on the
  user's portfolio. Concurrent trades and fills can't lose an update, and cash
  always reconciles exactly against the trade and bond ledgers.
- **Reservations, not deductions.** An open order earmarks cash or shares
  rather than moving them, so the balance stays a single ledger and only
  what's *available* changes.
- **Write-through cache.** The market snapshot is pushed to Redis after every
  tick commits, so reads never hit Postgres in steady state. Redis is
  disposable: if it's down, reads fall back to Postgres.
- **Failure isolation.** A failed bond settlement, order fill or lesson never
  takes down a tick. Lessons fall back to built-in text if the model is
  unavailable, and the backend checks at startup that its configured model
  still exists.
- **Auth.** JWT bearer tokens and bcrypt; every per-user query is scoped by
  user id, and other users' orders return 404, not 403.

## Data

| sport | athletes chosen by | per-game stats from |
|---|---|---|
| NBA | top 50 by season production | `nba_api` |
| NFL | top 50 by season production | `nfl_data_py` |
| NHL | top 50 by season production | NHL web API |
| MLB | top 50 by season production | MLB Stats API |
| Football | highest market value ([transfertracker.ai](https://transfertracker.ai/rankings/most-valuable-players)) | ESPN |

## Running locally

You'll need Docker, Python 3.14 and Node 24 (the versions it's developed on).

**1. Postgres and Redis**

```sh
docker compose up -d
```

**2. Backend**

```sh
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

Create `backend/.env`:

```sh
DATABASE_URL=postgresql+psycopg://trader:devpassword@localhost:5432/trade_superstars
JWT_SECRET=<python -c "import secrets; print(secrets.token_urlsafe(48))">
GROQ_API_KEY=          # optional: without it, lessons use built-in text
ENABLE_MANUAL_TICK=1   # optional: exposes manual advance-day / price-tick routes
```

Then build the schema, load the athletes, and start the server:

```sh
alembic upgrade head
python -m app.seed      # pulls live data from the public APIs; takes a few minutes
uvicorn app.main:app --reload
```

The market starts ticking on its own as soon as the server is up.

**3. Frontend**

```sh
cd client
npm install
npm run dev
```

Open [localhost:5173](http://localhost:5173). The Vite dev server proxies
`/api` to the backend on port 8000.

## Project layout

```
backend/
  app/
    adapters/      one per sport: who's in the market, and their game logs
    routers/       HTTP endpoints, all under /api
    pricing.py     the market engine: game-days, ticks, the perf stream
    norms.py       per-sport z-score normalization
    trading.py     the single trade path
    orders.py      limit/stop orders: reservations and the fill engine
    bonds.py       bond coupons, maturity and settlement
    funds.py       index fund construction and pricing
    lessons/       AI lessons: concept selection, generation, fallback
    ticker.py      the background scheduler that runs the market
  alembic/         schema migrations
client/
  src/
    components/    UI
    riskRules.ts   rule-based risk warnings
docs/
  deploy.md        deploying to Render + Neon + Vercel
```
