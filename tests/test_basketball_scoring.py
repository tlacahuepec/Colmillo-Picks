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
    pace_factor: float | None = 1.0,
    opp_rebound_rank: int | None = 15,
    line_points: float = 22.5,
    line_assists: float = 5.5,
    line_rebounds: float = 7.5,
    line_threes: float = 2.5,
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
    if pace_factor is not None:
        d["pace_factor"] = pace_factor
    if opp_rebound_rank is not None:
        d["opp_rebound_rank"] = opp_rebound_rank
    d["line_points"] = line_points
    d["line_assists"] = line_assists
    d["line_rebounds"] = line_rebounds
    d["line_threes"] = line_threes
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
