"""English Premier League adapter, backed by ESPN's public soccer endpoints.

ESPN publishes no league-wide player stats feed that works, so players are
discovered by walking the 20 club rosters and reading each player's gamelog.
That is a few hundred requests, so it is throttled.
"""

import time
from datetime import datetime

from app.adapters.base import AthleteData, GameLogData, SportAdapter
from app.adapters.http import get_json
from app.config import soccer_score

LEAGUE = "eng.1"
TOP_N = 25
MIN_APPEARANCES = 5
THROTTLE_SECONDS = 0.12

SITE = f"https://site.web.api.espn.com/apis/site/v2/sports/soccer/{LEAGUE}"
COMMON = f"https://site.web.api.espn.com/apis/common/v3/sports/soccer/{LEAGUE}"

# ESPN stat name -> our scoring key. Key passes are not published here.
STAT_NAMES = {
    "totalGoals": "goals",
    "goalAssists": "assists",
    "shotsOnTarget": "shots_on_target",
}


def _teams() -> list[dict]:
    data = get_json(f"{SITE}/teams")
    return [t["team"] for t in data["sports"][0]["leagues"][0]["teams"]]


def _roster(team_id: str) -> list[dict]:
    try:
        data = get_json(f"{SITE}/teams/{team_id}/roster")
    except Exception:
        return []
    return data.get("athletes", [])


def _gamelog(player_id: str) -> tuple[list[str], list[dict], dict]:
    data = get_json(f"{COMMON}/athletes/{player_id}/gamelog")
    names = data.get("names") or []
    entries = [
        entry
        for season in data.get("seasonTypes", [])
        for category in season.get("categories", [])
        for entry in category.get("events", [])
    ]
    return names, entries, data.get("events", {})


def _entry_stats(names: list[str], values: list) -> dict[str, float]:
    raw = dict(zip(names, values))
    stats = {}
    for espn_name, key in STAT_NAMES.items():
        try:
            stats[key] = float(raw.get(espn_name) or 0)
        except (TypeError, ValueError):
            stats[key] = 0.0
    return stats


class SoccerAdapter(SportAdapter):
    sport = "SOC"

    def __init__(self, top_n: int = TOP_N):
        self.top_n = top_n
        self._logs: dict[str, list[GameLogData]] = {}

    def fetch_athletes(self) -> list[AthleteData]:
        candidates = []
        for team in _teams():
            for entry in _roster(team["id"]):
                position = (entry.get("position") or {}).get("abbreviation") or ""
                if position.upper() in ("G", "GK"):
                    continue  # goalkeepers score on a different axis entirely
                candidates.append(
                    (entry.get("id"), entry.get("displayName"), team.get("abbreviation"))
                )
            time.sleep(THROTTLE_SECONDS)

        scored = []
        for player_id, name, team_abbrev in candidates:
            if not player_id:
                continue
            try:
                names, entries, events = _gamelog(player_id)
            except Exception:
                continue
            finally:
                time.sleep(THROTTLE_SECONDS)
            if "shotsOnTarget" not in names or len(entries) < MIN_APPEARANCES:
                continue

            logs, totals = [], {}
            for entry in entries:
                stats = _entry_stats(names, entry.get("stats") or [])
                for key, value in stats.items():
                    totals[key] = totals.get(key, 0.0) + value
                meta = events.get(entry.get("eventId"), {})
                raw_date = (meta.get("gameDate") or "")[:10]
                try:
                    game_date = datetime.strptime(raw_date, "%Y-%m-%d").date()
                except ValueError:
                    continue
                logs.append(
                    GameLogData(
                        game_date=game_date,
                        perf_score=soccer_score(stats),
                        pts=stats["goals"],
                        reb=stats["assists"],
                        ast=stats["shots_on_target"],
                    )
                )
            if len(logs) < MIN_APPEARANCES:
                continue

            logs.sort(key=lambda log: log.game_date)
            self._logs[str(player_id)] = logs
            games = len(logs)
            scored.append(
                (
                    soccer_score(totals),
                    AthleteData(
                        name=name,
                        team=team_abbrev or "EPL",
                        external_ref=str(player_id),
                        stats={k: round(v / games, 2) for k, v in totals.items()},
                    ),
                )
            )

        if not scored:
            raise RuntimeError("no EPL players with usable gamelogs")
        scored.sort(key=lambda s: -s[0])
        return [athlete for _, athlete in scored[: self.top_n]]

    def fetch_game_logs(self, external_ref: str) -> list[GameLogData]:
        # already gathered while ranking; refetching would double the requests
        return self._logs.get(str(external_ref), [])
