# NFL support specification

Approved scope: NFL regular season and postseason, full-game pregame markets.
Player markets: passing_yards, passing_touchdowns, interceptions_thrown,
rushing_yards, receiving_yards, receptions, anytime_touchdown.
Game markets: moneyline, spread, total. No preseason, live or partial-game bets.

Use existing grounded AI collection; no new data subscription. Every offer must
include a sportsbook, decimal price, selection, source URL and observed timestamp.
Keep line and price from the same offer; choose the best price for duplicates.
Unknown inputs stay null. Missing evidence produces exclusions or an explicit
no-picks report, never sample players or invented odds.

NFL picks carry subject_type, subject_name, selection and offer metadata while
retaining player as a compatibility display label. Moneyline and anytime TD have
null lines; spread supports signed numbers including zero. Persist metadata in
existing JSON columns. Reports and slates display subjects and sportsbook details.
NFL is manually graded and excluded from automatic player-stat settlement.

Acceptance: NFL discovery, Generate, Best Today, history and manual grading work;
other sports retain their behavior. Tests cover all markets, missing evidence,
invalid offers, inactive players, byes, prior-season samples, kickoff boundaries,
mixed slates and persistence. Run Ruff and the full pytest suite, plus a UI smoke
and live collection attempt when credentials are available.

## Implementation details

- Dates use the request's IANA timezone, then `COLMILLO_TIMEZONE`, then
  `America/Chicago` for NFL. Evening games may start on the next UTC day.
- Offer validation requires full-game, primary, pregame, overtime-inclusive lines,
  a finite decimal price greater than one, and an observed timestamp within 24
  hours (up to five minutes clock skew). Moneylines and anytime TD use null lines;
  spreads are signed for the selected team. Anytime TD supports the offered yes side.
- Provider search citations must support returned source URLs. Google citation
  redirects are resolved without following their external destination. Search
  query links alone are not evidence. Currently the Gemini adapter exposes these
  citations; adapters without them produce explicit no-picks results.
- Gemini first researches in prose with search citations, then extracts JSON in a
  separate request without search. Original source mappings and research text are
  retained in the trace. Context, game offers and player offers are separate
  stages; an unavailable offer group does not discard another group's results.
  Exact citation matches avoid extra redirect requests. Research/extraction calls
  use a timeout of at least 60 seconds, and all calls contribute to token counts.
- Player scoring uses mean production in the last five eligible games against
  the selected line, with opportunity, matchup and availability factors. Anytime
  TD uses games with a scored touchdown, excluding passing TDs. Small samples,
  prior-season inputs and missing context reduce confidence.
- Team projected scoring blends season (40%) and recent (60%) offense/defense,
  averages each offense with its opponent's defense, and adds 1.5 points for home
  advantage unless the venue is neutral. Margin and total support the offered
  direction, with availability, rest and weather factors. NFL scores are heuristic
  rankings, not calibrated probabilities or expected value; odds select the best
  price among otherwise identical offers. No high-confidence tier is assigned.
- Weights and thresholds live in `config.nfl_scoring.json`. The minimum score is
  0.55; clean inputs scoring at least 0.65 receive medium confidence.
- The main API continues using its existing JSON payload columns. The separate
  run ledger adds an idempotent `source_pick_json` column to preserve offer metadata
  and null lines. Its legacy numeric column remains compatible with old rows;
  readers prefer the JSON line when present. Existing rows require no backfill.

## Smoke test

```powershell
.venv/Scripts/python.exe scripts/smoke_nfl.py --date 2026-09-13 --timezone America/Chicago
```

Supply `--home` and `--away` to analyze a specific matchup. The script uses the
configured provider and writes public discovery/analysis/report artifacts under
ignored `data/nfl-smoke`; it does not touch app history. Exit 0 means picks were
produced; exit 2 means no qualifying data or a provider limitation. A no-picks
response is a valid application result, not evidence of a successful live pick.

## Validation recorded on 2026-09-11

- Full pytest suite: 1,530 passed, including 57 NFL-focused tests.
- Ruff and whitespace checks passed. Streamlit AppTest verified immediate sport
  switching and the NFL market groups; API tests verified reports, history,
  mixed-sport slates, nullable lines, migration compatibility and manual grading.
- Live research verified an upcoming matchup and sourced context. A focused
  game-odds collection returned 23 offers passing citation and offer validation;
  nine uncited offers were excluded. The sampled matchup lacked sufficient
  statistics for ranked recommendations, and an earlier player-offer request hit
  a provider server error. A complete live ranked-pick result remains unverified.
  Latest evidence is in `data/nfl-smoke-2026-09-13/game-offers.json`; successful
  recommendation tests use controlled fixtures.
