"""Load per-game logs for ingested athletes. Run: python -m app.gamelogs

Idempotent: a player's existing logs are deleted and rewritten each run, and
perf_mean/perf_std are upserted into athlete_stats.
"""

import statistics
import time
from datetime import date, datetime
from decimal import Decimal

from nba_api.stats.endpoints import playergamelog
from sqlalchemy import delete, select

from app.adapters.nba import SEASONS
from app.config import perf_score
from app.db import SessionLocal
from app.models import Athlete, AthleteStat, GameLog

SPORT = "NBA"
TIMEOUT = 60
RETRIES = 2
THROTTLE_SECONDS = 0.6


def _fetch_logs(player_id: str, season: str) -> list[dict]:
    """One player's game log for a season, retrying once -- nba_api is flaky."""
    last_error = None
    for attempt in range(RETRIES):
        try:
            endpoint = playergamelog.PlayerGameLog(
                player_id=player_id,
                season=season,
                season_type_all_star="Regular Season",
                timeout=TIMEOUT,
            )
            return endpoint.get_normalized_dict()["PlayerGameLog"]
        except Exception as exc:
            last_error = exc
            if attempt < RETRIES - 1:
                time.sleep(2)
    raise RuntimeError(f"nba_api failed for player {player_id}: {last_error}")


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


def load_game_logs() -> list[tuple[str, int]]:
    today = date.today()
    loaded = []

    with SessionLocal() as session:
        athletes = session.scalars(
            select(Athlete).where(Athlete.sport == SPORT).order_by(Athlete.id)
        ).all()

        for athlete in athletes:
            rows = []
            for season in SEASONS:
                rows = _fetch_logs(athlete.external_ref, season)
                if rows:
                    break
            time.sleep(THROTTLE_SECONDS)

            if not rows:
                loaded.append((athlete.name, 0))
                continue

            # nba_api returns newest game first; we store oldest first.
            rows = list(reversed(rows))

            session.execute(delete(GameLog).where(GameLog.athlete_id == athlete.id))

            scores = []
            for index, row in enumerate(rows):
                score = perf_score(row["PTS"], row["REB"], row["AST"])
                scores.append(score)
                session.add(
                    GameLog(
                        athlete_id=athlete.id,
                        game_index=index,
                        game_date=datetime.strptime(
                            row["GAME_DATE"], "%b %d, %Y"
                        ).date(),
                        pts=Decimal(str(row["PTS"])),
                        reb=Decimal(str(row["REB"])),
                        ast=Decimal(str(row["AST"])),
                        perf_score=Decimal(f"{score:.2f}"),
                    )
                )

            _upsert_stat(session, athlete.id, "perf_mean", statistics.mean(scores), today)
            # stdev needs 2+ games; a single game has no swing.
            spread = statistics.stdev(scores) if len(scores) > 1 else 0.0
            _upsert_stat(session, athlete.id, "perf_std", spread, today)

            loaded.append((athlete.name, len(rows)))

        session.commit()
    return loaded


def main() -> None:
    results = load_game_logs()
    print(f"Loaded game logs for {len(results)} athletes.")


if __name__ == "__main__":
    main()
