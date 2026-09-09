from contextlib import asynccontextmanager

from fastapi import FastAPI

from app import ticker
from app.routers import athletes, market, portfolio


@asynccontextmanager
async def lifespan(_: FastAPI):
    ticker.start()
    try:
        yield
    finally:
        await ticker.stop()


app = FastAPI(lifespan=lifespan)
app.include_router(market.router)
app.include_router(portfolio.router)
app.include_router(athletes.router)


@app.get("/health")
def health():
    return {"status": "ok"}
