"""Tests for Gemini fallback enrichment of missing sport inputs."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from baseball_domain import MLBGame, MLBGameContext, MLBProbablePitcher
from baseball_module import BaseballDataQualityError, BaseballModule
from basketball_module import BasketballDataQualityError, BasketballModule


class _RecordingEnrichmentProvider:
    def __init__(self, payload: dict[str, Any] | None = None, error: Exception | None = None) -> None:
        self.payload = payload
        self.error = error
        self.calls: list[dict[str, Any]] = []

    def enrich_missing_inputs(self, **kwargs: Any) -> dict[str, Any] | None:
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return self.payload


class _CompleteBasketballStatsProvider:
    last_sources: list = []

    def get_player_stats(self, *, home_team: str, away_team: str, match_date: str) -> list[dict[str, Any]]:
        del home_team, away_team, match_date
        return [_basketball_player()]


class _CompleteBasketballPropsProvider:
    last_sources: list = []

    def get_prop_lines(self, *, players: list[dict[str, Any]], markets: tuple[str, ...]) -> dict[str, Any]:
        del players, markets
        return {
            "LeBron James": {
                "points": {
                    "line": 25.5,
                    "source": "official_props",
                    "sources": [{"source": "official_props", "line": 25.5}],
                }
            }
        }


class _EmptyBasketballPropsProvider:
    last_sources: list = []

    def get_prop_lines(self, *, players: list[dict[str, Any]], markets: tuple[str, ...]) -> dict[str, Any]:
        del players, markets
        return {}


def _basketball_player(**overrides: Any) -> dict[str, Any]:
    player = {
        "player_name": "LeBron James",
        "team": "LAL",
        "position": "SF",
        "minutes_proj": 35.0,
        "usage_rate": 0.28,
        "points_avg": 25.5,
        "points_last5": 27.0,
        "assist_avg": 7.2,
        "assist_last5": 7.8,
        "rebound_avg": 7.5,
        "rebound_last5": 8.0,
        "threes_avg": 2.3,
        "threes_last5": 2.5,
        "three_point_attempts": 5.5,
        "rotation_risk": "locked_in",
        "is_starter": True,
    }
    player.update(overrides)
    return player


def _basketball_enrichment_payload(*, include_line: bool = True) -> dict[str, Any]:
    lines: dict[str, Any] = {}
    if include_line:
        lines = {
            "LeBron James": {
                "points": {
                    "line": 26.5,
                    "source": "PrizePicks",
                    "retrieved_at_utc": "2026-06-01T12:00:00Z",
                    "confidence": "high",
                    "sources": [{"source": "PrizePicks", "line": 26.5}],
                }
            }
        }
    return {
        "players": [_basketball_player()],
        "lines": lines,
        "retrieved_at_utc": "2026-06-01T12:00:00Z",
        "confidence": "high",
        "sources": [{"label": "PrizePicks", "url": "https://example.test/lebron"}],
    }


class TestBasketballGeminiFallbackEnrichment:
    def test_skips_enrichment_when_basketball_inputs_are_complete(self) -> None:
        provider = _RecordingEnrichmentProvider(payload=_basketball_enrichment_payload())
        module = BasketballModule(
            stats_provider=_CompleteBasketballStatsProvider(),
            props_provider=_CompleteBasketballPropsProvider(),
            enrichment_provider=provider,
            allow_deterministic_fallback=False,
        )

        inputs = module.collect_inputs(home_team="Lakers", away_team="Celtics", match_date="2026-06-01")
        scores = module.score(inputs, markets=("points",))

        assert scores
        assert provider.calls == []

    def test_basketball_missing_lines_use_gemini_enrichment_with_provenance(self) -> None:
        provider = _RecordingEnrichmentProvider(payload=_basketball_enrichment_payload())
        module = BasketballModule(
            stats_provider=_CompleteBasketballStatsProvider(),
            props_provider=_EmptyBasketballPropsProvider(),
            enrichment_provider=provider,
            allow_deterministic_fallback=False,
        )

        inputs = module.collect_inputs(home_team="Lakers", away_team="Celtics", match_date="2026-06-01")
        scores = module.score(inputs, markets=("points",))

        assert len(provider.calls) == 1
        assert provider.calls[0]["sport"] == "basketball"
        assert "prop_line:LeBron James:points" in provider.calls[0]["missing_fields"]
        assert scores
        assert scores[0]["line"] == 26.5
        assert scores[0]["input_provenance"]["line"]["source"] == "gemini_enriched"
        assert "gemini_enriched_input" in scores[0]["explainability"]["risk_flags"]
        assert inputs["data_quality"]["enrichment_status"] == "success"

    def test_basketball_incomplete_gemini_output_rejects_without_zero_line_pick(self) -> None:
        provider = _RecordingEnrichmentProvider(payload=_basketball_enrichment_payload(include_line=False))
        module = BasketballModule(
            stats_provider=_CompleteBasketballStatsProvider(),
            props_provider=_EmptyBasketballPropsProvider(),
            enrichment_provider=provider,
            allow_deterministic_fallback=False,
        )

        inputs = module.collect_inputs(home_team="Lakers", away_team="Celtics", match_date="2026-06-01")

        with pytest.raises(BasketballDataQualityError, match="missing prop lines") as exc_info:
            module.score(inputs, markets=("points",))
        assert exc_info.value.reason == "missing_prop_lines"
        assert provider.calls


def _make_schedule_result() -> MagicMock:
    result = MagicMock()
    result.meta.available = True
    result.games = [
        {
            "gamePk": 717001,
            "teams": {
                "home": {"team": {"id": 147, "name": "New York Yankees"}},
                "away": {"team": {"id": 111, "name": "Boston Red Sox"}},
            },
            "gameDate": "2026-05-25T23:05:00Z",
            "venue": {"id": 3313, "name": "Yankee Stadium"},
            "status": {"detailedState": "Scheduled"},
        }
    ]
    return result


def _make_pitcher_only_context() -> MLBGameContext:
    game = MLBGame(
        event_id="717001",
        home_team="New York Yankees",
        away_team="Boston Red Sox",
        venue="Yankee Stadium",
        game_time_utc="2026-05-25T23:05:00Z",
        home_team_id=147,
        away_team_id=111,
        venue_id=3313,
    )
    return MLBGameContext(
        game=game,
        home_probable_pitcher=MLBProbablePitcher(player_name="Gerrit Cole", player_id=543037, confirmed=True),
        away_probable_pitcher=MLBProbablePitcher(player_name="Brayan Bello", player_id=678394, confirmed=True),
    )


def _baseball_batter() -> dict[str, Any]:
    return {
        "player_name": "Aaron Judge",
        "team": "NYY",
        "position": "RF",
        "type": "batter",
        "player_type": "batter",
        "batting_order": 2,
        "hits_per_game": 1.2,
        "hits_last5_per_game": 1.4,
    }


def _baseball_enrichment_payload(*, include_line: bool = True) -> dict[str, Any]:
    lines: dict[str, Any] = {}
    if include_line:
        lines = {
            "Aaron Judge": {
                "hits": {
                    "line": 1.5,
                    "source": "PrizePicks",
                    "retrieved_at_utc": "2026-05-25T12:00:00Z",
                    "confidence": "high",
                    "sources": [{"source": "PrizePicks", "line": 1.5}],
                }
            }
        }
    return {
        "players": [_baseball_batter()],
        "lines": lines,
        "retrieved_at_utc": "2026-05-25T12:00:00Z",
        "confidence": "high",
        "sources": [{"label": "PrizePicks", "url": "https://example.test/judge"}],
    }


class TestBaseballGeminiFallbackEnrichment:
    def test_baseball_pitcher_only_hitter_markets_use_gemini_enrichment(self) -> None:
        service = MagicMock()
        service._schedule.get_schedule.return_value = _make_schedule_result()
        service.collect.return_value = _make_pitcher_only_context()
        provider = _RecordingEnrichmentProvider(payload=_baseball_enrichment_payload())

        module = BaseballModule(collection_service=service, enrichment_provider=provider)
        inputs = module.collect_inputs(
            home_team="New York Yankees",
            away_team="Boston Red Sox",
            match_date="2026-05-25",
        )
        scores = module.score(inputs, markets=("hits",))

        assert len(provider.calls) == 1
        assert provider.calls[0]["sport"] == "baseball"
        assert "batters" in provider.calls[0]["missing_fields"]
        assert scores
        assert scores[0]["player"] == "Aaron Judge"
        assert scores[0]["line"] == 1.5
        assert scores[0]["input_provenance"]["line"]["source"] == "gemini_enriched"
        assert inputs["data_quality"]["enrichment_status"] == "success"

    def test_baseball_incomplete_gemini_output_keeps_rejection(self) -> None:
        service = MagicMock()
        service._schedule.get_schedule.return_value = _make_schedule_result()
        service.collect.return_value = _make_pitcher_only_context()
        provider = _RecordingEnrichmentProvider(payload=_baseball_enrichment_payload(include_line=False))

        module = BaseballModule(collection_service=service, enrichment_provider=provider)
        inputs = module.collect_inputs(
            home_team="New York Yankees",
            away_team="Boston Red Sox",
            match_date="2026-05-25",
        )

        with pytest.raises(BaseballDataQualityError, match="missing prop lines") as exc_info:
            module.score(inputs, markets=("hits",))
        assert exc_info.value.reason == "missing_prop_lines"
        assert provider.calls
