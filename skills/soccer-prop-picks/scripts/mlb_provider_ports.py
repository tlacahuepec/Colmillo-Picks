"""MLB-specific provider port protocols and result types."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@dataclass
class MLBProviderMeta:
    available: bool = False
    source: str = "unknown"
    retrieved_at_utc: str | None = None
    expires_at_utc: str | None = None
    error_message: str | None = None
    provider_status: str = "unavailable"


@dataclass
class MLBScheduleResult:
    meta: MLBProviderMeta = field(default_factory=MLBProviderMeta)
    games: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class ProbablePitcherResult:
    meta: MLBProviderMeta = field(default_factory=MLBProviderMeta)
    home_pitcher: dict[str, Any] | None = None
    away_pitcher: dict[str, Any] | None = None


@dataclass
class MLBLineupsResult:
    meta: MLBProviderMeta = field(default_factory=MLBProviderMeta)
    home_order: list[dict[str, Any]] = field(default_factory=list)
    away_order: list[dict[str, Any]] = field(default_factory=list)
    confirmed: bool = False


@dataclass
class MLBPlayerStatsResult:
    meta: MLBProviderMeta = field(default_factory=MLBProviderMeta)
    player_id: int | None = None
    season_stats: dict[str, Any] = field(default_factory=dict)
    game_log: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class SplitsResult:
    meta: MLBProviderMeta = field(default_factory=MLBProviderMeta)
    splits: dict[str, dict[str, float]] = field(default_factory=dict)


@dataclass
class BullpenResult:
    meta: MLBProviderMeta = field(default_factory=MLBProviderMeta)
    arms: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class MLBWeatherResult:
    meta: MLBProviderMeta = field(default_factory=MLBProviderMeta)
    temp_f: int | None = None
    wind_mph: int | None = None
    wind_direction: str | None = None
    dome: bool = False


@dataclass
class BallparkResult:
    meta: MLBProviderMeta = field(default_factory=MLBProviderMeta)
    park_factor: float = 1.0
    hr_factor: float | None = None
    venue_name: str = ""


@runtime_checkable
class MLBSchedulePort(Protocol):
    def get_schedule(self, *, date: str, team_id: int | None = None) -> MLBScheduleResult: ...


@runtime_checkable
class ProbablePitcherPort(Protocol):
    def get_probable_pitchers(self, *, game_pk: int) -> ProbablePitcherResult: ...


@runtime_checkable
class MLBLineupsPort(Protocol):
    def get_lineups(self, *, game_pk: int) -> MLBLineupsResult: ...


@runtime_checkable
class MLBPlayerStatsPort(Protocol):
    def get_player_stats(self, *, player_id: int, season: int | None = None) -> MLBPlayerStatsResult: ...


@runtime_checkable
class PlayerSplitsPort(Protocol):
    def get_splits(self, *, player_id: int, season: int | None = None) -> SplitsResult: ...


@runtime_checkable
class BullpenPort(Protocol):
    def get_bullpen_state(self, *, team_id: int, date: str) -> BullpenResult: ...


@runtime_checkable
class MLBWeatherPort(Protocol):
    def get_weather(self, *, venue_id: int, game_time_utc: str) -> MLBWeatherResult: ...


@runtime_checkable
class BallparkPort(Protocol):
    def get_ballpark(self, *, venue_id: int) -> BallparkResult: ...
