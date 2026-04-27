"""Provider resolution and fallback decisions for collect_match_inputs."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ResolutionContext:
    critical_missing_fields: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def resolve_fixture(request: Any, fixture_provider: Any, fallback_fixture_fn: Any, context: ResolutionContext) -> dict[str, Any]:
    fixture = fixture_provider.lookup_fixture(request)
    if fixture:
        return fixture

    context.critical_missing_fields.append("match")
    context.notes.append("Fixture provider unavailable; used deterministic fallback fixture metadata.")
    return fallback_fixture_fn(request)


def resolve_lineup(fixture: dict[str, Any], lineup_provider: Any, fallback_lineup_provider: Any, context: ResolutionContext) -> dict[str, Any]:
    lineup_payload = lineup_provider.get_lineups_and_availability(fixture)
    if lineup_payload:
        return lineup_payload

    context.critical_missing_fields.append("teams.projected_lineup")
    context.notes.append("Lineup provider unavailable; used deterministic projected lineups and players.")
    return fallback_lineup_provider.get_lineups_and_availability(fixture)


def resolve_market(fixture: dict[str, Any], odds_provider: Any, fallback_odds_provider: Any, context: ResolutionContext) -> dict[str, Any]:
    market_payload = odds_provider.get_odds_snapshots(fixture)
    if market_payload:
        return market_payload

    context.critical_missing_fields.append("market.sportsbook_snapshots")
    context.notes.append("Odds provider unavailable; used deterministic synthetic odds snapshots.")
    return fallback_odds_provider.get_odds_snapshots(fixture)


def resolve_weather(fixture: dict[str, Any], weather_provider: Any, fallback_weather_provider: Any, context: ResolutionContext) -> dict[str, Any]:
    weather_payload = weather_provider.get_weather(fixture)
    if weather_payload:
        return weather_payload

    context.critical_missing_fields.append("match.weather")
    context.notes.append("Weather provider unavailable; used neutral weather assumptions.")
    return fallback_weather_provider.get_weather(fixture)


def resolve_timestamp(payload: dict[str, Any], timestamp_key: str, missing_note: str, now_utc_fn: Any, context: ResolutionContext) -> str:
    timestamp = payload.get(timestamp_key) or now_utc_fn()
    if timestamp_key not in payload:
        context.notes.append(missing_note)
    return timestamp


def append_players_missing(context: ResolutionContext) -> None:
    context.critical_missing_fields.append("players")
    context.notes.append("No player-level provider data returned; used deterministic fallback players.")


def append_insufficient_snapshots(context: ResolutionContext) -> None:
    context.critical_missing_fields.append("market.sportsbook_snapshots")
    context.notes.append("Insufficient odds snapshots from provider; padded with deterministic fallback snapshots.")


def build_validation(context: ResolutionContext) -> dict[str, Any]:
    critical_missing_fields = sorted(set(context.critical_missing_fields))
    should_reject = any(field in {"match", "players", "market.sportsbook_snapshots"} for field in critical_missing_fields)
    return {
        "critical_missing_fields": critical_missing_fields,
        "should_reject_prediction": should_reject,
        "notes": " ".join(context.notes) if context.notes else "All required providers returned data.",
    }
