"""Read-only fund endpoints. Trading funds is a later step."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_session
from app.funds import fund_rows
from app.models import Athlete, Fund, FundMember, FundPrice, Price

router = APIRouter(prefix="/funds", tags=["funds"])


def _fund_or_404(session: Session, code: str) -> Fund:
    fund = session.scalar(select(Fund).where(Fund.code == code.upper()))
    if fund is None:
        raise HTTPException(status_code=404, detail="fund not found")
    return fund


@router.get("")
def list_funds(session: Session = Depends(get_session)):
    return {"funds": fund_rows(session)}


@router.get("/{code}")
def fund_detail(code: str, session: Session = Depends(get_session)):
    fund = _fund_or_404(session, code)
    row = next(r for r in fund_rows(session) if r["fund_id"] == fund.id)

    # each member's newest price, so the basket can be read holding by holding
    latest = (
        select(Price.athlete_id, func.max(Price.id).label("price_id"))
        .group_by(Price.athlete_id)
        .subquery()
    )
    members = session.execute(
        select(Athlete, FundMember.weight, Price.price)
        .join(FundMember, FundMember.athlete_id == Athlete.id)
        .outerjoin(latest, latest.c.athlete_id == Athlete.id)
        .outerjoin(Price, Price.id == latest.c.price_id)
        .where(FundMember.fund_id == fund.id)
        .order_by(Price.price.desc())
    ).all()

    return {
        **row,
        "members": [
            {
                "athlete_id": athlete.id,
                "name": athlete.name,
                "sport": athlete.sport,
                "position": athlete.position,
                "weight": float(weight),
                "price": float(price) if price is not None else None,
            }
            for athlete, weight, price in members
        ],
    }


@router.get("/{code}/history")
def fund_history(
    code: str,
    limit: int = Query(default=60, gt=0, le=1000),
    session: Session = Depends(get_session),
):
    fund = _fund_or_404(session, code)
    rows = session.execute(
        select(FundPrice.recorded_at, FundPrice.price)
        .where(FundPrice.fund_id == fund.id)
        .order_by(FundPrice.id.desc())
        .limit(limit)
    ).all()

    return {
        "fund_id": fund.id,
        "code": fund.code,
        "history": [
            {"recorded_at": recorded_at.isoformat(), "price": float(price)}
            for recorded_at, price in reversed(rows)
        ],
    }
