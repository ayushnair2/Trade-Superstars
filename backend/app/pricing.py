"""Market pricing engine, in two layers.

A game-day advances every athlete one game, recomputes rolling form, and sets
the price target. Price ticks then walk the price toward that stored target
without touching form. The maths is unchanged from the single-step engine --
only the cadence is split.

Every random draw is derived from (seed, athlete_id, step, purpose), so a given
seed reproduces a run exactly and any past step can be re-derived without
replaying the ones before it.
"""

import random
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select

from app.config import (
    FORM_WINDOW,
    MARKET_SEED,
    MOMENTUM,
    OVERREACTION,
    PRICE_FLOOR,
    PRICE_SCALE,
    REACTION_JITTER,
    TETHER,
    TICK_JITTER,
)
from app.models import (
    Athlete,
    AthleteStat,
    GameLog,
    MarketAthleteState,
    MarketState,
    Price,
)


def _rng(seed: int, athlete_id: int, step: int, purpose: str) -> random.Random:
    """Independent, reproducible stream per (athlete, step, purpose)."""
    return random.Random(f"{seed}:{athlete_id}:{step}:{purpose}")


class AthleteStream:
    """An athlete's perf_score over time: real games first, then simulated."""

    def __init__(self, athlete_id: int, mean: float, std: float, games: list[float]):
        self.athlete_id = athlete_id
        self.mean = mean
        self.std = std
        self.games = games

    def perf_at(self, seed: int, step: int) -> float:
        if step < len(self.games):
            return self.games[step]
        return _rng(seed, self.athlete_id, step, "perf").gauss(self.mean, self.std)

    def form_at(self, seed: int, step: int) -> float:
        start = max(0, step - FORM_WINDOW + 1)
        window = [self.perf_at(seed, t) for t in range(start, step + 1)]
        return sum(window) / len(window)

    @property
    def baseline_price(self) -> float:
        return self.mean * PRICE_SCALE


def load_streams(session) -> list[tuple[Athlete, AthleteStream]]:
    streams = []
    for athlete in session.scalars(select(Athlete).order_by(Athlete.id)).all():
        stats = {
            s.stat_key: float(s.value)
            for s in session.scalars(
                select(AthleteStat).where(AthleteStat.athlete_id == athlete.id)
            ).all()
        }
        games = [
            float(g.perf_score)
            for g in session.scalars(
                select(GameLog)
                .where(GameLog.athlete_id == athlete.id)
                .order_by(GameLog.game_index)
            ).all()
        ]
        streams.append(
            (
                athlete,
                AthleteStream(
                    athlete.id,
                    stats.get("perf_mean", 0.0),
                    stats.get("perf_std", 0.0),
                    games,
                ),
            )
        )
    return streams


def get_state(session) -> MarketState:
    state = session.scalar(select(MarketState).where(MarketState.id == 1))
    if state is None:
        state = MarketState(id=1, current_step=0, seed=MARKET_SEED)
        session.add(state)
        session.flush()
    return state


def _latest_price(session, athlete_id: int) -> float | None:
    price = session.scalar(
        select(Price)
        .where(Price.athlete_id == athlete_id)
        .order_by(Price.id.desc())
        .limit(1)
    )
    return float(price.price) if price else None


def init_market(session) -> dict[str, float]:
    """Set every athlete's opening price to their baseline and record it."""
    state = get_state(session)
    state.current_step = 0
    state.current_day = 0

    opening = {}
    now = datetime.now(timezone.utc)
    for athlete, stream in load_streams(session):
        price = max(stream.baseline_price, PRICE_FLOOR)
        session.add(
            Price(
                athlete_id=athlete.id,
                price=Decimal(f"{price:.2f}"),
                recorded_at=now,
            )
        )
        opening[athlete.name] = price
    session.commit()
    return opening


def _athlete_state(session, athlete_id: int) -> MarketAthleteState | None:
    return session.scalar(
        select(MarketAthleteState).where(MarketAthleteState.athlete_id == athlete_id)
    )


def advance_game_day(session) -> dict[str, dict[str, float]]:
    """Play one game per athlete, refresh form, and set the new price target.

    Writes no Price rows -- prices only move on a price tick.
    """
    state = get_state(session)
    day = state.current_day
    seed = state.seed

    results = {}
    for athlete, stream in load_streams(session):
        baseline = stream.baseline_price
        # form_at averages the last FORM_WINDOW game-days of the stream
        gap = stream.form_at(seed, day) - stream.mean

        jitter = _rng(seed, athlete.id, day, "reaction").uniform(
            -REACTION_JITTER, REACTION_JITTER
        )
        reaction = OVERREACTION * (1 + jitter)
        target = baseline + reaction * gap * PRICE_SCALE

        athlete_state = _athlete_state(session, athlete.id)
        if athlete_state is None:
            athlete_state = MarketAthleteState(
                athlete_id=athlete.id,
                baseline_price=Decimal(f"{baseline:.2f}"),
                current_target=Decimal(f"{target:.2f}"),
                last_game_day=day,
            )
            session.add(athlete_state)
        else:
            athlete_state.baseline_price = Decimal(f"{baseline:.2f}")
            athlete_state.current_target = Decimal(f"{target:.2f}")
            athlete_state.last_game_day = day

        results[athlete.name] = {
            "perf": round(stream.perf_at(seed, day), 2),
            "baseline": round(baseline, 2),
            "target": round(target, 2),
        }

    state.current_day = day + 1
    session.commit()
    return results


def advance_price_tick(session, tick_index: int = 0) -> dict[str, float]:
    """Walk every price one step toward its stored target and record it."""
    state = get_state(session)
    state.current_step += 1
    seed = state.seed
    day = state.current_day

    now = datetime.now(timezone.utc)
    prices = {}
    for athlete, stream in load_streams(session):
        athlete_state = _athlete_state(session, athlete.id)
        if athlete_state is None:
            # no game-day has run yet; nothing to move toward
            continue

        baseline = float(athlete_state.baseline_price)
        target = float(athlete_state.current_target)

        prev = _latest_price(session, athlete.id)
        if prev is None:
            prev = baseline

        noise = _rng(seed, athlete.id, day * 1000 + tick_index, "tick").gauss(
            0, TICK_JITTER
        )
        new_price = (
            prev + MOMENTUM * (target - prev) + TETHER * (baseline - prev) + prev * noise
        )
        new_price = max(new_price, PRICE_FLOOR)

        session.add(
            Price(
                athlete_id=athlete.id,
                price=Decimal(f"{new_price:.2f}"),
                recorded_at=now,
            )
        )
        prices[athlete.name] = round(new_price, 2)

    session.commit()
    return prices
