from __future__ import annotations

from copy import deepcopy

from llm.client import LLMClient


class DeterministicMockLLMClient(LLMClient):
    """Deterministic fixture-based LLM client for tests and local development."""

    def __init__(self, *, fixture: dict | None = None) -> None:
        self._fixture = fixture or {
            "decision": "lean_over",
            "confidence": 0.5,
            "reasons": ["mock_reason"],
        }

    def generate_structured(
        self, *, system_prompt: str, user_prompt: str, schema: dict, temperature: float | None = None
    ) -> dict:
        _ = (system_prompt, user_prompt, schema, temperature)
        return deepcopy(self._fixture)
