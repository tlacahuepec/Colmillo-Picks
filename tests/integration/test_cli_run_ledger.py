"""Integration test: CLI creates a run record in the ledger."""

from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
import tempfile

from tests.conftest import REPO_ROOT


def test_cli_execution_creates_run_record_without_changing_output() -> None:
    script = REPO_ROOT / "skills" / "soccer-prop-picks" / "scripts" / "run_match_pick_pipeline.py"

    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = os.path.join(tmp_dir, "runs.db")

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
            env={
                "PATH": str(os.environ.get("PATH", "")),
                "COLMILLO_RUNS_DB_PATH": db_path,
            },
        )

        report = result.stdout
        assert "Top 5 Recommended Picks" in report
        assert "## Guardrail Status" in report

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM run_ledger").fetchall()
        conn.close()

        assert len(rows) == 1
        row = rows[0]
        assert row["status"] == "success"
        assert row["source"] == "cli"
        assert row["match_query"] == "juve - milan today"
        assert row["duration_ms"] is not None
        assert row["duration_ms"] >= 0
