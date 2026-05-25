"""Tests for MLB observability: structured logging, run_id correlation, lifecycle events."""

from __future__ import annotations

import logging
import uuid

from baseball_logging import (
    MLBRunContext,
    get_current_run_id,
    log_collection_start,
    log_collection_end,
    log_provider_status,
    log_scoring_start,
    log_scoring_end,
    log_explanation_start,
    log_explanation_end,
    log_render_start,
    log_render_end,
    set_run_context,
    clear_run_context,
)


class TestRunIdContext:
    def test_set_and_get_run_id(self):
        run_id = uuid.uuid4().hex
        ctx = MLBRunContext(run_id=run_id, sport="baseball", league="mlb")
        token = set_run_context(ctx)
        try:
            assert get_current_run_id() == run_id
        finally:
            clear_run_context(token)

    def test_get_run_id_returns_none_when_unset(self):
        assert get_current_run_id() is None

    def test_clear_run_context_resets(self):
        run_id = uuid.uuid4().hex
        ctx = MLBRunContext(run_id=run_id, sport="baseball", league="mlb")
        token = set_run_context(ctx)
        clear_run_context(token)
        assert get_current_run_id() is None


class TestLifecycleLogging:
    def test_collection_start_logged(self, caplog):
        run_id = uuid.uuid4().hex
        ctx = MLBRunContext(run_id=run_id, sport="baseball", league="mlb")
        token = set_run_context(ctx)
        try:
            with caplog.at_level(logging.INFO, logger="colmillo.mlb"):
                log_collection_start(home_team="NYY", away_team="BOS")
            assert any("collection_start" in r.message for r in caplog.records)
            record = next(r for r in caplog.records if "collection_start" in r.message)
            assert record.run_id == run_id
            assert record.home_team == "NYY"
            assert record.away_team == "BOS"
        finally:
            clear_run_context(token)

    def test_collection_end_logged_with_provider_count(self, caplog):
        run_id = uuid.uuid4().hex
        ctx = MLBRunContext(run_id=run_id, sport="baseball", league="mlb")
        token = set_run_context(ctx)
        try:
            with caplog.at_level(logging.INFO, logger="colmillo.mlb"):
                log_collection_end(providers_ok=3, providers_failed=1, cached=2)
            record = next(r for r in caplog.records if "collection_end" in r.message)
            assert record.run_id == run_id
            assert record.providers_ok == 3
            assert record.providers_failed == 1
            assert record.cached == 2
        finally:
            clear_run_context(token)

    def test_provider_status_logged(self, caplog):
        run_id = uuid.uuid4().hex
        ctx = MLBRunContext(run_id=run_id, sport="baseball", league="mlb")
        token = set_run_context(ctx)
        try:
            with caplog.at_level(logging.INFO, logger="colmillo.mlb"):
                log_provider_status(
                    provider="stats_api", status="ok", cached=True, latency_ms=42
                )
            record = next(r for r in caplog.records if "provider_status" in r.message)
            assert record.provider == "stats_api"
            assert record.status == "ok"
            assert record.cached is True
            assert record.latency_ms == 42
        finally:
            clear_run_context(token)

    def test_scoring_start_logged(self, caplog):
        run_id = uuid.uuid4().hex
        ctx = MLBRunContext(run_id=run_id, sport="baseball", league="mlb")
        token = set_run_context(ctx)
        try:
            with caplog.at_level(logging.INFO, logger="colmillo.mlb"):
                log_scoring_start(scorer_version="1.0", config_hash="abc123")
            record = next(r for r in caplog.records if "scoring_start" in r.message)
            assert record.scorer_version == "1.0"
            assert record.config_hash == "abc123"
        finally:
            clear_run_context(token)

    def test_scoring_end_logged_with_pick_count(self, caplog):
        run_id = uuid.uuid4().hex
        ctx = MLBRunContext(run_id=run_id, sport="baseball", league="mlb")
        token = set_run_context(ctx)
        try:
            with caplog.at_level(logging.INFO, logger="colmillo.mlb"):
                log_scoring_end(picks_generated=5, no_bet_count=2)
            record = next(r for r in caplog.records if "scoring_end" in r.message)
            assert record.picks_generated == 5
            assert record.no_bet_count == 2
        finally:
            clear_run_context(token)

    def test_explanation_start_logged(self, caplog):
        run_id = uuid.uuid4().hex
        ctx = MLBRunContext(run_id=run_id, sport="baseball", league="mlb")
        token = set_run_context(ctx)
        try:
            with caplog.at_level(logging.INFO, logger="colmillo.mlb"):
                log_explanation_start(mode="deterministic")
            record = next(r for r in caplog.records if "explanation_start" in r.message)
            assert record.mode == "deterministic"
        finally:
            clear_run_context(token)

    def test_explanation_end_logged(self, caplog):
        run_id = uuid.uuid4().hex
        ctx = MLBRunContext(run_id=run_id, sport="baseball", league="mlb")
        token = set_run_context(ctx)
        try:
            with caplog.at_level(logging.INFO, logger="colmillo.mlb"):
                log_explanation_end(success=True, fallback_used=False)
            record = next(r for r in caplog.records if "explanation_end" in r.message)
            assert record.success is True
            assert record.fallback_used is False
        finally:
            clear_run_context(token)

    def test_render_start_logged(self, caplog):
        run_id = uuid.uuid4().hex
        ctx = MLBRunContext(run_id=run_id, sport="baseball", league="mlb")
        token = set_run_context(ctx)
        try:
            with caplog.at_level(logging.INFO, logger="colmillo.mlb"):
                log_render_start()
            record = next(r for r in caplog.records if "render_start" in r.message)
            assert record.run_id == run_id
        finally:
            clear_run_context(token)

    def test_render_end_logged(self, caplog):
        run_id = uuid.uuid4().hex
        ctx = MLBRunContext(run_id=run_id, sport="baseball", league="mlb")
        token = set_run_context(ctx)
        try:
            with caplog.at_level(logging.INFO, logger="colmillo.mlb"):
                log_render_end(sections_rendered=6)
            record = next(r for r in caplog.records if "render_end" in r.message)
            assert record.sections_rendered == 6
        finally:
            clear_run_context(token)


