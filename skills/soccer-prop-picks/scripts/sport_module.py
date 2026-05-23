"""SportModule protocol and registry for multi-sport pipeline support."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


class UnsupportedSportError(ValueError):
    def __init__(self, sport: str):
        self.sport = sport
        super().__init__(f"Unsupported sport: '{sport}'")


@runtime_checkable
class SportModule(Protocol):
    @property
    def sport_id(self) -> str: ...

    @property
    def supported_leagues(self) -> set[str]: ...

    @property
    def supported_markets(self) -> set[str]: ...

    def collect_inputs(
        self, *, home_team: str, away_team: str, match_date: str, league: str | None = None
    ) -> dict[str, Any]: ...

    def score(
        self, match_inputs: dict[str, Any], *, markets: tuple[str, ...] = ()
    ) -> list[dict[str, Any]]: ...

    def explain(self, scored_pick: dict[str, Any]) -> str: ...


class SportModuleRegistry:
    def __init__(self) -> None:
        self._modules: dict[str, SportModule] = {}

    def register(self, module: SportModule) -> None:
        self._modules[module.sport_id] = module

    def get(self, sport: str) -> SportModule:
        try:
            return self._modules[sport]
        except KeyError:
            raise UnsupportedSportError(sport)

    @property
    def registered_sports(self) -> list[str]:
        return sorted(self._modules.keys())


class SoccerModule:
    @property
    def sport_id(self) -> str:
        return "soccer"

    @property
    def supported_leagues(self) -> set[str]:
        return {
            "premier_league", "la_liga", "serie_a", "bundesliga",
            "ligue_1", "mls", "champions_league",
        }

    @property
    def supported_markets(self) -> set[str]:
        return {"passes", "shots"}

    def collect_inputs(
        self, *, home_team: str, away_team: str, match_date: str, league: str | None = None
    ) -> dict[str, Any]:
        return {
            "home_team": home_team,
            "away_team": away_team,
            "match_date": match_date,
            "league": league,
        }

    def score(
        self, match_inputs: dict[str, Any], *, markets: tuple[str, ...] = ()
    ) -> list[dict[str, Any]]:
        raise NotImplementedError("Use the existing pipeline for soccer scoring")

    def explain(self, scored_pick: dict[str, Any]) -> str:
        raise NotImplementedError("Use the existing pipeline for soccer explanation")


_DEFAULT_REGISTRY = SportModuleRegistry()
_DEFAULT_REGISTRY.register(SoccerModule())


def get_sport_module(sport: str) -> SportModule:
    return _DEFAULT_REGISTRY.get(sport)
