from copy import deepcopy
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from nfl_module import NflModule, NflNoPicks
from services.api import db, main
from services.api.slate_orchestration import SlateOrchestrationDeps, execute_slate_job
from services.ui.best_today_helpers import build_availability_batch_payload
from tests.test_nfl import context, offer


@pytest.fixture
def nfl_client(tmp_path, monkeypatch):
    db.configure_engine(f"sqlite:///{tmp_path / 'nfl.db'}")
    monkeypatch.setenv("COLMILLO_RUNS_DB_PATH", str(tmp_path / "ledger.db"))
    monkeypatch.setenv("COLMILLO_API_KEY", "nfl-test-key")
    monkeypatch.delenv("COLMILLO_WORKER_MODE", raising=False)
    data = context()
    now = datetime.now(timezone.utc)
    data["game"]["kickoff_utc"] = (now + timedelta(days=1)).isoformat()
    data["offers"] = [
        offer("moneyline", observed_at=now.isoformat()),
        offer("spread", observed_at=now.isoformat()),
    ]
    module = NflModule(collector=lambda **kwargs: deepcopy(data))
    monkeypatch.setattr("sport_module.get_sport_module", lambda sport: module)
    client = TestClient(main.create_app())
    client.headers.update({"X-API-Key": "nfl-test-key"})
    return client


def test_nfl_request_report_history_and_manual_grading(nfl_client):
    response = nfl_client.post(
        "/picks",
        json={
            "sport": "nfl",
            "league": "nfl",
            "event_date": "2026-09-10",
            "home_team": "KC",
            "away_team": "BUF",
            "markets": ["moneyline", "spread"],
        },
    )
    assert response.status_code == 202
    ident = response.json()["id"]
    detail = nfl_client.get(f"/picks/{ident}").json()
    assert detail["status"] == "success"
    assert len(detail["scores"]) == 2
    assert {p["line"] for p in detail["scores"]} == {None, 0}
    assert all(p["subject_type"] == "team" for p in detail["scores"])
    assert (
        "Test Book" in detail["report_markdown"] and "NFL" in detail["report_markdown"]
    )
    assert nfl_client.get("/picks?sport=nfl").json()["items"][0]["sport"] == "nfl"
    outcome = {
        "rank": 1,
        "player": detail["scores"][0]["subject_name"],
        "market": detail["scores"][0]["market"],
        "result": "win",
    }
    assert (
        nfl_client.post(
            f"/picks/{ident}/outcomes", json={"outcomes": [outcome]}
        ).status_code
        == 201
    )
    assert (
        nfl_client.get(f"/picks/{ident}/outcomes").json()["items"][0]["player"]
        == "Kansas City Chiefs"
    )
    assert (
        nfl_client.post(f"/picks/{ident}/availability", json={}).json()["badges"] == []
    )
    runs = nfl_client.get("/runs").json()["items"]
    run = nfl_client.get(f"/runs/{runs[0]['id']}").json()
    assert run["status"] == "success"
    assert run["picks"][0]["line"] is None
    assert run["picks"][0]["source_pick"]["offer"]["sportsbook"] == "Test Book"


@pytest.mark.parametrize("kind", ["memory", "sqlite"])
def test_ledger_round_trips_null_line_and_evidence(kind, tmp_path):
    from run_ledger import InMemoryRunLedger, SqliteRunLedger

    ledger = (
        InMemoryRunLedger()
        if kind == "memory"
        else SqliteRunLedger(str(tmp_path / "runs.db"))
    )
    run = ledger.start_run(source="api", request={"sport": "nfl"})
    pick = {
        "sport": "nfl",
        "player": "KC",
        "subject_type": "team",
        "subject_name": "Kansas City Chiefs",
        "market": "moneyline",
        "line": None,
        "score": 0.7,
        "offer": offer("moneyline"),
    }
    ledger.save_picks(run.id, [pick])
    saved = ledger.get_picks(run.id)[0]
    assert saved.line is None
    assert saved.source_pick == pick


