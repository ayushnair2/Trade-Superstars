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


def compute_sport_norms(session) -> dict[str, SportNorm]:
    """Recompute each sport's perf_mean distribution from current athletes."""
    norms = {}
    for sport, values in _stat_by_sport(session, "perf_mean").items():
        mean = statistics.mean(values)
        std = statistics.stdev(values) if len(values) > 1 else 0.0
        std = max(std, MIN_STD)

        norm = session.scalar(select(SportNorm).where(SportNorm.sport == sport))
        if norm is None:
            norm = SportNorm(sport=sport)
            session.add(norm)
        norm.mean_perf = round(mean, 4)
        norm.std_perf = round(std, 4)
        norm.athlete_count = len(values)
        norms[sport] = norm

    session.commit()
    return norms


def get_sport_norms(session) -> dict[str, SportNorm]:
    return {n.sport: n for n in session.scalars(select(SportNorm)).all()}


def z_score(perf_mean: float, norm: SportNorm) -> float:
    """Standard deviations above (or below) this sport's average athlete."""
    return (perf_mean - float(norm.mean_perf)) / float(norm.std_perf)


def baseline_price(perf_mean: float, norm: SportNorm) -> float:
    return max(PRICE_FLOOR, PRICE_BASE + z_score(perf_mean, norm) * PRICE_Z_SCALE)


def typical_perf_std(session, sport: str) -> float | None:
    """The sport's average game-to-game spread, for judging volatility."""
    values = _stat_by_sport(session, "perf_std").get(sport)
    return statistics.mean(values) if values else None
