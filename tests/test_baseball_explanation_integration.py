"""Integration test: MLB scoring → explanation → trace pipeline."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from baseball_scoring import score_baseball_props
from baseball_explainer import (
    explain_picks,
    BANNED_GUARANTEE_WORDS,
)
from baseball_trace import (
    MLBTraceRecord,
    PickTrace,
    ProviderStatusEntry,
    compute_input_hash,
)


def _test_players() -> list[dict[str, Any]]:
    return [
        {
            "player_name": "Aaron Judge",
            "player_type": "batter",
            "team": "NYY",
            "batting_order": 2,
            "handedness": "R",
            "opposing_pitcher_hand": "L",
            "hits_per_game": 1.4,
            "hits_last5_per_game": 1.8,
            "tb_per_game": 2.5,
            "tb_last5_per_game": 3.2,
            "hr_per_game": 0.35,
            "hr_last5_per_game": 0.6,
            "runs_per_game": 0.9,
            "runs_last5_per_game": 1.2,
            "rbi_per_game": 1.2,
            "rbi_last5_per_game": 1.6,
            "bb_per_game": 0.8,
            "bb_last5_per_game": 0.6,
            "k_per_game": 1.8,
            "k_last5_per_game": 1.4,
            "park_factor": 0.55,
            "hr_factor": 0.6,
            "temp_f": 82,
            "wind_direction": "out to center",
            "team_implied_total": 5.2,
            "home_away": "home",
            "opp_k_rate": 0.22,
            "market_agreement": 0.7,
            "line_hits": 1.5,
            "line_home_runs": 0.5,
            "line_total_bases": 2.5,
        },
    ]


class TestEndToEndPipeline:
    def test_scoring_to_explanation_to_trace(self):
        players = _test_players()
        scored = score_baseball_props(players, markets=("hits", "home_runs"))
        assert len(scored) > 0

        input_context = {
            "players": ["Aaron Judge"],
            "stats": {"Aaron Judge": {"hr_per_game": 0.35}},
            "weather": {"temp_f": 82},
            "ballpark": "Yankee Stadium",
        }

        explained = explain_picks(
            picks=scored,
            input_context=input_context,
            use_llm=False,
        )
        assert len(explained) == len(scored)

        trace = MLBTraceRecord(
            run_id="integration-test-001",
            input_hash=compute_input_hash({"players": players}),
            provider_statuses=[
                ProviderStatusEntry(provider="statsapi", status="ok", cached=False),
            ],
            picks=[
                PickTrace(
                    player=e["player"],
                    market=e["market"],
                    direction=scored[i].get("direction", "over"),
                    line=scored[i].get("line", 0),
                    score=scored[i].get("score", 0),
                    confidence=scored[i].get("confidence", "medium"),
                    risk_flags=scored[i].get("explainability", {}).get("risk_flags", []),
                    top_factors=scored[i].get("explainability", {}).get("top_contributing_factors", []),
                    explanation=e["explanation"],
                )
                for i, e in enumerate(explained)
            ],
        )

        assert trace.sport == "baseball"
        assert trace.league == "mlb"
        assert trace.no_guarantee_flag is True
        assert len(trace.picks) > 0
        for pick in trace.picks:
            assert pick.explanation
            assert pick.player == "Aaron Judge"

    def test_trace_serialization_roundtrip(self):
        players = _test_players()
        scored = score_baseball_props(players, markets=("hits",))
        explained = explain_picks(
            picks=scored,
            input_context={"players": ["Aaron Judge"], "stats": {}},
            use_llm=False,
        )

        trace = MLBTraceRecord(
            run_id="roundtrip-test",
            picks=[
                PickTrace(
                    player=explained[0]["player"],
                    market=explained[0]["market"],
                    direction=scored[0]["direction"],
                    line=scored[0]["line"],
                    score=scored[0]["score"],
                    confidence=scored[0]["confidence"],
                    explanation=explained[0]["explanation"],
                )
            ],
        )

        json_str = trace.model_dump_json()
        restored = MLBTraceRecord.model_validate_json(json_str)
        assert restored.run_id == "roundtrip-test"
        assert restored.picks[0].player == "Aaron Judge"
        assert restored.no_guarantee_flag is True

    def test_no_banned_words_in_any_explanation(self):
        players = _test_players()
        scored = score_baseball_props(players)
        explained = explain_picks(
            picks=scored,
            input_context={"players": ["Aaron Judge"], "stats": {}},
            use_llm=False,
        )

        for item in explained:
            explanation_lower = item["explanation"].lower()
            for word in BANNED_GUARANTEE_WORDS:
                assert word not in explanation_lower

    def test_llm_fallback_produces_valid_trace(self):
        players = _test_players()
        scored = score_baseball_props(players, markets=("hits",))

        mock_client = MagicMock()
        mock_client.generate_structured.side_effect = RuntimeError("service down")

        explained = explain_picks(
            picks=scored,
            input_context={"players": ["Aaron Judge"], "stats": {}},
            use_llm=True,
            llm_client=mock_client,
        )

        assert all(e["explanation_status"] == "deterministic_fallback" for e in explained)
        assert all(e["explanation"] for e in explained)

    def test_no_bet_picks_preserved_through_pipeline(self):
        players = _test_players()
        scored = score_baseball_props(players, markets=("hits",))

        explained = explain_picks(
            picks=scored,
            input_context={"players": ["Aaron Judge"], "stats": {}},
            use_llm=False,
            no_bet_picks={"Aaron Judge:hits"},
        )

        trace = MLBTraceRecord(
            run_id="no-bet-test",
            picks=[
                PickTrace(
                    player=e["player"],
                    market=e["market"],
                    direction=scored[i]["direction"],
                    line=scored[i]["line"],
                    score=scored[i]["score"],
                    confidence=scored[i]["confidence"],
                    explanation=e["explanation"],
                    no_bet=e["no_bet"],
                    no_bet_reason="scorer_designation" if e["no_bet"] else None,
                )
                for i, e in enumerate(explained)
            ],
        )

        no_bet_picks = [p for p in trace.picks if p.no_bet]
        assert len(no_bet_picks) == 1
        assert no_bet_picks[0].player == "Aaron Judge"
        assert no_bet_picks[0].market == "hits"
