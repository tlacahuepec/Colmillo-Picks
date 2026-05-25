"""Tests for Streamlit UI form logic."""

from __future__ import annotations

import datetime

import pytest


def test_construct_match_query_from_parts() -> None:
    from services.ui.app import _construct_match_query

    result = _construct_match_query("Bayern Munich", "Stuttgart", "2026-05-23")
    assert result == "Bayern Munich - Stuttgart 2026-05-23"


def test_construct_match_query_strips_whitespace() -> None:
    from services.ui.app import _construct_match_query

    result = _construct_match_query("  Bayern Munich  ", "  Stuttgart  ", "  2026-05-23  ")
    assert result == "Bayern Munich - Stuttgart 2026-05-23"


def test_construct_match_query_requires_home_team() -> None:
    from services.ui.app import _construct_match_query

    with pytest.raises(ValueError, match="home team"):
        _construct_match_query("", "Stuttgart", "2026-05-23")

    with pytest.raises(ValueError, match="home team"):
        _construct_match_query("   ", "Stuttgart", "2026-05-23")


def test_construct_match_query_requires_away_team() -> None:
    from services.ui.app import _construct_match_query

    with pytest.raises(ValueError, match="away team"):
        _construct_match_query("Bayern Munich", "", "2026-05-23")

    with pytest.raises(ValueError, match="away team"):
        _construct_match_query("Bayern Munich", "   ", "2026-05-23")


def test_construct_match_query_validates_date_format() -> None:
    from services.ui.app import _construct_match_query

    _construct_match_query("Bayern Munich", "Stuttgart", "2026-05-23")
    _construct_match_query("Bayern Munich", "Stuttgart", "2026-12-31")

    with pytest.raises(ValueError, match="date"):
        _construct_match_query("Bayern Munich", "Stuttgart", "05-23-2026")

    with pytest.raises(ValueError, match="date"):
        _construct_match_query("Bayern Munich", "Stuttgart", "today")

    with pytest.raises(ValueError, match="date"):
        _construct_match_query("Bayern Munich", "Stuttgart", "")


def test_build_payload_omits_league_field() -> None:
    from services.ui.app import _build_pick_payload

    payload = _build_pick_payload(
        sport="soccer",
        home_team="Bayern Munich",
        away_team="Stuttgart",
        date=datetime.date(2026, 5, 23),
        top_n=3,
        use_llm_enrichment=False,
        allow_fallback=False,
    )
    assert "league" not in payload


def test_build_payload_omits_fixture_provider_field() -> None:
    from services.ui.app import _build_pick_payload

    payload = _build_pick_payload(
        sport="soccer",
        home_team="Bayern Munich",
        away_team="Stuttgart",
        date=datetime.date(2026, 5, 23),
        top_n=3,
        use_llm_enrichment=False,
        allow_fallback=False,
    )
    assert "fixture_provider" not in payload


def test_build_payload_llm_enrichment_on() -> None:
    from services.ui.app import _build_pick_payload

    payload = _build_pick_payload(
        sport="soccer",
        home_team="Bayern Munich",
        away_team="Stuttgart",
        date=datetime.date(2026, 5, 23),
        top_n=3,
        use_llm_enrichment=True,
        allow_fallback=False,
    )
    assert payload["use_llm"] is True
    assert "llm_provider" not in payload


def test_build_payload_llm_enrichment_off() -> None:
    from services.ui.app import _build_pick_payload

    payload = _build_pick_payload(
        sport="soccer",
        home_team="Bayern Munich",
        away_team="Stuttgart",
        date=datetime.date(2026, 5, 23),
        top_n=3,
        use_llm_enrichment=False,
        allow_fallback=False,
    )
    assert payload.get("use_llm") is not True


def test_build_payload_allow_fallback() -> None:
    from services.ui.app import _build_pick_payload

    payload = _build_pick_payload(
        sport="soccer",
        home_team="Bayern Munich",
        away_team="Stuttgart",
        date=datetime.date(2026, 5, 23),
        top_n=5,
        use_llm_enrichment=False,
        allow_fallback=True,
    )
    assert payload["allow_deterministic_fallback"] is True


