from fastapi import FastAPI

from app.routers import market

app = FastAPI()
app.include_router(market.router)


@app.get("/health")
def health():
    return {"status": "ok"}
