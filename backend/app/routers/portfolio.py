"""Trading and portfolio endpoints.

Trades execute at the current market price and do not move it -- the pricing
engine is the only thing that changes prices. The trade itself is made by
app.trading, which the order engine uses too.
"""

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.bonds import active_principal
from app.db import get_session
from app.models import Athlete, Fund, Holding, Side, User
from app.trading import (
    Asset,
    TradeError,
    available_cash,
    execute_trade,
    get_holding,
    get_portfolio,
    latest_fund_price,
    latest_price,
    money,
    resolve_asset,
)

router = APIRouter(prefix="/portfolio", tags=["portfolio"])

def _require_asset(
    session: Session, athlete_id: int | None, fund_id: int | None
) -> Asset:
    """resolve_asset, with its TradeError rendered as a status code."""
    try:
        return resolve_asset(session, athlete_id, fund_id)
    except TradeError as exc:
        status = 404 if "not found" in str(exc) or "no price" in str(exc) else 400
        raise HTTPException(status_code=status, detail=str(exc)) from None


def _holding_response(holding: Holding | None) -> dict:
    if holding is None:
        return {"quantity": 0, "avg_cost": 0.0}
    return {"quantity": holding.quantity, "avg_cost": float(holding.avg_cost)}


@router.post("/buy")
def buy(
    athlete_id: int | None = None,
    fund_id: int | None = None,
    quantity: int = Query(gt=0),
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    asset = _require_asset(session, athlete_id, fund_id)
    # locked before the cash is read, so the guard inside execute_trade cannot
    # go stale under a concurrent trade or an order filling on this tick
    portfolio = get_portfolio(session, user.id, for_update=True)

    try:
        trade, holding = execute_trade(
            session, portfolio, asset, Side.buy, quantity, asset.price
        )
        session.commit()
    except TradeError as exc:
        session.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from None
    except Exception:
        session.rollback()
        raise

    return {
        "cash": float(portfolio.cash),
        "available_cash": float(available_cash(portfolio)),
        "holding": _holding_response(holding),
        "trade_id": trade.id,
    }


@router.post("/sell")
def sell(
    athlete_id: int | None = None,
    fund_id: int | None = None,
    quantity: int = Query(gt=0),
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    asset = _require_asset(session, athlete_id, fund_id)
    # locked before the holding is read, for the same reason as the buy above
    portfolio = get_portfolio(session, user.id, for_update=True)

    try:
        trade, holding = execute_trade(
            session, portfolio, asset, Side.sell, quantity, asset.price
        )
        session.commit()
    except TradeError as exc:
        session.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from None
    except Exception:
        session.rollback()
        raise

    return {
        "cash": float(portfolio.cash),
        "available_cash": float(available_cash(portfolio)),
        "holding": _holding_response(holding),
        "trade_id": trade.id,
    }


@router.get("")
def read_portfolio(
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    portfolio = get_portfolio(session, user.id)
    session.commit()  # persist the row if this was the first read

    holdings = []
    total_market_value = Decimal("0")
    rows = session.scalars(
        select(Holding).where(Holding.user_id == user.id, Holding.quantity > 0)
    ).all()
    for holding in rows:
        if holding.fund_id is not None:
            fund = session.get(Fund, holding.fund_id)
            name = fund.name if fund else "unknown fund"
            price = latest_fund_price(session, holding.fund_id)
        else:
            athlete = session.get(Athlete, holding.athlete_id)
            name = athlete.name if athlete else "unknown athlete"
            price = latest_price(session, holding.athlete_id)
        if price is None:
            continue
        market_value = money(price * holding.quantity)
        total_market_value += market_value
        holdings.append(
            {
                # both ids are always present; the absent one is null, so a
                # client can tell the two kinds apart without guessing
                "asset_type": holding.asset_type,
                "athlete_id": holding.athlete_id,
                "fund_id": holding.fund_id,
                "name": name,
                "quantity": holding.quantity,
                "reserved_quantity": holding.reserved_quantity,
                "avg_cost": float(holding.avg_cost),
                "current_price": float(price),
                "market_value": float(market_value),
                "unrealized_pl": float(
                    money((price - holding.avg_cost) * holding.quantity)
                ),
            }
        )

    holdings.sort(key=lambda h: h["market_value"], reverse=True)
    # bonds are held at face until they mature or are redeemed, so principal is
    # what they are worth to the portfolio today
    bonds = active_principal(session, user.id)
    return {
        "cash": float(portfolio.cash),
        # a reservation earmarks cash, it does not spend it, so total_value is
        # deliberately built from `cash` and is unmoved by placing an order
        "reserved_cash": float(portfolio.reserved_cash),
        "available_cash": float(available_cash(portfolio)),
        "holdings": holdings,
        "bonds": {"active_principal": float(bonds)},
        "total_value": float(money(portfolio.cash + total_market_value + bonds)),
    }
