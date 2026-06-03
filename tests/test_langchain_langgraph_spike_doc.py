"""Tests for the LangChain/LangGraph orchestration spike decision document."""

from __future__ import annotations

from pathlib import Path


DOC_PATH = Path(__file__).resolve().parents[1] / "docs" / "langchain-langgraph-orchestration-spike.md"


def _content() -> str:
    assert DOC_PATH.exists(), f"Missing spike decision document: {DOC_PATH}"
    return DOC_PATH.read_text(encoding="utf-8")


class TestLangChainLangGraphSpikeDoc:
    def test_acceptance_criteria_sections_are_present(self) -> None:
        content = _content()
        required_sections = [
            "## Executive Summary",
            "## Current Colmillo Pipeline Fit",
            "## Option Comparison",
            "## Highest-Value Pipeline Stages",
            "## Recommendation",
            "## Follow-up Notes",
        ]
        for section in required_sections:
            assert section in content, f"Missing section: {section}"

    def test_compares_each_required_option(self) -> None:
        content = _content().lower()
        for option in ("langchain", "langgraph", "current approach"):
            assert option in content, f"Missing option comparison for {option}"

        assert "pros" in content
        assert "cons" in content

    def test_identifies_one_or_two_pipeline_stages(self) -> None:
        content = _content()
        expected_phrase = "Most likely to benefit"
        assert content.count(expected_phrase) in {1, 2}

    def test_records_clear_recommendation(self) -> None:
        content = _content().lower()
        assert "recommendation: defer broad adoption" in content
        assert "pilot langgraph" in content
        assert "do not add langchain as a broad dependency" in content
