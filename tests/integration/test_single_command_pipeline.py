from __future__ import annotations

import os
import subprocess
import sys

from tests.conftest import REPO_ROOT


def test_one_command_cli_prints_required_report_sections() -> None:
    script = REPO_ROOT / "skills" / "soccer-prop-picks" / "scripts" / "run_match_pick_pipeline.py"

    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "juve - milan today",
            "--top-n",
            "3",
            "--allow-deterministic-fallback",
        ],
        check=True,
        capture_output=True,
        text=True,
        env={"PATH": str(os.environ.get("PATH", ""))},
    )

    report = result.stdout
    assert "Top 5 Recommended Picks" in report
    assert "## Guardrail Status" in report
    assert "## 4) Availability Check" in report
