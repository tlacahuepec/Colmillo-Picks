"""Shared provider port interfaces for multi-sport data access.

These protocols define the contracts that sport modules consume.
Infrastructure adapters implement them for specific data sources.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@dataclass
class EventResult:
    found: bool = False
    event_id: str | None = None
    home_team: str | None = None
    away_team: str | None = None
    event_date: str | None = None
    venue: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class OddsResult:
    available: bool = False
    home_win_prob: float | None = None
    away_win_prob: float | None = None
    draw_prob: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class PlayerStatsResult:
    available: bool = False
    player_id: str | None = None
    stats: dict[str, Any] = field(default_factory=dict)


@dataclass
class InjuryResult:
    available: bool = False
    injuries: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class LineupsResult:
    available: bool = False
    status: str | None = None
    players: list[Any] = field(default_factory=list)


@dataclass
class PropLinesResult:
    available: bool = False
    lines: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class ProviderUnavailableResult:
    available: bool = False
    reason: str = ""


@runtime_checkable
class EventLookupPort(Protocol):
    def lookup_event(
        self, *, sport: str, home_team: str, away_team: str, event_date: str, league: str | None = None
    ) -> EventResult: ...


@runtime_checkable
class OddsPort(Protocol):
    def get_odds(self, *, sport: str, event_id: str) -> OddsResult: ...


@runtime_checkable
class PlayerStatsPort(Protocol):
    def get_player_stats(
        self, *, sport: str, player_id: str, league: str | None = None
    ) -> PlayerStatsResult: ...


@runtime_checkable
class InjuryReportPort(Protocol):
    def get_injuries(self, *, sport: str, team_id: str) -> InjuryResult: ...


@runtime_checkable
class LineupsPort(Protocol):
    def get_lineups(self, *, sport: str, event_id: str) -> LineupsResult: ...


@runtime_checkable
class PropLinesPort(Protocol):
    def get_prop_lines(
        self, *, sport: str, event_id: str, markets: tuple[str, ...] = ()
    ) -> PropLinesResult: ...
