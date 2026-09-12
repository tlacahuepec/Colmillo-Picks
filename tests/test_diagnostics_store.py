import json
import sqlite3
import time
from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context

import pytest

from services import diagnostics as d


@pytest.fixture
def store(tmp_path, monkeypatch):
    instance = d.DiagnosticsStore(tmp_path / "diagnostics.db")
    monkeypatch.setattr(d, "_store", instance)
    assert instance.ready.wait(3)
    yield instance
    instance.close()


def until(check):
    end = time.monotonic() + 4
    while time.monotonic() < end:
        value = check()
        if value:
            return value
        time.sleep(0.02)
    raise AssertionError("Diagnostic writer did not deliver the record")


def test_connected_events_and_failure_without_exception_text(store):
    with d.operation("generate", sport="nfl", pick_id="pick-1") as op:
        try:
            with d.stage("collect"):
                raise TimeoutError("api_key=SECRET provider payload")
        except TimeoutError as exc:
            op.finish("failed", **d.error_info(exc))
    record = until(lambda: (r := store.get_operation(op.id)) and r["outcome"] == "failed" and r)
    assert record["metadata"]["error_code"] == "timeout"
    assert store.get_operation("pick-1")["operation_id"] == op.id
    events = until(lambda: len(store.events(op.id)) >= 4 and store.events(op.id))
    assert "SECRET" not in json.dumps(events)
    assert any(e["event"] == "stage.failed" and e["metadata"]["frames"] for e in events)


def test_context_isolation_and_explicit_thread_handoff(store):
    def run(index):
        with d.operation("generate", sport="nfl", home_team=f"Team {index}") as op:
            with ThreadPoolExecutor(max_workers=1) as pool:
                assert pool.submit(copy_context().run, d.current_operation_id).result() == op.id
            d.emit("provider.completed", offer_count=index)
            return op.id
    with ThreadPoolExecutor(max_workers=4) as pool:
        ids = list(pool.map(run, range(12)))
    until(lambda: all(store.get_operation(i) for i in ids))
    for index, ident in enumerate(ids):
        events = until(lambda: len(store.events(ident)) >= 3 and store.events(ident))
        assert {e["metadata"]["home_team"] for e in events} == {f"Team {index}"}
    assert d.current_operation_id() is None


def test_allowlist_rejects_raw_nested_objects_and_redacts_known_secret(monkeypatch):
    monkeypatch.setenv("TEST_API_KEY", "sensitive-marker")
    d._secrets.cache_clear()
    class Explosive:
        def __str__(self):
            raise RuntimeError("must not serialize arbitrary objects")
    result = d.safe_metadata({"prompt": "sensitive-marker", "raw_response": Explosive(),
                              "model": "sensitive-marker", "provider": Explosive(),
                              "frames": [{"file": "C:/Users/private/code.py", "locals": "sensitive-marker"}],
                              "reason_counts": {"missing_line": 3, "raw secret content": 9}})
    encoded = json.dumps(result)
    assert "sensitive-marker" not in encoded
    assert "private" not in encoded
    assert result["reason_counts"] == {"missing_line": 3}
    assert "prompt" not in result and "provider" not in result
    d._secrets.cache_clear()


def test_overflow_is_nonblocking_and_reported(tmp_path, monkeypatch):
    instance = d.DiagnosticsStore(tmp_path / "unused.db", capacity=2, start=False)
    monkeypatch.setattr(d, "_store", instance)
    with d.operation("generate"):
        for _ in range(20):
            d.emit("provider.completed", offer_count=2)
    assert instance.health()["counters"]["dropped_events"] > 0
    assert not (tmp_path / "unused.db").exists()


