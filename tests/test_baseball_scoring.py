"""Tests for baseball config-driven scoring engine."""

from __future__ import annotations

import json
import tempfile
from typing import Any

from baseball_scoring import (
    score_baseball_props,
    _compute_factor,
    _determine_confidence,
    _load_config,
    _resolve_direction,
)


def _batter_player(**overrides: Any) -> dict[str, Any]:
    defaults: dict[str, Any] = {
        "player_name": "Aaron Judge",
        "player_type": "batter",
        "team": "NYY",
        "batting_order": 2,
        "handedness": "R",
        "opposing_pitcher_hand": "L",
        "hits_per_game": 1.5,
        "hits_last5_per_game": 1.6,
        "tb_per_game": 2.8,
        "tb_last5_per_game": 3.0,
        "runs_per_game": 0.9,
        "runs_last5_per_game": 1.0,
        "rbi_per_game": 1.2,
        "rbi_last5_per_game": 1.4,
        "hr_per_game": 0.35,
        "hr_last5_per_game": 0.4,
        "bb_per_game": 0.8,
        "bb_last5_per_game": 0.8,
        "park_factor": 1.05,
        "hr_factor": 1.15,
        "temp_f": 78,
        "wind_mph": 12,
        "wind_direction": "out",
        "team_implied_total": 4.8,
        "home_away": "home",
        "market_agreement": 0.7,
        "line_hits": 1.5,
        "line_total_bases": 2.5,
        "line_runs": 0.5,
        "line_rbi": 1.5,
        "line_home_runs": 0.5,
        "line_walks": 0.5,
        "line_strikeouts": 1.5,
    }
    defaults.update(overrides)
    return defaults


def _pitcher_player(**overrides: Any) -> dict[str, Any]:
    defaults: dict[str, Any] = {
        "player_name": "Gerrit Cole",
        "player_type": "pitcher",
        "team": "NYY",
        "handedness": "R",
        "k_per_game": 8.5,
        "k_last5_per_game": 9.0,
        "outs_per_game": 18.6,
        "outs_last5_per_game": 19.0,
        "days_rest": 5,
        "recent_innings": 12.0,
        "max_innings": 30.0,
        "opp_k_rate": 0.25,
        "home_away": "home",
        "market_agreement": 0.65,
        "line_strikeouts": 7.5,
        "line_pitcher_outs": 17.5,
    }
    defaults.update(overrides)
    return defaults


class TestScoringHappyPath:
    def test_scores_all_batter_markets(self) -> None:
        players = [_batter_player()]
        batter_markets = ("hits", "total_bases", "runs", "rbi", "home_runs", "walks")
        results = score_baseball_props(players, markets=batter_markets)
        assert len(results) == 6
        markets_returned = {r["market"] for r in results}
        assert markets_returned == set(batter_markets)

    def test_scores_pitcher_markets(self) -> None:
        players = [_pitcher_player()]
        pitcher_markets = ("strikeouts", "pitcher_outs")
        results = score_baseball_props(players, markets=pitcher_markets)
        assert len(results) == 2
        markets_returned = {r["market"] for r in results}
        assert markets_returned == set(pitcher_markets)

    def test_returns_expected_structure(self) -> None:
        players = [_batter_player()]
        results = score_baseball_props(players, markets=("hits",))
        assert len(results) == 1
        pick = results[0]
        assert "player" in pick
        assert "market" in pick
        assert "line" in pick
        assert "direction" in pick
        assert "score" in pick
        assert "confidence" in pick
        assert "explainability" in pick
        assert "risk_flags" in pick["explainability"]
        assert "top_contributing_factors" in pick["explainability"]

    def test_score_is_clipped_0_to_1(self) -> None:
        player = _batter_player(
            hits_per_game=3.0,
            hits_last5_per_game=5.0,
            park_factor=2.0,
            temp_f=110,
            team_implied_total=12.0,
            market_agreement=1.0,
        )
        results = score_baseball_props([player], markets=("hits",))
        assert results[0]["score"] <= 1.0
        assert results[0]["score"] >= 0.0


