"""SQLite persistence for normalized sports catalog records.

The store keeps immutable snapshots alongside a current event index. Provider
payload archival and its privacy policy belong to issue #323; this layer stores
only archive references and normalized contract data.
"""

from __future__ import annotations

import json
import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from services.catalog.contracts import (
    CanonicalRef,
    CatalogEvent,
    CatalogSnapshot,
    SourceObservation,
    catalog_event_from_dict,
    snapshot_from_dict,
    to_catalog_dict,
)
from services.catalog.archive import ArchivePolicy, archive_expiry, prepare_archive, utc_now


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
                    summary TEXT,
                    lease_owner TEXT,
                    lease_until TEXT,
                    attempt INTEGER NOT NULL DEFAULT 1
                );
                CREATE TABLE IF NOT EXISTS catalog_raw_archives (
                    archive_id TEXT PRIMARY KEY,
                    provider TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    warning TEXT NOT NULL,
                    read_count INTEGER NOT NULL DEFAULT 0
                );
                CREATE INDEX IF NOT EXISTS catalog_job_runs_date
                    ON catalog_job_runs(run_date, updated_at DESC);
                CREATE TABLE IF NOT EXISTS match_discovery_cache (
                    cache_key TEXT PRIMARY KEY,
                    response_json TEXT NOT NULL,
                    confidence TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS match_discovery_cache_expiry
                    ON match_discovery_cache(expires_at);
                CREATE TABLE IF NOT EXISTS catalog_sport_settings (
                    sport TEXT PRIMARY KEY,
                    enabled INTEGER NOT NULL CHECK(enabled IN (0, 1)),
                    discovered_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                """
            )
            existing = {row[1] for row in connection.execute("PRAGMA table_info(catalog_job_runs)")}
            for name, definition in (("lease_owner", "TEXT"), ("lease_until", "TEXT"), ("attempt", "INTEGER NOT NULL DEFAULT 1")):
                if name not in existing:
                    connection.execute(f"ALTER TABLE catalog_job_runs ADD COLUMN {name} {definition}")
            self._bootstrap_sport_settings(connection)

    @staticmethod
    def normalize_sport(value: str) -> str:
        """Return the stable key used by catalog persistence policy."""
        normalized = re.sub(r"[^a-z0-9]+", "_", value.casefold()).strip("_")
        if not normalized:
            raise ValueError("sport must contain letters or numbers")
        return normalized

    def _bootstrap_sport_settings(self, connection: sqlite3.Connection) -> None:
        """Seed supported sports once and retain all historical sport discoveries."""
        now = utc_now()
        existing = connection.execute("SELECT COUNT(*) FROM catalog_sport_settings").fetchone()[0]
        if existing:
            return
        enabled_defaults = {"soccer", "basketball", "baseball", "nfl"}
        discovered = {
            self.normalize_sport(row[0])
            for row in connection.execute("SELECT DISTINCT sport FROM catalog_events")
        }
        for sport in sorted(enabled_defaults | discovered):
            connection.execute(
                "INSERT INTO catalog_sport_settings(sport,enabled,discovered_at,updated_at) VALUES (?,?,?,?)",
                (sport, int(sport in enabled_defaults), now, now),
            )

    def register_discovered_sport(self, sport: str) -> str:
        key = self.normalize_sport(sport)
        now = utc_now()
        with self._connect() as connection:
            connection.execute(
                "INSERT OR IGNORE INTO catalog_sport_settings(sport,enabled,discovered_at,updated_at) VALUES (?,?,?,?)",
                (key, 0, now, now),
            )
        return key

    def set_sport_enabled(self, sport: str, *, enabled: bool) -> dict:
        key = self.register_discovered_sport(sport)
        with self._connect() as connection:
            connection.execute(
                "UPDATE catalog_sport_settings SET enabled=?,updated_at=? WHERE sport=?",
                (int(enabled), utc_now(), key),
            )
        return {"sport": key, "enabled": enabled}

    def is_sport_enabled(self, sport: str) -> bool:
        key = self.normalize_sport(sport)
        with self._connect() as connection:
            row = connection.execute(
                "SELECT enabled FROM catalog_sport_settings WHERE sport=?", (key,)
            ).fetchone()
        return bool(row["enabled"]) if row is not None else False

    def list_sport_settings(self) -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT sport,enabled,discovered_at,updated_at FROM catalog_sport_settings ORDER BY sport"
            ).fetchall()
            event_rows = connection.execute("SELECT sport,COUNT(*) AS count FROM catalog_events GROUP BY sport").fetchall()
        counts: dict[str, int] = {}
        for row in event_rows:
            key = self.normalize_sport(row["sport"])
            counts[key] = counts.get(key, 0) + row["count"]
        return [
            {**dict(row), "enabled": bool(row["enabled"]), "retained_events": counts.get(row["sport"], 0)}
            for row in rows
        ]

    def upsert_event(self, event: CatalogEvent) -> None:
        self.register_discovered_sport(event.sport)
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

    def get_discovery_cache(self, cache_key: str, *, now: str) -> dict | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT response_json,confidence,created_at,expires_at FROM match_discovery_cache WHERE cache_key=? AND expires_at>?",
                (cache_key, now),
            ).fetchone()
        if row is None:
            return None
        response = self._decode_snapshot(row["response_json"])
        response["cache_status"] = "cached"
        response["cache_confidence"] = row["confidence"]
        response["cache_expires_at"] = row["expires_at"]
        return response

    def save_discovery_cache(
        self, *, cache_key: str, response: dict, confidence: str, created_at: str, expires_at: str,
    ) -> None:
        payload = json.dumps(response, ensure_ascii=True, allow_nan=False)
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO match_discovery_cache(cache_key,response_json,confidence,created_at,expires_at)
                   VALUES(?,?,?,?,?)
                   ON CONFLICT(cache_key) DO UPDATE SET response_json=excluded.response_json,
                   confidence=excluded.confidence,created_at=excluded.created_at,expires_at=excluded.expires_at""",
                (cache_key, payload, confidence, created_at, expires_at),
            )

    def clear_discovery_cache(self, cache_key: str) -> bool:
        with self._connect() as connection:
            result = connection.execute("DELETE FROM match_discovery_cache WHERE cache_key=?", (cache_key,))
        return bool(result.rowcount)

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

    def get_latest_snapshot_object(self, event_id: str) -> CatalogSnapshot | None:
        """Return the latest snapshot for event_id as a typed CatalogSnapshot."""
        with self._connect() as connection:
            row = connection.execute(
                """SELECT payload FROM catalog_snapshots
                   WHERE event_id=? ORDER BY created_at DESC, snapshot_id DESC LIMIT 1""",
                (event_id,),
            ).fetchone()
        return snapshot_from_dict(self._decode_snapshot(row["payload"])) if row else None

    @classmethod
    def _match_team(cls, team: CanonicalRef | None, target_name: str) -> bool:
        if not team or not target_name:
            return False
        target = cls.normalize_sport(target_name) if target_name.strip() else ""
        if not target:
            return False

        candidates: list[str] = []
        if team.canonical_id:
            candidates.append(cls.normalize_sport(team.canonical_id))
            slug = team.canonical_id.split(":")[-1]
            candidates.append(cls.normalize_sport(slug))
        if team.display_name:
            candidates.append(cls.normalize_sport(team.display_name))
        for alias in team.provider_ids.values():
            if alias:
                candidates.append(cls.normalize_sport(alias))

        candidates = [c for c in candidates if c]
        for candidate in candidates:
            if target == candidate:
                return True
            if len(target) >= 3 and (target in candidate or candidate in target):
                return True
        return False

    def find_snapshot(
        self,
        *,
        sport: str,
        home_team: str,
        away_team: str,
        event_date: str,
    ) -> CatalogSnapshot | None:
        """Find the latest CatalogSnapshot matching sport, teams, and event date."""
        try:
            norm_sport = self.normalize_sport(sport)
        except ValueError:
            return None

        date_prefix = event_date[:10] if len(event_date) >= 10 else event_date
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT event_id, payload FROM catalog_events
                   WHERE sport=? AND (start_time LIKE ? OR start_time LIKE ?)
                   ORDER BY start_time, event_id""",
                (norm_sport, f"{date_prefix}%", f"%{date_prefix}%"),
            ).fetchall()

            matching_event_id: str | None = None
            for row in rows:
                try:
                    event = catalog_event_from_dict(self._decode_snapshot(row["payload"]))
                except Exception:
                    continue
                if self._match_team(event.home_team, home_team) and self._match_team(event.away_team, away_team):
                    matching_event_id = event.event_id
                    break

            if not matching_event_id:
                return None

            snap_row = connection.execute(
                """SELECT payload FROM catalog_snapshots
                   WHERE event_id=?
                   ORDER BY created_at DESC, snapshot_id DESC
                   LIMIT 1""",
                (matching_event_id,),
            ).fetchone()
            if not snap_row:
                return None

            return snapshot_from_dict(self._decode_snapshot(snap_row["payload"]))

    def list_events(self, *, sport: str | None = None, start_from: str | None = None,
                    start_to: str | None = None, limit: int = 100, offset: int = 0,
                    include_disabled: bool = False) -> list[dict]:
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
                + " ORDER BY start_time,event_id",
                params,
            ).fetchall()
        events = [self._decode_snapshot(row["payload"]) for row in rows]
        if not include_disabled:
            settings = {item["sport"]: item["enabled"] for item in self.list_sport_settings()}
            events = [event for event in events if settings.get(self.normalize_sport(event["sport"]), False)]
        return events[max(offset, 0):max(offset, 0) + min(max(limit, 1), 1000)]

    def health(self, *, operational: bool = False) -> dict:
        with self._connect() as connection:
            counts = {
                "events": connection.execute("SELECT COUNT(*) FROM catalog_events").fetchone()[0],
                "snapshots": connection.execute("SELECT COUNT(*) FROM catalog_snapshots").fetchone()[0],
                "observations": connection.execute("SELECT COUNT(*) FROM catalog_observations").fetchone()[0],
            }
            raw_archives = connection.execute("SELECT COUNT(*) FROM catalog_raw_archives").fetchone()[0]
            jobs = {row["state"]: row["count"] for row in connection.execute(
                "SELECT state, COUNT(*) AS count FROM catalog_job_runs GROUP BY state"
            ).fetchall()}
        result = {"available": True, "path": self.path, **counts}
        if operational:
            result["jobs_by_state"] = jobs
            result["raw_archives"] = raw_archives
        return result

    def save_raw_archive(self, *, provider: str, payload: object,
                         created_at: str | None = None,
                         policy: ArchivePolicy = ArchivePolicy()) -> str:
        created = created_at or utc_now()
        archive_id, encoded = prepare_archive(payload, policy=policy)
        with self._connect() as connection:
            connection.execute(
                "INSERT OR IGNORE INTO catalog_raw_archives (archive_id,provider,created_at,expires_at,payload,warning) VALUES (?,?,?,?,?,?)",
                (archive_id, provider, created, archive_expiry(created, policy), encoded,
                 "Provider source archive; may contain unverified or sensitive source material."),
            )
        return archive_id

    def get_raw_archive(self, archive_id: str) -> dict | None:
        with self._connect() as connection:
            row = connection.execute("SELECT archive_id,provider,created_at,expires_at,payload,warning FROM catalog_raw_archives WHERE archive_id=?", (archive_id,)).fetchone()
            if not row:
                return None
            connection.execute("UPDATE catalog_raw_archives SET read_count=read_count+1 WHERE archive_id=?", (archive_id,))
        result = dict(row)
        result["payload"] = json.loads(result["payload"])
        return result

    def purge_expired_archives(self, *, now: str | None = None) -> int:
        with self._connect() as connection:
            result = connection.execute("DELETE FROM catalog_raw_archives WHERE expires_at<=?", (now or utc_now(),))
        return result.rowcount

    def acquire_job(self, *, job_id: str, run_date: str, now: str,
                    lease_until: str, force: bool = False) -> bool:
        """Claim one daily run, or reclaim it after its lease expires."""
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT job_id,state,lease_until,attempt FROM catalog_job_runs WHERE run_date=? ORDER BY updated_at DESC LIMIT 1",
                (run_date,),
            ).fetchone()
            if row and row["state"] == "success" and not force:
                return False
            if row and row["state"] == "running" and (row["lease_until"] or "") > now:
                return False
            attempt = (row["attempt"] if row else 0) + 1
            if row:
                connection.execute(
                    """UPDATE catalog_job_runs SET job_id=?,state='running',updated_at=?,
                       lease_owner=?,lease_until=?,attempt=? WHERE job_id=?""",
                    (job_id, now, job_id, lease_until, attempt, row["job_id"]),
                )
            else:
                connection.execute(
                    """INSERT INTO catalog_job_runs
                       (job_id,run_date,state,started_at,updated_at,checkpoint,summary,lease_owner,lease_until,attempt)
                       VALUES (?,?, 'running',?,?,?,?,?,?,?)""",
                    (job_id, run_date, now, now, None, None, job_id, lease_until, attempt),
                )
            return True

    def update_job(self, job_id: str, *, now: str, checkpoint: str | None = None,
                   lease_until: str | None = None, state: str | None = None,
                   summary: str | None = None) -> bool:
        """Update only the claimed job; stale workers cannot mutate a new attempt."""
        assignments, values = ["updated_at=?"], [now]
        for column, value in (("checkpoint", checkpoint), ("lease_until", lease_until),
                              ("state", state), ("summary", summary)):
            if value is not None:
                assignments.append(f"{column}=?")
                values.append(value)
        values.append(job_id)
        with self._connect() as connection:
            result = connection.execute(
                "UPDATE catalog_job_runs SET " + ",".join(assignments) + " WHERE job_id=? AND state='running'",
                values,
            )
        return bool(result.rowcount)

    def get_job(self, job_id: str) -> dict | None:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM catalog_job_runs WHERE job_id=?", (job_id,)).fetchone()
        return dict(row) if row else None
