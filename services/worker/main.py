from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Any

from services.api import db, jobs
from services.api.main import _execute_pipeline_job

logger = logging.getLogger(__name__)

RESOLUTION_DELAY_HOURS = 3
RESOLUTION_CHECK_INTERVAL_CYCLES = 60


def _attempt_resolution(pick: db.PickRun) -> None:
    """Attempt LLM-based outcome resolution for a single pick."""
    from llm_post_match_stats import LLMPostMatchStatsProvider
    from outcome_resolver import OutcomeResolver

    scores: list[dict[str, Any]] = json.loads(pick.scores_json) if pick.scores_json else []
    if not scores:
        return

    picks_for_resolver = [
        {
            "rank": int(entry.get("rank", idx + 1)),
            "player": str(entry.get("player", entry.get("name", "unknown"))),
            "market": str(entry.get("market", entry.get("prop", "unknown"))),
            "line": float(entry.get("line", 0)),
            "direction": str(entry.get("direction", "over")),
        }
        for idx, entry in enumerate(scores)
    ]

    from llm.client import get_llm_client

    llm_client = get_llm_client()
    stats_provider = LLMPostMatchStatsProvider(llm_client=llm_client)

    def record_fn(pick_id: str, outcomes: list[dict[str, Any]]) -> None:
        db.record_outcomes(pick_id=pick_id, outcomes=outcomes)

    resolver = OutcomeResolver(stats_provider=stats_provider, outcome_recorder=record_fn)
    resolver.resolve(pick_id=pick.id, picks=picks_for_resolver)


def run_resolution_cycle() -> int:
    """Check for unresolved picks and attempt resolution. Returns count resolved."""
    settled_before = datetime.now(timezone.utc) - timedelta(hours=RESOLUTION_DELAY_HOURS)
    unresolved = db.list_unresolved_picks(settled_before=settled_before)
    resolved_count = 0
    for pick in unresolved:
        try:
            _attempt_resolution(pick)
            resolved_count += 1
        except Exception as exc:
            logger.warning("Resolution failed for pick %s: %s", pick.id, exc)
            with db.session_scope() as session:
                run = session.get(db.PickRun, pick.id)
                if run:
                    session.add(run)
    return resolved_count


def run_worker_loop(poll_seconds: float = 0.5) -> None:
    cycle_count = 0
    while True:
        item = jobs.dequeue_pick_run()
        if item is None:
            cycle_count += 1
            if cycle_count >= RESOLUTION_CHECK_INTERVAL_CYCLES:
                cycle_count = 0
                try:
                    run_resolution_cycle()
                except Exception as exc:
                    logger.warning("Resolution cycle error: %s", exc)
            time.sleep(poll_seconds)
            continue
        cycle_count = 0
        pick_id, request_dict, bundle_kwargs, job_id = item
        try:
            success = _execute_pipeline_job(
                pick_id=pick_id,
                request_dict=request_dict,
                bundle_kwargs=bundle_kwargs,
            )
            if success:
                jobs.mark_job_done(job_id)
            else:
                jobs.mark_job_failed(job_id, "pipeline execution failed")
        except Exception as exc:  # defensive guard
            jobs.mark_job_failed(job_id, str(exc))


if __name__ == "__main__":
    run_worker_loop()
