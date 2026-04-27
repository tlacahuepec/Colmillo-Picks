from __future__ import annotations

import json
import subprocess
import sys

from tests.conftest import REPO_ROOT, sample_match_inputs


def test_cli_run_scores_and_renders_report() -> None:
    match_inputs = sample_match_inputs()
    score_script = REPO_ROOT / "skills" / "soccer-prop-picks" / "scripts" / "score_player_props.py"
    render_script = REPO_ROOT / "skills" / "soccer-prop-picks" / "scripts" / "render_pick_report.py"

    score_result = subprocess.run(
        [
            sys.executable,
            str(score_script),
            "--input-json",
            json.dumps(match_inputs),
            "--emit-trace",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    score_payload = json.loads(score_result.stdout)
    scored_props = score_payload["scores"]
    trace = score_payload["trace"]

    assert len(scored_props) == 5
    assert isinstance(trace, dict)
    assert trace.get("picks")

    render_result = subprocess.run(
        [
            sys.executable,
            str(render_script),
            "--input-json",
            json.dumps(scored_props),
            "--match-input-json",
            json.dumps(match_inputs),
            "--trace-json",
            json.dumps(trace),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    report = render_result.stdout
    assert "Top 5 Recommended Picks" in report
    assert "Availability Check" in report
    assert "Response Contract" in report
