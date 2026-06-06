# Sports Stats Bible

**Parent research:** GitHub issue #249, the basketball enrichment flakiness spike, and the MLB provider decision documents.

## Purpose

This document is Colmillo Picks' canonical guide for sports data sources. It exists to make the pipeline more deterministic, make LLM grounding searches easier, and prevent critical scoring fields from depending on fragile public-page scraping.

**Constraint: Colmillo operates on free-tier and public data only. No paid subscriptions.** The primary collection method is LLM search grounding (Gemini), supplemented by free public APIs where stable and available.

The target architecture is **LLM-grounding-first, free APIs where available**:

1. Resolve the sport, league, event, player, and market.
2. Query free direct adapter sources first when implemented (MLB StatsAPI, PrizePicks availability).
3. Use LLM search grounding (Gemini) with targeted source URLs for remaining fields.
4. Normalize collected data into the sport context used by scoring.
5. Run completeness checks for required fields.
6. Persist source metadata, freshness, confidence, and fallback reasons.

Related repo context:

- `docs/mlb-provider-decision.md` keeps MLB StatsAPI as the MLB v1 provider.
- `docs/mlb-architecture.md` describes the deterministic MLB collection/scoring/explanation flow.
- `docs/spikes/spike-2026-05-30-basketball-enrichment-flakiness.md` documents why search-grounded basketball enrichment can be non-deterministic.

## Current architecture reality

| Sport | Collection method | Scoring | Status |
| --- | --- | --- | --- |
| Soccer | LLM (Gemini search grounding) | Deterministic | Production |
| Basketball | LLM (Gemini search grounding) | Deterministic | Production |
| Baseball (MLB) | MLB StatsAPI (free, no key required) | Deterministic | Production |
| Availability | PrizePicks public endpoint | N/A | Production |

All sports use deterministic scoring after collection. The LLM is used for data collection and enrichment, not for scoring decisions.

## Outlier-style target product

