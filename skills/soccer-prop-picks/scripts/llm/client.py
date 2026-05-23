from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class GroundingSource:
    url: str
    title: str


class LLMClient(Protocol):
    def generate_structured(self, *, system_prompt: str, user_prompt: str, schema: dict) -> dict:
        """Generate a structured object that satisfies the provided JSON schema."""


class LLMError(RuntimeError):
    """Raised when an LLM provider fails, times out, or returns invalid output."""
