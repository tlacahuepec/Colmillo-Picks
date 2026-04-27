from __future__ import annotations

from tests.conftest import load_script_module, sample_match_inputs


def test_end_to_end_score_then_render_flow() -> None:
    scorer = load_script_module("score_player_props.py")
    renderer = load_script_module("render_pick_report.py")

    match_inputs = sample_match_inputs()
    scored = scorer.score_props(match_inputs)
    report = renderer.render_report(scored_props=scored, match_inputs=match_inputs, availability_data={}, top_n=5)

    assert len(scored) == 5
    assert "Top 5 Recommended Picks" in report
    assert "| 1 |" in report
    assert "Risk Disclaimer (Mandatory)" in report


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
