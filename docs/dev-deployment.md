# Dev Environment Deployment

How to deploy and verify dev builds of Colmillo-Picks.

## Overview

The `dev` branch automatically produces Docker images tagged as `dev` on every
push. These images are separate from stable releases and can be deployed to a
development environment for testing.

## Image Tags

| Source | Tag pattern | Example |
|--------|------------|---------|
| `dev` branch push | `:dev`, `:dev-<sha>` | `ghcr.io/tlacahuepec/colmillo-api:dev` |
| Release tag | `:<version>`, `:latest` | `ghcr.io/tlacahuepec/colmillo-api:0.4.0` |

Dev images **never** receive the `:latest` tag.

## Deploying Locally

```bash
# Pull dev images
docker pull ghcr.io/tlacahuepec/colmillo-api:dev
docker pull ghcr.io/tlacahuepec/colmillo-ui:dev

# Run with dev configuration
docker run -d --name colmillo-api-dev \
  -e COLMILLO_API_KEY=dev-key \
  -e COLMILLO_VERSION=0.0.0-dev \
  -e COLMILLO_CHANNEL=dev \
  -p 8000:8000 \
  ghcr.io/tlacahuepec/colmillo-api:dev

docker run -d --name colmillo-ui-dev \
  -e COLMILLO_API_URL=http://localhost:8000 \
  -e COLMILLO_API_KEY=dev-key \
  -p 8501:8501 \
  ghcr.io/tlacahuepec/colmillo-ui:dev
```

## Verifying Dev Builds

```bash
# Check version endpoint
curl http://localhost:8000/version
# Expected: {"version": "0.0.0-dev", "channel": "dev", ...}

# Check health
curl http://localhost:8000/healthz
# Expected: {"status": "ok", "version": "0.0.0-dev", "channel": "dev", ...}
```

Key indicators of a dev build:
- `version` = `0.0.0-dev`
- `channel` = `dev`
- `commit` = the SHA from the dev branch

## Environment Separation

| Concern | Dev | Stable |
|---------|-----|--------|
| Docker tag | `:dev` | `:latest`, `:<version>` |
| Channel metadata | `dev` | `stable` |
| API key env var | `COLMILLO_API_KEY` (any value) | `COLMILLO_API_KEY` (production secret) |
| Database | Ephemeral / local | Persistent disk |
| External APIs | Optional / mocked | Real credentials |

## CI Workflow

The dev build workflow (`.github/workflows/dev-build.yml`) runs on every push
to `dev`:

1. Runs tests and lint
2. Builds Docker images
3. Tags as `:dev` and `:dev-<sha>`
4. Pushes to GHCR
5. Runs smoke test on API image

## Secrets

Dev deployments should NOT use production secrets:
- Use a separate `COLMILLO_API_KEY` value
- Do not set `SENTRY_DSN` (or use a dev Sentry project)
- Do not set `GEMINI_API_KEY` unless testing LLM features
- Use `COLMILLO_ADMIN_API_KEY` only if testing admin routes

## Differences from Stable

| Feature | Dev | Stable |
|---------|-----|--------|
| Auto-deployed | Yes (on dev push) | No (manual tag) |
| Docker `:latest` | Never | Yes |
| GitHub Release | Never | Yes |
| CLI artifact | Not produced | Attached to release |
| Pre-release | No | RC only |
