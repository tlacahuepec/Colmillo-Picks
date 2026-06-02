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


class _BestOfNEnrichmentProvider:
    """Mock provider that supports enrich_missing_inputs_best_of_n."""

    def __init__(self, payloads: list[dict[str, Any] | None]) -> None:
        self._payloads = list(payloads)
        self.calls: list[dict[str, Any]] = []
        self.model = "test-model"

    def enrich_missing_inputs(self, **kwargs: Any) -> dict[str, Any] | None:
        self.calls.append(kwargs)
        if self._payloads:
            return self._payloads[0]
        return None

    def enrich_missing_inputs_best_of_n(self, **kwargs: Any) -> tuple[dict[str, Any] | None, dict[str, Any]]:
        self.calls.append(kwargs)
        best = None
        for p in self._payloads:
            if p is not None:
                best = p
                break
        if best is None:
            return None, {
                "strategy": "best_of_n",
                "n_attempts": len(self._payloads),
                "successful_attempts": 0,
                "winner_attempt": 0,
                "winner_temperature": None,
                "selection_reason": "all_attempts_failed",
                "populated_field_count": 0,
                "avg_confidence": 0.0,
                "critical_null_count": 0,
            }
        return best, {
            "strategy": "best_of_n",
            "n_attempts": len(self._payloads),
            "successful_attempts": sum(1 for p in self._payloads if p is not None),
            "winner_attempt": self._payloads.index(best) + 1,
            "winner_temperature": 0.7 if self._payloads.index(best) > 0 else None,
            "selection_reason": "highest_populated_fields",
            "populated_field_count": 4,
            "avg_confidence": 0.75,
            "critical_null_count": 0,
        }


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


class TestBasketballBestOfNIntegration:
    def test_basketball_best_of_n_selects_richer_second_attempt(self) -> None:
        rich_payload = _basketball_enrichment_payload()
        provider = _BestOfNEnrichmentProvider(payloads=[None, rich_payload])
        module = BasketballModule(
            stats_provider=_CompleteBasketballStatsProvider(),
            props_provider=_EmptyBasketballPropsProvider(),
            enrichment_provider=provider,
            allow_deterministic_fallback=False,
        )

        inputs = module.collect_inputs(home_team="Lakers", away_team="Celtics", match_date="2026-06-01")
        scores = module.score(inputs, markets=("points",))

        assert len(provider.calls) == 1
        assert scores
        assert scores[0]["line"] == 26.5

    def test_basketball_best_of_n_metadata_in_data_quality(self) -> None:
        payload = _basketball_enrichment_payload()
        provider = _BestOfNEnrichmentProvider(payloads=[payload])
        module = BasketballModule(
            stats_provider=_CompleteBasketballStatsProvider(),
            props_provider=_EmptyBasketballPropsProvider(),
            enrichment_provider=provider,
            allow_deterministic_fallback=False,
        )

        inputs = module.collect_inputs(home_team="Lakers", away_team="Celtics", match_date="2026-06-01")
        module.score(inputs, markets=("points",))

        data_quality = inputs["data_quality"]
        assert "enrichment_decision" in data_quality
        decision = data_quality["enrichment_decision"]
        assert decision["strategy"] == "best_of_n"
        assert "winner_attempt" in decision
        assert "selection_reason" in decision


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


class TestBaseballBestOfNIntegration:
    def test_baseball_best_of_n_selects_richer_result(self) -> None:
        service = MagicMock()
        service._schedule.get_schedule.return_value = _make_schedule_result()
        service.collect.return_value = _make_pitcher_only_context()
        payload = _baseball_enrichment_payload()
        provider = _BestOfNEnrichmentProvider(payloads=[payload])

        module = BaseballModule(collection_service=service, enrichment_provider=provider)
        inputs = module.collect_inputs(
            home_team="New York Yankees",
            away_team="Boston Red Sox",
            match_date="2026-05-25",
        )
        scores = module.score(inputs, markets=("hits",))

        assert len(provider.calls) == 1
        assert scores
        assert scores[0]["player"] == "Aaron Judge"
        assert scores[0]["line"] == 1.5
        data_quality = inputs["data_quality"]
        assert "enrichment_decision" in data_quality
        assert data_quality["enrichment_decision"]["strategy"] == "best_of_n"


class _MultiShotClient:
    """Mock LLM client that returns different results per call, tracking temperature."""

    def __init__(self, responses: list[dict[str, Any]]) -> None:
        self._responses = list(responses)
        self.calls: list[dict[str, Any]] = []
        self.last_sources: list = []

    def generate_structured(
        self, *, system_prompt: str, user_prompt: str, schema: dict, temperature: float | None = None
    ) -> dict:
        self.calls.append({"temperature": temperature})
        if not self._responses:
            return {}
        return self._responses.pop(0)


class _FailingThenSuccessClient:
    """Mock LLM client that raises on first call, succeeds on later calls."""

    def __init__(self, *, fail_count: int, success_response: dict[str, Any]) -> None:
        self._fail_count = fail_count
        self._success_response = success_response
        self._call_index = 0
        self.calls: list[dict[str, Any]] = []
        self.last_sources: list = []

    def generate_structured(
        self, *, system_prompt: str, user_prompt: str, schema: dict, temperature: float | None = None
    ) -> dict:
        self.calls.append({"temperature": temperature})
        self._call_index += 1
        if self._call_index <= self._fail_count:
            raise RuntimeError("simulated LLM failure")
        return self._success_response


