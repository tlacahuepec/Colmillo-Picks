# Market Logic

Use market discipline rules for prop selection:

- **Odds aggregation (5 books minimum)**
  - Aggregate prices from five sportsbooks where possible.
  - Compute median implied probability for Over and Under separately.

- **Implied probability sanity checks**
  - Normalize hold/vig before comparing sides.
  - Reject edges driven by one outlier book unless supported by context factors.

- **Line-value interpretation**
  - Prefer props where projected true probability materially exceeds market-implied probability.
  - Re-check assumptions when market moves sharply close to kickoff.

- **Confidence calibration**
  - High confidence: multi-factor alignment + clear market edge across books.
  - Medium confidence: moderate edge with minor uncertainty.
  - Low confidence: small edge or elevated uncertainty; include explicit caveat.
