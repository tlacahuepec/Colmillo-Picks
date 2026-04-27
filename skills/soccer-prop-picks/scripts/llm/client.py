from __future__ import annotations

from typing import Protocol


class LLMClient(Protocol):
    def generate_structured(self, *, system_prompt: str, user_prompt: str, schema: dict) -> dict:
        """Generate a structured object that satisfies the provided JSON schema."""


class LLMError(RuntimeError):
    """Raised when an LLM provider fails, times out, or returns invalid output."""