def test_mixed_slate_keeps_subjects_and_partial_no_picks():
    def run(**kwargs):
        if kwargs["home_team"] == "empty":
            raise NflNoPicks("No verified sportsbook offers.")
        return [
            {
                "sport": kwargs["sport"],
                "player": "KC",
                "subject_type": "team",
                "subject_name": "Kansas City Chiefs",
                "market": "moneyline",
                "line": None,
                "selection": "home",
                "direction": "home",
                "score": 0.7,
                "offer": offer("moneyline"),
            }
        ]

    result = execute_slate_job(
        request_dict={"date": "2026-09-10", "sports": ["nfl", "soccer"]},
        deps=SlateOrchestrationDeps(
            discover_matches=lambda **kwargs: {
                "results": {
                    "nfl": {
                        "matches": [
                            {"home_team": "KC", "away_team": "BUF"},
                            {"home_team": "empty"},
                        ]
                    },
                    "soccer": {"matches": []},
                }
            },
            run_match_pipeline=run,
        ),
    )
    assert len(result.candidates) == 1
    assert result.candidates[0].subject_type == "team"
    assert result.match_runs[1]["status"] == "no_picks"


def test_nfl_never_gets_mock_platform_availability():
    picks = [
        {
            "sport": "nfl",
            "subject_type": "player",
            "player": "QB",
            "market": "passing_yards",
            "line": 250.5,
        },
        {
            "sport": "nfl",
            "subject_type": "team",
            "player": "KC",
            "market": "spread",
            "line": 0,
        },
        {
            "sport": "nfl",
            "subject_type": "player",
            "player": "RB",
            "market": "anytime_touchdown",
            "line": None,
        },
    ]
    batch = build_availability_batch_payload(picks)
    assert len(batch) == 1 and batch[0]["sport"] == "nfl"
    badges = main._check_availability_for_picks(batch, ["prizepicks"])
    assert len(badges) == 1 and badges[0].status == "unknown"


def test_worker_skips_nfl_without_reading_null_lines(monkeypatch):
    from services.worker import main as worker

    row = SimpleNamespace(sport="nfl", scores_json='[{"line": null}]')
    worker._attempt_resolution(row)
    monkeypatch.setattr(db, "list_unresolved_picks", lambda **kwargs: [row])
    monkeypatch.setattr(
        worker, "_attempt_resolution", lambda row: pytest.fail("NFL must be manual")
    )
    assert worker.run_resolution_cycle() == 0


def test_slate_api_round_trips_nfl_offer_and_subject(nfl_client, monkeypatch):
    from nfl_scoring import score_nfl
    from tests.test_nfl import NOW

    data = context()
    data["offers"] = [offer("moneyline")]
    monkeypatch.setattr(
        main,
        "_build_slate_deps",
        lambda request: SlateOrchestrationDeps(
            discover_matches=lambda **kwargs: {
                "results": {
                    "nfl": {
                        "matches": [
                            {
                                "home_team": "Kansas City Chiefs",
                                "away_team": "Buffalo Bills",
                                "event_date": "2026-09-10",
                            }
                        ]
                    }
                }
            },
            run_match_pipeline=lambda **kwargs: score_nfl(deepcopy(data), now=NOW),
        ),
    )
    response = nfl_client.post(
        "/slates",
        json={"date": "2026-09-10", "sports": ["nfl"], "nfl_market_group": "game_bets"},
    )
    assert response.status_code == 202
    detail = nfl_client.get(f"/slates/{response.json()['id']}").json()
    candidate = detail["candidates"][0]
    assert candidate["subject_type"] == "team" and candidate["line"] is None
    assert candidate["offer"]["sportsbook"] == "Test Book"
    assert candidate["selection"] == "home"


def test_existing_run_ledger_rows_survive_json_column_migration(tmp_path):
    import sqlite3
    from run_ledger.sqlite_ledger import SqliteRunLedger, _CREATE_PICKS_TABLE_SQL

    path = tmp_path / "legacy.db"
    with sqlite3.connect(path) as connection:
        connection.execute(_CREATE_PICKS_TABLE_SQL)
        connection.execute(
            "INSERT INTO run_picks(run_id, rank, player, market, line) VALUES ('legacy', 1, 'Player', 'shots', 2.5)"
        )
    for _ in range(2):
        ledger = SqliteRunLedger(str(path))
        pick = ledger.get_picks("legacy")[0]
        assert pick.line == 2.5 and pick.source_pick == {}
