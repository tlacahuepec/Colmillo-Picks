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

## Practical approximation of Outlier capabilities

Maps current free-tier + Gemini grounding coverage against the Outlier-style target above. Focus grounding energy on the **Strong** and **Moderate-Good** areas first — these already give Colmillo a research experience competitive with many paid tools for core prop reasoning.

- **Player trend cards & recent form** — Strong. StatMuse (`https://www.statmuse.com/nba/ask/wembanyama-last-5-games`) + ESPN gamelogs (`https://www.espn.com/nba/player/gamelog/_/id/5104157/victor-wembanyama`) + FotMob/Sofascore for last-5/10 aggregates, minutes, usage. LLM synthesizes cleanly when source URLs are required.
- **Injury / availability context** — Strong. Transfermarkt + Sofascore + ESPN news sections + FotMob injury flags. Always cross-reference 2+ sources and store confidence.
- **Matchup context (opponent pace, defensive rating, platoon splits)** — Moderate-Good. NBA.com advanced stats or FBref/WhoScored tactical tables + LLM extraction. Good for basketball and soccer props.
- **Trending / sentiment signals** — Moderate. Reddit r/PrizePicks + public betting % pages (when available via grounding). Never use for score-critical fields.
- **Line movement & real-time odds comparison** — Limited. TheOddsAPI free tier (Phase 4) gives basic moneylines/totals. Player props and movement require more quota. Currently rely on PrizePicks snapshot + LLM for context.
- **EV+ edge detection** — Future. Requires calibrated model probability + reliable odds. Can approximate "value" qualitatively via form + matchup + line context.
- **Arbitrage / middle / boost detection** — Future. Multi-book snapshots needed; currently out of scope.
- **Alerts & personalized feeds** — UI phase. Grounding quality directly enables better alert logic later.

## Source tiers

Use these tiers when adding a provider or prompting an LLM. A source can be direct-adapter-ready for one field and grounding-only for another.

| Tier | Usage mode | Description | Examples | Rule |
| --- | --- | --- | --- | --- |
| 0 | Direct adapter | Existing deterministic repo provider | MLB StatsAPI adapter, PrizePicks availability | Prefer when implemented and healthy |
| 1 | Free API | Free public API with stable docs (no subscription) | MLB StatsAPI, football-data.org free tier, StatsBomb Open Data, TheOddsAPI free tier, BALLDONTLIE free tier | Good first choice when fields fit and quota allows |
| 2 | LLM grounding | Public page useful for human/LLM extraction but not a supported automation API | FotMob, Sofascore, ESPN pages, NBA.com pages, StatMuse, LiveSport, Transfermarkt, FlashScore | Use to help LLM search; store source URLs |
| 3 | Scrape-sensitive grounding | Scrape-sensitive or unstable public pages | Basketball-Reference, FBref, WhoScored | Avoid direct scraping; use as LLM grounding reference only |
| 4 | Sentiment only | Forums/social/user chatter | Reddit `/r/PrizePicks`, betting forums | Never authoritative for scoring fields |

**Hard rule:** never make scrape-only public pages the only production dependency for critical scoring fields. If a public page is useful, classify it as an **LLM grounding** helper unless it has a documented free API and permitted automation path.

**Budget rule:** no paid subscriptions. Only use free tiers, public endpoints, and LLM grounding. If a provider requires payment for useful fields, note it as "future if budget exists" and use LLM grounding as the interim approach.

## Key Metrics Glossary

Consistent definitions help the LLM produce reliable, comparable outputs and help humans understand scoring logic. Reference these when writing grounding prompts or explanations.

