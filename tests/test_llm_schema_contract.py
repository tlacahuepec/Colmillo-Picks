from __future__ import annotations

import copy
import json
from typing import Any

import pytest

from llm.schema_validation import validate_llm_payload
from tests.conftest import REPO_ROOT
from tests.test_input_schema_contract import _validate_instance



def _load_schema() -> dict[str, Any]:
    schema_path = REPO_ROOT / "docs" / "schemas" / "llm_pick_explanation.schema.json"
    return json.loads(schema_path.read_text(encoding="utf-8"))



def _valid_payload() -> dict[str, Any]:
    return {
        "player_id": "ars-8",
        "market_type": "passes",
        "recommended_side": "over",
        "confidence_band": "medium",
        "rationale": "Projection and role stability support this edge.",
        "risk_flags": ["lineup volatility"],
    }



def test_llm_pick_explanation_schema_allows_valid_payload() -> None:
    schema = _load_schema()

    errors = _validate_instance(_valid_payload(), schema, schema, [])

    assert errors == []


@pytest.mark.parametrize(
    "missing_field",
    [
        "player_id",
        "market_type",
        "recommended_side",
        "confidence_band",
        "rationale",
        "risk_flags",
    ],
)
def test_llm_pick_explanation_schema_rejects_missing_required_fields(missing_field: str) -> None:
    schema = _load_schema()
    payload = _valid_payload()
    payload.pop(missing_field)

    errors = _validate_instance(payload, schema, schema, [])

    assert errors
    assert any(err.path == [missing_field] and err.message == "Missing required property" for err in errors)


@pytest.mark.parametrize(
    ("field", "invalid_value"),
    [
        ("confidence_band", "very_high"),
        ("recommended_side", "lean_over"),
    ],
)
def test_llm_pick_explanation_schema_rejects_enum_violations(field: str, invalid_value: str) -> None:
    schema = _load_schema()
    payload = _valid_payload()
    payload[field] = invalid_value

    errors = _validate_instance(payload, schema, schema, [])

    assert errors
    assert any(err.path == [field] and err.message == "Value not in enum" for err in errors)



def test_validate_llm_payload_returns_normalized_copy() -> None:
    payload = copy.deepcopy(_valid_payload())
    payload["recommended_side"] = " Over "
    payload["confidence_band"] = " Medium "
    payload["risk_flags"] = [" lineup volatility ", ""]

    validated = validate_llm_payload(payload)

    assert validated == {
        "player_id": "ars-8",
        "market_type": "passes",
        "recommended_side": "over",
        "confidence_band": "medium",
        "rationale": "Projection and role stability support this edge.",
        "risk_flags": ["lineup volatility"],
    }



def test_validate_llm_payload_raises_clear_error_for_invalid_enum() -> None:
    payload = _valid_payload()
    payload["confidence_band"] = "certain"

    with pytest.raises(ValueError, match="confidence_band must be one of"):
        validate_llm_payload(payload)
