# Cross-source market expansion backlog

Snapshot date: 2026-09-12. This backlog compares current Colmillo markets with
market families described by authorized provider documentation. It is a
prioritization artifact; it neither claims every source offers every market nor
enables automated wagering.

## Current baseline

Colmillo supports soccer passing and shots, a broad NBA player-prop registry,
eight MLB player props, and seven NFL player props plus full-game moneyline,
spread, and total. Candidate market data must include an event/player mapping,
selection, line where applicable, price, book/platform, source URL or provider
reference, and observed time.

## Feasibility-ranked candidates

| Priority | Candidate family | Sports | Why it is useful | Required work before implementation | Decision |
| --- | --- | --- | --- | --- | --- |
| 1 | Cross-book full-game moneyline, spread, total | Soccer, basketball, MLB, NFL | Common structured market family with clear selections and prices | Generic game-bet contract, sport-specific scoring and settlement, authorized odds source | Research next; implementation needs a separate issue |
| 2 | MLB hits+runs+RBIs and alternate pitcher strikeouts | MLB | Adjacent to existing StatsAPI-backed batter and pitcher fields | Define scoring and settlement combinations; verify paid odds coverage | Candidate after a source proof of value |
| 3 | NBA double-double and alternate points/rebounds/assists | Basketball | Common cross-book prop families | Distribution-aware scoring, minutes/role confidence, player ID mapping, settlement rules | Candidate; do not add as passthrough |
| 4 | NFL completions and rushing attempts | NFL | Natural extension of the current NFL player market set | Current-season collection, strict offer validation, manual-grade policy | Candidate for the next NFL market specification |
| 5 | Soccer full-game totals, draw-no-bet, and both-teams-to-score | Soccer | More consistently available than granular soccer player props | Team/game scoring model, period rules, settlement, and source evidence | Candidate only after generic game-bet design is reused safely |
| 6 | Soccer goalscorer props | Soccer | Available from some enterprise feeds | Reliable lineup/player data, event-specific availability, strict evidence | Do not build until source evaluation passes |
| 7 | Promotions, boosts, tacos, or social signals | Any | Marketing-driven rather than stable analytic input | Permission, terms, provenance, and product-boundary review | Do not build |

## Source coverage notes

- The Odds API documents standard game markets and paid player-prop coverage;
  its player-prop availability varies by sport and tier.
- SportsGameOdds documents a unified event tree for game lines, player props,
  alternate lines, and results.
- Sportradar documents authenticated, event-dependent player-prop coverage and
  warns that live availability is not guaranteed.
- Individual sportsbook and DFS pages are not an authorized production source
  without an explicit agreement.

### PrizePicks inventory limitation

On 2026-09-12, a read-only request to the existing public projections endpoint
returned a provider processing error. Therefore this report does not claim a
complete, current PrizePicks market inventory. Close the remaining #248
acceptance only after an authorized provider response or a manually preserved,
dated platform export supplies league and stat-type observations.

## Implementation gate for every candidate

1. Create one dedicated issue per market family; do not bundle unrelated
   markets.
2. Define the canonical market, subject, selection, line, price, period,
   overtime rule, source evidence, and settlement outcome.
3. Add deterministic scoring only when all scoring inputs and an authorized
   source are available; otherwise return an explicit unavailable result.
4. Add fixture-backed collection, validation, persistence, API/UI, history,
   report, and settlement tests before enabling the market.