class TestRunIdCorrelation:
    def test_all_lifecycle_logs_share_run_id(self, caplog):
        run_id = uuid.uuid4().hex
        ctx = MLBRunContext(run_id=run_id, sport="baseball", league="mlb")
        token = set_run_context(ctx)
        try:
            with caplog.at_level(logging.INFO, logger="colmillo.mlb"):
                log_collection_start(home_team="NYY", away_team="BOS")
                log_provider_status(provider="stats", status="ok", cached=False, latency_ms=100)
                log_collection_end(providers_ok=1, providers_failed=0, cached=0)
                log_scoring_start(scorer_version="1.0", config_hash="h")
                log_scoring_end(picks_generated=3, no_bet_count=0)
                log_explanation_start(mode="deterministic")
                log_explanation_end(success=True, fallback_used=False)
                log_render_start()
                log_render_end(sections_rendered=6)

            for record in caplog.records:
                assert record.run_id == run_id, f"Record '{record.message}' missing run_id"
        finally:
            clear_run_context(token)


class TestLogLevels:
    def test_lifecycle_events_are_info(self, caplog):
        run_id = uuid.uuid4().hex
        ctx = MLBRunContext(run_id=run_id, sport="baseball", league="mlb")
        token = set_run_context(ctx)
        try:
            with caplog.at_level(logging.DEBUG, logger="colmillo.mlb"):
                log_collection_start(home_team="NYY", away_team="BOS")
                log_scoring_start(scorer_version="1.0", config_hash="h")
            for record in caplog.records:
                assert record.levelno == logging.INFO
        finally:
            clear_run_context(token)
