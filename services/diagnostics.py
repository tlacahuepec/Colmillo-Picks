"""Bounded, metadata-only diagnostics shared by API, workers, and CLI.

Business records remain authoritative. Event delivery is best effort and never
performs disk or network I/O on the producer thread.
"""
from __future__ import annotations

import atexit
import contextvars
import functools
import json
import math
import os
import queue
import re
import sqlite3
import sys
import threading
import time
import uuid
from collections import Counter
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from itertools import islice
from pathlib import Path
from typing import Protocol

SCHEMA_VERSION = 1
MAX_EVENT_BYTES = 8192
MAX_OPERATION_EVENTS = 500
_context = contextvars.ContextVar("diagnostics_operation", default=None)
_span = contextvars.ContextVar("diagnostics_span", default=None)
_parent_span = contextvars.ContextVar("diagnostics_parent_span", default=None)
_request = contextvars.ContextVar("diagnostics_request", default=None)
_SAFE_KEYS = frozenset("""sport home_team away_team event_date match_date provider model
    request_id pick_id slate_id run_id job_id attempt attempt_id parent_operation_id
    exception_type cause_types error_code http_status status_code retryable retry_count
    timeout_ms timeout_seconds retry_after_seconds prompt_tokens completion_tokens total_tokens
    cached cache_hit fallback_used source_count player_count offer_count pick_count rejected_count
    accepted_count missing_count reason_counts frames function file line configured search_enabled
    method route service origin stage duration_ms outcome started_at detail_enabled interrupted
    suppressed_count dropped_count queue_ms version commit count failed_count partial_count
    process_id instance_id kind phase component action""".split())
_TOKEN = re.compile(r"^[A-Za-z0-9_.:/ -]{1,128}$")
_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_CODE = re.compile(r"^[a-zA-Z0-9_.-]{1,80}$")
MESSAGES = {
    "timeout": "The data provider did not respond within the time limit.",
    "rate_limited": "The provider temporarily limited requests.",
    "provider_server_error": "The provider could not complete the request.",
    "configuration_error": "The provider configuration is missing or invalid.",
    "invalid_output": "The provider returned data the application could not validate.",
    "missing_citations": "The provider returned no verifiable source citations.",
    "fixture_not_found": "The requested matchup could not be verified for this date.",
    "connection_error": "The application could not connect to the service.",
    "storage_error": "The application could not save the result.",
    "collection_error": "Data collection failed; no picks were generated.",
    "unexpected_error": "The operation failed. Technical diagnostics may identify the cause.",
    "no_picks": "Analysis completed, but no verified picks qualified.",
    "partial": "Some results are available; part of the operation could not complete.",
    "success": "The operation completed successfully.",
}


def utcnow():
    return datetime.now(timezone.utc).isoformat()


def valid_id(value):
    return isinstance(value, str) and bool(_ID.fullmatch(value))


@functools.lru_cache(maxsize=1)
def _secrets():
    return tuple(v for k, v in os.environ.items()
                 if any(s in k.upper() for s in ("KEY", "SECRET", "TOKEN", "PASSWORD", "DSN")) and len(v) >= 4)


def safe_text(value, limit=128):
    """Only for bounded metadata, never a substitute for a field allowlist."""
    if not isinstance(value, str):
        return ""
    value = value[:1024]
    for secret in _secrets():
        value = value.replace(secret, "[redacted]")
    value = re.sub(r"https?://\S+", "[url omitted]", value)
    value = re.sub(r"(?i)(bearer\s+\S+|(?:api[_-]?key|token|password|secret)\s*[=:]\s*\S+)", "[redacted]", value)
    value = re.sub(r"(?:[A-Za-z]:[\\/]|/)(?:[^\s/\\]+[/\\])+[^\s]*", "[path omitted]", value)
    return "".join(c for c in value if c.isprintable())[:limit]


