# Baseball reliability audit — 2026-09-12

Status: partial, stopped by the predefined systemic-failure condition.

## Method

The audit runner selected the first ten official MLB games published for
2025-05-24 and used ten fixed historical NBA and soccer fixtures. It makes one
pipeline attempt per fixture, saves only operational metadata, and disables
MLB LLM enrichment so missing market lines are measured rather than hidden by
additional provider calls. Gemini calls now enforce the client's configured
20-second transport deadline.

## Observed sample

| Sport | Attempted | Collection succeeded | Reached scoring | Primary outcome |
| --- | ---: | ---: | ---: | --- |
| Baseball | 10 | 10 | 10 | 10/10 score-stage rejections: `missing_prop_lines` |
| Basketball | 4 | 0 | 0 | 4/4 player-stats provider failures before scoring (two 504s, two read timeouts) |
| Soccer | 0 | N/A | N/A | Not sampled after the systemic NBA failure stop condition |

No pick-quality comparison is claimed: neither baseball nor basketball
produced scored picks, and soccer was intentionally not called after the stop
condition. The result is a reliability finding, not an accuracy evaluation.

## Root causes

1. **MLB market-data gap:** the official StatsAPI path returned schedule,
   lineup, pitcher, and player context, but does not supply player-prop lines.
   The scoring engine correctly rejects these inputs rather than issuing picks
   without lines.
2. **Basketball provider reliability:** the historical player-stats lookup
   failed four times in succession before the scoring stage. The new SDK
   transport deadline converts a former indefinite wait into a diagnostic
   `timeout`/504 failure.

## Recommendations

1. Add an authorized MLB player-prop-line provider before further MLB scoring
   calibration or player-exclusion work.
2. Keep the Gemini transport deadline and surface its timeout category in the
   operational diagnostics. Retry the NBA reliability sample only after the
   provider returns bounded successful player-stat payloads.
3. Resume the 10-game soccer sample only after basketball is stable, so the
   three-sport comparison uses comparable live-run conditions.
