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


@dataclass
class MLBGame:
    event_id: str
    home_team: str
    away_team: str
    venue: str
    game_time_utc: str
    status: str = "scheduled"
    home_team_id: int | None = None
    away_team_id: int | None = None
    venue_id: int | None = None
    double_header: bool = False
    game_number: int = 1


@dataclass
class MLBProbablePitcher:
    player_name: str
    player_id: int | None = None
    team: str = ""
    handedness: str | None = None
    confirmed: bool = False
    era: float | None = None
    whip: float | None = None
    k_per_9: float | None = None
    bb_per_9: float | None = None
    innings_pitched_season: float | None = None
    last_start_date: str | None = None
    days_rest: int | None = None


@dataclass
class MLBBattingOrderSlot:
    position: int
    player_name: str
    player_id: int | None = None
    handedness: str | None = None
    field_position: str | None = None


@dataclass
class MLBBattingOrder:
    team: str
    confirmed: bool = False
    slots: list[MLBBattingOrderSlot] = field(default_factory=list)
    source_timestamp_utc: str | None = None


@dataclass
class MLBBullpenArm:
    player_name: str
    player_id: int | None = None
    innings_last_3_days: float = 0.0
    days_since_last_appearance: int | None = None
    available: bool = True


@dataclass
class MLBBullpenState:
    team: str
    arms: list[MLBBullpenArm] = field(default_factory=list)
    source_timestamp_utc: str | None = None


@dataclass
class MLBWeather:
    temp_f: int | None = None
    wind_mph: int | None = None
    wind_direction: str | None = None
    humidity_pct: int | None = None
    dome: bool = False
    precip_probability: float | None = None
    source: str = "unknown"
    retrieved_at_utc: str | None = None


@dataclass
class MLBPropLine:
    player_name: str
    market: str
    line: float
    over_odds: int | None = None
    under_odds: int | None = None
    source: str = "user_input"
    retrieved_at_utc: str | None = None


@dataclass
class MLBPlayerSplits:
    player_name: str
    player_id: int | None = None
    vs_lhp: dict[str, float] = field(default_factory=dict)
    vs_rhp: dict[str, float] = field(default_factory=dict)
    home: dict[str, float] = field(default_factory=dict)
    away: dict[str, float] = field(default_factory=dict)
    last_7_days: dict[str, float] = field(default_factory=dict)
    last_14_days: dict[str, float] = field(default_factory=dict)
    last_30_days: dict[str, float] = field(default_factory=dict)
    vs_team: dict[str, float] = field(default_factory=dict)


@dataclass
class MLBGameContext:
    game: MLBGame
    home_probable_pitcher: MLBProbablePitcher | None = None
    away_probable_pitcher: MLBProbablePitcher | None = None
    home_batting_order: MLBBattingOrder | None = None
    away_batting_order: MLBBattingOrder | None = None
    home_bullpen: MLBBullpenState | None = None
    away_bullpen: MLBBullpenState | None = None
    weather: MLBWeather | None = None
    ballpark: BallparkInfo | None = None
    prop_lines: list[MLBPropLine] = field(default_factory=list)
    batters: list[BaseballBatter] = field(default_factory=list)
    pitchers: list[BaseballPitcher] = field(default_factory=list)
    splits: list[MLBPlayerSplits] = field(default_factory=list)
    provider_status: BaseballProviderStatus = field(default_factory=BaseballProviderStatus)
    should_reject_prediction: bool = False
    rejection_reasons: list[str] = field(default_factory=list)
    retrieved_at_utc: str | None = None
