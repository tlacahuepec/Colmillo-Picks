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
    def __init__(self, *, allow_deterministic_fallback: bool = True) -> None:
        self._allow_deterministic_fallback = allow_deterministic_fallback

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
        from collect_match_inputs import MatchInputRequest
        from dependency_bundle import build_dependency_bundle

        deps = build_dependency_bundle(
            use_llm=False,
            llm_provider=None,
            llm_model=None,
            allow_deterministic_fallback=self._allow_deterministic_fallback,
            league=league,
        )

        request = MatchInputRequest(
            home_team=home_team,
            away_team=away_team,
            match_date=match_date,
            competition=league or "League",
        )
        return deps["collect_inputs"](request)

    def score(
        self, match_inputs: dict[str, Any], *, markets: tuple[str, ...] = ()
    ) -> list[dict[str, Any]]:
        from score_player_props import score_props

        payload = score_props(match_inputs, include_trace=True)
        scores = payload["scores"]

        if markets:
            scores = [s for s in scores if s.get("market") in markets]

        return scores

    def explain(self, scored_pick: dict[str, Any]) -> str:
        player = scored_pick.get("player", "Unknown")
        market = scored_pick.get("market", "unknown")
        direction = scored_pick.get("direction", "over")
        line = scored_pick.get("line", 0)
        confidence = scored_pick.get("confidence", "medium")
        return (
            f"{player}: {direction} {line} {market} "
            f"(confidence: {confidence})"
        )


_DEFAULT_REGISTRY = SportModuleRegistry()
_DEFAULT_REGISTRY.register(SoccerModule())

from basketball_module import BasketballModule  # noqa: E402

_DEFAULT_REGISTRY.register(BasketballModule())


def get_sport_module(sport: str) -> SportModule:
    return _DEFAULT_REGISTRY.get(sport)
