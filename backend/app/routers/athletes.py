from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import Athlete, Price

router = APIRouter(prefix="/athletes", tags=["athletes"])


@router.get("/{athlete_id}/history")
def history(
    athlete_id: int,
    limit: int = Query(default=60, gt=0, le=1000),
    session: Session = Depends(get_session),
):
    if session.get(Athlete, athlete_id) is None:
        raise HTTPException(status_code=404, detail="athlete not found")

    # Take the newest `limit` rows in the DB, then flip to oldest->newest.
    rows = session.execute(
        select(Price.recorded_at, Price.price)
        .where(Price.athlete_id == athlete_id)
        .order_by(Price.id.desc())
        .limit(limit)
    ).all()

    return {
        "athlete_id": athlete_id,
        "history": [
            {"recorded_at": recorded_at.isoformat(), "price": float(price)}
            for recorded_at, price in reversed(rows)
        ],
    }
