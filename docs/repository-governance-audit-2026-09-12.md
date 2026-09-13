# Repository governance audit — 2026-09-12

Scope: GitHub repository settings, branch protection, rulesets, and the local
branch workflow documentation. This audit is read-only; no GitHub setting was
changed.

## Verified controls

| Control | `main` | `dev` |
| --- | --- | --- |
| Protected branch | Yes | Yes |
| Pull-request review | One approval; stale reviews dismissed | One approval |
| Required checks | Lint, Tests, Build container images; strict up-to-date | Lint and Tests |
| Force push and deletion | Disabled | Disabled |
| Repository branch deletion after merge | Enabled | Enabled |

The active `main` ruleset additionally requires code-owner review, resolved
threads, and squash-only pull requests. The active `dev` ruleset prevents
deletion and non-fast-forward updates.

## Findings requiring maintainer decision

| Gap or conflict | Evidence | Required decision |
| --- | --- | --- |
| Release merge strategy conflicts with enforcement | `docs/branch-strategy.md` calls for release-to-main merge commits, while the active `main` ruleset permits squash only | Choose squash-only releases and update docs, or permit merge commits for release PRs |
| `dev` merge method is not enforced | Repository settings allow squash, merge commits, and rebase; the `dev` ruleset does not restrict methods | Enforce squash-only for feature-to-dev PRs, or amend the documented policy |
| `dev` protection is weaker than `main` | It does not require an up-to-date branch, stale-review dismissal, resolved threads, code-owner review, or the container build | Decide which controls are proportionate for integration work, then configure them explicitly |
| Administrators can bypass the `main` ruleset | GitHub reports the current repository role can bypass the ruleset | Decide whether administrator bypass is acceptable and document an emergency-use policy if retained |
| Branch naming is documentary only | The repository has legacy `codex/*` and other non-standard branches; no matching ruleset exists | Choose a prospective naming policy and a maintainer-approved cleanup process; do not delete branches automatically |

## Current policy for contributors

Until a maintainer resolves the conflicts above, contributors should continue to
branch from `dev`, open pull requests to `dev`, use squash merges for
feature-to-dev work, and never push directly to protected branches. The branch
strategy document remains the contribution guide, but it must be reconciled
with the active `main` ruleset before the next release.

## Follow-up checklist

1. Record the selected release merge policy in `docs/branch-strategy.md`.
2. Configure the selected `dev` merge and review controls in GitHub.
3. Decide whether an administrator bypass policy and a branch-retention policy
   are needed.
4. Re-run this audit after each repository-ruleset change.

