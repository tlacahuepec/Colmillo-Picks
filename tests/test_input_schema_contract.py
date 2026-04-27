from __future__ import annotations

import copy
import json
import re
from datetime import datetime
from typing import Any

import pytest

from tests.conftest import REPO_ROOT, sample_match_inputs


class SchemaError(Exception):
    def __init__(self, path: list[str | int], message: str) -> None:
        self.path = path
        self.message = message
        super().__init__(f"{path}: {message}")


def _load_schema() -> dict[str, Any]:
    schema_path = REPO_ROOT / "docs" / "schemas" / "soccer_pick_input.schema.json"
    return json.loads(schema_path.read_text(encoding="utf-8"))


def _is_iso_datetime(value: str) -> bool:
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
        return True
    except ValueError:
        return False


def _validate_instance(instance: Any, schema: dict[str, Any], root: dict[str, Any], path: list[str | int]) -> list[SchemaError]:
    if "$ref" in schema:
        ref = schema["$ref"]
        if not ref.startswith("#/$defs/"):
            return [SchemaError(path, f"Unsupported ref: {ref}")]
        target = root["$defs"][ref.split("/")[-1]]
        return _validate_instance(instance, target, root, path)

    errors: list[SchemaError] = []
    schema_type = schema.get("type")

    if schema_type == "object":
        if not isinstance(instance, dict):
            return [SchemaError(path, "Expected object")]

        required = schema.get("required", [])
        for key in required:
            if key not in instance:
                errors.append(SchemaError(path + [key], "Missing required property"))

        additional = schema.get("additionalProperties", True)
        properties = schema.get("properties", {})
        if additional is False:
            for key in instance:
                if key not in properties:
                    errors.append(SchemaError(path + [key], "Additional property is not allowed"))

        for key, subschema in properties.items():
            if key in instance:
                errors.extend(_validate_instance(instance[key], subschema, root, path + [key]))

    elif schema_type == "array":
        if not isinstance(instance, list):
            return [SchemaError(path, "Expected array")]
        min_items = schema.get("minItems")
        max_items = schema.get("maxItems")
        if min_items is not None and len(instance) < min_items:
            errors.append(SchemaError(path, f"Expected at least {min_items} items"))
        if max_items is not None and len(instance) > max_items:
            errors.append(SchemaError(path, f"Expected at most {max_items} items"))

        item_schema = schema.get("items")
        if item_schema:
            for idx, item in enumerate(instance):
                errors.extend(_validate_instance(item, item_schema, root, path + [idx]))

    elif schema_type == "string":
        if not isinstance(instance, str):
            return [SchemaError(path, "Expected string")]
        if "enum" in schema and instance not in schema["enum"]:
            errors.append(SchemaError(path, "Value not in enum"))
        if "pattern" in schema and re.match(schema["pattern"], instance) is None:
            errors.append(SchemaError(path, "String does not match pattern"))
        if schema.get("format") == "date-time" and not _is_iso_datetime(instance):
            errors.append(SchemaError(path, "Invalid date-time format"))

    elif schema_type == "number":
        if not isinstance(instance, (int, float)) or isinstance(instance, bool):
            return [SchemaError(path, "Expected number")]
        if "minimum" in schema and float(instance) < float(schema["minimum"]):
            errors.append(SchemaError(path, f"Value below minimum {schema['minimum']}"))
        if "maximum" in schema and float(instance) > float(schema["maximum"]):
            errors.append(SchemaError(path, f"Value above maximum {schema['maximum']}"))
        if "exclusiveMinimum" in schema and float(instance) <= float(schema["exclusiveMinimum"]):
            errors.append(SchemaError(path, f"Value must be > {schema['exclusiveMinimum']}"))

    elif schema_type == "integer":
        if not isinstance(instance, int) or isinstance(instance, bool):
            return [SchemaError(path, "Expected integer")]
        if "minimum" in schema and instance < int(schema["minimum"]):
            errors.append(SchemaError(path, f"Value below minimum {schema['minimum']}"))
        if "maximum" in schema and instance > int(schema["maximum"]):
            errors.append(SchemaError(path, f"Value above maximum {schema['maximum']}"))

    elif schema_type == "boolean":
        if not isinstance(instance, bool):
            return [SchemaError(path, "Expected boolean")]

    if "enum" in schema and instance not in schema["enum"]:
        errors.append(SchemaError(path, "Value not in enum"))

    return errors


def _validate_payload(payload: dict[str, Any]) -> list[SchemaError]:
    schema = _load_schema()
    return _validate_instance(payload, schema, schema, [])


def test_sample_match_inputs_matches_input_schema_contract() -> None:
    errors = _validate_payload(sample_match_inputs())

    assert errors == [], "Schema drift detected:\n" + "\n".join(
        f"{error.path}: {error.message}" for error in errors
    )


@pytest.mark.parametrize(
    ("mutator", "expected_path"),
    [
        pytest.param(
            lambda payload: payload["teams"][0]["projected_lineup"].pop("source_timestamp_utc"),
            ["teams", 0, "projected_lineup", "source_timestamp_utc"],
            id="missing_required_key",
        ),
        pytest.param(
            lambda payload: payload["teams"][1]["suspensions"].__setitem__(
                0,
                {
                    "player_name": "Suspended B",
                    "reason": "red_card",
                    "status": "pending",
                },
            ),
            ["teams", 1, "suspensions", 0, "status"],
            id="bad_enum_value",
        ),
        pytest.param(
            lambda payload: payload["match"]["weather"].__setitem__("source_timestamp_utc", "not-a-timestamp"),
            ["match", "weather", "source_timestamp_utc"],
            id="malformed_timestamp",
        ),
    ],
)
def test_input_schema_rejects_invalid_payloads(mutator, expected_path: list[str | int]) -> None:
    payload = copy.deepcopy(sample_match_inputs())
    mutator(payload)

    errors = _validate_payload(payload)

    assert errors, "Expected at least one schema validation error"
    assert any(error.path == expected_path for error in errors)
