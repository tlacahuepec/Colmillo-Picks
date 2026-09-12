"""Deterministic LangGraph catalog workflow tests."""

from services.catalog.contracts import CatalogEvent, CatalogSnapshot, CompletenessStatus
from services.catalog.graph import CatalogGraphDeps, run_catalog_graph
from services.catalog.importance import ImportanceConfig


def make_event(number):
    return CatalogEvent(f"nfl:event:{number}", "nfl", "nfl", f"2026-09-11T{19 + number:02d}:00:00Z")


def test_graph_runs_nodes_in_order_and_checkpoints():
    events, checkpoints, published = [make_event(1)], [], []

    def normalize(event, raw):
        return CatalogSnapshot(f"snapshot:{event.event_id}", event, "2026-09-11T12:00:00Z", "2026-09-11T12:00:00Z",
                               completeness=CompletenessStatus.COMPLETE)

    state = run_catalog_graph(CatalogGraphDeps(
        discover=lambda date: events, collect=lambda event: {"ok": True}, normalize=normalize,
        validate=lambda snapshot: [], publish=published.append,
        checkpoint=lambda name, state: checkpoints.append(name), importance_config=ImportanceConfig({}, {}),
    ), job_id="job-1", run_date="2026-09-11")
    assert state["outcome"] == "success"
    assert state["completed_nodes"] == ["discover", "prioritize", "collect", "normalize", "validate", "publish", "finish"]
    assert checkpoints == state["completed_nodes"]
    assert len(published) == 1


def test_graph_keeps_partial_results_when_one_event_fails():
    events = [make_event(1), make_event(2)]

    def collect(event):
        if event.event_id.endswith(":2"):
            raise TimeoutError
        return {"ok": True}

    def normalize(event, raw):
        return CatalogSnapshot(f"snapshot:{event.event_id}", event, "2026-09-11T12:00:00Z", "2026-09-11T12:00:00Z")

    state = run_catalog_graph(CatalogGraphDeps(
        discover=lambda date: events, collect=collect, normalize=normalize,
        validate=lambda snapshot: [], publish=lambda snapshot: None,
        importance_config=ImportanceConfig({}, {}),
    ), job_id="job-2", run_date="2026-09-11")
    assert state["outcome"] == "partial"
    assert len(state["snapshots"]) == 1
    assert state["errors"] == [{"node": "collect", "event_id": "nfl:event:2", "error_code": "TimeoutError"}]


def test_graph_does_not_publish_incomplete_snapshots():
    event = make_event(1)
    state = run_catalog_graph(CatalogGraphDeps(
        discover=lambda date: [event], collect=lambda item: {},
        normalize=lambda item, raw: CatalogSnapshot("snapshot", item, "now", "now"),
        validate=lambda snapshot: ["lineup"], publish=lambda snapshot: (_ for _ in ()).throw(AssertionError()),
        importance_config=ImportanceConfig({}, {}),
    ), job_id="job-3", run_date="2026-09-11")
    assert state["outcome"] == "failed"
    assert state["snapshots"] == []
    assert state["missing_fields"] == {"snapshot": ["lineup"]}