def safe_metadata(values, *, include_frames=True):
    output = {}
    if not isinstance(values, dict):
        return output
    for key, value in islice(values.items(), 64):
        if key not in _SAFE_KEYS or (key == "frames" and not include_frames):
            continue
        if key == "reason_counts" and isinstance(value, dict):
            output[key] = {k: min(v, 1000000) for k, v in list(value.items())[:20]
                           if isinstance(k, str) and _CODE.fullmatch(k) and type(v) is int and v >= 0}
        elif key == "frames" and isinstance(value, list):
            output[key] = [safe_metadata(f) for f in value[:12] if isinstance(f, dict)]
        elif key == "cause_types" and isinstance(value, list):
            output[key] = [safe_text(v, 80) for v in value[:8] if isinstance(v, str) and _CODE.fullmatch(v)]
        elif type(value) in (int, float) and math.isfinite(value):
            output[key] = value
        elif isinstance(value, bool) or value is None:
            output[key] = value
        elif isinstance(value, str):
            output[key] = safe_text(value)
    return output


def error_info(exc):
    """Classify without ever storing str(exc), traceback source or locals."""
    types, seen, node, status, deepest = [], set(), exc, None, exc
    messages = []
    while node is not None and id(node) not in seen and len(types) < 8:
        seen.add(id(node))
        deepest = node
        types.append(type(node).__name__)
        try:
            messages.append(str(node)[:2000].lower())
        except Exception:
            pass
        candidate = getattr(node, "status_code", None) or getattr(node, "code", None) or getattr(getattr(node, "response", None), "status_code", None)
        if type(candidate) is int:
            status = candidate
        node = node.__cause__ or node.__context__
    names = " ".join(types).lower()
    # Inspect text for classification only; never retain it.
    message = " ".join(messages)
    code = "unexpected_error"
    if "timeout" in names or "timed out" in message:
        code = "timeout"
    elif status == 429 or "ratelimit" in names:
        code = "rate_limited"
    elif status and status >= 500 or "servererror" in names:
        code = "provider_server_error"
    elif "connect" in names:
        code = "connection_error"
    elif "sqlite" in names or "operationalerror" in names or "disk full" in message:
        code = "storage_error"
    elif "validation" in names or "json" in names:
        code = "invalid_output"
    elif "source citations" in message:
        code = "missing_citations"
    elif "no fixture matched" in message or "fixture not found" in message:
        code = "fixture_not_found"
    elif "api_key" in message or "configuration" in message or "search-enabled" in message:
        code = "configuration_error"
    elif "dataqualityerror" in names:
        code = "collection_error"
    frames, tb = [], deepest.__traceback__
    while tb is not None:
        frames.append({"file": Path(tb.tb_frame.f_code.co_filename).name,
                       "function": tb.tb_frame.f_code.co_name, "line": tb.tb_lineno})
        tb = tb.tb_next
    return safe_metadata({"error_code": code, "exception_type": type(exc).__name__,
                          "cause_types": types, "http_status": status,
                          "retryable": code in {"timeout", "rate_limited", "connection_error", "provider_server_error"},
                          "frames": frames[-12:]})


def public_trace(value):
    """Remove raw research material from old/new trace display and exports.

    Pick/report evidence is separate. Keep structured scoring detail compatible.
    """
    blocked = {"research_evidence", "raw_response", "raw_request", "prompt", "system_prompt",
               "user_prompt", "html", "authorization", "api_key", "headers", "cookies", "frames"}
    if isinstance(value, dict):
        return {k: public_trace(v) for k, v in list(value.items())[:500]
                if isinstance(k, str) and k.lower() not in blocked and not any(s in k.lower() for s in ("password", "secret"))
                and ("token" not in k.lower() or k in {"prompt_tokens", "completion_tokens", "total_tokens"})}
    if isinstance(value, list):
        return [public_trace(v) for v in value[:500]]
    if isinstance(value, str):
        return safe_text(value, 1024)
    return value if value is None or type(value) in (int, float, bool) else None


class DiagnosticsStorage(Protocol):
    def submit(self, event: dict) -> bool: ...
    def list_operations(self, limit=20, offset=0, **filters) -> list[dict]: ...
    def get_operation(self, ident: str) -> dict | None: ...
    def events(self, ident: str, limit=100, offset=0) -> list[dict]: ...
    def health(self) -> dict: ...
    def resolve(self, ident: str) -> str: ...
    def debug(self, ident: str, seconds=900) -> bool: ...


