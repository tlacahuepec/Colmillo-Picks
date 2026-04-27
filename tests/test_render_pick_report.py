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
    assert "Arsenal" in report
    assert "Liverpool" in report
