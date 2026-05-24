"""Basketball data collection layer.

Collects and normalizes basketball inputs from provider ports into a
structured context for scoring. Uses fake/placeholder providers until
real adapters are wired in.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ProviderStatus:
    stats: str = "ok"
    injuries: str = "ok"
    lineups: str = "ok"
    odds: str = "ok"


@dataclass
class BasketballPlayerContext:
    player_name: str
    position: str
    team: str
    minutes_proj: float | None = None
    usage_rate: float | None = None
    points_avg: float | None = None
    points_last5: float | None = None
    assist_avg: float | None = None
    assist_last5: float | None = None
    rebound_avg: float | None = None
    rebound_last5: float | None = None
    threes_avg: float | None = None
    threes_last5: float | None = None
    three_point_attempts: float | None = None
    pace_factor: float | None = None
    opp_rebound_rank: int | None = None
    opp_points_rank: int | None = None
    opp_assist_rank: int | None = None
    opp_three_rank: int | None = None
    is_starter: bool | None = None
    injury_status: str | None = None
    rotation_risk: str | None = None
    rest_days: int | None = None
    home_away: str | None = None
    usage_boost: float | None = None
    market_agreement: float | None = None
    line_points: float = 0.0
    line_assists: float = 0.0
    line_rebounds: float = 0.0
    line_threes: float = 0.0

    def to_scoring_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"player_name": self.player_name, "position": self.position}
        optional_fields = (
            "minutes_proj", "usage_rate",
            "points_avg", "points_last5",
            "assist_avg", "assist_last5",
            "rebound_avg", "rebound_last5",
            "threes_avg", "threes_last5",
            "three_point_attempts", "pace_factor",
            "opp_rebound_rank", "opp_points_rank", "opp_assist_rank", "opp_three_rank",
            "rotation_risk", "rest_days", "home_away",
            "usage_boost", "market_agreement",
        )
        for f in optional_fields:
            val = getattr(self, f)
            if val is not None:
                d[f] = val
        d["line_points"] = self.line_points
        d["line_assists"] = self.line_assists
        d["line_rebounds"] = self.line_rebounds
        d["line_threes"] = self.line_threes
        return d


@dataclass
class BasketballContext:
    home_team: str
    away_team: str
    match_date: str
    players: list[BasketballPlayerContext] = field(default_factory=list)
    provider_status: ProviderStatus = field(default_factory=ProviderStatus)
    league: str = "nba"
    pace: float | None = None


@dataclass
class BasketballGameContext:
    home_team: str
    away_team: str
    match_date: str
    league: str = "nba"
    tipoff_utc: str | None = None
    home_pace: float | None = None
    away_pace: float | None = None
    projected_game_pace: float | None = None
    home_defensive_rating: float | None = None
    away_defensive_rating: float | None = None
    home_win_prob: float | None = None
    away_win_prob: float | None = None
    over_under_total: float | None = None
    spread: float | None = None
    home_rest_days: int | None = None
    away_rest_days: int | None = None
    is_playoff: bool = False
    series_game_number: int | None = None
    venue: str | None = None


_FAKE_PLAYERS = [
    BasketballPlayerContext(
        player_name="LeBron James", position="SF", team="LAL",
        minutes_proj=35.0, usage_rate=0.28, points_avg=25.5,
        points_last5=27.0, assist_avg=7.2, assist_last5=7.8,
        rebound_avg=7.5, rebound_last5=8.0, threes_avg=2.3,
        threes_last5=2.5, pace_factor=1.02, opp_rebound_rank=18,
        is_starter=True, line_points=25.5, line_assists=7.5,
        line_rebounds=7.5, line_threes=2.5,
    ),
    BasketballPlayerContext(
        player_name="Anthony Davis", position="PF", team="LAL",
        minutes_proj=34.0, usage_rate=0.27, points_avg=24.0,
        points_last5=26.0, assist_avg=3.2, assist_last5=3.5,
        rebound_avg=10.5, rebound_last5=11.0, threes_avg=1.5,
        threes_last5=1.8, pace_factor=1.02, opp_rebound_rank=18,
        is_starter=True, line_points=24.5, line_assists=3.5,
        line_rebounds=10.5, line_threes=1.5,
    ),
    BasketballPlayerContext(
        player_name="Jayson Tatum", position="SF", team="BOS",
        minutes_proj=36.0, usage_rate=0.30, points_avg=27.0,
        points_last5=29.0, assist_avg=4.5, assist_last5=5.0,
        rebound_avg=8.5, rebound_last5=8.0, threes_avg=3.0,
        threes_last5=3.5, pace_factor=1.0, opp_rebound_rank=12,
        is_starter=True, line_points=27.5, line_assists=4.5,
        line_rebounds=8.5, line_threes=3.5,
    ),
    BasketballPlayerContext(
        player_name="Jaylen Brown", position="SG", team="BOS",
        minutes_proj=34.0, usage_rate=0.26, points_avg=23.0,
        points_last5=22.0, assist_avg=3.5, assist_last5=3.0,
        rebound_avg=5.5, rebound_last5=5.5, threes_avg=2.0,
        threes_last5=2.2, pace_factor=1.0, opp_rebound_rank=12,
        is_starter=True, line_points=23.5, line_assists=3.5,
        line_rebounds=5.5, line_threes=2.5,
    ),
]


def collect_basketball_inputs(
    *,
    home_team: str,
    away_team: str,
    match_date: str,
    league: str | None = None,
    injuries_available: bool = True,
    lineups_available: bool = True,
    stats_available: bool = True,
) -> BasketballContext:
    status = ProviderStatus(
        stats="ok" if stats_available else "unavailable",
        injuries="ok" if injuries_available else "unavailable",
        lineups="ok" if lineups_available else "unavailable",
    )

    players = [_copy_player(p) for p in _FAKE_PLAYERS]

    if not lineups_available:
        for p in players:
            p.is_starter = None

    return BasketballContext(
        home_team=home_team,
        away_team=away_team,
        match_date=match_date,
        players=players,
        provider_status=status,
        league=league or "nba",
    )


def _copy_player(p: BasketballPlayerContext) -> BasketballPlayerContext:
    return BasketballPlayerContext(
        player_name=p.player_name, position=p.position, team=p.team,
        minutes_proj=p.minutes_proj, usage_rate=p.usage_rate,
        points_avg=p.points_avg, points_last5=p.points_last5,
        assist_avg=p.assist_avg, assist_last5=p.assist_last5,
        rebound_avg=p.rebound_avg, rebound_last5=p.rebound_last5,
        threes_avg=p.threes_avg, threes_last5=p.threes_last5,
        three_point_attempts=p.three_point_attempts,
        pace_factor=p.pace_factor, opp_rebound_rank=p.opp_rebound_rank,
        opp_points_rank=p.opp_points_rank, opp_assist_rank=p.opp_assist_rank,
        opp_three_rank=p.opp_three_rank,
        is_starter=p.is_starter, injury_status=p.injury_status,
        rotation_risk=p.rotation_risk, rest_days=p.rest_days,
        home_away=p.home_away, usage_boost=p.usage_boost,
        market_agreement=p.market_agreement,
        line_points=p.line_points, line_assists=p.line_assists,
        line_rebounds=p.line_rebounds, line_threes=p.line_threes,
    )
