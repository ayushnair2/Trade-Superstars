"""Standing-order endpoints. Every one is authenticated and user-scoped."""

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.db import get_session
from app.models import Athlete, Fund, Order, OrderStatus, Side, User
from app.orders import cancel_order, place_order
from app.pricing import get_state
from app.trading import TradeError

router = APIRouter(prefix="/orders", tags=["orders"])

# enough to see what happened recently without paging
HISTORY_LIMIT = 25


class PlaceRequest(BaseModel):
    athlete_id: int | None = None
    fund_id: int | None = None
    side: Side
    order_type: str
    trigger_price: Decimal = Field(gt=0)
    quantity: int = Field(gt=0)
    expires_in_days: int | None = Field(default=None, gt=0)


def _name(session: Session, order: Order) -> str:
    if order.fund_id is not None:
        fund = session.get(Fund, order.fund_id)
        return fund.name if fund else "unknown fund"
    athlete = session.get(Athlete, order.athlete_id)
    return athlete.name if athlete else "unknown athlete"


def _order_response(session: Session, order: Order) -> dict:
    return {
        "id": order.id,
        "asset_type": order.asset_type,
        "athlete_id": order.athlete_id,
        "fund_id": order.fund_id,
        "name": _name(session, order),
        "side": order.side.value,
        "order_type": order.order_type,
        "trigger_price": float(order.trigger_price),
        "quantity": order.quantity,
        "reserved_amount": float(order.reserved_amount),
        "status": order.status,
        "created_day": order.created_day,
        "expires_day": order.expires_day,
        "fill_price": float(order.fill_price) if order.fill_price is not None else None,
        "trade_id": order.trade_id,
        "failure_reason": order.failure_reason,
    }


@router.post("")
def create(
    body: PlaceRequest,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    day = get_state(session).current_day
    try:
        order = place_order(
            session,
            user.id,
            athlete_id=body.athlete_id,
            fund_id=body.fund_id,
            side=body.side,
            order_type=body.order_type,
            trigger_price=body.trigger_price,
            quantity=body.quantity,
            current_day=day,
            expires_in_days=body.expires_in_days,
        )
        session.commit()
    except TradeError as exc:
        session.rollback()
        status = 404 if "not found" in str(exc) else 400
        raise HTTPException(status_code=status, detail=str(exc)) from None
    except Exception:
        session.rollback()
        raise

    return _order_response(session, order)


@router.get("")
def list_orders(
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """This user's resting orders, plus what recently became of the others."""
    open_orders = session.scalars(
        select(Order)
        .where(Order.user_id == user.id, Order.status == OrderStatus.open.value)
        .order_by(Order.id.desc())
    ).all()
    history = session.scalars(
        select(Order)
        .where(Order.user_id == user.id, Order.status != OrderStatus.open.value)
        .order_by(Order.id.desc())
        .limit(HISTORY_LIMIT)
    ).all()
    return {
        "open": [_order_response(session, o) for o in open_orders],
        "history": [_order_response(session, o) for o in history],
    }


@router.delete("/{order_id}")
def cancel(
    order_id: int,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    try:
        order = cancel_order(session, user.id, order_id)
        session.commit()
    except LookupError:
        # another user's order is "not found", never "not yours" -- the
        # endpoint must not confirm that an id exists
        session.rollback()
        raise HTTPException(status_code=404, detail="order not found") from None
    except TradeError as exc:
        session.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from None
    except Exception:
        session.rollback()
        raise

    return _order_response(session, order)
