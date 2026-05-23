"""Tests for scripts/smoke_test.py — release smoke test runner."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"


class TestCliSmokeTest:
    def test_smoke_test_script_exists(self):
        assert (SCRIPTS_DIR / "smoke_test.py").exists()

    def test_cli_deterministic_mode_succeeds(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "smoke_test.py"), "--cli"],
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert result.returncode == 0, f"stdout: {result.stdout}\nstderr: {result.stderr}"
        assert "PASS" in result.stdout

    def test_smoke_test_fails_on_broken_import(self):
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS_DIR / "smoke_test.py"),
                "--cli",
                "--entry-point",
                "nonexistent_module.py",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 1
        assert "FAIL" in result.stdout or "FAIL" in result.stderr

    def test_version_check_mode(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "smoke_test.py"), "--version-check"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0
        assert "PASS" in result.stdout
