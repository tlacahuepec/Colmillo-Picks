# run_match_pick_pipeline.py CLI arguments

### CLI arguments (`run_match_pick_pipeline.py`)

The pipeline command is:

```bash
API_FOOTBALL_API_KEY="your-api-football-key" \
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
  - `--top-n 5`: maximum supported shortlist for this CLI.

Concrete `--top-n` examples:

```bash
python skills/soccer-prop-picks/scripts/run_match_pick_pipeline.py "juve - milan today" --top-n 3
python skills/soccer-prop-picks/scripts/run_match_pick_pipeline.py "arsenal - liverpool tomorrow" --top-n 5
python skills/soccer-prop-picks/scripts/run_match_pick_pipeline.py "real madrid - barcelona 2026-05-03" --top-n 5
```

#### API-Football fixture lookup

Fixture lookup is strict by default. The command must resolve a real API-Football fixture before scoring; otherwise it exits with a clear error and does not render deterministic match metadata.

Set `API_FOOTBALL_API_KEY` before running a strict lookup:

```bash
export API_FOOTBALL_API_KEY="your-api-football-key"
python skills/soccer-prop-picks/scripts/run_match_pick_pipeline.py "arsenal - liverpool 2026-05-03"
```

Use optional hints when a team search or date could match multiple competitions:

```bash
python skills/soccer-prop-picks/scripts/run_match_pick_pipeline.py \
  "arsenal - liverpool 2026-05-03" \
  --league "Premier League" \
  --league-id 39 \
  --season 2025
```

For local demos, tests, or offline development, opt into deterministic fallback:

```bash
python skills/soccer-prop-picks/scripts/run_match_pick_pipeline.py \
  "juve - milan today" \
  --allow-deterministic-fallback
```

`--allow-deterministic-fallback` is intentionally explicit so synthetic fixture metadata is never mistaken for live API-Football data.

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
