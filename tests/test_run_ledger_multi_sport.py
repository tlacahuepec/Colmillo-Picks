"""Tests for multi-sport run ledger fields (issue #98)."""

from __future__ import annotations

import pytest

from run_ledger import InMemoryRunLedger, RunContext, SqliteRunLedger


class TestRunContextMultiSportFields:
    def test_run_context_stores_sport(self) -> None:
        ctx = RunContext(id="R1", sport="soccer")
        assert ctx.sport == "soccer"

    def test_run_context_stores_league(self) -> None:
        ctx = RunContext(id="R1", sport="basketball", league="NBA")
        assert ctx.league == "NBA"

    def test_run_context_stores_markets(self) -> None:
        ctx = RunContext(id="R1", sport="soccer", markets=("passes", "shots"))
        assert ctx.markets == ("passes", "shots")

    def test_run_context_stores_platform(self) -> None:
        ctx = RunContext(id="R1", sport="soccer", platform="prizepicks")
        assert ctx.platform == "prizepicks"

    def test_run_context_stores_provider_status(self) -> None:
        status = {"odds": "ok", "lineups": "unavailable"}
        ctx = RunContext(id="R1", sport="soccer", provider_status=status)
        assert ctx.provider_status == status

    def test_run_context_defaults_sport_to_empty(self) -> None:
        ctx = RunContext(id="R1")
        assert ctx.sport == ""

    def test_run_context_defaults_optional_fields_to_none(self) -> None:
        ctx = RunContext(id="R1")
        assert ctx.league is None
        assert ctx.markets == ()
        assert ctx.platform is None
        assert ctx.provider_status == {}


class TestInMemoryLedgerMultiSport:
    def test_start_run_stores_sport_and_league(self) -> None:
        ledger = InMemoryRunLedger()
        ctx = ledger.start_run(
            source="cli",
            request={
                "match_query": "Arsenal vs Liverpool",
                "sport": "soccer",
                "league": "Premier League",
                "markets": ["passes", "shots"],
                "platform": "prizepicks",
            },
        )
        assert ctx.sport == "soccer"
        assert ctx.league == "Premier League"
        assert ctx.markets == ("passes", "shots")
        assert ctx.platform == "prizepicks"

    def test_start_run_basketball(self) -> None:
        ledger = InMemoryRunLedger()
        ctx = ledger.start_run(
            source="api",
            request={
                "sport": "basketball",
                "league": "NBA",
                "markets": ["points", "assists"],
            },
        )
        assert ctx.sport == "basketball"
        assert ctx.league == "NBA"

    def test_list_runs_distinguishes_sports(self) -> None:
        ledger = InMemoryRunLedger()
        ledger.start_run(source="cli", request={"sport": "soccer"})
        ledger.start_run(source="cli", request={"sport": "basketball"})
        ledger.start_run(source="cli", request={"sport": "baseball"})
        runs = ledger.list_runs()
        sports = [r.sport for r in runs]
        assert "soccer" in sports
        assert "basketball" in sports
        assert "baseball" in sports

    def test_save_provider_status(self) -> None:
        ledger = InMemoryRunLedger()
        ctx = ledger.start_run(source="cli", request={"sport": "soccer"})
        updated = ledger.save_provider_status(
            ctx.id, {"odds": "ok", "lineups": "unavailable"}
        )
        assert updated.provider_status == {"odds": "ok", "lineups": "unavailable"}

    def test_get_run_has_provider_status(self) -> None:
        ledger = InMemoryRunLedger()
        ctx = ledger.start_run(source="cli", request={"sport": "soccer"})
        ledger.save_provider_status(ctx.id, {"odds": "ok"})
        fetched = ledger.get_run(ctx.id)
        assert fetched is not None
        assert fetched.provider_status == {"odds": "ok"}


class TestOldRunRecordsBackwardCompat:
    def test_minimal_run_record_still_readable(self) -> None:
        ctx = RunContext(id="OLD-1", source="cli", match_query="A vs B")
        assert ctx.sport == ""
        assert ctx.league is None
        assert ctx.markets == ()
        assert ctx.platform is None
        assert ctx.provider_status == {}

    def test_legacy_request_without_sport_defaults(self) -> None:
        ledger = InMemoryRunLedger()
        ctx = ledger.start_run(
            source="cli",
            request={"match_query": "Arsenal vs Liverpool"},
        )
        assert ctx.sport == ""
        assert ctx.league is None


class TestSqliteLedgerMultiSport:
    @pytest.fixture
    def db_path(self, tmp_path):
        return str(tmp_path / "test_runs.db")

    def test_sqlite_stores_sport_and_league(self, db_path) -> None:
        ledger = SqliteRunLedger(db_path=db_path)
        ctx = ledger.start_run(
            source="api",
            request={
                "sport": "soccer",
                "league": "La Liga",
                "markets": ["passes"],
                "platform": "prizepicks",
            },
        )
        fetched = ledger.get_run(ctx.id)
        assert fetched is not None
        assert fetched.sport == "soccer"
        assert fetched.league == "La Liga"
        assert fetched.markets == ("passes",)
        assert fetched.platform == "prizepicks"

    def test_sqlite_provider_status_persists(self, db_path) -> None:
        ledger = SqliteRunLedger(db_path=db_path)
        ctx = ledger.start_run(source="cli", request={"sport": "soccer"})
        ledger.save_provider_status(ctx.id, {"odds": "ok", "lineups": "failed"})
        fetched = ledger.get_run(ctx.id)
        assert fetched is not None
        assert fetched.provider_status == {"odds": "ok", "lineups": "failed"}

    def test_sqlite_old_records_without_sport_columns(self, db_path) -> None:
        ledger = SqliteRunLedger(db_path=db_path)
        ctx = ledger.start_run(
            source="cli", request={"match_query": "A vs B"}
        )
        fetched = ledger.get_run(ctx.id)
        assert fetched is not None
        assert fetched.sport == ""
        assert fetched.league is None

    def test_sqlite_list_runs_includes_sport(self, db_path) -> None:
        ledger = SqliteRunLedger(db_path=db_path)
        ledger.start_run(source="cli", request={"sport": "soccer"})
        ledger.start_run(source="cli", request={"sport": "basketball"})
        runs = ledger.list_runs()
        sports = {r.sport for r in runs}
        assert "soccer" in sports
        assert "basketball" in sports
