"""Tests for basketball core prop scoring."""

from __future__ import annotations

from basketball_scoring import score_basketball_props


class TestPointsScoring:
    def test_points_increases_with_minutes(self) -> None:
        base = _player_input(minutes_proj=30, usage_rate=0.25)
        high_min = _player_input(minutes_proj=38, usage_rate=0.25)
        base_scores = score_basketball_props([base], markets=("points",))
        high_scores = score_basketball_props([high_min], markets=("points",))
        assert high_scores[0]["score"] > base_scores[0]["score"]

    def test_points_increases_with_usage(self) -> None:
        low_usage = _player_input(minutes_proj=34, usage_rate=0.20)
        high_usage = _player_input(minutes_proj=34, usage_rate=0.32)
        low_scores = score_basketball_props([low_usage], markets=("points",))
        high_scores = score_basketball_props([high_usage], markets=("points",))
        assert high_scores[0]["score"] > low_scores[0]["score"]


class TestAssistsScoring:
    def test_assists_reacts_to_role(self) -> None:
        guard = _player_input(position="PG", assist_avg=6.0)
        forward = _player_input(position="SF", assist_avg=6.0)
        guard_scores = score_basketball_props([guard], markets=("assists",))
        forward_scores = score_basketball_props([forward], markets=("assists",))
        assert guard_scores[0]["score"] > forward_scores[0]["score"]

    def test_assists_reacts_to_recent_trend(self) -> None:
        trending_up = _player_input(assist_avg=6.0, assist_last5=8.5)
        trending_down = _player_input(assist_avg=6.0, assist_last5=4.0)
        up_scores = score_basketball_props([trending_up], markets=("assists",))
        down_scores = score_basketball_props([trending_down], markets=("assists",))
        assert up_scores[0]["score"] > down_scores[0]["score"]


class TestReboundsScoring:
    def test_rebounds_reacts_to_minutes(self) -> None:
        low_min = _player_input(minutes_proj=24, rebound_avg=8.0)
        high_min = _player_input(minutes_proj=36, rebound_avg=8.0)
        low_scores = score_basketball_props([low_min], markets=("rebounds",))
        high_scores = score_basketball_props([high_min], markets=("rebounds",))
        assert high_scores[0]["score"] > low_scores[0]["score"]

    def test_rebounds_reacts_to_matchup_context(self) -> None:
        easy = _player_input(rebound_avg=10.0, opp_rebound_rank=25)
        hard = _player_input(rebound_avg=10.0, opp_rebound_rank=5)
        easy_scores = score_basketball_props([easy], markets=("rebounds",))
        hard_scores = score_basketball_props([hard], markets=("rebounds",))
        assert easy_scores[0]["score"] > hard_scores[0]["score"]


class TestThreesScoring:
    def test_threes_scoring_produces_valid_output(self) -> None:
        player = _player_input(threes_avg=3.5, threes_last5=4.0)
        scores = score_basketball_props([player], markets=("threes",))
        assert len(scores) == 1
        pick = scores[0]
        assert pick["market"] == "threes"
        assert 0 <= pick["score"] <= 1
        assert "confidence" in pick
        assert "direction" in pick


class TestMissingDataHandling:
    def test_missing_optional_data_returns_lower_confidence(self) -> None:
        sparse = _player_input(minutes_proj=None, usage_rate=None)
        sparse_scores = score_basketball_props([sparse], markets=("points",))
        assert sparse_scores[0]["confidence"] in ("low", "medium")
        assert "missing_data" in sparse_scores[0]["explainability"]["risk_flags"]

    def test_missing_data_does_not_crash(self) -> None:
        minimal = {"player_name": "Test Player", "line_points": 20.5}
        scores = score_basketball_props([minimal], markets=("points",))
        assert len(scores) == 1
        assert scores[0]["player"] == "Test Player"


class TestOutputFormat:
    def test_output_includes_required_fields(self) -> None:
        player = _player_input()
        scores = score_basketball_props([player], markets=("points",))
        pick = scores[0]
        assert "player" in pick
        assert "market" in pick
        assert "score" in pick
        assert "confidence" in pick
        assert "direction" in pick
        assert "line" in pick
        assert "explainability" in pick
        assert "risk_flags" in pick["explainability"]


