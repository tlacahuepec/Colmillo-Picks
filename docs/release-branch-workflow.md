# Release Branch Workflow

Step-by-step guide for cutting a release branch, stabilizing it, and merging
to main.

## When to Cut a Release Branch

Create a release branch when:
- All planned features for a version are merged to `dev`.
- The team agrees the version is feature-complete.
- You want to start release candidate testing.

## Create the Release Branch

```bash
# Ensure dev is up-to-date
git checkout dev && git pull

# Create release branch
git checkout -b release/v0.4
git push -u origin release/v0.4
```

## Tag Release Candidates

```bash
# First RC
git tag v0.4.0-rc.1
git push origin v0.4.0-rc.1

# Subsequent RCs after fixes
git tag v0.4.0-rc.2
git push origin v0.4.0-rc.2
```

Each RC tag triggers the release workflow, which:
1. Validates tag format
2. Runs tests and lint
3. Runs smoke tests
4. Creates a pre-release on GitHub
5. Publishes Docker images (without `:latest` tag)

## Allowed Changes on Release Branches

Only stabilization work is permitted:

| Allowed | Not Allowed |
|---------|-------------|
| Bug fixes | New features |
| Documentation fixes | Refactoring |
| Test improvements | Dependency upgrades (non-security) |
| Security patches | Performance experiments |

```bash
# Fix a bug on the release branch
git checkout release/v0.4
git checkout -b fix/scoring-rounding
# ... fix, test, commit ...
gh pr create --base release/v0.4 --title "Fix scoring rounding"
```

## CI on Release Branches

The CI workflow runs full release-readiness checks on `release/*` branches:
- Lint (`ruff check .`)
- Full test suite (`pytest -q`)
- Docker image build
- Release-readiness validation (versioning doc, coverage)

## Merge to Main

When the release branch is stable (all RCs pass, no blocking issues):

```bash
# Create PR from release branch to main
gh pr create --base main --head release/v0.4 \
  --title "Release v0.4.0" \
  --body "Merge release/v0.4 to main for stable release."

# After PR is approved and merged, tag the release
git checkout main && git pull
git tag v0.4.0
git push origin v0.4.0
```

The stable tag triggers the full release workflow:
1. Tests + lint + smoke tests
2. CLI artifact packaging
3. GitHub Release creation
4. Docker image publishing with `:latest` tag

## After the Release

```bash
# Cherry-pick any release-branch fixes back to dev
git checkout dev && git pull
git cherry-pick <fix-commit-sha>
git push

# Delete the release branch (optional, keeps things clean)
git push origin --delete release/v0.4
git branch -d release/v0.4
```

## Rollback

If a problem is found after merging to main:

```bash
# Option 1: Hotfix (preferred for small issues)
git checkout -b fix/critical-issue main
# ... fix ...
gh pr create --base main

# Option 2: Revert the release merge
git checkout main
git revert -m 1 <merge-commit-sha>
gh pr create --base main --title "Revert v0.4.0 release"
```

## Timeline Example

```
Day 1: Cut release/v0.4 from dev
Day 1: Tag v0.4.0-rc.1, deploy to staging
Day 2: Bug found, fix merged to release/v0.4
Day 2: Tag v0.4.0-rc.2
Day 3: All clear, merge release/v0.4 → main
Day 3: Tag v0.4.0 (triggers stable release)
Day 3: Cherry-pick fixes to dev
```

## Related Docs

- [Release Process](release-process.md) — full release workflow details
- [Branch Strategy](branch-strategy.md) — branch roles and naming
- [Release Versioning](release-versioning.md) — version numbering rules
