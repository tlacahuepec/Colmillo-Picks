from __future__ import annotations

import copy

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
    assert "context_signals" in first["explainability"]


def test_score_props_can_optionally_emit_reasoning_trace() -> None:
    scorer = load_script_module("score_player_props.py")
    match_inputs = sample_match_inputs()

    payload = scorer.score_props(match_inputs, include_trace=True)

    assert set(payload.keys()) == {"scores", "trace"}
    assert isinstance(payload["scores"], list)
    trace = payload["trace"]
    assert isinstance(trace, dict)
    assert trace["match_context_summary"]["fixture"] == "Arsenal vs Liverpool"
    assert trace["guardrail_results"]["required_timestamps"]["odds_timestamp_utc"]
    assert isinstance(trace["picks"], list)
    assert len(trace["picks"]) == len(payload["scores"])

    for pick in trace["picks"]:
        assert isinstance(pick["rank"], int)
        assert isinstance(pick["risk_tags"], list)
        assert isinstance(pick["no_bet_reasons"], list)
        assert isinstance(pick["rationale"], dict)
        assert isinstance(pick["rationale"]["primary_risks_summary"], str)
        assert isinstance(pick["rationale"]["why_this_pick"], str)


def test_unconfirmed_lineup_creates_blocking_warning_flag() -> None:
    scorer = load_script_module("score_player_props.py")
    match_inputs = sample_match_inputs()
    match_inputs["teams"][0]["projected_lineup"]["status"] = "projected"

    results = scorer.score_props(match_inputs)

    assert any("lineup_unconfirmed" in w for w in results[0]["guardrails"]["blocking_warnings"])
    assert "blocking_warning_active" in results[0]["explainability"]["risk_flags"]


def _get_candidate(results: list[dict], player_id: str, market: str) -> dict:
    return next(item for item in results if item["player_id"] == player_id and item["market"] == market)


def test_higher_team_win_probability_increases_passes_score() -> None:
    scorer = load_script_module("score_player_props.py")
    low_prob_inputs = sample_match_inputs()
    high_prob_inputs = copy.deepcopy(low_prob_inputs)
    low_prob_inputs["teams"][0]["team_win_probability"] = 0.2
    high_prob_inputs["teams"][0]["team_win_probability"] = 0.75

    low_prob_results = scorer.score_props(low_prob_inputs)
    high_prob_results = scorer.score_props(high_prob_inputs)
    low_candidate = _get_candidate(low_prob_results, "ars-8", "passes")
    high_candidate = _get_candidate(high_prob_results, "ars-8", "passes")

    assert high_candidate["score"] > low_candidate["score"]


def test_stronger_last_five_form_increases_shots_score() -> None:
    scorer = load_script_module("score_player_props.py")
    poor_form_inputs = sample_match_inputs()
    hot_form_inputs = copy.deepcopy(poor_form_inputs)
    poor_form_inputs["teams"][0]["last_5_results"] = ["L", "L", "D", "L", "D"]
    hot_form_inputs["teams"][0]["last_5_results"] = ["W", "W", "W", "D", "W"]

    poor_form_results = scorer.score_props(poor_form_inputs)
    hot_form_results = scorer.score_props(hot_form_inputs)
    poor_candidate = _get_candidate(poor_form_results, "ars-9", "shots")
    hot_candidate = _get_candidate(hot_form_results, "ars-9", "shots")

    assert hot_candidate["score"] > poor_candidate["score"]


def test_home_context_beats_away_context_for_same_player_market() -> None:
    scorer = load_script_module("score_player_props.py")
    home_inputs = sample_match_inputs()
    away_inputs = copy.deepcopy(home_inputs)
    away_inputs["teams"][0]["home_away"] = "away"
    away_inputs["teams"][1]["home_away"] = "home"

    home_results = scorer.score_props(home_inputs)
    away_results = scorer.score_props(away_inputs)
    home_candidate = _get_candidate(home_results, "ars-8", "passes")
    away_candidate = _get_candidate(away_results, "ars-8", "passes")

    assert home_candidate["score"] > away_candidate["score"]


def test_new_context_factors_can_surface_in_top_contributors() -> None:
    scorer = load_script_module("score_player_props.py")
    match_inputs = sample_match_inputs()
    match_inputs["teams"][0]["team_win_probability"] = 0.82
    match_inputs["teams"][0]["last_5_results"] = ["W", "W", "W", "W", "W"]

    results = scorer.score_props(match_inputs)
    candidate = _get_candidate(results, "ars-8", "passes")
    top_factor_names = {item["factor"] for item in candidate["explainability"]["top_contributing_factors"]}

    assert top_factor_names & {"win_probability_context", "last_5_form_momentum", "home_away_adjustment"}


def test_clear_over_edge_sets_over_direction_and_bet() -> None:
    scorer = load_script_module("score_player_props.py")
    match_inputs = sample_match_inputs()
    player = next(item for item in match_inputs["players"] if item["player_id"] == "ars-8")
    player["expected_passes_baseline"] = 72.0
    player["market_lines"]["passes"] = 61.5

    results = scorer.score_props(match_inputs)
    candidate = _get_candidate(results, "ars-8", "passes")

    assert candidate["direction"] == "over"
    assert candidate["recommendation"] == "bet"


def test_clear_under_edge_sets_under_direction_and_bet() -> None:
    scorer = load_script_module("score_player_props.py")
    match_inputs = sample_match_inputs()
    player = next(item for item in match_inputs["players"] if item["player_id"] == "ars-8")
    player["expected_passes_baseline"] = 49.0
    player["market_lines"]["passes"] = 61.5

    results = scorer.score_props(match_inputs)
    candidate = _get_candidate(results, "ars-8", "passes")

    assert candidate["direction"] == "under"
    assert candidate["recommendation"] == "bet"


def test_no_edge_returns_no_bet_with_ambiguous_flags() -> None:
    scorer = load_script_module("score_player_props.py")
    match_inputs = sample_match_inputs()
    player = next(item for item in match_inputs["players"] if item["player_id"] == "ars-8")
    player["expected_passes_baseline"] = 61.55
    player["market_lines"]["passes"] = 61.5

    results = scorer.score_props(match_inputs)
    candidate = _get_candidate(results, "ars-8", "passes")

    assert candidate["direction"] == "no-bet"
    assert candidate["recommendation"] == "no-bet"
    assert "insufficient_projection_edge" in candidate["explainability"]["risk_flags"]
    assert "ambiguous_direction" in candidate["explainability"]["risk_flags"]
