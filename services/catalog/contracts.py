"""Framework-independent contracts for the local sports intelligence catalog.

These types describe normalized facts and their provenance. Provider payloads,
database rows and API responses should be converted at the boundaries instead of
being passed through the application as untyped dictionaries.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from enum import StrEnum
from typing import Any, Mapping


CATALOG_SCHEMA_VERSION = 1


class FreshnessStatus(StrEnum):
    """Field-level freshness classification used by read and refresh policies."""

    FRESH = "fresh"
    STALE = "stale"
    EXPIRED = "expired"
    UNKNOWN = "unknown"
    NOT_APPLICABLE = "not_applicable"


class CompletenessStatus(StrEnum):
    """Whether a snapshot contains enough information for its intended use."""

    COMPLETE = "complete"
    PARTIAL = "partial"
    CONFLICTING = "conflicting"
    FAILED = "failed"
    UNKNOWN = "unknown"


class Confidence(StrEnum):
    """Confidence in a normalized fact, independent of freshness."""

    CONFIRMED = "confirmed"
    PROJECTED = "projected"
    ESTIMATED = "estimated"
    LOW = "low"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class CanonicalRef:
    """A stable local identity with optional provider-native aliases."""

    entity_type: str
    canonical_id: str
    display_name: str | None = None
    provider_ids: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class SourceObservation:
    """Provenance for one normalized observation.

    ``raw_archive_id`` points to separately governed source content. It is never
    the raw content itself and may be absent when a provider returns structured
    data that is safe to retain only as normalized facts.
    """

    observation_id: str
    provider: str
    observed_at: str
    source_url: str | None = None
    provider_record_id: str | None = None
    raw_archive_id: str | None = None
    extraction_method: str = "direct"
    provider_version: str | None = None
    confidence: Confidence = Confidence.UNKNOWN


@dataclass(frozen=True)
class CatalogField:
    """A normalized value plus the metadata needed to decide whether to reuse it."""

    name: str
    value: Any
    observed_at: str | None = None
    valid_until: str | None = None
    freshness: FreshnessStatus = FreshnessStatus.UNKNOWN
    confidence: Confidence = Confidence.UNKNOWN
    observation_id: str | None = None
    conflict_group: str | None = None


@dataclass(frozen=True)
class CatalogEvent:
    """Canonical scheduled event shared by all sports."""

    event_id: str
    sport: str
    league: str
    start_time: str
    status: str = "scheduled"
    home_team: CanonicalRef | None = None
    away_team: CanonicalRef | None = None
    venue: Mapping[str, Any] = field(default_factory=dict)
    importance_score: float | None = None
    importance_reasons: tuple[str, ...] = ()
    source_observation_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class LineupSnapshot:
    """Confirmed or projected participants for one event and team."""

    event_id: str
    team_id: str
    status: Confidence
    players: tuple[CanonicalRef, ...] = ()
    formation: str | None = None
    observed_at: str | None = None
    valid_until: str | None = None
    observation_id: str | None = None


@dataclass(frozen=True)
class InjurySnapshot:
    """Availability observation for a player or team member."""

    event_id: str
    subject: CanonicalRef
    status: str
    reason: str | None = None
    expected_return: str | None = None
    observed_at: str | None = None
    valid_until: str | None = None
    observation_id: str | None = None


@dataclass(frozen=True)
class CatalogSnapshot:
    """Versioned normalized facts for one event."""

    snapshot_id: str
    event: CatalogEvent
    created_at: str
    as_of: str
    completeness: CompletenessStatus = CompletenessStatus.UNKNOWN
    fields: tuple[CatalogField, ...] = ()
    lineups: tuple[LineupSnapshot, ...] = ()
    injuries: tuple[InjurySnapshot, ...] = ()
    source_observations: tuple[SourceObservation, ...] = ()
    missing_fields: tuple[str, ...] = ()
    conflicting_fields: tuple[str, ...] = ()
    normalization_version: str = "1"

    @property
    def schema_version(self) -> int:
        return CATALOG_SCHEMA_VERSION

    def field(self, name: str) -> CatalogField | None:
        """Return the newest field with ``name`` from this immutable snapshot."""
        matches = [item for item in self.fields if item.name == name]
        return matches[-1] if matches else None


def to_catalog_dict(value: Any) -> Any:
    """Convert contracts to bounded JSON-compatible primitives.

    This helper intentionally does not stringify arbitrary objects. Values inside
    ``CatalogField.value`` must already be JSON-compatible provider output.
    """

    if is_dataclass(value):
        payload = {key: to_catalog_dict(item) for key, item in asdict(value).items()}
        if isinstance(value, CatalogSnapshot):
            payload["schema_version"] = value.schema_version
        return payload
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, Mapping):
        return {str(key): to_catalog_dict(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [to_catalog_dict(item) for item in value]
    if value is None or type(value) in (str, int, float, bool):
        return value
    raise TypeError(f"Catalog value is not JSON-compatible: {type(value).__name__}")
