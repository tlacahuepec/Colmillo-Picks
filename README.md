# Colmillo-Picks

AI-powered soccer prop pick assistant — generates ranked picks with confidence levels, risk flags, and platform availability checks.

## Quickstart

```bash
git clone https://github.com/tlacahuepec/Colmillo-Picks.git && cd Colmillo-Picks
pip install -r requirements.txt
export GEMINI_API_KEY="your-gemini-key"
python skills/soccer-prop-picks/scripts/run_match_pick_pipeline.py "arsenal - liverpool today"
```

PowerShell (Windows) equivalent:

```powershell
$env:GEMINI_API_KEY = "your-gemini-key"
python skills/soccer-prop-picks/scripts/run_match_pick_pipeline.py "arsenal - liverpool today"
```

## What it does

1. **Parse** — Extracts teams, date, and competition from a natural-language match query
2. **Fixture lookup** — Resolves the real match via LLM (Gemini by default)
3. **Collect inputs** — Gathers lineups, odds, weather into a schema-validated payload
4. **Score** — Deterministic weighted scoring of player props (passes, shots)
5. **Report** — Renders a markdown report with top picks, evidence, and risk flags

## Project structure

```
skills/soccer-prop-picks/
  scripts/
    run_match_pick_pipeline.py   Single-command CLI entry point
    collect_match_inputs.py      Schema-validated input assembly
    score_player_props.py        Deterministic scoring engine
    render_pick_report.py        Markdown report renderer
    dependency_bundle.py         Provider wiring (shared by CLI + API)
    llm/                         LLM client adapters (Gemini, Grok, OpenAI)
    llm_fixture_provider.py      LLM-based fixture resolution
  templates/
    pick_report.md               Output contract template
services/
  api/                           FastAPI REST service
  ui/                            Streamlit web UI
tests/                           pytest suite
```

## Configuration

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| `GEMINI_API_KEY` | **Yes** | — | LLM provider for fixture lookup and enrichment |
| `COLMILLO_API_KEY` | For HTTP service | — | API authentication (X-API-Key header) |
| `OPENAI_API_KEY` | No | — | Alternative LLM provider |
| `XAI_API_KEY` | No | — | Grok/xAI LLM provider |
| `COLMILLO_DB_PATH` | For HTTP service | `/var/data/colmillo.db` | SQLite persistence path |
| `COLMILLO_UI_ORIGIN` | No | — | CORS allowlist for UI |
| `COLMILLO_RATE_LIMIT_PER_HOUR` | No | `30` | Per-key request quota (0 = disabled) |

See `.env.example` for the complete list with descriptions.

## Running tests

```bash
pytest -q
```

## CLI usage

```bash
# Basic usage (requires GEMINI_API_KEY)
python skills/soccer-prop-picks/scripts/run_match_pick_pipeline.py "juve - milan today"

# With options
python skills/soccer-prop-picks/scripts/run_match_pick_pipeline.py \
  "arsenal - liverpool 2026-05-03" \
  --league "Premier League" \
  --top-n 3

# Offline/demo mode (no API key needed)
python skills/soccer-prop-picks/scripts/run_match_pick_pipeline.py \
  "juve - milan today" --allow-deterministic-fallback
```

PowerShell example (force LLM for fixture lookup + enrichment):

```powershell
$env:GEMINI_API_KEY = "your-gemini-key"
python skills/soccer-prop-picks/scripts/run_match_pick_pipeline.py "bayern munich - vfb stuttgart 2026-05-23" --fixture-provider llm --fixture-llm-provider gemini --use-llm --llm-provider gemini
```

### Smart run modes

Use the mode that matches your intent:

| Intent | Command shape |
|---|---|
| Fast deterministic demo (no API key) | `python ... --allow-deterministic-fallback` |
| LLM for fixture lookup only | `python ... --fixture-provider llm --fixture-llm-provider gemini` |
| LLM for fixture lookup + pick enrichment | `python ... --fixture-provider llm --fixture-llm-provider gemini --use-llm --llm-provider gemini` |

Windows PowerShell quick checks before running:

```powershell
if ($env:GEMINI_API_KEY) { "GEMINI_API_KEY is set" } else { "GEMINI_API_KEY is NOT set" }
```

Verify LLM enrichment ran by checking the report includes:

- `LLM status: success`
- `provider=gemini`
- `latency_ms=` with a value greater than `0`

If you see `LLM status: not_requested`, run included only deterministic scoring for explanation text. Add `--use-llm --llm-provider gemini`.

If provider status shows fixture success but lineups still look generic/projected, check key availability in the same terminal session and rerun with explicit fixture flags.

`--top-n` controls how many top picks to return in the report (1–5, default 5).

Match query format: `"home - away today|tomorrow|YYYY-MM-DD"`

Full CLI reference: [`docs/run_match_pick_pipeline_cli.md`](docs/run_match_pick_pipeline_cli.md)

## HTTP service (optional)

The pipeline is also available as a REST API + Streamlit UI:

```bash
cp .env.example .env   # fill in COLMILLO_API_KEY + GEMINI_API_KEY
uvicorn services.api.main:app --reload --port 8000   # API
streamlit run services/ui/app.py                      # UI (separate terminal)
```

### API surface

All routes except `/healthz` require `X-API-Key`. `POST /picks` is async (returns 202, poll for completion).

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/healthz` | Health check + configured providers |
| POST | `/picks` | Enqueue a pick run → `202 {id, status}` |
| GET | `/picks` | Paginated history |
| GET | `/picks/{id}` | Full payload + report |
| GET | `/picks/{id}/status` | Lightweight polling endpoint |
| POST | `/picks/{id}/outcomes` | Record outcomes (win/loss/push/void) |
| GET | `/stats/hit-rate` | Aggregate hit rate stats |
| GET | `/admin/stats` | Operational stats (requires X-Admin-API-Key) |

## Deployment

### Docker

```bash
cp .env.example .env
docker compose up --build
```

### Render

The repo includes `render.yaml` (Render Blueprint) for one-click deployment:

1. Push to GitHub
2. Render → New → Blueprint → connect repo
3. Set secrets in dashboard: `COLMILLO_API_KEY`, `GEMINI_API_KEY`
4. Auto-deploys on push to `main`
