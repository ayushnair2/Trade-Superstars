"""Sport-agnostic ingest interface.

Each sport implements a SportAdapter that knows how to reach its own data
source and flatten the result into AthleteData. Nothing downstream of this
module should know which sport it is handling.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class AthleteData:
    """One athlete, as returned by any sport's adapter."""

    name: str
    team: str
    external_ref: str
    stats: dict[str, float] = field(default_factory=dict)


class SportAdapter(ABC):
    """Base for per-sport ingest adapters."""

    sport: str

    @abstractmethod
    def fetch_athletes(self) -> list[AthleteData]:
        """Fetch athletes and their stats from this sport's data source."""
        raise NotImplementedError
