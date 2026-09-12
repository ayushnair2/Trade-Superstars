"""Football (soccer) adapter: selection by market value, movement from ESPN.

Two sources, each doing the one thing it can.

A published market-value ranking picks WHO is in the market. Ranking on the
attacking stats ESPN publishes selected only forwards, because the free
per-game football data has no tackles, interceptions, clearances, blocks, key
passes or xG -- a world-class centre-back scores ~0 in it. Market value is the
one public number that rates every position on the same scale.

ESPN then supplies the per-game logs that make prices MOVE, plus each player's
authoritative position and club. The ranking page's own position and club
columns are third-party aggregations and demonstrably unreliable (midfielders
labelled DEF, players at clubs they left), so only its market value is used.

Consequence worth knowing: per-game movement is still attacking-only, so it is
damped by position in pricing.move_weight rather than pretended to be complete.
"""

import re
import time
import unicodedata
from datetime import datetime

from app.adapters.base import AthleteData, GameLogData, SportAdapter
from app.adapters.http import get_json, get_text
from app.config import FUT_VALUE_TOP_N, fut_score

# ESPN league slug -> the tag shown on an athlete's row
LEAGUES = {
    "eng.1": "EPL",
    "esp.1": "LIGA",
    "ger.1": "BUND",
    "ita.1": "SERA",
    "fra.1": "LIG1",
}

# Third-party aggregation of Transfermarkt values. transfermarkt.com itself is
# Cloudflare-walled and must not be scraped directly.
VALUE_URL = "https://transfertracker.ai/rankings/most-valuable-players"

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

# dropped when comparing club names across the two sources
CLUB_STOPWORDS = {"fc", "cf", "sc", "ac", "de", "club", "the", "1"}


def _norm(text: str) -> str:
    """Accent-free lowercase, for comparing names across two sources."""
    text = unicodedata.normalize("NFD", text or "")
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    text = text.lower().replace("-", " ").replace("'", "").replace(".", "")
    return re.sub(r"\s+", " ", text).strip()


def _club_tokens(name: str) -> set[str]:
    return {t for t in _norm(name).split() if t not in CLUB_STOPWORDS}


def _cell_text(cell: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", cell)).strip()


def fetch_value_ranking(url: str = VALUE_URL) -> list[dict]:
    """Parse the published ranking: name, club and market value in millions."""
    html = get_text(url)
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.S)

    ranked = []
    for row in rows:
        cells = [
            _cell_text(c) for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row, re.S)
        ]
        if len(cells) < 6 or not cells[0].isdigit():
            continue  # header, or a layout row that is not a player
        value = re.search(r"([\d.]+)", cells[5].replace(",", ""))
        if value is None:
            continue
        ranked.append(
            {
                "rank": int(cells[0]),
                "name": cells[1],
                "club": cells[2],
                "source_position": cells[3],
                "value_m": float(value.group(1)),
            }
        )
    if not ranked:
        raise RuntimeError(f"no player rows parsed from {url}")
    return ranked


def roster_index(leagues: dict[str, str], status: dict[str, str]) -> list[dict]:
    """Every big-5 player ESPN lists, with their club and position."""
    index = []
    for league, tag in leagues.items():
        try:
            data = get_json(f"{SITE}/{league}/teams")
            teams = [t["team"] for t in data["sports"][0]["leagues"][0]["teams"]]
        except Exception as exc:
            # one league's feed failing must not lose the other four
            status[league] = f"FAILED - {type(exc).__name__}"
            continue

        found = 0
        for team in teams:
            try:
                roster = get_json(f"{SITE}/{league}/teams/{team['id']}/roster")
            except Exception:
                continue  # a single club failing should not lose the league
            finally:
                time.sleep(THROTTLE_SECONDS)

            for entry in roster.get("athletes", []):
                if not entry.get("id"):
                    continue
                index.append(
                    {
                        "id": str(entry["id"]),
                        "league": league,
                        "tag": tag,
                        "team": team.get("abbreviation") or tag,
                        "club": team.get("displayName") or "",
                        "display": entry.get("displayName") or "",
                        "full": entry.get("fullName") or "",
                        "last": entry.get("lastName") or "",
                        "position": (entry.get("position") or {}).get("abbreviation"),
                    }
                )
                found += 1
        status[league] = f"{len(teams)} clubs, {found} players"
    return index


