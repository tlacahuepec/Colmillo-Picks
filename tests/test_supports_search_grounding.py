"""Tests for _supports_search_grounding and fixture provider grounding guard."""

from __future__ import annotations

from dependency_bundle import _supports_search_grounding


class TestSupportsSearchGrounding:
    def test_gemini_2_flash(self) -> None:
        assert _supports_search_grounding("gemini-2.5-flash") is True

    def test_gemini_2_pro(self) -> None:
        assert _supports_search_grounding("gemini-2.5-pro") is True

    def test_gemini_2_0_flash(self) -> None:
        assert _supports_search_grounding("gemini-2.0-flash") is True

    def test_gemini_2_flash_lite(self) -> None:
        assert _supports_search_grounding("gemini-2.5-flash-lite") is True

    def test_gemini_3_flash(self) -> None:
        assert _supports_search_grounding("gemini-3.5-flash") is True

    def test_gemini_3_pro(self) -> None:
        assert _supports_search_grounding("gemini-3.0-pro") is True

    def test_rejects_gpt(self) -> None:
        assert _supports_search_grounding("gpt-4") is False

    def test_rejects_gemini_1(self) -> None:
        assert _supports_search_grounding("gemini-1.5-pro") is False

    def test_rejects_claude(self) -> None:
        assert _supports_search_grounding("claude-3") is False

    def test_rejects_grok(self) -> None:
        assert _supports_search_grounding("grok-3") is False
