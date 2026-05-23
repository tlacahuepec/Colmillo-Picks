"""Unit tests for the sport-aware PickRequest model and validation."""

from __future__ import annotations

import pytest

from pick_request import (
    SPORT_MARKETS,
    SUPPORTED_SPORTS,
    PickRequest,
    PickRequestValidationError,
    pick_request_from_legacy_dict,
    pick_request_to_legacy_dict,
    validate_pick_request,
)


class TestPickRequestValidation:
    def test_valid_soccer_request(self) -> None:
        req = PickRequest(
            sport="soccer",
            event_date="2026-05-25",
            home_team="Arsenal",
            away_team="Liverpool",
            markets=("passes", "shots"),
        )
        validate_pick_request(req)

    def test_valid_basketball_request(self) -> None:
        req = PickRequest(
            sport="basketball",
            event_date="2026-05-25",
            home_team="Lakers",
            away_team="Celtics",
            markets=("points", "rebounds", "assists"),
            league="nba",
        )
        validate_pick_request(req)

    def test_valid_baseball_request(self) -> None:
        req = PickRequest(
            sport="baseball",
            event_date="2026-05-25",
            home_team="Yankees",
            away_team="Red Sox",
            markets=("strikeouts", "hits"),
            league="mlb",
        )
        validate_pick_request(req)

    def test_unsupported_sport_raises_error(self) -> None:
        req = PickRequest(
            sport="cricket",
            event_date="2026-05-25",
            home_team="Team A",
            away_team="Team B",
            markets=("runs",),
        )
        with pytest.raises(PickRequestValidationError) as exc_info:
            validate_pick_request(req)
        assert "cricket" in exc_info.value.errors[0]

    def test_invalid_market_for_sport(self) -> None:
        req = PickRequest(
            sport="basketball",
            event_date="2026-05-25",
            home_team="Lakers",
            away_team="Celtics",
            markets=("passes",),
        )
        with pytest.raises(PickRequestValidationError) as exc_info:
            validate_pick_request(req)
        assert "passes" in exc_info.value.errors[0]

    def test_invalid_date_format(self) -> None:
        req = PickRequest(
            sport="soccer",
            event_date="25-05-2026",
            home_team="Arsenal",
            away_team="Liverpool",
            markets=("passes",),
        )
        with pytest.raises(PickRequestValidationError) as exc_info:
            validate_pick_request(req)
        assert "date" in exc_info.value.errors[0].lower()

    def test_invalid_league_for_sport(self) -> None:
        req = PickRequest(
            sport="soccer",
            event_date="2026-05-25",
            home_team="Arsenal",
            away_team="Liverpool",
            markets=("passes",),
            league="nba",
        )
        with pytest.raises(PickRequestValidationError) as exc_info:
            validate_pick_request(req)
        assert "nba" in exc_info.value.errors[0]

    def test_multiple_errors_collected(self) -> None:
        req = PickRequest(
            sport="cricket",
            event_date="bad-date",
            home_team="A",
            away_team="B",
            markets=("unknown_market",),
            top_n=10,
        )
        with pytest.raises(PickRequestValidationError) as exc_info:
            validate_pick_request(req)
        assert len(exc_info.value.errors) >= 2

    def test_top_n_out_of_range(self) -> None:
        req = PickRequest(
            sport="soccer",
            event_date="2026-05-25",
            home_team="Arsenal",
            away_team="Liverpool",
            markets=("passes",),
            top_n=10,
        )
        with pytest.raises(PickRequestValidationError) as exc_info:
            validate_pick_request(req)
        assert "top_n" in exc_info.value.errors[0]


class TestLegacyAdapters:
    def test_legacy_dict_produces_correct_pick_request(self) -> None:
        legacy = {"match_query": "juve - milan today", "top_n": 3, "use_llm": False}
        req = pick_request_from_legacy_dict(legacy)
        assert req.sport == "soccer"
        assert req.home_team == "Juve"
        assert req.away_team == "Milan"
        assert req.markets == ("passes", "shots")
        assert req.top_n == 3

    def test_legacy_dict_with_competition(self) -> None:
        legacy = {
            "match_query": "arsenal - liverpool 2026-06-01",
            "top_n": 5,
            "use_llm": True,
            "llm_provider": "gemini",
            "llm_model": "gemini-pro",
            "competition": "Premier League",
        }
        req = pick_request_from_legacy_dict(legacy)
        assert req.sport == "soccer"
        assert req.home_team == "Arsenal"
        assert req.away_team == "Liverpool"
        assert req.event_date == "2026-06-01"
        assert req.use_llm is True
        assert req.llm_provider == "gemini"

    def test_pick_request_to_legacy_dict_round_trip(self) -> None:
        req = PickRequest(
            sport="soccer",
            event_date="2026-05-25",
            home_team="Arsenal",
            away_team="Liverpool",
            markets=("passes", "shots"),
            top_n=3,
            league="premier_league",
        )
        legacy = pick_request_to_legacy_dict(req)
        assert legacy["match_query"] == "Arsenal - Liverpool 2026-05-25"
        assert legacy["top_n"] == 3
        assert legacy["competition"] == "premier_league"


class TestConstants:
    def test_supported_sports_contains_expected(self) -> None:
        assert "soccer" in SUPPORTED_SPORTS
        assert "basketball" in SUPPORTED_SPORTS
        assert "baseball" in SUPPORTED_SPORTS

    def test_soccer_markets(self) -> None:
        assert "passes" in SPORT_MARKETS["soccer"]
        assert "shots" in SPORT_MARKETS["soccer"]

    def test_basketball_markets(self) -> None:
        assert "points" in SPORT_MARKETS["basketball"]
        assert "rebounds" in SPORT_MARKETS["basketball"]

    def test_baseball_markets(self) -> None:
        assert "strikeouts" in SPORT_MARKETS["baseball"]
        assert "hits" in SPORT_MARKETS["baseball"]
