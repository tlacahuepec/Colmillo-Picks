"""In-memory RunLedger implementation for tests and demos."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from run_ledger.contract import RunContext


class InMemoryRunLedger:
    def __init__(self) -> None:
        self._runs: dict[str, RunContext] = {}

    def start_run(self, *, source: str, request: dict[str, Any]) -> RunContext:
        ctx = RunContext(
            id=str(uuid.uuid4()),
            source=source,
            match_query=str(request.get("match_query", "")),
            competition=request.get("competition"),
            request_snapshot=dict(request),
            status="running",
            started_at=datetime.now(timezone.utc),
        )
        self._runs[ctx.id] = ctx
        return ctx

    def complete_run(self, run_id: str) -> RunContext:
        ctx = self._runs[run_id]
        now = datetime.now(timezone.utc)
        ctx.status = "success"
        ctx.completed_at = now
        ctx.duration_ms = max(0, round((now - ctx.started_at).total_seconds() * 1000))
        return ctx

    def fail_run(self, run_id: str, *, error_summary: str, error_stage: str | None = None) -> RunContext:
        ctx = self._runs[run_id]
        now = datetime.now(timezone.utc)
        ctx.status = "failed"
        ctx.error_summary = error_summary
        ctx.error_stage = error_stage
        ctx.completed_at = now
        ctx.duration_ms = max(0, round((now - ctx.started_at).total_seconds() * 1000))
        return ctx

    def get_run(self, run_id: str) -> RunContext | None:
        return self._runs.get(run_id)

    @property
    def runs(self) -> list[RunContext]:
        return list(self._runs.values())
