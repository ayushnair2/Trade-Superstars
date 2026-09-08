from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import Athlete, Price
from app.pricing import advance_market, get_state

router = APIRouter(prefix="/market", tags=["market"])


def _latest_prices(session: Session) -> list[dict]:
    rows = []
    for athlete in session.scalars(select(Athlete)).all():
        price = session.scalar(
            select(Price)
            .where(Price.athlete_id == athlete.id)
            .order_by(Price.id.desc())
            .limit(1)
        )
        rows.append(
            {
                "athlete_id": athlete.id,
                "name": athlete.name,
                "sport": athlete.sport,
                "price": float(price.price) if price else None,
            }
        )
    return sorted(rows, key=lambda r: (r["price"] is not None, r["price"]), reverse=True)


@router.post("/tick")
def tick(steps: int = 1, session: Session = Depends(get_session)):
    for _ in range(steps):
        advance_market(session)
    return {
        "current_step": get_state(session).current_step,
        "prices": _latest_prices(session),
    }


@router.get("/prices")
def prices(session: Session = Depends(get_session)):
    return {
        "current_step": get_state(session).current_step,
        "prices": _latest_prices(session),
    }
