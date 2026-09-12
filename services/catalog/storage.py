"""SQLite persistence for normalized sports catalog records.

The store keeps immutable snapshots alongside a current event index. Provider
payload archival and its privacy policy belong to issue #323; this layer stores
only archive references and normalized contract data.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from services.catalog.contracts import (
    CatalogEvent,
    CatalogSnapshot,
    SourceObservation,
    to_catalog_dict,
)


class CatalogStore:
    """Small SQLite repository with idempotent writes and immutable snapshots."""

    def __init__(self, path: str | Path):
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=5, check_same_thread=False)
        connection.row_factory = sqlite3.Row
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA foreign_keys=ON")
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS catalog_events (
                    event_id TEXT PRIMARY KEY,
                    sport TEXT NOT NULL,
                    league TEXT NOT NULL,
                    start_time TEXT NOT NULL,
                    status TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS catalog_events_sport_start
                    ON catalog_events(sport, start_time);
                CREATE TABLE IF NOT EXISTS catalog_snapshots (
                    snapshot_id TEXT PRIMARY KEY,
                    event_id TEXT NOT NULL REFERENCES catalog_events(event_id),
                    created_at TEXT NOT NULL,
                    as_of TEXT NOT NULL,
                    completeness TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    normalization_version TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS catalog_snapshots_event_created
                    ON catalog_snapshots(event_id, created_at DESC);
                CREATE TABLE IF NOT EXISTS catalog_observations (
                    observation_id TEXT PRIMARY KEY,
                    provider TEXT NOT NULL,
                    observed_at TEXT NOT NULL,
                    source_url TEXT,
                    provider_record_id TEXT,
                    raw_archive_id TEXT,
                    extraction_method TEXT NOT NULL,
                    provider_version TEXT,
                    confidence TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS catalog_observations_provider_time
                    ON catalog_observations(provider, observed_at DESC);
                CREATE TABLE IF NOT EXISTS catalog_job_runs (
                    job_id TEXT PRIMARY KEY,
                    run_date TEXT NOT NULL,
                    state TEXT NOT NULL,
                    started_at TEXT,
                    updated_at TEXT NOT NULL,
                    checkpoint TEXT,
                    summary TEXT
                );
                CREATE INDEX IF NOT EXISTS catalog_job_runs_date
                    ON catalog_job_runs(run_date, updated_at DESC);
                """
            )

    def upsert_event(self, event: CatalogEvent) -> None:
        payload = json.dumps(to_catalog_dict(event), ensure_ascii=True, allow_nan=False)
        updated_at = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO catalog_events
                   (event_id,sport,league,start_time,status,payload,updated_at)
                   VALUES (?,?,?,?,?,?,?)
                   ON CONFLICT(event_id) DO UPDATE SET
                   sport=excluded.sport, league=excluded.league,
                   start_time=excluded.start_time, status=excluded.status,
                   payload=excluded.payload, updated_at=excluded.updated_at""",
                (event.event_id, event.sport, event.league, event.start_time,
                 event.status, payload, updated_at),
            )

    def save_observation(self, observation: SourceObservation) -> None:
        payload = to_catalog_dict(observation)
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO catalog_observations
                   (observation_id,provider,observed_at,source_url,provider_record_id,
                    raw_archive_id,extraction_method,provider_version,confidence)
                   VALUES (:observation_id,:provider,:observed_at,:source_url,
                    :provider_record_id,:raw_archive_id,:extraction_method,
                    :provider_version,:confidence)
                   ON CONFLICT(observation_id) DO UPDATE SET
                    provider=excluded.provider, observed_at=excluded.observed_at,
                    source_url=excluded.source_url, provider_record_id=excluded.provider_record_id,
                    raw_archive_id=excluded.raw_archive_id,
                    extraction_method=excluded.extraction_method,
                    provider_version=excluded.provider_version, confidence=excluded.confidence""",
                {**payload, "confidence": payload["confidence"]},
            )

    def save_snapshot(self, snapshot: CatalogSnapshot) -> None:
        """Persist one immutable snapshot and its event/observation references."""
        self.upsert_event(snapshot.event)
        for observation in snapshot.source_observations:
            self.save_observation(observation)
        payload = json.dumps(to_catalog_dict(snapshot), ensure_ascii=True, allow_nan=False)
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO catalog_snapshots
                   (snapshot_id,event_id,created_at,as_of,completeness,payload,normalization_version)
                   VALUES (?,?,?,?,?,?,?)
                   ON CONFLICT(snapshot_id) DO NOTHING""",
                (snapshot.snapshot_id, snapshot.event.event_id, snapshot.created_at,
                 snapshot.as_of, snapshot.completeness.value, payload,
                 snapshot.normalization_version),
            )

    @staticmethod
    def _decode_snapshot(payload: str) -> dict:
        value = json.loads(payload)
        if not isinstance(value, dict):
            raise ValueError("Stored catalog snapshot is not an object")
        return value

    def get_snapshot(self, snapshot_id: str) -> dict | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload FROM catalog_snapshots WHERE snapshot_id=?", (snapshot_id,)
            ).fetchone()
        return self._decode_snapshot(row["payload"]) if row else None

    def get_latest_snapshot(self, event_id: str) -> dict | None:
        with self._connect() as connection:
            row = connection.execute(
                """SELECT payload FROM catalog_snapshots
                   WHERE event_id=? ORDER BY created_at DESC, snapshot_id DESC LIMIT 1""",
                (event_id,),
            ).fetchone()
        return self._decode_snapshot(row["payload"]) if row else None

    def list_events(self, *, sport: str | None = None, start_from: str | None = None,
                    start_to: str | None = None, limit: int = 100, offset: int = 0) -> list[dict]:
        conditions, params = [], []
        if sport:
            conditions.append("sport=?")
            params.append(sport)
        if start_from:
            conditions.append("start_time>=?")
            params.append(start_from)
        if start_to:
            conditions.append("start_time<?")
            params.append(start_to)
        where = " WHERE " + " AND ".join(conditions) if conditions else ""
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT payload FROM catalog_events" + where
                + " ORDER BY start_time,event_id LIMIT ? OFFSET ?",
                (*params, min(max(limit, 1), 1000), max(offset, 0)),
            ).fetchall()
        return [self._decode_snapshot(row["payload"]) for row in rows]

    def health(self) -> dict:
        with self._connect() as connection:
            counts = {
                "events": connection.execute("SELECT COUNT(*) FROM catalog_events").fetchone()[0],
                "snapshots": connection.execute("SELECT COUNT(*) FROM catalog_snapshots").fetchone()[0],
                "observations": connection.execute("SELECT COUNT(*) FROM catalog_observations").fetchone()[0],
            }
        return {"available": True, "path": self.path, **counts}