class TestBuildStructuredPayload:
    """Tests for the structured payload format."""

    def test_structured_payload_shape(self) -> None:
        from services.ui.app import _build_pick_payload

        payload = _build_pick_payload(
            sport="soccer",
            home_team="Bayern Munich",
            away_team="Stuttgart",
            date=datetime.date(2026, 5, 23),
            top_n=3,
            use_llm_enrichment=False,
            allow_fallback=False,
        )
        assert payload["sport"] == "soccer"
        assert payload["event_date"] == "2026-05-23"
        assert payload["home_team"] == "Bayern Munich"
        assert payload["away_team"] == "Stuttgart"
        assert payload["top_n"] == 3
        assert payload["allow_deterministic_fallback"] is False
        assert "match_query" not in payload

    def test_date_serialized_to_iso(self) -> None:
        from services.ui.app import _build_pick_payload

        payload = _build_pick_payload(
            sport="soccer",
            home_team="Arsenal",
            away_team="Liverpool",
            date=datetime.date(2026, 12, 31),
            top_n=2,
            use_llm_enrichment=False,
            allow_fallback=False,
        )
        assert payload["event_date"] == "2026-12-31"

    def test_whitespace_stripped_from_teams(self) -> None:
        from services.ui.app import _build_pick_payload

        payload = _build_pick_payload(
            sport="soccer",
            home_team="  Bayern Munich  ",
            away_team="  Stuttgart  ",
            date=datetime.date(2026, 5, 23),
            top_n=3,
            use_llm_enrichment=False,
            allow_fallback=False,
        )
        assert payload["home_team"] == "Bayern Munich"
        assert payload["away_team"] == "Stuttgart"

    def test_empty_home_team_raises(self) -> None:
        from services.ui.app import _build_pick_payload

        with pytest.raises(ValueError, match="home team"):
            _build_pick_payload(
                sport="soccer",
                home_team="",
                away_team="Stuttgart",
                date=datetime.date(2026, 5, 23),
                top_n=3,
                use_llm_enrichment=False,
                allow_fallback=False,
            )

    def test_empty_away_team_raises(self) -> None:
        from services.ui.app import _build_pick_payload

        with pytest.raises(ValueError, match="away team"):
            _build_pick_payload(
                sport="soccer",
                home_team="Bayern Munich",
                away_team="   ",
                date=datetime.date(2026, 5, 23),
                top_n=3,
                use_llm_enrichment=False,
                allow_fallback=False,
            )

    def test_llm_flag_included_when_true(self) -> None:
        from services.ui.app import _build_pick_payload

        payload = _build_pick_payload(
            sport="soccer",
            home_team="Bayern Munich",
            away_team="Stuttgart",
            date=datetime.date(2026, 5, 23),
            top_n=5,
            use_llm_enrichment=True,
            allow_fallback=False,
        )
        assert payload["use_llm"] is True

    def test_llm_flag_absent_when_false(self) -> None:
        from services.ui.app import _build_pick_payload

        payload = _build_pick_payload(
            sport="soccer",
            home_team="Bayern Munich",
            away_team="Stuttgart",
            date=datetime.date(2026, 5, 23),
            top_n=5,
            use_llm_enrichment=False,
            allow_fallback=False,
        )
        assert payload.get("use_llm") is not True


class TestBaseballPayload:
    """Tests for baseball-specific payload construction."""

    def test_baseball_payload_with_teams_does_not_raise(self) -> None:
        """Regression: selecting baseball must not lose home/away values.

        The Generate form conditionally renders league/market widgets when
        sport == "baseball". Without stable widget keys, Streamlit resets
        text_input values to their default ("") on the first submit after
        sport changes — causing a spurious "home team is required" error.
        This test verifies the payload builder accepts valid team names
        regardless of sport, confirming the data path works when widget
        keys are stable.
        """
        from services.ui.app import _build_pick_payload

        payload = _build_pick_payload(
            sport="baseball",
            home_team="New York Yankees",
            away_team="Boston Red Sox",
            date=datetime.date(2026, 5, 25),
            top_n=5,
            use_llm_enrichment=False,
            allow_fallback=False,
            markets=["hits", "home_runs"],
            league="mlb",
        )
        assert payload["home_team"] == "New York Yankees"
        assert payload["away_team"] == "Boston Red Sox"
        assert payload["sport"] == "baseball"

    def test_baseball_payload_includes_markets(self) -> None:
        from services.ui.app import _build_pick_payload

        payload = _build_pick_payload(
            sport="baseball",
            home_team="New York Yankees",
            away_team="Boston Red Sox",
            date=datetime.date(2026, 5, 25),
            top_n=5,
            use_llm_enrichment=False,
            allow_fallback=False,
            markets=["hits", "home_runs", "strikeouts"],
        )
        assert payload["sport"] == "baseball"
        assert payload["markets"] == ["hits", "home_runs", "strikeouts"]

    def test_baseball_payload_includes_league(self) -> None:
        from services.ui.app import _build_pick_payload

        payload = _build_pick_payload(
            sport="baseball",
            home_team="New York Yankees",
            away_team="Boston Red Sox",
            date=datetime.date(2026, 5, 25),
            top_n=5,
            use_llm_enrichment=False,
            allow_fallback=False,
            league="mlb",
        )
        assert payload["league"] == "mlb"

    def test_baseball_payload_omits_markets_when_none(self) -> None:
        from services.ui.app import _build_pick_payload

        payload = _build_pick_payload(
            sport="baseball",
            home_team="New York Yankees",
            away_team="Boston Red Sox",
            date=datetime.date(2026, 5, 25),
            top_n=5,
            use_llm_enrichment=False,
            allow_fallback=False,
        )
        assert "markets" not in payload

    def test_baseball_payload_omits_league_when_none(self) -> None:
        from services.ui.app import _build_pick_payload

        payload = _build_pick_payload(
            sport="baseball",
            home_team="New York Yankees",
            away_team="Boston Red Sox",
            date=datetime.date(2026, 5, 25),
            top_n=5,
            use_llm_enrichment=False,
            allow_fallback=False,
        )
        assert "league" not in payload

    def test_soccer_payload_unaffected_by_new_params(self) -> None:
        from services.ui.app import _build_pick_payload

        payload = _build_pick_payload(
            sport="soccer",
            home_team="Bayern Munich",
            away_team="Stuttgart",
            date=datetime.date(2026, 5, 23),
            top_n=3,
            use_llm_enrichment=False,
            allow_fallback=False,
        )
        assert "markets" not in payload
        assert "league" not in payload
        assert payload["sport"] == "soccer"
