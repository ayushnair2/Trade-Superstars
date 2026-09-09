# Deploying Trade Superstars

Backend on Render, frontend on Vercel, Postgres on Neon.

## Backend (Render)

### Environment variables

| Variable | Required | Example | Notes |
|---|---|---|---|
| `DATABASE_URL` | yes | `postgresql+psycopg://user:pass@host/db` | Neon connection string. Must use the `postgresql+psycopg://` scheme — Neon hands out `postgresql://`, so rewrite the prefix. |
| `GROQ_API_KEY` | yes | `gsk_...` | Groq API key for lesson generation. |
| `ALLOWED_ORIGINS` | yes | `https://trade-superstars.vercel.app` | Comma-separated list of origins allowed by CORS. Defaults to `http://localhost:5173` if unset, which will block the deployed frontend. |
| `PORT` | no | `10000` | Render sets this automatically. |

`DATABASE_URL` is read in `app/db.py`; `GROQ_API_KEY` in `app/lessons/provider.py`. Both
come from the process environment, so no `.env` file is needed in production —
`backend/.env` is for local dev only and is gitignored.

### Build command

```
pip install -r requirements.txt
```

### Start command

```
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

Run it from the `backend/` directory (set Render's root directory to `backend`).
`python -m app.main` also works and reads `PORT` itself, defaulting to 8000.

### Seeding the database

Once, after the database exists and `DATABASE_URL` is set:

```
python -m app.seed
```

This creates the tables, ingests athletes from the NBA adapter, loads per-game
logs and perf baselines, and opens the market at each athlete's baseline price.
It is idempotent — re-running updates athletes and logs in place and leaves an
already-open market untouched. It takes roughly 20-30s, mostly nba_api throttling.

### Notes

- The market advances on its own every `TICK_INTERVAL_SECONDS` (3s) via a
  background task started in the FastAPI lifespan handler. It runs per process,
  so keep the backend at a single instance or the market will tick faster than
  intended.
- Render free instances sleep when idle; the ticker stops while asleep.

## Frontend (Vercel)

### Environment variables

| Variable | Required | Example |
|---|---|---|
| `VITE_API_URL` | yes | `https://trade-superstars-api.onrender.com` |

Leave it empty locally: requests stay relative and the Vite proxy in
`vite.config.ts` forwards them to `http://localhost:8000`. In production it is
prefixed onto every backend call (`client/src/api.ts`). No trailing slash needed —
one is stripped if present.

See `client/.env.example`.

### Build

| Setting | Value |
|---|---|
| Root directory | `client` |
| Build command | `npm run build` |
| Output directory | `dist` |

### Order of operations

1. Create the Neon database and copy its connection string.
2. Deploy the backend with `DATABASE_URL` and `GROQ_API_KEY`; set
   `ALLOWED_ORIGINS` to a placeholder for now.
3. Run `python -m app.seed` against it.
4. Deploy the frontend with `VITE_API_URL` pointing at the backend.
5. Set `ALLOWED_ORIGINS` on the backend to the real Vercel URL and redeploy.

Step 5 matters: CORS defaults to localhost only, so the deployed frontend is
blocked until the real origin is added.
