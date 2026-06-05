# Sports Stats Bible

**Parent research:** GitHub issue #249, the basketball enrichment flakiness spike, and the MLB provider decision documents.

## Purpose

This document is Colmillo Picks' canonical guide for sports data sources. It exists to make the pipeline more deterministic, make LLM grounding searches easier, and prevent critical scoring fields from depending on fragile public-page scraping.

The target architecture is **stats-first, LLM-second**:

1. Resolve the sport, league, event, player, and market.
2. Query direct adapter sources first: official APIs, paid provider APIs, or existing in-repo deterministic providers.
3. Normalize provider payloads into the sport context used by scoring.
4. Run completeness checks for required fields.
5. Use LLM grounding only for missing, explainable, or contextual fields that cannot be sourced directly.
6. Persist source metadata, freshness, confidence, and fallback reasons.

Related repo context:

- `docs/mlb-provider-decision.md` keeps MLB StatsAPI as the MLB v1 provider.
- `docs/mlb-architecture.md` describes the deterministic MLB collection/scoring/explanation flow.
- `docs/spikes/spike-2026-05-30-basketball-enrichment-flakiness.md` documents why search-grounded basketball enrichment can be non-deterministic.

## Outlier-style target product

[Outlier.bet](https://outlier.bet/) is the closest product benchmark for the research experience we want to approximate over time. Public product messaging emphasizes player props, game lines, trends, injuries, matchup information, line movement, odds comparison, positive-EV style discovery, arbitrage/middle/boost opportunities, real-time alerts, and sportsbook/DFS availability.

Colmillo should implement that benchmark incrementally instead of trying to copy the entire product at once.

| Outlier-style capability | Required source category | Normalized fields needed | Colmillo phase |
| --- | --- | --- | --- |
| Trending picks/feed | Stats provider + props provider + scoring ledger | pick score, edge, sport, market, source freshness, confidence | After direct props provider |
| Thousands of props/game lines | Prop-lines aggregator | event id, player id, sportsbook, market, line, side, price, timestamp | After SportsGameOdds/TheOddsAPI/OpticOdds adapter |
| Player trend cards | Stats provider + recent-game logs | season average, last-5 average, last-10 average, game log rows, minutes/starts | After sport-specific stats adapters |
| Injury context | Injury provider + news grounding | injury status, expected availability, minutes risk, source timestamp | After injury adapter per sport |
| Matchup context | Stats provider + opponent/team metrics | opponent rank, pace, defensive rating, possession share, handedness/platoon splits | Sport-by-sport |
| Line movement | Prop/odds snapshots | opening line, current line, movement, book, captured timestamp | After odds snapshot persistence |
| Odds comparison | Odds/props aggregator | sportsbook, line, price, market, availability | After direct props provider |
| EV+ indicators | Odds/props + model probability | model probability, implied probability, edge, confidence, vig handling | After model calibration |
| Sharp-book reference | Odds provider with selected books | Pinnacle/Circa-style reference price, consensus price, book tier | Later betting analytics |
| Boosts | Sportsbook/DFS promotion source | boost type, boosted line/odds, book, expiration | Later; may require manual/LLM grounding |
| Arbitrage/middle detection | Multi-book odds snapshots | book A/B lines, sides, price, stake math, timestamp | After odds snapshot persistence |
| Alerts | Snapshot diff + user preferences | watched player/team/market, threshold, delivery channel | UI/notification phase |
| Sportsbook/DFS availability | Availability provider | platform, available/unavailable/unknown, url, checked timestamp | Existing PrizePicks path plus provider expansion |
| Responsible gaming | Static policy + UI copy | no guarantees, no risk-free language, help resources | Always required |

## Source tiers

Use these tiers when adding a provider or prompting an LLM. A source can be direct-adapter-ready for one field and grounding-only for another.

| Tier | Usage mode | Description | Examples | Rule |
| --- | --- | --- | --- | --- |
| 0 | Direct adapter | Existing deterministic repo provider | MLB StatsAPI adapter | Prefer when implemented and healthy |
| 1 | Direct adapter | Official/public API with stable docs | MLB StatsAPI, football-data.org, StatsBomb Open Data | Good first choice when fields fit |
| 2 | Direct adapter | Paid provider API with product/SLA expectations | BALLDONTLIE paid tiers, Sportradar, SportsGameOdds, TheOddsAPI, OpticOdds | Best for production if budget/key exists |
| 3 | LLM grounding | Public page useful for human/LLM extraction but not a supported automation API | StatMuse, ESPN pages, NBA.com pages, FotMob pages, LiveSport pages | Use to help LLM search; store source URLs |
| 4 | LLM grounding/manual research | Scrape-sensitive or unstable public pages | Basketball-Reference, FBref, WhoScored | Avoid direct scraping unless explicitly approved |
| 5 | Sentiment only | Forums/social/user chatter | Reddit `/r/PrizePicks`, betting forums | Never authoritative for scoring fields |

**Hard rule:** never make scrape-only public pages the only production dependency for critical scoring fields. If a public page is useful, classify it as an **LLM grounding** helper unless it has a documented API and permitted automation path.

## Basketball source matrix

| Source | Data fields | Direct adapter candidate | LLM grounding candidate | Risk/cost notes | Recommended use |
| --- | --- | --- | --- | --- | --- |
| BALLDONTLIE | NBA teams, players, games, game player stats, season averages, advanced stats, lineups, injuries, odds, player props | Yes | Yes | Key endpoints are paid-tier gated; requires API key and rate-limit handling | First NBA stats/injury/lineup adapter if budget allows |
| NBA.com stats | Official profile, splits, advanced, tracking, matchup, usage-style data | Conditional | Yes | The public pages are grounding-friendly; endpoint automation is not an official SLA | Grounding helper and source for `nba_api` validation |
| `nba_api` | Python access to NBA.com stats/live endpoints | Conditional | No | Useful but NBA.com can change undocumented endpoints | Secondary NBA advanced-stats adapter with caching/fallback |
| ESPN NBA player game logs | Game logs, profile context, basic per-game stats | No | Yes | JavaScript/bot checks can block automation | Grounding URL for recent-form extraction only |
| StatMuse | Natural-language last-N answers and tables | No | Yes | Great for questions like "Wemby last 5 games"; not canonical API | LLM grounding helper for recent form |
| Basketball-Reference | Historical, advanced, game logs, usage references | No | Yes | Scrape/TOS risk; public HTML can change | Manual/reference source, not production dependency |
| PrizePicks | DFS prop availability and lines | Conditional | Yes | Current repo has availability adapter; platform may change payloads | Availability/DFS line source with graceful fallback |
| Reddit `/r/PrizePicks` | Community slips, market chatter, sentiment | No | Yes | Not authoritative; noisy and biased | Sentiment/context only; never score-critical |

Basketball field priorities:

- Player identity: `player_id`, `player_name`, `team`, `position`.
- Workload: `minutes_proj`, `starts`, `rest_days`, `rotation_risk`.
- Usage and scoring: `usage_rate`, `points_avg`, `points_last5`, `three_point_attempts`, `threes_avg`, `threes_last5`.
- Playmaking/rebounding: `assist_avg`, `assist_last5`, `rebound_avg`, `rebound_last5`.
- Context: `pace_factor`, opponent defensive rank, opponent rebound/assist/three rank, injury status.
- Props: sportsbook/DFS line, market, side, price, source, captured timestamp, market agreement.

## Soccer source matrix

| Source | Data fields | Direct adapter candidate | LLM grounding candidate | Risk/cost notes | Recommended use |
| --- | --- | --- | --- | --- | --- |
| Sportradar Soccer Extended | Broad official soccer stats, player/team/match data | Yes | No | Paid/sales-led provider | Best production soccer provider if budget allows |
| StatsBomb Open Data | Competitions, matches, lineups, events, selected 360 data | Yes | Yes | Free/open but limited competitions and not live full coverage | Tests, fixtures, research, backfills |
| football-data.org | Competitions, teams, matches, standings, optional lineups/bookings/subs/goals | Yes | Yes | Free tier exists but deep player prop fields are limited | Schedule/results support source |
| FotMob | Player profile, recent matches, goals, assists, starts, minutes, ratings, xG/xA-style sections | No | Yes | Public page; automation risk | Strong soccer LLM grounding helper |
| WhoScored | Player ratings, tactical stats, matchup context | No | Yes | Scrape-sensitive and bot-sensitive | Grounding/manual context only |
| FBref | Player/team advanced soccer tables | No | Yes | Scraping risk and recent public data instability | Reference/grounding only; not first adapter |
| ESPN soccer player pages | Profile, appearances, game logs/news context | No | Yes | Bot checks/JS can block automation | Grounding URL only |
| LiveSport | Schedules, scores, fixtures, standings, live match stats across sports | No | Yes | Public site; not a stable API | Broad schedule/score grounding |

Soccer field priorities:

- Player identity: `player_id`, `player_name`, `team`, `position`, league/competition.
- Availability: starts, minutes, injury/suspension, expected lineup status.
- Attacking: goals, assists, shots, shots_on_target, xG, xA, chances created.
- Passing/possession: passes, pass attempts, pass completion, key passes, crosses, dribbles.
- Defensive/discipline: tackles, interceptions, blocks, fouls, yellow/red cards.
- Recent form: last-5 and last-10 aggregates, match-level minutes, opponent strength.
- Props: market line, side, price, sportsbook/DFS platform, captured timestamp.

## Baseball source matrix

| Source | Data fields | Direct adapter candidate | LLM grounding candidate | Risk/cost notes | Recommended use |
| --- | --- | --- | --- | --- | --- |
| MLB StatsAPI | Schedule, rosters, probable pitchers, live feed, lineups, season stats, game logs, venue data | Yes | No | Already implemented and public/free | Keep as primary MLB StatsAPI provider |
| Existing Colmillo MLB adapters | `StatsAPIScheduleAdapter`, `StatsAPIPitcherAdapter`, `StatsAPIPlayerStatsAdapter`, `StatsAPISplitsAdapter`, lineups, bullpen, weather/park factor | Yes | No | Needs deeper matchup split normalization | Expand, do not replace |
| SportsGameOdds/TheOddsAPI/OpticOdds | MLB odds and player props depending tier | Yes | No | Paid API/key likely required | Add for MLB prop lines and line movement |
| Baseball-Reference / StatMuse / ESPN MLB pages | Historical/recent player context | No | Yes | Public-page automation risk | Grounding or manual validation only |

MLB field priorities:

- Event: `game_pk`, teams, venue, start time, weather/roof, park factor.
- Pitching: probable pitchers, handedness, strikeout rate, walk rate, recent game logs.
- Batting: lineup slot, handedness, season stats, recent game logs, home/away and platoon splits.
- Bullpen/team context: bullpen availability, team offense/defense context.
- Props: hits, home runs, total bases, RBIs, runs, strikeouts, outs, walks, line/price/source.

## Betting and props source matrix

| Source | Sports | Data fields | Direct adapter candidate | LLM grounding candidate | Risk/cost notes | Recommended use |
| --- | --- | --- | --- | --- | --- | --- |
| PrizePicks | Multi-sport DFS props | Projections/lines, platform availability | Conditional | Yes | Existing adapter checks availability; endpoint/payload can change | DFS availability and candidate line source |
| SportsGameOdds | Multi-sport odds/props | Odds, props, consensus, books, event metadata | Yes | No | Free tier is limited; paid tiers for production scale | First cross-sport prop aggregator to evaluate |
| TheOddsAPI | Multi-sport odds/props depending tier | Moneylines, totals, spreads, player props, bookmaker prices | Yes | No | Request quotas and prop access vary by plan | Lower-cost alternate/backup aggregator |
| OpticOdds | Multi-sport odds/props/injuries/grading | Odds, props, injuries, results/grading | Yes | No | Commercial provider | Evaluate if consolidating odds + injuries is valuable |
| Sportsbook pages | Individual book lines/prices | Public prices and promotions | No | Yes | Automation/legal risk varies by book | Grounding/manual validation only |
| Reddit `/r/PrizePicks` | DFS betting discussion | Slips, player chatter, promo/context | No | Yes | Sentiment only; not authoritative | Forum context only |

Betting field priorities:

- Event identity: sport, league, event id, home/away, start time.
- Market identity: player, market, side, line, price, book/platform.
- Freshness: captured timestamp, provider timestamp, TTL, stale/ok status.
- Comparison: consensus line, market agreement, best price, line movement, opening/current line.
- Risk: platform availability, missing-line reason, no-bet reason, source confidence.

## Field dictionary

| Category | Fields | Freshness target | Preferred source type | LLM fallback allowed? |
| --- | --- | --- | --- | --- |
| Player identity | `player_id`, `player_name`, `team`, `position` | Daily or provider TTL | Direct stats API | Yes for mapping hints; must be verified |
| Schedule/event | event id, teams, venue, start time | Same day/live | Official schedule API | Yes only when direct lookup fails |
| Season stats | season averages, rates, splits | Daily or hourly during season | Direct stats API | Yes for non-critical explanation; no for critical scoring if absent |
| Recent form | last-5/last-10 game logs and averages | Same day after games settle | Direct game-log API | Yes if source URL and confidence stored |
| Injury/lineup | injury status, expected starter, minutes risk | Hourly/game day | Injury/lineup provider | Yes for narrative; critical status should remain nullable if uncertain |
| Props/odds | line, side, price, sportsbook, timestamp | Minutes | Direct odds/props API | Avoid except as temporary fallback with low confidence |
| Forums/social | player chatter, sentiment, market popularity | Minutes/hours | Reddit/forum search | Never for score-critical fields |

## LLM grounding recipes

LLM grounding should narrow the search space instead of asking the model to discover everything from scratch. The prompt should include the sport, event, player, market, required fields, source priority, and rules for nulls.

### Basketball recipe

Preferred source order:

1. Direct adapter data from BALLDONTLIE or `nba_api` when available.
2. NBA.com player page or stats page for official context.
3. ESPN game log page for recent game rows when readable.
4. StatMuse natural-language recent-form page for last-N summaries.
5. Basketball-Reference only for historical/manual reference.
6. Reddit `/r/PrizePicks` only for sentiment, never for critical numbers.

Prompt rules:

- Ask for exact fields such as `usage_rate`, `minutes_proj`, `points_last5`, `assist_last5`, `rebound_last5`, `threes_last5`, and `three_point_attempts`.
- Require a source URL per populated field group.
- Use `null` when a value cannot be verified.
- Do not fabricate PrizePicks or sportsbook lines.

### Soccer recipe

Preferred source order:

1. Direct adapter data from Sportradar or another paid soccer provider when configured.
2. StatsBomb Open Data for supported competitions/tests.
3. football-data.org for schedules/results/basic match context.
4. FotMob, WhoScored, FBref, ESPN, and LiveSport as grounding/manual sources.
5. Forums/social only for context, not stats.

Prompt rules:

- Ask for exact market fields: shots, shots on target, passes, tackles, fouls, cards, goals, assists, minutes, starts, xG/xA where available.
- Preserve competition/date context because soccer players move across clubs and national teams.
- Do not merge club and national-team recent form unless the market explicitly asks for it.

### Baseball recipe

Preferred source order:

1. Existing MLB StatsAPI adapters.
2. Expanded MLB split/recent-form adapters.
3. Direct odds/props provider for lines.
4. Public pages only for narrative validation.

Prompt rules:

- Prefer StatsAPI values for season stats, game logs, probable pitchers, lineups, and venue context.
- Ask the LLM only to summarize or fill non-critical narrative fields when direct data is partial.

## Implementation roadmap

### Phase 1 — Documentation only

- Add this Sports Stats Bible.
- Add documentation tests so required sections and sources cannot disappear silently.
- Link future issue/PR work to this document.

### Phase 2 — Basketball direct data

- Add a BALLDONTLIE-backed NBA adapter for player stats, advanced stats, lineups, injuries, and possibly prop lines where tier permits.
- Keep LLM enrichment as fallback only.
- Add provider metadata: source, retrieved timestamp, freshness, field-level missing reasons.

### Phase 3 — NBA advanced-stats spike

- Evaluate `nba_api` for usage rate, player dashboards, tracking, and advanced splits.
- Cache IDs and stable responses aggressively.
- Treat NBA.com endpoint failures as provider-unavailable, not pipeline-crashing.

### Phase 4 — Direct props/odds provider

- Evaluate SportsGameOdds, TheOddsAPI, and OpticOdds against required sports, markets, quotas, books, and price.
- Normalize line snapshots for line movement, odds comparison, EV+, middle/arbitrage, and availability.

### Phase 5 — Soccer provider decision

- Decide whether Sportradar or another paid soccer provider is feasible.
- Use StatsBomb Open Data for tests and deterministic fixtures.
- Use football-data.org for schedules/results where sufficient.
- Keep FotMob, WhoScored, FBref, ESPN, and LiveSport as LLM grounding sources unless a permitted API path is documented.

### Phase 6 — Outlier-like research cards

- Build player trend cards from normalized stats and game logs.
- Add injury context, matchup context, line movement, and odds comparison.
- Add responsible gaming language anywhere Colmillo surfaces betting guidance.
