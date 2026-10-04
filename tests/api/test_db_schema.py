"""Schema regression guard for SQLAlchemy declarative models.

Ensures that refactoring models (e.g. from legacy Column to Mapped/mapped_column)
does not inadvertently change table names, column names, types, nullability,
or primary keys.
"""

from __future__ import annotations

from services.api.db import Base


EXPECTED_SCHEMA = {
    "picks_history": [
        ("id", "VARCHAR(36)", False, True),
        ("created_at", "DATETIME", False, False),
        ("match_query", "VARCHAR(255)", False, False),
        ("competition", "VARCHAR(255)", True, False),
        ("top_n", "INTEGER", False, False),
        ("request_json", "TEXT", False, False),
        ("report_markdown", "TEXT", False, False),
        ("scores_json", "TEXT", False, False),
        ("trace_json", "TEXT", True, False),
        ("fixture_status", "VARCHAR(64)", True, False),
        ("llm_status", "VARCHAR(64)", True, False),
        ("latency_ms", "INTEGER", True, False),
        ("status", "VARCHAR(16)", False, False),
        ("error_stage", "VARCHAR(64)", True, False),
        ("error_message", "TEXT", True, False),
        ("error_details_json", "TEXT", True, False),
        ("sport", "VARCHAR(32)", True, False),
        ("league", "VARCHAR(64)", True, False),
        ("markets_json", "TEXT", True, False),
        ("scheduled_kickoff_utc", "DATETIME", True, False),
        ("operation_id", "VARCHAR(64)", True, False),
        ("outcome", "VARCHAR(16)", True, False),
        ("diagnostics_json", "TEXT", True, False),
    ],
    "pick_outcomes": [
        ("id", "VARCHAR(36)", False, True),
        ("pick_id", "VARCHAR(36)", False, False),
        ("rank", "INTEGER", False, False),
        ("player", "VARCHAR(255)", False, False),
        ("market", "VARCHAR(64)", False, False),
        ("result", "VARCHAR(8)", False, False),
        ("recorded_at", "DATETIME", False, False),
        ("resolution_attempted_at", "DATETIME", True, False),
        ("last_resolution_error", "TEXT", True, False),
    ],
    "pick_jobs": [
        ("id", "VARCHAR(36)", False, True),
        ("pick_id", "VARCHAR(36)", False, False),
        ("request_json", "TEXT", False, False),
        ("bundle_kwargs_json", "TEXT", False, False),
        ("state", "VARCHAR(16)", False, False),
        ("attempts", "INTEGER", False, False),
        ("last_error", "TEXT", True, False),
        ("created_at", "DATETIME", False, False),
        ("updated_at", "DATETIME", False, False),
    ],
    "slate_runs": [
        ("id", "VARCHAR(36)", False, True),
        ("created_at", "DATETIME", False, False),
        ("status", "VARCHAR(16)", False, False),
        ("request_json", "TEXT", False, False),
        ("candidates_json", "TEXT", False, False),
        ("match_runs_json", "TEXT", False, False),
        ("latency_ms", "INTEGER", True, False),
        ("discovery_latency_ms", "INTEGER", True, False),
        ("error_stage", "VARCHAR(64)", True, False),
        ("error_message", "TEXT", True, False),
        ("matches_attempted", "INTEGER", True, False),
        ("matches_succeeded", "INTEGER", True, False),
        ("prompt_tokens", "INTEGER", True, False),
        ("completion_tokens", "INTEGER", True, False),
        ("total_tokens", "INTEGER", True, False),
        ("operation_id", "VARCHAR(64)", True, False),
        ("outcome", "VARCHAR(16)", True, False),
        ("diagnostics_json", "TEXT", True, False),
        ("progress_stage", "VARCHAR(32)", True, False),
        ("matches_discovered", "INTEGER", True, False),
        ("matches_completed", "INTEGER", True, False),
        ("discovered_matches_json", "TEXT", False, False),
        ("heartbeat_at", "DATETIME", True, False),
        ("stop_reason", "VARCHAR(32)", True, False),
        ("interrupted_at", "DATETIME", True, False),
        ("resume_count", "INTEGER", False, False),
    ],
    "slate_jobs": [
        ("id", "VARCHAR(36)", False, True),
        ("slate_id", "VARCHAR(36)", False, False),
        ("request_json", "TEXT", False, False),
        ("state", "VARCHAR(16)", False, False),
        ("attempts", "INTEGER", False, False),
        ("last_error", "TEXT", True, False),
        ("created_at", "DATETIME", False, False),
        ("updated_at", "DATETIME", False, False),
        ("heartbeat_at", "DATETIME", True, False),
        ("lease_until", "DATETIME", True, False),
    ],
}


def test_orm_schema_matches_exact_specification() -> None:
    actual_tables = set(Base.metadata.tables.keys())
    expected_tables = set(EXPECTED_SCHEMA.keys())
    assert actual_tables == expected_tables

    for table_name, expected_cols in EXPECTED_SCHEMA.items():
        table = Base.metadata.tables[table_name]
        actual_cols = [
            (c.name, str(c.type), c.nullable, c.primary_key)
            for c in table.columns
        ]
        assert actual_cols == expected_cols, f"Mismatch in schema for {table_name}"
