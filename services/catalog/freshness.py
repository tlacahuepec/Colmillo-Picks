"""Field-level freshness and selective refresh decisions for the catalog."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable

from services.catalog.contracts import CatalogField, CatalogSnapshot, FreshnessStatus


DEFAULT_FIELD_TTLS: dict[str, timedelta] = {
    "markets": timedelta(minutes=15),
    "odds": timedelta(minutes=15),
    "lineups": timedelta(hours=2),
    "injuries": timedelta(hours=2),
    "weather": timedelta(hours=3),
    "form": timedelta(hours=24),
    "stable": timedelta(hours=24),
}


@dataclass(frozen=True)
class FreshnessPolicy:
    """Configurable TTLs used without making network calls."""

    field_ttls: dict[str, timedelta]
    default_ttl: timedelta = timedelta(hours=24)

    def ttl_for(self, field_name: str) -> timedelta:
        if field_name in self.field_ttls:
            return self.field_ttls[field_name]
        prefix = field_name.split(".", 1)[0]
        return self.field_ttls.get(prefix, self.default_ttl)


DEFAULT_FRESHNESS_POLICY = FreshnessPolicy(DEFAULT_FIELD_TTLS)


@dataclass(frozen=True)
class FreshnessDecision:
    field_name: str
    status: FreshnessStatus
    should_refresh: bool
    observed_at: str | None = None
    valid_until: str | None = None


def classify_timestamp(*, observed_at: str | None, valid_until: str | None,
                       now: datetime, ttl: timedelta) -> FreshnessStatus:
    """Classify a timestamp pair; malformed or absent timestamps stay unknown."""
    if not observed_at:
        return FreshnessStatus.UNKNOWN
    observed = _parse_timestamp(observed_at)
    if observed is None:
        return FreshnessStatus.UNKNOWN
    if valid_until:
        expiry = _parse_timestamp(valid_until)
        if expiry is None:
            return FreshnessStatus.UNKNOWN
    else:
        expiry = observed + ttl
    if now < observed:
        return FreshnessStatus.UNKNOWN
    if now <= expiry:
        return FreshnessStatus.FRESH
    if now <= expiry + ttl:
        return FreshnessStatus.STALE
    return FreshnessStatus.EXPIRED


def evaluate_field(field: CatalogField, *, now: datetime,
                   policy: FreshnessPolicy = DEFAULT_FRESHNESS_POLICY) -> FreshnessDecision:
    status = classify_timestamp(
        observed_at=field.observed_at, valid_until=field.valid_until,
        now=now, ttl=policy.ttl_for(field.name),
    )
    return FreshnessDecision(field.name, status, status in {
        FreshnessStatus.STALE, FreshnessStatus.EXPIRED, FreshnessStatus.UNKNOWN,
    }, field.observed_at, field.valid_until)


def evaluate_snapshot(snapshot: CatalogSnapshot, *, now: datetime,
                      policy: FreshnessPolicy = DEFAULT_FRESHNESS_POLICY) -> tuple[FreshnessDecision, ...]:
    decisions = [evaluate_field(field, now=now, policy=policy) for field in snapshot.fields]
    decisions.extend(_evaluate_collection("lineups", item.observed_at, item.valid_until, now, policy) for item in snapshot.lineups)
    decisions.extend(_evaluate_collection("injuries", item.observed_at, item.valid_until, now, policy) for item in snapshot.injuries)
    return tuple(decisions)


def resources_to_refresh(snapshot: CatalogSnapshot, *, now: datetime,
                        policy: FreshnessPolicy = DEFAULT_FRESHNESS_POLICY) -> tuple[str, ...]:
    """Return unique resource names requiring refresh, in stable order."""
    return tuple(sorted({decision.field_name for decision in evaluate_snapshot(snapshot, now=now, policy=policy)
                         if decision.should_refresh}))


def missing_resources(snapshot: CatalogSnapshot, requested: Iterable[str]) -> tuple[str, ...]:
    """Return requested resources absent from the snapshot's explicit facts."""
    present = {field.name.split(".", 1)[0] for field in snapshot.fields}
    if snapshot.lineups:
        present.add("lineups")
    if snapshot.injuries:
        present.add("injuries")
    return tuple(sorted(set(requested) - present))


def _evaluate_collection(name: str, observed_at: str | None, valid_until: str | None,
                         now: datetime, policy: FreshnessPolicy) -> FreshnessDecision:
    status = classify_timestamp(observed_at=observed_at, valid_until=valid_until,
                                now=now, ttl=policy.ttl_for(name))
    return FreshnessDecision(name, status, status in {
        FreshnessStatus.STALE, FreshnessStatus.EXPIRED, FreshnessStatus.UNKNOWN,
    }, observed_at, valid_until)


def _parse_timestamp(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)
