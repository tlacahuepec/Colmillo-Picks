"""Tests for the LLM post-match stats provider."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from llm_post_match_stats import (
    LLMPostMatchStatsProvider,
    build_stats_prompt,
)


class TestBuildStatsPrompt:
    def test_prompt_includes_player_names(self):
        picks = [
            {"player": "Aaron Judge", "market": "hits"},
            {"player": "Mookie Betts", "market": "strikeouts"},
        ]
        prompt = build_stats_prompt(
            match_description="NYY vs BOS 2026-05-25", picks=picks
        )
        assert "Aaron Judge" in prompt
        assert "Mookie Betts" in prompt

    def test_prompt_includes_markets(self):
        picks = [{"player": "Judge", "market": "hits"}]
        prompt = build_stats_prompt(match_description="NYY vs BOS", picks=picks)
        assert "hits" in prompt

    def test_prompt_requests_confidence(self):
        picks = [{"player": "Judge", "market": "hits"}]
        prompt = build_stats_prompt(match_description="NYY vs BOS", picks=picks)
        assert "confidence" in prompt.lower()


class TestLLMPostMatchStatsProvider:
    def test_returns_parsed_stats(self):
        mock_client = MagicMock()
        mock_client.generate_structured.return_value = {
            "stats": [
                {"player": "Judge", "market": "hits", "actual_value": 2, "confidence": "high"},
            ]
        }

        provider = LLMPostMatchStatsProvider(llm_client=mock_client)
        results = provider.fetch_player_stats(
            match_description="NYY vs BOS 2026-05-25",
            picks=[{"player": "Judge", "market": "hits"}],
        )

        assert len(results) == 1
        assert results[0].player == "Judge"
        assert results[0].actual_value == 2
        assert results[0].confidence == "high"

    def test_filters_low_confidence_when_requested(self):
        mock_client = MagicMock()
        mock_client.generate_structured.return_value = {
            "stats": [
                {"player": "Judge", "market": "hits", "actual_value": 2, "confidence": "low"},
            ]
        }

        provider = LLMPostMatchStatsProvider(llm_client=mock_client)
        results = provider.fetch_player_stats(
            match_description="NYY vs BOS",
            picks=[{"player": "Judge", "market": "hits"}],
            min_confidence="high",
        )

        assert len(results) == 0

    def test_handles_llm_error_gracefully(self):
        mock_client = MagicMock()
        mock_client.generate_structured.side_effect = RuntimeError("LLM timeout")

        provider = LLMPostMatchStatsProvider(llm_client=mock_client)

        with pytest.raises(RuntimeError, match="LLM timeout"):
            provider.fetch_player_stats(
                match_description="NYY vs BOS",
                picks=[{"player": "Judge", "market": "hits"}],
            )

    def test_empty_picks_returns_empty(self):
        mock_client = MagicMock()
        provider = LLMPostMatchStatsProvider(llm_client=mock_client)
        results = provider.fetch_player_stats(
            match_description="NYY vs BOS", picks=[]
        )
        assert results == []
        mock_client.generate_structured.assert_not_called()
