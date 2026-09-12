"""Durable daily catalog scheduling primitives."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import uuid

from services.catalog.storage import CatalogStore


@dataclass(frozen=True)
class DailySchedule:
    hour_utc: int = 6
    minute_utc: int = 0

    def __post_init__(self):
        if not 0 <= self.hour_utc <= 23 or not 0 <= self.minute_utc <= 59:
            raise ValueError("Daily schedule must use a valid UTC time")


class CatalogScheduler:
    """Claims and heartbeats one preparation run for a UTC calendar date."""

    def __init__(self, store: CatalogStore, *, schedule: DailySchedule | None = None,
                 lease_minutes: int = 45):
        self.store = store
        self.schedule = schedule or DailySchedule()
        self.lease_minutes = max(1, lease_minutes)

    def due(self, now: datetime) -> bool:
        current = now.astimezone(timezone.utc)
        target = current.replace(hour=self.schedule.hour_utc, minute=self.schedule.minute_utc,
                                second=0, microsecond=0)
        return current >= target

    def claim(self, *, now: datetime | None = None) -> str | None:
        current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        if not self.due(current):
            return None
        job_id = str(uuid.uuid4())
        lease_until = current + timedelta(minutes=self.lease_minutes)
        claimed = self.store.acquire_job(
            job_id=job_id, run_date=current.date().isoformat(),
            now=current.isoformat(), lease_until=lease_until.isoformat(),
        )
        return job_id if claimed else None

    def heartbeat(self, job_id: str, *, now: datetime | None = None) -> bool:
        current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        lease_until = current + timedelta(minutes=self.lease_minutes)
        return self.store.update_job(job_id, now=current.isoformat(), lease_until=lease_until.isoformat())

    def checkpoint(self, job_id: str, checkpoint: str, *, now: datetime | None = None) -> bool:
        current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        return self.store.update_job(job_id, now=current.isoformat(), checkpoint=checkpoint)

    def finish(self, job_id: str, state: str, *, summary: str | None = None,
               now: datetime | None = None) -> bool:
        if state not in {"partial", "success", "failed", "interrupted"}:
            raise ValueError(f"Invalid catalog terminal state: {state}")
        current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        return self.store.update_job(job_id, now=current.isoformat(), state=state, summary=summary)
