"""Tests for MLB validation harness script."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "validate_mlb.py"


class TestValidateMLBScript:
    def test_script_runs_successfully(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH)],
            capture_output=True, text=True, timeout=30,
        )
        assert result.returncode == 0
        assert "MLB VALIDATION HARNESS" in result.stdout
        assert "HIT RATE" in result.stdout

    def test_script_market_filter(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), "--market", "hits"],
            capture_output=True, text=True, timeout=30,
        )
        assert result.returncode == 0
        assert "Market filter: hits" in result.stdout

    def test_reproducible_output(self):
        result1 = subprocess.run(
            [sys.executable, str(SCRIPT_PATH)],
            capture_output=True, text=True, timeout=30,
        )
        result2 = subprocess.run(
            [sys.executable, str(SCRIPT_PATH)],
            capture_output=True, text=True, timeout=30,
        )
        assert result1.stdout == result2.stdout

    def test_minimum_10_games(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH)],
            capture_output=True, text=True, timeout=30,
        )
        assert "Games evaluated: 10" in result.stdout


class TestValidationFunction:
    def test_run_validation_returns_stats(self):
        sys.path.insert(0, str(SCRIPT_PATH.parent.parent / "skills" / "soccer-prop-picks" / "scripts"))
        sys.path.insert(0, str(SCRIPT_PATH.parent))

        from validate_mlb import run_validation

        stats = run_validation()
        assert stats["games_evaluated"] >= 10
        assert stats["total_picks"] > 0
        assert stats["decided"] > 0
        assert stats["hit_rate"] is not None
        assert 0 <= stats["hit_rate"] <= 1

    def test_run_validation_market_filter(self):
        from validate_mlb import run_validation

        stats = run_validation(market_filter="hits")
        assert stats["market_filter"] == "hits"
        assert stats["decided"] > 0

    def test_run_validation_unknown_market_returns_zero(self):
        from validate_mlb import run_validation

        stats = run_validation(market_filter="nonexistent_market")
        assert stats["decided"] == 0
        assert stats["hit_rate"] is None
