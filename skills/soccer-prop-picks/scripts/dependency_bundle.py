"""Build the dependency bundle consumed by the soccer pick pipeline.

Extracted from ``run_match_pick_pipeline.py`` so that both the CLI and the
FastAPI service can wire the same providers without depending on argparse-driven
script entry points.
"""

from __future__ import annotations

import os

from availability import DeterministicMockAvailabilityAdapter, PrizePicksAdapter
from collect_match_inputs import MatchInputRequest, collect_inputs
from llm_fixture_provider import LLMFixtureProvider
from llm_lineup_provider import LLMLineupProvider
from llm.gemini_client import GeminiLLMClient
from llm.grok_client import GrokLLMClient
from llm.provider_adapter import build_enrich_with_llm
from provider_config import LLMFixtureProviderConfig
from render_pick_report import render_report
from score_player_props import score_props


_SUPPORTED_FIXTURE_PROVIDERS = {"llm", "auto"}
_SUPPORTED_AVAILABILITY_PROVIDERS = {"prizepicks", "mock", "none"}


def _optional_value(raw_value: str | None) -> str | None:
    if raw_value is None:
        return None
    value = raw_value.strip()
    return value or None


def _fixture_provider_source(raw_value: str | None) -> str:
    source = (
        _optional_value(raw_value)
        or _optional_value(os.getenv("SOCCER_FIXTURE_PROVIDER"))
        or "llm"
    ).lower()
    if source not in _SUPPORTED_FIXTURE_PROVIDERS:
        supported = ", ".join(sorted(_SUPPORTED_FIXTURE_PROVIDERS))
        raise ValueError(
            f"Unsupported fixture provider '{source}'. Supported values: {supported}."
        )
    return source


def _build_llm_fixture_provider(
    *,
    fixture_llm_provider: str | None,
    fixture_llm_model: str | None,
    fixture_llm_base_url: str | None,
) -> LLMFixtureProvider:
    config = LLMFixtureProviderConfig.from_env(
        provider=fixture_llm_provider,
        model=fixture_llm_model,
        base_url=fixture_llm_base_url,
    )
    if config.provider == "gemini":
        client = GeminiLLMClient(api_key=config.api_key or "", model=config.model or "gemini-2.5-flash", search_grounding=True, max_output_tokens=4000)
        return LLMFixtureProvider(config=config, client=client)
    if config.provider == "xai" or config.provider == "grok":
        client = GrokLLMClient(
            api_key=config.api_key or "",
            base_url=config.base_url or "https://api.x.ai/v1",
            model=config.model or "grok-3",
        )
        return LLMFixtureProvider(config=config, client=client)
    return LLMFixtureProvider(config=config)


def _build_llm_lineup_provider(
    *,
    fixture_llm_provider: str | None,
    fixture_llm_model: str | None,
    fixture_llm_base_url: str | None,
) -> LLMLineupProvider | None:
    config = LLMFixtureProviderConfig.from_env(
        provider=fixture_llm_provider,
        model=fixture_llm_model,
        base_url=fixture_llm_base_url,
    )
    if config.provider == "gemini" and config.api_key:
        client = GeminiLLMClient(
            api_key=config.api_key,
            model=config.model or "gemini-2.5-flash",
            search_grounding=True,
        )
        return LLMLineupProvider(client=client)
    return None


def build_dependency_bundle(
    *,
    use_llm: bool,
    llm_provider: str | None,
    llm_model: str | None,
    allow_deterministic_fallback: bool = False,
    league: str | None = None,
    fixture_provider_name: str | None = None,
    fixture_llm_provider: str | None = None,
    fixture_llm_model: str | None = None,
    fixture_llm_base_url: str | None = None,
    availability_provider: str | None = None,
    parse_match_query=None,
) -> dict[str, object]:
    """Wire fixture/LLM providers and return a deps dict for ``run_pipeline``."""

    if parse_match_query is None:
        from run_match_pick_pipeline import parse_match_query as _parse_match_query

        parse_match_query = _parse_match_query

    source = _fixture_provider_source(fixture_provider_name)
    fixture_provider = None

    if source == "llm":
        llm_config = LLMFixtureProviderConfig.from_env(
            provider=fixture_llm_provider,
            model=fixture_llm_model,
            base_url=fixture_llm_base_url,
        )
        has_explicit_config = any([fixture_llm_provider, fixture_llm_model, fixture_llm_base_url])
        if llm_config.is_configured() or has_explicit_config:
            fixture_provider = _build_llm_fixture_provider(
                fixture_llm_provider=fixture_llm_provider,
                fixture_llm_model=fixture_llm_model,
                fixture_llm_base_url=fixture_llm_base_url,
            )
        elif not allow_deterministic_fallback:
            raise ValueError(
                "No LLM fixture provider configured. Set GEMINI_API_KEY or pass --fixture-llm-provider."
            )
    elif source == "auto":
        llm_config = LLMFixtureProviderConfig.from_env(
            provider=fixture_llm_provider,
            model=fixture_llm_model,
            base_url=fixture_llm_base_url,
        )
        if llm_config.is_configured():
            fixture_provider = _build_llm_fixture_provider(
                fixture_llm_provider=fixture_llm_provider,
                fixture_llm_model=fixture_llm_model,
                fixture_llm_base_url=fixture_llm_base_url,
            )
        elif not allow_deterministic_fallback:
            raise ValueError(
                "No LLM fixture provider configured. Set GEMINI_API_KEY or pass --fixture-llm-provider."
            )

    availability_source = (
        _optional_value(availability_provider)
        or _optional_value(os.getenv("COLMILLO_AVAILABILITY_PROVIDER"))
        or "none"
    ).lower()
    if availability_source not in _SUPPORTED_AVAILABILITY_PROVIDERS:
        supported = ", ".join(sorted(_SUPPORTED_AVAILABILITY_PROVIDERS))
        raise ValueError(
            f"Unsupported availability provider '{availability_source}'. Supported: {supported}."
        )
    availability_adapter = None
    if availability_source == "prizepicks":
        availability_adapter = PrizePicksAdapter()
    elif availability_source == "mock":
        availability_adapter = DeterministicMockAvailabilityAdapter()

    competition_hint = _optional_value(league)

    lineup_provider = _build_llm_lineup_provider(
        fixture_llm_provider=fixture_llm_provider,
        fixture_llm_model=fixture_llm_model,
        fixture_llm_base_url=fixture_llm_base_url,
    )

    return {
        "parse_match_query": parse_match_query,
        "build_match_input_request": lambda *, parsed, competition: MatchInputRequest(
            home_team=parsed.home_team,
            away_team=parsed.away_team,
            match_date=parsed.match_date,
            competition=competition_hint or competition,
            competition_hints=[competition_hint] if competition_hint else None,
        ),
        "collect_inputs": lambda request: collect_inputs(
            request,
            fixture_provider=fixture_provider,
            lineup_provider=lineup_provider,
            allow_fixture_fallback=allow_deterministic_fallback,
        ),
        "score_props": score_props,
        "render_report": render_report,
        "enrich_with_llm": build_enrich_with_llm(
            use_llm=use_llm,
            llm_provider=llm_provider,
            llm_model=llm_model,
        ),
        "check_availability": availability_adapter.check_picks if availability_adapter else None,
    }
