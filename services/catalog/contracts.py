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
class PredictionMarketObservation:
    """A displayed prediction-market contract, deliberately distinct from odds."""

    market_id: str
    market_type: str
    selection: str
    displayed_price: str | None
    volume: str | None
    status: str
    observed_at: str
    source_url: str


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
    prediction_markets: tuple[PredictionMarketObservation, ...] = ()
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

    if is_dataclass(value) and not isinstance(value, type):
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


def canonical_ref_from_dict(data: Mapping[str, Any] | None) -> CanonicalRef | None:
    """Deserialize a CanonicalRef from a dictionary payload."""
    if not data:
        return None
    return CanonicalRef(
        entity_type=str(data["entity_type"]),
        canonical_id=str(data["canonical_id"]),
        display_name=str(data["display_name"]) if data.get("display_name") is not None else None,
        provider_ids=dict(data.get("provider_ids") or {}),
    )


def source_observation_from_dict(data: Mapping[str, Any]) -> SourceObservation:
    """Deserialize a SourceObservation from a dictionary payload."""
    conf = data.get("confidence")
    confidence_val = Confidence(conf) if conf in Confidence._value2member_map_ else Confidence.UNKNOWN
    return SourceObservation(
        observation_id=str(data["observation_id"]),
        provider=str(data["provider"]),
        observed_at=str(data["observed_at"]),
        source_url=str(data["source_url"]) if data.get("source_url") is not None else None,
        provider_record_id=str(data["provider_record_id"]) if data.get("provider_record_id") is not None else None,
        raw_archive_id=str(data["raw_archive_id"]) if data.get("raw_archive_id") is not None else None,
        extraction_method=str(data.get("extraction_method", "direct")),
        provider_version=str(data["provider_version"]) if data.get("provider_version") is not None else None,
        confidence=confidence_val,
    )


def catalog_field_from_dict(data: Mapping[str, Any]) -> CatalogField:
    """Deserialize a CatalogField from a dictionary payload."""
    fresh = data.get("freshness")
    freshness_val = FreshnessStatus(fresh) if fresh in FreshnessStatus._value2member_map_ else FreshnessStatus.UNKNOWN
    conf = data.get("confidence")
    confidence_val = Confidence(conf) if conf in Confidence._value2member_map_ else Confidence.UNKNOWN
    return CatalogField(
        name=str(data["name"]),
        value=data.get("value"),
        observed_at=str(data["observed_at"]) if data.get("observed_at") is not None else None,
        valid_until=str(data["valid_until"]) if data.get("valid_until") is not None else None,
        freshness=freshness_val,
        confidence=confidence_val,
        observation_id=str(data["observation_id"]) if data.get("observation_id") is not None else None,
        conflict_group=str(data["conflict_group"]) if data.get("conflict_group") is not None else None,
    )


def catalog_event_from_dict(data: Mapping[str, Any]) -> CatalogEvent:
    """Deserialize a CatalogEvent from a dictionary payload."""
    reasons = data.get("importance_reasons")
    obs_ids = data.get("source_observation_ids")
    return CatalogEvent(
        event_id=str(data["event_id"]),
        sport=str(data["sport"]),
        league=str(data["league"]),
        start_time=str(data["start_time"]),
        status=str(data.get("status", "scheduled")),
        home_team=canonical_ref_from_dict(data.get("home_team")),
        away_team=canonical_ref_from_dict(data.get("away_team")),
        venue=dict(data.get("venue") or {}),
        importance_score=float(data["importance_score"]) if data.get("importance_score") is not None else None,
        importance_reasons=tuple(str(r) for r in reasons) if reasons is not None else (),
        source_observation_ids=tuple(str(o) for o in obs_ids) if obs_ids is not None else (),
    )


def lineup_snapshot_from_dict(data: Mapping[str, Any]) -> LineupSnapshot:
    """Deserialize a LineupSnapshot from a dictionary payload."""
    conf = data.get("status")
    status_val = Confidence(conf) if conf in Confidence._value2member_map_ else Confidence.UNKNOWN
    players = [canonical_ref_from_dict(p) for p in data.get("players") or ()]
    return LineupSnapshot(
        event_id=str(data["event_id"]),
        team_id=str(data["team_id"]),
        status=status_val,
        players=tuple(p for p in players if p is not None),
        formation=str(data["formation"]) if data.get("formation") is not None else None,
        observed_at=str(data["observed_at"]) if data.get("observed_at") is not None else None,
        valid_until=str(data["valid_until"]) if data.get("valid_until") is not None else None,
        observation_id=str(data["observation_id"]) if data.get("observation_id") is not None else None,
    )


def injury_snapshot_from_dict(data: Mapping[str, Any]) -> InjurySnapshot:
    """Deserialize an InjurySnapshot from a dictionary payload."""
    subject = canonical_ref_from_dict(data.get("subject"))
    if subject is None:
        raise ValueError("InjurySnapshot requires subject CanonicalRef")
    return InjurySnapshot(
        event_id=str(data["event_id"]),
        subject=subject,
        status=str(data.get("status", "unknown")),
        reason=str(data["reason"]) if data.get("reason") is not None else None,
        expected_return=str(data["expected_return"]) if data.get("expected_return") is not None else None,
        observed_at=str(data["observed_at"]) if data.get("observed_at") is not None else None,
        valid_until=str(data["valid_until"]) if data.get("valid_until") is not None else None,
        observation_id=str(data["observation_id"]) if data.get("observation_id") is not None else None,
    )


def prediction_market_from_dict(data: Mapping[str, Any]) -> PredictionMarketObservation:
    """Deserialize a PredictionMarketObservation from a dictionary payload."""
    return PredictionMarketObservation(
        market_id=str(data["market_id"]),
        market_type=str(data["market_type"]),
        selection=str(data["selection"]),
        displayed_price=str(data["displayed_price"]) if data.get("displayed_price") is not None else None,
        volume=str(data["volume"]) if data.get("volume") is not None else None,
        status=str(data.get("status", "active")),
        observed_at=str(data["observed_at"]),
        source_url=str(data.get("source_url", "")),
    )


def snapshot_from_dict(data: Mapping[str, Any]) -> CatalogSnapshot:
    """Deserialize a full CatalogSnapshot from a dictionary payload."""
    completeness_raw = data.get("completeness")
    completeness_val = (
        CompletenessStatus(completeness_raw)
        if completeness_raw in CompletenessStatus._value2member_map_
        else CompletenessStatus.UNKNOWN
    )
    event_raw = data.get("event")
    if not event_raw or not isinstance(event_raw, Mapping):
        raise ValueError("CatalogSnapshot requires event Mapping")
    return CatalogSnapshot(
        snapshot_id=str(data["snapshot_id"]),
        event=catalog_event_from_dict(event_raw),
        created_at=str(data["created_at"]),
        as_of=str(data["as_of"]),
        completeness=completeness_val,
        fields=tuple(catalog_field_from_dict(f) for f in data.get("fields") or ()),
        lineups=tuple(lineup_snapshot_from_dict(lineup) for lineup in data.get("lineups") or ()),
        injuries=tuple(injury_snapshot_from_dict(i) for i in data.get("injuries") or ()),
        prediction_markets=tuple(prediction_market_from_dict(p) for p in data.get("prediction_markets") or ()),
        source_observations=tuple(source_observation_from_dict(s) for s in data.get("source_observations") or ()),
        missing_fields=tuple(str(m) for m in data.get("missing_fields") or ()),
        conflicting_fields=tuple(str(c) for c in data.get("conflicting_fields") or ()),
        normalization_version=str(data.get("normalization_version", "1")),
    )