- **Usage Rate (USG%)** — Share of team possessions a player uses while on the floor. High usage often means higher variance and prop ceiling.
- **Expected Goals (xG) / Expected Assists (xA)** — Quality-weighted scoring and creation metrics. Much more stable than raw goals/assists over small samples.
- **Pace** — Team possessions per 48 minutes. Directly impacts volume stats (points, rebounds, etc.).
- **Defensive Rating / Opponent Defensive Rank** — Points allowed per 100 possessions. Key for matchup adjustments in props.
- **Minutes Projection / Rotation Risk** — Expected playing time + likelihood of unexpected DNP or reduced role. Critical for prop volume.
- **Platoon / Handedness Splits** — Performance vs left- or right-handed opponents (or LHP/RHP in MLB). Often material for props.
- **Recent Form (Last-5 / Last-10)** — Aggregates from the most recent settled games. Prefer these over season averages for short-term props.
- **Market Agreement / Line Consensus** — How aligned different books or DFS platforms are on a line. Useful signal of sharp vs public money.

Add new terms here as grounding recipes and scoring logic evolve.

## Basketball source matrix

| Source | Data fields | Free API? | LLM grounding candidate | Risk/cost notes | Recommended use |
| --- | --- | --- | --- | --- | --- |
| BALLDONTLIE | NBA teams, players, games, game player stats, season averages | Free tier (limited) | Yes | Free tier has rate limits and limited endpoints; advanced stats require paid | Use free tier for basic player/team lookups; LLM grounding for the rest |
| NBA.com stats | Official profile, splits, advanced, tracking, matchup, usage-style data | No (undocumented) | Yes | Public pages are grounding-friendly; endpoint automation is not an official SLA | Primary LLM grounding source for NBA advanced stats |
| `nba_api` | Python access to NBA.com stats/live endpoints | Free (unofficial) | No | Useful but NBA.com can change undocumented endpoints without notice | Secondary adapter with aggressive caching; treat failures as provider-unavailable |
| ESPN NBA player game logs | Game logs, profile context, basic per-game stats | No | Yes | JavaScript/bot checks can block automation | Grounding URL for recent-form extraction only |
| StatMuse | Natural-language last-N answers and tables | No | Yes | Great for questions like "Wemby last 5 games"; not canonical API | LLM grounding helper for recent form |
| Basketball-Reference | Historical, advanced, game logs, usage references | No | Yes | Scrape/TOS risk; public HTML can change | Manual/reference source, not production dependency |
| PrizePicks | DFS prop availability and lines | Free (public endpoint) | Yes | Current repo has availability adapter; platform may change payloads | Availability/DFS line source with graceful fallback |
| Reddit `/r/PrizePicks` | Community slips, market chatter, sentiment | No | Yes | Not authoritative; noisy and biased | Sentiment/context only; never score-critical |

Basketball field priorities:

- Player identity: `player_id`, `player_name`, `team`, `position`.
- Workload: `minutes_proj`, `starts`, `rest_days`, `rotation_risk`.
- Usage and scoring: `usage_rate`, `points_avg`, `points_last5`, `three_point_attempts`, `threes_avg`, `threes_last5`.
- Playmaking/rebounding: `assist_avg`, `assist_last5`, `rebound_avg`, `rebound_last5`.
- Context: `pace_factor`, opponent defensive rank, opponent rebound/assist/three rank, injury status.
- Props: sportsbook/DFS line, market, side, price, source, captured timestamp, market agreement.

Basketball example grounding URLs:

- ESPN gamelog: `https://www.espn.com/nba/player/gamelog/_/id/{espn_id}/{player-slug}`
- StatMuse: `https://www.statmuse.com/nba/ask/{player-slug}-last-5-games`
- NBA.com stats: `https://www.nba.com/stats/player/{nba_id}`
- Basketball-Reference: `https://www.basketball-reference.com/players/{letter}/{bbref_id}.html`

## Soccer source matrix

