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


def _build_basketball_module():
    """Construct BasketballModule with real LLM providers when API keys are available."""
    import os

    from basketball_module import BasketballModule
    from provider_config import LLMFixtureProviderConfig

    config = LLMFixtureProviderConfig.from_env()
    if not config.is_configured():
        return BasketballModule()

    game_provider = None
    stats_provider = None
    props_provider = None

    try:
        if config.provider == "gemini" and config.api_key:
            from llm.gemini_client import GeminiLLMClient

            model = os.getenv("COLMILLO_BASKETBALL_LLM_MODEL") or config.model or "gemini-2.5-flash"
            client = GeminiLLMClient(
                api_key=config.api_key,
                model=model,
                search_grounding=True,
                max_output_tokens=4000,
                max_retries=1,
                retry_delay_seconds=2.0,
            )

            from llm_game_provider import LLMGameProvider
            from llm_player_stats_provider import LLMPlayerStatsProvider
            from llm_props_provider import LLMPropsProvider

            game_provider = LLMGameProvider(config=config, client=client)
            stats_provider = LLMPlayerStatsProvider(client=client)
            props_provider = LLMPropsProvider(client=client)
        elif config.provider in ("xai", "grok") and config.api_key:
            from llm.grok_client import GrokLLMClient

            client = GrokLLMClient(
                api_key=config.api_key,
                base_url=config.base_url or "https://api.x.ai/v1",
                model=config.model or "grok-3",
                max_retries=1,
                retry_delay_seconds=2.0,
            )

            from llm_game_provider import LLMGameProvider
            from llm_player_stats_provider import LLMPlayerStatsProvider
            from llm_props_provider import LLMPropsProvider

            game_provider = LLMGameProvider(config=config, client=client)
            stats_provider = LLMPlayerStatsProvider(client=client)
            props_provider = LLMPropsProvider(client=client)
    except Exception:
        pass

    return BasketballModule(
        game_provider=game_provider,
        stats_provider=stats_provider,
        props_provider=props_provider,
    )


_DEFAULT_REGISTRY.register(_build_basketball_module())


def _build_baseball_module():  # noqa: E302
    """Wire MLB StatsAPI providers into the baseball module."""
    try:
        import httpx
        from mlb_statsapi_adapter import (
            StatsAPIBallparkAdapter,
            StatsAPIBullpenAdapter,
            StatsAPIConfig,
            StatsAPILineupsAdapter,
            StatsAPIPitcherAdapter,
            StatsAPIPlayerStatsAdapter,
            StatsAPIScheduleAdapter,
            StatsAPISplitsAdapter,
            StatsAPIWeatherAdapter,
        )
        from mlb_collection import MLBCollectionService
        from baseball_module import BaseballModule

        config = StatsAPIConfig()
        transport = httpx.HTTPTransport(retries=2)
        client = httpx.Client(timeout=config.timeout_seconds, transport=transport)

        service = MLBCollectionService(
            schedule=StatsAPIScheduleAdapter(client=client, config=config),
            pitchers=StatsAPIPitcherAdapter(client=client, config=config),
            lineups=StatsAPILineupsAdapter(client=client, config=config),
            player_stats=StatsAPIPlayerStatsAdapter(client=client, config=config),
            splits=StatsAPISplitsAdapter(client=client, config=config),
            bullpen=StatsAPIBullpenAdapter(client=client, config=config),
            weather=StatsAPIWeatherAdapter(client=client, config=config),
            ballpark=StatsAPIBallparkAdapter(client=client, config=config),
        )
        return BaseballModule(collection_service=service)
    except Exception:
        from baseball_module import BaseballModule
        return BaseballModule()


_DEFAULT_REGISTRY.register(_build_baseball_module())


def get_sport_module(sport: str) -> SportModule:
    return _DEFAULT_REGISTRY.get(sport)