def _player_input(
    *,
    player_name: str = "Test Player",
    position: str = "SF",
    minutes_proj: float | None = 34.0,
    usage_rate: float | None = 0.26,
    points_avg: float | None = 22.0,
    points_last5: float | None = 24.0,
    assist_avg: float | None = 5.0,
    assist_last5: float | None = 5.5,
    rebound_avg: float | None = 7.0,
    rebound_last5: float | None = 7.0,
    threes_avg: float | None = 2.5,
    threes_last5: float | None = 2.5,
    steals_avg: float | None = 1.2,
    steals_last5: float | None = 1.3,
    blocks_avg: float | None = 0.8,
    blocks_last5: float | None = 0.9,
    turnovers_avg: float | None = 2.5,
    turnovers_last5: float | None = 2.3,
    fg_made_avg: float | None = 8.0,
    fg_made_last5: float | None = 8.5,
    fg_attempted_avg: float | None = 16.0,
    fg_attempted_last5: float | None = 17.0,
    two_pt_made_avg: float | None = 5.5,
    two_pt_made_last5: float | None = 6.0,
    pace_factor: float | None = 1.0,
    opp_rebound_rank: int | None = 15,
    line_points: float = 22.5,
    line_assists: float = 5.5,
    line_rebounds: float = 7.5,
    line_threes: float = 2.5,
    line_steals: float = 1.5,
    line_blocks: float = 1.5,
    line_turnovers: float = 2.5,
    line_fg_made: float = 8.5,
    line_fg_attempted: float = 16.5,
    line_two_pt_made: float = 5.5,
    line_rebs_asts: float = 12.5,
    line_pra: float = 35.5,
    line_blks_stls: float = 2.5,
) -> dict:
    d: dict = {"player_name": player_name, "position": position}
    if minutes_proj is not None:
        d["minutes_proj"] = minutes_proj
    if usage_rate is not None:
        d["usage_rate"] = usage_rate
    if points_avg is not None:
        d["points_avg"] = points_avg
    if points_last5 is not None:
        d["points_last5"] = points_last5
    if assist_avg is not None:
        d["assist_avg"] = assist_avg
    if assist_last5 is not None:
        d["assist_last5"] = assist_last5
    if rebound_avg is not None:
        d["rebound_avg"] = rebound_avg
    if rebound_last5 is not None:
        d["rebound_last5"] = rebound_last5
    if threes_avg is not None:
        d["threes_avg"] = threes_avg
    if threes_last5 is not None:
        d["threes_last5"] = threes_last5
    if steals_avg is not None:
        d["steals_avg"] = steals_avg
    if steals_last5 is not None:
        d["steals_last5"] = steals_last5
    if blocks_avg is not None:
        d["blocks_avg"] = blocks_avg
    if blocks_last5 is not None:
        d["blocks_last5"] = blocks_last5
    if turnovers_avg is not None:
        d["turnovers_avg"] = turnovers_avg
    if turnovers_last5 is not None:
        d["turnovers_last5"] = turnovers_last5
    if fg_made_avg is not None:
        d["fg_made_avg"] = fg_made_avg
    if fg_made_last5 is not None:
        d["fg_made_last5"] = fg_made_last5
    if fg_attempted_avg is not None:
        d["fg_attempted_avg"] = fg_attempted_avg
    if fg_attempted_last5 is not None:
        d["fg_attempted_last5"] = fg_attempted_last5
    if two_pt_made_avg is not None:
        d["two_pt_made_avg"] = two_pt_made_avg
    if two_pt_made_last5 is not None:
        d["two_pt_made_last5"] = two_pt_made_last5
    if pace_factor is not None:
        d["pace_factor"] = pace_factor
    if opp_rebound_rank is not None:
        d["opp_rebound_rank"] = opp_rebound_rank
    d["line_points"] = line_points
    d["line_assists"] = line_assists
    d["line_rebounds"] = line_rebounds
    d["line_threes"] = line_threes
    d["line_steals"] = line_steals
    d["line_blocks"] = line_blocks
    d["line_turnovers"] = line_turnovers
    d["line_fg_made"] = line_fg_made
    d["line_fg_attempted"] = line_fg_attempted
    d["line_two_pt_made"] = line_two_pt_made
    d["line_rebs_asts"] = line_rebs_asts
    d["line_pra"] = line_pra
    d["line_blks_stls"] = line_blks_stls
    return d


class TestZeroLineRejection:
    """Defense-in-depth: scoring must never produce picks with line=0 or missing line."""

    def test_zero_line_player_excluded(self) -> None:
        player = _player_input(line_points=0)
        results = score_basketball_props([player], markets=("points",))
        assert results == []

    def test_missing_line_key_excluded(self) -> None:
        player = _player_input()
        del player["line_points"]
        results = score_basketball_props([player], markets=("points",))
        assert results == []

    def test_valid_nonzero_line_still_scores(self) -> None:
        player = _player_input(line_points=25.5)
        results = score_basketball_props([player], markets=("points",))
        assert len(results) == 1
        assert results[0]["line"] == 25.5


