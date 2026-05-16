"""Base interface for sportsbook availability adapters.

Adapters expose a single-pick availability lookup and a batch helper that can be
reused by concrete sportsbook integrations.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Pick:
    player: str
    market: str
    line: float


@dataclass(frozen=True)
class AvailabilityResult:
    available: bool
    platform: str
    odds: float | None
    url: str | None
    last_checked: datetime


@dataclass(frozen=True)
class AdapterRuntimeConfig:
    rate_limit_per_second: float = 1.0
    max_retries: int = 2
    retry_backoff_seconds: float = 0.5


class SportsbookAvailabilityAdapter(ABC):
    def __init__(self, *, platform: str, config: AdapterRuntimeConfig | None = None) -> None:
        self.platform = platform
        self.config = config or AdapterRuntimeConfig()

    @abstractmethod
    def check_availability(self, player: str, market: str, line: float) -> AvailabilityResult:
        """Check availability for one player prop line on this adapter's platform."""

    def check_batch(self, picks: list[Pick]) -> list[AvailabilityResult]:
        return [self.check_availability(pick.player, pick.market, pick.line) for pick in picks]

