from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Callable

from llm.client import LLMClient, LLMError
from llm.intelligence_prompt_builder import (
    build_match_discovery_system_prompt,
    build_match_discovery_user_prompt,
)


SUPPORTED_DISCOVERY_SPORTS: tuple[str, ...] = ("soccer", "basketball", "baseball")


class MatchDiscoveryError(RuntimeError):
    """Sanitized match discovery failure safe to expose through the API."""


class MatchDiscoveryValidationError(MatchDiscoveryError):
    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__("; ".join(errors))


def validate_match_discovery_inputs(
    *,
    date_utc: str,
    sports: list[str],
    limit_per_sport: int,
) -> list[str]:
    errors: list[str] = []

    try:
        datetime.strptime(date_utc, "%Y-%m-%d")
    except ValueError:
        errors.append(f"Invalid date '{date_utc}'. Expected YYYY-MM-DD format.")

    if not 1 <= limit_per_sport <= 5:
        errors.append(
            f"limit_per_sport must be between 1 and 5, got {limit_per_sport}."
        )

    normalized_sports: list[str] = []
    for sport in sports:
        normalized = sport.lower().strip()
        if not normalized:
            continue
        if normalized not in SUPPORTED_DISCOVERY_SPORTS:
            errors.append(
                f"Unsupported sport '{sport}'. Supported: {list(SUPPORTED_DISCOVERY_SPORTS)}"
            )
            continue
        if normalized not in normalized_sports:
            normalized_sports.append(normalized)

    if not normalized_sports:
        errors.append("At least one supported sport is required.")

    if errors:
        raise MatchDiscoveryValidationError(errors)

    return normalized_sports


class MatchDiscoveryClient:
    """Discovers important matches grouped by sport using an LLM client."""

    def __init__(self, *, client: LLMClient) -> None:
        self._client = client

    @classmethod
    def from_env(
        cls,
        getenv: Callable[[str], str | None] = os.getenv,
        provider: str | None = None,
        model: str | None = None,
    ) -> "MatchDiscoveryClient":
        resolved_provider = (
            provider
            or getenv("COLMILLO_LLM_PROVIDER")
            or "gemini"
        ).lower().strip()

        if resolved_provider == "gemini":
            api_key = getenv("GEMINI_API_KEY")
            if not api_key:
                raise MatchDiscoveryError(
                    "GEMINI_API_KEY is required for match discovery with provider 'gemini'."
                )
            from llm.gemini_client import GeminiLLMClient

            client = GeminiLLMClient(
                api_key=api_key,
                model=model or getenv("GEMINI_MODEL") or "gemini-2.5-flash",
                search_grounding=True,
            )
        elif resolved_provider == "grok":
            api_key = getenv("XAI_API_KEY")
            if not api_key:
                raise MatchDiscoveryError(
                    "XAI_API_KEY is required for match discovery with provider 'grok'."
                )
            from llm.grok_client import GrokLLMClient

            client = GrokLLMClient(
                api_key=api_key,
                base_url=getenv("XAI_BASE_URL") or "https://api.x.ai/v1",
                model=model or getenv("XAI_MODEL") or "grok-3",
            )
        elif resolved_provider == "openai":
            api_key = getenv("OPENAI_API_KEY")
            if not api_key:
                raise MatchDiscoveryError(
                    "OPENAI_API_KEY is required for match discovery with provider 'openai'."
                )
            from llm.openai_client import OpenAILLMClient

            from openai import OpenAI

            sdk_client = OpenAI(api_key=api_key)
            client = OpenAILLMClient(
                sdk_client=sdk_client,
                model=model or getenv("OPENAI_MODEL") or "gpt-4.1-mini",
            )
        else:
            raise MatchDiscoveryError(
                f"Unsupported LLM provider '{resolved_provider}'. Supported: gemini, grok, openai."
            )

        return cls(client=client)

    def discover_matches(
        self,
        *,
        date_utc: str,
        sports: list[str],
        limit_per_sport: int = 5,
    ) -> dict[str, Any]:
        normalized_sports = validate_match_discovery_inputs(
            date_utc=date_utc,
            sports=sports,
            limit_per_sport=limit_per_sport,
        )

        results: dict[str, dict[str, Any]] = {}
        generated_at_utc: str | None = None

        for sport in normalized_sports:
            try:
                raw = self._request_sport(
                    date_utc=date_utc,
                    sport=sport,
                    limit_per_sport=limit_per_sport,
                )
                generated_at_utc = generated_at_utc or _string_or_none(
                    raw.get("generated_at_utc")
                )
                results[sport] = _normalize_sport_result(
                    raw=raw,
                    sport=sport,
                    date_utc=date_utc,
                    limit_per_sport=limit_per_sport,
                )
            except LLMError as exc:
                results[sport] = _error_result(str(exc))
            except MatchDiscoveryError as exc:
                results[sport] = _error_result(str(exc))

        return {
            "date_utc": date_utc,
            "generated_at_utc": generated_at_utc or _now_utc_z(),
            "limit_per_sport": limit_per_sport,
            "results": results,
        }

    def _request_sport(
        self,
        *,
        date_utc: str,
        sport: str,
        limit_per_sport: int,
    ) -> dict[str, Any]:
        system_prompt = build_match_discovery_system_prompt()
        user_prompt = build_match_discovery_user_prompt(
            date_utc=date_utc,
            sports=[sport],
            limit_per_sport=limit_per_sport,
        )
        result = self._client.generate_structured(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            schema={},
        )
        if not isinstance(result, dict):
            raise MatchDiscoveryError("LLM returned a non-object response.")
        return result


