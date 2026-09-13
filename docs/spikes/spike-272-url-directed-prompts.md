# Spike #272: URL-Directed vs Vague Enrichment Prompts

**Date:** 2026-06-06
**Model:** gemini-2.5-flash (search grounding enabled)
**Players:** 5 (2026 NBA Finals: NYK vs SAS)
**Attempts per player:** 3 (temperatures: None, 0.7, 1.0)

## Hypothesis

Adding explicit source URLs and anti-pattern rules to the system prompt (bible-style)
will improve Gemini's source selection and grounding quality compared to the current
vague guidance ("Search basketball-reference.com, nba.com/stats, or equivalent sources").

## Method

- **Variant A (vague):** Production `_build_system_prompt()` — no explicit URLs
- **Variant B (bible-style):** `BibleStyleEnrichmentProvider` with:
  - Explicit URL patterns for StatMuse, ESPN, NBA.com, Basketball-Reference
  - Anti-pattern rules (null over guessing, multi-source verification, recency preference)
- Same players, same session, same model configuration
- Measured via Streamlit Grounding Audit page

## Results

### Quality Metrics

| Metric | Vague (A) | Bible-style (B) | Delta |
|--------|-----------|-----------------|-------|
| Avg Field-Fill Rate | 89.0% | 80.0% | -9.0% |
| Avg Source-URL Presence | 100.0% | 100.0% | — |
| Avg Critical-Null Rate | 11.0% | 20.0% | +9.0% |
| LLM Errors | 1 (6.7%) | 0 (0%) | better |
| Avg Confidence | 0.90 | 1.00 | +0.10 |

### Per-Player Comparison

| Player | Fill (A) | Fill (B) | Nulls (A) | Nulls (B) | CV (A) | CV (B) |
|--------|----------|----------|-----------|-----------|--------|--------|
| Karl-Anthony Towns | 84.8% | 84.8% | 15.2% | 15.2% | 0.066 | 0.000 |
| Jalen Brunson | 87.9% | 87.9% | 12.1% | 12.1% | 0.002 | 0.002 |
| Victor Wembanyama | 81.8% | 63.6% | 18.2% | 36.4% | 0.065 | 0.036 |
| Devin Vassell | 100.0% | 93.9% | 0.0% | 6.1% | 0.053 | 0.001 |
| Stephon Castle | 93.9% | 69.7% | 6.1% | 30.3% | 0.033 | 0.106 |

### Source Distribution

| Source Domain | Vague (A) | Bible (B) | Change |
|--------------|-----------|-----------|--------|
| vertexaisearch.cloud.google.com | 57 | 9 | -84% |
| www.statmuse.com | 10 | 32 | +220% |
| www.basketball-reference.com | 6 | 7 | +17% |
| www.espn.com | 1 | 2 | +100% |
| www.fanduel.com | 6 | 4 | -33% |
| www.rotowire.com | 3 | 8 | +167% |

### Bible-Expected Sources

| Source | Vague (A) | Bible (B) |
|--------|-----------|-----------|
| espn.com | PRESENT (1) | PRESENT (2) |
| statmuse.com | PRESENT (10) | PRESENT (32) |
| nba.com | PRESENT | PRESENT |
| basketball-reference.com | PRESENT (6) | PRESENT (7) |

## Key Findings

1. **Explicit URLs redirect source selection.** Bible-style moved citations from opaque
   Vertex AI internal search (57→9) to named, verifiable sources (StatMuse 10→32).
   This is the primary win — we get auditable provenance.

2. **Anti-pattern rules reduce fill rate.** "Return null rather than guessing" makes
   the model more conservative. Wembanyama and Castle dropped significantly.
   The vague prompt may fill those fields with lower-confidence values.

3. **Consistency is mixed.** Bible improved KAT (0.066→0.000) and Vassell (0.053→0.001)
   but worsened Castle (0.033→0.106). More investigation needed on why Castle is volatile.

4. **Zero LLM errors with bible.** The structured prompt may produce more reliable JSON
   output (1 failure vs 0).

5. **Confidence scores improved.** Bible-style achieved 1.00 across all players vs 0.90
   average for vague. When the model does fill a field, it's more confident.

## Recommendation: GO (with modification)

**Wire the explicit source URLs into production** (Story #275) but **soften the anti-pattern rules**:

- Keep: Explicit URL patterns for StatMuse, ESPN, NBA.com, Basketball-Reference
- Keep: "Return null ONLY when no source can verify the value"
- Soften: Remove "Never accept a critical numeric from only one source" — this is
  over-constraining when the single source is a tier-1 reference like Basketball-Reference
- Soften: Reword recency rule as preference, not hard requirement

Expected outcome: Fill rate recovers to ~85-90% while keeping the improved source
distribution and auditability.

## Next Steps

- Story #275: Wire bible URLs into production `_build_system_prompt()` with softened rules
- Monitor fill rate after integration — target ≥85% with all 4 bible sources present
- Consider per-player difficulty tiers (stars vs role players) for quality expectations
