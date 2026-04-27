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

### CLI arguments (`run_match_pick_pipeline.py`)

The pipeline command is:

```bash
python skills/soccer-prop-picks/scripts/run_match_pick_pipeline.py "<match_query>" [--top-n N]
```

#### Positional argument: `match_query`

`match_query` must follow:

```text
<home> - <away> <date>
```

Accepted `<date>` tokens are:

- `today`
- `tomorrow`
- `YYYY-MM-DD` (ISO date, e.g. `2026-05-03`)

Examples:

```bash
python skills/soccer-prop-picks/scripts/run_match_pick_pipeline.py "juve - milan today"
python skills/soccer-prop-picks/scripts/run_match_pick_pipeline.py "arsenal - liverpool tomorrow"
python skills/soccer-prop-picks/scripts/run_match_pick_pipeline.py "real madrid - barcelona 2026-05-03"
```

#### Optional argument: `--top-n`

- Meaning: number of ranked picks rendered in the report output.
- Default: `5`.
- Practical guidance:
  - `--top-n 3`: compact shortlist when you only want the strongest calls.
  - `--top-n 5`: balanced default for most runs (signal + some diversity).
  - `--top-n 8` or higher: broader scan for research/debug sessions (includes lower-ranked options).

Concrete `--top-n` examples:

```bash
python skills/soccer-prop-picks/scripts/run_match_pick_pipeline.py "juve - milan today" --top-n 3
python skills/soccer-prop-picks/scripts/run_match_pick_pipeline.py "arsenal - liverpool tomorrow" --top-n 5
python skills/soccer-prop-picks/scripts/run_match_pick_pipeline.py "real madrid - barcelona 2026-05-03" --top-n 8
```

#### Error examples (parser behavior)

Malformed query format (missing ` - ` separator):

```text
Input: juve vs milan today
Error: Invalid match query format. Expected e.g. 'juve - milan today' or 'juve - milan 2026-05-03'.
```

Invalid date token / format (not `today`, `tomorrow`, or `YYYY-MM-DD`):

```text
Input: juve - milan friday
Error: Invalid match query format. Expected e.g. 'juve - milan today' or 'juve - milan 2026-05-03'.
```

Invalid ISO date value (matches pattern but is not a real date):

```text
Input: juve - milan 2026-99-99
Error: Invalid match date. Use 'today', 'tomorrow', or YYYY-MM-DD format.
```

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
