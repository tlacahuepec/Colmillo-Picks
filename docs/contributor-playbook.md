# Contributor Playbook

Single source of truth for branching, releases, and agent development in
Colmillo-Picks.

## Branch Model

```
main          ← stable releases (v0.3.0, v0.4.0)
dev           ← integration branch for active work
feat/*        ← feature branches (from dev → PR to dev)
fix/*         ← bug fixes (from dev → PR to dev)
release/*     ← release candidates (from dev → PR to main)
fix/* (hotfix)← urgent fixes (from main → PR to main → cherry-pick to dev)
```

### Branch Meanings

| Branch | Represents | Protected? |
|--------|-----------|------------|
| `main` | Latest stable released version | Yes — PR + 1 approval + CI (Lint, Tests, Docker Build) |
| `dev` | Integration branch for active development | Yes — PR + 1 approval + CI (Lint, Tests) |
| `feat/*` | Feature work in progress | No |
| `fix/*` | Bug fix work in progress | No |
| `release/*` | Release candidate stabilization | CI runs release-readiness checks |

## Workflow: Feature Development

### 1. Create feature branch from dev

```bash
git checkout dev && git pull
git checkout -b feat/my-feature
```

### 2. Develop with TDD

```bash
# Write failing tests first
pytest tests/test_my_feature.py -v  # Should FAIL

# Implement
# ...

pytest tests/test_my_feature.py -v  # Should PASS
pytest -q                            # Full suite
ruff check .                         # Lint
```

### 3. Commit and push

```bash
git add <specific-files>
git commit -m "Add my feature (#issue-number)"
git push -u origin feat/my-feature
```

### 4. Open PR to dev

```bash
gh pr create --base dev \
  --title "Add my feature" \
  --body "## Summary
- Description of changes

## Test plan
- [x] pytest -q passes
- [x] ruff check . passes

Closes #<issue-number>"
```

### 5. Merge after CI passes

```bash
gh pr merge --squash
```

## Workflow: Cutting a Release

### 1. Create release branch from dev

```bash
git checkout dev && git pull
git checkout -b release/v0.4
git push -u origin release/v0.4
```

### 2. Stabilize (bug fixes only)

```bash
# Only fixes allowed on release branches
git checkout -b fix/release-bug release/v0.4
# ... fix ...
gh pr create --base release/v0.4
```

### 3. Tag release candidates

```bash
git checkout release/v0.4 && git pull
git tag v0.4.0-rc.1
git push origin v0.4.0-rc.1
```

### 4. Merge to main when stable

```bash
gh pr create --base main --head release/v0.4 \
  --title "Release v0.4.0"
# After approval:
gh pr merge --merge
```

### 5. Tag stable release

```bash
git checkout main && git pull
git tag v0.4.0
git push origin v0.4.0
```

This triggers the release workflow which:
- Validates tag format
- Runs tests, lint, smoke tests
- Packages CLI artifact
- Creates GitHub Release
- Publishes Docker images to GHCR

### 6. Backport fixes to dev

```bash
git checkout dev && git pull
git cherry-pick <release-fix-sha>
git push
```

## Workflow: Hotfix

### 1. Branch from main

```bash
git checkout main && git pull
git checkout -b fix/critical-issue
```

### 2. Fix with TDD

```bash
# Write test that reproduces the bug
pytest tests/test_hotfix.py -v  # FAIL
# Fix
pytest -q && ruff check .
```

### 3. PR to main

```bash
gh pr create --base main --title "Fix critical issue"
gh pr merge --squash --admin
```

### 4. Tag patch release

```bash
git checkout main && git pull
git tag v0.3.1
git push origin v0.3.1
```

### 5. Backport to dev

```bash
git checkout dev && git pull
git cherry-pick <fix-sha>
git push
```

## CI and Checks

### Checks before PR to dev

| Check | Command | Required? |
|-------|---------|-----------|
| Tests | `pytest -q` | Yes |
| Lint | `ruff check .` | Yes |

### Checks before merge to main

| Check | Command | Required? |
|-------|---------|-----------|
| Tests | `pytest -q` | Yes |
| Lint | `ruff check .` | Yes |
| Docker Build | CI builds images | Yes |
| Smoke tests | `python scripts/smoke_test.py --all` | On release |

### GitHub Actions

| Workflow | Triggers on | Purpose |
|----------|------------|---------|
| `ci.yml` | Push/PR to main, dev, release/* | Lint, test, Docker build |
| `release.yml` | Version tags | Create GitHub Release + artifacts |
| `publish-docker.yml` | Called by release.yml | Push images to GHCR |
| `dev-build.yml` | Push to dev | Build and push `:dev` images |

## Rules for Agents

### MUST

- Branch from `dev` (not `main`)
- One issue per feature branch
- Run `pytest -q` and `ruff check .` before pushing
- Open PRs to `dev`
- Use descriptive branch names: `feat/basketball-scoring`
- Reference issue numbers in commits

### MUST NOT

- Push directly to `main` or `dev`
- Force-push (`git push --force`)
- Skip tests or lint
- Commit secrets (`.env`, API keys, tokens)
- Bundle multiple issues in one PR
- Modify CI workflows without explicit request
- Amend published commits
- Create branches from `main` (except hotfixes)

## Branch Naming

```
feat/basketball-scoring       ✓
feat/add-prizepicks-adapter   ✓
fix/passes-formula-rounding   ✓
docs/release-process          ✓
release/v0.4                  ✓
my-branch                     ✗ (missing prefix)
feat/ISSUE-99                 ✗ (use description, not number)
```

## Commit Messages

```
Add basketball scoring module (#100)
Fix passes formula rounding error (#145)
Update release process documentation (#128)
Remove deprecated record_pick_run function (#130)
```

Start with a verb. Keep under 72 characters. Reference the issue.

## Related Documentation

- [Branch Strategy](branch-strategy.md) — detailed branch roles
- [Release Process](release-process.md) — release workflow details
- [Release Branch Workflow](release-branch-workflow.md) — release branch lifecycle
- [Hotfix Workflow](hotfix-workflow.md) — emergency fix process
- [Agent Workflow](agent-workflow.md) — agent-specific rules
- [Dev Deployment](dev-deployment.md) — dev environment setup
- [Release Versioning](release-versioning.md) — version numbering
