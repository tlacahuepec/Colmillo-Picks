from __future__ import annotations

from tests.conftest import load_script_module, sample_match_inputs


def test_score_props_returns_top_five_ranked_candidates() -> None:
    scorer = load_script_module("score_player_props.py")
    match_inputs = sample_match_inputs()

    results = scorer.score_props(match_inputs)

    assert len(results) == 5
    assert all(item["market"] in {"passes", "shots"} for item in results)
    assert results == sorted(results, key=lambda item: item["score"], reverse=True)


def test_score_props_attaches_guardrails_and_model_metadata() -> None:
    scorer = load_script_module("score_player_props.py")
    match_inputs = sample_match_inputs()

    results = scorer.score_props(match_inputs)

    first = results[0]
    assert "guardrails" in first
    assert "required_timestamps" in first["guardrails"]
    assert first["model_version"]
    assert "top_contributing_factors" in first["explainability"]


def test_unconfirmed_lineup_creates_blocking_warning_flag() -> None:
    scorer = load_script_module("score_player_props.py")
    match_inputs = sample_match_inputs()
    match_inputs["teams"][0]["projected_lineup"]["status"] = "projected"

    results = scorer.score_props(match_inputs)

    assert any("lineup_unconfirmed" in w for w in results[0]["guardrails"]["blocking_warnings"])
    assert "blocking_warning_active" in results[0]["explainability"]["risk_flags"]
