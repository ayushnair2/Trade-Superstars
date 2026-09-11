"""Football (soccer) adapter over ESPN's public endpoints, across Europe's big five.

ESPN has no working league-wide player stats feed (statistics/byathlete returns
an empty list for every league and season), so players are discovered by walking
club rosters, which do carry season totals. Those totals shortlist candidates
cheaply; only the shortlist pays for per-game logs.

Tradeoff worth knowing: ranking on attacking output (goals, assists, shots on
target) selects forwards and attacking midfielders. Elite defenders and
goalkeepers score near zero here and will not appear, even though they are among
the best players in the world. A defensive metric would need its own formula.
"""

import time
from datetime import datetime

from app.adapters.base import AthleteData, GameLogData, SportAdapter
from app.adapters.http import get_json
from app.config import fut_score

# ESPN league slug -> the tag shown on an athlete's row
LEAGUES = {
    "eng.1": "EPL",
    "esp.1": "LIGA",
    "ger.1": "BUND",
    "ita.1": "SERA",
    "fra.1": "LIG1",
}

TOP_N = 25
# ESPN's domestic gamelog only exposes the season in progress, and passing a
# season parameter switches competition (it returns Champions League fixtures)
# rather than the previous league campaign. Three matchweeks in, three is the
# most a regular starter can have -- it still filters out the injured, the
# fringe and the newly transferred. Raise it as the season grows.
MIN_APPEARANCES = 3
# candidates carried from each league into the game-log round
SHORTLIST_PER_LEAGUE = 20
THROTTLE_SECONDS = 0.08

SITE = "https://site.web.api.espn.com/apis/site/v2/sports/soccer"
COMMON = "https://site.web.api.espn.com/apis/common/v3/sports/soccer"

# ESPN stat name -> our scoring key. Key passes are not published anywhere in
# these feeds, so that component scores zero.
STAT_NAMES = {
    "totalGoals": "goals",
    "goalAssists": "assists",
    "shotsOnTarget": "shots_on_target",
}


def _roster_stats(entry: dict) -> dict[str, float]:
    """Season totals carried on a roster entry."""
    flat = {}
    categories = (entry.get("statistics") or {}).get("splits", {}).get("categories", [])
    for category in categories:
        for stat in category.get("stats", []):
            flat[stat.get("name")] = stat.get("value")

    stats = {key: float(flat.get(name) or 0.0) for name, key in STAT_NAMES.items()}
    stats["appearances"] = float(flat.get("appearances") or 0.0)
    return stats


def _entry_stats(names: list[str], values: list) -> dict[str, float]:
    raw = dict(zip(names, values))
    stats = {}
    for espn_name, key in STAT_NAMES.items():
        try:
            stats[key] = float(raw.get(espn_name) or 0)
        except (TypeError, ValueError):
            stats[key] = 0.0
    return stats


def league_candidates(league: str) -> list[dict]:
    """Shortlist one league's best attacking output from club rosters."""
    data = get_json(f"{SITE}/{league}/teams")
    teams = [t["team"] for t in data["sports"][0]["leagues"][0]["teams"]]

    scored = []
    for team in teams:
        try:
            roster = get_json(f"{SITE}/{league}/teams/{team['id']}/roster")
        except Exception:
            continue  # a single club failing should not lose the league
        finally:
            time.sleep(THROTTLE_SECONDS)

        for entry in roster.get("athletes", []):
            position = (entry.get("position") or {}).get("abbreviation") or ""
            if position.upper() in ("G", "GK") or not entry.get("id"):
                continue
            stats = _roster_stats(entry)
            scored.append(
                {
                    "id": str(entry["id"]),
                    "name": entry.get("displayName"),
                    "team": team.get("abbreviation") or LEAGUES[league],
                    "league": league,
                    "season_score": fut_score(stats),
                }
            )

    scored.sort(key=lambda c: -c["season_score"])
    return scored[:SHORTLIST_PER_LEAGUE]


def player_logs(league: str, player_id: str) -> tuple[list[GameLogData], dict[str, float]]:
    """Per-game logs plus season totals, from the player's gamelog."""
    data = get_json(f"{COMMON}/{league}/athletes/{player_id}/gamelog")
    names = data.get("names") or []
    if "shotsOnTarget" not in names:
        return [], {}

    events = data.get("events", {})
    entries = [
        entry
        for season in data.get("seasonTypes", [])
        for category in season.get("categories", [])
        for entry in category.get("events", [])
    ]

    logs, totals = [], {}
    for entry in entries:
        stats = _entry_stats(names, entry.get("stats") or [])
        raw_date = ((events.get(entry.get("eventId")) or {}).get("gameDate") or "")[:10]
        try:
            game_date = datetime.strptime(raw_date, "%Y-%m-%d").date()
        except ValueError:
            continue
        for key, value in stats.items():
            totals[key] = totals.get(key, 0.0) + value
        logs.append(
            GameLogData(
                game_date=game_date,
                perf_score=fut_score(stats),
                pts=stats["goals"],
                reb=stats["assists"],
                ast=stats["shots_on_target"],
            )
        )

    logs.sort(key=lambda log: log.game_date)
    return logs, totals


class SoccerAdapter(SportAdapter):
    sport = "FUT"

    def __init__(self, leagues: dict[str, str] = LEAGUES, top_n: int = TOP_N):
        self.leagues = leagues
        self.top_n = top_n
        self._logs: dict[str, list[GameLogData]] = {}
        self.league_status: dict[str, str] = {}
        # external_ref -> league tag, for reporting; stats stay numeric
        self.player_league: dict[str, str] = {}

    def fetch_athletes(self) -> list[AthleteData]:
        candidates = []
        for league in self.leagues:
            try:
                found = league_candidates(league)
                candidates.extend(found)
                self.league_status[league] = f"{len(found)} shortlisted"
            except Exception as exc:
                # one league's feed failing must not lose the other four
                self.league_status[league] = f"FAILED - {type(exc).__name__}"

        if not candidates:
            raise RuntimeError("no candidates from any league")

        ranked = []
        for candidate in candidates:
            try:
                logs, totals = player_logs(candidate["league"], candidate["id"])
            except Exception:
                continue
            finally:
                time.sleep(THROTTLE_SECONDS)
            if len(logs) < MIN_APPEARANCES:
                continue
            self._logs[candidate["id"]] = logs
            games = len(logs)
            ranked.append(
                (
                    fut_score(totals),
                    AthleteData(
                        name=candidate["name"],
                        team=candidate["team"],
                        external_ref=candidate["id"],
                        stats={k: round(v / games, 2) for k, v in totals.items()},
                    ),
                )
            )

        if not ranked:
            raise RuntimeError("no football players with usable gamelogs")
        ranked.sort(key=lambda r: -r[0])
        selected = [athlete for _, athlete in ranked[: self.top_n]]
        by_ref = {c["id"]: self.leagues[c["league"]] for c in candidates}
        self.player_league = {a.external_ref: by_ref[a.external_ref] for a in selected}
        return selected

    def fetch_game_logs(self, external_ref: str) -> list[GameLogData]:
        # gathered while ranking; refetching would double the request count
        return self._logs.get(str(external_ref), [])
