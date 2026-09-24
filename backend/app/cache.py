"""Redis cache for the current-prices read path.

Only /market/prices is cached. Portfolios, trades and every write path go
straight to Postgres, which stays the source of truth -- a cache that can
serve a stale balance or swallow a trade is worse than no cache.

The whole module is built around one rule: Redis is an optimisation, never a
dependency. Every call here is wrapped, so with Redis stopped the app keeps
answering from Postgres and simply counts every read as a miss.
"""

import json
import logging
import os

import redis
from sqlalchemy import select

from app.config import LEADERBOARD_CACHE_TTL, PRICE_CACHE_TTL_MULTIPLIER
from app.models import Settings

logger = logging.getLogger(__name__)

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

# ONE aggregate key, not one per athlete. The ticker writes every price in a
# single commit and the endpoint reads every price in a single response, so the
# snapshot is the unit that is actually produced and consumed. Per-athlete keys
# would turn one round trip into N and could serve a torn mix of two ticks.
PRICES_KEY = "market:prices"

# Cache-aside, not write-through like the prices key: the leaderboard has as
# many writers as there are traders, so invalidating on every trade or tick
# would cost more than it saves and a ranking half a minute stale is fine.
LEADERBOARD_KEY = "leaderboard:ranking"

# One client per process, created at import. redis-py's client is a connection
# pool, so this is shared by every request rather than dialled per call.
#
# The timeouts are short on purpose: when Redis is unreachable the read path
# has to fall through to Postgres quickly. A default-length connect timeout
# would turn "cache is down" into "every request hangs", which is the failure
# this design is supposed to rule out.
client = redis.Redis.from_url(
    REDIS_URL,
    socket_connect_timeout=0.25,
    socket_timeout=0.25,
)

# Per-process counters; fine at WEB_CONCURRENCY=1, where one process serves
# every request. With more workers each would report only its own share.
hits = 0
misses = 0
leaderboard_hits = 0
leaderboard_misses = 0


def read_prices() -> bytes | None:
    """The cached snapshot, or None if it is absent or Redis is unreachable.

    Counts the hit or miss here, at the point the outcome is actually decided,
    so a Redis error is recorded as the miss it behaves like.
    """
    global hits, misses
    try:
        body = client.get(PRICES_KEY)
    except redis.RedisError:
        # Cache down is a miss, not an error: the caller falls back to Postgres.
        logger.warning("prices cache read failed; serving from Postgres")
        misses += 1
        return None

    if body is None:
        misses += 1
        return None
    hits += 1
    return body


def price_cache_ttl(session) -> int:
    """Reads the cadence from Settings, the same source the ticker paces itself
    by, so the TTL tracks it rather than a constant that can disagree. It is a
    multiple of the MEAN spacing because tick gaps are exponential and a single
    gap can run well past the mean.
    """
    settings = session.scalar(select(Settings))
    if settings is None:
        # no cadence row yet: the model's defaults are what it will be created with
        day_minutes = Settings.day_length_minutes.default.arg
        ticks = Settings.ticks_per_day.default.arg
    else:
        day_minutes, ticks = settings.day_length_minutes, settings.ticks_per_day

    mean_spacing = (day_minutes * 60) / max(1, ticks)
    return max(1, round(mean_spacing * PRICE_CACHE_TTL_MULTIPLIER))


def write_prices(body: bytes, ttl: int) -> None:
    """Publish a snapshot, with the TTL as its backstop.

    Swallowed on failure by design. Callers reach here only after Postgres has
    already committed, so a Redis problem must not turn a succeeded write into
    a failed request or a dead ticker.
    """
    try:
        client.set(PRICES_KEY, body, ex=ttl)
    except redis.RedisError:
        logger.warning("prices cache write failed; cache left to expire")


def read_leaderboard() -> list | None:
    """The cached ranking, or None if absent or Redis is unreachable."""
    global leaderboard_hits, leaderboard_misses
    try:
        body = client.get(LEADERBOARD_KEY)
    except redis.RedisError:
        logger.warning("leaderboard cache read failed; computing from Postgres")
        leaderboard_misses += 1
        return None

    if body is None:
        leaderboard_misses += 1
        return None
    try:
        rows = json.loads(body)
    except ValueError:
        # unreadable value is a miss, not a crash
        leaderboard_misses += 1
        return None
    leaderboard_hits += 1
    return rows


def write_leaderboard(rows: list) -> None:
    """Publish a ranking. Swallowed on failure -- the caller already has the
    freshly computed answer to serve."""
    try:
        client.set(LEADERBOARD_KEY, json.dumps(rows), ex=LEADERBOARD_CACHE_TTL)
    except redis.RedisError:
        logger.warning("leaderboard cache write failed; left to recompute")


def clear_leaderboard() -> None:
    """Drop the cached ranking so the next read recomputes.

    The only invalidation the leaderboard has: a rename must show at once,
    where a trade can wait for the TTL.
    """
    try:
        client.delete(LEADERBOARD_KEY)
    except redis.RedisError:
        logger.warning("leaderboard cache clear failed; stale until its TTL")


def _rate(h: int, m: int) -> float:
    total = h + m
    return round(h / total, 4) if total else 0.0


def metrics() -> dict:
    """Per-process counters, kept separate per cache: the two have different
    strategies and one hit rate would hide both."""
    return {
        "prices": {"hits": hits, "misses": misses, "hit_rate": _rate(hits, misses)},
        "leaderboard": {
            "hits": leaderboard_hits,
            "misses": leaderboard_misses,
            "hit_rate": _rate(leaderboard_hits, leaderboard_misses),
        },
    }
