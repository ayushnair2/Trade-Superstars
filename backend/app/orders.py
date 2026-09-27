"""Standing orders: placement, the reservation they hold, and the fill engine.

A resting order is a promise the user has already made, so the cash or shares
behind it are reserved the moment it is placed. Nothing else may spend them --
that is what stops an account from promising the same $1,000 to three orders
and a manual trade.
"""

import logging
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import ORDER_EXPIRY_DAYS, ORDER_MAX_EXPIRY_DAYS
from app.models import (
    Order,
    OrderStatus,
    OrderType,
    Portfolio,
    Side,
)
from app.trading import (
    Asset,
    TradeError,
    available_cash,
    available_quantity,
    execute_trade,
    get_holding,
    get_portfolio,
    money,
    resolve_asset,
)

logger = logging.getLogger(__name__)


def triggers(order_type: str, side: Side, price: Decimal, trigger: Decimal) -> bool:
    """Has `price` crossed this order's trigger?

    A limit waits for a better price than the one showing, a stop for a worse
    one, which flips the comparison between the two -- and the side flips it
    again. All four cases, in one place, so they cannot disagree.
    """
    if order_type == OrderType.limit.value:
        return price <= trigger if side is Side.buy else price >= trigger
    return price >= trigger if side is Side.buy else price <= trigger


def _expiry_day(current_day: int, expires_in_days: int | None) -> int:
    days = ORDER_EXPIRY_DAYS if expires_in_days is None else expires_in_days
    if days < 1 or days > ORDER_MAX_EXPIRY_DAYS:
        raise TradeError(f"expires_in_days must be between 1 and {ORDER_MAX_EXPIRY_DAYS}")
    return current_day + days


def place_order(
    session: Session,
    user_id: int,
    *,
    athlete_id: int | None,
    fund_id: int | None,
    side: Side,
    order_type: str,
    trigger_price: Decimal,
    quantity: int,
    current_day: int,
    expires_in_days: int | None = None,
) -> Order:
    """Reserve what the order will need, then record it. No commit.

    The reservation is the point: a buy holds back quantity * trigger_price of
    cash and a sell holds back the shares, both checked against what is
    available rather than the raw balance, so orders and manual trades draw
    down the same pool.
    """
    if order_type not in (OrderType.limit.value, OrderType.stop.value):
        raise TradeError("order_type must be 'limit' or 'stop'")
    if quantity <= 0:
        raise TradeError("quantity must be positive")
    if trigger_price <= 0:
        raise TradeError("trigger_price must be positive")

    asset = resolve_asset(session, athlete_id, fund_id)
    expires_day = _expiry_day(current_day, expires_in_days)

    # locked before anything is reserved, so two orders placed at once cannot
    # both measure themselves against the same untouched balance
    portfolio = get_portfolio(session, user_id, for_update=True)

    order = Order(
        user_id=user_id,
        asset_type=asset.type,
        athlete_id=asset.athlete_id,
        fund_id=asset.fund_id,
        side=side,
        order_type=order_type,
        trigger_price=trigger_price,
        quantity=quantity,
        status=OrderStatus.open.value,
        created_day=current_day,
        expires_day=expires_day,
    )

    if side is Side.buy:
        reserved = money(trigger_price * quantity)
        if reserved > available_cash(portfolio):
            raise TradeError("insufficient funds")
        portfolio.reserved_cash = money(portfolio.reserved_cash + reserved)
        order.reserved_amount = reserved
    else:
        holding = get_holding(session, user_id, asset)
        if quantity > available_quantity(holding):
            raise TradeError("insufficient shares")
        holding.reserved_quantity += quantity
        # a sell reserves shares, not cash; the column stays zero
        order.reserved_amount = Decimal("0")

    session.add(order)
    return order


def release(session: Session, order: Order, portfolio: Portfolio) -> None:
    """Give back whatever the order was holding. No commit.

    Called on every way out of `open` -- cancel, expiry, and the fill itself,
    which releases first and then spends from the freed balance.
    """
    if order.side is Side.buy:
        portfolio.reserved_cash = money(portfolio.reserved_cash - order.reserved_amount)
    else:
        holding = get_holding(session, order.user_id, _order_asset(order))
        if holding is not None:
            holding.reserved_quantity -= order.quantity


def _order_asset(order: Order, price: Decimal = Decimal("0")) -> Asset:
    """The order's asset in the shape the trading core expects.

    Built from the order's own columns rather than re-read, so a fill prices
    at the tick that triggered it instead of whatever is latest by then.
    """
    return Asset(
        type=order.asset_type,
        name="",
        price=price,
        athlete_id=order.athlete_id,
        fund_id=order.fund_id,
    )


