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

Use the single-command pipeline script as the primary path. For current-season
matches, the fixture lookup can use an LLM provider instead of API-Football:

```bash
export SOCCER_FIXTURE_PROVIDER="llm"
export SOCCER_FIXTURE_LLM_PROVIDER="openai"
export OPENAI_API_KEY="your-openai-api-key"
export SOCCER_FIXTURE_LLM_MODEL="gpt-4.1-mini"

python skills/soccer-prop-picks/scripts/run_match_pick_pipeline.py \
  "arsenal - liverpool 2026-05-03" \
  --league "Premier League" \
  --season 2025
```

Grok/xAI or another OpenAI-compatible endpoint can use the same fixture provider
contract:

```bash
export SOCCER_FIXTURE_PROVIDER="llm"
export SOCCER_FIXTURE_LLM_PROVIDER="xai"
export XAI_API_KEY="your-xai-api-key" # GROK_API_KEY also works
export SOCCER_FIXTURE_LLM_MODEL="your-grok-model"

python skills/soccer-prop-picks/scripts/run_match_pick_pipeline.py \
  "arsenal - liverpool 2026-05-03" \
  --league "Premier League"
```

For legacy API-Football lookup, keep using:

```bash
export API_FOOTBALL_API_KEY="your-api-football-key"
python skills/soccer-prop-picks/scripts/run_match_pick_pipeline.py "juve - milan today" --top-n 5
```

The script parses the match query, retrieves fixture metadata from the selected
fixture provider, collects schema-compatible inputs, scores props, renders the
markdown report, and prints it to stdout.

`--top-n` controls how many top picks to return in the report output.

Match query format guidance: use `"home - away today"`, `"home - away tomorrow"`, or `"home - away YYYY-MM-DD"`.

Fixture retrieval is strict by default: if the selected fixture provider cannot
resolve the requested match, the CLI exits with a clear error instead of
generating a synthetic report. For local demos or tests, opt into the
deterministic fallback path explicitly:

```bash
python skills/soccer-prop-picks/scripts/run_match_pick_pipeline.py "juve - milan today" --allow-deterministic-fallback
```

Use API-Football hints when team names or competitions are ambiguous:

```bash
python skills/soccer-prop-picks/scripts/run_match_pick_pipeline.py \
  "arsenal - liverpool 2026-05-03" \
  --league "Premier League" \
  --league-id 39 \
  --season 2025
```

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

## Run the program as an HTTP service (FastAPI + Streamlit)

The same pipeline is exposed as a small REST API plus a Streamlit UI so you
can share Colmillo-Picks with friends without giving them shell access. See
[CHANGELOG.md](CHANGELOG.md) for the full v0.2.0 surface.

### Configure

Copy `.env.example` to `.env` and fill in at minimum:

- `COLMILLO_API_KEY` — required; clients send it as the `X-API-Key` header.
- `API_FOOTBALL_API_KEY` and/or one of `OPENAI_API_KEY` / `XAI_API_KEY` —
  whatever the fixture and LLM providers you intend to use require.
- `COLMILLO_DB_PATH` — where to persist SQLite. In Docker this defaults to
  `/var/data/colmillo.db` (the persistent disk mount).

Optional but recommended:

- `COLMILLO_UI_ORIGIN` — comma-separated CORS allowlist (e.g. the UI host).
- `COLMILLO_RATE_LIMIT_PER_HOUR` — per-key request quota; default `30`.
  Set to `0` to disable.
- `COLMILLO_ADMIN_API_KEY` — required to call `GET /admin/stats` (sent as
  the `X-Admin-API-Key` header, in addition to `X-API-Key`).
- `SENTRY_DSN` — enables Sentry error reporting. The SDK is already in
  `requirements.txt`; just set the DSN.

### Run locally

API:

```bash
uvicorn services.api.main:app --reload --port 8000
```

UI (in a second terminal):

```bash
streamlit run services/ui/app.py
```

The UI defaults to talking to `http://localhost:8000`. Override with
`COLMILLO_API_URL` if needed.

### REST API surface

