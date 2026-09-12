"""Safe rollout modes for introducing catalog-backed reads."""

from __future__ import annotations

from enum import StrEnum


class CatalogReadMode(StrEnum):
    SHADOW = "shadow"
    CATALOG_FIRST = "catalog_first"
    LIVE = "live"


def resolve_read_mode(value: str | None, *, default: CatalogReadMode = CatalogReadMode.SHADOW) -> CatalogReadMode:
    """Resolve configuration while keeping unknown values safe and deterministic."""
    if not value:
        return default
    try:
        return CatalogReadMode(value.casefold().strip())
    except ValueError:
        return default


def should_use_catalog(mode: CatalogReadMode, *, snapshot_available: bool) -> bool:
    return mode == CatalogReadMode.CATALOG_FIRST and snapshot_available