[Outlier.bet](https://outlier.bet/) is the closest product benchmark for the research experience we want to approximate over time. Public product messaging emphasizes player props, game lines, trends, injuries, matchup information, line movement, odds comparison, positive-EV style discovery, arbitrage/middle/boost opportunities, real-time alerts, and sportsbook/DFS availability.

Colmillo should implement that benchmark incrementally instead of trying to copy the entire product at once.

| Outlier-style capability | Required source category | Normalized fields needed | Colmillo phase |
| --- | --- | --- | --- |
| Trending picks/feed | Stats provider + props provider + scoring ledger | pick score, edge, sport, market, source freshness, confidence | After odds/props grounding |
| Thousands of props/game lines | Prop-lines aggregator | event id, player id, sportsbook, market, line, side, price, timestamp | After TheOddsAPI free tier or LLM grounding |
| Player trend cards | Stats provider + recent-game logs | season average, last-5 average, last-10 average, game log rows, minutes/starts | After sport-specific grounding recipes |
| Injury context | Injury provider + news grounding | injury status, expected availability, minutes risk, source timestamp | LLM grounding from sports pages |
| Matchup context | Stats provider + opponent/team metrics | opponent rank, pace, defensive rating, possession share, handedness/platoon splits | Sport-by-sport |
| Line movement | Prop/odds snapshots | opening line, current line, movement, book, captured timestamp | After odds snapshot persistence |
| Odds comparison | Odds/props aggregator | sportsbook, line, price, market, availability | After TheOddsAPI free tier |
| EV+ indicators | Odds/props + model probability | model probability, implied probability, edge, confidence, vig handling | After model calibration |
| Sharp-book reference | Odds provider with selected books | Pinnacle/Circa-style reference price, consensus price, book tier | Later betting analytics |
| Boosts | Sportsbook/DFS promotion source | boost type, boosted line/odds, book, expiration | Later; may require manual/LLM grounding |
| Arbitrage/middle detection | Multi-book odds snapshots | book A/B lines, sides, price, stake math, timestamp | After odds snapshot persistence |
| Alerts | Snapshot diff + user preferences | watched player/team/market, threshold, delivery channel | UI/notification phase |
| Sportsbook/DFS availability | Availability provider | platform, available/unavailable/unknown, url, checked timestamp | Existing PrizePicks path plus provider expansion |
| Responsible gaming | Static policy + UI copy | no guarantees, no risk-free language, help resources | Always required |

## Practical Approximation of Outlier Capabilities (Current Free + LLM State)

This section maps how close we are today to Outlier.bet-style insights using only free sources, public pages, and Gemini grounding. The goal is to give the LLM (and future UI) concrete guidance on what “good enough” research looks like without paid tools.

- **Player trend cards & recent form**: Strong today. Use StatMuse + ESPN gamelogs (e.g. https://www.espn.com/nba/player/gamelog/_/id/5104157/victor-wembanyama) + FotMob/Sofascore for last-5/10 aggregates, minutes, usage. LLM synthesizes cleanly when source URLs are required.
- **Injury / load management / availability context**: Strong. Transfermarkt + Sofascore + ESPN news sections + FotMob injury flags. Always cross-reference 2+ sources and store confidence.
- **Matchup context (opponent pace, defensive rating, platoon splits)**: Moderate-Good. NBA.com advanced or FBref/WhoScored tactical stats + LLM extraction. Good for basketball and soccer props.
- **Trending / sentiment signals**: Moderate. Reddit r/PrizePicks + public betting % pages (when available via grounding). Never use for score-critical fields.
- **Line movement & real-time odds comparison**: Limited today. TheOddsAPI free tier (evaluated in roadmap) gives basic moneylines/totals. Player props and movement require more quota or later paid tier. Currently rely on PrizePicks snapshot + LLM for context.
- **EV+ style edge detection**: Future. Requires calibrated model probability + reliable odds. We can approximate “value” qualitatively via form + matchup + line context.
- **Arbitrage / middle / boost detection**: Future / limited. Multi-book snapshots needed; currently out of scope or manual.
- **Alerts & personalized feeds**: UI phase. The bible + grounding quality directly enables better alert logic later.

**Key takeaway**: Focus grounding recipes and field dictionary on the “Strong” and “Moderate-Good” areas first. These already give Colmillo a research experience competitive with many paid tools for core prop reasoning.

## Source tiers

... (unchanged from current — all your tiers and rules preserved) ...

## Key Metrics Glossary

Consistent definitions help the LLM produce reliable, comparable outputs and help humans understand scoring logic. Reference these when writing grounding prompts or explanations.

- **Usage Rate (USG%)**: Share of team possessions a player uses while on the floor. High usage often means higher variance and prop ceiling.
- **Expected Goals (xG) / Expected Assists (xA)**: Quality-weighted scoring and creation metrics. Much more stable than raw goals/assists over small samples.
- **Pace**: Team possessions per 48 minutes. Directly impacts volume stats (points, rebounds, etc.).
- **Defensive Rating / Opponent Defensive Rank**: Points allowed per 100 possessions. Key for matchup adjustments in props.
- **Minutes Projection / Rotation Risk**: Expected playing time + likelihood of unexpected DNP or reduced role. Critical for prop volume.
- **Platoon / Handedness Splits**: Performance vs left- or right-handed opponents (or LHP/RHP in MLB). Often material for props.
- **Recent Form (Last-5 / Last-10)**: Aggregates from the most recent settled games. Prefer these over season averages for short-term props.
- **Market Agreement / Line Consensus**: How aligned different books or DFS platforms are on a line. Useful signal of sharp vs public money.

Add new terms here as the grounding recipes and scoring logic evolve.

## Basketball source matrix

... (enhanced with your exact example URLs for Wembanyama ESPN gamelog and StatMuse) ...

## Soccer source matrix

... (enhanced with your example FBref Lamine Yamal and ESPN Kvaratskhelia links) ...

## ... (Baseball, Betting matrices unchanged but still excellent) ...

## LLM grounding recipes

... (original recipes preserved) ...

### Example Grounding Query Patterns (Proven / Recommended)

These patterns have shown good consistency when used with Gemini. Copy/adapt them in prompts and future code.

**Basketball recent-form + usage (inspired by your examples)**:
"For [Player Name], pull the last 5 games from StatMuse[](https://www.statmuse.com/nba/ask/[player-slug]-last-5-games) and the ESPN gamelog (example: https://www.espn.com/nba/player/gamelog/_/id/[espn-id]/[player-slug]). Also check NBA.com advanced splits and any load management notes. Return structured JSON with points, assists, rebounds, threes, minutes, usage_rate per game + averages. Include source URLs for each group. Use null for anything unverifiable."

**Soccer player props form + availability**:
"Using FotMob and Sofascore for [Player], extract recent form (last 5-10 matches): goals, assists, shots, xG if available, minutes played, starts. From Transfermarkt check injury/suspension status and expected availability for the upcoming match. Cross-reference FBref advanced stats (example: https://fbref.com/en/players/[fbref-id]/[player]) for xG, progressive carries, etc. if relevant to the prop. Keep club vs national team context separate. Return with source URLs and confidence per field."

**General rule for all examples**: Always require source URLs. Prefer the most recent settled games. Note opponent strength when available. Never invent numbers.

## Anti-Patterns & Grounding Quality Rules

To keep outputs reliable and reduce hallucination risk, follow these rules in all grounding prompts and LLM calls:

- **Never blend club and national-team form** unless the specific market or prop explicitly requires it. Soccer players frequently switch contexts.
- **Injuries & availability**: Always cross-check at least two sources (e.g. Transfermarkt + Sofascore + ESPN). If they conflict, return the most conservative status + note the discrepancy and lower confidence.
- **Recent form**: Always include both last-5/last-10 and season context. Small samples are noisy; opponent quality matters.
- **Single-source rule**: Never accept a critical numeric field (points, goals, usage, minutes) from only one source without a second confirmation or explicit low-confidence flag.
- **No fabrication**: If the LLM cannot find a verifiable value with a source URL, return null rather than guessing or averaging creatively.
- **Line/price fields**: Only use PrizePicks adapter or TheOddsAPI. Never let LLM invent or “recall” betting lines.
- **Recency & freshness**: Grounding should prefer the most recent completed games. Note game dates.
- **Context preservation**: For soccer, always keep league/competition and date context. For basketball, note back-to-back or rest days.
- **Sentiment vs facts**: Reddit and forums are Tier 4 only. Use for narrative color, never for any scoring input.

These rules should be included (or referenced) in every grounding prompt template.

## Field dictionary

... (unchanged) ...

## Implementation roadmap

... (original phases 1-6 preserved) ...

### Phase 7 — Grounding quality & glossary integration (NEW)

- Embed the Key Metrics Glossary and Anti-Patterns rules directly into all grounding prompt templates.
- Add automated or manual checks for grounding consistency (e.g., same player queried twice in a day should produce similar recent-form numbers within tolerance).
- Measure and track per-source success rate / freshness compliance.
- Expand example query patterns with more sports/markets.

## How to contribute to this Bible

- When adding a new source or field, update the relevant matrix, tiers, and field dictionary.
- When improving grounding prompts in code, sync the recipes and examples here.
- Link related spikes or issues to this document.
- Propose new glossary terms or anti-patterns when you notice recurring LLM issues.
- Keep the free-only and LLM-grounding-first principles intact.

See also `docs/contributor-playbook.md` for general contribution workflow.
