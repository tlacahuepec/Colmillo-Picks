from render_nfl_report import render_nfl_report


def test_report_distinguishes_limited_data_from_provider_failure():
    limited = render_nfl_report([], {"home_team": "A", "away_team": "B", "data_quality": {"status": "prior_season_only"}})
    failed = render_nfl_report([], {"home_team": "A", "away_team": "B", "provider_errors": {"offers": {}}})
    assert "limited current-season data" in limited
    assert "data collection failed" in failed
