# Changelog

All notable changes to Colmillo-Picks are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project
adheres to [Semantic Versioning](https://semver.org/).

## [0.2.0] — 2026-05-10

The MVP iteration: the deterministic CLI pipeline is now wrapped in a
FastAPI service, fronted by a Streamlit UI, persisted in SQLite, and
deployable to Render (or any container host) via Docker. Auth is a single
shared `X-API-Key`. See [README.md](README.md) for usage.

### Added — Phase A · Service-ize the pipeline (Stories 1–3)

- New `services/api/main.py` FastAPI app exposing the pick pipeline as HTTP.
  - `POST /picks` — accepts `match_query`, optional `league`/`league_id`/`season`,
    `top_n`, `use_llm`/`llm_provider`/`llm_model`, fixture provider overrides,
    and `allow_deterministic_fallback`.
  - `GET /healthz` — open endpoint reporting which provider credentials are
    configured (boolean flags, no secret values).
  - `GET /picks` and `GET /picks/{id}` — list and replay persisted runs.
- Extracted `build_dependency_bundle` from the CLI into
  `skills/soccer-prop-picks/scripts/dependency_bundle.py` so both CLI and
  HTTP entry points share the same dependency factory without argparse
  side effects.
- `services/api/middleware.py`:
  - `APIKeyAuthMiddleware` — fails closed (503) when `COLMILLO_API_KEY` is
    unset; rejects mismatched keys with 401. Bypasses `/healthz`, `/docs`,
    `/openapi.json`, `/redoc`.
  - `RequestLoggingMiddleware` — emits one structured JSON log per request
    with `request_id`, `method`, `path`, `status_code`, `latency_ms`. Echoes
    inbound `X-Request-Id` headers back on the response.
- `services/api/logging_config.py` — `JsonFormatter` that promotes `extra=`
  fields to top-level JSON keys; `configure_json_logging()` is idempotent.
- CORS middleware activates only when `COLMILLO_UI_ORIGIN` is set
  (comma-separated allowlist).
- `services/api/db.py` — SQLAlchemy 2.0 model `PickRun` (table
  `picks_history`) on SQLite. `configure_engine()` rebuilds the global
  engine for tests; `init_db()` runs `create_all` at app startup.
  `_safe_request_payload` strips auth-related keys before persisting.

### Added — Phase B · Streamlit UI (Stories 4–5)

- `services/ui/api_client.py` — synchronous httpx client
  (`PicksAPIClient`, `APIClientConfig`, `APIError`). Reads `COLMILLO_API_URL`,
  `COLMILLO_API_KEY`, `COLMILLO_API_TIMEOUT` from env. Raises `APIError`
  with the API's `detail` payload on non-2xx responses.
- `services/ui/app.py` — single-file Streamlit app with sidebar nav between
  **Generate** and **History** pages.
  - Generate: form with match query, league, season, top-N slider, fixture
    provider radio, deterministic fallback toggle, optional LLM block.
  - History: paginated list of past runs with per-row status badges; clicking
    a row replays the stored markdown without re-running the pipeline.

### Added — Phase C · Deployable (Stories 6–7)

- `Dockerfile.api` and `Dockerfile.ui` (both `python:3.11-slim`).
- `docker-compose.yml` with `api` + `ui` services, named volume
  `colmillo-data` mounted at `/var/data`, and a healthcheck on `/healthz`.
- `render.yaml` — Render Blueprint for two `runtime: docker` web services
  on the `starter` plan with a 1 GiB persistent disk for SQLite. UI receives
  the API URL via `fromService` resolution.
- `.github/workflows/ci.yml` — GitHub Actions:
  - `test` job: Python 3.11 + `pytest -q`.
  - `docker-build` job: `buildx` build of both images and a smoke test
    (`curl /healthz`) of the API container.
- `.env.example` — documents every supported environment variable.
- `requirements.txt` and `requirements-dev.txt`.
- `.gitignore` updated to exclude `data/`, `*.db`, `*.db-journal`,
  `*.sqlite*`.

### Added — Phase D · Hardening (Stories 8–10)

#### Story 8 — async pick generation

- `POST /picks` is now **async**: it validates the request synchronously,
  persists a `pending` row, schedules a `fastapi.BackgroundTasks` worker, and
  returns **`202 Accepted`** with `{id, status, created_at}`.
- The background worker runs the pipeline and updates the row to either
  `success` (full payload) or `failed` (with `error_stage` + `error_message`).
- New endpoint **`GET /picks/{id}/status`** returns a lightweight body
  `{id, status, error_stage, error_message, latency_ms}` for polling.
- `GET /picks/{id}` now also surfaces `status`, `error_stage`,
  `error_message`. List items include `status`.
- `services/api/db.py` adds columns `status`, `error_stage`, `error_message`
  on `picks_history`. A lightweight forward migration
  (`_ensure_added_columns`) issues `ALTER TABLE ADD COLUMN` on existing
  SQLite files at startup so deployed databases pick up the schema with no
  manual SQL.
- New helpers `create_pending_pick_run`, `mark_pick_success`,
  `mark_pick_failed` replace the previous sync `record_pick_run`.
- UI: Generate page now submits, then calls
  `PicksAPIClient.wait_for_pick(...)` (polls `/status` every 1.5 s until
  terminal) and renders the resulting payload; failures are surfaced inline.

#### Story 9 — outcome capture & hit rate

- New `pick_outcomes` table (`PickOutcome` model) with `pick_id`, `rank`,
  `player`, `market`, `result` (`win|loss|push|void`), `recorded_at`.
- `POST /picks/{id}/outcomes` — accepts `{outcomes: [{rank, player, market,
  result}]}`. Returns 201 with the persisted rows. 404 when the pick is
  unknown; 422 when `result` is not in the allowed set.
- `GET /picks/{id}/outcomes` — returns all recorded outcomes for a pick.
- `GET /stats/hit-rate?since=ISO8601` — aggregate counts and a hit rate
  over decided outcomes (`win` / (`win` + `loss`)). `push` and `void` are
  excluded from both numerator and denominator.
- UI: history detail page now includes an outcome capture form (one row per
  scored pick) and shows a previously-recorded outcomes table; the sidebar
  shows a global hit-rate metric.

#### Story 10 — observability, rate limits, admin stats

- `services/api/rate_limit.py` — small in-memory fixed-window
  `RateLimiter` (no extra dependency). Configured via
  `COLMILLO_RATE_LIMIT_PER_HOUR` (default `30`; `0` disables). Limited
  requests return `429` with a `Retry-After` header and a JSON body
  `{detail, retry_after_seconds}`.
- Admin gate on the `/admin/*` route prefix in `APIKeyAuthMiddleware`:
  requires `COLMILLO_ADMIN_API_KEY` to be set (else 503) and the request to
  carry a matching `X-Admin-API-Key` header (else 403).
- `GET /admin/stats` — returns `total_runs`, `by_status`,
  `avg_success_latency_ms`, `recent_failures` (last 5), and
  `outcomes_recorded`.
- `services/api/sentry.py` — `init_sentry_if_configured()` activates
  Sentry only when both `SENTRY_DSN` is set **and** `sentry-sdk` is
  installed; called from the FastAPI factory. Optional knobs:
  `SENTRY_ENVIRONMENT`, `SENTRY_TRACES_SAMPLE_RATE`.
- `requirements.txt` adds `sentry-sdk>=2.0,<3.0` so the integration is one
  env-var flip away in production.
- `.env.example` and `render.yaml` updated with `COLMILLO_RATE_LIMIT_PER_HOUR`,
  `COLMILLO_ADMIN_API_KEY`, `SENTRY_DSN`, `SENTRY_ENVIRONMENT`,
  `SENTRY_TRACES_SAMPLE_RATE`.

### Changed

- `pipeline_service.run_pipeline_with_payload(request, deps)` is the new
  integration seam used by both the CLI and the FastAPI worker. The old
  `run_pipeline(...)` wrapper still works and continues to return just the
  rendered markdown.
- The synchronous response contract for `POST /picks` is gone. Clients that
  used to consume the rendered payload directly from the POST response must
  now follow up with `GET /picks/{id}/status` (poll) and then
  `GET /picks/{id}` for the full payload, or use `PicksAPIClient.wait_for_pick`.
- Pipeline failures no longer surface as HTTP 4xx/5xx on the POST. They are
  persisted as a `failed` row and exposed via the status endpoint. Synchronous
  4xx is reserved for request validation and dependency-bundle config errors
  (e.g. missing provider credentials).
- The picks-history schema gained `status`, `error_stage`, `error_message`
  and a sibling `pick_outcomes` table. SQLite databases created before
  v0.2.0 are migrated transparently on app startup.

### Deprecated / Removed

- `services.api.db.record_pick_run(...)` — replaced by the
  `create_pending_pick_run` / `mark_pick_success` / `mark_pick_failed` trio.

### Tests

- 191 tests pass (was 175 before Phase D).
- New: `tests/api/test_phase_d_endpoints.py` (status polling, outcomes,
  hit rate, admin stats, rate limit, Sentry skip).
- Updated: `tests/api/test_picks_endpoint.py` and `tests/ui/test_api_client.py`
  for the 202-async contract.

[0.2.0]: https://github.com/your-org/Colmillo-Picks/releases/tag/v0.2.0
