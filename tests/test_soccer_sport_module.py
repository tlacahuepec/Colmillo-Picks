"""Tests for the fully wired SoccerSportModule."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from sport_module import SoccerModule, SportModule
from tests.conftest import sample_match_inputs

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "skills" / "soccer-prop-picks" / "scripts"


@pytest.fixture
def sample_inputs() -> dict[str, Any]:
    return sample_match_inputs()


class TestSoccerModuleProtocol:
    def test_soccer_module_satisfies_protocol(self) -> None:
        module = SoccerModule()
        assert isinstance(module, SportModule)

    def test_soccer_module_sport_id(self) -> None:
        module = SoccerModule()
        assert module.sport_id == "soccer"

    def test_soccer_module_supported_markets(self) -> None:
        module = SoccerModule()
        assert module.supported_markets == {"passes", "shots"}

    def test_soccer_module_supported_leagues(self) -> None:
        module = SoccerModule()
        assert "premier_league" in module.supported_leagues
        assert "la_liga" in module.supported_leagues


class TestSoccerModuleScore:
    def test_score_with_sample_inputs(self, sample_inputs: dict) -> None:
        module = SoccerModule()
        scored = module.score(sample_inputs, markets=("passes", "shots"))
        assert isinstance(scored, list)
        assert len(scored) > 0
        assert "player" in scored[0]
        assert "score" in scored[0]

    def test_score_returns_only_requested_markets(self, sample_inputs: dict) -> None:
        module = SoccerModule()
        scored = module.score(sample_inputs, markets=("passes",))
        for pick in scored:
            assert pick["market"] == "passes"


class TestSoccerModuleExplain:
    def test_explain_produces_non_empty_string(self) -> None:
        module = SoccerModule()
        pick = {
            "player": "Test Player",
            "market": "passes",
            "line": 55.5,
            "direction": "over",
            "score": 0.75,
            "confidence": "high",
        }
        explanation = module.explain(pick)
        assert isinstance(explanation, str)
        assert len(explanation) > 0
        assert "Test Player" in explanation

    def test_explain_includes_market_and_direction(self) -> None:
        module = SoccerModule()
        pick = {
            "player": "Star CM",
            "market": "shots",
            "line": 3.5,
            "direction": "under",
            "score": 0.6,
            "confidence": "medium",
        }
        explanation = module.explain(pick)
        assert "shots" in explanation
        assert "under" in explanation


class TestSoccerModuleCollectInputs:
    def test_collect_inputs_deterministic(self) -> None:
        module = SoccerModule(allow_deterministic_fallback=True)
        inputs = module.collect_inputs(
            home_team="Arsenal", away_team="Liverpool", match_date="2026-06-01"
        )
        assert isinstance(inputs, dict)
        assert "players" in inputs
        assert "teams" in inputs


class TestRegressionCLI:
    def test_cli_still_produces_report(self, tmp_path: Path) -> None:
        import os

        env = {**os.environ, "COLMILLO_RUNS_DB_PATH": str(tmp_path / "runs.db"), "PYTHONIOENCODING": "utf-8"}
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS_DIR / "run_match_pick_pipeline.py"),
                "arsenal - liverpool 2026-06-01",
                "--allow-deterministic-fallback",
            ],
            capture_output=True,
            timeout=60,
            env=env,
        )
        stdout = result.stdout.decode("utf-8", errors="replace")
        assert result.returncode == 0, f"CLI failed: {result.stderr.decode('utf-8', errors='replace')}"
        assert "Pick" in stdout or "pick" in stdout
