"""MLB explanation service with deterministic fallback and hallucination guard.

Provides explanations for scored baseball picks. Supports two modes:
1. Deterministic: factor-list explanation without LLM
2. LLM-enriched: uses an LLM client with validation guardrails
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Protocol

BANNED_GUARANTEE_WORDS = frozenset([
    "guaranteed", "certain", "sure thing", "lock", "certainty",
    "100%", "can't lose", "no-brainer", "slam dunk",
])

_NO_GUARANTEE_DISCLAIMER = "This is a projection, not a prediction of outcome. Past performance does not predict future results."


class LLMClientProtocol(Protocol):
    def generate_structured(self, *, system_prompt: str, user_prompt: str, schema: dict) -> dict: ...


@dataclass
class ValidationResult:
    valid: bool
    reason: str = ""


def build_deterministic_explanation(
    pick: dict[str, Any],
    *,
    no_bet: bool = False,
    no_bet_reason: str | None = None,
) -> str:
    player = pick.get("player", "Unknown")
    market = pick.get("market", "unknown")
    direction = pick.get("direction", "over")
    line = pick.get("line", 0)
    confidence = pick.get("confidence", "medium")
    explainability = pick.get("explainability", {})
    factors = explainability.get("top_contributing_factors", [])
    risk_flags = explainability.get("risk_flags", [])

    parts: list[str] = []

    if no_bet:
        reason_text = no_bet_reason or "insufficient data"
        parts.append(f"{player} — NO-BET {market} (reason: {reason_text})")
    else:
        parts.append(f"{player} — {direction.upper()} {line} {market} (confidence: {confidence})")

    if factors:
        factor_strs = [f"{f['factor']} ({f['score']:.2f})" for f in factors[:3]]
        parts.append(f"Key factors: {', '.join(factor_strs)}")

    if risk_flags:
        parts.append(f"Risks: {', '.join(risk_flags)}")

    parts.append(_NO_GUARANTEE_DISCLAIMER)
    return "\n".join(parts)


def validate_explanation_against_inputs(
    explanation: str, context: dict[str, Any]
) -> ValidationResult:
    explanation_lower = explanation.lower()

    for word in BANNED_GUARANTEE_WORDS:
        if word in explanation_lower:
            return ValidationResult(valid=False, reason=f"Contains banned guarantee language: '{word}'")

    known_players = {p.lower() for p in context.get("players", [])}
    if known_players:
        words_in_explanation = set(re.findall(r"[A-Z][a-z]+ [A-Z][a-z]+", explanation))
        for name in words_in_explanation:
            if name.lower() not in known_players and name.lower() not in _COMMON_TERMS:
                return ValidationResult(
                    valid=False,
                    reason=f"Hallucination detected: references unknown player '{name}'",
                )

    return ValidationResult(valid=True)


_COMMON_TERMS = frozenset([
    "yankee stadium", "fenway park", "wrigley field",
    "no bet", "key factors", "this pick",
])


_SYSTEM_PROMPT = """You are a baseball analytics assistant explaining MLB prop picks.
Use ONLY the supplied context to generate your explanation.
Do NOT reference any players, stats, or information not present in the input data.
Do NOT use words like: guaranteed, certain, sure thing, lock, certainty, 100%, can't lose.
Keep explanations concise (2-3 sentences max).
Always include a note that outcomes are not guaranteed."""

_EXPLANATION_SCHEMA = {
    "type": "object",
    "properties": {
        "explanation": {"type": "string"},
    },
    "required": ["explanation"],
}


def build_llm_explanation(
    *,
    pick: dict[str, Any],
    input_context: dict[str, Any],
    llm_client: LLMClientProtocol,
) -> str:
    try:
        user_prompt = _build_user_prompt(pick, input_context)
        response = llm_client.generate_structured(
            system_prompt=_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            schema=_EXPLANATION_SCHEMA,
        )
        explanation = response.get("explanation", "")

        validation = validate_explanation_against_inputs(explanation, input_context)
        if not validation.valid:
            return build_deterministic_explanation(pick)

        return explanation

    except Exception:
        return build_deterministic_explanation(pick)


def _build_user_prompt(pick: dict[str, Any], context: dict[str, Any]) -> str:
    player = pick.get("player", "Unknown")
    market = pick.get("market", "unknown")
    direction = pick.get("direction", "over")
    line = pick.get("line", 0)
    confidence = pick.get("confidence", "medium")
    factors = pick.get("explainability", {}).get("top_contributing_factors", [])

    parts = [
        f"Player: {player}",
        f"Market: {market}",
        f"Direction: {direction} {line}",
        f"Confidence: {confidence}",
        f"Top factors: {factors}",
        f"Context: {context}",
        "Explain why this pick was selected using only the data above.",
    ]
    return "\n".join(parts)


def explain_picks(
    *,
    picks: list[dict[str, Any]],
    input_context: dict[str, Any],
    use_llm: bool = False,
    llm_client: LLMClientProtocol | None = None,
    no_bet_picks: set[str] | None = None,
) -> list[dict[str, Any]]:
    no_bet_picks = no_bet_picks or set()
    results: list[dict[str, Any]] = []

    for pick in picks:
        player = pick.get("player", "Unknown")
        market = pick.get("market", "unknown")
        pick_key = f"{player}:{market}"
        is_no_bet = pick_key in no_bet_picks

        if use_llm and llm_client is not None and not is_no_bet:
            explanation = build_llm_explanation(
                pick=pick, input_context=input_context, llm_client=llm_client
            )
            deterministic_fallback = build_deterministic_explanation(pick)
            status = "llm_success" if explanation != deterministic_fallback else "deterministic_fallback"
        else:
            explanation = build_deterministic_explanation(
                pick, no_bet=is_no_bet, no_bet_reason="scorer_designation" if is_no_bet else None
            )
            status = "deterministic"

        results.append({
            "player": player,
            "market": market,
            "explanation": explanation,
            "explanation_status": status,
            "no_bet": is_no_bet,
        })

    return results
