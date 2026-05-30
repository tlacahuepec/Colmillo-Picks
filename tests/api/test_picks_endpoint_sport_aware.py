"""Tests for sport-aware structured request support in POST /picks."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from pipeline_runner import PipelineRunError
from services.api import main as api_main
from services.api import db as db_module


_TEST_API_KEY = "test-api-key"


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch) -> None:
    db_module.configure_engine(f"sqlite:///{tmp_path / 'colmillo-test.db'}")
    monkeypatch.setenv("COLMILLO_RUNS_DB_PATH", str(tmp_path / "runs-ledger.db"))


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    monkeypatch.delenv("GROK_API_KEY", raising=False)
    monkeypatch.delenv("SOCCER_FIXTURE_LLM_API_KEY", raising=False)
    monkeypatch.delenv("COLMILLO_UI_ORIGIN", raising=False)
    monkeypatch.setenv("COLMILLO_API_KEY", _TEST_API_KEY)
    monkeypatch.setenv("COLMILLO_WORKER_MODE", "external")
    test_client = TestClient(api_main.create_app())
    test_client.headers.update({"X-API-Key": _TEST_API_KEY})
    return test_client


class TestStructuredPicksRequest:
    def test_structured_soccer_requires_real_provider_by_default(self, client: TestClient) -> None:
        resp = client.post("/picks", json={
            "sport": "soccer",
            "event_date": "2026-06-01",
            "home_team": "Arsenal",
            "away_team": "Liverpool",
            "markets": ["passes", "shots"],
            "top_n": 3,
        })

        assert resp.status_code == 400
        assert "No LLM fixture provider configured" in resp.json()["detail"]

    def test_structured_soccer_request_returns_202(self, client: TestClient) -> None:
        resp = client.post("/picks", json={
            "sport": "soccer",
            "event_date": "2026-06-01",
            "home_team": "Arsenal",
            "away_team": "Liverpool",
            "markets": ["passes", "shots"],
            "top_n": 3,
            "allow_deterministic_fallback": True,
        })
        assert resp.status_code == 202
        data = resp.json()
        assert "id" in data
        assert data["status"] == "pending"

    def test_sport_module_pipeline_error_persists_stage(
        self,
        client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        row = db_module.create_pending_pick_run(
            request_payload={
                "_sport_module_path": True,
                "sport": "baseball",
                "home_team": "CIN",
                "away_team": "ATL",
                "event_date": "2026-05-29",
                "markets": ["hits"],
                "top_n": 5,
                "league": "mlb",
            }
        )

        def fail_pipeline(_request_dict):
            raise PipelineRunError(
                stage="score",
                message="Could not find enough match details: missing prop lines.",
            )

        monkeypatch.setattr(api_main, "_run_sport_module_pipeline", fail_pipeline)

        api_main._execute_pipeline_job(
            pick_id=row.id,
            request_dict={
                "_sport_module_path": True,
                "sport": "baseball",
                "home_team": "CIN",
                "away_team": "ATL",
                "event_date": "2026-05-29",
                "markets": ["hits"],
                "top_n": 5,
                "league": "mlb",
            },
            bundle_kwargs={},
        )

        status = client.get(f"/picks/{row.id}/status").json()
        assert status["status"] == "failed"
        assert status["error_stage"] == "score"
        assert "Could not find enough match details" in status["error_message"]

    def test_pipeline_failure_persists_rich_observability_context(
        self,
        client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """When a sport module pipeline fails (e.g. collect due to missing provider data from
        ResolutionContext / provider_resolution), the persisted run and API responses must
        include rich observability context (critical_missing_fields, provider_status, notes).
        This is core to Epic #219 cross-sport observability for all sports.
        """
        row = db_module.create_pending_pick_run(
            request_payload={
                "_sport_module_path": True,
                "sport": "soccer",
                "home_team": "Arsenal",
                "away_team": "Liverpool",
                "event_date": "2026-06-01",
                "markets": ["passes", "shots"],
                "top_n": 3,
            }
        )

        rich_error_context = {
            "critical_missing_fields": ["market.sportsbook_snapshots", "players"],
            "provider_status": {
                "fixture": {"attempted": True, "success": True, "fallback_used": False, "error_summary": ""},
                "lineup": {"attempted": True, "success": False, "fallback_used": False, "error_summary": "No lineup data"},
                "odds": {"attempted": True, "success": False, "fallback_used": False, "error_summary": "Insufficient snapshots"},
                "weather": {"attempted": False, "success": False, "fallback_used": False, "error_summary": ""},
            },
            "notes": "Critical data missing from providers. No deterministic fallback allowed.",
            "should_reject_prediction": True,
        }

        def fail_with_rich_context(_request_dict):
            # Now PipelineRunError supports error_details for rich observability.
            raise PipelineRunError(
                stage="collect",
                message="Could not find enough match details: missing critical provider data.",
                error_details=rich_error_context,
            )

        monkeypatch.setattr(api_main, "_run_sport_module_pipeline", fail_with_rich_context)

        api_main._execute_pipeline_job(
            pick_id=row.id,
            request_dict={
                "_sport_module_path": True,
                "sport": "soccer",
                "home_team": "Arsenal",
                "away_team": "Liverpool",
                "event_date": "2026-06-01",
                "markets": ["passes", "shots"],
                "top_n": 3,
            },
            bundle_kwargs={},
        )

        status = client.get(f"/picks/{row.id}/status").json()
        assert status["status"] == "failed"
        assert status["error_stage"] == "collect"
        # These assertions will drive the full observability implementation (currently red)
        assert "error_details" in status
        assert status["error_details"]["critical_missing_fields"] == ["market.sportsbook_snapshots", "players"]
        assert "provider_status" in status["error_details"]
        assert status["error_details"]["should_reject_prediction"] is True

        # Full detail response must also surface the rich context
        detail = client.get(f"/picks/{row.id}").json()
        assert "error_details" in detail
        assert detail["error_details"]["notes"] == "Critical data missing from providers. No deterministic fallback allowed."

    def test_pipeline_failure_emits_structured_observability_logs(
        self,
        client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """On any pipeline failure, the system must emit structured logs (colmillo logger)
        containing sport, stage, critical_missing_fields, provider_status summaries, etc.
        This satisfies the 'every provider failure... is logged with ... details' requirement
        from Epic #219.
        """
        import logging
        row = db_module.create_pending_pick_run(
            request_payload={
                "_sport_module_path": True,
                "sport": "basketball",
                "home_team": "Lakers",
                "away_team": "Celtics",
                "event_date": "2026-06-01",
                "markets": ["points"],
                "top_n": 3,
            }
        )

        def fail_and_log(_request_dict):
            # Rich context now carried on the exception so the handler produces structured log
            rich_context = {
                "critical_missing_fields": ["player_stats", "prop_lines"],
                "provider_status": {"game": {"success": False}, "stats": {"success": False}},
                "error_summary": "All player stats providers failed",
            }
            raise PipelineRunError(
                stage="collect",
                message="Failed to collect basketball inputs.",
                error_details=rich_context,
            )

        monkeypatch.setattr(api_main, "_run_sport_module_pipeline", fail_and_log)

        with caplog.at_level(logging.WARNING, logger="colmillo"):
            api_main._execute_pipeline_job(
                pick_id=row.id,
                request_dict={
                    "_sport_module_path": True,
                    "sport": "basketball",
                    "home_team": "Lakers",
                    "away_team": "Celtics",
                    "event_date": "2026-06-01",
                    "markets": ["points"],
                    "top_n": 3,
                },
                bundle_kwargs={},
            )

        # The handler emits "pipeline_run_failed" with the rich error_details fields promoted via extra=
        # (filter uses multiple accessors for cross-env robustness with caplog + our JsonFormatter;
        # the semantic assertions below on the log content are preserved exactly as required)
        failed_logs = [
            r for r in caplog.records
            if getattr(r, "msg", "") == "pipeline_run_failed"
            or getattr(r, "message", "") == "pipeline_run_failed"
            or r.getMessage() == "pipeline_run_failed"
        ]
        assert failed_logs, "Expected structured 'pipeline_run_failed' log from error handler"
        log_record = failed_logs[0]
        # The JsonFormatter promotes extra keys; they should be directly on the record
        assert getattr(log_record, "critical_missing_fields", None) == ["player_stats", "prop_lines"]
        assert getattr(log_record, "sport", None) == "basketball"
        assert "player_stats" in str(getattr(log_record, "provider_status_summary", {})) or "provider_status_summary" in log_record.__dict__

    def test_basketball_failure_persists_rich_observability_context(
        self,
        client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Basketball (and by extension baseball) must follow the same rich observability contract
        as soccer on failure. Cross-sport consistency is mandatory for Epic #219.
        """
        row = db_module.create_pending_pick_run(
            request_payload={
                "_sport_module_path": True,
                "sport": "basketball",
                "home_team": "Lakers",
                "away_team": "Celtics",
                "event_date": "2026-06-01",
                "markets": ["points", "rebounds"],
                "top_n": 3,
            }
        )

        rich_basketball_context = {
            "critical_missing_fields": ["player_stats", "prop_lines"],
            "provider_status": {
                "game": {"attempted": True, "success": True, "fallback_used": False, "error_summary": ""},
                "stats": {"attempted": True, "success": False, "fallback_used": False, "error_summary": "Stats provider unavailable"},
                "props": {"attempted": True, "success": False, "fallback_used": False, "error_summary": "No lines returned"},
            },
            "notes": "Basketball data collection incomplete.",
        }

        def fail_basketball(_request_dict):
            raise PipelineRunError(
                stage="collect",
                message="Basketball collection failed: insufficient data.",
                error_details=rich_basketball_context,
            )

        monkeypatch.setattr(api_main, "_run_sport_module_pipeline", fail_basketball)

        api_main._execute_pipeline_job(
            pick_id=row.id,
            request_dict={
                "_sport_module_path": True,
                "sport": "basketball",
                "home_team": "Lakers",
                "away_team": "Celtics",
                "event_date": "2026-06-01",
                "markets": ["points", "rebounds"],
                "top_n": 3,
            },
            bundle_kwargs={},
        )

        status = client.get(f"/picks/{row.id}/status").json()
        assert status["status"] == "failed"
        assert "error_details" in status
        assert "player_stats" in status["error_details"]["critical_missing_fields"]
        assert status["error_details"]["provider_status"]["stats"]["success"] is False

    def test_baseball_failure_persists_rich_observability_context(
        self,
        client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Baseball must follow the same rich observability contract as soccer/basketball on failure.
        Cross-sport consistency for Epic #219.
        """
        row = db_module.create_pending_pick_run(
            request_payload={
                "_sport_module_path": True,
                "sport": "baseball",
                "home_team": "NYY",
                "away_team": "BOS",
                "event_date": "2026-06-01",
                "markets": ["hits", "home_runs"],
                "top_n": 3,
                "league": "mlb",
            }
        )

        rich_baseball_context = {
            "critical_missing_fields": ["pitcher_stats", "batter_lines"],
            "provider_status": {
                "game": {"attempted": True, "success": True, "fallback_used": False, "error_summary": ""},
                "stats": {"attempted": True, "success": False, "fallback_used": False, "error_summary": "MLB StatsAPI unavailable"},
                "lines": {"attempted": True, "success": False, "fallback_used": False, "error_summary": "No prop lines"},
            },
            "notes": "Baseball data collection incomplete for hitter markets.",
        }

        def fail_baseball(_request_dict):
            raise PipelineRunError(
                stage="collect",
                message="Baseball collection failed: insufficient data for requested markets.",
                error_details=rich_baseball_context,
            )

        monkeypatch.setattr(api_main, "_run_sport_module_pipeline", fail_baseball)

        api_main._execute_pipeline_job(
            pick_id=row.id,
            request_dict={
                "_sport_module_path": True,
                "sport": "baseball",
                "home_team": "NYY",
                "away_team": "BOS",
                "event_date": "2026-06-01",
                "markets": ["hits", "home_runs"],
                "top_n": 3,
                "league": "mlb",
            },
            bundle_kwargs={},
        )

        status = client.get(f"/picks/{row.id}/status").json()
        assert status["status"] == "failed"
        assert "error_details" in status
        assert "pitcher_stats" in status["error_details"]["critical_missing_fields"]
        assert status["error_details"]["provider_status"]["stats"]["success"] is False

    def test_invalid_sport_returns_400(self, client: TestClient) -> None:
        resp = client.post("/picks", json={
            "sport": "cricket",
            "event_date": "2026-06-01",
            "home_team": "Team A",
            "away_team": "Team B",
            "markets": ["runs"],
        })
        assert resp.status_code == 400
        assert "cricket" in resp.json()["detail"]

    def test_invalid_market_for_sport_returns_400(self, client: TestClient) -> None:
        resp = client.post("/picks", json={
            "sport": "basketball",
            "event_date": "2026-06-01",
            "home_team": "Lakers",
            "away_team": "Celtics",
            "markets": ["passes"],
        })
        assert resp.status_code == 400
        assert "passes" in resp.json()["detail"]

    def test_basketball_sport_returns_202_accepted(self, client: TestClient) -> None:
        resp = client.post("/picks", json={
            "sport": "basketball",
            "event_date": "2026-06-01",
            "home_team": "Lakers",
            "away_team": "Celtics",
            "markets": ["points", "rebounds"],
        })
        assert resp.status_code == 202
        data = resp.json()
        assert "id" in data
        assert data["status"] == "pending"


class TestLegacyPicksRequestRegression:
    def test_match_query_request_still_works(self, client: TestClient) -> None:
        resp = client.post("/picks", json={
            "match_query": "arsenal - liverpool 2026-06-01",
            "top_n": 3,
            "allow_deterministic_fallback": True,
        })
        assert resp.status_code == 202
        data = resp.json()
        assert "id" in data
        assert data["status"] == "pending"