class TestFactorComputation:
    def test_lineup_position_first_bat_highest(self) -> None:
        config = _load_config()
        market_config = config["hits"]
        calibration = config.get("calibration", {})
        player_first = _batter_player(batting_order=1)
        player_ninth = _batter_player(batting_order=9)
        score_first = _compute_factor(
            "lineup_position_opportunity", player_first, "hits", market_config, calibration
        )
        score_ninth = _compute_factor(
            "lineup_position_opportunity", player_ninth, "hits", market_config, calibration
        )
        assert score_first > score_ninth

    def test_pitcher_matchup_platoon_advantage(self) -> None:
        config = _load_config()
        market_config = config["hits"]
        calibration = config.get("calibration", {})
        player = _batter_player(handedness="L", opposing_pitcher_hand="R")
        score = _compute_factor(
            "pitcher_matchup_handedness", player, "hits", market_config, calibration
        )
        assert score > 0.5

    def test_pitcher_matchup_same_hand_penalty(self) -> None:
        config = _load_config()
        market_config = config["hits"]
        calibration = config.get("calibration", {})
        player = _batter_player(handedness="L", opposing_pitcher_hand="L")
        score = _compute_factor(
            "pitcher_matchup_handedness", player, "hits", market_config, calibration
        )
        assert score < 0.5

    def test_recent_form_hot_streak(self) -> None:
        config = _load_config()
        market_config = config["hits"]
        calibration = config.get("calibration", {})
        player = _batter_player(hits_per_game=1.0, hits_last5_per_game=2.0)
        score = _compute_factor(
            "recent_form_momentum", player, "hits", market_config, calibration
        )
        assert score > 0.6

    def test_recent_form_cold_streak(self) -> None:
        config = _load_config()
        market_config = config["hits"]
        calibration = config.get("calibration", {})
        player = _batter_player(hits_per_game=1.5, hits_last5_per_game=0.6)
        score = _compute_factor(
            "recent_form_momentum", player, "hits", market_config, calibration
        )
        assert score < 0.4

    def test_ballpark_factor_high(self) -> None:
        config = _load_config()
        market_config = config["hits"]
        calibration = config.get("calibration", {})
        player = _batter_player(park_factor=1.15)
        score = _compute_factor(
            "ballpark_factor", player, "hits", market_config, calibration
        )
        assert score > 0.5

    def test_ballpark_hr_factor_used_for_home_runs(self) -> None:
        config = _load_config()
        market_config = config["home_runs"]
        calibration = config.get("calibration", {})
        player = _batter_player(park_factor=0.90, hr_factor=1.30)
        score = _compute_factor(
            "ballpark_factor", player, "home_runs", market_config, calibration
        )
        assert score > 0.5

    def test_weather_hot_boosts(self) -> None:
        config = _load_config()
        market_config = config["hits"]
        calibration = config.get("calibration", {})
        player = _batter_player(temp_f=90)
        score = _compute_factor(
            "weather_impact", player, "hits", market_config, calibration
        )
        assert score > 0.55

    def test_weather_cold_suppresses(self) -> None:
        config = _load_config()
        market_config = config["hits"]
        calibration = config.get("calibration", {})
        player = _batter_player(temp_f=40)
        score = _compute_factor(
            "weather_impact", player, "hits", market_config, calibration
        )
        assert score < 0.45

    def test_wind_out_boosts(self) -> None:
        config = _load_config()
        market_config = config["hits"]
        calibration = config.get("calibration", {})
        player_out = _batter_player(wind_direction="out", temp_f=75)
        player_in = _batter_player(wind_direction="in", temp_f=75)
        score_out = _compute_factor(
            "weather_impact", player_out, "hits", market_config, calibration
        )
        score_in = _compute_factor(
            "weather_impact", player_in, "hits", market_config, calibration
        )
        assert score_out > score_in

    def test_rest_days_well_rested(self) -> None:
        config = _load_config()
        market_config = config["pitcher_outs"]
        calibration = config.get("calibration", {})
        player = _pitcher_player(days_rest=6)
        score = _compute_factor(
            "rest_days", player, "pitcher_outs", market_config, calibration
        )
        assert score > 0.5

    def test_home_away_home_bonus(self) -> None:
        config = _load_config()
        market_config = config["hits"]
        calibration = config.get("calibration", {})
        player_home = _batter_player(home_away="home")
        player_away = _batter_player(home_away="away")
        score_home = _compute_factor(
            "home_away_adjustment", player_home, "hits", market_config, calibration
        )
        score_away = _compute_factor(
            "home_away_adjustment", player_away, "hits", market_config, calibration
        )
        assert score_home > score_away


