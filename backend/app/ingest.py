"""Ingest athletes from a sport adapter into the DB. Run: python -m app.ingest

Idempotent: athletes match on (external_ref, sport), stats on (athlete_id,
stat_key), so re-running updates in place rather than inserting duplicates.
"""

from datetime import date
from decimal import Decimal

from sqlalchemy import select

from app.adapters.base import SportAdapter
from app.adapters.nba import NBAAdapter
from app.db import SessionLocal
from app.models import Athlete, AthleteStat


def ingest(adapter: SportAdapter) -> int:
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
                    external_ref=data.external_ref,
                )
                session.add(athlete)
            else:
                athlete.name = data.name
                athlete.team = data.team
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
    return len(athletes)


def main() -> None:
    count = ingest(NBAAdapter())
    print(f"Ingested {count} NBA athletes.")


if __name__ == "__main__":
    main()
