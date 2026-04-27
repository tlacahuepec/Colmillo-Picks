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
- CLI integration test: runs the scoring and rendering scripts as a user would from the terminal.

Run tests:

```bash
pytest -q
```

## Run the program from the CLI

Use the single-command pipeline script as the primary path:

```bash
python skills/soccer-prop-picks/scripts/run_match_pick_pipeline.py "juve - milan today" --top-n 5
```

The script parses the match query, collects schema-compatible inputs, scores props, renders the markdown report, and prints it to stdout.

`--top-n` controls how many top picks to return in the report output.

Match query format guidance: use `"home - away today"`, `"home - away tomorrow"`, or `"home - away YYYY-MM-DD"`.

### CLI arguments (`run_match_pick_pipeline.py`)

Detailed CLI argument syntax, examples, and parser-aligned error cases now live in:

- [`docs/run_match_pick_pipeline_cli.md`](docs/run_match_pick_pipeline_cli.md)

Keeping this guide in a dedicated file reduces README merge conflicts and makes parser/docs updates easier to review.

### Advanced / debug flow (manual JSON steps)

If you want to inspect each phase manually, use the step-by-step JSON workflow below.

1) Build an input payload JSON file (matching `docs/schemas/soccer_pick_input.schema.json`):

```bash
python -c 'import json; from tests.conftest import sample_match_inputs; print(json.dumps(sample_match_inputs()))' \
  > /tmp/match-input.json
```

2) Score props from the input payload:

```bash
python skills/soccer-prop-picks/scripts/score_player_props.py \
  --input-json "$(cat /tmp/match-input.json)" \
  --emit-trace > /tmp/scored-with-trace.json
```

3) Render the markdown report:

```bash
python skills/soccer-prop-picks/scripts/render_pick_report.py \
  --input-json "$(python -c 'import json; print(json.dumps(json.load(open("/tmp/scored-with-trace.json"))["scores"]))')" \
  --match-input-json "$(cat /tmp/match-input.json)" \
  --trace-json "$(python -c 'import json; print(json.dumps(json.load(open("/tmp/scored-with-trace.json"))["trace"]))')" \
  > /tmp/pick-report.md
```

4) Open the report:

```bash
cat /tmp/pick-report.md
```
