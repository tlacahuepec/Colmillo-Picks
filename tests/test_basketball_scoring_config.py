"""Tests for config-driven basketball scoring engine."""

from __future__ import annotations

import json
from pathlib import Path

from basketball_scoring import score_basketball_props


CONFIG_PATH = (
    Path(__file__).resolve().parents[1]
    / "skills"
    / "soccer-prop-picks"
    / "config.basketball_scoring_weights.json"
)


class TestConfigLoads:
    def test_config_file_exists(self) -> None:
        assert CONFIG_PATH.exists()

    def test_config_is_valid_json(self) -> None:
        config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        assert "global" in config
        assert "points" in config
        assert "rebounds" in config
        assert "assists" in config
        assert "threes" in config
        assert "calibration" in config

    def test_factor_weights_sum_to_one(self) -> None:
        config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        for market in ("points", "rebounds", "assists", "threes"):
            weights = config[market]["factor_weights"]
            total = sum(weights.values())
            assert abs(total - 1.0) < 0.01, f"{market} weights sum to {total}"


class TestExplainability:
    def test_output_includes_top_contributing_factors(self) -> None:
        player = _player(minutes_proj=36, usage_rate=0.30, points_avg=25.0, points_last5=28.0)
        scores = score_basketball_props([player], markets=("points",))
        pick = scores[0]
        assert "top_contributing_factors" in pick["explainability"]
        factors = pick["explainability"]["top_contributing_factors"]
        assert len(factors) >= 1
        assert "factor" in factors[0]
        assert "score" in factors[0]
        assert "weight" in factors[0]

    def test_factors_sorted_by_weighted_contribution(self) -> None:
        player = _player(minutes_proj=36, usage_rate=0.30, points_avg=25.0, points_last5=28.0)
        scores = score_basketball_props([player], markets=("points",))
        factors = scores[0]["explainability"]["top_contributing_factors"]
        contributions = [f["score"] * f["weight"] for f in factors]
        assert contributions == sorted(contributions, reverse=True)


class TestDirectionResolution:
    def test_over_direction_when_projecting_above_line(self) -> None:
        player = _player(
            points_avg=28.0, points_last5=30.0, line_points=22.5,
            minutes_proj=36, usage_rate=0.30,
        )
        scores = score_basketball_props([player], markets=("points",))
        assert scores[0]["direction"] == "over"

    def test_under_direction_when_projecting_below_line(self) -> None:
        player = _player(
            points_avg=15.0, points_last5=12.0, line_points=22.5,
            minutes_proj=24, usage_rate=0.18,
        )
        scores = score_basketball_props([player], markets=("points",))
        assert scores[0]["direction"] == "under"


class TestConfidenceThresholds:
    def test_high_confidence_for_strong_signal(self) -> None:
        player = _player(
            minutes_proj=38, usage_rate=0.32, points_avg=30.0, points_last5=33.0,
            pace_factor=1.10, home_away="home", rest_days=2,
        )
        scores = score_basketball_props([player], markets=("points",))
        assert scores[0]["confidence"] in ("high", "medium")

    def test_low_confidence_with_missing_data(self) -> None:
        player = {"player_name": "Sparse Player", "line_points": 20.5}
        scores = score_basketball_props([player], markets=("points",))
        assert scores[0]["confidence"] == "low"
        assert "missing_data" in scores[0]["explainability"]["risk_flags"]


class TestRestDaysFactor:
    def test_back_to_back_lowers_score(self) -> None:
        rested = _player(rest_days=2, minutes_proj=34, usage_rate=0.26)
        b2b = _player(rest_days=0, minutes_proj=34, usage_rate=0.26)
        rested_scores = score_basketball_props([rested], markets=("points",))
        b2b_scores = score_basketball_props([b2b], markets=("points",))
        assert rested_scores[0]["score"] > b2b_scores[0]["score"]


class TestHomeAwayFactor:
    def test_home_scores_higher_than_away(self) -> None:
        home = _player(home_away="home", minutes_proj=34, usage_rate=0.26)
        away = _player(home_away="away", minutes_proj=34, usage_rate=0.26)
        home_scores = score_basketball_props([home], markets=("points",))
        away_scores = score_basketball_props([away], markets=("points",))
        assert home_scores[0]["score"] > away_scores[0]["score"]


class TestPaceFactor:
    def test_fast_pace_increases_score(self) -> None:
        fast = _player(pace_factor=1.10, minutes_proj=34, usage_rate=0.26)
        slow = _player(pace_factor=0.90, minutes_proj=34, usage_rate=0.26)
        fast_scores = score_basketball_props([fast], markets=("points",))
        slow_scores = score_basketball_props([slow], markets=("points",))
        assert fast_scores[0]["score"] > slow_scores[0]["score"]


def _player(
    *,
    player_name: str = "Test Player",
    position: str = "SF",
    minutes_proj: float | None = 34.0,
    usage_rate: float | None = 0.26,
    points_avg: float | None = 22.0,
    points_last5: float | None = 24.0,
    assist_avg: float | None = 5.0,
    assist_last5: float | None = 5.5,
    rebound_avg: float | None = 7.0,
    rebound_last5: float | None = 7.0,
    threes_avg: float | None = 2.5,
    threes_last5: float | None = 2.5,
    pace_factor: float | None = 1.0,
    opp_rebound_rank: int | None = 15,
    opp_points_rank: int | None = 15,
    opp_assist_rank: int | None = 15,
    opp_three_rank: int | None = 15,
    rest_days: int | None = 1,
    home_away: str | None = None,
    usage_boost: float | None = None,
    line_points: float = 22.5,
    line_assists: float = 5.5,
    line_rebounds: float = 7.5,
    line_threes: float = 2.5,
) -> dict:
    d: dict = {"player_name": player_name, "position": position}
    if minutes_proj is not None:
        d["minutes_proj"] = minutes_proj
    if usage_rate is not None:
        d["usage_rate"] = usage_rate
    if points_avg is not None:
        d["points_avg"] = points_avg
    if points_last5 is not None:
        d["points_last5"] = points_last5
    if assist_avg is not None:
        d["assist_avg"] = assist_avg
    if assist_last5 is not None:
        d["assist_last5"] = assist_last5
    if rebound_avg is not None:
        d["rebound_avg"] = rebound_avg
    if rebound_last5 is not None:
        d["rebound_last5"] = rebound_last5
    if threes_avg is not None:
        d["threes_avg"] = threes_avg
    if threes_last5 is not None:
        d["threes_last5"] = threes_last5
    if pace_factor is not None:
        d["pace_factor"] = pace_factor
    if opp_rebound_rank is not None:
        d["opp_rebound_rank"] = opp_rebound_rank
    if opp_points_rank is not None:
        d["opp_points_rank"] = opp_points_rank
    if opp_assist_rank is not None:
        d["opp_assist_rank"] = opp_assist_rank
    if opp_three_rank is not None:
        d["opp_three_rank"] = opp_three_rank
    if rest_days is not None:
        d["rest_days"] = rest_days
    if home_away is not None:
        d["home_away"] = home_away
    if usage_boost is not None:
        d["usage_boost"] = usage_boost
    d["line_points"] = line_points
    d["line_assists"] = line_assists
    d["line_rebounds"] = line_rebounds
    d["line_threes"] = line_threes
    return d
