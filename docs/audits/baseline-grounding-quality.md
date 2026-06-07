# Grounding Quality Baseline — Basketball Enrichment

**Date:** 2026-06-06
**Model:** gemini-2.5-flash
**Players tested:** 5 (2026 NBA Finals: NYK vs SAS)
**Attempts per player:** 3 (temperatures: None, 0.7, 1.0)
**Total calls:** 15 (14 successful, 1 failed — invalid JSON)

## Summary Metrics

| Metric | Value |
|--------|-------|
| Avg Field-Fill Rate | 89.6% |
| Avg Source-URL Presence | 100.0% |
| Avg Critical-Null Rate | 10.4% |
| LLM Error Rate | 6.7% (1/15) |

## Per-Player Results

| Player | Fill Rate | Source URLs | Critical Nulls | Confidence | Consistency (CV) |
|--------|-----------|------------|----------------|------------|------------------|
| Karl-Anthony Towns | 84.8% | 100.0% | 15.2% | 1.00 | 0.007 |
| Jalen Brunson | 93.9% | 100.0% | 6.1% | 1.00 | 0.021 |
| Victor Wembanyama | 84.8% | 100.0% | 15.2% | 1.00 | 0.056 |
| Devin Vassell | 100.0% | 100.0% | 0.0% | 1.00 | 0.000 |
| Stephon Castle | 87.9% | 100.0% | 12.1% | 0.67 | 0.081 |

## Grounding Sources Observed

| Domain | Count |
|--------|-------|
| vertexaisearch.cloud.google.com | 23 |
| www.statmuse.com | 16 |
| www.basketball-reference.com | 9 |
| www.fanduel.com | 6 |
| www.rotowire.com | 4 |
| www.sofascore.com | 3 |
| craftednba.com | 3 |
| www.lineups.com | 3 |
| www.fantasypros.com | 3 |
| www.flashscore.com | 2 |
| basketnews.com | 2 |
| www.nbastuffer.com | 2 |
| basketball.realgm.com | 2 |
| www.hoopsforecast.com | 1 |
| www.actionnetwork.com | 1 |
| www.foxsports.com | 1 |
| empiresportsmedia.com | 1 |
| prizepicks.com | 1 |
| snyk.nyc | 1 |
| lees.substack.com | 1 |
| www.cbssports.com | 1 |
| www.3stepsbasket.com | 1 |

## Bible-Expected Sources

| Source | Status |
|--------|--------|
| espn.com | MISSING |
| statmuse.com | PRESENT |
| nba.com | PRESENT |
| basketball-reference.com | PRESENT |

## Observations

- **ESPN absent**: Gemini does not find ESPN gamelogs without explicit URL guidance. This validates the bible integration hypothesis (Story #275).
- **StatMuse dominant**: Most-cited source after Vertex internal search. Already aligned with bible recommendations.
- **High fill rate for role players**: Devin Vassell achieved 100% fill, suggesting data availability isn't the bottleneck.
- **KAT/Wemby lower fill**: 84.8% — likely missing some last-5/recent-form fields. Explicit ESPN gamelog URLs may help.
- **Consistency is good**: CV values 0.007–0.081 mean repeated queries produce similar numbers. Low hallucination risk.
- **Confidence high**: 4/5 players scored "high" confidence. Castle at 0.67 (one "medium" attempt).
- **Unexpected sources**: FanDuel, RotOwire, FantasyPros appearing — useful but not in bible's recommended list. Consider adding to Tier 2.

## Next Steps

- Story #275: Wire bible URLs (ESPN gamelog, StatMuse pattern, NBA.com) into basketball enrichment config
- Compare post-integration results against this baseline
- Track whether ESPN appears and fill rate improves for KAT/Wemby
