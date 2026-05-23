"""Baseball domain models.

Provider-agnostic representations of baseball-specific concepts needed
for prop scoring: batters, pitchers, ballpark, weather, lineup status.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class BaseballBatter:
    player_name: str
    team: str
    position: str
    handedness: str | None = None
    batting_order: int | None = None
    in_confirmed_lineup: bool | None = None
    avg: float | None = None
    obp: float | None = None
    slg: float | None = None
    hits_last5: int | None = None
    total_bases_last5: int | None = None
    runs_last5: int | None = None
    rbi_last5: int | None = None
    hr_last5: int | None = None
    walks_last5: int | None = None


@dataclass
class BaseballPitcher:
    player_name: str
    team: str
    handedness: str | None = None
    is_starter: bool | None = None
    era: float | None = None
    whip: float | None = None
    k_per_9: float | None = None
    bb_per_9: float | None = None
    recent_workload_innings: float | None = None
    pitch_count_last_start: int | None = None
    days_rest: int | None = None


@dataclass
class BallparkInfo:
    name: str
    park_factor: float = 1.0
    hr_factor: float | None = None
    dimensions: dict[str, Any] = field(default_factory=dict)


@dataclass
class BaseballProviderStatus:
    stats: str = "ok"
    lineup: str = "ok"
    weather: str = "ok"
    bullpen: str = "ok"
    odds: str = "ok"


@dataclass
class BaseballContext:
    home_team: str
    away_team: str
    match_date: str
    batters: list[BaseballBatter] = field(default_factory=list)
    pitchers: list[BaseballPitcher] = field(default_factory=list)
    ballpark: BallparkInfo | None = None
    weather: dict[str, Any] = field(default_factory=dict)
    provider_status: BaseballProviderStatus = field(default_factory=BaseballProviderStatus)
    league: str = "mlb"
