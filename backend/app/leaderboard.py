"""Ranking every trader by what their portfolio is worth.

One query, not a loop per user: the latest athlete price and the latest fund
price are each resolved in a subquery, joined onto holdings, and summed per
user alongside their cash.
"""

from sqlalchemy import Numeric, cast, desc, func, select

from app.config import BOND_FACE
from app.models import (
    BondPosition,
    BondStatus,
    FundPrice,
    Holding,
    Portfolio,
    Price,
    User,
)

# Every portfolio opens on this, so it is the denominator for return_pct.
# Read off the model rather than restated, so the two cannot drift.
STARTING_CASH = float(Portfolio.cash.default.arg)


def ranked_rows(session) -> list[dict]:
    """Every user, best first, ties broken by id. Includes user_id: this is
    the server-side shape, and the endpoint strips it before responding."""
    latest_athlete = (
        select(Price.athlete_id, func.max(Price.id).label("price_id"))
        .group_by(Price.athlete_id)
        .subquery()
    )
    athlete_price = (
        select(latest_athlete.c.athlete_id, Price.price)
        .join(Price, Price.id == latest_athlete.c.price_id)
        .subquery()
    )
    latest_fund = (
        select(FundPrice.fund_id, func.max(FundPrice.id).label("price_id"))
        .group_by(FundPrice.fund_id)
        .subquery()
    )
    fund_price = (
        select(latest_fund.c.fund_id, FundPrice.price)
        .join(FundPrice, FundPrice.id == latest_fund.c.price_id)
        .subquery()
    )

    # a holding names exactly one asset, so coalesce picks whichever price
    # applies and the sum covers athletes and funds in one pass
    unit_price = func.coalesce(athlete_price.c.price, fund_price.c.price, 0)
    holdings_value = (
        select(
            Holding.user_id.label("user_id"),
            func.sum(cast(Holding.quantity, Numeric) * unit_price).label("value"),
        )
        .outerjoin(athlete_price, athlete_price.c.athlete_id == Holding.athlete_id)
        .outerjoin(fund_price, fund_price.c.fund_id == Holding.fund_id)
        .where(Holding.quantity > 0)
        .group_by(Holding.user_id)
        .subquery()
    )

    # bonds are held at face while active, the same value the portfolio shows
    bonds_value = (
        select(
            BondPosition.user_id.label("user_id"),
            func.sum(cast(BondPosition.quantity, Numeric) * BOND_FACE).label("value"),
        )
        .where(BondPosition.status == BondStatus.active.value)
        .group_by(BondPosition.user_id)
        .subquery()
    )

    # a user who has never opened their portfolio has no row yet, but they do
    # have the starting cash, so they rank rather than vanish
    total = (
        func.coalesce(Portfolio.cash, STARTING_CASH)
        + func.coalesce(holdings_value.c.value, 0)
        + func.coalesce(bonds_value.c.value, 0)
    )

    rows = session.execute(
        select(User.id, User.display_name, total.label("total_value"))
        .outerjoin(Portfolio, Portfolio.user_id == User.id)
        .outerjoin(holdings_value, holdings_value.c.user_id == User.id)
        .outerjoin(bonds_value, bonds_value.c.user_id == User.id)
        .order_by(desc("total_value"), User.id)
    ).all()

    return [
        {
            "rank": index,
            "user_id": user_id,
            "display_name": display_name,
            "total_value": round(float(value), 2),
            "return_pct": round((float(value) - STARTING_CASH) / STARTING_CASH * 100, 2),
        }
        for index, (user_id, display_name, value) in enumerate(rows, start=1)
    ]


def public_entry(row: dict) -> dict:
    """The shape a caller may see -- no email, no user id."""
    return {
        "rank": row["rank"],
        "display_name": row["display_name"],
        "total_value": row["total_value"],
        "return_pct": row["return_pct"],
    }
