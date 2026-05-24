"""Tests for sport-aware market registry."""

from __future__ import annotations

import pytest

from market_registry import (
    Market,
    MarketRegistry,
    UnsupportedMarketError,
    get_default_registry,
)


class TestMarketModel:
    def test_market_has_required_fields(self) -> None:
        m = Market(
            id="passes",
            display_name="Passes",
            sport="soccer",
            value_type="float",
            sides=("over", "under"),
        )
        assert m.id == "passes"
        assert m.display_name == "Passes"
        assert m.sport == "soccer"
        assert m.value_type == "float"
        assert m.sides == ("over", "under")


class TestMarketRegistrySoccer:
    def test_soccer_markets_registered(self) -> None:
        registry = get_default_registry()
        soccer_markets = registry.get_markets_for_sport("soccer")
        ids = {m.id for m in soccer_markets}
        assert "passes" in ids
        assert "shots" in ids

    def test_soccer_market_by_id(self) -> None:
        registry = get_default_registry()
        m = registry.get_market("soccer", "passes")
        assert m.display_name == "Passes"
        assert m.sport == "soccer"


class TestMarketRegistryBasketball:
    def test_basketball_markets_registered(self) -> None:
        registry = get_default_registry()
        bball_markets = registry.get_markets_for_sport("basketball")
        ids = {m.id for m in bball_markets}
        assert "points" in ids
        assert "rebounds" in ids
        assert "assists" in ids
        assert "threes" in ids


class TestMarketRegistryBaseball:
    def test_baseball_markets_registered(self) -> None:
        registry = get_default_registry()
        bb_markets = registry.get_markets_for_sport("baseball")
        ids = {m.id for m in bb_markets}
        assert "hits" in ids
        assert "strikeouts" in ids
        assert "total_bases" in ids


class TestUnsupportedMarketRejection:
    def test_unsupported_market_for_sport_raises(self) -> None:
        registry = get_default_registry()
        with pytest.raises(UnsupportedMarketError):
            registry.get_market("soccer", "touchdowns")

    def test_unsupported_sport_raises(self) -> None:
        registry = get_default_registry()
        with pytest.raises(UnsupportedMarketError):
            registry.get_market("cricket", "wickets")


class TestRegistryCompatibility:
    def test_existing_soccer_request_markets_validate(self) -> None:
        registry = get_default_registry()
        for market_id in ("passes", "shots"):
            m = registry.get_market("soccer", market_id)
            assert m is not None

    def test_registry_markets_match_pick_request_constants(self) -> None:
        from pick_request import SPORT_MARKETS

        registry = get_default_registry()
        for sport, market_ids in SPORT_MARKETS.items():
            registered = {m.id for m in registry.get_markets_for_sport(sport)}
            assert market_ids.issubset(registered), (
                f"{sport}: {market_ids - registered} not in registry"
            )


class TestRegistryCustomization:
    def test_register_new_market(self) -> None:
        registry = MarketRegistry()
        m = Market(
            id="tackles",
            display_name="Tackles",
            sport="soccer",
            value_type="float",
            sides=("over", "under"),
        )
        registry.register(m)
        assert registry.get_market("soccer", "tackles") == m

    def test_sport_module_can_expose_markets(self) -> None:
        registry = get_default_registry()
        soccer_ids = {m.id for m in registry.get_markets_for_sport("soccer")}
        assert len(soccer_ids) >= 2
