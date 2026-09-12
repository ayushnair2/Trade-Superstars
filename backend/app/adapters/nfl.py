"""NFL adapter, backed by nfl_data_py's weekly player data."""

import os

import certifi

from app.adapters.base import AthleteData, SportAdapter
from app.config import fantasy_points

# nfl_data_py fetches over https via urllib, which on a python.org macOS build
# has no CA store wired up. Point it at certifi's bundle -- a real trust store,
# not a verification bypass. Left alone if the environment already sets one.
os.environ.setdefault("SSL_CERT_FILE", certifi.where())

import nfl_data_py as nfl  # noqa: E402  (must follow the SSL_CERT_FILE default)

SEASONS = (2025, 2024)
TOP_N = 50
MIN_GAMES = 5

# nfl_data_py column -> our scoring key. Fumbles are split across three columns
# in the source, so they are summed separately below.
STAT_COLUMNS = {
    "passing_yards": "passing_yds",
    "passing_tds": "passing_td",
    "interceptions": "interceptions",
    "rushing_yards": "rushing_yds",
    "rushing_tds": "rushing_td",
    "receiving_yards": "receiving_yds",
    "receptions": "receptions",
    "receiving_tds": "receiving_td",
}
FUMBLE_COLUMNS = ("sack_fumbles_lost", "rushing_fumbles_lost", "receiving_fumbles_lost")


def week_stats(row) -> dict[str, float]:
    """One week's component stats, keyed the way config.fantasy_points expects."""
    stats = {key: float(row.get(column) or 0.0) for column, key in STAT_COLUMNS.items()}
    stats["fumbles_lost"] = sum(float(row.get(c) or 0.0) for c in FUMBLE_COLUMNS)
    return stats


def load_weekly(seasons: tuple[int, ...] = SEASONS):
    """Regular-season weekly rows for the most recent season that has data."""
    for season in seasons:
        try:
            frame = nfl.import_weekly_data([season])
        except Exception:
            # a season that has not been published yet 404s; try the next
            continue
        frame = frame[frame["season_type"] == "REG"]
        if len(frame):
            return season, frame
    raise RuntimeError(f"no NFL weekly data for any of {seasons}")


def game_dates(season: int) -> dict[tuple[int, str], str]:
    """(week, team) -> gameday, so weekly rows can carry a real date."""
    schedule = nfl.import_schedules([season])
    schedule = schedule[schedule["game_type"] == "REG"]
    dates = {}
    for row in schedule.itertuples():
        dates[(int(row.week), row.home_team)] = row.gameday
        dates[(int(row.week), row.away_team)] = row.gameday
    return dates


class NFLAdapter(SportAdapter):
    sport = "NFL"

    def __init__(self, seasons: tuple[int, ...] = SEASONS, top_n: int = TOP_N):
        self.seasons = seasons
        self.top_n = top_n
        self.season: int | None = None

    def fetch_athletes(self) -> list[AthleteData]:
        season, weekly = load_weekly(self.seasons)
        self.season = season

        totals: dict[str, dict] = {}
        for row in weekly.to_dict("records"):
            player_id = row["player_id"]
            entry = totals.setdefault(
                player_id,
                {
                    "player_id": player_id,
                    "name": row["player_display_name"],
                    "team": row["recent_team"],
                    "games": 0,
                    "points": 0.0,
                    "sums": {},
                },
            )
            stats = week_stats(row)
            entry["games"] += 1
            entry["points"] += fantasy_points(stats)
            entry["team"] = row["recent_team"]
            for key, value in stats.items():
                entry["sums"][key] = entry["sums"].get(key, 0.0) + value

        eligible = [e for e in totals.values() if e["games"] >= MIN_GAMES]
        top = sorted(eligible, key=lambda e: e["points"], reverse=True)[: self.top_n]

        athletes = []
        for entry in top:
            games = entry["games"]
            athletes.append(
                AthleteData(
                    name=entry["name"],
                    team=entry["team"],
                    external_ref=str(entry["player_id"]),
                    stats={
                        key: round(total / games, 2)
                        for key, total in entry["sums"].items()
                    },
                )
            )
        return athletes
