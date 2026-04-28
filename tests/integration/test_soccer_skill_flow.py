from __future__ import annotations

import os
import subprocess
import sys

from availability.mock_adapter import DeterministicMockAvailabilityAdapter

from tests.conftest import load_script_module, sample_match_inputs


def _section(report: str, heading: str, next_heading: str) -> str:
    start = report.index(heading)
    end = report.index(next_heading, start)
    return report[start:end]


def _markdown_data_rows(section: str) -> list[str]:
    return [
        line
        for line in section.splitlines()
        if line.startswith("|")
        and "---" not in line
        and "Rank |" not in line
        and "Player | Team | Prop Type" not in line
        and "Model Version" not in line
    ]


def test_end_to_end_score_then_render_flow() -> None:
    scorer = load_script_module("score_player_props.py")
    renderer = load_script_module("render_pick_report.py")

    match_inputs = sample_match_inputs()
    scored = scorer.score_props(match_inputs)
    report = renderer.render_report(scored_props=scored, match_inputs=match_inputs, availability_data={}, top_n=5)

    assert len(scored) == 5
    assert "Top 5 Recommended Picks" in report
    assert "Decision Playbook Checkpoints" in report
    assert "Response Contract" in report
    assert "Assumptions Disclosure" in report
    assert "Confidence Explanation Rules" in report
    assert "No-Bet Trigger Rules" in report
    assert "| 1 |" in report
    assert "Risk Disclaimer (Mandatory)" in report

    top_picks = _section(report, "## 3) Top 5 Recommended Picks", "## 4) Availability Check")
    top_pick_rows = _markdown_data_rows(top_picks)
    assert len(top_pick_rows) == 5
    for row in top_pick_rows:
        cells = [cell.strip() for cell in row.split("|")[1:-1]]
        assert len(cells) == 9
        assert cells[5] in {"BET", "NO-BET"}
        assert cells[6] in {"High", "Medium", "Low"}
        assert cells[8]

    availability = _section(report, "## 4) Availability Check", "### Availability Fallback Behavior")
    availability_rows = _markdown_data_rows(availability)
    assert len(availability_rows) == 5


def test_end_to_end_includes_deterministic_under_pick_from_fixture() -> None:
    scorer = load_script_module("score_player_props.py")
    match_inputs = sample_match_inputs()
    target_player = next(item for item in match_inputs["players"] if item["player_id"] == "ars-8")
    target_player["expected_passes_baseline"] = 47.0
    target_player["market_lines"]["passes"] = 61.5

    scored = scorer.score_props(match_inputs)
    under_candidate = next(item for item in scored if item["player_id"] == "ars-8" and item["market"] == "passes")

    assert under_candidate["direction"] == "under"
    assert under_candidate["recommendation"] == "bet"


def test_end_to_end_top_five_contains_mixed_over_and_under_directions() -> None:
    scorer = load_script_module("score_player_props.py")
    match_inputs = sample_match_inputs()
    ars_mid = next(item for item in match_inputs["players"] if item["player_id"] == "ars-8")
    liv_cb = next(item for item in match_inputs["players"] if item["player_id"] == "liv-4")
    ars_mid["expected_passes_baseline"] = 47.0
    ars_mid["market_lines"]["passes"] = 61.5
    liv_cb["expected_passes_baseline"] = 77.0
    liv_cb["market_lines"]["passes"] = 64.5

    scored = scorer.score_props(match_inputs)
    top_five_directions = {item["direction"] for item in scored[:5]}

    assert "under" in top_five_directions
    assert "over" in top_five_directions


def test_top_pick_why_includes_match_context_and_player_role_signals() -> None:
    scorer = load_script_module("score_player_props.py")
    renderer = load_script_module("render_pick_report.py")

    match_inputs = sample_match_inputs()
    scored = scorer.score_props(match_inputs)
    report = renderer.render_report(scored_props=scored, match_inputs=match_inputs, availability_data={}, top_n=5)

    top_picks = _section(report, "## 3) Top 5 Recommended Picks", "## 4) Availability Check")
    top_pick_rows = _markdown_data_rows(top_picks)
    rationale_cells = []
    for row in top_pick_rows:
        cells = [cell.strip() for cell in row.split("|")[1:-1]]
        # include both "Primary Risks" and "Why This Pick" as rationale text
        rationale_cells.append(cells[7])
        rationale_cells.append(cells[8])
    rationale_blob = " ".join(rationale_cells)

    assert any(signal in rationale_blob for signal in {"home_context", "away_context", "home_away_adjustment", "win_probability_context", "match_state_context"})
    assert any(signal in rationale_blob for signal in {"role_opportunity", "attacker_role_for_passes", "deep_role_for_shots"})


