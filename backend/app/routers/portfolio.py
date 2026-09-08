"""Trading and portfolio endpoints.

Trades execute at the current market price and do not move it -- the pricing
engine is the only thing that changes prices.
"""

from decimal import ROUND_HALF_UP, Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import Athlete, Holding, Portfolio, Price, Side, Trade

router = APIRouter(prefix="/portfolio", tags=["portfolio"])

CENTS = Decimal("0.01")


def _money(value: Decimal) -> Decimal:
    return value.quantize(CENTS, rounding=ROUND_HALF_UP)


def _get_portfolio(session: Session) -> Portfolio:
    portfolio = session.scalar(select(Portfolio).where(Portfolio.id == 1))
    if portfolio is None:
        portfolio = Portfolio(id=1)
        session.add(portfolio)
        session.flush()
    return portfolio


def _latest_price(session: Session, athlete_id: int) -> Decimal | None:
    price = session.scalar(
        select(Price)
        .where(Price.athlete_id == athlete_id)
        .order_by(Price.id.desc())
        .limit(1)
    )
    return price.price if price else None


def _require_athlete_and_price(
    session: Session, athlete_id: int
) -> tuple[Athlete, Decimal]:
    athlete = session.get(Athlete, athlete_id)
    if athlete is None:
        raise HTTPException(status_code=404, detail="athlete not found")
    price = _latest_price(session, athlete_id)
    if price is None:
        raise HTTPException(status_code=404, detail="no price for athlete")
    return athlete, price


def _holding_response(holding: Holding | None) -> dict:
    if holding is None:
        return {"quantity": 0, "avg_cost": 0.0}
    return {"quantity": holding.quantity, "avg_cost": float(holding.avg_cost)}


@router.post("/buy")
def buy(
    athlete_id: int,
    quantity: int = Query(gt=0),
    session: Session = Depends(get_session),
):
    _, price = _require_athlete_and_price(session, athlete_id)
    portfolio = _get_portfolio(session)
    cost = _money(price * quantity)

    if cost > portfolio.cash:
        raise HTTPException(status_code=400, detail="insufficient funds")

    try:
        portfolio.cash = _money(portfolio.cash - cost)
        session.add(
            Trade(
                athlete_id=athlete_id,
                side=Side.buy,
                quantity=quantity,
                price=price,
            )
        )

        holding = session.scalar(
            select(Holding).where(Holding.athlete_id == athlete_id)
        )
        if holding is None:
            holding = Holding(
                athlete_id=athlete_id, quantity=quantity, avg_cost=price
            )
            session.add(holding)
        else:
            total_cost = holding.quantity * holding.avg_cost + quantity * price
            holding.quantity += quantity
            holding.avg_cost = _money(total_cost / holding.quantity)

        session.commit()
    except Exception:
        session.rollback()
        raise

    return {
        "cash": float(portfolio.cash),
        "holding": _holding_response(holding),
    }


@router.post("/sell")
def sell(
    athlete_id: int,
    quantity: int = Query(gt=0),
    session: Session = Depends(get_session),
):
    _, price = _require_athlete_and_price(session, athlete_id)
    portfolio = _get_portfolio(session)

    holding = session.scalar(select(Holding).where(Holding.athlete_id == athlete_id))
    if holding is None or quantity > holding.quantity:
        raise HTTPException(status_code=400, detail="insufficient shares")

    try:
        portfolio.cash = _money(portfolio.cash + _money(price * quantity))
        session.add(
            Trade(
                athlete_id=athlete_id,
                side=Side.sell,
                quantity=quantity,
                price=price,
            )
        )
        # avg_cost is the cost basis of the shares still held, so it doesn't move.
        holding.quantity -= quantity
        session.commit()
    except Exception:
        session.rollback()
        raise

    return {
        "cash": float(portfolio.cash),
        "holding": _holding_response(holding),
    }


@router.get("")
def get_portfolio(session: Session = Depends(get_session)):
    portfolio = _get_portfolio(session)
    session.commit()  # persist the row if this was the first read

    holdings = []
    total_market_value = Decimal("0")
    rows = session.scalars(select(Holding).where(Holding.quantity > 0)).all()
    for holding in rows:
        athlete = session.get(Athlete, holding.athlete_id)
        price = _latest_price(session, holding.athlete_id)
        if price is None:
            continue
        market_value = _money(price * holding.quantity)
        total_market_value += market_value
        holdings.append(
            {
                "athlete_id": holding.athlete_id,
                "name": athlete.name,
                "quantity": holding.quantity,
                "avg_cost": float(holding.avg_cost),
                "current_price": float(price),
                "market_value": float(market_value),
                "unrealized_pl": float(
                    _money((price - holding.avg_cost) * holding.quantity)
                ),
            }
        )

    holdings.sort(key=lambda h: h["market_value"], reverse=True)
    return {
        "cash": float(portfolio.cash),
        "holdings": holdings,
        "total_value": float(_money(portfolio.cash + total_market_value)),
    }
