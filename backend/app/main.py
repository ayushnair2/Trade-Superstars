import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import ticker
from app.routers import athletes, lessons, market, portfolio, settings

DEFAULT_ORIGINS = "http://localhost:5173"


def allowed_origins() -> list[str]:
    """Comma-separated ALLOWED_ORIGINS, falling back to the Vite dev server."""
    raw = os.environ.get("ALLOWED_ORIGINS") or DEFAULT_ORIGINS
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


@asynccontextmanager
async def lifespan(_: FastAPI):
    ticker.start()
    try:
        yield
    finally:
        await ticker.stop()


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(market.router)
app.include_router(portfolio.router)
app.include_router(athletes.router)
app.include_router(lessons.router)
app.include_router(settings.router)


@app.get("/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    # Render injects PORT; fall back to 8000 locally.
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
