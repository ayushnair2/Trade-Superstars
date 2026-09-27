"""The one place a trade is made.

Both the trading endpoints and the order engine go through execute_trade, so
the guards, the cash movement, the ledger row and the holding update cannot
drift apart between a trade a user clicks and one an order fills.

Nothing here commits or takes a lock. The caller opens the transaction and
holds the portfolio row lock, because what has to be atomic differs: an
endpoint wraps one trade, the order engine wraps a release plus a trade.
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    AssetType,
    Athlete,
    Fund,
    FundPrice,
    Holding,
    Portfolio,
    Price,
    Side,
    Trade,
)

CENTS = Decimal("0.01")


class TradeError(Exception):
    """A trade that cannot be made: not enough available cash or shares.

    Deliberately not an HTTPException. The order engine hits the same wall as
    the endpoints and has to record it on the order rather than return a
    status code, so the rule lives here and each caller renders it.
    """


def money(value: Decimal) -> Decimal:
    return value.quantize(CENTS, rounding=ROUND_HALF_UP)


def get_portfolio(
    session: Session, user_id: int, *, for_update: bool = False
) -> Portfolio:
    """This user's portfolio, opened with the starting cash on first access.

    for_update takes a row lock, held until the transaction commits. A trade
    must take it before reading cash or holdings: sync endpoints run in a
    threadpool and the ticker fills orders from another thread again, so
    without it two writers can read the same balance, both pass their guard,
    and both write -- the second silently overwriting the first. The lock is
    on this user's row alone, so other users' trades are never blocked by it.
    """
    query = select(Portfolio).where(Portfolio.user_id == user_id)
    if for_update:
        query = query.with_for_update()
    portfolio = session.scalar(query)
    if portfolio is None:
        # unlocked read-then-insert: two simultaneous first requests from the
        # same user would race, and unique(user_id) fails the loser with a 500
        # rather than creating a second portfolio. Acceptable at this scale.
        portfolio = Portfolio(user_id=user_id)
        session.add(portfolio)
        session.flush()
    return portfolio


def get_holding(session: Session, user_id: int, asset: "Asset") -> Holding | None:
    """This user's position in one asset. Always filtered by user_id: the
    asset columns alone would match every user's row for it."""
    query = select(Holding).where(Holding.user_id == user_id)
    if asset.is_fund:
        query = query.where(Holding.fund_id == asset.fund_id)
    else:
        query = query.where(Holding.athlete_id == asset.athlete_id)
    return session.scalar(query)


def available_cash(portfolio: Portfolio) -> Decimal:
    """Cash that can actually be spent -- the rest is promised to open buys."""
    return portfolio.cash - portfolio.reserved_cash


def available_quantity(holding: Holding | None) -> int:
    """Shares that can actually be sold -- the rest are promised to open sells."""
    if holding is None:
        return 0
    return holding.quantity - holding.reserved_quantity


def latest_price(session: Session, athlete_id: int) -> Decimal | None:
    price = session.scalar(
        select(Price)
        .where(Price.athlete_id == athlete_id)
        .order_by(Price.id.desc())
        .limit(1)
    )
    return price.price if price else None


def latest_fund_price(session: Session, fund_id: int) -> Decimal | None:
    price = session.scalar(
        select(FundPrice)
        .where(FundPrice.fund_id == fund_id)
        .order_by(FundPrice.id.desc())
        .limit(1)
    )
    return price.price if price else None


@dataclass
class Asset:
    """Whatever is being traded, resolved to one shape so the cash, ledger and
    holding logic below never needs to know which kind it is."""

    type: str
    name: str
    price: Decimal
    athlete_id: int | None = None
    fund_id: int | None = None

    @property
    def is_fund(self) -> bool:
        return self.type == AssetType.fund.value


def resolve_asset(
    session: Session, athlete_id: int | None, fund_id: int | None
) -> Asset:
    """Resolve exactly one of athlete_id/fund_id to a priced asset.

    Raises TradeError rather than HTTPException so the order engine can use it
    too; the routers turn it into a 400/404.
    """
    if (athlete_id is None) == (fund_id is None):
        raise TradeError("pass exactly one of athlete_id or fund_id")

    if fund_id is not None:
        fund = session.get(Fund, fund_id)
        if fund is None:
            raise TradeError("fund not found")
        price = latest_fund_price(session, fund_id)
        if price is None:
            raise TradeError("no price for fund")
        return Asset(AssetType.fund.value, fund.name, price, fund_id=fund_id)

    athlete = session.get(Athlete, athlete_id)
    if athlete is None:
        raise TradeError("athlete not found")
    price = latest_price(session, athlete_id)
    if price is None:
        raise TradeError("no price for athlete")
    return Asset(AssetType.athlete.value, athlete.name, price, athlete_id=athlete_id)


def execute_trade(
    session: Session,
    portfolio: Portfolio,
    asset: Asset,
    side: Side,
    quantity: int,
    price: Decimal,
) -> tuple[Trade, Holding]:
    """Move the cash, write the ledger row, update the holding. No commit.

    `portfolio` must already be locked by the caller. Every guard runs before
    the first write, so a TradeError leaves the session exactly as it was and
    the caller can record the failure in the same transaction.
    """
    holding = get_holding(session, portfolio.user_id, asset)

    if side is Side.buy:
        cost = money(price * quantity)
        if cost > available_cash(portfolio):
            raise TradeError("insufficient funds")
    else:
        if quantity > available_quantity(holding):
            raise TradeError("insufficient shares")

    trade = Trade(
        user_id=portfolio.user_id,
        asset_type=asset.type,
        athlete_id=asset.athlete_id,
        fund_id=asset.fund_id,
        side=side,
        quantity=quantity,
        price=price,
    )
    session.add(trade)

    if side is Side.buy:
        portfolio.cash = money(portfolio.cash - cost)
        if holding is None:
            holding = Holding(
                user_id=portfolio.user_id,
                asset_type=asset.type,
                athlete_id=asset.athlete_id,
                fund_id=asset.fund_id,
                quantity=quantity,
                avg_cost=price,
            )
            session.add(holding)
        else:
            total_cost = holding.quantity * holding.avg_cost + quantity * price
            holding.quantity += quantity
            holding.avg_cost = money(total_cost / holding.quantity)
    else:
        portfolio.cash = money(portfolio.cash + money(price * quantity))
        # avg_cost is the cost basis of the shares still held, so it doesn't move.
        holding.quantity -= quantity

    return trade, holding
