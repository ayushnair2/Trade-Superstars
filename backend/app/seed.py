"""Seed a database from empty to playable. Run: python -m app.seed

Idempotent end to end, so it is safe to re-run against any DATABASE_URL:
  1. create tables
  2. ingest athletes from the sport adapters
  3. load per-game logs and perf baselines
  4. open the market at each athlete's baseline price
"""

from sqlalchemy import func, select

from app.adapters.nba import NBAAdapter
from app.adapters.nfl import NFLAdapter
from app.db import Base, SessionLocal, engine
from app.gamelogs import load_game_logs
from app.gamelogs_nfl import load_nfl_game_logs
from app.ingest import ingest
from app.models import Price
from app.norms import compute_sport_norms
from app.pricing import init_market


def main() -> None:
    print("1/5 creating tables...")
    Base.metadata.create_all(engine)

    print("2/5 ingesting athletes...")
    nba = ingest(NBAAdapter())
    print(f"     NBA: {nba} athletes")
    nfl = ingest(NFLAdapter())
    print(f"     NFL: {nfl} athletes")

    print("3/5 loading game logs...")
    loaded = load_game_logs()
    print(f"     NBA: {sum(g for _, g in loaded)} games for {len(loaded)} athletes")
    loaded_nfl = load_nfl_game_logs()
    print(f"     NFL: {sum(g for _, g in loaded_nfl)} games for {len(loaded_nfl)} athletes")

    print("4/5 computing per-sport norms...")
    with SessionLocal() as session:
        norms = compute_sport_norms(session)
        for sport, norm in sorted(norms.items()):
            print(
                f"     {sport}: mean {norm.mean_perf}, std {norm.std_perf}, "
                f"{norm.athlete_count} athletes"
            )

    print("5/5 opening the market...")
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
