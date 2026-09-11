"""Seed a database from empty to playable. Run: python -m app.seed

Idempotent end to end, so it is safe to re-run against any DATABASE_URL:
  1. create tables
  2. ingest athletes from the sport adapters
  3. load per-game logs and perf baselines
  4. open the market at each athlete's baseline price
"""

from sqlalchemy import func, select

from app.adapters.mlb import MLBAdapter
from app.adapters.nba import NBAAdapter
from app.adapters.nfl import NFLAdapter
from app.adapters.nhl import NHLAdapter
from app.adapters.soccer import SoccerAdapter
from app.db import Base, SessionLocal, engine
from app.gamelogs import load_game_logs
from app.gamelogs_generic import load_game_logs_for
from app.gamelogs_nfl import load_nfl_game_logs
from app.ingest import ingest
from app.models import Price
from app.norms import compute_sport_norms
from app.pricing import init_market, open_missing_prices


def _sport_jobs():
    """Each sport: (label, ingest callable, game-log callable)."""
    nba, nfl = NBAAdapter(), NFLAdapter()
    nhl, mlb, soc = NHLAdapter(), MLBAdapter(), SoccerAdapter()
    return [
        ("NBA", nba, load_game_logs),
        ("NFL", nfl, load_nfl_game_logs),
        ("NHL", nhl, lambda: load_game_logs_for(nhl)),
        ("MLB", mlb, lambda: load_game_logs_for(mlb)),
        ("SOC", soc, lambda: load_game_logs_for(soc)),
    ]


def run_all_sports() -> list[str]:
    """Ingest every sport in isolation. One sport failing never stops the rest."""
    status = []
    for label, adapter, load_logs in _sport_jobs():
        try:
            count = ingest(adapter)
            logs = load_logs()
            games = sum(g for _, g in logs)
            status.append(f"{label}: {count} players, {games} games")
        except Exception as exc:
            status.append(f"{label}: FAILED - {type(exc).__name__}: {str(exc)[:110]}")
    return status


def main() -> None:
    print("1/5 creating tables...")
    Base.metadata.create_all(engine)

    print("2/5 ingesting athletes and loading game logs (per sport)...")
    status = run_all_sports()
    print()
    print("3/5 STATUS")
    for line in status:
        print(f"     {line}")

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
            # market already trading: only newcomers need an opening price
            opened = open_missing_prices(session)
            print(f"     already open; opened {len(opened)} new athletes")
        else:
            opening = init_market(session)
            print(f"     opened {len(opening)} athletes at their baseline")

    print("done.")


if __name__ == "__main__":
    main()