def test_cap_retains_terminal_event(store):
    # Direct batch writing avoids queue loss and tests the persisted per-run cap.
    with d.operation("generate") as op:
        pass
    until(lambda: (r := store.get_operation(op.id)) and r["outcome"] == "success")
    base = store.events(op.id)[0]
    batch = [{**base, "event": "provider.completed", "event_id": f"extra-{i}"} for i in range(600)]
    store._write(batch)
    assert len(store.events(op.id, limit=500)) <= 500
    assert store.get_operation(op.id)["completeness"] == "truncated"
    assert any(e["event"] == "operation.finished" for e in store.events(op.id, limit=500))


def test_expiry_removes_detail_but_preserves_summary(store):
    with d.operation("generate") as op:
        pass
    until(lambda: store.get_operation(op.id))
    with sqlite3.connect(store.path) as conn:
        conn.execute("UPDATE events SET ts='2000-01-01' WHERE operation_id=?", (op.id,))
    store.cleanup()
    assert store.events(op.id) == []
    assert store.get_operation(op.id)["completeness"] == "expired"


def test_storage_failure_does_not_escape_producer(store, monkeypatch):
    def failure(batch):
        raise sqlite3.OperationalError("disk full secret")
    monkeypatch.setattr(store, "_write", failure)
    with d.operation("generate") as op:
        op.finish("success")
    until(lambda: store.health()["counters"].get("write_failures"))
    assert store.health()["error_code"] == "storage_error"


def test_disabled_collection_keeps_terminal_summary(store, monkeypatch):
    monkeypatch.setenv("COLMILLO_DIAGNOSTICS_ENABLED", "0")
    with d.operation("generate") as op:
        d.emit("provider.completed")
        op.finish("no_picks")
    until(lambda: store.get_operation(op.id))
    assert [e["event"] for e in store.events(op.id)] == ["operation.finished"]


def test_debug_is_time_limited_and_still_metadata_only(store):
    with d.operation("generate") as op:
        until(lambda: store.get_operation(op.id))
        assert store.debug(op.id)
        d.emit("provider.detail", level="DEBUG", prompt="NEVER", offer_count=4)
    until(lambda: len(store.events(op.id)) >= 3)
    assert "NEVER" not in json.dumps(store.events(op.id))
    assert store.get_operation(op.id)["debug_until"] <= time.time() + 900


def test_later_resolution_does_not_overwrite_generation_or_hide_its_id(store):
    with d.operation("generate", operation_id="pick-canonical") as generation:
        generation.finish("partial")
    with d.operation("resolution", pick_id=generation.id, parent_operation_id=generation.id) as resolution:
        resolution.finish("success")
    until(lambda: store.get_operation(resolution.id))
    assert store.get_operation(generation.id)["outcome"] == "partial"
    assert store.get_operation(resolution.id)["parent_operation_id"] == generation.id


def test_interruption_and_storage_pruning_are_visible(store):
    with d.operation("generate") as op:
        pass
    until(lambda: store.get_operation(op.id))
    with sqlite3.connect(store.path) as conn:
        conn.execute("INSERT INTO instances VALUES ('dead-writer',?)", (time.time() - 500,))
        conn.execute("UPDATE operations SET outcome='running',instance_id='dead-writer' WHERE operation_id=?", (op.id,))
    store.cleanup()
    assert store.get_operation(op.id)["completeness"] == "interrupted"
    assert store.get_operation(op.id)["outcome"] == "running"
    store.max_bytes = 1
    store.cleanup()
    assert store.events(op.id) == []
    assert store.get_operation(op.id)["completeness"] == "pruned"
    assert store.health()["counters"]["storage_pruned"] == 1


def test_sqlite_lock_drops_bounded_batch_and_recovers(store):
    with sqlite3.connect(store.path, isolation_level=None) as blocker:
        blocker.execute("BEGIN IMMEDIATE")
        with d.operation("generate"):
            d.emit("provider.completed")
        until(lambda: store.health()["counters"].get("dropped_events"))
        assert store.health()["counters"]["dropped_events"] > 0
        blocker.execute("ROLLBACK")
    with d.operation("generate") as recovered:
        recovered.finish("success")
    until(lambda: store.get_operation(recovered.id))
    assert store.health()["available"]
