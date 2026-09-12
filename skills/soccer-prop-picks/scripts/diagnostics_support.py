"""Script entry-point bootstrap and adapters for shared diagnostics.

Only explicit metadata is recorded; call arguments and results are never captured.
"""

from contextlib import contextmanager
from collections import Counter
from contextvars import copy_context
from functools import wraps
from pathlib import Path
import sys
from time import perf_counter

_ROOT = str(Path(__file__).resolve().parents[3])
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from services.diagnostics import current_operation_id, emit, error_info, operation, stage  # noqa: E402


def diagnostic_stage(name, **metadata):
    def decorate(fn):
        @wraps(fn)
        def wrapped(*args, **kwargs):
            with stage(name, **metadata):
                return fn(*args, **kwargs)
        return wrapped
    return decorate


def pipeline_operation(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        if current_operation_id():
            return fn(*args, **kwargs)
        with operation("pipeline", service="cli") as handle:
            result = fn(*args, **kwargs)
            scores = result.get("scores", []) if isinstance(result, dict) else result.scores
            steps = result.get("steps", []) if isinstance(result, dict) else result.steps
            outcome = "partial" if any(s["status"] == "failed" for s in steps) else (
                "success" if scores else "no_picks"
            )
            handle.finish(outcome, pick_count=len(scores))
            return result
    return wrapped


@contextmanager
def provider_attempt(provider, *, attempt=1, **metadata):
    started = perf_counter()
    emit("provider_attempt_started", provider=provider, attempt=attempt, **metadata)
    result = {}
    try:
        yield result
    except Exception as exc:
        emit("provider_attempt_finished", level="ERROR", outcome="failed",
             duration_ms=round((perf_counter() - started) * 1000),
             provider=provider, attempt=attempt, **metadata, **error_info(exc))
        raise
    else:
        emit("provider_attempt_finished", outcome=result.pop("outcome", "success"),
             duration_ms=round((perf_counter() - started) * 1000),
             provider=provider, attempt=attempt, **metadata, **result)


def submit_with_context(executor, fn, /, *args, **kwargs):
    """Copy separately per submission: a Context cannot run concurrently."""
    return executor.submit(copy_context().run, fn, *args, **kwargs)


def retry_sleep(sleep_fn, *, provider, model):
    def wait(delay):
        emit("provider.retry_scheduled", provider=provider, model=model, retry_after_seconds=delay)
        return sleep_fn(delay)
    return wait


def summarize_inputs(inputs, *, event="collection.summary", pick_count=None):
    if not isinstance(inputs, dict):
        return
    reasons = Counter()
    categories = (("citation", "uncited_source"), ("fixture", "fixture_unverified"),
                  ("threshold", "below_threshold"), ("insufficient", "insufficient_data"),
                  ("unavailable", "provider_unavailable"), ("malformed", "invalid_offer"),
                  ("stale", "invalid_offer"))
    for excluded in (inputs.get("exclusions") or [])[:500]:
        message = excluded.get("reason", "") if isinstance(excluded, dict) else ""
        code = next((code for needle, code in categories if needle in message.lower()), "other")
        reasons[code] += 1
    emit(event, source_count=len(inputs.get("grounding_sources") or []),
         player_count=len(inputs.get("players") or []), offer_count=len(inputs.get("offers") or []),
         rejected_count=sum(reasons.values()), reason_counts=dict(reasons), pick_count=pick_count)
