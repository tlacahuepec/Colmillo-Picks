from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_market_source_research_records_boundaries_and_candidates() -> None:
    content = (ROOT / "docs" / "market-source-research.md").read_text(encoding="utf-8")

    assert "## Source decision matrix" in content
    assert "The Odds API" in content
    assert "SportsGameOdds" in content
    assert "Sportradar" in content
    assert "OpticOdds" in content
    assert "stats-first, LLM-second" in content
    assert "Procurement gate" in content


def test_market_expansion_backlog_has_priorities_and_safety_gate() -> None:
    content = (ROOT / "docs" / "market-expansion-backlog.md").read_text(encoding="utf-8")

    assert "## Feasibility-ranked candidates" in content
    assert "## Implementation gate for every candidate" in content
    assert "Do not build" in content
    assert "automated wagering" in content
    assert "PrizePicks inventory limitation" in content


def test_backlog_triage_records_active_and_deferred_work() -> None:
    content = (ROOT / "docs" / "backlog-triage-2026-09-12.md").read_text(encoding="utf-8")

    assert "## Closed as delivered" in content
    assert "## Discarded" in content
    assert "## Deferred" in content
    assert "#249" in content
    assert "#248" in content
