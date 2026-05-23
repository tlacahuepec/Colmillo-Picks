# Hotfix Workflow

Guide for applying urgent fixes to the stable `main` branch and backporting
them to `dev`.

## When to Use a Hotfix

Use a hotfix when:
- A critical bug is found in a released version.
- A security vulnerability requires immediate patching.
- A production issue is blocking users.

Do NOT use a hotfix for:
- Non-critical improvements.
- Feature additions.
- Refactoring.

## Hotfix Process

### 1. Create hotfix branch from main

```bash
git checkout main && git pull
git checkout -b fix/critical-issue
```

### 2. Fix, test, and verify

```bash
# Make the fix
# Write a test that reproduces the issue first (TDD)

# Run tests
pytest -q

# Run lint
ruff check .

# Run smoke test
python scripts/smoke_test.py --all
```

### 3. Push and create PR to main

```bash
git push -u origin fix/critical-issue

gh pr create --base main \
  --title "Fix critical issue in scoring" \
  --body "Fixes #<issue-number>

## What happened
<description of the bug>

## Root cause
<what went wrong>

## Fix
<what was changed and why>

## Test plan
- [x] Added regression test
- [x] pytest -q passes
- [x] ruff check . passes"
```

### 4. Merge to main

After PR approval and CI passes:

```bash
gh pr merge --squash --admin
```

### 5. Tag the patch release

```bash
git checkout main && git pull

# If current release is v0.3.0, tag as v0.3.1
git tag v0.3.1
git push origin v0.3.1
```

This triggers the release workflow automatically:
- Runs tests + lint + smoke tests
- Packages CLI artifact
- Creates GitHub Release
- Publishes Docker images

### 6. Backport to dev

```bash
git checkout dev && git pull

# Cherry-pick the fix commit (use the merge commit SHA from main)
git cherry-pick <fix-commit-sha>
git push
```

If cherry-pick has conflicts:
```bash
# Resolve conflicts
git cherry-pick <fix-commit-sha>
# Fix conflicts in affected files
git add <resolved-files>
git cherry-pick --continue
git push
```

Alternative: create a PR to dev with the fix:
```bash
git checkout -b fix/critical-issue-dev dev
git cherry-pick <fix-commit-sha>
git push -u origin fix/critical-issue-dev
gh pr create --base dev --title "Backport: Fix critical issue"
```

## Versioning Rules

| Current release | Hotfix tag | Example |
|----------------|-----------|---------|
| `v0.3.0` | `v0.3.1` | First patch |
| `v0.3.1` | `v0.3.2` | Second patch |
| `v1.0.0` | `v1.0.1` | Major version patch |

## Checklist

- [ ] Hotfix branch created from `main` (not `dev`)
- [ ] Regression test added (TDD: test fails without fix)
- [ ] `pytest -q` passes
- [ ] `ruff check .` passes
- [ ] PR targets `main`
- [ ] PR merged and patch version tagged
- [ ] Release workflow completed successfully
- [ ] Fix backported to `dev` via cherry-pick

## Common Issues

| Problem | Solution |
|---------|----------|
| Cherry-pick conflicts | Resolve manually, ensure both main and dev have the fix |
| Wrong base branch | Close PR, recreate from main |
| Forgot to tag | Tag the merge commit on main: `git tag v0.3.1 <sha>` |
| Release workflow failed | Fix the issue, delete tag, re-tag |

## Related Docs

- [Release Process](release-process.md) — full release flow
- [Branch Strategy](branch-strategy.md) — branch roles
- [Release Versioning](release-versioning.md) — version numbering
