from __future__ import annotations

from tests.conftest import load_script_module, sample_match_inputs


def test_render_report_includes_required_sections() -> None:
    scorer = load_script_module("score_player_props.py")
    renderer = load_script_module("render_pick_report.py")

    match_inputs = sample_match_inputs()
    scored = scorer.score_props(match_inputs)
    availability = {
        "picks": {
            f"{item['player_id']}:{item['market']}": {
                "prizepicks": "available" if i == 0 else "unavailable",
                "alternatives": {"Underdog": "available" if i == 1 else "unavailable"},
                "retrieved_at_utc": "2026-04-27T12:00:00Z",
            }
            for i, item in enumerate(scored)
        }
    }

    report = renderer.render_report(scored, match_inputs, availability_data=availability, top_n=5)

    assert "# Soccer Prop Pick Report" in report
    assert "## 3) Top 5 Recommended Picks" in report
    assert "## 4) Availability Check" in report
    assert "## 5) Decision Playbook Checkpoints" in report
    assert "## 6) Response Contract" in report
    assert "### Assumptions Disclosure" in report
    assert "### Confidence Explanation Rules" in report
    assert "### No-Bet Trigger Rules" in report
    assert "Arsenal" in report
    assert "Liverpool" in report


def test_render_report_uses_trace_rationale_when_provided() -> None:
    renderer = load_script_module("render_pick_report.py")
    match_inputs = sample_match_inputs()
    scored = [
        {
            "player": "Arsenal CM",
            "player_id": "ars-8",
            "team_id": "ARS",
            "market": "passes",
            "line": 61.5,
            "direction": "under",
            "recommendation": "bet",
            "confidence": "high",
            "baseline_projection": 54.0,
            "model_version": "test",
            "explainability": {
                "risk_flags": ["old_risk"],
                "top_contributing_factors": [{"factor": "old_factor", "score": 0.9}],
            },
            "guardrails": {"blocking_warnings": [], "required_timestamps": {}},
        }
    ]
    trace = {
        "picks": [
            {
                "player_id": "ars-8",
                "market": "passes",
                "rationale": {
                    "minutes_signal": "trace_minutes_signal",
                    "tactical_fit": "trace_tactical_fit",
                    "notes": "trace_note",
                    "primary_risks_summary": "trace_risk_summary",
                    "why_this_pick": "trace_why_line",
                },
                "risk_tags": ["trace_risk_tag"],
                "no_bet_reasons": [],
            }
        ]
    }

    report = renderer.render_report(scored, match_inputs, availability_data={}, top_n=1, trace=trace)

    assert "trace_minutes_signal" in report
    assert "trace_tactical_fit" in report
    assert "trace_note" in report
    assert "trace_risk_summary" in report
    assert "trace_why_line" in report
    assert "old_factor" not in report


def test_render_report_shows_under_direction_and_no_bet_label() -> None:
    renderer = load_script_module("render_pick_report.py")
    match_inputs = sample_match_inputs()
    scored = [
        {
            "player": "Arsenal CM",
            "player_id": "ars-8",
            "team_id": "ARS",
            "market": "passes",
            "line": 61.5,
            "direction": "under",
            "recommendation": "bet",
            "confidence": "high",
            "baseline_projection": 54.0,
            "model_version": "test",
            "explainability": {
                "risk_flags": ["test_flag"],
                "top_contributing_factors": [{"factor": "role_opportunity", "score": 0.9}],
            },
            "guardrails": {"blocking_warnings": [], "required_timestamps": {}},
        },
        {
            "player": "Arsenal ST",
            "player_id": "ars-9",
            "team_id": "ARS",
            "market": "shots",
            "line": 2.5,
            "direction": "under",
            "recommendation": "no-bet",
            "confidence": "low",
            "baseline_projection": 2.5,
            "model_version": "test",
            "explainability": {"risk_flags": ["ambiguous_direction"], "top_contributing_factors": []},
            "guardrails": {"blocking_warnings": [], "required_timestamps": {}},
        },
    ]

    report = renderer.render_report(scored, match_inputs, availability_data={}, top_n=2)

    assert "| 1 | Arsenal CM | ARS | passes | Under | BET | High |" in report
    assert "| 2 | Arsenal ST | ARS | shots | No Bet | NO-BET | Low |" in report
