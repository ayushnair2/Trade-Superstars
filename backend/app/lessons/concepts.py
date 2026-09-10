"""Which lesson to teach for a given trade."""

from decimal import Decimal
from enum import StrEnum

from sqlalchemy import func, select

from app.models import Athlete, AthleteStat, Holding, Price, Side, Trade
from app.norms import VOLATILITY_RATIO, typical_perf_std


class Concept(StrEnum):
    VOLATILITY = "VOLATILITY"
    STABILITY = "STABILITY"
    TAKE_GAINS = "TAKE_GAINS"
    CUT_LOSSES = "CUT_LOSSES"
    CHASING = "CHASING"
    BUY_LOW = "BUY_LOW"
    WELCOME = "WELCOME"
    DIVERSIFICATION = "DIVERSIFICATION"


# Concepts about the market in general, not about one athlete.
GLOBAL_CONCEPTS = {Concept.WELCOME, Concept.DIVERSIFICATION}

# How many recent prices count as "lately" when judging a buy.
RECENT_PRICE_WINDOW = 12
# Percent move over that window that counts as notable.
NOTABLE_MOVE_PCT = Decimal("5")
# Holding this many different athletes makes diversification the lesson.
DIVERSIFIED_HOLDINGS = 5


def _recent_move_pct(session, athlete_id: int, price: Decimal) -> Decimal | None:
    """Percent change from the oldest price in the recent window to `price`."""
    rows = session.scalars(
        select(Price.price)
        .where(Price.athlete_id == athlete_id)
        .order_by(Price.id.desc())
        .limit(RECENT_PRICE_WINDOW)
    ).all()
    if len(rows) < 2:
        return None
    oldest = rows[-1]
    if oldest == 0:
        return None
    return (price - oldest) / oldest * 100


def _perf_std(session, athlete_id: int) -> Decimal | None:
    return session.scalar(
        select(AthleteStat.value).where(
            AthleteStat.athlete_id == athlete_id, AthleteStat.stat_key == "perf_std"
        )
    )


def _distinct_holdings(session) -> int:
    return session.scalar(
        select(func.count()).select_from(Holding).where(Holding.quantity > 0)
    )


def pick_concept(session, trade: Trade) -> Concept:
    trade_count = session.scalar(
        select(func.count()).select_from(Trade).where(Trade.id <= trade.id)
    )
    if trade_count <= 1:
        return Concept.WELCOME

    if trade.side is Side.sell:
        holding = session.scalar(
            select(Holding).where(Holding.athlete_id == trade.athlete_id)
        )
        # avg_cost is untouched by a sell, so it is still the cost basis sold against.
        if holding is not None:
            gain = trade.price - holding.avg_cost
            if gain > 0:
                return Concept.TAKE_GAINS
            if gain < 0:
                return Concept.CUT_LOSSES
        # broke exactly even, or the holding is gone -- fall through to the
        # athlete's own character below

    elif _distinct_holdings(session) >= DIVERSIFIED_HOLDINGS:
        return Concept.DIVERSIFICATION

    else:
        move = _recent_move_pct(session, trade.athlete_id, trade.price)
        if move is not None:
            if move >= NOTABLE_MOVE_PCT:
                return Concept.CHASING
            if move <= -NOTABLE_MOVE_PCT:
                return Concept.BUY_LOW

    # Volatility is judged against the athlete's own sport, so a swingy NBA
    # guard and a swingy NFL receiver both read as volatile on their own terms.
    std = _perf_std(session, trade.athlete_id)
    athlete = session.get(Athlete, trade.athlete_id)
    typical = typical_perf_std(session, athlete.sport) if athlete else None
    if std is not None and typical and float(std) > typical * VOLATILITY_RATIO:
        return Concept.VOLATILITY
    return Concept.STABILITY


def cache_key(concept: Concept, athlete_id: int) -> str:
    if concept in GLOBAL_CONCEPTS:
        return str(concept)
    return f"{concept}:{athlete_id}"
