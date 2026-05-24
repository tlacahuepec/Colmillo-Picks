"""Tests for the SportModule protocol and registry."""

from __future__ import annotations

from typing import Any

import pytest

from sport_module import (
    SportModule,
    SportModuleRegistry,
    UnsupportedSportError,
    get_sport_module,
)


class FakeTestModule:
    """A minimal implementation satisfying the SportModule protocol."""

    @property
    def sport_id(self) -> str:
        return "test_sport"

    @property
    def supported_leagues(self) -> set[str]:
        return {"league_a", "league_b"}

    @property
    def supported_markets(self) -> set[str]:
        return {"market_x", "market_y"}

    def collect_inputs(self, *, home_team: str, away_team: str, match_date: str, league: str | None = None) -> dict[str, Any]:
        return {
            "home_team": home_team,
            "away_team": away_team,
            "match_date": match_date,
            "league": league,
        }

    def score(self, match_inputs: dict[str, Any], *, markets: tuple[str, ...] = ()) -> list[dict[str, Any]]:
        return [{"player": "Test Player", "market": m, "score": 0.5} for m in markets]

    def explain(self, scored_pick: dict[str, Any]) -> str:
        return f"Explanation for {scored_pick.get('player', 'unknown')}"


class TestSportModuleRegistry:
    def test_registry_returns_correct_module_for_soccer(self) -> None:
        module = get_sport_module("soccer")
        assert module.sport_id == "soccer"

    def test_registry_raises_for_unsupported_sport(self) -> None:
        with pytest.raises(UnsupportedSportError) as exc_info:
            get_sport_module("curling")
        assert "curling" in str(exc_info.value)

    def test_registry_register_and_retrieve_custom_module(self) -> None:
        registry = SportModuleRegistry()
        fake = FakeTestModule()
        registry.register(fake)
        retrieved = registry.get("test_sport")
        assert retrieved is fake

    def test_registry_get_raises_for_unknown(self) -> None:
        registry = SportModuleRegistry()
        with pytest.raises(UnsupportedSportError):
            registry.get("nonexistent")


class TestSportModuleContract:
    def test_fake_module_satisfies_protocol(self) -> None:
        fake = FakeTestModule()
        assert isinstance(fake, SportModule)

    def test_fake_module_collect_inputs(self) -> None:
        fake = FakeTestModule()
        inputs = fake.collect_inputs(
            home_team="Team A", away_team="Team B", match_date="2026-05-25"
        )
        assert inputs["home_team"] == "Team A"
        assert inputs["away_team"] == "Team B"

    def test_fake_module_score(self) -> None:
        fake = FakeTestModule()
        inputs = fake.collect_inputs(
            home_team="Team A", away_team="Team B", match_date="2026-05-25"
        )
        scored = fake.score(inputs, markets=("market_x",))
        assert len(scored) == 1
        assert scored[0]["market"] == "market_x"

    def test_fake_module_explain(self) -> None:
        fake = FakeTestModule()
        explanation = fake.explain({"player": "Star Player", "market": "market_x", "score": 0.9})
        assert "Star Player" in explanation

    def test_soccer_module_has_expected_markets(self) -> None:
        module = get_sport_module("soccer")
        assert "passes" in module.supported_markets
        assert "shots" in module.supported_markets

    def test_soccer_module_has_expected_leagues(self) -> None:
        module = get_sport_module("soccer")
        assert len(module.supported_leagues) > 0