def fill_order(session: Session, order_id: int, price: Decimal) -> str:
    """Fill one triggered order at `price`, in its own transaction.

    Re-reads the order under the portfolio lock: by the time we get here it may
    have been cancelled, expired, or already filled by an overlapping tick.
    """
    try:
        order = session.get(Order, order_id)
        if order is None or order.status != OrderStatus.open.value:
            session.rollback()
            return "skipped"

        portfolio = get_portfolio(session, order.user_id, for_update=True)
        session.refresh(order)
        if order.status != OrderStatus.open.value:
            session.rollback()
            return "skipped"

        # released first, so the reservation is spendable by its own fill --
        # and so a stop that gapped past its trigger can reach for whatever
        # else is available to cover the difference
        release(session, order, portfolio)

        try:
            trade, _ = execute_trade(
                session, portfolio, _order_asset(order, price),
                order.side, order.quantity, price,
            )
            session.flush()
            order.status = OrderStatus.filled.value
            order.fill_price = price
            order.trade_id = trade.id
            outcome = "filled"
        except TradeError as exc:
            # every guard runs before the first write, so nothing of the trade
            # is half-applied here; the release above stands and the order is
            # closed out rather than left resting on money it cannot use
            order.status = OrderStatus.failed.value
            order.failure_reason = str(exc)
            outcome = "failed"
            logger.warning(
                "order %s (%s %s x%s) could not fill at %s: %s",
                order.id, order.order_type, order.side.value, order.quantity,
                price, exc,
            )

        session.commit()
        return outcome
    except Exception:
        session.rollback()
        raise


def fill_triggered(
    session: Session,
    athlete_prices: dict[int, Decimal],
    fund_prices: dict[int, Decimal],
) -> dict[str, int]:
    """Fill every open order the tick's new prices have triggered.

    Runs after the tick has committed, never inside it: a fill takes a user's
    portfolio lock, and holding those across the price write would let one
    slow trader block the market. Each order is filled in its own transaction
    and one failure is logged and stepped over -- an order that cannot fill
    must not cost the other orders their tick, or the tick its prices.
    """
    if not athlete_prices and not fund_prices:
        return {}

    open_orders = session.scalars(
        select(Order).where(Order.status == OrderStatus.open.value)
    ).all()

    # (id, price) captured before any fill, so the list cannot shift underneath
    # us as the transactions below commit
    hits = []
    for order in open_orders:
        if order.fund_id is not None:
            price = fund_prices.get(order.fund_id)
        else:
            price = athlete_prices.get(order.athlete_id)
        if price is None:
            continue  # this tick did not move the thing the order watches
        if triggers(order.order_type, order.side, price, order.trigger_price):
            hits.append((order.id, price))
    session.rollback()  # release the read transaction before taking row locks

    counts: dict[str, int] = {}
    for order_id, price in hits:
        try:
            outcome = fill_order(session, order_id, price)
        except Exception:
            logger.exception("order %s failed to fill; continuing", order_id)
            outcome = "error"
        counts[outcome] = counts.get(outcome, 0) + 1
    return counts


def expire_due(session: Session, current_day: int) -> int:
    """Expire orders whose day has come, releasing each reservation.

    One transaction per order, for the same reason the fill loop uses one:
    each needs that user's portfolio lock and no user should wait on another.
    """
    due = session.scalars(
        select(Order.id).where(
            Order.status == OrderStatus.open.value,
            Order.expires_day <= current_day,
        )
    ).all()
    session.rollback()

    expired = 0
    for order_id in due:
        try:
            order = session.get(Order, order_id)
            if order is None or order.status != OrderStatus.open.value:
                session.rollback()
                continue
            portfolio = get_portfolio(session, order.user_id, for_update=True)
            session.refresh(order)
            if order.status != OrderStatus.open.value:
                session.rollback()
                continue
            release(session, order, portfolio)
            order.status = OrderStatus.expired.value
            session.commit()
            expired += 1
        except Exception:
            session.rollback()
            logger.exception("could not expire order %s; continuing", order_id)
    return expired


def cancel_order(session: Session, user_id: int, order_id: int) -> Order:
    """Cancel one open order and release its reservation. No commit.

    Scoped by user_id: another user's order is not found rather than not
    cancellable, so the endpoint cannot be used to probe for their order ids.
    """
    order = session.scalar(
        select(Order).where(Order.id == order_id, Order.user_id == user_id)
    )
    if order is None:
        raise LookupError("order not found")
    if order.status != OrderStatus.open.value:
        raise TradeError(f"order is {order.status}, not open")

    portfolio = get_portfolio(session, user_id, for_update=True)
    session.refresh(order)
    if order.status != OrderStatus.open.value:
        raise TradeError(f"order is {order.status}, not open")

    release(session, order, portfolio)
    order.status = OrderStatus.cancelled.value
    return order
