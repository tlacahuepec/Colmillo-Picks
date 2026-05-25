"""MLB trace schema and explanation models.

Defines the structured trace record for every MLB pick run, capturing
provenance, scoring metadata, and AI explanation with guardrails.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


class ProviderStatusEntry(BaseModel):
    provider: str
    status: str
    source: str = "unknown"
    cached: bool = False
    retrieved_at_utc: str | None = None


class PickTrace(BaseModel):
    player: str
    market: str
    direction: str
    line: float
    score: float
    confidence: str
    risk_flags: list[str] = Field(default_factory=list)
    top_factors: list[dict[str, Any]] = Field(default_factory=list)
    explanation: str = ""
    no_bet: bool = False
    no_bet_reason: str | None = None


class MLBTraceRecord(BaseModel):
    trace_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    run_id: str = ""
    sport: str = "baseball"
    league: str = "mlb"
    provider_statuses: list[ProviderStatusEntry] = Field(default_factory=list)
    input_hash: str = ""
    scorer_version: str = "1.0.0"
    scorer_config_hash: str = ""
    llm_model: str = "none"
    llm_provider: str = "none"
    prompt_hash: str = ""
    explanation_status: str = "not_requested"
    risk_flags: list[str] = Field(default_factory=list)
    no_guarantee_flag: bool = True
    picks: list[PickTrace] = Field(default_factory=list)
    created_at_utc: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    )


def compute_input_hash(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def compute_config_hash(config_path: str) -> str:
    from pathlib import Path

    content = Path(config_path).read_bytes()
    return hashlib.sha256(content).hexdigest()[:16]


def compute_prompt_hash(system_prompt: str, user_prompt: str) -> str:
    combined = system_prompt + user_prompt
    return hashlib.sha256(combined.encode()).hexdigest()[:16]