All routes (except `/healthz`) require the `X-API-Key` header. `POST /picks`
is **asynchronous** — it returns `202` immediately and the client polls for
completion.

| Method | Path                            | Purpose                                           |
| ------ | ------------------------------- | ------------------------------------------------- |
| GET    | `/healthz`                      | Open. Reports configured providers (no secrets). |
| POST   | `/picks`                        | Enqueue a pick run. Returns `202 {id, status, created_at}`. |
| GET    | `/picks`                        | Paginated history (`limit`, `offset`).            |
| GET    | `/picks/{id}`                   | Full payload + `status`, `error_*` if failed.     |
| GET    | `/picks/{id}/status`            | Lightweight `{status, error_stage, error_message, latency_ms}` for polling. |
| POST   | `/picks/{id}/outcomes`          | Record per-pick outcomes (`win|loss|push|void`). 201. |
| GET    | `/picks/{id}/outcomes`          | List recorded outcomes.                           |
| GET    | `/stats/hit-rate?since=...`     | Aggregate counts and `hit_rate` (`win / (win + loss)`). |
| GET    | `/admin/stats`                  | Operational stats. Requires `X-Admin-API-Key`.    |

Async flow with `curl`:

```bash
# Submit a pick
ID=$(curl -s -H "X-API-Key: $COLMILLO_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"match_query":"juve - milan today","top_n":3}' \
  http://localhost:8000/picks | jq -r .id)

# Poll until terminal
while true; do
  STATUS=$(curl -s -H "X-API-Key: $COLMILLO_API_KEY" \
    http://localhost:8000/picks/$ID/status | jq -r .status)
  [ "$STATUS" = "success" ] || [ "$STATUS" = "failed" ] && break
  sleep 1
done

# Fetch the full payload
curl -s -H "X-API-Key: $COLMILLO_API_KEY" http://localhost:8000/picks/$ID | jq
```

The UI (`services/ui/app.py`) wraps this loop in
`PicksAPIClient.wait_for_pick(...)` and shows a spinner while polling.

Errors surface in two places:

- **Synchronous 4xx** on `POST /picks` — request validation (`422`),
  unsupported LLM combination (`400`), missing provider credentials (`400`).
- **Asynchronous `failed` status** — anything that goes wrong inside the
  pipeline (parse, collect, score, llm). Inspect `error_stage` and
  `error_message` via `GET /picks/{id}/status`.

Rate-limited clients receive `429` with a `Retry-After` header.

## Run with Docker

`docker-compose.yml` builds both images and wires them with a named volume
for the SQLite database:

```bash
cp .env.example .env  # then fill in COLMILLO_API_KEY etc.
docker compose up --build
```

The API is then on `http://localhost:8000` and the UI on
`http://localhost:8501`.

## Deploy to Render

`render.yaml` is a Render Blueprint defining two `runtime: docker` web
services (`colmillo-api`, `colmillo-ui`) on the `starter` plan plus a
1 GiB persistent disk for SQLite.

1. Push the repo to GitHub.
2. In Render: **New → Blueprint → connect repo**.
3. Set the secret env vars in the dashboard (`COLMILLO_API_KEY`,
   `API_FOOTBALL_API_KEY`, `OPENAI_API_KEY` / `XAI_API_KEY`,
   `COLMILLO_ADMIN_API_KEY`, optionally `SENTRY_DSN`).
4. Render auto-deploys on every push to `main`.

The UI service receives the API URL via Render's `fromService` lookup, so
you don't need to hard-code anything.

## Project layout (HTTP service)

```
services/
  api/
    main.py             FastAPI app + routes
    db.py               SQLAlchemy models + helpers (PickRun, PickOutcome)
    middleware.py       Auth, admin gate, rate limit, request logging
    rate_limit.py       In-memory token bucket
    sentry.py           Optional Sentry init
    logging_config.py   JSON log formatter
  ui/
    app.py              Streamlit Generate + History pages
    api_client.py       httpx client used by the UI and tests
tests/
  api/                  FastAPI route + persistence tests
  ui/                   API client tests (httpx.MockTransport → TestClient)
```