class TestStealsScoring:
    def test_steals_produces_valid_output(self) -> None:
        player = _player_input(steals_avg=1.5, steals_last5=1.8)
        scores = score_basketball_props([player], markets=("steals",))
        assert len(scores) == 1
        assert scores[0]["market"] == "steals"
        assert 0 <= scores[0]["score"] <= 1


class TestBlocksScoring:
    def test_blocks_favors_centers(self) -> None:
        center = _player_input(position="C", blocks_avg=2.0, blocks_last5=2.5)
        guard = _player_input(position="PG", blocks_avg=2.0, blocks_last5=2.5)
        center_scores = score_basketball_props([center], markets=("blocks",))
        guard_scores = score_basketball_props([guard], markets=("blocks",))
        assert center_scores[0]["score"] > guard_scores[0]["score"]


class TestTurnoversScoring:
    def test_turnovers_produces_valid_output(self) -> None:
        player = _player_input(turnovers_avg=3.0, turnovers_last5=2.8)
        scores = score_basketball_props([player], markets=("turnovers",))
        assert len(scores) == 1
        assert scores[0]["market"] == "turnovers"
        assert 0 <= scores[0]["score"] <= 1


class TestFGMadeScoring:
    def test_fg_made_produces_valid_output(self) -> None:
        player = _player_input(fg_made_avg=8.0, fg_made_last5=9.0)
        scores = score_basketball_props([player], markets=("fg_made",))
        assert len(scores) == 1
        assert scores[0]["market"] == "fg_made"
        assert 0 <= scores[0]["score"] <= 1


class TestFGAttemptedScoring:
    def test_fg_attempted_produces_valid_output(self) -> None:
        player = _player_input(fg_attempted_avg=16.0, fg_attempted_last5=17.0)
        scores = score_basketball_props([player], markets=("fg_attempted",))
        assert len(scores) == 1
        assert scores[0]["market"] == "fg_attempted"
        assert 0 <= scores[0]["score"] <= 1


class TestTwoPtMadeScoring:
    def test_two_pt_made_produces_valid_output(self) -> None:
        player = _player_input(position="C", two_pt_made_avg=6.0, two_pt_made_last5=6.5)
        scores = score_basketball_props([player], markets=("two_pt_made",))
        assert len(scores) == 1
        assert scores[0]["market"] == "two_pt_made"
        assert 0 <= scores[0]["score"] <= 1

    def test_two_pt_made_direction_resolves(self) -> None:
        player = _player_input(two_pt_made_avg=5.0, two_pt_made_last5=6.0, line_two_pt_made=5.5)
        scores = score_basketball_props([player], markets=("two_pt_made",))
        assert scores[0]["direction"] == "over"


class TestComboMarkets:
    def test_rebs_asts_produces_valid_output(self) -> None:
        player = _player_input(rebound_avg=7.0, rebound_last5=7.5, assist_avg=5.0, assist_last5=5.5)
        scores = score_basketball_props([player], markets=("rebs_asts",))
        assert len(scores) == 1
        assert scores[0]["market"] == "rebs_asts"
        assert 0 <= scores[0]["score"] <= 1

    def test_rebs_asts_direction_uses_combined_projection(self) -> None:
        player = _player_input(
            rebound_last5=8.0, assist_last5=6.0, line_rebs_asts=15.0,
        )
        scores = score_basketball_props([player], markets=("rebs_asts",))
        assert scores[0]["direction"] == "under"

    def test_pra_produces_valid_output(self) -> None:
        player = _player_input()
        scores = score_basketball_props([player], markets=("pra",))
        assert len(scores) == 1
        assert scores[0]["market"] == "pra"
        assert 0 <= scores[0]["score"] <= 1

    def test_pra_direction_sums_all_three(self) -> None:
        player = _player_input(
            points_last5=25.0, rebound_last5=8.0, assist_last5=6.0, line_pra=38.0,
        )
        scores = score_basketball_props([player], markets=("pra",))
        assert scores[0]["direction"] == "over"

    def test_blks_stls_produces_valid_output(self) -> None:
        player = _player_input(blocks_avg=1.5, blocks_last5=1.8, steals_avg=1.2, steals_last5=1.5)
        scores = score_basketball_props([player], markets=("blks_stls",))
        assert len(scores) == 1
        assert scores[0]["market"] == "blks_stls"
        assert 0 <= scores[0]["score"] <= 1

    def test_blks_stls_direction_uses_sum(self) -> None:
        player = _player_input(
            blocks_last5=2.0, steals_last5=1.5, line_blks_stls=4.0,
        )
        scores = score_basketball_props([player], markets=("blks_stls",))
        assert scores[0]["direction"] == "under"
