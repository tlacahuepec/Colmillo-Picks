"""Shared contracts and persistence for the local sports intelligence catalog."""

from services.catalog.contracts import (
    CatalogEvent,
    CatalogSnapshot,
    CompletenessStatus,
    Confidence,
    FreshnessStatus,
    SourceObservation,
)
from services.catalog.storage import CatalogStore
from services.catalog.providers import CatalogProvider, ProviderRequest, ProviderResult
from services.catalog.importance import ImportanceConfig, rank_events, score_event, select_important_events
from services.catalog.scheduler import CatalogScheduler, DailySchedule

__all__ = [
    "CatalogEvent",
    "CatalogSnapshot",
    "CompletenessStatus",
    "Confidence",
    "FreshnessStatus",
    "SourceObservation",
    "CatalogStore",
    "CatalogProvider",
    "ProviderRequest",
    "ProviderResult",
    "ImportanceConfig",
    "score_event",
    "rank_events",
    "select_important_events",
    "CatalogScheduler",
    "DailySchedule",
]