| Source | Data fields | Free API? | LLM grounding candidate | Risk/cost notes | Recommended use |
| --- | --- | --- | --- | --- | --- |
| football-data.org | Competitions, teams, matches, standings, lineups/bookings/subs/goals | Free tier (10 req/min, limited competitions) | Yes | Free tier covers major leagues; deep player prop fields limited | Schedule/results/standings adapter; first free soccer API to integrate |
| StatsBomb Open Data | Competitions, matches, lineups, events, selected 360 data | Free (open source) | Yes | Limited competitions and not live; great for tests/backfills | Tests, deterministic fixtures, research |
| FotMob | Player profile, recent matches, goals, assists, starts, minutes, ratings, xG/xA-style sections | No | Yes | Public page; automation risk; rich player data | Primary soccer LLM grounding helper for player stats |
| Sofascore | Player stats, ratings, match events, lineups, live scores, heat maps | No | Yes | Public page; rich data; no official API | Strong LLM grounding for player ratings and match events |
| Transfermarkt | Injuries, transfers, market values, squad info, contract details | No | Yes | Public page; scraping legal grey area in some jurisdictions | LLM grounding for injuries, transfers, squad availability |
| FlashScore | Live scores, schedules, fixtures, standings, match statistics | No | Yes | Public page; broad coverage across leagues | LLM grounding for schedules, scores, and match stats |
| WhoScored | Player ratings, tactical stats, matchup context | No | Yes | Scrape-sensitive and bot-sensitive | Grounding for tactical/matchup context only |
| FBref | Player/team advanced soccer tables, xG, passing, defensive stats | No | Yes | Scraping risk and recent public data instability | Reference/grounding only; not first adapter |
| ESPN soccer player pages | Profile, appearances, game logs/news context | No | Yes | Bot checks/JS can block automation | Grounding URL only |
| LiveSport | Schedules, scores, fixtures, standings, live match stats across sports | No | Yes | Public site; not a stable API | Broad schedule/score grounding |
| API-Football | Fixtures, lineups, player stats, standings, injuries, predictions | Free tier (100 req/day) | No | Previously integrated and removed from Colmillo; replaced by LLM grounding | Reference only; was removed in favor of Gemini-based fixture resolution |

Soccer field priorities:

- Player identity: `player_id`, `player_name`, `team`, `position`, league/competition.
- Availability: starts, minutes, injury/suspension, expected lineup status.
- Attacking: goals, assists, shots, shots_on_target, xG, xA, chances created.
- Passing/possession: passes, pass attempts, pass completion, key passes, crosses, dribbles.
- Defensive/discipline: tackles, interceptions, blocks, fouls, yellow/red cards.
- Recent form: last-5 and last-10 aggregates, match-level minutes, opponent strength.
- Props: market line, side, price, sportsbook/DFS platform, captured timestamp.

Soccer example grounding URLs:

- FotMob: `https://www.fotmob.com/players/{fotmob_id}/{player-slug}`
- FBref: `https://fbref.com/en/players/{fbref_id}/{player}`
- Sofascore: `https://www.sofascore.com/player/{player-slug}/{sofascore_id}`
- Transfermarkt: `https://www.transfermarkt.com/{player-slug}/profil/spieler/{tm_id}`
- ESPN: `https://www.espn.com/soccer/player/_/id/{espn_id}/{player-slug}`

## Baseball source matrix

| Source | Data fields | Free API? | LLM grounding candidate | Risk/cost notes | Recommended use |
| --- | --- | --- | --- | --- | --- |
| MLB StatsAPI | Schedule, rosters, probable pitchers, live feed, lineups, season stats, game logs, venue data | Free (no key required) | No | Already implemented and public/free | Keep as primary MLB provider |
| Existing Colmillo MLB adapters | `StatsAPIScheduleAdapter`, `StatsAPIPitcherAdapter`, `StatsAPIPlayerStatsAdapter`, `StatsAPISplitsAdapter`, lineups, bullpen, weather/park factor | Free (built on StatsAPI) | No | Needs deeper matchup split normalization | Expand, do not replace |
| Baseball-Reference / StatMuse / ESPN MLB pages | Historical/recent player context | No | Yes | Public-page automation risk | Grounding or manual validation only |

MLB field priorities:

