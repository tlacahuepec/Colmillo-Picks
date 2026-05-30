"""Integration tests for basketball module with real providers wired."""

from __future__ import annotations

import pytest

from basketball_module import BasketballDataQualityError, BasketballModule
from pick_request import PickRequest
from pipeline_runner import PipelineRunner, PipelineResult
from sport_module import get_sport_module


class _FakeGameProvider:
    last_sources: list = []

    def lookup_game(self, *, home_team, away_team, match_date):
        return {
            "home_team": home_team,
            "away_team": away_team,
            "tipoff_utc": "2026-06-01T19:30:00Z",
            "home_pace": 100.2,
            "away_pace": 98.5,
            "projected_game_pace": 99.3,
            "home_defensive_rating": 112.3,
            "away_defensive_rating": 108.7,
            "home_win_prob": 0.55,
            "away_win_prob": 0.45,
            "over_under_total": 224.5,
            "spread": -3.5,
            "home_rest_days": 2,
            "away_rest_days": 1,
            "venue": "Crypto.com Arena",
            "is_playoff": False,
        }


class _FakeStatsProvider:
    last_sources: list = []

    def get_player_stats(self, *, home_team, away_team, match_date):
        return [
            {
                "player_name": "LeBron James", "team": "LAL", "position": "SF",
                "minutes_proj": 35.0, "usage_rate": 0.28,
                "points_avg": 25.5, "points_last5": 27.0,
                "assist_avg": 7.2, "assist_last5": 7.8,
                "rebound_avg": 7.5, "rebound_last5": 8.0,
                "threes_avg": 2.3, "threes_last5": 2.5,
                "three_point_attempts": 5.5,
                "rotation_risk": "locked_in", "is_starter": True,
            },
            {
                "player_name": "Anthony Davis", "team": "LAL", "position": "PF",
                "minutes_proj": 34.0, "usage_rate": 0.27,
                "points_avg": 24.0, "points_last5": 26.0,
                "assist_avg": 3.2, "assist_last5": 3.5,
                "rebound_avg": 10.5, "rebound_last5": 11.0,
                "threes_avg": 1.5, "threes_last5": 1.8,
                "three_point_attempts": 3.0,
                "rotation_risk": "normal", "is_starter": True,
            },
            {
                "player_name": "Jayson Tatum", "team": "BOS", "position": "SF",
                "minutes_proj": 36.0, "usage_rate": 0.30,
                "points_avg": 27.0, "points_last5": 29.0,
                "assist_avg": 4.5, "assist_last5": 5.0,
                "rebound_avg": 8.5, "rebound_last5": 8.0,
                "threes_avg": 3.0, "threes_last5": 3.5,
                "three_point_attempts": 8.0,
                "rotation_risk": "locked_in", "is_starter": True,
            },
        ]


class _FakePropsProvider:
    last_sources: list = []

    def get_prop_lines(self, *, players, markets):
        return {
            "LeBron James": {
                "points": {"line": 25.5, "market_agreement": 0.95, "sources": []},
                "assists": {"line": 7.5, "market_agreement": 0.90, "sources": []},
                "rebounds": {"line": 7.5, "market_agreement": 0.88, "sources": []},
                "threes": {"line": 2.5, "market_agreement": 0.92, "sources": []},
            },
            "Anthony Davis": {
                "points": {"line": 24.5, "market_agreement": 0.93, "sources": []},
                "assists": {"line": 3.5, "market_agreement": 0.85, "sources": []},
                "rebounds": {"line": 10.5, "market_agreement": 0.90, "sources": []},
                "threes": {"line": 1.5, "market_agreement": 0.80, "sources": []},
            },
            "Jayson Tatum": {
                "points": {"line": 27.5, "market_agreement": 0.94, "sources": []},
                "assists": {"line": 4.5, "market_agreement": 0.87, "sources": []},
                "rebounds": {"line": 8.5, "market_agreement": 0.91, "sources": []},
                "threes": {"line": 3.5, "market_agreement": 0.89, "sources": []},
            },
        }


class _FailingProvider:
    last_sources: list = []

    def lookup_game(self, **kwargs):
        raise RuntimeError("provider down")

    def get_player_stats(self, **kwargs):
        raise RuntimeError("provider down")

    def get_prop_lines(self, **kwargs):
        raise RuntimeError("provider down")


