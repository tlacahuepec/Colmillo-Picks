"""Deterministic LangGraph workflow for daily catalog preparation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Iterable, TypedDict

from langgraph.graph import END, START, StateGraph

from services.catalog.contracts import CatalogEvent, CatalogSnapshot
from services.catalog.importance import DEFAULT_IMPORTANCE_CONFIG, ImportanceConfig, select_important_events


class CatalogGraphState(TypedDict, total=False):
    job_id: str
    run_date: str
    events: list[CatalogEvent]
    selected_events: list[CatalogEvent]
    collected: dict[str, Any]
    snapshots: list[CatalogSnapshot]
    errors: list[dict[str, str]]
    missing_fields: dict[str, list[str]]
    completed_nodes: list[str]
    checkpoint: str
    outcome: str


@dataclass(frozen=True)
class CatalogGraphDeps:
    """Pure workflow dependencies supplied by adapters and storage wiring."""

    discover: Callable[[str], Iterable[CatalogEvent]]
    collect: Callable[[CatalogEvent], Any]
    normalize: Callable[[CatalogEvent, Any], CatalogSnapshot]
    validate: Callable[[CatalogSnapshot], list[str]]
    publish: Callable[[CatalogSnapshot], None]
    checkpoint: Callable[[str, CatalogGraphState], None] = lambda _name, _state: None
    importance_config: ImportanceConfig = DEFAULT_IMPORTANCE_CONFIG


def _mark(state: CatalogGraphState, name: str, deps: CatalogGraphDeps) -> dict:
    completed = [*state.get("completed_nodes", []), name]
    update = {"completed_nodes": completed, "checkpoint": name}
    merged = {**state, **update}
    deps.checkpoint(name, merged)
    return update


def build_catalog_graph(deps: CatalogGraphDeps):
    """Compile the daily graph; all provider behavior remains injected."""
    graph = StateGraph(CatalogGraphState)

    def discover(state: CatalogGraphState) -> dict:
        try:
            events = sorted(deps.discover(state["run_date"]), key=lambda item: item.event_id)
            update = {"events": events, "errors": list(state.get("errors", []))}
        except Exception as exc:
            update = {"events": [], "errors": [*state.get("errors", []),
                      {"node": "discover", "error_code": type(exc).__name__}]}
        update.update(_mark({**state, **update}, "discover", deps))
        return update

    def prioritize(state: CatalogGraphState) -> dict:
        selected = select_important_events(state.get("events", []), config=deps.importance_config)
        update = {"selected_events": selected}
        update.update(_mark({**state, **update}, "prioritize", deps))
        return update

    def collect(state: CatalogGraphState) -> dict:
        collected, errors = dict(state.get("collected", {})), list(state.get("errors", []))
        for event in state.get("selected_events", []):
            try:
                collected[event.event_id] = deps.collect(event)
            except Exception as exc:
                errors.append({"node": "collect", "event_id": event.event_id,
                               "error_code": type(exc).__name__})
        update = {"collected": collected, "errors": errors}
        update.update(_mark({**state, **update}, "collect", deps))
        return update

    def normalize(state: CatalogGraphState) -> dict:
        snapshots, errors = list(state.get("snapshots", [])), list(state.get("errors", []))
        selected_by_id = {event.event_id: event for event in state.get("selected_events", [])}
        for event_id, raw in state.get("collected", {}).items():
            try:
                snapshots.append(deps.normalize(selected_by_id[event_id], raw))
            except Exception as exc:
                errors.append({"node": "normalize", "event_id": event_id,
                               "error_code": type(exc).__name__})
        update = {"snapshots": snapshots, "errors": errors}
        update.update(_mark({**state, **update}, "normalize", deps))
        return update

    def validate(state: CatalogGraphState) -> dict:
        missing, errors = dict(state.get("missing_fields", {})), list(state.get("errors", []))
        valid_snapshots = []
        for snapshot in state.get("snapshots", []):
            try:
                fields = deps.validate(snapshot)
                missing[snapshot.snapshot_id] = fields
                if not fields:
                    valid_snapshots.append(snapshot)
            except Exception as exc:
                errors.append({"node": "validate", "event_id": snapshot.event.event_id,
                               "error_code": type(exc).__name__})
        update = {"snapshots": valid_snapshots, "missing_fields": missing, "errors": errors}
        update.update(_mark({**state, **update}, "validate", deps))
        return update

    def publish(state: CatalogGraphState) -> dict:
        errors = list(state.get("errors", []))
        for snapshot in state.get("snapshots", []):
            try:
                deps.publish(snapshot)
            except Exception as exc:
                errors.append({"node": "publish", "event_id": snapshot.event.event_id,
                               "error_code": type(exc).__name__})
        update = {"errors": errors}
        update.update(_mark({**state, **update}, "publish", deps))
        return update

    def finish(state: CatalogGraphState) -> dict:
        errors = state.get("errors", [])
        has_missing = any(state.get("missing_fields", {}).values())
        if errors or has_missing:
            outcome = "partial" if state.get("snapshots") else "failed"
        else:
            outcome = "success"
        update = {"outcome": outcome}
        update.update(_mark({**state, **update}, "finish", deps))
        return update

    for name, node in (("discover", discover), ("prioritize", prioritize), ("collect", collect),
                       ("normalize", normalize), ("validate", validate), ("publish", publish),
                       ("finish", finish)):
        graph.add_node(name, node)
    graph.add_edge(START, "discover")
    graph.add_edge("discover", "prioritize")
    graph.add_edge("prioritize", "collect")
    graph.add_edge("collect", "normalize")
    graph.add_edge("normalize", "validate")
    graph.add_edge("validate", "publish")
    graph.add_edge("publish", "finish")
    graph.add_edge("finish", END)
    return graph.compile()


def run_catalog_graph(deps: CatalogGraphDeps, *, job_id: str, run_date: str) -> CatalogGraphState:
    """Run one graph invocation with a fresh state and durable checkpoints."""
    initial: CatalogGraphState = {
        "job_id": job_id, "run_date": run_date, "events": [], "selected_events": [],
        "collected": {}, "snapshots": [], "errors": [], "missing_fields": {},
        "completed_nodes": [], "checkpoint": "queued",
    }
    return build_catalog_graph(deps).invoke(initial)
