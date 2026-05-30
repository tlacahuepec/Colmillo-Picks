"""RunLedger protocol and RunContext data model."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol


@dataclass
class RunContext:
    id: str = ""
    source: str = "cli"
    match_query: str = ""
    home_team: str | None = None
    away_team: str | None = None
    match_date: str | None = None
    competition: str | None = None
    request_snapshot: dict[str, Any] = field(default_factory=dict)
    status: str = "running"
    error_summary: str | None = None
    error_stage: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration_ms: int | None = None
    partial_reasons: list[str] = field(default_factory=list)
    sport: str = ""
    league: str | None = None
    markets: tuple[str, ...] = ()
    platform: str | None = None
    provider_status: dict[str, str] = field(default_factory=dict)


@dataclass
class RunStep:
    run_id: str
    step_name: str
    status: str = "success"
    started_at: datetime | None = None
    duration_ms: int = 0


@dataclass
class SavedPick:
    run_id: str
    rank: int
    player: str
    team_id: str
    market: str
    direction: str
    line: float
    score: float
    confidence: str
    risk_notes: list[str] = field(default_factory=list)


class RunLedger(Protocol):
    def start_run(self, *, source: str, request: dict[str, Any]) -> RunContext: ...
    def complete_run(self, run_id: str) -> RunContext: ...
    def partial_run(self, run_id: str, *, reasons: list[str]) -> RunContext: ...
    def fail_run(
        self,
        run_id: str,
        *,
        error_summary: str,
        error_stage: str | None = None,
        provider_status: dict[str, Any] | None = None,  # From rich observability context (Epic #219)
    ) -> RunContext: ...
    def get_run(self, run_id: str) -> RunContext | None: ...
    def list_runs(self, *, limit: int = 20, offset: int = 0) -> list[RunContext]: ...
    def save_provider_status(self, run_id: str, status: dict[str, str]) -> RunContext: ...
    def record_step(self, run_id: str, step_name: str, *, status: str = "success", duration_ms: int = 0) -> RunStep: ...
    def get_steps(self, run_id: str) -> list[RunStep]: ...
    def save_picks(self, run_id: str, scored_picks: list[dict[str, Any]]) -> list[SavedPick]: ...
    def get_picks(self, run_id: str) -> list[SavedPick]: ...
