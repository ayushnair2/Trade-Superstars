"""NBA adapter, backed by nba_api's leaguedashplayerstats endpoint."""

import time

from nba_api.stats.endpoints import leaguedashplayerstats

from app.adapters.base import AthleteData, SportAdapter

SEASONS = ("2025-26", "2024-25")
TOP_N = 50
TIMEOUT = 60
RETRIES = 2


class NBAAdapter(SportAdapter):
    sport = "NBA"

    def __init__(self, seasons: tuple[str, ...] = SEASONS, top_n: int = TOP_N):
        self.seasons = seasons
        self.top_n = top_n

    def _fetch_season(self, season: str) -> list[dict]:
        """Pull one season's player totals, retrying once -- nba_api is flaky."""
        last_error = None
        for attempt in range(RETRIES):
            try:
                endpoint = leaguedashplayerstats.LeagueDashPlayerStats(
                    season=season,
                    season_type_all_star="Regular Season",
                    timeout=TIMEOUT,
                )
                return endpoint.get_normalized_dict()["LeagueDashPlayerStats"]
            except Exception as exc:  # network/timeout/shape -- all retryable here
                last_error = exc
                if attempt < RETRIES - 1:
                    time.sleep(2)
        raise RuntimeError(f"nba_api failed for {season}: {last_error}")

    def fetch_athletes(self) -> list[AthleteData]:
        rows: list[dict] = []
        for season in self.seasons:
            rows = self._fetch_season(season)
            if rows:
                break

        if not rows:
            raise RuntimeError(f"no rows from nba_api for any of {self.seasons}")

        # Rank by total points, then report per-game averages.
        top = sorted(rows, key=lambda r: r["PTS"], reverse=True)[: self.top_n]

        athletes = []
        for r in top:
            gp = r["GP"] or 1  # guard: never divide by zero
            athletes.append(
                AthleteData(
                    name=r["PLAYER_NAME"],
                    team=r["TEAM_ABBREVIATION"],
                    external_ref=str(r["PLAYER_ID"]),
                    stats={
                        "pts": round(r["PTS"] / gp, 2),
                        "reb": round(r["REB"] / gp, 2),
                        "ast": round(r["AST"] / gp, 2),
                    },
                )
            )
        return athletes
