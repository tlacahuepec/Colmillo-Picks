"""Tests that availability checks are wired into the pipeline."""

from __future__ import annotations

from typing import Any

import pytest

from availability.mock_adapter import DeterministicMockAvailabilityAdapter
from pipeline_service import run_pipeline_with_payload


def _stub_deps(*, availability_adapter=None) -> dict[str, Any]:
    """Build minimal deps dict for pipeline testing."""

    class _Parsed:
        home_team = "Arsenal"
        away_team = "Liverpool"
        match_date = "2026-05-17"

    def parse_match_query(query: str):
        return _Parsed()

    def build_match_input_request(*, parsed, competition):
        return {"home": parsed.home_team, "away": parsed.away_team}

    def collect_inputs(request):
        return {
            "match": {"id": "x", "fixture_status": "scheduled"},
            "lineups": {},
            "odds": {},
            "weather": {},
        }

    def score_props(*, match_inputs, include_trace=False):
        return {
            "scores": [
                {
                    "player_id": "ars-8",
                    "player": "Odegaard",
                    "market": "passes",
                    "line": 52.5,
                    "direction": "over",
                    "score": 0.85,
                    "confidence": "high",
                    "recommendation": "bet",
                },
                {
                    "player_id": "liv-11",
                    "player": "Salah",
                    "market": "shots",
                    "line": 2.5,
                    "direction": "over",
                    "score": 0.72,
                    "confidence": "medium",
                    "recommendation": "bet",
                },
            ],
            "trace": {"llm_status": "not_requested"},
        }

    def enrich_with_llm(*, scored_payload, match_inputs):
        return scored_payload

    def render_report(*, scored_props, match_inputs, availability_data=None, top_n=5, trace=None):
        return f"availability_keys={list((availability_data or {}).get('picks', {}).keys())}"

    deps = {
        "parse_match_query": parse_match_query,
        "build_match_input_request": build_match_input_request,
        "collect_inputs": collect_inputs,
        "score_props": score_props,
        "enrich_with_llm": enrich_with_llm,
        "render_report": render_report,
        "check_availability": availability_adapter.check_picks if availability_adapter else None,
    }
    return deps


def test_pipeline_calls_availability_adapter_and_passes_data_to_renderer() -> None:
    adapter = DeterministicMockAvailabilityAdapter(
        seed_data={
            "ars-8:passes": {"prizepicks": "available"},
            "liv-11:shots": {"prizepicks": "unavailable"},
        },
    )
    deps = _stub_deps(availability_adapter=adapter)

    result = run_pipeline_with_payload(
        request={"match_query": "arsenal - liverpool today", "top_n": 2},
        deps=deps,
    )

    assert "ars-8:passes" in result["report_markdown"]
    assert "liv-11:shots" in result["report_markdown"]


def test_pipeline_works_without_availability_provider() -> None:
    deps = _stub_deps(availability_adapter=None)

    result = run_pipeline_with_payload(
        request={"match_query": "arsenal - liverpool today", "top_n": 2},
        deps=deps,
    )

    assert "availability_keys=[]" in result["report_markdown"]


def test_pipeline_survives_availability_adapter_failure() -> None:
    class _FailingAdapter:
        def check_picks(self, picks):
            raise RuntimeError("Network timeout")

    deps = _stub_deps()
    deps["check_availability"] = _FailingAdapter().check_picks

    result = run_pipeline_with_payload(
        request={"match_query": "arsenal - liverpool today", "top_n": 2},
        deps=deps,
    )

    assert "availability_keys=[]" in result["report_markdown"]
