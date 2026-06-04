from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class GroundingSource:
    url: str
    title: str


@dataclass(frozen=True)
class GroundingSupport:
    start_index: int
    end_index: int
    text: str
    source_indices: tuple[int, ...]


@dataclass(frozen=True)
class GroundingMetadataResult:
    sources: tuple[GroundingSource, ...]
    supports: tuple[GroundingSupport, ...]
    web_search_queries: tuple[str, ...]


class LLMClient(Protocol):
    def generate_structured(
        self, *, system_prompt: str, user_prompt: str, schema: dict, temperature: float | None = None
    ) -> dict:
        """Generate a structured object that satisfies the provided JSON schema."""


class LLMError(RuntimeError):
    """Raised when an LLM provider fails, times out, or returns invalid output."""
