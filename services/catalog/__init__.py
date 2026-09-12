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
]
