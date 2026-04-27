# Colmillo-Picks

Colmillo Picks is an AI-powered soccer assistant that generates smart picks with clear reasoning, confidence levels, and risk insights.

## Current repo coverage against the core soccer principles

This repo now represents the key principles for soccer prop-pick analysis:

- Lineups, injuries/suspensions, home/away context, standings, weather, and match format are all represented in the structured input schema and reporting template.
- Possession style and opponent style are explicitly modeled in scoring to support passes projections.
- Player reliability (expected minutes, substitution risk, role, lone striker context) is included for passes/shots recommendations.
- Odds consensus logic supports multi-book agreement checks.
- Guardrails enforce freshness timestamps and flag unconfirmed lineups or stale odds.
- Output includes top 5 picks with confidence, risk flags, and availability checks for PrizePicks + alternatives.

## Core implementation

- `skills/soccer-prop-picks/scripts/score_player_props.py`: deterministic, weighted scoring engine for passes/shots picks.
- `skills/soccer-prop-picks/scripts/render_pick_report.py`: final report renderer with match summary, evidence table, picks table, and availability section.
- `templates/pick_report.md`: required output contract template.

## Testing

This repository includes both unit tests and an integration test:

- Unit tests: scoring behavior and report rendering.
- Integration test: end-to-end flow from scoring to report generation.

Run tests:

```bash
pytest -q
```
