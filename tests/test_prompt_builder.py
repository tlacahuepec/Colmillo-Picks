from __future__ import annotations

from tests.conftest import sample_match_inputs
from llm.prompt_builder import build_system_prompt, build_user_prompt


def _sample_scored_props() -> list[dict]:
    return [
        {
            "rank": 1,
            "player_id": "ars-8",
            "player_name": "Arsenal CM",
            "team_id": "ARS",
            "market": "passes",
            "line": 61.5,
            "direction": "over",
            "recommendation": "bet",
            "confidence": "high",
            "score": 0.88,
            "guardrails": {
                "blocking_warnings": ["lineup_unconfirmed:Arsenal"],
                "missing_freshness_timestamps": ["odds_timestamp_utc"],
            },
        },
        {
            "rank": 2,
            "player_id": "ars-9",
            "player_name": "Arsenal ST",
            "team_id": "ARS",
            "market": "shots",
            "line": 2.5,
            "direction": "under",
            "recommendation": "no-bet",
            "confidence": "medium",
            "score": 0.71,
            "guardrails": {
                "blocking_warnings": [],
                "missing_freshness_timestamps": [],
            },
        },
    ]


def test_build_system_prompt_requires_schema_compliant_json_only() -> None:
    prompt = build_system_prompt()

    assert "schema-compliant JSON" in prompt
    assert "Do not include markdown" in prompt


def test_build_user_prompt_includes_match_teams_top_candidates_and_risk_flags() -> None:
    match_inputs = sample_match_inputs()
    scored_props = _sample_scored_props()

    prompt = build_user_prompt(match_inputs=match_inputs, scored_props=scored_props, top_n=1)

    assert "EPL-ARS-LIV-2026-04-27" in prompt
    assert "Arsenal vs Liverpool" in prompt
    assert "Top 1 candidate props" in prompt
    assert "ars-8" in prompt
    assert "lineup_unconfirmed:Arsenal" in prompt
    assert "odds_timestamp_utc" in prompt


def test_build_user_prompt_excludes_irrelevant_raw_fields() -> None:
    match_inputs = sample_match_inputs()
    match_inputs["internal_debug_token"] = "SENSITIVE-TOKEN"
    match_inputs["players"][0]["raw_tracking_blob"] = {"very": "large"}
    scored_props = _sample_scored_props()

    prompt = build_user_prompt(match_inputs=match_inputs, scored_props=scored_props, top_n=2)

    assert "SENSITIVE-TOKEN" not in prompt
    assert "raw_tracking_blob" not in prompt
    assert "sportsbook_snapshots" not in prompt


def test_build_user_prompt_snapshot_is_stable() -> None:
    match_inputs = sample_match_inputs()
    scored_props = _sample_scored_props()

    prompt = build_user_prompt(match_inputs=match_inputs, scored_props=scored_props, top_n=1)

    assert prompt == (
        "Match context:\n"
        "- match_id: EPL-ARS-LIV-2026-04-27\n"
        "- competition: Premier League\n"
        "- fixture: Arsenal vs Liverpool\n"
        "- kickoff_utc: " + match_inputs["match"]["kickoff_utc"] + "\n\n"
        "Top 1 candidate props:\n"
        "1. ars-8 | Arsenal CM | ARS | passes 61.5 | over | bet | confidence=high | score=0.88\n"
        "   risk_flags: lineup_unconfirmed:Arsenal; odds_timestamp_utc\n\n"
        "Return only schema-compliant JSON."
    )