class DiagnosticsStore:
    def __init__(self, path, *, capacity=2000, max_bytes=128 * 1024 * 1024, start=True):
        self.path = str(path)
        self.max_bytes = max_bytes
        reserve = max(1, capacity // 10)
        self.queue = queue.Queue(maxsize=max(1, capacity - reserve))
        self.priority = queue.Queue(maxsize=reserve)
        self.counters = Counter()
        self.lock = threading.Lock()
        self.ready = threading.Event()
        self.stop = threading.Event()
        self.last_error = None
        self.available = False
        self.instance = uuid.uuid4().hex
        self.thread = threading.Thread(target=self._listen, name="diagnostics-writer", daemon=True)
        if start:
            self.thread.start()

    def count(self, key, amount=1):
        with self.lock:
            self.counters[key] += amount

    def _counter_snapshot(self):
        with self.lock:
            return dict(self.counters)

    def submit(self, event):
        critical = event["level"] in {"ERROR", "WARNING"} or event["event"] in {"operation.finished", "operation.started", "operation.accepted"}
        target = self.priority if critical else self.queue
        try:
            target.put_nowait(event)
            return True
        except queue.Full:
            self.count("dropped_events")
            return False

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(self.path, timeout=0.05)
        conn.row_factory = sqlite3.Row
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def _initialize(self):
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute("PRAGMA auto_vacuum=INCREMENTAL")
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA journal_size_limit=4194304")
            conn.execute("PRAGMA wal_autocheckpoint=256")
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS operations (
                    operation_id TEXT PRIMARY KEY, started_at TEXT, updated_at TEXT,
                    service TEXT, sport TEXT, home_team TEXT, away_team TEXT,
                    outcome TEXT, duration_ms REAL, summary TEXT, completeness TEXT,
                    metadata TEXT, event_count INTEGER DEFAULT 0, debug_until REAL DEFAULT 0,
                    instance_id TEXT, heartbeat REAL, parent_operation_id TEXT);
                CREATE INDEX IF NOT EXISTS diag_started ON operations(started_at);
                CREATE INDEX IF NOT EXISTS diag_outcome ON operations(outcome, started_at);
                CREATE INDEX IF NOT EXISTS diag_sport ON operations(sport, started_at);
                CREATE INDEX IF NOT EXISTS diag_service ON operations(service, started_at);
                CREATE TABLE IF NOT EXISTS events (
                    event_id TEXT PRIMARY KEY, operation_id TEXT, ts TEXT, level TEXT,
                    payload TEXT, size INTEGER);
                CREATE INDEX IF NOT EXISTS diag_events ON events(operation_id, ts);
                CREATE INDEX IF NOT EXISTS diag_expiry ON events(ts);
                CREATE INDEX IF NOT EXISTS diag_level ON events(level, ts);
                CREATE TABLE IF NOT EXISTS links (ident TEXT PRIMARY KEY, operation_id TEXT);
                CREATE INDEX IF NOT EXISTS diag_links ON links(operation_id);
                CREATE TABLE IF NOT EXISTS instances (id TEXT PRIMARY KEY, heartbeat REAL);
                CREATE TABLE IF NOT EXISTS diagnostic_health (instance_id TEXT PRIMARY KEY, heartbeat REAL, payload TEXT);
            """)
        self.available = True

    def _listen(self):
        maintenance = 0
        while not self.stop.is_set() or not (self.queue.empty() and self.priority.empty()):
            try:
                if not self.available:
                    self._initialize()
                    self.ready.set()
                batch = []
                for target in (self.priority, self.queue):
                    while len(batch) < 100:
                        try:
                            batch.append(target.get_nowait())
                        except queue.Empty:
                            break
                if batch:
                    if os.getenv("COLMILLO_DIAGNOSTICS_CONSOLE", "0" if "pytest" in sys.modules else "1") == "1":
                        for event in batch:
                            if event["event"] == "operation.finished" or event["level"] in {"ERROR", "WARNING"}:
                                safe = {**event, "metadata": safe_metadata(event["metadata"], include_frames=False)}
                                try:
                                    output = sys.stderr if event["service"] == "cli" else sys.stdout
                                    output.write(json.dumps(safe, separators=(",", ":")) + "\n")
                                except (OSError, ValueError):
                                    self.count("console_failures")
                    self._write(batch)
                if time.monotonic() - maintenance > 60:
                    self.cleanup()
                    maintenance = time.monotonic()
                if not batch:
                    self.stop.wait(0.1)
            except (OSError, sqlite3.Error, ValueError):
                self.count("write_failures")
                self.last_error = "storage_error"
                self.ready.set()
                self.stop.wait(1)
                if self.stop.is_set():
                    break
        if self.available:
            try:
                with self._connect() as conn:
                    conn.execute("INSERT OR REPLACE INTO diagnostic_health VALUES (?,?,?)",
                                 (self.instance, time.time(), json.dumps(self._counter_snapshot())))
            except (OSError, sqlite3.Error):
                pass
        self.available = False

    def _write(self, batch):
        # Two short attempts; the producer never waits for this lock.
        for attempt in range(2):
            try:
                with self._connect() as conn:
                    used = (conn.execute("PRAGMA page_count").fetchone()[0] - conn.execute("PRAGMA freelist_count").fetchone()[0]) * conn.execute("PRAGMA page_size").fetchone()[0]
                    if used > self.max_bytes:
                        self.count("storage_budget_reached")
                        self.count("dropped_events", len(batch))
                        self.last_error = "storage_budget_reached"
                        return
                    for event in sorted(batch, key=lambda e: e["ts"]):
                        self._insert(conn, event)
                self.last_error = None
                return
            except (OSError, sqlite3.Error):
                if attempt:
                    self.count("dropped_events", len(batch))
                    raise
                time.sleep(0.025)

    def _insert(self, conn, event):
        ident, meta, outcome = event["operation_id"], event["metadata"], event.get("outcome")
        conn.execute("""INSERT OR IGNORE INTO operations
            (operation_id, started_at, updated_at, service, sport, home_team, away_team,
             outcome, summary, completeness, metadata, instance_id, heartbeat, parent_operation_id)
            VALUES (?,?,?,?,?,?,?,'running','Operation is running.','complete',?,?,?,?)""",
            (ident, event["ts"], event["ts"], event["service"], meta.get("sport"), meta.get("home_team"),
             meta.get("away_team"), "{}", self.instance, time.time(), meta.get("parent_operation_id")))
        row = conn.execute("SELECT * FROM operations WHERE operation_id=?", (ident,)).fetchone()
        if event["level"] == "DEBUG" and row["debug_until"] < time.time():
            return
        merged = {**json.loads(row["metadata"]), **{k: v for k, v in meta.items() if k != "frames"}}
        for key in ("pick_id", "slate_id", "request_id", "run_id", "job_id"):
            if valid_id(meta.get(key)):
                conn.execute("INSERT OR REPLACE INTO links VALUES (?,?)", (meta[key], ident))
        # Late stage events must not reset a completed operation's status.
        terminal = event["event"] == "operation.finished"
        newest = event["ts"] >= row["updated_at"]
        op_outcome = outcome if terminal and newest else row["outcome"]
        if event["event"] == "operation.accepted" and row["outcome"] == "running":
            op_outcome = "queued"
        elif event["event"] == "operation.started" and row["outcome"] == "queued":
            op_outcome = "running"
        summary = row["summary"]
        if terminal and newest:
            summary = MESSAGES.get(meta.get("error_code"), MESSAGES.get(outcome, MESSAGES["unexpected_error"]))
        completeness = row["completeness"]
        if terminal and row["event_count"] >= MAX_OPERATION_EVENTS:
            # A retried operation can finish more than once. Retain the latest
            # terminal record without growing beyond the operation budget.
            conn.execute("DELETE FROM events WHERE event_id IN (SELECT event_id FROM events WHERE operation_id=? ORDER BY ts,event_id LIMIT 1)", (ident,))
            conn.execute("UPDATE operations SET event_count=event_count-1 WHERE operation_id=?", (ident,))
            completeness = "truncated"
        if row["event_count"] >= MAX_OPERATION_EVENTS - 1 and not terminal:
            completeness = "truncated"
        else:
            encoded = json.dumps(event, separators=(",", ":"))
            if len(encoded.encode()) <= MAX_EVENT_BYTES:
                inserted = conn.execute("INSERT OR IGNORE INTO events VALUES (?,?,?,?,?,?)",
                                        (event["event_id"], ident, event["ts"], event["level"], encoded, len(encoded.encode()))).rowcount
                if inserted:
                    conn.execute("UPDATE operations SET event_count=event_count+1 WHERE operation_id=?", (ident,))
        conn.execute("""UPDATE operations SET updated_at=?, outcome=?, summary=?, completeness=?, metadata=?,
            duration_ms=?, heartbeat=?, instance_id=?, sport=COALESCE(?,sport),home_team=COALESCE(?,home_team),
            away_team=COALESCE(?,away_team),started_at=MIN(started_at,?) WHERE operation_id=?""",
            (max(event["ts"], row["updated_at"]), op_outcome, summary, completeness, json.dumps(merged),
             event.get("duration_ms") if terminal and newest else row["duration_ms"], time.time(), self.instance,
             meta.get("sport"), meta.get("home_team"), meta.get("away_team"), event["ts"], ident))

    def _read(self, sql, params=()):
        if not self.available:
            return []
        try:
            with self._connect() as conn:
                return [dict(r) for r in conn.execute(sql, params).fetchall()]
        except (OSError, sqlite3.Error):
            self.last_error = "storage_error"
            return []

    def resolve(self, ident):
        # A later resolution/check may refer to a pick too. Its alias must never
        # hide the canonical generation operation with that same identifier.
        rows = self._read("SELECT operation_id FROM operations WHERE operation_id=? UNION ALL SELECT operation_id FROM links WHERE ident=? LIMIT 1", (ident, ident))
        return rows[0]["operation_id"] if rows else ident

    def list_operations(self, limit=20, offset=0, **filters):
        conditions, params = [], []
        for key in ("sport", "outcome", "service", "operation_id"):
            if filters.get(key):
                conditions.append(key + "=?")
                params.append(self.resolve(filters[key]) if key == "operation_id" else filters[key])
        if filters.get("since"):
            conditions.append("started_at>=?")
            params.append(filters["since"])
        where = " WHERE " + " AND ".join(conditions) if conditions else ""
        rows = self._read("SELECT * FROM operations" + where + " ORDER BY started_at DESC LIMIT ? OFFSET ?",
                          (*params, min(max(limit, 1), 100), max(offset, 0)))
        return [self._view(r) for r in rows]

    def _view(self, row):
        row = dict(row)
        row["metadata"] = json.loads(row["metadata"])
        row.pop("instance_id", None)
        row.pop("heartbeat", None)
        if self.counters["dropped_events"] and row["completeness"] == "complete":
            row["completeness"] = "possibly_incomplete"
        if row["outcome"] == "running" and (datetime.now(timezone.utc) - datetime.fromisoformat(row["updated_at"])).total_seconds() > 180:
            row["summary"] = "No recent events. Work may still be running; completion is unconfirmed."
        return row

    def get_operation(self, ident):
        rows = self._read("SELECT * FROM operations WHERE operation_id=?", (self.resolve(ident),))
        return self._view(rows[0]) if rows else None

    def events(self, ident, limit=100, offset=0):
        rows = self._read("SELECT payload FROM events WHERE operation_id=? ORDER BY ts,event_id LIMIT ? OFFSET ?",
                          (self.resolve(ident), min(max(limit, 1), 500), max(offset, 0)))
        return [json.loads(row["payload"]) for row in rows]

    def health(self):
        counters = Counter()
        for row in self._read("SELECT instance_id,payload FROM diagnostic_health"):
            if row["instance_id"] != self.instance:
                counters.update(json.loads(row["payload"]))
        counters.update(self._counter_snapshot())
        return {"available": self.available and self.last_error is None, "error_code": self.last_error,
                "queue_depth": self.queue.qsize() + self.priority.qsize(),
                "counters": dict(counters), "details_days": 30, "summaries_days": 90,
                "storage_budget_bytes": self.max_bytes,
                "collection_enabled": os.getenv("COLMILLO_DIAGNOSTICS_ENABLED", "1") != "0"}

    def debug(self, ident, seconds=900):
        ident = self.resolve(ident)
        try:
            with self._connect() as conn:
                return bool(conn.execute("UPDATE operations SET debug_until=? WHERE operation_id=?",
                                         (time.time() + min(max(seconds, 0), 900), ident)).rowcount)
        except (OSError, sqlite3.Error):
            return False

    def cleanup(self):
        with self._connect() as conn:
            now = datetime.now(timezone.utc)
            conn.execute("INSERT OR REPLACE INTO instances VALUES (?,?)", (self.instance, time.time()))
            conn.execute("INSERT OR REPLACE INTO diagnostic_health VALUES (?,?,?)", (self.instance, time.time(), json.dumps(self._counter_snapshot())))
            conn.execute("DELETE FROM diagnostic_health WHERE heartbeat<?", (time.time() - 90 * 86400,))
            conn.execute("DELETE FROM instances WHERE heartbeat<?", (time.time() - 90 * 86400,))
            # A dead writer's lease is evidence of interruption, not a failed job.
            conn.execute("""UPDATE operations SET completeness='interrupted',
                summary='The recording process stopped; job completion is unconfirmed.'
                WHERE outcome='running' AND instance_id IN (SELECT id FROM instances WHERE heartbeat<?)""",
                         (time.time() - 180,))
            expired = conn.execute("SELECT event_id,operation_id FROM events WHERE ts<? LIMIT 1000",
                                   ((now - timedelta(days=30)).isoformat(),)).fetchall()
            for row in expired:
                conn.execute("DELETE FROM events WHERE event_id=?", (row["event_id"],))
                conn.execute("UPDATE operations SET completeness='expired' WHERE operation_id=?", (row["operation_id"],))
            old = conn.execute("SELECT operation_id FROM operations WHERE started_at<? LIMIT 1000",
                               ((now - timedelta(days=90)).isoformat(),)).fetchall()
            for row in old:
                for table in ("events", "links", "operations"):
                    conn.execute(f"DELETE FROM {table} WHERE operation_id=?", (row[0],))
            pages = conn.execute("PRAGMA page_count").fetchone()[0]
            free = conn.execute("PRAGMA freelist_count").fetchone()[0]
            page_size = conn.execute("PRAGMA page_size").fetchone()[0]
            if (pages - free) * page_size > self.max_bytes:
                rows = conn.execute("SELECT event_id,operation_id FROM events ORDER BY ts LIMIT 1000").fetchall()
                for row in rows:
                    conn.execute("DELETE FROM events WHERE event_id=?", (row[0],))
                    conn.execute("UPDATE operations SET completeness='pruned' WHERE operation_id=?", (row[1],))
                if not rows:
                    for row in conn.execute("SELECT operation_id FROM operations ORDER BY started_at LIMIT 100").fetchall():
                        conn.execute("DELETE FROM links WHERE operation_id=?", (row[0],))
                        conn.execute("DELETE FROM operations WHERE operation_id=?", (row[0],))
                self.count("storage_pruned")
            conn.execute("PRAGMA incremental_vacuum(256)")
        with self._connect() as conn:
            conn.execute("PRAGMA wal_checkpoint(PASSIVE)")

    def flush(self, timeout=3):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.queue.empty() and self.priority.empty():
                # Writer may have dequeued a batch; callers should poll their desired record.
                return
            time.sleep(0.01)

    def close(self):
        self.stop.set()
        if self.thread.is_alive():
            self.thread.join(timeout=2)


_store = None
_store_lock = threading.Lock()


def get_store():
    global _store
    if _store is None:
        with _store_lock:
            if _store is None:
                path = os.getenv("COLMILLO_DIAGNOSTICS_DB_PATH")
                if not path:
                    path = str(Path(os.getenv("COLMILLO_DB_PATH", "data/colmillo.db")).resolve().parent / "diagnostics.db")
                _store = DiagnosticsStore(path)
                atexit.register(_store.close)
    return _store


def current_operation_id():
    op = _context.get()
    return op.id if op else None


def current_request_id():
    return _request.get()


def finish_operation(outcome, **metadata):
    op = _context.get()
    if op:
        op.finish(outcome, **metadata)


@contextmanager
def request_context(request_id):
    token = _request.set(request_id if valid_id(request_id) else uuid.uuid4().hex)
    try:
        yield _request.get()
    finally:
        _request.reset(token)


def emit(event, *, stage=None, level="INFO", outcome=None, duration_ms=None, **metadata):
    try:
        op = _context.get()
        ident = metadata.pop("operation_id", None) or (op.id if op else None)
        if not ident or not valid_id(ident):
            return False
        if os.getenv("COLMILLO_DIAGNOSTICS_ENABLED", "1") == "0" and event != "operation.finished":
            return False
        if not isinstance(event, str) or not _CODE.fullmatch(event):
            return False
        meta = safe_metadata({**(op.metadata if op else {}), **({"request_id": _request.get()} if _request.get() else {}), **metadata})
        if op and meta.get("frames"):
            fingerprint = json.dumps(meta["frames"], sort_keys=True)
            with op.lock:
                if fingerprint in op.error_frames or len(op.error_frames) >= 16:
                    meta.pop("frames", None)
                else:
                    op.error_frames.add(fingerprint)
        record = {"schema_version": SCHEMA_VERSION, "event_id": uuid.uuid4().hex, "ts": utcnow(),
                  "event": event, "operation_id": ident, "span_id": _span.get(), "parent_span": _parent_span.get(),
                  "service": op.service if op else meta.get("service", "api"),
                  "stage": safe_text(stage or "", 64), "level": level if level in {"DEBUG", "INFO", "WARNING", "ERROR"} else "INFO",
                  "outcome": outcome if outcome in {"running", "queued", "success", "partial", "no_picks", "failed"} else None,
                  "duration_ms": duration_ms if type(duration_ms) in (int, float) and math.isfinite(duration_ms) else None,
                  "metadata": meta}
        if len(json.dumps(record).encode()) > MAX_EVENT_BYTES:
            record["metadata"] = {"error_code": "metadata_truncated"}
            get_store().count("truncated_events")
        return get_store().submit(record)
    except Exception:
        return False


class Operation:
    def __init__(self, kind, operation_id=None, service="api", **metadata):
        self.id = operation_id if valid_id(operation_id) else str(uuid.uuid4())
        self.service = service
        parent = current_operation_id()
        self.metadata = safe_metadata({"kind": kind, "parent_operation_id": parent,
                                       "version": os.getenv("COLMILLO_VERSION") or "0.0.0-dev",
                                       "commit": os.getenv("COLMILLO_COMMIT") or "unknown", **metadata})
        self.started = time.perf_counter()
        self.finished = False
        self.outcome = None
        self.error_frames = set()
        self.lock = threading.Lock()

    def finish(self, outcome, **metadata):
        if self.finished:
            return
        self.finished = True
        self.outcome = outcome
        self.metadata.update(safe_metadata(metadata))
        emit("operation.finished", level="ERROR" if outcome == "failed" else "INFO", outcome=outcome,
             duration_ms=round((time.perf_counter() - self.started) * 1000, 3), **metadata)


@contextmanager
def operation(kind, *, operation_id=None, service="api", **metadata):
    op = Operation(kind, operation_id, service, **metadata)
    token = _context.set(op)
    emit("operation.started", outcome="running")
    try:
        yield op
    except BaseException as exc:
        op.finish("failed", **error_info(exc))
        raise
    finally:
        if not op.finished:
            op.finish("success")
        _context.reset(token)


@contextmanager
def stage(name, **metadata):
    started = time.perf_counter()
    parent_token = _parent_span.set(_span.get())
    token = _span.set(uuid.uuid4().hex)
    emit("stage.started", stage=name, started_at=utcnow(), **metadata)
    try:
        yield
    except BaseException as exc:
        emit("stage.failed", stage=name, level="ERROR", outcome="failed",
             duration_ms=round((time.perf_counter() - started) * 1000, 3), **metadata, **error_info(exc))
        raise
    else:
        emit("stage.completed", stage=name, outcome="success",
             duration_ms=round((time.perf_counter() - started) * 1000, 3), **metadata)
    finally:
        _span.reset(token)
        _parent_span.reset(parent_token)


def instrument(kind, service="api"):
    """Wrap auxiliary workflows; a caller can supply parent context implicitly."""
    def decorate(fn):
        @functools.wraps(fn)
        def wrapped(*args, **kwargs):
            with operation(kind, service=service):
                return fn(*args, **kwargs)
        return wrapped
    return decorate
