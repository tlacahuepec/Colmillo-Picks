"""Tests for basketball sport module skeleton."""

from __future__ import annotations

import logging
from typing import Any

import pytest

from basketball_module import BasketballModule, BasketballDataQualityError
from pick_request import PickRequest
from pipeline_runner import PipelineRunner, PipelineResult
from sport_module import SportModule, SportModuleRegistry


class TestBasketballModuleProtocol:
    def test_basketball_module_satisfies_sport_module_protocol(self) -> None:
        module = BasketballModule()
        assert isinstance(module, SportModule)

    def test_sport_id_is_basketball(self) -> None:
        module = BasketballModule()
        assert module.sport_id == "basketball"

    def test_supported_markets(self) -> None:
        module = BasketballModule()
        expected = {"points", "rebounds", "assists", "threes", "steals", "blocks", "turnovers", "fantasy_score"}
        assert module.supported_markets == expected

    def test_supported_leagues(self) -> None:
        module = BasketballModule()
        assert "nba" in module.supported_leagues


class TestBasketballModuleRegistry:
    def test_basketball_registers_in_sport_module_registry(self) -> None:
        registry = SportModuleRegistry()
        module = BasketballModule()
        registry.register(module)
        assert registry.get("basketball") is module

    def test_basketball_does_not_conflict_with_soccer(self) -> None:
        from sport_module import SoccerModule

        registry = SportModuleRegistry()
        registry.register(SoccerModule())
        registry.register(BasketballModule())
        assert registry.get("soccer").sport_id == "soccer"
        assert registry.get("basketball").sport_id == "basketball"


class TestBasketballPlaceholderScoring:
    def test_collect_inputs_returns_structured_data(self) -> None:
        module = BasketballModule(allow_deterministic_fallback=True)
        inputs = module.collect_inputs(
            home_team="Lakers",
            away_team="Celtics",
            match_date="2026-06-01",
            league="nba",
        )
        assert "home_team" in inputs
        assert "away_team" in inputs
        assert "players" in inputs
        assert len(inputs["players"]) > 0

    def test_score_returns_valid_picks(self) -> None:
        module = BasketballModule(allow_deterministic_fallback=True)
        inputs = module.collect_inputs(
            home_team="Lakers",
            away_team="Celtics",
            match_date="2026-06-01",
        )
        scores = module.score(inputs, markets=("points", "assists"))
        assert len(scores) > 0
        for pick in scores:
            assert "player" in pick
            assert "market" in pick
            assert "score" in pick
            assert "line" in pick
            assert "direction" in pick
            assert "confidence" in pick
            assert pick["market"] in ("points", "assists")

    def test_score_all_markets_when_none_specified(self) -> None:
        module = BasketballModule(allow_deterministic_fallback=True)
        inputs = module.collect_inputs(
            home_team="Lakers",
            away_team="Celtics",
            match_date="2026-06-01",
        )
        scores = module.score(inputs)
        markets_seen = {s["market"] for s in scores}
        assert len(markets_seen) >= 2

    def test_explain_returns_nonempty_string(self) -> None:
        module = BasketballModule()
        pick = {
            "player": "LeBron James",
            "market": "points",
            "direction": "over",
            "line": 25.5,
            "confidence": "high",
            "score": 0.8,
        }
        explanation = module.explain(pick)
        assert isinstance(explanation, str)
        assert len(explanation) > 0
        assert "LeBron James" in explanation


class TestBasketballPipelineIntegration:
    def test_basketball_request_runs_through_pipeline(self) -> None:
        module = BasketballModule(allow_deterministic_fallback=True)
        request = PickRequest(
            sport="basketball",
            event_date="2026-06-01",
            home_team="Lakers",
            away_team="Celtics",
            markets=("points", "rebounds"),
            league="nba",
        )
        runner = PipelineRunner()
        result = runner.run(request=request, module=module)
        assert isinstance(result, PipelineResult)
        assert result.status == "success"
        assert len(result.scores) > 0

    def test_basketball_pipeline_does_not_affect_soccer(self) -> None:
        from sport_module import SoccerModule

        soccer_module = SoccerModule(allow_deterministic_fallback=True)
        request = PickRequest(
            sport="soccer",
            event_date="2026-06-01",
            home_team="Arsenal",
            away_team="Liverpool",
            markets=("passes",),
        )
        runner = PipelineRunner()
        result = runner.run(request=request, module=soccer_module)
        assert result.status == "success"
        assert len(result.scores) > 0


class TestBasketballHardening:
    def test_fallback_disabled_by_default(self) -> None:
        module = BasketballModule()
        assert module._allow_fallback is False

    def test_provider_failure_raises_when_no_fallback(self) -> None:
        module = BasketballModule(allow_deterministic_fallback=False)
        with pytest.raises(BasketballDataQualityError, match="Could not find enough match details"):
            module.collect_inputs(
                home_team="Lakers",
                away_team="Celtics",
                match_date="2026-06-01",
            )

    def test_provider_exception_logged_with_context(self, caplog: pytest.LogCaptureFixture) -> None:
        class _FailingGameProvider:
            def lookup_game(self, **kwargs: Any) -> None:
                raise RuntimeError("API timeout")

        module = BasketballModule(
            game_provider=_FailingGameProvider(),
            allow_deterministic_fallback=True,
        )
        with caplog.at_level(logging.WARNING):
            module.collect_inputs(
                home_team="Lakers",
                away_team="Celtics",
                match_date="2026-06-01",
            )

        assert any("basketball_provider_error" in r.message for r in caplog.records)
        assert any("API timeout" in str(getattr(r, "error", "")) for r in caplog.records)


