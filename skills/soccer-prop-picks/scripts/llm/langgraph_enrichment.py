"""LangGraph enrichment state schema and graph implementation."""

from __future__ import annotations

from typing import Any, TypedDict

from llm.client import GroundingMetadataResult


class EnrichmentState(TypedDict, total=False):
    prompt: dict[str, str]
    raw_output: dict[str, Any]
    explanations: list[dict[str, Any]]
    grounding_metadata: GroundingMetadataResult | None
    scored_payload: dict[str, Any]
    match_inputs: dict[str, Any]
    top_n: int
    transitions: list[str]
    error: str | None
