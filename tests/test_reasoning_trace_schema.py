from __future__ import annotations

import json
from typing import Any

from tests.conftest import REPO_ROOT, load_script_module, sample_match_inputs
from tests.test_input_schema_contract import _validate_instance


def _load_schema() -> dict[str, Any]:
    schema_path = REPO_ROOT / "docs" / "schemas" / "soccer_analysis_trace.schema.json"
    return json.loads(schema_path.read_text(encoding="utf-8"))


def test_trace_schema_validates_generated_trace_payload() -> None:
    scorer = load_script_module("score_player_props.py")
    schema = _load_schema()

    payload = scorer.score_props(sample_match_inputs(), include_trace=True)

    errors = _validate_instance(payload["trace"], schema, schema, [])
    assert errors == [], "Trace schema drift:\n" + "\n".join(f"{e.path}: {e.message}" for e in errors)


def test_trace_schema_rejects_wrong_pick_field_type() -> None:
    schema = _load_schema()
    scorer = load_script_module("score_player_props.py")
    payload = scorer.score_props(sample_match_inputs(), include_trace=True)["trace"]
    payload["picks"][0]["risk_tags"] = "not-a-list"

    errors = _validate_instance(payload, schema, schema, [])

    assert errors
    assert any(e.path == ["picks", 0, "risk_tags"] for e in errors)
