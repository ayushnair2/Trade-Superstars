"""MLB adapter, backed by the public MLB StatsAPI (hitters only)."""

from datetime import datetime

from app.adapters.base import AthleteData, GameLogData, SportAdapter
from app.adapters.http import get_json
from app.config import mlb_score

SEASONS = (2025, 2024)
TOP_N = 50
MIN_GAMES = 20

BASE = "https://statsapi.mlb.com/api/v1"


def batting_stats(stat: dict) -> dict[str, float]:
    """Component stats keyed for config.mlb_score. Singles are derived."""
    hits = stat.get("hits") or 0
    doubles = stat.get("doubles") or 0
    triples = stat.get("triples") or 0
    home_runs = stat.get("homeRuns") or 0
    return {
        "singles": max(0, hits - doubles - triples - home_runs),
        "doubles": doubles,
        "triples": triples,
        "home_runs": home_runs,
        "rbi": stat.get("rbi") or 0,
        "runs": stat.get("runs") or 0,
        "walks": stat.get("baseOnBalls") or 0,
        "stolen_bases": stat.get("stolenBases") or 0,
    }


class MLBAdapter(SportAdapter):
    sport = "MLB"

    def __init__(self, seasons: tuple[int, ...] = SEASONS, top_n: int = TOP_N):
        self.seasons = seasons
        self.top_n = top_n
        self.season: int | None = None

    def fetch_athletes(self) -> list[AthleteData]:
        for season in self.seasons:
            data = get_json(
                f"{BASE}/stats",
                {
                    "stats": "season",
                    "group": "hitting",
                    "season": season,
                    "sportId": 1,
                    "limit": 300,
                },
            )
            splits = data.get("stats", [{}])[0].get("splits", [])
            if not splits:
                continue
            self.season = season

            rows = []
            for split in splits:
                stat = split.get("stat", {})
                games = stat.get("gamesPlayed") or 0
                if games < MIN_GAMES:
                    continue
                stats = batting_stats(stat)
                rows.append((mlb_score(stats), split, stats, games))

            rows.sort(key=lambda r: -r[0])
            return [
                AthleteData(
                    name=split["player"]["fullName"],
                    team=(split.get("team") or {}).get("abbreviation") or "MLB",
                    external_ref=str(split["player"]["id"]),
                    stats={k: round(v / games, 2) for k, v in stats.items()},
                )
                for _, split, stats, games in rows[: self.top_n]
            ]
        raise RuntimeError(f"no MLB hitting data for any of {self.seasons}")

    def fetch_game_logs(self, external_ref: str) -> list[GameLogData]:
        season = self.season or self.seasons[0]
        data = get_json(
            f"{BASE}/people/{external_ref}/stats",
            {"stats": "gameLog", "group": "hitting", "season": season},
        )
        splits = data.get("stats", [{}])[0].get("splits", [])
        logs = []
        for split in splits:
            stats = batting_stats(split.get("stat", {}))
            logs.append(
                GameLogData(
                    game_date=datetime.strptime(split["date"], "%Y-%m-%d").date(),
                    perf_score=mlb_score(stats),
                    pts=stats["home_runs"],
                    reb=stats["rbi"],
                    ast=stats["runs"],
                )
            )
        # gameLog comes back chronologically; keep it explicit
        logs.sort(key=lambda log: log.game_date)
        return logs
