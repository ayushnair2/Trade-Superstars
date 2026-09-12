import os

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.config import SPARK_WINDOW
from app.db import get_session
from app.funds import fund_rows
from app.models import Athlete, Price
from app.pricing import advance_game_day, advance_price_tick, get_state

router = APIRouter(prefix="/market", tags=["market"])

TRUTHY = {"1", "true", "yes", "on"}


def require_manual_tick() -> None:
    """Manual market control is a local dev/testing tool only.

    In production the background ticker drives the market, so these routes stay
    off unless ENABLE_MANUAL_TICK is set -- they mutate state shared by every
    user. 404 rather than 403 so a disabled build looks like it has no such route.
    """
    if (os.environ.get("ENABLE_MANUAL_TICK") or "").lower() not in TRUTHY:
        raise HTTPException(status_code=404, detail="Not Found")


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
    for athlete in session.scalars(
        select(Athlete).where(Athlete.retired_at.is_(None))
    ).all():
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


@router.post(
    "/advance-day",
    dependencies=[Depends(require_manual_tick), Depends(get_current_user)],
)
def advance_day(session: Session = Depends(get_session)):
    """Run one game-day: new game per athlete, new form, new targets."""
    results = advance_game_day(session)
    state = get_state(session)
    return {
        "current_day": state.current_day,
        "athletes": results,
    }


@router.post(
    "/price-tick",
    dependencies=[Depends(require_manual_tick), Depends(get_current_user)],
)
def price_tick(tick_index: int = 0, session: Session = Depends(get_session)):
    """Run one price tick: move every price toward its stored target."""
    prices = advance_price_tick(session, tick_index)
    state = get_state(session)
    return {
        "current_day": state.current_day,
        "current_step": state.current_step,
        "prices": prices,
    }


@router.get("/prices")
def prices(session: Session = Depends(get_session)):
    state = get_state(session)
    return {
        "current_step": state.current_step,
        "current_day": state.current_day,
        "prices": _latest_prices(session),
        # a separate key, so every existing reader of "prices" is unaffected
        "funds": fund_rows(session),
    }
