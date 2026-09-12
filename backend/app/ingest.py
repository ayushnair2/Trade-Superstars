"""Ingest athletes from a sport adapter into the DB. Run: python -m app.ingest

Idempotent: athletes match on (external_ref, sport), stats on (athlete_id,
stat_key), so re-running updates in place rather than inserting duplicates.
"""

from datetime import date
from decimal import Decimal

from sqlalchemy import delete, func, select

from app.adapters.base import SportAdapter
from app.adapters.nba import NBAAdapter
from app.db import SessionLocal
from app.models import (
    Athlete,
    AthleteStat,
    GameLog,
    Holding,
    MarketAthleteState,
    Price,
    Trade,
)


def ingest(adapter: SportAdapter) -> list[str]:
    """Write this adapter's athletes and stats. Returns the refs it wrote."""
    today = date.today()
    athletes = adapter.fetch_athletes()

    with SessionLocal() as session:
        for data in athletes:
            athlete = session.scalar(
                select(Athlete).where(
                    Athlete.external_ref == data.external_ref,
                    Athlete.sport == adapter.sport,
                )
            )
            if athlete is None:
                athlete = Athlete(
                    name=data.name,
                    sport=adapter.sport,
                    team=data.team,
                    position=data.position,
                    external_ref=data.external_ref,
                )
                session.add(athlete)
            else:
                athlete.name = data.name
                athlete.team = data.team
                athlete.position = data.position
            session.flush()  # assign athlete.id before writing its stats

            for stat_key, value in data.stats.items():
                stat = session.scalar(
                    select(AthleteStat).where(
                        AthleteStat.athlete_id == athlete.id,
                        AthleteStat.stat_key == stat_key,
                    )
                )
                if stat is None:
                    session.add(
                        AthleteStat(
                            athlete_id=athlete.id,
                            stat_key=stat_key,
                            value=Decimal(str(value)),
                            as_of=today,
                        )
                    )
                else:
                    stat.value = Decimal(str(value))
                    stat.as_of = today

        session.commit()
    return [data.external_ref for data in athletes]


def prune_sport(session, sport: str, keep_refs: set[str]) -> tuple[list[str], list[str]]:
    """Drop this sport's athletes that the adapter no longer selects.

    An adapter returns the sport's current roster, so anything else of that
    sport is stale -- a player who fell out of the top N, or was chosen by a
    selection rule we have since replaced.

    Returns (removed, kept). Anyone a user has traded or still holds is kept:
    deleting them would tear a hole in that user's history for the sake of
    tidiness. Their price feed keeps running, they just are not re-ingested.
    """
    stale = session.scalars(
        select(Athlete).where(
            Athlete.sport == sport, Athlete.external_ref.not_in(keep_refs)
        )
    ).all()

    removed, kept = [], []
    for athlete in stale:
        traded = session.scalar(
            select(func.count()).select_from(Trade).where(Trade.athlete_id == athlete.id)
        ) or session.scalar(
            select(func.count())
            .select_from(Holding)
            .where(Holding.athlete_id == athlete.id)
        )
        if traded:
            kept.append(athlete.name)
            continue
        for model in (Price, GameLog, AthleteStat, MarketAthleteState):
            session.execute(delete(model).where(model.athlete_id == athlete.id))
        session.delete(athlete)
        removed.append(athlete.name)

    session.commit()
    return removed, kept


def main() -> None:
    refs = ingest(NBAAdapter())
    print(f"Ingested {len(refs)} NBA athletes.")


if __name__ == "__main__":
    main()
