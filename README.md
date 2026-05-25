# Colmillo-Picks

This project follows the [Engineering Constitution](https://github.com/tlacahuepec/Constitution).

AI-powered soccer prop pick assistant — generates ranked player prop picks with confidence levels, risk flags, grounding sources, and platform availability checks.

## Quickstart (CLI)

```bash
git clone https://github.com/tlacahuepec/Colmillo-Picks.git && cd Colmillo-Picks
pip install -r requirements.txt
cp .env.example .env       # add your GEMINI_API_KEY
python skills/soccer-prop-picks/scripts/run_match_pick_pipeline.py "arsenal - liverpool today"
```

PowerShell:

```powershell
$env:GEMINI_API_KEY = "your-gemini-key"
python skills/soccer-prop-picks/scripts/run_match_pick_pipeline.py "arsenal - liverpool today"
```

## How it works

1. **Parse** — Extracts teams, date, and competition from a natural-language match query
2. **Fixture lookup** — Resolves the real match via Gemini with search grounding
3. **Collect inputs** — Gathers lineups, odds, weather into a schema-validated payload
4. **Score** — Deterministic weighted scoring of player props (passes, shots)
5. **LLM enrich** (optional) — Gemini adds rationale, tactical fit, risk narratives
6. **Report** — Renders a markdown report with top picks, evidence, sources, and risk flags

## Local development (UI + API)

Both services auto-load `.env` from the project root via `python-dotenv`. No manual env exporting needed.

### Setup

```bash
pip install -r requirements.txt
cp .env.example .env
# Edit .env: add your GEMINI_API_KEY and set COLMILLO_API_KEY to any string
```

### Run

Open two terminals from the project root:

**Terminal 1 — API (port 8000):**

```bash
uvicorn services.api.main:app --reload --port 8000
```

```powershell
uvicorn services.api.main:app --reload --port 8000
```

**Terminal 2 — UI (port 8501):**

```bash
streamlit run services/ui/app.py --server.port 8501
```

```powershell
streamlit run services/ui/app.py --server.port 8501
```

Then open:
- **UI:** http://localhost:8501
- **API docs (Swagger):** http://localhost:8000/docs

## Project structure

```
skills/soccer-prop-picks/
  scripts/
    run_match_pick_pipeline.py   CLI entry point
    collect_match_inputs.py      Schema-validated input assembly
    score_player_props.py        Deterministic scoring engine
    render_pick_report.py        Markdown report renderer
    dependency_bundle.py         Provider wiring (shared by CLI + API)
    llm/                         LLM client adapters (Gemini, Grok, OpenAI)
    llm_fixture_provider.py      LLM-based fixture resolution
    llm_lineup_provider.py       LLM-based lineup resolution
    llm_odds_provider.py         LLM-based odds resolution
services/
  api/                           FastAPI REST service (port 8000)
  ui/                            Streamlit web UI (port 8501)
  worker/                        Optional background job processor
templates/
  pick_report.md                 Report output template
tests/                           pytest suite (~250 tests)
```

## Configuration

All config is via environment variables. Copy `.env.example` to `.env` and fill in your keys.

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| `GEMINI_API_KEY` | **Yes** | — | Gemini LLM (fixture lookup, enrichment, grounding) |
| `COLMILLO_API_KEY` | For services | — | API authentication (`X-API-Key` header) |
| `COLMILLO_DB_PATH` | For services | `./colmillo.db` | SQLite database path |
| `COLMILLO_API_URL` | For UI | `http://localhost:8000` | Where UI sends requests |
| `COLMILLO_UI_ORIGIN` | For API | `http://localhost:8501` | CORS allowlist |
| `OPENAI_API_KEY` | No | — | Alternative LLM provider |
| `XAI_API_KEY` | No | — | Grok/xAI LLM provider |
| `COLMILLO_RATE_LIMIT_PER_HOUR` | No | `30` | Per-key request quota |

See `.env.example` for the full list.

## CLI usage

```bash
# Basic (requires GEMINI_API_KEY in .env or environment)
python skills/soccer-prop-picks/scripts/run_match_pick_pipeline.py "juve - milan today"

# With options
python skills/soccer-prop-picks/scripts/run_match_pick_pipeline.py \
  "arsenal - liverpool 2026-05-03" \
  --league "Premier League" \
  --top-n 3

# Offline/demo mode (no API key needed)
python skills/soccer-prop-picks/scripts/run_match_pick_pipeline.py \
  "juve - milan today" --allow-deterministic-fallback

# Full LLM pipeline (fixture + enrichment + search grounding)
python skills/soccer-prop-picks/scripts/run_match_pick_pipeline.py \
  "bayern munich - vfb stuttgart 2026-05-23" \
  --fixture-provider llm --fixture-llm-provider gemini \
  --use-llm --llm-provider gemini
```

Match query format: `"home - away today|tomorrow|YYYY-MM-DD"`

`--top-n` controls how many top picks to return in the report (1–5, default 5).

### Smart run modes

| Intent | Flags |
|--------|-------|
| Fast demo (no API key) | `--allow-deterministic-fallback` |
| LLM fixture lookup only | `--fixture-provider llm --fixture-llm-provider gemini` |
| Full LLM (fixture + enrichment) | `--fixture-provider llm --fixture-llm-provider gemini --use-llm --llm-provider gemini` |

Verify LLM enrichment ran by checking the report includes:

- `LLM status: success`
- `provider=gemini`
- `latency_ms=` with a value greater than `0`

If you see `LLM status: not_requested`, the run included only deterministic scoring. Add `--use-llm --llm-provider gemini` to enable LLM enrichment.

### Debug fixture LLM

```powershell
$env:COLMILLO_FIXTURE_LLM_DEBUG = "1"
python skills/soccer-prop-picks/scripts/run_match_pick_pipeline.py "..." 2> fixture-debug.log
```

### Debug grounding sources

```powershell
$env:COLMILLO_DEBUG_GROUNDING = "1"
python skills/soccer-prop-picks/scripts/run_match_pick_pipeline.py "..." 2> grounding-debug.log
```

## API surface

All routes except `/healthz` require `X-API-Key`. `POST /picks` is async (returns 202, poll for completion).

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/healthz` | Health check + configured providers |
| POST | `/picks` | Enqueue a pick run (returns `202 {id, status}`) |
| GET | `/picks` | Paginated history |
| GET | `/picks/{id}` | Full payload + report |
| GET | `/picks/{id}/status` | Lightweight polling |
| POST | `/picks/{id}/outcomes` | Record outcomes (win/loss/push/void) |
| GET | `/stats/hit-rate` | Aggregate hit rate |
| GET | `/admin/stats` | Operational stats (requires `X-Admin-API-Key`) |

## Running tests

```bash
pytest -q
```

## Docker

Docker Compose packages both services for deployment. Useful for CI or if you don't want to manage Python locally.

```bash
cp .env.example .env   # fill in keys
docker compose up --build
```

The compose file overrides `COLMILLO_DB_PATH` and `COLMILLO_API_URL` to use container-internal paths and networking.

## Deployment (Render)

The repo includes `render.yaml` (Render Blueprint):

1. Push to GitHub
2. Render > New > Blueprint > connect repo
3. Set secrets in dashboard: `COLMILLO_API_KEY`, `GEMINI_API_KEY`
4. Auto-deploys on push to `main`

## Contributing

See the [Contributor Playbook](docs/contributor-playbook.md) for branching strategy,
release process, and agent development workflow.
