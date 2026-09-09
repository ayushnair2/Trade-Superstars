"""Background market ticker.

advance_market is synchronous and hits the DB, so each tick runs in a worker
thread with its own session -- never sharing one across ticks, and never
blocking the event loop.
"""

import asyncio
import logging

from app.config import TICK_INTERVAL_SECONDS
from app.db import SessionLocal
from app.pricing import advance_market, get_state

logger = logging.getLogger(__name__)

# Module-level so a second import of the app (uvicorn --reload) reuses this
# reference instead of starting a second ticker.
_task: asyncio.Task | None = None


def _tick_once() -> int:
    with SessionLocal() as session:
        advance_market(session)
        return get_state(session).current_step


async def _run() -> None:
    while True:
        await asyncio.sleep(TICK_INTERVAL_SECONDS)
        try:
            step = await asyncio.to_thread(_tick_once)
            logger.info("market advanced to step %s", step)
        except asyncio.CancelledError:
            raise
        except Exception:
            # A bad tick must never kill the loop -- log it and keep ticking.
            logger.exception("market tick failed")


def start() -> None:
    global _task
    if _task is not None and not _task.done():
        logger.info("ticker already running; not starting another")
        return
    _task = asyncio.create_task(_run())
    logger.info("ticker started (every %ss)", TICK_INTERVAL_SECONDS)


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
    logger.info("ticker stopped")
