"""Provider ports and deterministic normalization helpers for the catalog."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Mapping, Protocol, cast, runtime_checkable

from services.catalog.contracts import (
    CanonicalRef,
    CatalogEvent,
    CatalogField,
    Confidence,
    FreshnessStatus,
    SourceObservation,
)


class ProviderStatus(StrEnum):
    AVAILABLE = "available"
    PARTIAL = "partial"
    UNAVAILABLE = "unavailable"


class ProviderErrorCategory(StrEnum):
    TIMEOUT = "timeout"
    RATE_LIMITED = "rate_limited"
    AUTHENTICATION = "authentication"
    INVALID_DATA = "invalid_data"
    UNAVAILABLE = "unavailable"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ProviderRequest:
    """Stable request identity passed to every catalog provider."""

    sport: str
    resource: str
    requested_at: str
    event_id: str | None = None
    entity_id: str | None = None
    date: str | None = None
    parameters: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ProviderResult:
    """Provider output at the boundary before normalization.

    ``facts`` must contain JSON-compatible values. Raw payloads are deliberately
    represented by an archive reference only; issue #323 owns raw persistence.
    """

    provider: str
    status: ProviderStatus
    retrieved_at: str
    facts: Mapping[str, Any] = field(default_factory=dict)
    observation: SourceObservation | None = None
    error_category: ProviderErrorCategory | None = None
    retryable: bool = False
    archive_reference: str | None = None
    quota_units: int = 0


@runtime_checkable
class CatalogProvider(Protocol):
    """Port implemented by direct APIs and grounded extraction adapters."""

    provider_name: str

    def fetch(self, request: ProviderRequest) -> ProviderResult: ...


class CatalogProviderError(RuntimeError):
    """Typed provider failure without requiring callers to parse messages."""

    def __init__(self, category: ProviderErrorCategory, *, retryable: bool = False):
        self.category = category
        self.retryable = retryable
        super().__init__(category.value)


def canonical_entity_id(sport: str, entity_type: str, provider_id: str | None = None,
                       display_name: str | None = None) -> str:
    """Create a stable local ID from a provider ID or normalized display name."""
    value = provider_id or display_name or "unknown"
    slug = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-") or "unknown"
    return f"{sport.casefold()}:{entity_type.casefold()}:{slug}"


def canonical_ref(sport: str, entity_type: str, *, provider_id: str | None = None,
                  display_name: str | None = None, provider: str | None = None) -> CanonicalRef:
    provider_ids = {provider: provider_id} if provider and provider_id else {}
    return CanonicalRef(
        entity_type=entity_type,
        canonical_id=canonical_entity_id(sport, entity_type, provider_id, display_name),
        display_name=display_name,
        provider_ids=provider_ids,
    )


def normalize_event(*, raw: Mapping[str, Any], sport: str, league: str,
                    provider: str, observed_at: str) -> tuple[CatalogEvent, SourceObservation]:
    """Normalize a provider event while retaining only explicit source facts."""
    home_name = raw.get("home_team") or raw.get("home")
    away_name = raw.get("away_team") or raw.get("away")
    provider_event_id = raw.get("event_id") or raw.get("id")
    event_id = canonical_entity_id(sport, "event", str(provider_event_id) if provider_event_id else None,
                                   f"{home_name}-{away_name}-{raw.get('start_time', 'unknown')}")
    observation = SourceObservation(
        observation_id=f"{provider}:{event_id}:{observed_at}",
        provider=provider,
        observed_at=observed_at,
        source_url=raw.get("source_url") if isinstance(raw.get("source_url"), str) else None,
        provider_record_id=str(provider_event_id) if provider_event_id is not None else None,
        extraction_method="direct",
        confidence=Confidence.CONFIRMED,
    )
    venue = raw.get("venue")
    event = CatalogEvent(
        event_id=event_id,
        sport=sport,
        league=league,
        start_time=str(raw.get("start_time") or raw.get("event_date") or "unknown"),
        status=str(raw.get("status") or "scheduled"),
        home_team=canonical_ref(sport, "team", display_name=str(home_name) if home_name else None,
                                provider=provider, provider_id=str(raw.get("home_team_id")) if raw.get("home_team_id") else None),
        away_team=canonical_ref(sport, "team", display_name=str(away_name) if away_name else None,
                                provider=provider, provider_id=str(raw.get("away_team_id")) if raw.get("away_team_id") else None),
        venue=cast(Mapping[str, Any], venue) if isinstance(venue, Mapping) else {},
        source_observation_ids=(observation.observation_id,),
    )
    return event, observation


def merge_field_observations(name: str, observations: list[tuple[Any, SourceObservation]],
                             *, valid_until: str | None = None) -> CatalogField:
    """Merge provider values deterministically and label disagreement as conflict."""
    if not observations:
        return CatalogField(name, None, valid_until=valid_until,
                            freshness=FreshnessStatus.UNKNOWN)
    first_value = observations[0][0]
    conflicting = any(value != first_value for value, _ in observations[1:])
    selected, source = observations[0]
    return CatalogField(
        name=name,
        value=selected,
        observed_at=source.observed_at,
        valid_until=valid_until,
        freshness=FreshnessStatus.FRESH,
        confidence=Confidence.UNKNOWN if conflicting else source.confidence,
        observation_id=source.observation_id,
        conflict_group=f"{name}:conflict" if conflicting else None,
    )
