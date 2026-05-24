# Agent Workflow Guide

Instructions for AI coding agents (Claude Code, Codex, Copilot) working on
Colmillo-Picks.

## Core Rules

1. **Branch from `dev`**, never from `main`.
2. **One issue per feature branch.** Do not bundle unrelated changes.
3. **Open PRs to `dev`**, unless it's a hotfix (then PR to `main`).
4. **Run tests and lint before pushing.** No exceptions.
5. **Never force-push or rewrite shared branch history.**

## Starting Work

```bash
# Pull latest dev
git checkout dev && git pull

# Create feature branch
git checkout -b feat/my-feature

# Or for a bug fix
git checkout -b fix/scoring-bug
```

## Branch Naming

| Type | Pattern | Example |
|------|---------|---------|
| Feature | `feat/<description>` | `feat/basketball-explainer` |
| Bug fix | `fix/<description>` | `fix/passes-formula-rounding` |
| Documentation | `docs/<description>` | `docs/release-process` |
| Refactor | `refactor/<description>` | `refactor/provider-interface` |

Keep names short, lowercase, hyphen-separated. No issue numbers in branch names.

## Development Cycle

### 1. Write failing tests first (TDD)

```bash
# Create test file
# Write tests that define expected behavior
pytest tests/test_my_feature.py -v
# Tests should FAIL (red phase)
```

### 2. Implement the feature

```bash
# Write minimal code to make tests pass
pytest tests/test_my_feature.py -v
# Tests should PASS (green phase)
```

### 3. Verify everything

```bash
# Full test suite
pytest -q

# Lint
ruff check .

# Fix any lint issues
ruff check . --fix
```

### 4. Commit and push

```bash
git add <specific-files>
git commit -m "Add my feature (#issue-number)"
git push -u origin feat/my-feature
```

### 5. Open PR

```bash
gh pr create --base dev \
  --title "Add my feature" \
  --body "## Summary
- What was added/changed

## Test plan
- [x] pytest -q passes
- [x] ruff check . passes

Closes #<issue-number>"
```

## PR Targets

| PR type | Base branch | When |
|---------|-------------|------|
| Feature | `dev` | Always |
| Bug fix | `dev` | Normal fixes |
| Hotfix | `main` | Critical production issues only |
| Release | `main` | Cutting a stable release |
| Documentation | `dev` | Usually |

## Pre-Push Checklist

Before pushing, verify:

- [ ] `pytest -q` — all tests pass
- [ ] `ruff check .` — no lint errors
- [ ] No secrets committed (`.env`, API keys, tokens)
- [ ] No unrelated changes included
- [ ] Commit message references issue number

## What Agents Must NOT Do

- Push directly to `main` or `dev`
- Force-push (`git push --force`)
- Delete remote branches they didn't create
- Commit `.env` files or secrets
- Skip tests or lint
- Bundle multiple issues in one PR
- Create branches from `main` (except hotfixes)
- Modify CI workflows without explicit request
- Amend published commits

## Commit Messages

Format: `<verb> <description> (#issue-number)`

```
Add basketball scoring module (#100)
Fix passes formula rounding error (#145)
Update release process documentation (#128)
```

- Start with a verb: Add, Fix, Update, Remove, Refactor
- Keep under 72 characters
- Reference the issue number

## Working with Multiple Issues

Process issues one at a time:
1. Pick up an issue
2. Create feature branch from `dev`
3. Implement (TDD: tests first, then code)
4. Run tests + lint
5. Push, create PR, merge
6. Move to next issue

Do NOT work on multiple issues in parallel on the same branch.

## Error Recovery

### Tests fail after implementation

```bash
# Fix the failing tests
pytest tests/test_my_feature.py -v
# Iterate until green
```

### Lint fails

```bash
# Auto-fix what's possible
ruff check . --fix
# Manually fix remaining issues
```

### Merge conflicts

```bash
git checkout dev && git pull
git checkout feat/my-feature
git rebase dev
# Resolve conflicts
git add <resolved-files>
git rebase --continue
git push --force-with-lease
```

## Related Docs

- [Branch Strategy](branch-strategy.md) — branch roles and merge rules
- [Release Process](release-process.md) — how releases work
- [Hotfix Workflow](hotfix-workflow.md) — emergency fix process
