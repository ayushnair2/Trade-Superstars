"""Seed a database from empty to playable. Run: python -m app.seed

Idempotent end to end, so it is safe to re-run against any DATABASE_URL:
  1. create tables
  2. ingest athletes from the sport adapters
  3. load per-game logs and perf baselines
  4. open the market at each athlete's baseline price
"""

from sqlalchemy import func, select

from app.adapters.nba import NBAAdapter
from app.db import Base, SessionLocal, engine
from app.gamelogs import load_game_logs
from app.ingest import ingest
from app.models import Price
from app.pricing import init_market


def main() -> None:
    print("1/4 creating tables...")
    Base.metadata.create_all(engine)

    print("2/4 ingesting athletes...")
    count = ingest(NBAAdapter())
    print(f"     {count} athletes")

    print("3/4 loading game logs...")
    loaded = load_game_logs()
    print(f"     {sum(games for _, games in loaded)} games for {len(loaded)} athletes")

    print("4/4 opening the market...")
    with SessionLocal() as session:
        # init_market writes a fresh opening price for everyone, so only run it
        # on a market that has never been opened.
        if session.scalar(select(func.count()).select_from(Price)):
            print("     already open, leaving prices alone")
        else:
            opening = init_market(session)
            print(f"     opened {len(opening)} athletes at their baseline")

    print("done.")


if __name__ == "__main__":
    main()
