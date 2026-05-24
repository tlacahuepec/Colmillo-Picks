from __future__ import annotations

from types import SimpleNamespace

import pytest

from tests.conftest import load_script_module



def test_run_pipeline_calls_collaborators_in_order() -> None:
    pipeline_service = load_script_module("pipeline_service.py")
    call_order: list[str] = []

    parsed_query = SimpleNamespace(home_team="Juve", away_team="Milan", match_date="2026-05-03")
    match_request = {"home_team": "Juve", "away_team": "Milan", "match_date": "2026-05-03", "competition": "League"}
    match_inputs = {"match": {"id": "x"}}
    scored_payload = {"scores": [{"player": "A"}], "trace": {"picks": []}}

    def parse_match_query(match_query: str):
        call_order.append("parse")
        assert match_query == "juve - milan today"
        return parsed_query

    def build_match_input_request(*, parsed, competition: str):
        call_order.append("build_request")
        assert parsed is parsed_query
        assert competition == "League"
        return match_request

    def collect_inputs(request):
        call_order.append("collect")
        assert request is match_request
        return match_inputs

    def score_props(*, match_inputs, include_trace: bool):
        call_order.append("score")
        assert match_inputs == {"match": {"id": "x"}}
        assert include_trace is True
        return scored_payload

    def render_report(*, scored_props, match_inputs, availability_data, top_n: int, trace):
        call_order.append("render")
        assert scored_props == scored_payload["scores"]
        assert match_inputs == {"match": {"id": "x"}}
        assert availability_data == {}
        assert top_n == 3
        assert trace["picks"] == scored_payload["trace"]["picks"]
        assert trace["llm_status"] == "not_requested"
        return "rendered report"

    report = pipeline_service.run_pipeline(
        request={"match_query": "juve - milan today", "top_n": 3},
        deps={
            "parse_match_query": parse_match_query,
            "build_match_input_request": build_match_input_request,
            "collect_inputs": collect_inputs,
            "score_props": score_props,
            "render_report": render_report,
        },
    )

    assert report == "rendered report"
    assert call_order == ["parse", "build_request", "collect", "score", "render"]



def test_run_pipeline_surfaces_predictable_stage_errors() -> None:
    pipeline_service = load_script_module("pipeline_service.py")

    base_deps = {
        "parse_match_query": lambda _: SimpleNamespace(home_team="Juve", away_team="Milan", match_date="2026-05-03"),
        "build_match_input_request": lambda **_: {"request": True},
        "collect_inputs": lambda _: {"match": {"id": "x"}},
        "score_props": lambda **_: {"scores": [], "trace": {"picks": []}},
        "render_report": lambda **_: "report",
    }

    for stage in ("parse", "collect", "score"):
        deps = dict(base_deps)
        if stage == "parse":
            deps["parse_match_query"] = lambda _: (_ for _ in ()).throw(ValueError("bad parse"))
        elif stage == "collect":
            deps["collect_inputs"] = lambda _: (_ for _ in ()).throw(RuntimeError("collector down"))
        else:
            deps["score_props"] = lambda **_: (_ for _ in ()).throw(RuntimeError("scorer down"))

        with pytest.raises(pipeline_service.PipelineServiceError) as exc_info:
            pipeline_service.run_pipeline(request={"match_query": "juve - milan today", "top_n": 2}, deps=deps)

        assert exc_info.value.stage == stage
        assert str(exc_info.value) == f"Pipeline failed during '{stage}' stage."
        assert exc_info.value.__cause__ is not None


def test_run_pipeline_skips_llm_enrichment_by_default() -> None:
    pipeline_service = load_script_module("pipeline_service.py")
    calls = {"llm": 0}
    scored_payload = {"scores": [{"player": "A"}], "trace": {"picks": []}}

    def enrich_with_llm(*, scored_payload, match_inputs):
        calls["llm"] += 1
        return scored_payload

    report = pipeline_service.run_pipeline(
        request={"match_query": "juve - milan today", "top_n": 1},
        deps={
            "parse_match_query": lambda _: SimpleNamespace(home_team="Juve", away_team="Milan", match_date="2026-05-03"),
            "build_match_input_request": lambda **_: {"request": True},
            "collect_inputs": lambda _: {"match": {"id": "x"}},
            "score_props": lambda **_: scored_payload,
            "enrich_with_llm": enrich_with_llm,
            "render_report": lambda **kwargs: kwargs["scored_props"][0]["player"],
        },
    )

    assert report == "A"
    assert calls["llm"] == 0


def test_run_pipeline_sets_trace_llm_metadata_when_llm_not_requested() -> None:
    pipeline_service = load_script_module("pipeline_service.py")
    captured: dict[str, object] = {}
    scored_payload = {"scores": [{"player": "A"}], "trace": {"picks": []}}

    def render_report(*, scored_props, match_inputs, availability_data, top_n: int, trace):
        captured["trace"] = trace
        return "rendered"

    pipeline_service.run_pipeline(
        request={"match_query": "juve - milan today", "top_n": 1, "use_llm": False},
        deps={
            "parse_match_query": lambda _: SimpleNamespace(home_team="Juve", away_team="Milan", match_date="2026-05-03"),
            "build_match_input_request": lambda **_: {"request": True},
            "collect_inputs": lambda _: {"match": {"id": "x"}},
            "score_props": lambda **_: scored_payload,
            "enrich_with_llm": lambda **_: scored_payload,
            "render_report": render_report,
        },
    )

    trace = captured["trace"]
    assert trace["llm_status"] == "not_requested"
    assert trace["llm_fallback_used"] is False


