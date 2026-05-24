"""Tests for Colmillo domain models and provider payload mappers."""

from __future__ import annotations

import pytest

from domain_models import (
    ColmilloEvent,
    ColmilloPlayer,
    ColmilloPropLine,
    MappingError,
    map_event_payload,
    map_player_payload,
    map_prop_line_payload,
)


class TestColmilloEventModel:
    def test_event_from_valid_payload(self) -> None:
        payload = {
            "event_id": "EVT-123",
            "home_team": "Arsenal",
            "away_team": "Liverpool",
            "event_date": "2026-06-01",
            "sport": "soccer",
            "venue": "Emirates Stadium",
        }
        event = map_event_payload(payload)
        assert isinstance(event, ColmilloEvent)
        assert event.event_id == "EVT-123"
        assert event.home_team == "Arsenal"
        assert event.sport == "soccer"

    def test_event_missing_required_field_raises_mapping_error(self) -> None:
        payload = {"home_team": "Arsenal"}
        with pytest.raises(MappingError) as exc_info:
            map_event_payload(payload)
        assert "event_id" in str(exc_info.value) or "away_team" in str(exc_info.value)


class TestColmilloPlayerModel:
    def test_player_from_valid_payload(self) -> None:
        payload = {
            "player_id": "P1",
            "player_name": "Bukayo Saka",
            "team_id": "ARS",
            "position": "FWD",
            "sport": "soccer",
        }
        player = map_player_payload(payload)
        assert isinstance(player, ColmilloPlayer)
        assert player.player_name == "Bukayo Saka"
        assert player.position == "FWD"

    def test_player_with_extra_sport_fields(self) -> None:
        payload = {
            "player_id": "P2",
            "player_name": "LeBron James",
            "team_id": "LAL",
            "position": "SF",
            "sport": "basketball",
            "extra": {"ppg": 25.5},
        }
        player = map_player_payload(payload)
        assert player.sport == "basketball"
        assert player.extra["ppg"] == 25.5

    def test_player_missing_id_raises_mapping_error(self) -> None:
        payload = {"player_name": "Nobody", "team_id": "X", "sport": "soccer"}
        with pytest.raises(MappingError):
            map_player_payload(payload)


class TestColmilloPropLineModel:
    def test_prop_line_from_valid_payload(self) -> None:
        payload = {
            "player_id": "P1",
            "market": "passes",
            "line": 55.5,
            "sport": "soccer",
        }
        prop = map_prop_line_payload(payload)
        assert isinstance(prop, ColmilloPropLine)
        assert prop.market == "passes"
        assert prop.line == 55.5

    def test_prop_line_missing_market_raises_mapping_error(self) -> None:
        payload = {"player_id": "P1", "line": 50.0, "sport": "soccer"}
        with pytest.raises(MappingError):
            map_prop_line_payload(payload)


class TestDomainModelsAreProviderAgnostic:
    def test_event_has_no_provider_specific_fields(self) -> None:
        event = ColmilloEvent(
            event_id="E1", home_team="A", away_team="B",
            event_date="2026-06-01", sport="soccer",
        )
        attrs = vars(event)
        assert "api_response" not in attrs
        assert "raw_json" not in attrs

    def test_player_supports_any_sport(self) -> None:
        soccer_player = ColmilloPlayer(
            player_id="P1", player_name="Saka", team_id="ARS",
            position="FWD", sport="soccer",
        )
        basketball_player = ColmilloPlayer(
            player_id="P2", player_name="LeBron", team_id="LAL",
            position="SF", sport="basketball",
        )
        assert soccer_player.sport == "soccer"
        assert basketball_player.sport == "basketball"
