from fastapi import FastAPI

from app.routers import market, portfolio

app = FastAPI()
app.include_router(market.router)
app.include_router(portfolio.router)


@app.get("/health")
def health():
    return {"status": "ok"}
