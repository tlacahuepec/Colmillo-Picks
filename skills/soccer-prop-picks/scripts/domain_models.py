"""Colmillo domain models — provider-agnostic data representations.

These models normalize data from any provider into a consistent shape
that the scoring and rendering layers consume.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class MappingError(Exception):
    """Raised when a provider payload cannot be mapped to a domain model."""


@dataclass
class ColmilloEvent:
    event_id: str
    home_team: str
    away_team: str
    event_date: str
    sport: str
    venue: str | None = None


@dataclass
class ColmilloTeam:
    team_id: str
    team_name: str
    sport: str


@dataclass
class ColmilloPlayer:
    player_id: str
    player_name: str
    team_id: str
    position: str
    sport: str
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class ColmilloPropLine:
    player_id: str
    market: str
    line: float
    sport: str


@dataclass
class ColmilloInjury:
    player_id: str
    status: str
    reason: str
    sport: str


def map_event_payload(payload: dict[str, Any]) -> ColmilloEvent:
    required = ("event_id", "home_team", "away_team", "event_date", "sport")
    missing = [k for k in required if k not in payload]
    if missing:
        raise MappingError(f"Missing required fields: {', '.join(missing)}")
    return ColmilloEvent(
        event_id=payload["event_id"],
        home_team=payload["home_team"],
        away_team=payload["away_team"],
        event_date=payload["event_date"],
        sport=payload["sport"],
        venue=payload.get("venue"),
    )


def map_player_payload(payload: dict[str, Any]) -> ColmilloPlayer:
    required = ("player_id", "player_name", "team_id", "sport")
    missing = [k for k in required if k not in payload]
    if missing:
        raise MappingError(f"Missing required fields: {', '.join(missing)}")
    return ColmilloPlayer(
        player_id=payload["player_id"],
        player_name=payload["player_name"],
        team_id=payload["team_id"],
        position=payload.get("position", ""),
        sport=payload["sport"],
        extra=payload.get("extra", {}),
    )


def map_prop_line_payload(payload: dict[str, Any]) -> ColmilloPropLine:
    required = ("player_id", "market", "line", "sport")
    missing = [k for k in required if k not in payload]
    if missing:
        raise MappingError(f"Missing required fields: {', '.join(missing)}")
    return ColmilloPropLine(
        player_id=payload["player_id"],
        market=payload["market"],
        line=payload["line"],
        sport=payload["sport"],
    )
