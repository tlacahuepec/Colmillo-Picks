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
  - `--top-n 5`: maximum supported shortlist for this CLI.

Concrete `--top-n` examples:

```bash
python skills/soccer-prop-picks/scripts/run_match_pick_pipeline.py "juve - milan today" --top-n 3
python skills/soccer-prop-picks/scripts/run_match_pick_pipeline.py "arsenal - liverpool tomorrow" --top-n 5
python skills/soccer-prop-picks/scripts/run_match_pick_pipeline.py "real madrid - barcelona 2026-05-03" --top-n 5
```

#### Fixture lookup provider

The command resolves a real fixture before scoring. Use `--fixture-provider` or
`SOCCER_FIXTURE_PROVIDER` to choose the source:

- `llm` (default): Gemini, OpenAI, Grok/xAI, or another OpenAI-compatible LLM endpoint.
- `auto`: use fixture LLM config when complete, otherwise deterministic fallback (if allowed).

Gemini example (default — only requires `GEMINI_API_KEY`):

```bash
export GEMINI_API_KEY="your-gemini-key"

python skills/soccer-prop-picks/scripts/run_match_pick_pipeline.py \
  "arsenal - liverpool 2026-05-03" \
  --league "Premier League"
```

OpenAI example:

```bash
export SOCCER_FIXTURE_PROVIDER="llm"
export SOCCER_FIXTURE_LLM_PROVIDER="openai"
export OPENAI_API_KEY="your-openai-api-key"
export SOCCER_FIXTURE_LLM_MODEL="gpt-4.1-mini"

python skills/soccer-prop-picks/scripts/run_match_pick_pipeline.py \
  "arsenal - liverpool 2026-05-03" \
  --league "Premier League"
```

Grok/xAI example:

```bash
export SOCCER_FIXTURE_PROVIDER="llm"
export SOCCER_FIXTURE_LLM_PROVIDER="xai"
export XAI_API_KEY="your-xai-api-key"
export SOCCER_FIXTURE_LLM_MODEL="your-grok-model"

python skills/soccer-prop-picks/scripts/run_match_pick_pipeline.py \
  "arsenal - liverpool 2026-05-03" \
  --league "Premier League"
```

For another OpenAI-compatible endpoint:

```bash
export SOCCER_FIXTURE_PROVIDER="llm"
export SOCCER_FIXTURE_LLM_PROVIDER="openai-compatible"
export SOCCER_FIXTURE_LLM_API_KEY="your-provider-key"
export SOCCER_FIXTURE_LLM_BASE_URL="https://provider.example/v1"
export SOCCER_FIXTURE_LLM_MODEL="provider-model"
```

CLI overrides are also available:

```bash
python skills/soccer-prop-picks/scripts/run_match_pick_pipeline.py \
  "arsenal - liverpool 2026-05-03" \
  --league "Premier League" \
  --fixture-provider llm \
  --fixture-llm-provider openai-compatible \
  --fixture-llm-base-url "https://provider.example/v1" \
  --fixture-llm-model "provider-model"
```

#### Deterministic fallback

Fixture lookup is strict by default: if the provider cannot resolve the requested
match, the CLI exits with a clear error instead of generating synthetic data.

For local demos, tests, or offline development, opt into deterministic fallback:

```bash
python skills/soccer-prop-picks/scripts/run_match_pick_pipeline.py \
  "juve - milan today" \
  --allow-deterministic-fallback
```

`--allow-deterministic-fallback` is intentionally explicit so synthetic fixture metadata is never mistaken for live data.

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
