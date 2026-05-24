# Release Process

Step-by-step guide for preparing, publishing, verifying, and rolling back
Colmillo-Picks releases.

## Prerequisites

- Push access to `main`
- `gh` CLI authenticated (`gh auth status`)
- Docker installed locally (for verification)

## 1. Prepare the Release

### Stable release

```bash
# Ensure main is up-to-date
git checkout main && git pull

# Verify tests and lint pass
pytest -q && ruff check .

# Confirm changelog has an entry for the target version
python scripts/validate_changelog.py v0.4.0
```

### Release candidate

```bash
# Create release branch from dev
git checkout dev && git pull
git checkout -b release/v0.4
git push -u origin release/v0.4

# Tag the RC
git tag v0.4.0-rc.1
git push origin v0.4.0-rc.1
```

## 2. Trigger the Release

### Option A: Push a version tag (recommended)

```bash
git tag v0.4.0
git push origin v0.4.0
```

The release workflow (`.github/workflows/release.yml`) fires automatically on
tags matching `v[0-9]+.[0-9]+.[0-9]+` or `v[0-9]+.[0-9]+.[0-9]+-rc.[0-9]+`.

### Option B: Manual dispatch

1. Go to **Actions → Release → Run workflow**
2. Enter the tag (e.g., `v0.4.0`)
3. Click **Run workflow**

## 3. What the Workflow Does

| Step | Description |
|------|-------------|
| Validate tag format | Rejects invalid tags (e.g., missing `v` prefix) |
| Run tests | `pytest -q` |
| Run lint | `ruff check .` |
| Package CLI artifact | Creates `colmillo-picks-<version>.tar.gz` |
| Create GitHub Release | Attaches release notes + CLI artifact |
| Publish Docker images | Pushes API and UI images to `ghcr.io` |

## 4. Verify the Release

### Check GitHub Release

```bash
gh release view v0.4.0
gh release download v0.4.0 --pattern "*.tar.gz"
```

### Verify CLI artifact

```bash
tar xzf colmillo-picks-0.4.0.tar.gz
cd colmillo-picks-0.4.0
cat VERSION  # should show "0.4.0"
pip install -r requirements.txt
python skills/soccer-prop-picks/scripts/run_match_pick_pipeline.py \
  --match-query "Arsenal vs Chelsea" --allow-deterministic-fallback
```

### Verify Docker images

```bash
# Pull the image
docker pull ghcr.io/tlacahuepec/colmillo-api:0.4.0

# Run health check
docker run -d --name verify \
  -e COLMILLO_API_KEY=verify-key \
  -p 8000:8000 ghcr.io/tlacahuepec/colmillo-api:0.4.0

curl http://localhost:8000/healthz
curl http://localhost:8000/version

docker rm -f verify
```

## 5. Rollback

### Delete a bad release

```bash
# Remove the GitHub Release (keeps the tag)
gh release delete v0.4.0 --yes

# Remove the tag if needed
git push --delete origin v0.4.0
git tag -d v0.4.0
```

### Revert to previous version

```bash
# Point :latest back to the previous stable
docker pull ghcr.io/tlacahuepec/colmillo-api:0.3.0
docker tag ghcr.io/tlacahuepec/colmillo-api:0.3.0 \
  ghcr.io/tlacahuepec/colmillo-api:latest
docker push ghcr.io/tlacahuepec/colmillo-api:latest
```

### Hotfix release

```bash
# Branch from the affected tag
git checkout -b fix/critical-bug v0.3.0

# Fix, test, commit
pytest -q && ruff check .
git push -u origin fix/critical-bug

# Merge to main, then tag the patch
git checkout main && git pull
gh pr create --title "Fix critical bug" --base main
# After merge:
git tag v0.3.1
git push origin v0.3.1
```

## 6. Common Failures

| Symptom | Cause | Fix |
|---------|-------|-----|
| Workflow fails at "Validate tag format" | Tag doesn't match `v0.0.0` pattern | Delete tag, recreate with correct format |
| Tests fail in release workflow | Code on main has broken tests | Fix on a branch, merge, re-tag |
| Docker push fails with 403 | `packages: write` permission missing | Check workflow permissions or repo settings |
| Smoke test fails | App crashes on startup | Check Dockerfile, env vars, then re-release |
| Changelog validation fails | No `## [version]` section | Add changelog entry, merge, re-tag |

## Workflow Files

| File | Purpose |
|------|---------|
| `.github/workflows/release.yml` | Main release orchestrator |
| `.github/workflows/publish-docker.yml` | Docker build + push to GHCR |
| `scripts/validate_changelog.py` | Verify changelog has version entry |
| `scripts/package_cli.py` | Build CLI release archive |
| `scripts/docker_tags.py` | Generate Docker image tags |
