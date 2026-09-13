"""Catalog-first read decisions used by pick and slate orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Callable

from services.catalog.contracts import CatalogSnapshot
from services.catalog.freshness import DEFAULT_FRESHNESS_POLICY, FreshnessDecision, FreshnessPolicy, evaluate_snapshot, resources_to_refresh


@dataclass(frozen=True)
class CatalogReadResult:
    snapshot: CatalogSnapshot | None
    decisions: tuple[FreshnessDecision, ...]
    refresh_resources: tuple[str, ...]
    source: str


class CatalogFirstReader:
    """Read local data first and optionally refresh only requested stale resources."""

    def __init__(self, *, lookup: Callable[[str, str, str, str], CatalogSnapshot | None],
                 refresh: Callable[[str, str, str, str, tuple[str, ...]], CatalogSnapshot | None] | None = None,
                 policy: FreshnessPolicy | None = None) -> None:
        self._lookup = lookup
        self._refresh = refresh
        self._policy = policy or DEFAULT_FRESHNESS_POLICY

    def read(self, *, sport: str, home_team: str, away_team: str, event_date: str,
             requested_resources: tuple[str, ...] = (), now: datetime) -> CatalogReadResult:
        snapshot = self._lookup(sport, home_team, away_team, event_date)
        if snapshot is None:
            resources = tuple(sorted(set(requested_resources)))
            if self._refresh:
                refreshed = self._refresh(sport, home_team, away_team, event_date, resources)
                if refreshed is not None:
                    return self._result(refreshed, resources, "refreshed", now)
            return CatalogReadResult(None, (), resources, "live")
        stale = set(resources_to_refresh(snapshot, now=now, policy=self._policy))
        resources = tuple(sorted(stale | set(requested_resources)))
        if resources and self._refresh:
            refreshed = self._refresh(sport, home_team, away_team, event_date, resources)
            if refreshed is not None:
                return self._result(refreshed, resources, "refreshed", now)
        return self._result(snapshot, resources, "catalog" if not resources else "catalog_stale", now)

    def _result(self, snapshot: CatalogSnapshot, resources: tuple[str, ...], source: str,
                now: datetime) -> CatalogReadResult:
        return CatalogReadResult(snapshot, evaluate_snapshot(snapshot, now=now, policy=self._policy), resources, source)
