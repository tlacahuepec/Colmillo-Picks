from concurrent.futures import ThreadPoolExecutor
from contextvars import ContextVar
import json
from pathlib import Path
import subprocess
import sys
from threading import Barrier
from types import SimpleNamespace

import pytest

from diagnostics_support import current_operation_id, operation, submit_with_context
from llm.openai_client import OpenAILLMClient
from nfl_collection import _source_urls
from nfl_module import NflDataQualityError, NflModule
from pick_request import PickRequest
from pipeline_runner import PipelineRunError, PipelineRunner
from run_ledger import InMemoryRunLedger, SqliteRunLedger
from services import diagnostics


@pytest.fixture(autouse=True)
def events(monkeypatch):
    records = []
    monkeypatch.setattr(diagnostics, "get_store", lambda: SimpleNamespace(submit=lambda e: records.append(e)))
    return records


def request():
    return PickRequest(sport="nfl", home_team="KC", away_team="BUF", event_date="2026-09-10", markets=())


def test_masked_nfl_exception_remains_failure_with_safe_cause_chain(events):
    secret = "Bearer secret-token https://provider.invalid/?api_key=private"

    def collect(**kwargs):
        try:
            raise TimeoutError(secret)
        except TimeoutError as exc:
            raise RuntimeError(secret) from exc

    with pytest.raises(PipelineRunError) as caught:
        PipelineRunner().run(request=request(), module=NflModule(collector=collect))
    outer = caught.value
    assert outer.stage == "collect"
    assert isinstance(outer.__cause__, NflDataQualityError)
    assert isinstance(outer.__cause__.__cause__, RuntimeError)
    assert isinstance(outer.__cause__.__cause__.__cause__, TimeoutError)
    reason = outer.error_details["reason"]
    assert reason["error_code"] == "timeout"
    assert reason["cause_types"] == ["RuntimeError", "TimeoutError"]
    assert reason["frames"]
    assert secret not in json.dumps(reason)
    assert secret not in str(outer)
    assert secret not in json.dumps(events)
    assert events[-1]["outcome"] == "failed"


def test_normal_no_fixture_is_no_picks(events):
    module = NflModule(collector=lambda **kw: {"game": None, "players": [], "offers": []})
    result = PipelineRunner().run(request=request(), module=module)
    assert result.scores == []
    assert events[-1]["outcome"] == "no_picks"
    assert not any(e["outcome"] == "failed" for e in events)


def test_offer_failure_retains_cause_and_safe_provider_details():
    cause = TimeoutError("raw provider response")

    class Collector:
        last_provider_error = cause

        def __call__(self, **kwargs):
            return {"game": {}, "offers": [], "provider_errors": {
                "game_offers": diagnostics.error_info(cause),
            }}

    with pytest.raises(NflDataQualityError) as caught:
        NflModule(collector=Collector()).collect_inputs(home_team="KC", away_team="BUF", match_date="2026-09-10")
    assert caught.value.__cause__ is cause
    assert caught.value.reason["provider_errors"]["game_offers"]["error_code"] == "timeout"
    assert "raw provider response" not in json.dumps(caught.value.reason)


def test_context_is_copied_per_submission_and_does_not_leak():
    local = ContextVar("test_local", default="clean")
    barrier = Barrier(4)

    def task(index):
        barrier.wait(timeout=5)
        before = local.get()
        local.set(index)
        return current_operation_id(), before

    with ThreadPoolExecutor(max_workers=4) as pool:
        with operation("test", operation_id="parallel-operation"):
            local.set("parent")
            futures = [submit_with_context(pool, task, i) for i in range(4)]
            assert [f.result(timeout=10) for f in futures] == [("parallel-operation", "parent")] * 4
            assert local.get() == "parent"
        assert pool.submit(current_operation_id).result() is None
        assert pool.submit(local.get).result() == "clean"
    assert current_operation_id() is None


def test_nfl_citation_pool_preserves_concurrent_operation_ids(monkeypatch):
    barrier = Barrier(2)
    seen = []

    def resolve(url):
        seen.append((url, current_operation_id()))
        return url

    monkeypatch.setattr("nfl_collection._resolve_citation_url", resolve)

    def collect(ident):
        with operation("test", operation_id=ident):
            barrier.wait(timeout=5)
            urls = [f"https://example.com/{ident}/{i}" for i in range(8)]
            assert _source_urls(SimpleNamespace(last_sources=[SimpleNamespace(url=u) for u in urls])) == set(urls)

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(collect, ident) for ident in ("first", "second")]
        for future in futures:
            future.result(timeout=10)
    assert len(seen) == 16
    assert all(f"/{ident}/" in url for url, ident in seen)


def test_openai_attempts_keep_retry_policy_without_recording_prompts(events):
    calls, sleeps = [], []

    def parse(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            raise TimeoutError("private response body")
        return SimpleNamespace(output_parsed={"answer": "private answer"})

    client = OpenAILLMClient(sdk_client=SimpleNamespace(responses=SimpleNamespace(parse=parse)),
                             model="test-model", max_retries=1, sleep_fn=sleeps.append)
    with operation("test", operation_id="llm-operation"):
        assert client.generate_structured(system_prompt="private system", user_prompt="private user", schema={})
    completed = [e for e in events if e["event"] == "provider_attempt_finished"]
    assert [e["outcome"] for e in completed] == ["failed", "success"]
    assert [e["metadata"]["attempt"] for e in completed] == [1, 2]
    assert all(e["duration_ms"] >= 0 for e in completed)
    assert all(e["operation_id"] == "llm-operation" for e in completed)
    assert sleeps == [0.5]
    assert "private" not in json.dumps(events)


@pytest.mark.parametrize("backend", ["memory", "sqlite"])
def test_ledger_persists_diagnostic_identity_and_outcomes(backend, tmp_path):
    path = str(tmp_path / "runs.db")
    ledger = InMemoryRunLedger() if backend == "memory" else SqliteRunLedger(path)
    with operation("test", operation_id="ledger-operation"):
        ctx = ledger.start_run(source="cli", request={})
    assert ctx.operation_id == "ledger-operation"
    assert ctx.request_snapshot["operation_id"] == "ledger-operation"
    ledger.complete_run(ctx.id, outcome="no_picks")
    if backend == "sqlite":
        ledger = SqliteRunLedger(path)
    restored = ledger.get_run(ctx.id)
    assert restored.outcome == "no_picks"
    assert restored.diagnostic_summary == diagnostics.MESSAGES["no_picks"]
    assert ledger.list_runs()[0].operation_id == "ledger-operation"
    assert ledger.list_runs()[0].outcome == "no_picks"
    failed = ledger.start_run(source="api", request={"operation_id": "api-operation"})
    failed = ledger.fail_run(failed.id, error_summary="private provider response", error_code="timeout")
    assert failed.outcome == "failed"
    assert failed.diagnostic_summary == diagnostics.MESSAGES["timeout"]
    assert "private" not in failed.diagnostic_summary


def test_cli_imports_shared_services_from_outside_repo(tmp_path):
    script = Path(__file__).resolve().parents[1] / "run_match_pick_pipeline.py"
    result = subprocess.run([sys.executable, str(script), "--help"], cwd=tmp_path,
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    assert "--top-n" in result.stdout