- Event: `game_pk`, teams, venue, start time, weather/roof, park factor.
- Pitching: probable pitchers, handedness, strikeout rate, walk rate, recent game logs.
- Batting: lineup slot, handedness, season stats, recent game logs, home/away and platoon splits.
- Bullpen/team context: bullpen availability, team offense/defense context.
- Props: hits, home runs, total bases, RBIs, runs, strikeouts, outs, walks, line/price/source.

## Betting and props source matrix

| Source | Sports | Data fields | Free API? | LLM grounding candidate | Risk/cost notes | Recommended use |
| --- | --- | --- | --- | --- | --- | --- |
| PrizePicks | Multi-sport DFS props | Projections/lines, platform availability | Free (public endpoint) | Yes | Existing adapter checks availability; endpoint/payload can change | DFS availability and candidate line source |
| TheOddsAPI | Multi-sport odds/props | Moneylines, totals, spreads, player props, bookmaker prices | Free tier (500 req/month) | No | Free tier covers basic odds; player props require paid plans | First odds aggregator to evaluate on free tier |
| Sportsbook pages | Individual book lines/prices | Public prices and promotions | No | Yes | Automation/legal risk varies by book | Grounding/manual validation only |
| Reddit `/r/PrizePicks` | DFS betting discussion | Slips, player chatter, promo/context | No | Yes | Sentiment only; not authoritative | Forum context only |

**Not applicable currently (paid only):** SportsGameOdds (paid tiers for production), OpticOdds (commercial provider). Revisit if budget becomes available.

Betting field priorities:

- Event identity: sport, league, event id, home/away, start time.
- Market identity: player, market, side, line, price, book/platform.
- Freshness: captured timestamp, provider timestamp, TTL, stale/ok status.
- Comparison: consensus line, market agreement, best price, line movement, opening/current line.
- Risk: platform availability, missing-line reason, no-bet reason, source confidence.

## Field dictionary

| Category | Fields | Freshness target | Preferred source type | LLM fallback allowed? |
| --- | --- | --- | --- | --- |
| Player identity | `player_id`, `player_name`, `team`, `position` | Daily or provider TTL | Free stats API or LLM grounding | Yes for mapping hints; must be verified |
| Schedule/event | event id, teams, venue, start time | Same day/live | Free schedule API (football-data.org, MLB StatsAPI) | Yes only when direct lookup fails |
| Season stats | season averages, rates, splits | Daily or hourly during season | Free stats API or LLM grounding | Yes if source URL and confidence stored |
| Recent form | last-5/last-10 game logs and averages | Same day after games settle | LLM grounding (FotMob, ESPN, StatMuse) | Yes if source URL and confidence stored |
| Injury/lineup | injury status, expected starter, minutes risk | Hourly/game day | LLM grounding (Transfermarkt, Sofascore, ESPN) | Yes for narrative; critical status should remain nullable if uncertain |
| Props/odds | line, side, price, sportsbook, timestamp | Minutes | PrizePicks adapter or TheOddsAPI free tier | Avoid except as temporary fallback with low confidence |
| Forums/social | player chatter, sentiment, market popularity | Minutes/hours | Reddit/forum search | Never for score-critical fields |

## LLM grounding recipes

LLM grounding should narrow the search space instead of asking the model to discover everything from scratch. The prompt should include the sport, event, player, market, required fields, source priority, and rules for nulls.

### Basketball recipe

Preferred source order:

1. BALLDONTLIE free tier or `nba_api` for basic player/team data when available.
2. NBA.com player page or stats page for official context.
3. ESPN game log page for recent game rows when readable (e.g., `https://www.espn.com/nba/player/gamelog/_/id/{id}/{slug}`).
4. StatMuse natural-language recent-form page for last-N summaries (e.g., `https://www.statmuse.com/nba/ask/{slug}-last-5-games`).
5. Basketball-Reference only for historical/manual reference.
6. Reddit `/r/PrizePicks` only for sentiment, never for critical numbers.

Prompt rules:

