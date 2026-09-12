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
from services.catalog.graph import CatalogGraphDeps, CatalogGraphState, build_catalog_graph, run_catalog_graph
from services.catalog.sport_adapters import SoccerCatalogAdapter, SportCatalogConfig

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
    "CatalogGraphDeps",
    "CatalogGraphState",
    "build_catalog_graph",
    "run_catalog_graph",
    "SoccerCatalogAdapter",
    "SportCatalogConfig",
]
