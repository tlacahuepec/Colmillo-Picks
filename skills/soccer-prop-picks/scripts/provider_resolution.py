"""Provider resolution and fallback decisions for collect_match_inputs."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


_PROVIDER_KEYS = ("fixture", "lineup", "odds", "weather")


class ProviderResolutionError(RuntimeError):
    """Provider data could not be resolved and fallback is disabled."""

    def __init__(self, message: str, *, context: "ResolutionContext" | None = None) -> None:
        super().__init__(message)
        self.context = context  # Rich observability data for Epic #219 failures


def _default_provider_status() -> dict[str, dict[str, Any]]:
    return {
        key: {
            "attempted": False,
            "success": False,
            "fallback_used": False,
            "error_summary": "",
        }
        for key in _PROVIDER_KEYS
    }


@dataclass
class ResolutionContext:
    critical_missing_fields: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    provider_status: dict[str, dict[str, Any]] = field(default_factory=_default_provider_status)


def _record_attempt(context: ResolutionContext, provider_key: str) -> None:
    context.provider_status[provider_key]["attempted"] = True


def _record_success(context: ResolutionContext, provider_key: str) -> None:
    context.provider_status[provider_key]["success"] = True
    context.provider_status[provider_key]["error_summary"] = ""


def _record_failure(context: ResolutionContext, provider_key: str, error: Exception | None = None) -> None:
    status = context.provider_status[provider_key]
    status["success"] = False
    if error is None:
        return
    error_message = str(error).strip()
    status["error_summary"] = error_message[:120] if error_message else error.__class__.__name__


def _record_fallback(context: ResolutionContext, provider_key: str) -> None:
    context.provider_status[provider_key]["fallback_used"] = True


def _fixture_request_label(request: Any) -> str:
    home = getattr(request, "parsed_home_team", None) or getattr(request, "home_team", "unknown")
    away = getattr(request, "parsed_away_team", None) or getattr(request, "away_team", "unknown")
    match_date = getattr(request, "parsed_match_date", None) or getattr(request, "match_date", "unknown")
    return f"{home} vs {away} on {match_date}"


def _fixture_provider_label(fixture_provider: Any) -> str:
    return str(getattr(fixture_provider, "provider_label", "fixture provider"))


def _provider_label(provider: Any, default: str) -> str:
    return str(getattr(provider, "provider_label", default))


def resolve_fixture(
    request: Any,
    fixture_provider: Any,
    fallback_fixture_fn: Any,
    context: ResolutionContext,
    *,
    allow_fallback: bool = True,
) -> dict[str, Any]:
    _record_attempt(context, "fixture")
    failure: Exception | None = None
    if fixture_provider is None:
        failure = ProviderResolutionError("No fixture provider configured.")
        _record_failure(context, "fixture", failure)
        fixture = None
    else:
        try:
            fixture = fixture_provider.lookup_fixture(request)
        except Exception as exc:
            _record_failure(context, "fixture", exc)
            failure = exc
            fixture = None
    if fixture:
        _record_success(context, "fixture")
        return fixture

    if failure is None:
        failure = ProviderResolutionError(
            f"No {_fixture_provider_label(fixture_provider)} fixture matched {_fixture_request_label(request)}."
        )
        _record_failure(context, "fixture", failure)
    if not allow_fallback:
        status = context.provider_status["fixture"]
        summary = str(status.get("error_summary") or failure)
        raise ProviderResolutionError(f"Fixture lookup failed: {summary}", context=context) from failure

    context.critical_missing_fields.append("match")
    context.notes.append("Fixture provider unavailable; used deterministic fallback fixture metadata.")
    _record_fallback(context, "fixture")
    return fallback_fixture_fn(request)


def resolve_lineup(
    fixture: dict[str, Any],
    lineup_provider: Any,
    fallback_lineup_provider: Any,
    context: ResolutionContext,
    *,
    allow_fallback: bool = True,
) -> dict[str, Any]:
    _record_attempt(context, "lineup")
    failure: Exception | None = None
    if lineup_provider is None:
        failure = ProviderResolutionError("No lineup provider configured.")
        _record_failure(context, "lineup", failure)
        lineup_payload = None
    else:
        try:
            lineup_payload = lineup_provider.get_lineups_and_availability(fixture)
        except Exception as exc:
            _record_failure(context, "lineup", exc)
            failure = exc
            lineup_payload = None
    if lineup_payload:
        _record_success(context, "lineup")
        return lineup_payload

    if failure is None:
        failure = ProviderResolutionError(
            f"No {_provider_label(lineup_provider, 'lineup provider')} lineup data returned."
        )
        _record_failure(context, "lineup", failure)
    if not allow_fallback:
        status = context.provider_status["lineup"]
        summary = str(status.get("error_summary") or failure)
        raise ProviderResolutionError(f"Lineup lookup failed: {summary}", context=context) from failure

    context.critical_missing_fields.append("teams.projected_lineup")
    context.notes.append("Lineup provider unavailable; used deterministic projected lineups and players.")
    _record_fallback(context, "lineup")
    return fallback_lineup_provider.get_lineups_and_availability(fixture)


def resolve_market(
    fixture: dict[str, Any],
    odds_provider: Any,
    fallback_odds_provider: Any,
    context: ResolutionContext,
    *,
    allow_fallback: bool = True,
) -> dict[str, Any]:
    _record_attempt(context, "odds")
    failure: Exception | None = None
    if odds_provider is None:
        failure = ProviderResolutionError("No odds provider configured.")
        _record_failure(context, "odds", failure)
        market_payload = None
    else:
        try:
            market_payload = odds_provider.get_odds_snapshots(fixture)
        except Exception as exc:
            _record_failure(context, "odds", exc)
            failure = exc
            market_payload = None
    if market_payload:
        _record_success(context, "odds")
        return market_payload

    if failure is None:
        failure = ProviderResolutionError(
            f"No {_provider_label(odds_provider, 'odds provider')} odds data returned."
        )
        _record_failure(context, "odds", failure)
    if not allow_fallback:
        status = context.provider_status["odds"]
        summary = str(status.get("error_summary") or failure)
        raise ProviderResolutionError(f"Odds lookup failed: {summary}", context=context) from failure

    context.critical_missing_fields.append("market.sportsbook_snapshots")
    context.notes.append("Odds provider unavailable; used deterministic synthetic odds snapshots.")
    _record_fallback(context, "odds")
    return fallback_odds_provider.get_odds_snapshots(fixture)


def resolve_weather(
    fixture: dict[str, Any],
    weather_provider: Any,
    fallback_weather_provider: Any,
    context: ResolutionContext,
    *,
    allow_fallback: bool = True,
) -> dict[str, Any]:
    _record_attempt(context, "weather")
    failure: Exception | None = None
    if weather_provider is None:
        failure = ProviderResolutionError("No weather provider configured.")
        _record_failure(context, "weather", failure)
        weather_payload = None
    else:
        try:
            weather_payload = weather_provider.get_weather(fixture)
        except Exception as exc:
            _record_failure(context, "weather", exc)
            failure = exc
            weather_payload = None
    if weather_payload:
        _record_success(context, "weather")
        return weather_payload

    if failure is None:
        failure = ProviderResolutionError(
            f"No {_provider_label(weather_provider, 'weather provider')} weather data returned."
        )
        _record_failure(context, "weather", failure)
    if not allow_fallback:
        status = context.provider_status["weather"]
        summary = str(status.get("error_summary") or failure)
        raise ProviderResolutionError(f"Weather lookup failed: {summary}", context=context) from failure

    context.critical_missing_fields.append("match.weather")
    context.notes.append("Weather provider unavailable; used neutral weather assumptions.")
    _record_fallback(context, "weather")
    return fallback_weather_provider.get_weather(fixture)


def resolve_timestamp(payload: dict[str, Any], timestamp_key: str, missing_note: str, now_utc_fn: Any, context: ResolutionContext) -> str:
    timestamp = payload.get(timestamp_key) or now_utc_fn()
    if timestamp_key not in payload:
        context.notes.append(missing_note)
    return timestamp


def append_players_missing(context: ResolutionContext, *, fallback_used: bool = True) -> None:
    context.critical_missing_fields.append("players")
    if fallback_used:
        context.notes.append("No player-level provider data returned; used deterministic fallback players.")
    else:
        context.notes.append("No player-level provider data returned; deterministic fallback disabled.")


def append_insufficient_snapshots(context: ResolutionContext, *, fallback_used: bool = True) -> None:
    context.critical_missing_fields.append("market.sportsbook_snapshots")
    if fallback_used:
        context.notes.append("Insufficient odds snapshots from provider; padded with deterministic fallback snapshots.")
    else:
        context.notes.append("Insufficient odds snapshots from provider; deterministic fallback disabled.")


def build_validation(context: ResolutionContext) -> dict[str, Any]:
    critical_missing_fields = sorted(set(context.critical_missing_fields))
    should_reject = any(field in {"match", "players", "market.sportsbook_snapshots"} for field in critical_missing_fields)
    return {
        "critical_missing_fields": critical_missing_fields,
        "should_reject_prediction": should_reject,
        "notes": " ".join(context.notes) if context.notes else "All required providers returned data.",
        "provider_status": context.provider_status,
    }