- Ask for exact fields such as `usage_rate`, `minutes_proj`, `points_last5`, `assist_last5`, `rebound_last5`, `threes_last5`, and `three_point_attempts`.
- Require a source URL per populated field group.
- Use `null` when a value cannot be verified.
- Do not fabricate PrizePicks or sportsbook lines.

### Soccer recipe

Preferred source order:

1. football-data.org free tier for schedules, results, standings, and basic match context.
2. StatsBomb Open Data for supported competitions/tests.
3. FotMob for player profiles, recent form, goals, assists, starts, minutes, ratings, xG/xA (e.g., `https://www.fotmob.com/players/{id}/{slug}`).
4. Sofascore for player ratings, match events, lineups, and live data (e.g., `https://www.sofascore.com/player/{slug}/{id}`).
5. Transfermarkt for injuries, transfers, and squad availability (e.g., `https://www.transfermarkt.com/{slug}/profil/spieler/{id}`).
6. FlashScore for schedules, live scores, and match statistics.
7. WhoScored, FBref, ESPN, and LiveSport as additional grounding sources.
8. Forums/social only for context, not stats.

Prompt rules:

- Ask for exact market fields: shots, shots on target, passes, tackles, fouls, cards, goals, assists, minutes, starts, xG/xA where available.
- Preserve competition/date context because soccer players move across clubs and national teams.
- Do not merge club and national-team recent form unless the market explicitly asks for it.
- Prefer FotMob and Sofascore for recent player form; prefer Transfermarkt for injury/availability.

### Baseball recipe

Preferred source order:

1. Existing MLB StatsAPI adapters (free, already implemented).
2. Expanded MLB split/recent-form adapters.
3. TheOddsAPI free tier for basic odds when available.
4. Public pages (ESPN, StatMuse, Baseball-Reference) only for narrative validation.

Prompt rules:

- Prefer StatsAPI values for season stats, game logs, probable pitchers, lineups, and venue context.
- Ask the LLM only to summarize or fill non-critical narrative fields when direct data is partial.

### Example grounding query patterns

These patterns have shown good consistency with Gemini. Copy/adapt them in prompts and future code.

**Basketball recent-form + usage:**

> For [Player Name], pull the last 5 games from StatMuse (`https://www.statmuse.com/nba/ask/[player-slug]-last-5-games`) and the ESPN gamelog (`https://www.espn.com/nba/player/gamelog/_/id/[espn-id]/[player-slug]`). Also check NBA.com advanced splits and any load management notes. Return structured JSON with points, assists, rebounds, threes, minutes, usage_rate per game + averages. Include source URLs for each field group. Use null for anything unverifiable.

**Soccer player props form + availability:**

> Using FotMob (`https://www.fotmob.com/players/[id]/[slug]`) and Sofascore for [Player], extract recent form (last 5-10 matches): goals, assists, shots, xG if available, minutes played, starts. From Transfermarkt (`https://www.transfermarkt.com/[slug]/profil/spieler/[id]`) check injury/suspension status and expected availability for the upcoming match. Cross-reference FBref advanced stats (`https://fbref.com/en/players/[fbref-id]/[player]`) for xG, progressive carries, etc. if relevant to the prop. Keep club vs national team context separate. Return with source URLs and confidence per field.

**General rules for all grounding queries:**

- Always require source URLs per populated field group.
- Prefer the most recent settled games. Note game dates.
- Note opponent strength when available.
- Never invent numbers — use null for anything unverifiable.
- Never fabricate or "recall" betting lines.

## Anti-patterns and grounding quality rules

Follow these rules in all grounding prompts and LLM calls to keep outputs reliable and reduce hallucination risk.