class TestBasketballModuleWithProviders:
    def test_collect_inputs_uses_providers(self) -> None:
        module = BasketballModule(
            game_provider=_FakeGameProvider(),
            stats_provider=_FakeStatsProvider(),
            props_provider=_FakePropsProvider(),
        )
        inputs = module.collect_inputs(
            home_team="Lakers", away_team="Celtics", match_date="2026-06-01",
        )
        assert inputs["home_team"] == "Lakers"
        assert inputs["away_team"] == "Celtics"
        assert "game" in inputs
        assert inputs["game"]["home_pace"] == 100.2
        assert inputs["game"]["spread"] == -3.5
        assert len(inputs["players"]) == 3
        assert inputs["players"][0]["player_name"] == "LeBron James"
        assert "lines" in inputs
        assert "LeBron James" in inputs["lines"]

    def test_score_uses_config_driven_scorer(self) -> None:
        module = BasketballModule(
            game_provider=_FakeGameProvider(),
            stats_provider=_FakeStatsProvider(),
            props_provider=_FakePropsProvider(),
        )
        inputs = module.collect_inputs(
            home_team="Lakers", away_team="Celtics", match_date="2026-06-01",
        )
        scores = module.score(inputs, markets=("points", "assists"))
        assert len(scores) > 0
        for pick in scores:
            assert "player" in pick
            assert "market" in pick
            assert "score" in pick
            assert "confidence" in pick
            assert "explainability" in pick
            assert pick["market"] in ("points", "assists")

    def test_score_includes_explainability(self) -> None:
        module = BasketballModule(
            game_provider=_FakeGameProvider(),
            stats_provider=_FakeStatsProvider(),
            props_provider=_FakePropsProvider(),
        )
        inputs = module.collect_inputs(
            home_team="Lakers", away_team="Celtics", match_date="2026-06-01",
        )
        scores = module.score(inputs, markets=("points",))
        pick = scores[0]
        assert "top_contributing_factors" in pick["explainability"]
        assert "risk_flags" in pick["explainability"]


class TestBasketballModuleFallback:
    def test_fallback_when_all_providers_fail(self) -> None:
        module = BasketballModule(
            game_provider=_FailingProvider(),
            stats_provider=_FailingProvider(),
            props_provider=_FailingProvider(),
            allow_deterministic_fallback=True,
        )
        inputs = module.collect_inputs(
            home_team="Lakers", away_team="Celtics", match_date="2026-06-01",
        )
        assert inputs["home_team"] == "Lakers"
        assert len(inputs["players"]) > 0
        scores = module.score(inputs, markets=("points",))
        assert len(scores) > 0

    def test_partial_prop_provider_failure_rejects_missing_lines_without_enrichment(self) -> None:
        module = BasketballModule(
            game_provider=_FakeGameProvider(),
            stats_provider=_FakeStatsProvider(),
            props_provider=_FailingProvider(),
        )
        inputs = module.collect_inputs(
            home_team="Lakers", away_team="Celtics", match_date="2026-06-01",
        )
        assert len(inputs["players"]) == 3
        with pytest.raises(BasketballDataQualityError, match="missing prop lines"):
            module.score(inputs, markets=("points",))


class TestBasketballModuleRegistered:
    def test_get_sport_module_returns_basketball(self) -> None:
        module = get_sport_module("basketball")
        assert module.sport_id == "basketball"

    def test_basketball_pipeline_end_to_end(self) -> None:
        module = BasketballModule(
            game_provider=_FakeGameProvider(),
            stats_provider=_FakeStatsProvider(),
            props_provider=_FakePropsProvider(),
        )
        request = PickRequest(
            sport="basketball",
            event_date="2026-06-01",
            home_team="Lakers",
            away_team="Celtics",
            markets=("points", "rebounds", "assists", "threes"),
            league="nba",
        )
        runner = PipelineRunner()
        result = runner.run(request=request, module=module)
        assert isinstance(result, PipelineResult)
        assert result.status == "success"
        assert len(result.scores) > 0
        for pick in result.scores:
            assert pick["market"] in ("points", "rebounds", "assists", "threes")
            assert 0 <= pick["score"] <= 1
