"""NHL adapter, backed by the public NHL stats APIs (skaters only)."""

from datetime import datetime

from app.adapters.base import AthleteData, GameLogData, SportAdapter
from app.adapters.http import get_json
from app.config import nhl_score

SEASONS = ("20242025", "20232024")
TOP_N = 25
MIN_GAMES = 10

STATS_BASE = "https://api.nhle.com/stats/rest/en/skater"
WEB_BASE = "https://api-web.nhle.com/v1"


def _report(report: str, season: str) -> list[dict]:
    """One skater report for a season, all rows."""
    data = get_json(
        f"{STATS_BASE}/{report}",
        {"limit": -1, "cayenneExp": f"seasonId={season} and gameTypeId=2"},
    )
    return data.get("data", [])


class NHLAdapter(SportAdapter):
    sport = "NHL"

    def __init__(self, seasons: tuple[str, ...] = SEASONS, top_n: int = TOP_N):
        self.seasons = seasons
        self.top_n = top_n
        self.season: str | None = None

    def fetch_athletes(self) -> list[AthleteData]:
        for season in self.seasons:
            summary = _report("summary", season)
            if not summary:
                continue
            self.season = season

            # blocks live in a separate report, joined on playerId
            blocks = {
                row["playerId"]: row.get("blockedShots") or 0
                for row in _report("realtime", season)
            }

            rows = []
            for row in summary:
                games = row.get("gamesPlayed") or 0
                if games < MIN_GAMES:
                    continue
                stats = {
                    "goals": row.get("goals") or 0,
                    "assists": row.get("assists") or 0,
                    "shots": row.get("shots") or 0,
                    "blocks": blocks.get(row["playerId"], 0),
                    "powerplay_points": row.get("ppPoints") or 0,
                }
                rows.append((nhl_score(stats), row, stats, games))

            rows.sort(key=lambda r: -r[0])
            return [
                AthleteData(
                    name=row["skaterFullName"],
                    # a traded skater lists every team; the latest is last
                    team=(row.get("teamAbbrevs") or "").split(",")[-1].strip(),
                    external_ref=str(row["playerId"]),
                    stats={k: round(v / games, 2) for k, v in stats.items()},
                )
                for _, row, stats, games in rows[: self.top_n]
            ]
        raise RuntimeError(f"no NHL skater data for any of {self.seasons}")

    def fetch_game_logs(self, external_ref: str) -> list[GameLogData]:
        season = self.season or self.seasons[0]
        data = get_json(f"{WEB_BASE}/player/{external_ref}/game-log/{season}/2")
        logs = []
        for game in reversed(data.get("gameLog", [])):
            stats = {
                "goals": game.get("goals") or 0,
                "assists": game.get("assists") or 0,
                "shots": game.get("shots") or 0,
                # the game-log endpoint does not publish blocks
                "blocks": 0,
                "powerplay_points": game.get("powerPlayPoints") or 0,
            }
            logs.append(
                GameLogData(
                    game_date=datetime.strptime(game["gameDate"], "%Y-%m-%d").date(),
                    perf_score=nhl_score(stats),
                    pts=stats["goals"],
                    reb=stats["assists"],
                    ast=stats["shots"],
                )
            )
        return logs
