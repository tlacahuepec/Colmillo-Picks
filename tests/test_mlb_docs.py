"""Tests for S15 documentation completeness and correctness."""

from __future__ import annotations

from pathlib import Path

import pytest


_ROOT = Path(__file__).resolve().parents[1]
_DOCS = _ROOT / "docs"


class TestReadmeMultiSport:
    def test_readme_mentions_soccer(self):
        readme = (_ROOT / "README.md").read_text(encoding="utf-8")
        assert "soccer" in readme.lower()

    def test_readme_mentions_basketball(self):
        readme = (_ROOT / "README.md").read_text(encoding="utf-8")
        assert "basketball" in readme.lower()

    def test_readme_mentions_baseball(self):
        readme = (_ROOT / "README.md").read_text(encoding="utf-8")
        assert "baseball" in readme.lower() or "mlb" in readme.lower()

    def test_readme_mentions_multi_sport(self):
        readme = (_ROOT / "README.md").read_text(encoding="utf-8")
        assert "multi-sport" in readme.lower() or "multiple sports" in readme.lower()


class TestMLBArchitectureDoc:
    @pytest.fixture
    def arch_doc(self) -> str:
        path = _DOCS / "mlb-architecture.md"
        assert path.exists(), f"Missing {path}"
        return path.read_text(encoding="utf-8")

    def test_has_data_flow_section(self, arch_doc):
        assert "data flow" in arch_doc.lower() or "pipeline" in arch_doc.lower()

    def test_has_provider_section(self, arch_doc):
        assert "provider" in arch_doc.lower()

    def test_has_scoring_section(self, arch_doc):
        assert "scoring" in arch_doc.lower()

    def test_has_no_bet_section(self, arch_doc):
        assert "no-bet" in arch_doc.lower() or "no_bet" in arch_doc.lower()

    def test_has_trace_section(self, arch_doc):
        assert "trace" in arch_doc.lower()

    def test_has_cache_section(self, arch_doc):
        assert "cache" in arch_doc.lower()

    def test_has_mermaid_diagram(self, arch_doc):
        assert "```mermaid" in arch_doc


class TestMLBMarketsDoc:
    @pytest.fixture
    def markets_doc(self) -> str:
        path = _DOCS / "mlb-markets.md"
        assert path.exists(), f"Missing {path}"
        return path.read_text(encoding="utf-8")

    def test_has_market_table(self, markets_doc):
        assert "|" in markets_doc

    def test_lists_hits_market(self, markets_doc):
        assert "hits" in markets_doc.lower()

    def test_lists_home_runs_market(self, markets_doc):
        assert "home_runs" in markets_doc or "home runs" in markets_doc.lower()

    def test_lists_strikeouts_market(self, markets_doc):
        assert "strikeouts" in markets_doc.lower()

    def test_lists_settlement_rules(self, markets_doc):
        assert "settlement" in markets_doc.lower()


class TestMLBResponsibleGamingDoc:
    @pytest.fixture
    def rg_doc(self) -> str:
        path = _DOCS / "mlb-responsible-gaming.md"
        assert path.exists(), f"Missing {path}"
        return path.read_text(encoding="utf-8")

    def test_has_banned_words_section(self, rg_doc):
        assert "banned" in rg_doc.lower() or "prohibited" in rg_doc.lower()

    def test_has_disclaimer_section(self, rg_doc):
        assert "disclaimer" in rg_doc.lower()

    def test_mentions_ncpg(self, rg_doc):
        assert "ncpg" in rg_doc.lower() or "1-800-522-4700" in rg_doc


class TestEnvExampleMLBVars:
    @pytest.fixture
    def env_example(self) -> str:
        path = _ROOT / ".env.example"
        assert path.exists()
        return path.read_text(encoding="utf-8")

    def test_has_baseball_section(self, env_example):
        assert "baseball" in env_example.lower() or "mlb" in env_example.lower()