class TestConfidenceAndDirection:
    def test_high_confidence_above_threshold(self) -> None:
        thresholds = {"high": 0.76, "medium": 0.60}
        result = _determine_confidence(0.80, [], thresholds)
        assert result == "high"

    def test_medium_confidence_in_range(self) -> None:
        thresholds = {"high": 0.76, "medium": 0.60}
        result = _determine_confidence(0.65, [], thresholds)
        assert result == "medium"

    def test_low_confidence_below_threshold(self) -> None:
        thresholds = {"high": 0.76, "medium": 0.60}
        result = _determine_confidence(0.45, [], thresholds)
        assert result == "low"

    def test_missing_data_forces_low(self) -> None:
        thresholds = {"high": 0.76, "medium": 0.60}
        result = _determine_confidence(0.85, ["missing_data"], thresholds)
        assert result == "low"

    def test_direction_over_when_projected_above_line(self) -> None:
        player = _batter_player(hits_per_game=1.5, hits_last5_per_game=2.0)
        result = _resolve_direction(player, "hits", 1.5)
        assert result == "over"

    def test_direction_under_when_projected_below_line(self) -> None:
        player = _batter_player(hits_per_game=0.8, hits_last5_per_game=0.9)
        result = _resolve_direction(player, "hits", 1.5)
        assert result == "under"


class TestConfigLoading:
    def test_loads_default_config(self) -> None:
        config = _load_config()
        assert "global" in config
        assert "hits" in config
        assert "calibration" in config

    def test_custom_config_path(self) -> None:
        custom = {
            "global": {"top_k": 3, "model_version": "test"},
            "hits": {"factor_weights": {"market_agreement": 1.0}, "position_scores": {}},
            "calibration": {"confidence_thresholds": {"high": 0.80, "medium": 0.50}},
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(custom, f)
            f.flush()
            config = _load_config(config_path=f.name)
        assert config["global"]["top_k"] == 3

    def test_unknown_market_skipped(self) -> None:
        players = [_batter_player()]
        results = score_baseball_props(players, markets=("nonexistent_market",))
        assert results == []


class TestDegradedInput:
    def test_missing_player_fields_still_scores(self) -> None:
        player = {
            "player_name": "Unknown",
            "player_type": "batter",
            "line_hits": 1.5,
        }
        results = score_baseball_props([player], markets=("hits",))
        assert len(results) == 1
        assert results[0]["score"] >= 0.0
        assert results[0]["score"] <= 1.0
        assert "missing_data" in results[0]["explainability"]["risk_flags"]

    def test_empty_players_returns_empty(self) -> None:
        results = score_baseball_props([])
        assert results == []

    def test_partial_config_uses_defaults(self) -> None:
        custom = {
            "global": {"top_k": 5, "model_version": "test"},
            "hits": {"factor_weights": {"market_agreement": 1.0}, "position_scores": {}},
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(custom, f)
            f.flush()
            results = score_baseball_props(
                [_batter_player()], markets=("hits",), config_path=f.name
            )
        assert len(results) == 1
        assert results[0]["confidence"] in ("high", "medium", "low")


class TestZeroLineRejection:
    """Defense-in-depth: scoring must never produce picks with line=0 or missing line."""

    def test_zero_line_player_excluded_from_results(self) -> None:
        player = _batter_player(line_hits=0)
        results = score_baseball_props([player], markets=("hits",))
        assert results == []

    def test_missing_line_key_excluded_from_results(self) -> None:
        player = _batter_player()
        del player["line_hits"]
        results = score_baseball_props([player], markets=("hits",))
        assert results == []

    def test_valid_nonzero_line_still_scores(self) -> None:
        player = _batter_player(line_hits=1.5)
        results = score_baseball_props([player], markets=("hits",))
        assert len(results) == 1
        assert results[0]["line"] == 1.5
