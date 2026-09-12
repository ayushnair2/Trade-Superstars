"""Per-sport normalization.

An athlete's price comes from how far their perf_mean sits from their own
sport's average, measured in standard deviations. That keeps a star in one
sport priced like a star in another, whatever the raw stat scales are.
"""

import statistics

from sqlalchemy import select

from app.config import PRICE_BASE, PRICE_FLOOR, PRICE_Z_SCALE
from app.models import Athlete, AthleteStat, SportNorm

# Guards against a divide-by-zero when a sport has one athlete, or all of them
# happen to share a perf_mean.
MIN_STD = 0.5
# perf_std above this multiple of the sport's typical spread counts as volatile.
VOLATILITY_RATIO = 1.0

# Which stat sets a sport's price LEVEL. Everything defaults to on-field
# production; football uses market value because its free per-game data is
# attacking-only and would price elite defenders and keepers at the floor.
DEFAULT_ANCHOR = "perf_mean"
ANCHOR_STATS = {"FUT": "market_value"}


def _stat_by_sport(session, stat_key: str) -> dict[str, list[float]]:
    rows = session.execute(
        select(Athlete.sport, AthleteStat.value)
        .join(AthleteStat, AthleteStat.athlete_id == Athlete.id)
        .where(AthleteStat.stat_key == stat_key)
    ).all()
    grouped: dict[str, list[float]] = {}
    for sport, value in rows:
        grouped.setdefault(sport, []).append(float(value))
    return grouped


def _mean_std(values: list[float]) -> tuple[float, float]:
    mean = statistics.mean(values)
    std = statistics.stdev(values) if len(values) > 1 else 0.0
    return mean, max(std, MIN_STD)


def compute_sport_norms(session) -> dict[str, SportNorm]:
    """Recompute each sport's production and anchor distributions."""
    perf = _stat_by_sport(session, "perf_mean")
    anchors = {
        stat: _stat_by_sport(session, stat) for stat in set(ANCHOR_STATS.values())
    }

    norms = {}
    # a sport counts if it has either distribution: football players selected by
    # value are priceable before a single game log lands
    sports = set(perf) | {s for grouped in anchors.values() for s in grouped}
    for sport in sports:
        perf_values = perf.get(sport) or [0.0]
        mean_perf, std_perf = _mean_std(perf_values)

        anchor_stat = ANCHOR_STATS.get(sport, DEFAULT_ANCHOR)
        anchor_values = (
            perf_values
            if anchor_stat == DEFAULT_ANCHOR
            else anchors.get(anchor_stat, {}).get(sport)
        )
        if not anchor_values:
            # configured anchor never got written; fall back so the sport still prices
            anchor_stat, anchor_values = DEFAULT_ANCHOR, perf_values
        mean_anchor, std_anchor = _mean_std(anchor_values)

        norm = session.scalar(select(SportNorm).where(SportNorm.sport == sport))
        if norm is None:
            norm = SportNorm(sport=sport)
            session.add(norm)
        norm.mean_perf = round(mean_perf, 4)
        norm.std_perf = round(std_perf, 4)
        norm.anchor_stat = anchor_stat
        norm.mean_anchor = round(mean_anchor, 4)
        norm.std_anchor = round(std_anchor, 4)
        norm.athlete_count = len(anchor_values)
        norms[sport] = norm

    session.commit()
    return norms


def get_sport_norms(session) -> dict[str, SportNorm]:
    return {n.sport: n for n in session.scalars(select(SportNorm)).all()}


def z_score(perf_mean: float, norm: SportNorm) -> float:
    """Standard deviations above (or below) this sport's average athlete."""
    return (perf_mean - float(norm.mean_perf)) / float(norm.std_perf)


def anchor_z(anchor_value: float, norm: SportNorm) -> float:
    """Where this athlete sits in whatever sets their sport's price level."""
    return (anchor_value - float(norm.mean_anchor)) / float(norm.std_anchor)


def baseline_price(anchor_value: float, norm: SportNorm) -> float:
    """Price level from the sport's anchor stat -- production, or market value."""
    return max(PRICE_FLOOR, PRICE_BASE + anchor_z(anchor_value, norm) * PRICE_Z_SCALE)


def typical_perf_std(session, sport: str) -> float | None:
    """The sport's average game-to-game spread, for judging volatility."""
    values = _stat_by_sport(session, "perf_std").get(sport)
    return statistics.mean(values) if values else None
