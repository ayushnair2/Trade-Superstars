"""Index funds: fixed baskets of athletes priced as a single asset.

Membership is chosen once at seed from three global rules, then fixed -- a
fund the market can reshuffle is not an index. Every rule compares athletes
across sports, so each is expressed in units that survive the comparison:
volatility and form are measured against the athlete's own sport, never in raw
stat points, where an NHL goal count and an NFL yardage total mean nothing to
each other.
"""

import statistics
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import func, select

from app.config import (
    FORM_WINDOW,
    FUND_MIN_GAMES,
    FUND_SIZE,
    FUND_WEIGHT,
    SPARK_WINDOW,
)
from app.models import Athlete, AthleteStat, Fund, FundMember, FundPrice, GameLog, Price
from app.norms import baseline_price, get_sport_norms, typical_perf_std

FUND_SPECS = [
    {
        "code": "CONSISTENCY",
        "name": "Consistency Index",
        "description": (
            "The ten steadiest performers in the market, measured against how "
            "much their own sport normally swings."
        ),
        "rule": "lowest_volatility",
    },
    {
        "code": "MOMENTUM",
        "name": "Momentum Index",
        "description": (
            "The ten players most above their own recent average -- form "
            "running hot, for better or worse."
        ),
        "rule": "highest_form",
    },
    {
        "code": "BLUECHIP",
        "name": "Blue Chip Index",
        "description": "The ten most valuable players in the market by baseline price.",
        "rule": "highest_baseline",
    },
]


def _recent_scores(session, limit: int) -> dict[int, list[float]]:
    """Each athlete's last `limit` game scores, newest first.

    One window-function query rather than a query per athlete: the fund rules
    run over every athlete in the market.
    """
    rank = (
        func.row_number()
        .over(partition_by=GameLog.athlete_id, order_by=GameLog.game_index.desc())
        .label("rank")
    )
    ranked = select(GameLog.athlete_id, GameLog.perf_score, rank).subquery()
    rows = session.execute(
        select(ranked.c.athlete_id, ranked.c.perf_score).where(ranked.c.rank <= limit)
    ).all()

    scores: dict[int, list[float]] = {}
    for athlete_id, score in rows:
        scores.setdefault(athlete_id, []).append(float(score))
    return scores


def candidates(session) -> list[dict]:
    """Every tradeable athlete, with the three measures the fund rules need."""
    norms = get_sport_norms(session)
    typical_vol = {
        sport: typical_perf_std(session, sport) for sport in norms
    }
    recent = _recent_scores(session, FORM_WINDOW)
    games = dict(
        session.execute(
            select(GameLog.athlete_id, func.count()).group_by(GameLog.athlete_id)
        ).all()
    )

    stats_by_athlete: dict[int, dict[str, float]] = {}
    for athlete_id, key, value in session.execute(
        select(AthleteStat.athlete_id, AthleteStat.stat_key, AthleteStat.value)
    ).all():
        stats_by_athlete.setdefault(athlete_id, {})[key] = float(value)

    out = []
    for athlete in session.scalars(
        select(Athlete).where(Athlete.retired_at.is_(None))
    ).all():
        norm = norms.get(athlete.sport)
        if norm is None:
            continue
        stats = stats_by_athlete.get(athlete.id, {})
        perf_mean = stats.get("perf_mean", 0.0)
        perf_std = stats.get("perf_std", 0.0)
        anchor = stats.get(norm.anchor_stat, float(norm.mean_anchor))

        # volatility relative to what this sport normally does
        typical = typical_vol.get(athlete.sport) or 0.0
        vol_ratio = perf_std / typical if typical > 0 else None

        # Recent form against the athlete's own mean, scaled by their own
        # spread -- "how unusual is this run for them". Scaling by the sport's
        # std_perf instead let MLB sweep the fund: that figure sits on the
        # MIN_STD floor of 0.5 for baseball, which inflates every MLB gap.
        window = recent.get(athlete.id, [])
        form_gap = None
        if window and perf_std > 0:
            form_gap = (statistics.mean(window) - perf_mean) / perf_std

        out.append(
            {
                "athlete": athlete,
                "sport": athlete.sport,
                "games": games.get(athlete.id, 0),
                "perf_mean": perf_mean,
                "perf_std": perf_std,
                "vol_ratio": vol_ratio,
                "form_gap": form_gap,
                "baseline": baseline_price(anchor, norm),
            }
        )
    return out


def _pick(rule: str, rows: list[dict]) -> list[dict]:
    """The FUND_SIZE athletes this rule selects, best first."""
    if rule == "lowest_volatility":
        # perf_std of 0 means too few games to have a spread, not steadiness
        eligible = [
            r
            for r in rows
            if r["games"] >= FUND_MIN_GAMES and r["vol_ratio"] and r["perf_std"] > 0
        ]
        return sorted(eligible, key=lambda r: r["vol_ratio"])[:FUND_SIZE]

    if rule == "highest_form":
        eligible = [
            r for r in rows if r["games"] >= FUND_MIN_GAMES and r["form_gap"] is not None
        ]
        return sorted(eligible, key=lambda r: -r["form_gap"])[:FUND_SIZE]

    if rule == "highest_baseline":
        return sorted(rows, key=lambda r: -r["baseline"])[:FUND_SIZE]

    raise ValueError(f"unknown fund rule: {rule}")


