# Cross-source market research

Snapshot date: 2026-09-12. This is a planning inventory, not authorization to
subscribe to a service, scrape a site, place a wager, or use a source outside
its contract and terms.

## Decision

Use a **stats-first, LLM-second** pipeline. A direct, authorized data API may
provide fixture identity, lines, prices, timestamps, player identifiers, and
settlement inputs. Gemini grounding remains for narrative context and for
fields not available from a direct source. Missing evidence stays null and
never becomes an inferred line or price.

The current default remains the existing MLB StatsAPI path, the existing
PrizePicks availability adapter, and grounded NFL offers. No new commercial
provider is selected by this research.

## Source decision matrix

| Source category | Representative | Coverage and useful fields | Access and operating constraint | Recommendation |
| --- | --- | --- | --- | --- |
| Existing direct stats | MLB StatsAPI | MLB schedules, rosters, box scores, player statistics, probable pitchers | Existing free adapter; no odds | Keep as the authoritative MLB stats and settlement input |
| DFS platform | PrizePicks | Availability and platform lines when exposed by the existing adapter | Public payload shape is not a stable documented vendor contract | Keep availability-only; do not treat it as a universal odds feed |
| DFS platform | Underdog / Sleeper | Pick'em projections and promotions vary by jurisdiction and product | No authorized project integration or stable public contract verified | Manual product research only; no collection adapter |
| Odds aggregator | [The Odds API](https://theoddsapi.com/docs/) | Standard game markets, event IDs, bookmaker prices, selected player props, history on paid tiers | API key and plan required; player-prop and historical coverage are tiered | First commercial candidate for a bounded proof of value; do not integrate without budget approval |
| Odds aggregator | [SportsGameOdds](https://sportsgameodds.com/player-props-odds-api) | Event tree with cross-book game lines, player props, alternate lines, scores and results | API key, plan, coverage, and update interval must be contracted and measured | Evaluate as the broadest all-in-one comparison candidate after The Odds API |
| Enterprise odds feed | [Sportradar Odds Comparison](https://developer.sportradar.com/odds/reference/oc-player-props-overview) | Pre-match player props, book, market, price, player/event IDs, change log and selected global coverage | Authentication and commercial access required; coverage is event-dependent | Enterprise option only; retain for later procurement, not a near-term integration |
| Enterprise odds feed | [OpticOdds](https://developer.opticodds.com/docs/opticodds-mcp-integration-guide) | Fixtures, markets, sportsbook comparisons, player props, injuries, results, and line history | Commercial account and integration review required | Evaluate only if lower-cost candidates fail required coverage |
| Individual sportsbook | Named sportsbook sites | Published prices and promotions | No general authorized API; terms and automation rules differ by operator | Grounding or manual evidence only; never scrape as a production dependency |

## Sport coverage and recommended source order

| Sport | Direct data first | Market comparison candidate | LLM role | Current recommendation |
| --- | --- | --- | --- | --- |
| Soccer | Authorized schedule/stat provider when available | Aggregator for full-game markets | Lineups, injuries, tactical context | Keep player-prop expansion blocked until a reliable structured player-stat source is approved |
| Basketball | Official/free statistics where coverage permits | Aggregator for game lines and player props | Role, rotation, and injury narrative | Evaluate only markets with a source-backed stat and price contract |
| MLB | Existing MLB StatsAPI | Aggregator for cross-book lines and non-core prop comparison | Narrative-only gaps | Preserve StatsAPI as the settlement authority |
| NFL | Official schedule/injury sources plus grounded evidence | Aggregator for game lines and in-season player props | Availability and context corroboration | Preserve strict offer citation and manual grading until a contract is approved |

## Replace-or-supplement map

| Current collection responsibility | Direct-source opportunity | Guardrail |
| --- | --- | --- |
| LLM fixture and game-offer discovery | Authorized odds API event and market endpoints | Retain source timestamp, provider ID, book, selection, line, and price as one observation |
| LLM player-prop discovery | Authorized player-prop endpoint | Reject absent player/event mapping and stale observations; do not normalize ambiguous player names |
| LLM market context | Stats API or odds API only where the exact field is supplied | Keep grounding for qualitative context, never for invented numerical fields |
| Player-stat settlement | MLB StatsAPI today; sport-specific official source later | Never grade against an odds-provider value alone |

## Procurement gate

Before any adapter is implemented, run a time-boxed authorized evaluation with
one sport, documented quota, representative fixtures, freshness measurements,
event/player ID match rate, market coverage, cost, and redacted sample
responses. Integration requires explicit budget approval and a separate issue.

