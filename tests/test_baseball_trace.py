"""Tests for MLB trace schema and explanation service."""

from __future__ import annotations

import json

from baseball_trace import (
    MLBTraceRecord,
    PickTrace,
    ProviderStatusEntry,
    compute_config_hash,
    compute_input_hash,
    compute_prompt_hash,
)


class TestTraceSchema:
    def test_trace_record_has_required_fields(self):
        record = MLBTraceRecord(run_id="run-001")
        assert record.trace_id
        assert record.run_id == "run-001"
        assert record.sport == "baseball"
        assert record.league == "mlb"
        assert record.no_guarantee_flag is True
        assert record.created_at_utc

    def test_trace_record_defaults(self):
        record = MLBTraceRecord()
        assert record.scorer_version == "1.0.0"
        assert record.llm_model == "none"
        assert record.llm_provider == "none"
        assert record.explanation_status == "not_requested"
        assert record.picks == []
        assert record.provider_statuses == []

    def test_provider_status_entry(self):
        entry = ProviderStatusEntry(
            provider="statsapi",
            status="ok",
            source="mlb_statsapi",
            cached=True,
            retrieved_at_utc="2026-05-25T10:00:00Z",
        )
        assert entry.provider == "statsapi"
        assert entry.cached is True

    def test_pick_trace_structure(self):
        pick = PickTrace(
            player="Aaron Judge",
            market="home_runs",
            direction="over",
            line=0.5,
            score=0.82,
            confidence="high",
            risk_flags=[],
            top_factors=[{"factor": "ballpark_factor", "score": 0.9, "weight": 0.2}],
            explanation="Judge has favorable ballpark conditions.",
        )
        assert pick.player == "Aaron Judge"
        assert pick.no_bet is False

    def test_pick_trace_no_bet(self):
        pick = PickTrace(
            player="Test Player",
            market="hits",
            direction="over",
            line=1.5,
            score=0.3,
            confidence="low",
            no_bet=True,
            no_bet_reason="missing_probable_pitcher",
        )
        assert pick.no_bet is True
        assert pick.no_bet_reason == "missing_probable_pitcher"

    def test_trace_record_serializes_to_json(self):
        record = MLBTraceRecord(
            run_id="run-test",
            picks=[
                PickTrace(
                    player="Judge",
                    market="hits",
                    direction="over",
                    line=1.5,
                    score=0.75,
                    confidence="medium",
                )
            ],
        )
        data = json.loads(record.model_dump_json())
        assert data["sport"] == "baseball"
        assert len(data["picks"]) == 1
        assert data["picks"][0]["player"] == "Judge"
        assert data["no_guarantee_flag"] is True

    def test_compute_input_hash_deterministic(self):
        payload = {"players": [{"name": "Judge"}], "market": "hits"}
        h1 = compute_input_hash(payload)
        h2 = compute_input_hash(payload)
        assert h1 == h2
        assert len(h1) == 16

    def test_compute_input_hash_changes_on_different_input(self):
        h1 = compute_input_hash({"a": 1})
        h2 = compute_input_hash({"a": 2})
        assert h1 != h2

    def test_compute_config_hash(self, tmp_path):
        config_file = tmp_path / "config.json"
        config_file.write_text('{"hits": {"factor_weights": {}}}')
        h = compute_config_hash(str(config_file))
        assert len(h) == 16

    def test_compute_prompt_hash(self):
        h = compute_prompt_hash("system prompt", "user prompt")
        assert len(h) == 16
        h2 = compute_prompt_hash("different", "prompts")
        assert h != h2