def test_missing_platform_data_uses_fallback_and_resolves_final_availability() -> None:
    scorer = load_script_module("score_player_props.py")
    renderer = load_script_module("render_pick_report.py")

    match_inputs = sample_match_inputs()
    scored = scorer.score_props(match_inputs)
    top = scored[:5]
    availability_data = {
        "fallback_mode": True,
        "fallback_reason": "platform_timeout",
        "picks": {
            f"{top[0]['player_id']}:{top[0]['market']}": {
                "prizepicks": "unknown",
                "alternatives": {"Underdog": "available", "Sleeper": "unknown"},
                "retrieved_at_utc": "2026-04-27T12:00:00Z",
            },
            f"{top[1]['player_id']}:{top[1]['market']}": {
                "prizepicks": "unknown",
                "alternatives": {"Underdog": "unavailable"},
                "retrieved_at_utc": "2026-04-27T12:00:00Z",
            },
        },
    }

    report = renderer.render_report(scored_props=scored, match_inputs=match_inputs, availability_data=availability_data, top_n=5)
    availability = _section(report, "## 4) Availability Check", "### Availability Fallback Behavior")
    availability_rows = _markdown_data_rows(availability)

    assert len(availability_rows) == 5
    assert "platform_timeout" in availability
    assert "| 1 |" in availability
    assert "Underdog:available" in availability
    assert "| available |" in availability
    assert "| unknown |" in availability


def test_guardrail_warnings_propagate_to_final_report() -> None:
    scorer = load_script_module("score_player_props.py")
    renderer = load_script_module("render_pick_report.py")

    match_inputs = sample_match_inputs()
    match_inputs["teams"][0]["projected_lineup"]["status"] = "projected"
    match_inputs["market"]["source_timestamp_utc"] = "2026-04-27T00:00:00Z"

    scored = scorer.score_props(match_inputs)
    report = renderer.render_report(scored_props=scored, match_inputs=match_inputs, availability_data={}, top_n=5)

    assert "## Guardrail Status" in report
    assert "lineup_unconfirmed:Arsenal" in report
    assert "odds_stale:" in report


def test_trace_to_report_consistency_for_top_pick() -> None:
    scorer = load_script_module("score_player_props.py")
    renderer = load_script_module("render_pick_report.py")

    match_inputs = sample_match_inputs()
    scored_payload = scorer.score_props(match_inputs, include_trace=True)
    scored = scored_payload["scores"]
    trace = scored_payload["trace"]

    report = renderer.render_report(scored_props=scored, match_inputs=match_inputs, availability_data={}, top_n=5, trace=trace)

    top_pick = trace["picks"][0]
    assert top_pick["rationale"]["why_this_pick"] in report
    assert top_pick["rationale"]["primary_risks_summary"] in report


def test_fallback_mode_with_partial_adapter_data_marks_missing_picks_unknown() -> None:
    scorer = load_script_module("score_player_props.py")
    renderer = load_script_module("render_pick_report.py")

    match_inputs = sample_match_inputs()
    scored = scorer.score_props(match_inputs)
    top = scored[:5]
    adapter = DeterministicMockAvailabilityAdapter(
        seed_data={
            f"{top[0]['player_id']}:{top[0]['market']}": {
                "prizepicks": "unknown",
                "alternatives": {"Underdog": "available"},
                "retrieved_at_utc": "2026-04-27T12:00:00Z",
            },
            f"{top[1]['player_id']}:{top[1]['market']}": {
                "prizepicks": "unavailable",
                "alternatives": {"Underdog": "unavailable"},
                "retrieved_at_utc": "2026-04-27T12:00:00Z",
            },
        },
        fallback_mode=True,
        fallback_reason="partial_platform_data",
    )
    availability_data = adapter.check_picks(
        [{"player_id": item["player_id"], "market": item["market"]} for item in top]
    )

    report = renderer.render_report(scored_props=scored, match_inputs=match_inputs, availability_data=availability_data, top_n=5)
    availability = _section(report, "## 4) Availability Check", "### Availability Fallback Behavior")

    assert "yes (partial_platform_data)" in availability
    assert "Underdog:available" in availability
    assert "| unavailable |" in availability
    assert "| unknown |" in availability


def test_end_to_end_user_path_is_single_command_cli() -> None:
    script = load_script_module("run_match_pick_pipeline.py").__file__

    result = subprocess.run(
        [sys.executable, script, "arsenal - liverpool today", "--top-n", "2"],
        check=True,
        capture_output=True,
        text=True,
        env={"PATH": str(os.environ.get("PATH", "")), "API_FOOTBALL_API_KEY": "dummy-test-key"},
    )

    report = result.stdout
    assert "Top 5 Recommended Picks" in report
    assert "## 4) Availability Check" in report
