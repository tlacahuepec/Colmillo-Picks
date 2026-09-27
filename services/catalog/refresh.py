"""Manual catalog-refresh orchestration for public Fanatics Markets data."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Callable
from uuid import uuid4

from services.catalog.fanatics_markets import FanaticsMarketsCollector, FanaticsMarketsError
from services.catalog.storage import CatalogStore


def start_fanatics_refresh(store: CatalogStore, *, run_date: str, now: datetime | None = None) -> str | None:
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    job_id = str(uuid4())
    claimed = store.acquire_job(
        job_id=job_id, run_date=run_date, now=current.isoformat(),
        lease_until=(current + timedelta(minutes=15)).isoformat(), force=True,
    )
    return job_id if claimed else None


def run_fanatics_refresh(
    store: CatalogStore, *, job_id: str, run_date: str,
    collector_factory: Callable[[], FanaticsMarketsCollector] = FanaticsMarketsCollector,
) -> None:
    try:
        result = collector_factory().collect(run_date=run_date)
        skipped_by_sport: dict[str, int] = {}
        persisted = []
        for snapshot in result.snapshots:
            sport = store.register_discovered_sport(snapshot.event.sport)
            if store.is_sport_enabled(sport):
                store.save_snapshot(snapshot)
                persisted.append(snapshot)
            else:
                skipped_by_sport[sport] = skipped_by_sport.get(sport, 0) + 1
        state = "success" if persisted else "partial"
        summary = json.dumps({"snapshots": len(persisted), "market_observations": sum(
            len(snapshot.prediction_markets) for snapshot in persisted
        ), "skipped_by_sport": skipped_by_sport,
           "supplemental_signals": result.supplemental_signals,
           "unavailable_pages": result.unavailable_pages})
        store.update_job(job_id, now=datetime.now(timezone.utc).isoformat(), state=state, summary=summary)
    except FanaticsMarketsError as exc:
        store.update_job(job_id, now=datetime.now(timezone.utc).isoformat(), state="failed", summary=str(exc))
    except Exception:
        store.update_job(job_id, now=datetime.now(timezone.utc).isoformat(), state="failed", summary="Catalog refresh failed.")
