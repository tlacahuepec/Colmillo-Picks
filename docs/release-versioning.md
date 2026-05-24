# Release Versioning Strategy

## Semantic Versioning

Colmillo-Picks follows [Semantic Versioning 2.0.0](https://semver.org/):

```
v<MAJOR>.<MINOR>.<PATCH>
```

| Component | When to increment |
|-----------|-------------------|
| **MAJOR** | Breaking API changes, incompatible data format changes, removal of supported sport |
| **MINOR** | New sport module, new feature (e.g., new market, new provider), backward-compatible API additions |
| **PATCH** | Bug fixes, scoring formula tweaks, documentation updates, dependency bumps |

## Tag Format

- Release tags: `v0.3.0`, `v1.0.0`, `v1.2.1`
- Pre-release tags: `v0.4.0-rc.1`, `v0.4.0-rc.2`
- Dev tags: `v0.4.0-dev.1`

### Invalid examples

- `0.3.0` (missing `v` prefix)
- `v1` (incomplete)
- `v1.0.0.0` (too many segments)
- `release-1.0` (wrong format)

## Release Channels

| Channel | Branch | Tag pattern | Purpose |
|---------|--------|-------------|---------|
| **dev** | `dev` | `v*-dev.*` | Latest development builds, may be unstable |
| **release-candidate** | `release/v*` | `v*-rc.*` | Pre-release testing before stable |
| **stable** | `main` | `v*.*.*` (no suffix) | Production-ready releases |

## Branch-to-Channel Mapping

```
main          → stable releases (v0.3.0, v1.0.0)
release/v0.4  → release candidates (v0.4.0-rc.1)
dev           → dev builds (v0.4.0-dev.3)
feat/*        → no releases (feature work)
fix/*         → no releases (bug fix work)
```

## Release Qualification Examples

### Patch release (v0.3.0 → v0.3.1)
- Fix scoring bug in soccer passes formula
- Update dependency with security patch
- Fix typo in API error message

### Minor release (v0.3.1 → v0.4.0)
- Add basketball sport module
- Add new provider adapter (e.g., DraftKings)
- Add new API endpoint
- Add new market to existing sport

### Major release (v0.4.0 → v1.0.0)
- Remove legacy `match_query` API format
- Change run ledger schema in incompatible way
- Remove a supported sport

## Milestone Examples

| Version | Content |
|---------|---------|
| `v0.3.0` | Soccer-only MVP with PrizePicks availability |
| `v0.4.0` | Multi-sport architecture (basketball + baseball skeletons) |
| `v0.5.0` | Basketball scoring with real NBA data |
| `v0.6.0` | Baseball scoring with real MLB data |
| `v1.0.0` | Stable multi-sport platform, public API contract |

## Hotfix Process

1. Branch from the affected release tag: `git checkout -b fix/critical-bug v0.3.0`
2. Fix, test, merge to `main`
3. Tag as patch: `v0.3.1`
4. Cherry-pick to `dev` if applicable

## Current Version

The project is currently pre-1.0. All minor releases may include small breaking changes until `v1.0.0` is reached and the public API contract is frozen.