def _complete_player(name: str, team: str = "LAL") -> dict[str, Any]:
    """Build a player dict with all required fields for all markets."""
    return {
        "player_name": name,
        "team": team,
        "position": "SF",
        "minutes_proj": 34.0,
        "usage_rate": 0.28,
        "points_avg": 25.0,
        "points_last5": 26.0,
        "rebound_avg": 7.0,
        "rebound_last5": 7.5,
        "assist_avg": 6.0,
        "assist_last5": 6.5,
        "threes_avg": 2.5,
        "threes_last5": 2.8,
        "three_point_attempts": 6.0,
    }


def _incomplete_player(name: str, team: str = "BOS", missing: tuple[str, ...] = ("usage_rate",)) -> dict[str, Any]:
    """Build a player dict missing specified fields."""
    p = _complete_player(name, team)
    for field in missing:
        p.pop(field, None)
    return p


def _make_match_inputs(
    players: list[dict[str, Any]],
    lines: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build match_inputs dict suitable for score()."""
    if lines is None:
        lines = {
            p["player_name"]: {"points": 25.5, "rebounds": 7.5, "assists": 6.5, "threes": 2.5}
            for p in players
        }
    return {
        "home_team": "LAL",
        "away_team": "BOS",
        "match_date": "2026-06-01",
        "league": "nba",
        "game": {},
        "players": players,
        "lines": lines,
        "data_quality": {"source": "provider", "enrichment_status": "success"},
    }


class TestPerPlayerExclusion:
    """Test that partial player data excludes only incomplete players."""

    def test_score_succeeds_with_some_players_missing_data(self) -> None:
        """2 complete + 1 incomplete player should produce scores for 2 players only."""
        players = [
            _complete_player("LeBron James", "LAL"),
            _complete_player("Anthony Davis", "LAL"),
            _incomplete_player("Donte DiVincenzo", "BOS", missing=("usage_rate",)),
        ]
        module = BasketballModule()
        inputs = _make_match_inputs(players)
        scores = module.score(inputs, markets=("points",))
        scored_players = {s["player"] for s in scores}
        assert "LeBron James" in scored_players
        assert "Anthony Davis" in scored_players
        assert "Donte DiVincenzo" not in scored_players

    def test_excluded_player_not_in_results(self) -> None:
        """Player missing usage_rate excluded from all markets."""
        players = [
            _complete_player("LeBron James", "LAL"),
            _incomplete_player("Donte DiVincenzo", "BOS", missing=("usage_rate",)),
        ]
        module = BasketballModule()
        inputs = _make_match_inputs(players)
        scores = module.score(inputs, markets=("points", "rebounds", "assists", "threes"))
        scored_players = {s["player"] for s in scores}
        assert "LeBron James" in scored_players
        assert "Donte DiVincenzo" not in scored_players

    def test_player_excluded_from_threes_but_scored_for_points(self) -> None:
        """Player missing three_point_attempts excluded from threes but scored for points."""
        player = _complete_player("Victor Wembanyama", "SAS")
        player.pop("three_point_attempts")
        players = [player]
        module = BasketballModule()
        inputs = _make_match_inputs(players)
        scores = module.score(inputs, markets=("points", "threes"))
        scored_markets = {s["market"] for s in scores if s["player"] == "Victor Wembanyama"}
        assert "points" in scored_markets
        assert "threes" not in scored_markets

    def test_all_players_excluded_raises_data_quality_error(self) -> None:
        """When no player has complete data for any market, still raises."""
        players = [
            _incomplete_player("Player A", "LAL", missing=("usage_rate",)),
            _incomplete_player("Player B", "BOS", missing=("usage_rate",)),
        ]
        module = BasketballModule()
        inputs = _make_match_inputs(players)
        with pytest.raises(BasketballDataQualityError, match="missing basketball player context"):
            module.score(inputs, markets=("points",))

    def test_exclusion_logged(self, caplog: pytest.LogCaptureFixture) -> None:
        """basketball_players_excluded_from_scoring event emitted."""
        players = [
            _complete_player("LeBron James", "LAL"),
            _incomplete_player("Donte DiVincenzo", "BOS", missing=("usage_rate",)),
        ]
        module = BasketballModule()
        inputs = _make_match_inputs(players)
        with caplog.at_level(logging.INFO, logger="colmillo.basketball"):
            module.score(inputs, markets=("points",))
        assert any("basketball_players_excluded" in r.message for r in caplog.records)

    def test_excluded_players_in_data_quality(self) -> None:
        """match_inputs data_quality tracks excluded players."""
        players = [
            _complete_player("LeBron James", "LAL"),
            _incomplete_player("Donte DiVincenzo", "BOS", missing=("usage_rate",)),
        ]
        module = BasketballModule()
        inputs = _make_match_inputs(players)
        module.score(inputs, markets=("points",))
        excluded = inputs["data_quality"].get("excluded_players")
        assert excluded is not None
        assert "Donte DiVincenzo" in str(excluded)
