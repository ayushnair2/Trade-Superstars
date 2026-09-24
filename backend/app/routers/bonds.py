"""League bond endpoints. Every one is authenticated and user-scoped."""

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.bonds import (
    active_principal,
    coupons_received,
    credit_cash,
    money,
    principal,
    terms,
)
from app.config import BOND_EARLY_PENALTY, BOND_FACE, BOND_TERMS
from app.db import get_session
from app.models import BondKind, BondPosition, BondStatus, BondTransaction, User
from app.pricing import get_state
from app.routers.portfolio import _get_portfolio

router = APIRouter(prefix="/bonds", tags=["bonds"])


class BuyRequest(BaseModel):
    term_days: int
    quantity: int = Field(gt=0)


@router.get("/terms")
def list_terms():
    """Public: the offer is a price list with nothing user-specific in it."""
    return {"terms": terms()}


@router.post("/buy")
def buy(
    body: BuyRequest,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    rate = BOND_TERMS.get(body.term_days)
    if rate is None:
        raise HTTPException(status_code=400, detail="unknown bond term")

    day = get_state(session).current_day
    cost = money(Decimal(body.quantity) * Decimal(BOND_FACE))

    # the same lock the trade path takes, for the same reason: the funds check
    # below must not be able to go stale under a concurrent buy
    portfolio = _get_portfolio(session, user, for_update=True)
    if cost > portfolio.cash:
        raise HTTPException(status_code=400, detail="insufficient funds")

    try:
        position = BondPosition(
            user_id=user.id,
            term_days=body.term_days,
            quantity=body.quantity,
            coupon_rate=Decimal(str(rate)),
            bought_day=day,
            maturity_day=day + body.term_days,
            status=BondStatus.active.value,
        )
        session.add(position)
        session.flush()

        credit_cash(session, user.id, -cost)
        session.add(
            BondTransaction(
                user_id=user.id,
                position_id=position.id,
                kind=BondKind.buy.value,
                # negative: this leaves the user's cash
                amount=-cost,
                day=day,
            )
        )
        session.commit()
    except Exception:
        session.rollback()
        raise

    session.refresh(portfolio)
    return {
        "position_id": position.id,
        "term_days": position.term_days,
        "quantity": position.quantity,
        "cost": float(cost),
        "coupon_rate": float(position.coupon_rate),
        "bought_day": position.bought_day,
        "maturity_day": position.maturity_day,
        "cash": float(portfolio.cash),
    }


@router.post("/{position_id}/redeem")
def redeem(
    position_id: int,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    day = get_state(session).current_day
    portfolio = _get_portfolio(session, user, for_update=True)

    # scoped to the caller, and someone else's position reads as missing rather
    # than forbidden, so the endpoint cannot be used to probe which ids exist
    position = session.scalar(
        select(BondPosition).where(
            BondPosition.id == position_id, BondPosition.user_id == user.id
        )
    )
    if position is None:
        raise HTTPException(status_code=404, detail="bond not found")
    if position.status != BondStatus.active.value:
        raise HTTPException(status_code=400, detail=f"bond already {position.status}")

    payout = money(principal(position) * (Decimal("1") - Decimal(str(BOND_EARLY_PENALTY))))
    try:
        credit_cash(session, user.id, payout)
        session.add(
            BondTransaction(
                user_id=user.id,
                position_id=position.id,
                kind=BondKind.redeem.value,
                amount=payout,
                day=day,
            )
        )
        position.status = BondStatus.redeemed.value
        session.commit()
    except Exception:
        session.rollback()
        raise

    session.refresh(portfolio)
    return {
        "position_id": position.id,
        "status": position.status,
        "principal": float(principal(position)),
        "penalty_pct": round(BOND_EARLY_PENALTY * 100, 2),
        "paid_out": float(payout),
        "cash": float(portfolio.cash),
    }


@router.get("/positions")
def positions(
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    day = get_state(session).current_day
    rows = session.scalars(
        select(BondPosition)
        .where(BondPosition.user_id == user.id)
        .order_by(BondPosition.id.desc())
    ).all()

    return {
        "current_day": day,
        "active_principal": float(active_principal(session, user.id)),
        "positions": [
            {
                "position_id": p.id,
                "term_days": p.term_days,
                "quantity": p.quantity,
                "principal": float(principal(p)),
                "coupon_rate": float(p.coupon_rate),
                "bought_day": p.bought_day,
                "maturity_day": p.maturity_day,
                "status": p.status,
                "coupons_received": float(coupons_received(session, p.id)),
                # only meaningful while it is still running
                "days_to_maturity": (
                    max(0, p.maturity_day - day)
                    if p.status == BondStatus.active.value
                    else 0
                ),
            }
            for p in rows
        ],
    }
