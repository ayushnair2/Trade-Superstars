"""Load game logs for any adapter that implements fetch_game_logs.

The NBA and NFL keep bespoke loaders because their sources are bulk frames;
every other sport goes through here.
"""

import statistics
from datetime import date
from decimal import Decimal

from sqlalchemy import delete, select

from app.adapters.base import SportAdapter
from app.db import SessionLocal
from app.models import Athlete, AthleteStat, GameLog


def _upsert_stat(session, athlete_id: int, key: str, value: float, as_of: date) -> None:
    stat = session.scalar(
        select(AthleteStat).where(
            AthleteStat.athlete_id == athlete_id, AthleteStat.stat_key == key
        )
    )
    if stat is None:
        session.add(
            AthleteStat(
                athlete_id=athlete_id,
                stat_key=key,
                value=Decimal(f"{value:.2f}"),
                as_of=as_of,
            )
        )
    else:
        stat.value = Decimal(f"{value:.2f}")
        stat.as_of = as_of


def load_game_logs_for(adapter: SportAdapter) -> list[tuple[str, int]]:
    """Rewrite every athlete's logs for this sport. Idempotent per athlete."""
    today = date.today()
    loaded = []

    with SessionLocal() as session:
        athletes = session.scalars(
            select(Athlete)
            .where(Athlete.sport == adapter.sport)
            .order_by(Athlete.id)
        ).all()

        for athlete in athletes:
            try:
                logs = adapter.fetch_game_logs(athlete.external_ref)
            except Exception:
                # one athlete's feed failing must not abort the sport
                loaded.append((athlete.name, 0))
                continue
            if not logs:
                loaded.append((athlete.name, 0))
                continue

            session.execute(delete(GameLog).where(GameLog.athlete_id == athlete.id))
            scores = []
            for index, log in enumerate(logs):
                scores.append(log.perf_score)
                session.add(
                    GameLog(
                        athlete_id=athlete.id,
                        game_index=index,
                        game_date=log.game_date,
                        pts=Decimal(f"{log.pts:.2f}"),
                        reb=Decimal(f"{log.reb:.2f}"),
                        ast=Decimal(f"{log.ast:.2f}"),
                        perf_score=Decimal(f"{log.perf_score:.2f}"),
                    )
                )

            _upsert_stat(session, athlete.id, "perf_mean", statistics.mean(scores), today)
            spread = statistics.stdev(scores) if len(scores) > 1 else 0.0
            _upsert_stat(session, athlete.id, "perf_std", spread, today)
            loaded.append((athlete.name, len(logs)))

        session.commit()
    return loaded
