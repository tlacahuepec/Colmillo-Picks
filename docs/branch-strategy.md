# Branch Strategy and Contribution Rules

## Branch Roles

| Branch | Purpose | Merges from | Merges to |
|--------|---------|-------------|-----------|
| `main` | Stable, release-ready code | `release/*`, `fix/*` (hotfix) | — |
| `dev` | Integration branch for active development | `feat/*`, `fix/*` | `release/*` |
| `feat/*` | Feature work | — | `dev` |
| `fix/*` | Bug fixes | — | `dev` (or `main` for hotfixes) |
| `release/*` | Release candidates | `dev` | `main` |

## Branch Naming

```
feat/basketball-scoring       — new feature
feat/add-prizepicks-adapter   — new integration
fix/passes-formula-off-by-one — bug fix
release/v0.4                  — release branch
fix/critical-auth-bypass      — hotfix (branches from main)
docs/release-process          — documentation only
```

## Workflow Rules

### For developers and agents

1. **Always branch from `dev`** for new work:
   ```bash
   git checkout dev && git pull
   git checkout -b feat/my-feature
   ```

2. **Open PRs to `dev`**, never directly to `main`:
   ```bash
   gh pr create --base dev --title "Add my feature"
   ```

3. **Never commit directly to `main` or `dev`** — always use a PR.

4. **Keep feature branches short-lived** — merge within days, not weeks.

5. **Delete branches after merge** — GitHub does this automatically with squash merge.

### What NOT to do

- Do NOT push directly to `main` (it is protected).
- Do NOT create feature branches from `main` (branch from `dev`).
- Do NOT merge `dev` directly into `main` (use a release branch).
- Do NOT leave stale branches open for more than a week.

## Merge Strategy

| Merge type | Strategy | When |
|-----------|----------|------|
| Feature → dev | **Squash merge** | Always |
| Release → main | **Merge commit** | Release cut |
| Hotfix → main | **Squash merge** | Critical fixes |
| Hotfix → dev | **Cherry-pick** | After main merge |

## Review Expectations

| PR target | Reviewer required? | CI must pass? |
|-----------|-------------------|---------------|
| `dev` | Recommended (1 reviewer) | Yes |
| `main` | Required (1 reviewer minimum) | Yes |

## Release Flow

```
dev ──► release/v0.4 ──► main
         │
         └─ tag: v0.4.0-rc.1
                  v0.4.0-rc.2
                  ...
         └─ final merge to main
         └─ tag: v0.4.0
```

1. Cut release branch from `dev`: `git checkout -b release/v0.4 dev`
2. Only bug fixes go into the release branch (no new features).
3. Tag release candidates: `v0.4.0-rc.1`, `v0.4.0-rc.2`, etc.
4. When stable, merge to `main` and tag: `v0.4.0`.
5. Cherry-pick any release-branch fixes back to `dev`.

## Hotfix Flow

```
main ──► fix/critical-bug ──► main
                              └─► cherry-pick to dev
```

1. Branch from `main`: `git checkout -b fix/critical-bug main`
2. Fix, test, PR to `main`.
3. Tag patch release: `v0.3.1`.
4. Cherry-pick the fix to `dev`.

## Agent-Specific Rules

When using AI coding agents (Claude Code, Copilot, etc.):

- Agents MUST branch from `dev`, not `main`.
- Agents MUST open PRs to `dev`.
- Agents should use descriptive branch names: `feat/agent-basketball-explainer`.
- Agents must run `pytest -q` and `ruff check .` before pushing.
- Agents must not force-push or rewrite shared branch history.

## Quick Reference

```bash
# Start new feature
git checkout dev && git pull
git checkout -b feat/my-feature

# Work, commit, push
git add <files>
git commit -m "Add my feature"
git push -u origin feat/my-feature

# Open PR to dev
gh pr create --base dev --title "Add my feature"

# After merge, clean up
git checkout dev && git pull
git branch -d feat/my-feature
```
