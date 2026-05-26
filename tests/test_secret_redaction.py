"""Tests for secret redaction: API keys never appear in logs, DB, traces, or reports."""

from __future__ import annotations

import json
import logging
import re
import uuid

import pytest

from baseball_logging import (
    MLBRunContext,
    SecretRedactionFilter,
    set_run_context,
    clear_run_context,
    log_collection_start,
    log_provider_status,
)


_FAKE_GEMINI_KEY = "AIzaSyD-FAKE-GEMINI-KEY-1234567890ab"
_FAKE_COLMILLO_KEY = "colmillo-secret-key-xyz789"
_API_KEY_PATTERN = re.compile(
    r"(AIzaSy[A-Za-z0-9_-]{33}|colmillo-secret-key-[a-z0-9]+)", re.IGNORECASE
)


class TestSecretRedactionFilter:
    def test_filter_redacts_known_api_key_from_message(self):
        filt = SecretRedactionFilter(secrets=[_FAKE_GEMINI_KEY, _FAKE_COLMILLO_KEY])
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg=f"Calling provider with key={_FAKE_GEMINI_KEY}",
            args=None, exc_info=None,
        )
        filt.filter(record)
        assert _FAKE_GEMINI_KEY not in record.getMessage()
        assert "[REDACTED]" in record.getMessage()

    def test_filter_redacts_multiple_secrets(self):
        filt = SecretRedactionFilter(secrets=[_FAKE_GEMINI_KEY, _FAKE_COLMILLO_KEY])
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg=f"keys: {_FAKE_GEMINI_KEY} and {_FAKE_COLMILLO_KEY}",
            args=None, exc_info=None,
        )
        filt.filter(record)
        msg = record.getMessage()
        assert _FAKE_GEMINI_KEY not in msg
        assert _FAKE_COLMILLO_KEY not in msg

    def test_filter_does_not_modify_safe_messages(self):
        filt = SecretRedactionFilter(secrets=[_FAKE_GEMINI_KEY])
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="Normal log message without secrets",
            args=None, exc_info=None,
        )
        filt.filter(record)
        assert record.getMessage() == "Normal log message without secrets"

    def test_filter_redacts_secrets_in_extra_fields(self):
        filt = SecretRedactionFilter(secrets=[_FAKE_GEMINI_KEY])
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="provider call",
            args=None, exc_info=None,
        )
        record.api_key = _FAKE_GEMINI_KEY
        filt.filter(record)
        assert record.api_key == "[REDACTED]"


class TestSecretsNeverInLogs:
    @pytest.fixture(autouse=True)
    def _set_env_keys(self, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", _FAKE_GEMINI_KEY)
        monkeypatch.setenv("COLMILLO_API_KEY", _FAKE_COLMILLO_KEY)

    def test_api_key_never_in_lifecycle_logs(self, caplog, monkeypatch):
        filt = SecretRedactionFilter.from_env()
        logger = logging.getLogger("colmillo.mlb")
        logger.addFilter(filt)
        try:
            run_id = uuid.uuid4().hex
            ctx = MLBRunContext(run_id=run_id, sport="baseball", league="mlb")
            token = set_run_context(ctx)
            try:
                with caplog.at_level(logging.DEBUG, logger="colmillo.mlb"):
                    log_collection_start(home_team="NYY", away_team="BOS")
                    log_provider_status(
                        provider="gemini",
                        status="ok",
                        cached=False,
                        latency_ms=200,
                    )
                for record in caplog.records:
                    full_text = record.getMessage()
                    assert _FAKE_GEMINI_KEY not in full_text
                    assert _FAKE_COLMILLO_KEY not in full_text
            finally:
                clear_run_context(token)
        finally:
            logger.removeFilter(filt)


class TestSecretsNeverInTraceJson:
    def test_trace_json_does_not_contain_api_keys(self):
        from baseball_trace import MLBTraceRecord

        trace = MLBTraceRecord(
            trace_id=uuid.uuid4().hex,
            run_id=uuid.uuid4().hex,
            sport="baseball",
            league="mlb",
            provider_statuses=[],
            input_hash="abc",
            scorer_version="1.0",
            scorer_config_hash="def",
            explanation="Player is hot",
            risk_flags=[],
            no_guarantee_flag=True,
        )
        trace_json = trace.model_dump_json()
        assert _FAKE_GEMINI_KEY not in trace_json
        assert _FAKE_COLMILLO_KEY not in trace_json
        assert "api_key" not in trace_json.lower()

    def test_trace_json_fields_do_not_leak_secrets(self):
        from baseball_trace import MLBTraceRecord

        trace = MLBTraceRecord(
            trace_id=uuid.uuid4().hex,
            run_id=uuid.uuid4().hex,
            sport="baseball",
            league="mlb",
            provider_statuses=[
                {"provider": "stats_api", "status": "ok", "cached": True}
            ],
            input_hash="hash123",
            scorer_version="1.0",
            scorer_config_hash="cfghash",
            explanation=f"This should not have {_FAKE_GEMINI_KEY}",
            risk_flags=[],
            no_guarantee_flag=True,
        )
        trace_dict = trace.model_dump()
        serialized = json.dumps(trace_dict, default=str)
        for key_pattern in [_FAKE_GEMINI_KEY, _FAKE_COLMILLO_KEY, "COLMILLO_API_KEY", "GEMINI_API_KEY"]:
            if key_pattern in serialized:
                pytest.fail(f"Secret pattern '{key_pattern[:10]}...' found in trace JSON")


class TestSecretsNeverInReportMarkdown:
    def test_report_does_not_contain_api_keys(self, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", _FAKE_GEMINI_KEY)
        monkeypatch.setenv("COLMILLO_API_KEY", _FAKE_COLMILLO_KEY)

        from render_baseball_report import render_baseball_report

        report = render_baseball_report(
            match_context={"home_team": "NYY", "away_team": "BOS", "date": "2026-05-25"},
            picks=[
                {
                    "player": "Aaron Judge",
                    "market": "hits",
                    "direction": "over",
                    "line": 1.5,
                    "score": 0.72,
                    "explanation": "Hot streak",
                }
            ],
        )
        assert _FAKE_GEMINI_KEY not in report
        assert _FAKE_COLMILLO_KEY not in report
        assert "api_key" not in report.lower()


class TestSecretsNeverInErrorResponses:
    def test_provider_error_message_is_safe(self):
        from baseball_logging import safe_error_message

        raw_error = f"Connection to API failed: key={_FAKE_GEMINI_KEY} endpoint=https://api.example.com"
        safe_msg = safe_error_message(raw_error, secrets=[_FAKE_GEMINI_KEY])
        assert _FAKE_GEMINI_KEY not in safe_msg
        assert "[REDACTED]" in safe_msg