class TestBestOfNEnrichment:
    def _enrich_kwargs(self) -> dict[str, Any]:
        return {
            "sport": "basketball",
            "home_team": "OKC",
            "away_team": "SAS",
            "match_date": "2026-05-30",
            "league": "nba",
            "requested_markets": ("points",),
            "missing_fields": ["player_stats", "prop_lines"],
            "players": [],
            "lines": {},
            "game": {},
            "official_context": {},
        }

    def test_best_of_n_returns_richest_result(self) -> None:
        from missing_input_enrichment import GeminiMissingInputEnrichmentProvider

        sparse = {
            "players": [{"player_name": "Shai", "minutes_proj": 35.0}],
            "lines": {},
            "confidence": "medium",
        }
        rich = {
            "players": [
                {
                    "player_name": "Shai",
                    "minutes_proj": 35.0,
                    "usage_rate": 0.30,
                    "points_avg": 31.0,
                    "points_last5": 33.0,
                }
            ],
            "lines": {
                "Shai": {
                    "points": {
                        "line": 30.5,
                        "source": "PrizePicks",
                        "sources": [{"source": "PrizePicks", "line": 30.5}],
                    }
                }
            },
            "confidence": "high",
        }
        client = _MultiShotClient([sparse, rich])
        provider = GeminiMissingInputEnrichmentProvider(client=client, model="test")

        required = {"points": ("minutes_proj", "usage_rate", "points_avg", "points_last5")}
        result, metadata = provider.enrich_missing_inputs_best_of_n(
            **self._enrich_kwargs(),
            n_attempts=2,
            temperatures=(None, 0.7),
            required_fields_map=required,
        )

        assert result is not None
        assert result["players"][0]["usage_rate"] == 0.30
        assert metadata["winner_attempt"] == 2
        assert metadata["winner_temperature"] == 0.7
        assert metadata["successful_attempts"] == 2

    def test_best_of_n_first_attempt_wins_when_all_equal(self) -> None:
        from missing_input_enrichment import GeminiMissingInputEnrichmentProvider

        response = {
            "players": [{"player_name": "Shai", "minutes_proj": 35.0}],
            "lines": {},
            "confidence": "medium",
        }
        client = _MultiShotClient([response.copy(), response.copy()])
        provider = GeminiMissingInputEnrichmentProvider(client=client, model="test")

        result, metadata = provider.enrich_missing_inputs_best_of_n(
            **self._enrich_kwargs(),
            n_attempts=2,
            temperatures=(None, 0.7),
        )

        assert result is not None
        assert metadata["winner_attempt"] == 1

    def test_best_of_n_single_attempt_mode(self) -> None:
        from missing_input_enrichment import GeminiMissingInputEnrichmentProvider

        response = {
            "players": [{"player_name": "Shai", "minutes_proj": 35.0}],
            "lines": {},
            "confidence": "high",
        }
        client = _MultiShotClient([response])
        provider = GeminiMissingInputEnrichmentProvider(client=client, model="test")

        result, metadata = provider.enrich_missing_inputs_best_of_n(
            **self._enrich_kwargs(),
            n_attempts=1,
            temperatures=(None,),
        )

        assert result is not None
        assert metadata["n_attempts"] == 1
        assert metadata["successful_attempts"] == 1

    def test_best_of_n_all_fail_returns_none(self) -> None:
        from missing_input_enrichment import GeminiMissingInputEnrichmentProvider

        client = _FailingThenSuccessClient(fail_count=3, success_response={})
        provider = GeminiMissingInputEnrichmentProvider(client=client, model="test")

        result, metadata = provider.enrich_missing_inputs_best_of_n(
            **self._enrich_kwargs(),
            n_attempts=3,
            temperatures=(None, 0.7, 1.0),
        )

        assert result is None
        assert metadata["successful_attempts"] == 0
        assert metadata["strategy"] == "best_of_n"

    def test_best_of_n_some_attempts_raise_still_returns_best(self) -> None:
        from missing_input_enrichment import GeminiMissingInputEnrichmentProvider

        good_response = {
            "players": [{"player_name": "Shai", "minutes_proj": 35.0, "usage_rate": 0.30}],
            "lines": {},
            "confidence": "high",
        }
        client = _FailingThenSuccessClient(fail_count=1, success_response=good_response)
        provider = GeminiMissingInputEnrichmentProvider(client=client, model="test")

        result, metadata = provider.enrich_missing_inputs_best_of_n(
            **self._enrich_kwargs(),
            n_attempts=3,
            temperatures=(None, 0.7, 1.0),
        )

        assert result is not None
        assert metadata["successful_attempts"] == 2
        assert metadata["winner_attempt"] >= 2

    def test_best_of_n_decision_metadata_recorded(self) -> None:
        from missing_input_enrichment import GeminiMissingInputEnrichmentProvider

        response = {
            "players": [{"player_name": "Shai", "minutes_proj": 35.0}],
            "lines": {},
            "confidence": "medium",
        }
        client = _MultiShotClient([response])
        provider = GeminiMissingInputEnrichmentProvider(client=client, model="test")

        _, metadata = provider.enrich_missing_inputs_best_of_n(
            **self._enrich_kwargs(),
            n_attempts=1,
            temperatures=(None,),
        )

        assert "strategy" in metadata
        assert metadata["strategy"] == "best_of_n"
        assert "winner_attempt" in metadata
        assert "winner_temperature" in metadata
        assert "selection_reason" in metadata
        assert "populated_field_count" in metadata
        assert "avg_confidence" in metadata
        assert "critical_null_count" in metadata
