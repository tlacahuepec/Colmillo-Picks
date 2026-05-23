"""Sport-aware market registry.

Defines supported prop markets per sport with metadata (display name,
value type, sides). Provides validation and lookup for pipeline use.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


class UnsupportedMarketError(ValueError):
    pass


@dataclass(frozen=True)
class Market:
    id: str
    display_name: str
    sport: str
    value_type: str
    sides: tuple[str, ...]


class MarketRegistry:
    def __init__(self) -> None:
        self._markets: dict[str, dict[str, Market]] = {}

    def register(self, market: Market) -> None:
        self._markets.setdefault(market.sport, {})[market.id] = market

    def get_market(self, sport: str, market_id: str) -> Market:
        sport_markets = self._markets.get(sport)
        if sport_markets is None:
            raise UnsupportedMarketError(
                f"Sport '{sport}' has no registered markets"
            )
        market = sport_markets.get(market_id)
        if market is None:
            raise UnsupportedMarketError(
                f"Market '{market_id}' not supported for sport '{sport}'"
            )
        return market

    def get_markets_for_sport(self, sport: str) -> Sequence[Market]:
        return list(self._markets.get(sport, {}).values())


def _build_default_registry() -> MarketRegistry:
    registry = MarketRegistry()

    soccer_markets = [
        Market(id="passes", display_name="Passes", sport="soccer", value_type="float", sides=("over", "under")),
        Market(id="shots", display_name="Shots", sport="soccer", value_type="float", sides=("over", "under")),
    ]

    basketball_markets = [
        Market(id="points", display_name="Points", sport="basketball", value_type="float", sides=("over", "under")),
        Market(id="rebounds", display_name="Rebounds", sport="basketball", value_type="float", sides=("over", "under")),
        Market(id="assists", display_name="Assists", sport="basketball", value_type="float", sides=("over", "under")),
        Market(id="threes", display_name="Three-Pointers", sport="basketball", value_type="float", sides=("over", "under")),
    ]

    baseball_markets = [
        Market(id="hits", display_name="Hits", sport="baseball", value_type="float", sides=("over", "under")),
        Market(id="strikeouts", display_name="Strikeouts", sport="baseball", value_type="float", sides=("over", "under")),
        Market(id="total_bases", display_name="Total Bases", sport="baseball", value_type="float", sides=("over", "under")),
    ]

    for m in soccer_markets + basketball_markets + baseball_markets:
        registry.register(m)

    return registry


_DEFAULT_REGISTRY: MarketRegistry | None = None


def get_default_registry() -> MarketRegistry:
    global _DEFAULT_REGISTRY
    if _DEFAULT_REGISTRY is None:
        _DEFAULT_REGISTRY = _build_default_registry()
    return _DEFAULT_REGISTRY
