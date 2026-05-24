"""Tests for the daily intelligence prompt builder."""

from __future__ import annotations

import json

from llm.intelligence_prompt_builder import (
    build_daily_intelligence_system_prompt,
    build_daily_intelligence_user_prompt,
)


def test_system_prompt_contains_live_search_instruction() -> None:
    prompt = build_daily_intelligence_system_prompt()
    assert "web search" in prompt.lower()
    assert "JSON" in prompt


def test_system_prompt_contains_no_fabrication_guardrail() -> None:
    prompt = build_daily_intelligence_system_prompt()
    assert "null" in prompt
    assert "Never invent" in prompt or "never invent" in prompt.lower()


def test_system_prompt_has_no_markdown_fences() -> None:
    prompt = build_daily_intelligence_system_prompt()
    assert "```" not in prompt


def test_user_prompt_is_valid_json() -> None:
    raw = build_daily_intelligence_user_prompt(date_utc="2026-05-21", top_n=5)
    parsed = json.loads(raw)
    assert isinstance(parsed, dict)


def test_user_prompt_contains_date_utc() -> None:
    raw = build_daily_intelligence_user_prompt(date_utc="2026-05-21", top_n=5)
    assert "2026-05-21" in raw


def test_user_prompt_embeds_top_n_in_task_and_rules() -> None:
    raw = build_daily_intelligence_user_prompt(date_utc="2026-05-21", top_n=3)
    assert "3" in raw


def test_user_prompt_is_stable_for_same_inputs() -> None:
    a = build_daily_intelligence_user_prompt(date_utc="2026-05-21", top_n=5)
    b = build_daily_intelligence_user_prompt(date_utc="2026-05-21", top_n=5)
    assert a == b


def test_user_prompt_required_json_shape_has_top_matches() -> None:
    raw = build_daily_intelligence_user_prompt(date_utc="2026-05-21", top_n=5)
    parsed = json.loads(raw)
    shape = parsed["required_json_shape"]
    assert "top_matches" in shape
    match = shape["top_matches"][0]
    for key in ("rank", "injuries", "projected_lineups", "odds", "match_importance"):
        assert key in match, f"missing key: {key}"


def test_user_prompt_selection_criteria_mentions_major_leagues() -> None:
    raw = build_daily_intelligence_user_prompt(date_utc="2026-05-21", top_n=5)
    assert "Champions League" in raw
    assert "Premier League" in raw
    assert "La Liga" in raw
