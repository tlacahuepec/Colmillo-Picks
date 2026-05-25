# MLB Data Provider Decision

**Status:** Accepted  
**Date:** 2026-05-24  
**Scope:** MLB player prop picks (v1)

## Decision

Use **MLB-StatsAPI** (`statsapi.mlb.com`) as the sole data provider for MLB v1. No odds/lines provider in v1 — prop lines are user-supplied or placeholder.

## Rationale

- Free, no API key required
- Comprehensive coverage: schedule, rosters, probable pitchers, lineups, player stats (season + game log), splits, venues
- Well-documented community usage (unofficial but stable)
- Sufficient for player-prop scoring without odds-based value signals

## Endpoint Mapping

| Data Need | Endpoint | Notes |
|-----------|----------|-------|
| Daily schedule | `GET /api/v1/schedule?sportId=1&date=YYYY-MM-DD` | Returns all MLB games for a date |
| Probable pitchers | `GET /api/v1/schedule?sportId=1&date=YYYY-MM-DD&hydrate=probablePitcher` | Pitchers attached to schedule response |
| Game feed (lineups) | `GET /api/v1.1/game/{gamePk}/feed/live` | Confirmed lineups in `liveData.boxscore.teams` |
| Player season stats | `GET /api/v1/people/{playerId}?hydrate=stats(group=[hitting,pitching],type=[season])` | Season batting/pitching splits |
| Player game log | `GET /api/v1/people/{playerId}?hydrate=stats(group=[hitting,pitching],type=[gameLog])` | Per-game stat lines |
| Player splits | `GET /api/v1/people/{playerId}?hydrate=stats(group=[hitting,pitching],type=[vsPlatoon,home,away])` | L/R, home/away splits |
| Team roster | `GET /api/v1/teams/{teamId}/roster?rosterType=active` | Active 26-man roster |
| Venue info | `GET /api/v1/venues/{venueId}` | Location, capacity, roof type |

## V1 Supported Markets

Player props only (no game-level markets):

| Market ID | Display Name | Player Type |
|-----------|-------------|-------------|
| hits | Hits | Batter |
| total_bases | Total Bases | Batter |
| runs | Runs | Batter |
| rbi | RBI | Batter |
| home_runs | Home Runs | Batter |
| strikeouts | Strikeouts | Both (batter K's or pitcher K's) |
| walks | Walks | Both |
| pitcher_outs | Pitcher Outs (Recorded) | Pitcher |

## Rate Limits

- No formal rate limit or API key requirement
- Informal community guidance: ~200 requests/minute is safe
- Strategy: cache responses aggressively
  - Schedule: 30 min TTL
  - Player stats (season): 1 hour TTL
  - Game feed (lineups): 5 min TTL (changes close to game time)
  - Venue: 24 hour TTL (static data)

## Environment Variables

None required for MLB-StatsAPI (it's free/public).

Future additions when odds provider is integrated:
- `MLB_ODDS_API_KEY` — API key for odds/lines provider (e.g., The Odds API)
- `MLB_ODDS_CACHE_TTL_SECONDS` — cache duration for odds data

## Odds Provider (Deferred)

Not included in v1. Prop lines will come from:
1. User input via the UI/API request
2. Placeholder lines for testing/development

When added (future story), The Odds API is the likely candidate:
- Covers MLB player props
- Same vendor pattern as existing sportsbook checks
- Would require paid subscription

## Data Not Available from MLB-StatsAPI

| Data | Alternative | Impact |
|------|-------------|--------|
| Betting odds/lines | User input or future odds provider | No odds-value factor in v1 scoring |
| Weather (detailed) | Future weather API or game feed `weather` field | Game feed includes basic weather; may be sufficient |
| Park factors (historical) | Hardcoded table from public sources | Static data, update annually |
| Bullpen recent usage | Derived from game logs (last 3 days) | Requires multiple API calls per reliever |

## Legal & Compliance

- MLB-StatsAPI is publicly accessible with no TOS restricting derived analysis
- No user data collection or storage needed for stat retrieval
- Responsible gaming: all picks must include uncertainty language and disclaimers
- No guaranteed outcomes — confidence labels only (low/medium/high)

## Risks

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| API structure changes without notice | Low | Pin to known response shapes; defensive parsing |
| Rate limiting under heavy load | Low | Aggressive caching, batch requests |
| Lineups not available until close to game time | Expected | Mark as unconfirmed; reduce confidence when missing |
| Weather data sparse in game feed | Medium | Basic impact only; dome detection from venue |
| Bullpen state requires multiple calls | Certain | Batch team game logs; cache per team per day |