def test_run_pipeline_invokes_llm_enrichment_when_requested() -> None:
    pipeline_service = load_script_module("pipeline_service.py")
    calls = {"llm": 0}
    match_inputs = {"match": {"id": "x"}}
    scored_payload = {"scores": [{"player": "A"}], "trace": {"picks": []}}

    def enrich_with_llm(*, scored_payload, match_inputs):
        calls["llm"] += 1
        assert match_inputs == {"match": {"id": "x"}}
        return {
            "scores": [{"player": "A+"}],
            "trace": {"picks": [], "notes": ["LLM enriched"]},
        }

    report = pipeline_service.run_pipeline(
        request={
            "match_query": "juve - milan today",
            "top_n": 1,
            "use_llm": True,
            "llm_provider": "openai",
            "llm_model": "gpt-4.1-mini",
        },
        deps={
            "parse_match_query": lambda _: SimpleNamespace(home_team="Juve", away_team="Milan", match_date="2026-05-03"),
            "build_match_input_request": lambda **_: {"request": True},
            "collect_inputs": lambda _: match_inputs,
            "score_props": lambda **_: scored_payload,
            "enrich_with_llm": enrich_with_llm,
            "render_report": lambda **kwargs: kwargs["scored_props"][0]["player"],
        },
    )

    assert report == "A+"
    assert calls["llm"] == 1


def test_run_pipeline_sets_success_llm_trace_metadata() -> None:
    pipeline_service = load_script_module("pipeline_service.py")
    captured: dict[str, object] = {}
    scored_payload = {"scores": [{"player": "A"}], "trace": {"picks": []}}

    def render_report(*, scored_props, match_inputs, availability_data, top_n: int, trace):
        captured["trace"] = trace
        return "rendered report"

    pipeline_service.run_pipeline(
        request={
            "match_query": "juve - milan today",
            "top_n": 1,
            "use_llm": True,
            "llm_provider": "openai",
            "llm_model": "gpt-4.1-mini",
        },
        deps={
            "parse_match_query": lambda _: SimpleNamespace(home_team="Juve", away_team="Milan", match_date="2026-05-03"),
            "build_match_input_request": lambda **_: {"request": True},
            "collect_inputs": lambda _: {"match": {"id": "x"}},
            "score_props": lambda **_: scored_payload,
            "enrich_with_llm": lambda **_: {"scores": [{"player": "A+"}], "trace": {"picks": []}},
            "render_report": render_report,
        },
    )

    trace = captured["trace"]
    assert trace["llm_provider"] == "openai"
    assert trace["llm_model"] == "gpt-4.1-mini"
    assert trace["llm_status"] == "success"
    assert trace["llm_fallback_used"] is False
    assert isinstance(trace["llm_latency_ms"], int)
    assert trace["llm_latency_ms"] >= 0


def test_run_pipeline_falls_back_when_llm_enrichment_fails() -> None:
    pipeline_service = load_script_module("pipeline_service.py")
    scored_payload = {"scores": [{"player": "A"}], "trace": {"picks": []}}

    def enrich_with_llm(*, scored_payload, match_inputs):
        raise RuntimeError("LLM unavailable")

    captured = {}

    def render_report(*, scored_props, match_inputs, availability_data, top_n: int, trace):
        captured["scored_props"] = scored_props
        captured["trace"] = trace
        return "rendered fallback report"

    report = pipeline_service.run_pipeline(
        request={
            "match_query": "juve - milan today",
            "top_n": 1,
            "use_llm": True,
            "llm_provider": "openai",
            "llm_model": "gpt-4.1-mini",
        },
        deps={
            "parse_match_query": lambda _: SimpleNamespace(home_team="Juve", away_team="Milan", match_date="2026-05-03"),
            "build_match_input_request": lambda **_: {"request": True},
            "collect_inputs": lambda _: {"match": {"id": "x"}},
            "score_props": lambda **_: scored_payload,
            "enrich_with_llm": enrich_with_llm,
            "render_report": render_report,
        },
    )

    assert report == "rendered fallback report"
    assert captured["scored_props"] == [{"player": "A"}]
    assert captured["trace"]["notes"] == ["LLM enrichment failed; using deterministic results."]
    assert captured["trace"]["llm_status"] == "failed"
    assert captured["trace"]["llm_fallback_used"] is True


def test_run_pipeline_trace_shows_default_model_when_llm_requested_without_explicit_model() -> None:
    pipeline_service = load_script_module("pipeline_service.py")
    captured: dict[str, object] = {}
    scored_payload = {"scores": [{"player": "A"}], "trace": {"picks": []}}

    def render_report(*, scored_props, match_inputs, availability_data, top_n: int, trace):
        captured["trace"] = trace
        return "rendered"

    pipeline_service.run_pipeline(
        request={
            "match_query": "juve - milan today",
            "top_n": 1,
            "use_llm": True,
        },
        deps={
            "parse_match_query": lambda _: SimpleNamespace(home_team="Juve", away_team="Milan", match_date="2026-05-03"),
            "build_match_input_request": lambda **_: {"request": True},
            "collect_inputs": lambda _: {"match": {"id": "x"}},
            "score_props": lambda **_: scored_payload,
            "enrich_with_llm": lambda **_: {"scores": [{"player": "A+"}], "trace": {"picks": []}},
            "render_report": render_report,
        },
    )

    trace = captured["trace"]
    assert trace["llm_provider"] == "gemini"
    assert trace["llm_model"] == "gemini-2.5-flash"
    assert trace["llm_status"] == "success"
