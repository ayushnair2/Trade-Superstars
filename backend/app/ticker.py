"""Two-layer market scheduler.

Slow layer: a game-day advances every athlete one game and sets their price
target. Fast layer: price ticks walk prices toward that target at randomly
spaced moments within the day -- a Poisson process, so the count per day is
itself random and ticks may clump or leave gaps.

The DB work is synchronous, so each call runs in a worker thread with its own
session; the event loop only sleeps.
"""

import asyncio
import logging
import random

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Settings
from app.pricing import advance_game_day, advance_price_tick, get_state

logger = logging.getLogger(__name__)

# Module-level so a second import of the app (uvicorn --reload) reuses this
# reference instead of starting a second scheduler.
_task: asyncio.Task | None = None


def get_settings(session) -> Settings:
    settings = session.scalar(select(Settings))
    if settings is None:
        settings = Settings(id=1)
        session.add(settings)
        session.commit()
    return settings


def _read_cadence() -> tuple[int, float, int, int]:
    """(day, day_length_seconds, ticks_per_day, seed) read fresh each game-day."""
    with SessionLocal() as session:
        settings = get_settings(session)
        state = get_state(session)
        session.commit()
        return (
            state.current_day,
            settings.day_length_minutes * 60,
            settings.ticks_per_day,
            state.seed,
        )


def _run_game_day() -> int:
    with SessionLocal() as session:
        advance_game_day(session)
        return get_state(session).current_day


def _run_price_tick(tick_index: int) -> None:
    with SessionLocal() as session:
        advance_price_tick(session, tick_index)


async def _run() -> None:
    while True:
        try:
            day, day_seconds, ticks_per_day, seed = await asyncio.to_thread(
                _read_cadence
            )
            await asyncio.to_thread(_run_game_day)
            logger.info(
                "game-day %s: %ss long, ~%s ticks", day, day_seconds, ticks_per_day
            )

            # Poisson arrivals: exponential gaps at this rate. The number of
            # ticks in a day is therefore random, not fixed.
            rate = ticks_per_day / day_seconds
            timing = random.Random(f"{seed}:timing:{day}")

            elapsed = 0.0
            tick_index = 0
            while True:
                gap = timing.expovariate(rate)
                if elapsed + gap >= day_seconds:
                    # no more arrivals; sit out the rest of the day
                    await asyncio.sleep(max(0.0, day_seconds - elapsed))
                    break
                await asyncio.sleep(gap)
                elapsed += gap
                await asyncio.to_thread(_run_price_tick, tick_index)
                tick_index += 1
        except asyncio.CancelledError:
            raise
        except Exception:
            # A bad day must never kill the loop -- log it and carry on.
            logger.exception("market scheduler day failed")
            await asyncio.sleep(5)


def start() -> None:
    global _task
    if _task is not None and not _task.done():
        logger.info("scheduler already running; not starting another")
        return
    _task = asyncio.create_task(_run())
    logger.info("market scheduler started")


async def stop() -> None:
    global _task
    if _task is None:
        return
    _task.cancel()
    try:
        await _task
    except asyncio.CancelledError:
        pass
    _task = None
    logger.info("market scheduler stopped")
