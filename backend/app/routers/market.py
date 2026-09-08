from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import SPARK_WINDOW
from app.db import get_session
from app.models import Athlete, Price
from app.pricing import advance_market, get_state

router = APIRouter(prefix="/market", tags=["market"])


def _recent_prices(session: Session) -> dict[int, list[float]]:
    """Most recent SPARK_WINDOW+1 prices per athlete, oldest->newest.

    One window-function query for every athlete rather than a query each;
    the extra row is the baseline for change_pct (SPARK_WINDOW steps back).
    """
    rank = (
        func.row_number()
        .over(partition_by=Price.athlete_id, order_by=Price.id.desc())
        .label("rank")
    )
    ranked = select(Price.athlete_id, Price.price, Price.id, rank).subquery()
    rows = session.execute(
        select(ranked.c.athlete_id, ranked.c.price)
        .where(ranked.c.rank <= SPARK_WINDOW + 1)
        .order_by(ranked.c.athlete_id, ranked.c.id)
    ).all()

    series: dict[int, list[float]] = {}
    for athlete_id, price in rows:
        series.setdefault(athlete_id, []).append(float(price))
    return series


def _change_pct(current: float, baseline: float) -> float:
    if baseline == 0:
        return 0.0
    return round((current - baseline) / baseline * 100, 1)


def _latest_prices(session: Session) -> list[dict]:
    series = _recent_prices(session)

    rows = []
    for athlete in session.scalars(select(Athlete)).all():
        prices = series.get(athlete.id, [])
        spark = prices[-SPARK_WINDOW:]
        rows.append(
            {
                "athlete_id": athlete.id,
                "name": athlete.name,
                "sport": athlete.sport,
                "price": spark[-1] if spark else None,
                "change_pct": _change_pct(prices[-1], prices[0]) if prices else None,
                "spark": spark,
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