1. **Never blend club and national-team form** unless the specific market explicitly requires it. Soccer players frequently switch contexts.
2. **Cross-check injuries from 2+ sources.** If Transfermarkt and Sofascore conflict, return the most conservative status + note the discrepancy and lower confidence.
3. **Never accept a critical numeric field** (points, goals, usage, minutes) from only one source without a second confirmation or explicit low-confidence flag.
4. **No fabrication.** If the LLM cannot find a verifiable value with a source URL, return null rather than guessing or averaging creatively.
5. **Line/price fields: PrizePicks adapter or TheOddsAPI only.** Never let LLM invent or "recall" betting lines.
6. **Recency preference.** Grounding should prefer the most recent completed games. Note game dates in output.
7. **Context preservation.** For soccer, always keep league/competition and date context. For basketball, note back-to-back or rest days.
8. **Sentiment is Tier 4 only.** Reddit and forums are never authoritative for scoring fields.

These rules should be referenced in every grounding prompt template.

## Implementation roadmap

### Phase 1 — Documentation only (DONE)

- Add this Sports Stats Bible.
- Add documentation tests so required sections and sources cannot disappear silently.
- Link future issue/PR work to this document.

### Phase 2 — Expand LLM grounding recipes

- Add specific source URLs per player/sport to grounding prompts.
- Improve Gemini search grounding prompts with FotMob, Sofascore, and Transfermarkt as preferred soccer sources.
- Add StatMuse and NBA.com as preferred basketball grounding sources.
- Track source quality and freshness per grounded field.

### Phase 3 — football-data.org free tier adapter

- Evaluate football-data.org free tier for soccer schedule/results/standings.
- Build a lightweight adapter for match schedules and basic context.
- Use as deterministic fallback when LLM grounding is unavailable or slow.

### Phase 4 — TheOddsAPI free tier for basic odds

- Evaluate TheOddsAPI free tier (500 requests/month) for moneylines and totals.
- Determine if quota is sufficient for daily pick generation across supported sports.
- Normalize line snapshots for basic odds comparison.

### Phase 5 — Basketball free data spike

- Evaluate BALLDONTLIE free tier for basic player/team/game data.
- Evaluate `nba_api` for usage rate, player dashboards, and advanced splits.
- Cache IDs and stable responses aggressively.
- Treat endpoint failures as provider-unavailable, not pipeline-crashing.

### Phase 6 — Outlier-like research cards

- Build player trend cards from normalized stats and game logs.
- Add injury context, matchup context, line movement, and odds comparison.
- Add responsible gaming language anywhere Colmillo surfaces betting guidance.

### Phase 7 — Grounding quality and glossary integration

- Embed the Key Metrics Glossary and Anti-Patterns rules directly into all grounding prompt templates.
- Add automated or manual checks for grounding consistency (same player queried twice in a day should produce similar recent-form numbers within tolerance).
- Measure and track per-source success rate / freshness compliance.
- Expand example grounding query patterns with more sports/markets.

## How to contribute to this Bible

- When adding a new source or field, update the relevant matrix, tiers, and field dictionary.
- When improving grounding prompts in code, sync the recipes and examples here.
- Link related spikes or issues to this document.
- Propose new glossary terms or anti-patterns when you notice recurring LLM issues.
- Keep the free-only and LLM-grounding-first principles intact.

See also `docs/contributor-playbook.md` for general contribution workflow.

## Adding a new sport

Adding a new sport (e.g., NFL, NHL) requires configuration and a module implementation. The config registry pattern means no prompt builder or pipeline edits are needed — just define the config and register it.

### Quick steps

1. Research sources and document them in a source matrix above.
2. Define markets and required fields per market.
3. Create a `SportEnrichmentConfig` with URLs, anti-patterns, and field format rules.
4. Register the config in `_build_default_registry()`.
5. Implement the `SportModule` protocol (collect, score, explain).
6. Register the module in `SportModuleRegistry`.
7. Add tests verifying config content and prompt integration.
8. Update this bible with the sport's source matrix, recipe, and anti-patterns.

### Full guide

See [`docs/sport-onboarding-guide.md`](sport-onboarding-guide.md) for a complete walkthrough with NFL as an example, including code skeletons, test templates, and a checklist.
