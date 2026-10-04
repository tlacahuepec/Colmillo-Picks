from __future__ import annotations

import os
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Callable

from llm.client import LLMClient, LLMError
from llm.intelligence_prompt_builder import (
    build_match_discovery_system_prompt,
    build_match_discovery_user_prompt,
)
from pick_request import normalize_league


SUPPORTED_DISCOVERY_SPORTS: tuple[str, ...] = ("soccer", "basketball", "baseball", "nfl")
EXCLUDED_DISCOVERY_COMPETITIONS: frozenset[str] = frozenset({
    "fifa u 20 womens world cup",
    "fiba 3x3 u23 mens world cup",
})


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

    if not 1 <= limit_per_sport <= 10:
        errors.append(
            f"limit_per_sport must be between 1 and 10, got {limit_per_sport}."
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

    @property
    def client(self) -> LLMClient:
        return self._client

    @classmethod
    def from_env(
        cls,
        getenv: Callable[[str], str | None] = os.getenv,
        provider: str | None = None,
        model: str | None = None,
        max_output_tokens: int = 8192,
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

            discovery_timeout = float(getenv("COLMILLO_DISCOVERY_TIMEOUT") or 90.0)
            client = GeminiLLMClient(
                api_key=api_key,
                model=model or getenv("GEMINI_MODEL") or "gemini-2.5-flash",
                search_grounding=True,
                max_output_tokens=max(8192, max_output_tokens),
                timeout_seconds=discovery_timeout,
                max_retries=2,
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
        timezone: str | None = None,
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
                    **({"timezone_name": timezone or os.getenv("COLMILLO_TIMEZONE") or "America/Chicago"} if sport == "nfl" else {}),
                )
                generated_at_utc = generated_at_utc or _string_or_none(
                    raw.get("generated_at_utc")
                )
                # A URL emitted in structured text is not evidence by itself.  Gemini
                # exposes the provider's grounding metadata separately; preserve that
                # boundary so normalization can only accept URLs the provider actually
                # returned as grounding sources.  Other providers may not expose this
                # metadata yet, in which case their suggestions are honestly withheld.
                raw = {
                    **raw,
                    "grounding_sources": _grounding_sources_from_client(self._client),
                }
                results[sport] = _normalize_sport_result(
                    raw=raw,
                    sport=sport,
                    date_utc=date_utc,
                    limit_per_sport=limit_per_sport,
                    timezone=timezone,
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
        timezone_name: str | None = None,
    ) -> dict[str, Any]:
        system_prompt = build_match_discovery_system_prompt()
        user_prompt = build_match_discovery_user_prompt(
            date_utc=date_utc,
            sports=[sport],
            limit_per_sport=limit_per_sport,
        )
        if timezone_name:
            user_prompt += f"\nInterpret {date_utc} in {timezone_name}; kickoff_utc may fall on the next UTC day. event_date must be the requested local date."
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
    timezone: str | None = None,
) -> dict[str, Any]:
    sport_payload = _extract_sport_payload(raw, sport)
    provider = _string_or_none(raw.get("provider"))
    model = _string_or_none(raw.get("model"))
    raw_matches = sport_payload.get("matches")
    if raw_matches is None:
        raw_matches = sport_payload.get("top_matches", [])
    if not isinstance(raw_matches, list):
        return _error_result(f"Discovery response for '{sport}' has non-list matches.")

    normalized_matches = [
        _normalize_match(
            item=item,
            sport=sport,
            date_utc=date_utc,
            source_provider=provider,
            source_model=model,
            fallback_sources=raw.get("sources", []),
            grounding_sources=raw.get("grounding_sources", []),
        )
        for item in raw_matches
        if isinstance(item, dict)
    ]

    rejected: Counter[str] = Counter()
    matches: list[dict[str, Any]] = []
    for match in normalized_matches:
        reason = _fixture_rejection_reason(match)
        if reason:
            rejected[reason] += 1
        else:
            matches.append(match)

    if sport == "nfl":
        from nfl_domain import timestamp
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
        from datetime import timezone as utc_timezone

        reference = datetime.now(utc_timezone.utc)
        try:
            zone = ZoneInfo(timezone or os.getenv("COLMILLO_TIMEZONE") or "America/Chicago")
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise MatchDiscoveryError("Invalid NFL date timezone.") from exc
        eligible_matches: list[dict[str, Any]] = []
        for match in matches:
            kickoff = timestamp(match.get("kickoff_utc"))
            if kickoff is None:
                rejected["invalid_kickoff"] += 1
            elif kickoff <= reference:
                rejected["already_started"] += 1
            elif kickoff.astimezone(zone).date().isoformat() != date_utc:
                rejected["wrong_date"] += 1
            elif (match.get("league") or "").lower() != "nfl":
                rejected["unsupported_league"] += 1
            else:
                eligible_matches.append(match)
        matches = eligible_matches
        for match in matches:
            match["event_date"] = date_utc
    else:
        dated_matches: list[dict[str, Any]] = []
        for match in matches:
            if not _matches_requested_date(match, date_utc, timezone=timezone):
                rejected["wrong_date"] += 1
            elif not _is_match_upcoming(match):
                rejected["already_started"] += 1
            else:
                dated_matches.append(match)
        matches = dated_matches

    included_matches: list[dict[str, Any]] = []
    for match in matches:
        if _is_excluded_competition(match):
            rejected["unsupported_league"] += 1
        else:
            included_matches.append(match)
    matches = included_matches
    matches = matches[:limit_per_sport]

    data_quality = sport_payload.get("data_quality")
    if not isinstance(data_quality, dict):
        data_quality = {}
    error = _string_or_none(sport_payload.get("error"))

    # Candidate-shaped LLM text without fixture evidence is neither an empty
    # schedule nor a provider failure. Withhold it and explain the outcome.
    if error:
        status = "error"
    elif matches:
        status = "verified"
    elif normalized_matches:
        status = "unavailable"
    else:
        status = "empty"
    data_quality = {
        **data_quality,
        "status": status,
        "verified_count": len(matches),
        "rejected_counts": dict(sorted(rejected.items())),
    }
    if status == "unavailable":
        data_quality["reason"] = "No verifiable upcoming fixtures were returned."

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


def _matches_requested_date(match: dict[str, Any], date_utc: str, *, timezone: str | None = None) -> bool:
    """Return True if the match's event_date or kickoff_utc falls on the requested date."""
    event_date = match.get("event_date", "")
    if event_date:
        return event_date == date_utc
    kickoff = match.get("kickoff_utc", "")
    if not kickoff:
        return False
    if timezone:
        from datetime import datetime
        from zoneinfo import ZoneInfo

        try:
            dt = datetime.fromisoformat(kickoff.replace("Z", "+00:00"))
            local_date = dt.astimezone(ZoneInfo(timezone)).date().isoformat()
            return local_date == date_utc
        except (ValueError, TypeError, KeyError):
            pass
    return kickoff.startswith(date_utc)


def _is_match_upcoming(
    match: dict[str, Any],
    *,
    now: datetime | None = None,
    buffer_minutes: int = 15,
) -> bool:
    """Return True if the match has not yet started (with buffer for pre-kickoff bets)."""
    kickoff = match.get("kickoff_utc", "")
    if not kickoff:
        return True
    try:
        kickoff_dt = datetime.fromisoformat(kickoff.replace("Z", "+00:00"))
        from datetime import timedelta

        reference = now if now is not None else datetime.now(timezone.utc)
        cutoff = reference - timedelta(minutes=buffer_minutes)
        return kickoff_dt > cutoff
    except (ValueError, TypeError):
        return True


def _normalize_match(
    *,
    item: dict[str, Any],
    sport: str,
    date_utc: str,
    source_provider: str | None,
    source_model: str | None,
    fallback_sources: Any,
    grounding_sources: Any = (),
) -> dict[str, Any]:
    teams = item.get("teams") if isinstance(item.get("teams"), dict) else {}
    home_team = _string_or_none(item.get("home_team")) or _team_name(teams.get("home"))
    away_team = _string_or_none(item.get("away_team")) or _team_name(teams.get("away"))
    sources = _normalize_sources(
        item.get("sources") or fallback_sources,
        grounding_sources=grounding_sources,
    )

    raw_league = _string_or_none(item.get("league"))
    raw_comp = _string_or_none(item.get("competition"))
    normalized_league = normalize_league(raw_league, sport)
    if not normalized_league and raw_comp:
        normalized_league = normalize_league(raw_comp, sport)

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
        "league": normalized_league,
        "competition": raw_comp or raw_league or normalized_league,
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


def _fixture_rejection_reason(match: dict[str, Any]) -> str | None:
    """Return why a candidate cannot be offered as a verified fixture."""
    if match.get("home_team") == "Unknown" or match.get("away_team") == "Unknown":
        return "missing_teams"
    if not _parse_kickoff(match.get("kickoff_utc")):
        return "missing_kickoff"
    if not match.get("league"):
        return "unsupported_league"
    if not any(source.get("grounded") for source in match.get("sources", [])):
        return "missing_citation"
    return None


def _parse_kickoff(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _is_usable_source_url(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    normalized = value.strip().lower()
    return normalized.startswith("https://") or normalized.startswith("http://")


def _is_excluded_competition(match: dict[str, Any]) -> bool:
    """Return whether a match belongs to a competition excluded from suggestions."""
    competition = _string_or_none(match.get("competition"))
    league = _string_or_none(match.get("league"))
    return any(
        _normalize_competition_name(value) in EXCLUDED_DISCOVERY_COMPETITIONS
        for value in (competition, league)
        if value
    )


def _normalize_competition_name(value: str) -> str:
    normalized = value.casefold().replace("'", "").replace("’", "")
    return " ".join("".join(char if char.isalnum() else " " for char in normalized).split())


def _normalize_sources(
    raw_sources: Any, *, grounding_sources: Any
) -> list[dict[str, str | bool | None]]:
    if not isinstance(raw_sources, list):
        return []
    trusted_urls = {
        url
        for source in grounding_sources if isinstance(grounding_sources, list)
        for url in [_string_or_none(source.get("url")) if isinstance(source, dict) else _string_or_none(getattr(source, "url", None))]
        if url and _is_usable_source_url(url)
    }
    normalized: list[dict[str, str | bool | None]] = []
    for source in raw_sources:
        if not isinstance(source, dict):
            continue
        label = _string_or_none(source.get("label")) or _string_or_none(source.get("title"))
        url = _string_or_none(source.get("url"))
        normalized.append({"label": label or "source", "url": url, "grounded": url in trusted_urls})
    return normalized


def _grounding_sources_from_client(client: LLMClient) -> list[dict[str, str]]:
    """Return provider-issued citations without trusting model-authored JSON."""
    raw_sources = getattr(client, "last_sources", ())
    sources: list[dict[str, str]] = []
    for source in raw_sources or ():
        url = _string_or_none(source.get("url")) if isinstance(source, dict) else _string_or_none(getattr(source, "url", None))
        if url and _is_usable_source_url(url):
            title = _string_or_none(source.get("title")) if isinstance(source, dict) else _string_or_none(getattr(source, "title", None))
            sources.append({"url": url, "title": title or "source"})
    return sources


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
