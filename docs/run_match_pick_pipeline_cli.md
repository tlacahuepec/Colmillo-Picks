# run_match_pick_pipeline.py CLI arguments

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
