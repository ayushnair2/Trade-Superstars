"""Load weekly NFL game logs. Run: python -m app.gamelogs_nfl

Mirrors app.gamelogs for the NBA: one GameLog row per week, oldest first, with
perf_score set to that week's PPR fantasy points, plus perf_mean / perf_std.
Idempotent -- a player's logs are deleted and rewritten each run.
"""

import statistics
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import delete, select

from app.adapters.nfl import SEASONS, game_dates, load_weekly, week_stats
from app.config import fantasy_points
from app.db import SessionLocal
from app.models import Athlete, AthleteStat, GameLog

SPORT = "NFL"


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


def load_nfl_game_logs() -> list[tuple[str, int]]:
    today = date.today()
    season, weekly = load_weekly(SEASONS)
    dates = game_dates(season)

    # weekly rows keyed by player, already in week order
    by_player: dict[str, list[dict]] = {}
    for row in weekly.sort_values("week").to_dict("records"):
        by_player.setdefault(row["player_id"], []).append(row)

    loaded = []
    with SessionLocal() as session:
        athletes = session.scalars(
            select(Athlete).where(Athlete.sport == SPORT).order_by(Athlete.id)
        ).all()

        for athlete in athletes:
            rows = by_player.get(athlete.external_ref, [])
            if not rows:
                loaded.append((athlete.name, 0))
                continue

            session.execute(delete(GameLog).where(GameLog.athlete_id == athlete.id))

            scores = []
            for index, row in enumerate(rows):
                stats = week_stats(row)
                score = fantasy_points(stats)
                scores.append(score)
                gameday = dates.get((int(row["week"]), row["recent_team"]))
                session.add(
                    GameLog(
                        athlete_id=athlete.id,
                        game_index=index,
                        game_date=(
                            datetime.strptime(gameday, "%Y-%m-%d").date()
                            if gameday
                            else today
                        ),
                        # GameLog's three stat columns are shared across sports:
                        # for the NFL they carry the scoring components that
                        # matter most for a skill player.
                        pts=Decimal(f"{stats['receiving_yds'] + stats['rushing_yds']:.2f}"),
                        reb=Decimal(f"{stats['receptions']:.2f}"),
                        ast=Decimal(f"{stats['passing_yds']:.2f}"),
                        perf_score=Decimal(f"{score:.2f}"),
                    )
                )

            _upsert_stat(session, athlete.id, "perf_mean", statistics.mean(scores), today)
            spread = statistics.stdev(scores) if len(scores) > 1 else 0.0
            _upsert_stat(session, athlete.id, "perf_std", spread, today)
            loaded.append((athlete.name, len(rows)))

        session.commit()
    return loaded


def main() -> None:
    results = load_nfl_game_logs()
    print(f"Loaded NFL game logs for {len(results)} athletes.")


if __name__ == "__main__":
    main()