def _normalize_sport_result(
    *,
    raw: dict[str, Any],
    sport: str,
    date_utc: str,
    limit_per_sport: int,
) -> dict[str, Any]:
    sport_payload = _extract_sport_payload(raw, sport)
    provider = _string_or_none(raw.get("provider"))
    model = _string_or_none(raw.get("model"))
    raw_matches = sport_payload.get("matches")
    if raw_matches is None:
        raw_matches = sport_payload.get("top_matches", [])
    if not isinstance(raw_matches, list):
        return _error_result(f"Discovery response for '{sport}' has non-list matches.")

    matches = [
        _normalize_match(
            item=item,
            sport=sport,
            date_utc=date_utc,
            source_provider=provider,
            source_model=model,
            fallback_sources=raw.get("sources", []),
        )
        for item in raw_matches[:limit_per_sport]
        if isinstance(item, dict)
    ]

    data_quality = sport_payload.get("data_quality")
    if not isinstance(data_quality, dict):
        data_quality = {"status": "ok" if matches else "empty"}
    error = _string_or_none(sport_payload.get("error"))

    return {
        "matches": matches,
        "error": error,
        "data_quality": data_quality,
    }


def _extract_sport_payload(raw: dict[str, Any], sport: str) -> dict[str, Any]:
    grouped = raw.get("grouped_by_sport")
    if not isinstance(grouped, dict):
        grouped = raw.get("sports")
    if isinstance(grouped, dict):
        payload = grouped.get(sport, {})
        return payload if isinstance(payload, dict) else {}
    return raw


def _normalize_match(
    *,
    item: dict[str, Any],
    sport: str,
    date_utc: str,
    source_provider: str | None,
    source_model: str | None,
    fallback_sources: Any,
) -> dict[str, Any]:
    teams = item.get("teams") if isinstance(item.get("teams"), dict) else {}
    home_team = _string_or_none(item.get("home_team")) or _team_name(teams.get("home"))
    away_team = _string_or_none(item.get("away_team")) or _team_name(teams.get("away"))
    sources = _normalize_sources(item.get("sources") or fallback_sources)

    data_quality = item.get("data_quality")
    if not isinstance(data_quality, dict):
        data_quality = {}
    missing_fields = list(data_quality.get("missing_fields", []))
    for field_name, value in (
        ("home_team", home_team),
        ("away_team", away_team),
        ("kickoff_utc", item.get("kickoff_utc")),
    ):
        if not value and field_name not in missing_fields:
            missing_fields.append(field_name)
    data_quality = {
        **data_quality,
        "confidence": data_quality.get("confidence", "low" if missing_fields else "medium"),
        "missing_fields": missing_fields,
        "source_count": len(sources),
    }

    return {
        "sport": sport,
        "home_team": home_team or "Unknown",
        "away_team": away_team or "Unknown",
        "event_date": _string_or_none(item.get("event_date")) or date_utc,
        "league": _string_or_none(item.get("league")),
        "competition": _string_or_none(item.get("competition")),
        "kickoff_utc": _string_or_none(item.get("kickoff_utc")),
        "importance": _string_or_none(item.get("importance"))
        or _string_or_none(item.get("match_importance"))
        or "medium",
        "notes": _string_or_none(item.get("notes")),
        "source_provider": source_provider,
        "source_model": source_model,
        "sources": sources,
        "data_quality": data_quality,
    }


def _normalize_sources(raw_sources: Any) -> list[dict[str, str | None]]:
    if not isinstance(raw_sources, list):
        return []
    normalized: list[dict[str, str | None]] = []
    for source in raw_sources:
        if not isinstance(source, dict):
            continue
        label = _string_or_none(source.get("label")) or _string_or_none(source.get("title"))
        url = _string_or_none(source.get("url"))
        normalized.append({"label": label or "source", "url": url})
    return normalized


def _team_name(raw_team: Any) -> str | None:
    if isinstance(raw_team, dict):
        return _string_or_none(raw_team.get("name"))
    return _string_or_none(raw_team)


def _string_or_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _error_result(message: str) -> dict[str, Any]:
    return {
        "matches": [],
        "error": message,
        "data_quality": {"status": "error", "reason": message},
    }


def _now_utc_z() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
