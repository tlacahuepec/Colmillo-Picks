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
        assert trace == scored_payload["trace"]
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
