"""League bonds: fixed-term instruments that pay a coupon every game-day.

Cash moves here the same way it moves for trades -- through the portfolio row
-- but the arithmetic is different. A coupon credit runs while a user may be
trading in another thread, so it is applied as an atomic UPDATE rather than a
read in Python followed by a write, which would be exactly the lost update the
trade path takes a row lock to avoid.
"""

import logging
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.config import BOND_EARLY_PENALTY, BOND_FACE, BOND_TERMS
from app.models import BondKind, BondPosition, BondStatus, BondTransaction, Portfolio

logger = logging.getLogger(__name__)

CENTS = Decimal("0.01")


def money(value: Decimal) -> Decimal:
    return Decimal(value).quantize(CENTS, rounding=ROUND_HALF_UP)


def principal(position: BondPosition) -> Decimal:
    return money(Decimal(position.quantity) * Decimal(BOND_FACE))


def terms() -> list[dict]:
    """What is on offer, with the full return for holding to maturity."""
    return [
        {
            "term_days": days,
            "coupon_rate": rate,
            "face": BOND_FACE,
            # coupons accrue once per game-day for the whole term
            "total_return_pct": round(days * rate * 100, 4),
            "early_penalty_pct": round(BOND_EARLY_PENALTY * 100, 2),
        }
        for days, rate in sorted(BOND_TERMS.items())
    ]


def credit_cash(session, user_id: int, amount: Decimal) -> None:
    """Move cash by `amount` without reading it first.

    Read-modify-write in Python would drop a concurrent trade's write; letting
    Postgres do the arithmetic makes the update atomic on its own.
    """
    session.execute(
        update(Portfolio)
        .where(Portfolio.user_id == user_id)
        .values(cash=Portfolio.cash + amount)
    )


def _record(session, position: BondPosition, kind: BondKind, amount: Decimal, day: int) -> bool:
    """Write one ledger row, or report that it already existed.

    ON CONFLICT DO NOTHING against the (position, kind, day) unique constraint
    is what makes a game-day re-runnable: the second attempt inserts nothing
    and returns False, so the caller knows not to move any cash.
    """
    result = session.execute(
        pg_insert(BondTransaction)
        .values(
            user_id=position.user_id,
            position_id=position.id,
            kind=kind.value,
            amount=amount,
            day=day,
        )
        .on_conflict_do_nothing(constraint="uq_bond_txn_position_kind_day")
        .returning(BondTransaction.id)
    ).first()
    return result is not None


def _settle_day(session, day: int, paid: dict[str, int]) -> None:
    """Pay every position whatever it is owed for one game-day."""
    positions = session.scalars(
        select(BondPosition).where(BondPosition.status == BondStatus.active.value)
    ).all()

    for position in positions:
        # a bond bought on day N first accrues on N+1, and last on maturity day
        if day <= position.bought_day or day > position.maturity_day:
            continue

        coupon = money(principal(position) * Decimal(str(position.coupon_rate)))
        if _record(session, position, BondKind.coupon, coupon, day):
            credit_cash(session, position.user_id, coupon)
            paid["coupons"] += 1
        else:
            paid["skipped"] += 1

        if day == position.maturity_day:
            face = principal(position)
            if _record(session, position, BondKind.maturity, face, day):
                credit_cash(session, position.user_id, face)
                position.status = BondStatus.matured.value
                paid["matured"] += 1


def _earliest_unsettled(session, through_day: int) -> int | None:
    """The first game-day any active position is still owed for.

    Per position that is the day after whichever is later: the day it was
    bought, or the last day it was actually paid. Taking the minimum across
    positions gives the day settlement has to restart from.
    """
    last_paid = (
        select(
            BondTransaction.position_id.label("position_id"),
            func.max(BondTransaction.day).label("day"),
        )
        .where(BondTransaction.kind.in_((BondKind.coupon.value, BondKind.maturity.value)))
        .group_by(BondTransaction.position_id)
        .subquery()
    )
    earliest = session.scalar(
        select(
            func.min(
                func.greatest(
                    BondPosition.bought_day, func.coalesce(last_paid.c.day, 0)
                )
            )
        )
        .outerjoin(last_paid, last_paid.c.position_id == BondPosition.id)
        .where(BondPosition.status == BondStatus.active.value)
    )
    if earliest is None:
        return None

    start = int(earliest) + 1
    # A position can never be owed more days than its own term, so however far
    # behind settlement has fallen, this is the furthest back it can matter.
    floor = through_day - max(BOND_TERMS) if BOND_TERMS else through_day
    return max(start, floor)


def process_game_day(session, through_day: int) -> dict[str, int]:
    """Settle every unsettled game-day up to and including `through_day`.

    Not just the one day passed in: if a day's settlement failed, or the
    process was down for it, nobody should silently lose those coupons. The
    ledger's unique constraint makes re-covering a settled day free, so the
    catch-up can start from the earliest day anything is still owed for.
    """
    paid = {"coupons": 0, "matured": 0, "skipped": 0, "days": 0}

    start = _earliest_unsettled(session, through_day)
    if start is None:
        session.commit()
        return paid

    for day in range(start, through_day + 1):
        _settle_day(session, day, paid)
        paid["days"] += 1

    session.commit()
    return paid


def coupons_received(session, position_id: int) -> Decimal:
    total = session.scalar(
        select(func.coalesce(func.sum(BondTransaction.amount), 0)).where(
            BondTransaction.position_id == position_id,
            BondTransaction.kind == BondKind.coupon.value,
        )
    )
    return money(total or 0)


def active_principal(session, user_id: int) -> Decimal:
    """What this user has locked up in bonds, for portfolio and ranking."""
    total = session.scalar(
        select(
            func.coalesce(func.sum(BondPosition.quantity * BOND_FACE), 0)
        ).where(
            BondPosition.user_id == user_id,
            BondPosition.status == BondStatus.active.value,
        )
    )
    return money(total or 0)