def seed_funds(session) -> dict[str, list[dict]]:
    """Create the funds and their membership. Idempotent.

    Membership is left alone once a fund has it: an index whose holdings move
    under the people tracking it is not an index. Re-selection will be an
    explicit rebalance, not a side effect of re-seeding.
    """
    rows = candidates(session)

    selected = {}
    for spec in FUND_SPECS:
        fund = session.scalar(select(Fund).where(Fund.code == spec["code"]))
        if fund is None:
            fund = Fund(
                code=spec["code"], name=spec["name"], description=spec["description"]
            )
            session.add(fund)
            session.flush()

        existing = session.scalars(
            select(FundMember).where(FundMember.fund_id == fund.id)
        ).all()
        if existing:
            selected[spec["code"]] = []  # already populated; nothing to report
            continue

        picks = _pick(spec["rule"], rows)
        for pick in picks:
            session.add(
                FundMember(
                    fund_id=fund.id,
                    athlete_id=pick["athlete"].id,
                    weight=Decimal(f"{FUND_WEIGHT:.6f}"),
                )
            )
        selected[spec["code"]] = picks

    session.commit()
    return selected


def _latest_athlete_prices(session) -> dict[int, float]:
    """Each athlete's newest price, in one window-function query."""
    rank = (
        func.row_number()
        .over(partition_by=Price.athlete_id, order_by=Price.id.desc())
        .label("rank")
    )
    ranked = select(Price.athlete_id, Price.price, rank).subquery()
    return {
        athlete_id: float(price)
        for athlete_id, price in session.execute(
            select(ranked.c.athlete_id, ranked.c.price).where(ranked.c.rank == 1)
        ).all()
    }


def price_funds(session, priced: dict[int, float] | None = None) -> dict[str, float]:
    """Write one price row per fund: the weighted sum of its members' prices.

    `priced` carries the prices just written by this tick, so a fund tracks the
    same tick its members moved on rather than the one before it.
    """
    latest = _latest_athlete_prices(session)
    if priced:
        latest.update(priced)

    now = datetime.now(timezone.utc)
    out = {}
    for fund in session.scalars(select(Fund).order_by(Fund.id)).all():
        members = session.scalars(
            select(FundMember).where(FundMember.fund_id == fund.id)
        ).all()
        # a member with no price yet would silently drag the basket down
        known = [m for m in members if m.athlete_id in latest]
        if not known:
            continue

        value = sum(float(m.weight) * latest[m.athlete_id] for m in known)
        session.add(
            FundPrice(fund_id=fund.id, price=Decimal(f"{value:.2f}"), recorded_at=now)
        )
        out[fund.code] = round(value, 2)

    session.commit()
    return out


def _recent_fund_prices(session) -> dict[int, list[float]]:
    """Last SPARK_WINDOW+1 prices per fund, oldest->newest.

    Same shape as the athlete sparkline query: the extra row is the baseline
    that change_pct is measured against.
    """
    rank = (
        func.row_number()
        .over(partition_by=FundPrice.fund_id, order_by=FundPrice.id.desc())
        .label("rank")
    )
    ranked = select(FundPrice.fund_id, FundPrice.price, FundPrice.id, rank).subquery()
    rows = session.execute(
        select(ranked.c.fund_id, ranked.c.price)
        .where(ranked.c.rank <= SPARK_WINDOW + 1)
        .order_by(ranked.c.fund_id, ranked.c.id)
    ).all()

    series: dict[int, list[float]] = {}
    for fund_id, price in rows:
        series.setdefault(fund_id, []).append(float(price))
    return series


def fund_rows(session) -> list[dict]:
    """Every fund as the market sees it: price, change and sparkline."""
    series = _recent_fund_prices(session)
    counts = dict(
        session.execute(
            select(FundMember.fund_id, func.count()).group_by(FundMember.fund_id)
        ).all()
    )

    rows = []
    for fund in session.scalars(select(Fund).order_by(Fund.id)).all():
        prices = series.get(fund.id, [])
        spark = prices[-SPARK_WINDOW:]
        change = None
        if prices and prices[0] != 0:
            change = round((prices[-1] - prices[0]) / prices[0] * 100, 1)
        rows.append(
            {
                "fund_id": fund.id,
                "code": fund.code,
                "name": fund.name,
                "description": fund.description,
                # a count here; /funds/{code} carries the list itself
                "member_count": counts.get(fund.id, 0),
                "price": spark[-1] if spark else None,
                "change_pct": change,
                "spark": spark,
            }
        )
    return rows
