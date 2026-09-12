"""Sport-agnostic ingest interface.

Each sport implements a SportAdapter that knows how to reach its own data
source and flatten the result into AthleteData. Nothing downstream of this
module should know which sport it is handling.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date


@dataclass
class AthleteData:
    """One athlete, as returned by any sport's adapter."""

    name: str
    team: str
    external_ref: str
    stats: dict[str, float] = field(default_factory=dict)
    # the source's own position code, where it publishes one
    position: str | None = None


@dataclass
class GameLogData:
    """One athlete's single game, already scored by the sport's own formula."""

    game_date: date
    perf_score: float
    # GameLog's three shared stat columns, whatever they mean for this sport
    pts: float = 0.0
    reb: float = 0.0
    ast: float = 0.0


class SportAdapter(ABC):
    """Base for per-sport ingest adapters."""

    sport: str

    @abstractmethod
    def fetch_athletes(self) -> list[AthleteData]:
        """Fetch athletes and their stats from this sport's data source."""
        raise NotImplementedError

    def fetch_game_logs(self, external_ref: str) -> list[GameLogData]:
        """Per-game logs, oldest first. Sports with a bespoke loader skip this."""
        raise NotImplementedError