class _Matcher:
    """Resolves ranking names to ESPN players, using club as the tiebreak."""

    def __init__(self, index: list[dict]):
        self.index = index
        self.by_display: dict[str, list[dict]] = {}
        self.by_full: dict[str, list[dict]] = {}
        self.by_last: dict[str, list[dict]] = {}
        for player in index:
            self.by_display.setdefault(_norm(player["display"]), []).append(player)
            self.by_full.setdefault(_norm(player["full"]), []).append(player)
            self.by_last.setdefault(_norm(player["last"]), []).append(player)
        self.clubs = {p["club"]: _club_tokens(p["club"]) for p in index}

    def _club(self, club: str) -> str | None:
        """The ESPN club whose name shares the most words with this one."""
        want = _club_tokens(club)
        best, score = None, 0
        for full, tokens in self.clubs.items():
            overlap = len(want & tokens)
            if overlap > score:
                best, score = full, overlap
        return best

    def find(self, name: str, club: str) -> tuple[dict | None, str]:
        key = _norm(name)
        espn_club = self._club(club)

        def pick(candidates: list[dict], how: str) -> tuple[dict | None, str | None]:
            if len(candidates) == 1:
                return candidates[0], how
            if len(candidates) > 1 and espn_club:
                same = [c for c in candidates if c["club"] == espn_club]
                if len(same) == 1:
                    return same[0], f"{how}+club"
            return None, None

        for table, how in ((self.by_display, "display"), (self.by_full, "full")):
            found, why = pick(table.get(key, []), how)
            if found:
                return found, why
        found, why = pick(self.by_last.get(key.split()[-1], []), "lastname")
        if found:
            return found, why

        # mononyms ("Gabriel") only resolve inside the club that was named
        if espn_club:
            same = [
                p
                for p in self.index
                if p["club"] == espn_club
                and (
                    _norm(p["display"]).startswith(key)
                    or _norm(p["full"]).startswith(key)
                )
            ]
            if len(same) == 1:
                return same[0], "club+prefix"

        seen = (
            self.by_display.get(key)
            or self.by_full.get(key)
            or self.by_last.get(key.split()[-1])
            or []
        )
        return None, f"ambiguous ({len(seen)} matches)" if seen else "not in big-5"


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
        raw = dict(zip(names, entry.get("stats") or []))
        stats = {}
        for espn_name, key in STAT_NAMES.items():
            try:
                stats[key] = float(raw.get(espn_name) or 0)
            except (TypeError, ValueError):
                stats[key] = 0.0

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

    def __init__(
        self,
        leagues: dict[str, str] = LEAGUES,
        top_n: int = FUT_VALUE_TOP_N,
        value_url: str = VALUE_URL,
    ):
        self.leagues = leagues
        self.top_n = top_n
        self.value_url = value_url
        self._logs: dict[str, list[GameLogData]] = {}
        self.league_status: dict[str, str] = {}
        # filled during fetch_athletes, for the seed report
        self.value_rows: list[dict] = []
        self.resolved: list[dict] = []
        self.unresolved: list[dict] = []

    def fetch_athletes(self) -> list[AthleteData]:
        self.value_rows = fetch_value_ranking(self.value_url)[: self.top_n]

        index = roster_index(self.leagues, self.league_status)
        if not index:
            raise RuntimeError("no ESPN rosters from any league")
        matcher = _Matcher(index)

        self.resolved, self.unresolved, claimed = [], [], {}
        for row in self.value_rows:
            found, why = matcher.find(row["name"], row["club"])
            if found is None:
                self.unresolved.append({**row, "why": why})
                continue
            if found["id"] in claimed:
                # two ranking rows naming one real player
                self.unresolved.append(
                    {**row, "why": f"duplicate of rank {claimed[found['id']]}"}
                )
                continue
            claimed[found["id"]] = row["rank"]
            self.resolved.append({**row, "espn": found})

        athletes = []
        for entry in self.resolved:
            espn = entry["espn"]
            try:
                logs, totals = player_logs(espn["league"], espn["id"])
            except Exception:
                logs, totals = [], {}
            finally:
                time.sleep(THROTTLE_SECONDS)

            self._logs[espn["id"]] = logs
            games = max(len(logs), 1)
            stats = {key: round(value / games, 2) for key, value in totals.items()}
            # the anchor: what the market says this player is worth
            stats["market_value"] = entry["value_m"]
            stats["appearances"] = float(len(logs))
            entry["games"] = len(logs)

            athletes.append(
                AthleteData(
                    name=espn["display"],
                    team=espn["team"],
                    external_ref=espn["id"],
                    position=espn["position"],
                    stats=stats,
                )
            )

        if not athletes:
            raise RuntimeError("no value-ranked players matched an ESPN roster")
        return athletes

    def fetch_game_logs(self, external_ref: str) -> list[GameLogData]:
        # gathered while matching; refetching would double the request count
        return self._logs.get(str(external_ref), [])
