"""In-memory RunLedger implementation for tests and demos."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from run_ledger.contract import RunContext, RunStep, SavedPick


class InMemoryRunLedger:
    def __init__(self) -> None:
        self._runs: dict[str, RunContext] = {}
        self._steps: dict[str, list[RunStep]] = {}
        self._picks: dict[str, list[SavedPick]] = {}

    def start_run(self, *, source: str, request: dict[str, Any]) -> RunContext:
        markets_raw = request.get("markets", ())
        markets = tuple(markets_raw) if markets_raw else ()
        ctx = RunContext(
            id=str(uuid.uuid4()),
            source=source,
            match_query=str(request.get("match_query", "")),
            competition=request.get("competition"),
            request_snapshot=dict(request),
            status="running",
            started_at=datetime.now(timezone.utc),
            sport=request.get("sport", ""),
            league=request.get("league"),
            markets=markets,
            platform=request.get("platform"),
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

    def partial_run(self, run_id: str, *, reasons: list[str]) -> RunContext:
        ctx = self._runs[run_id]
        now = datetime.now(timezone.utc)
        ctx.status = "partial"
        ctx.partial_reasons = list(reasons)
        ctx.completed_at = now
        ctx.duration_ms = max(0, round((now - ctx.started_at).total_seconds() * 1000))
        return ctx

    def fail_run(
        self,
        run_id: str,
        *,
        error_summary: str,
        error_stage: str | None = None,
        provider_status: dict[str, Any] | None = None,
    ) -> RunContext:
        ctx = self._runs[run_id]
        now = datetime.now(timezone.utc)
        ctx.status = "failed"
        ctx.error_summary = error_summary
        ctx.error_stage = error_stage
        if provider_status:
            ctx.provider_status = dict(provider_status)
        ctx.completed_at = now
        ctx.duration_ms = max(0, round((now - ctx.started_at).total_seconds() * 1000))
        return ctx

    def get_run(self, run_id: str) -> RunContext | None:
        return self._runs.get(run_id)

    def save_provider_status(self, run_id: str, status: dict[str, str]) -> RunContext:
        ctx = self._runs[run_id]
        ctx.provider_status = dict(status)
        return ctx

    def record_step(self, run_id: str, step_name: str, *, status: str = "success", duration_ms: int = 0) -> RunStep:
        step = RunStep(
            run_id=run_id,
            step_name=step_name,
            status=status,
            started_at=datetime.now(timezone.utc),
            duration_ms=duration_ms,
        )
        self._steps.setdefault(run_id, []).append(step)
        return step

    def get_steps(self, run_id: str) -> list[RunStep]:
        return list(self._steps.get(run_id, []))

    def save_picks(self, run_id: str, scored_picks: list[dict[str, Any]]) -> list[SavedPick]:
        saved: list[SavedPick] = []
        for rank, pick in enumerate(scored_picks, start=1):
            risk_flags = pick.get("explainability", {}).get("risk_flags", [])
            sp = SavedPick(
                run_id=run_id,
                rank=rank,
                player=pick.get("player", ""),
                team_id=pick.get("team_id", ""),
                market=pick.get("market", ""),
                direction=pick.get("direction", ""),
                line=float(pick.get("line", 0)),
                score=float(pick.get("score", 0)),
                confidence=pick.get("confidence", ""),
                risk_notes=list(risk_flags),
            )
            saved.append(sp)
        self._picks.setdefault(run_id, []).extend(saved)
        return saved

    def get_picks(self, run_id: str) -> list[SavedPick]:
        return list(self._picks.get(run_id, []))

    def list_runs(self, *, limit: int = 20, offset: int = 0) -> list[RunContext]:
        all_runs = sorted(self._runs.values(), key=lambda r: r.started_at or datetime.min, reverse=True)
        page = all_runs[offset:offset + limit]
        return [
            RunContext(
                id=r.id,
                source=r.source,
                match_query=r.match_query,
                home_team=r.home_team,
                away_team=r.away_team,
                match_date=r.match_date,
                competition=r.competition,
                request_snapshot={},
                status=r.status,
                error_summary=r.error_summary,
                error_stage=r.error_stage,
                started_at=r.started_at,
                completed_at=r.completed_at,
                duration_ms=r.duration_ms,
                partial_reasons=list(r.partial_reasons),
                sport=r.sport,
                league=r.league,
                markets=r.markets,
                platform=r.platform,
                provider_status=dict(r.provider_status),
            )
            for r in page
        ]

    @property
    def runs(self) -> list[RunContext]:
        return list(self._runs.values())
