from fastapi import FastAPI

from app.routers import athletes, market, portfolio

app = FastAPI()
app.include_router(market.router)
app.include_router(portfolio.router)
app.include_router(athletes.router)


@app.get("/health")
def health():
    return {"status": "ok"}
