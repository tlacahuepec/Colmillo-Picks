# Epic: Daily sports intelligence catalog

Status: complete. The epic covers soccer, basketball, MLB/baseball and NFL.

Progress: #310 contracts, #311 storage foundation, #312 provider ports, #313
importance scoring, #314 scheduling, #315 the deterministic LangGraph workflow,
and #316 the soccer adapter, #317 the basketball adapter, #318 the MLB adapter,
#319 the NFL adapter, #320 freshness decisions, #321 the catalog-first slate
read seam, #322 catalog read endpoints, #323 archive governance, #324 catalog
health and #325 rollout policy are
implemented and validated on
`feat/daily-sports-catalog`.

Completion record: child issues #310–#325 were delivered in merged PR #326.
The catalog retains its shadow-mode default and catalog-first/live rollback
configuration for staged operational use.

## Goal

Run a daily preparation job that discovers important matches, collects schedules,
lineups, projected starters, injuries, suspensions, depth charts, weather, venue,
rest/travel context, recent form, matchup metrics, market snapshots and relevant
news, then stores the results locally for fast catalog-first pick generation.

User requests use local data when its field-level freshness is sufficient and
selectively refresh only stale or missing fields. Offline use is supported when
the local snapshot satisfies the requested freshness rules.

## Architecture decisions

LangGraph orchestrates a deterministic workflow: discovery, prioritization,
fan-out, collection, normalization, validation, archival and publication.
LangChain is limited to structured extraction or grounded synthesis. Provider
selection, quotas, retries, freshness, scoring and safety rules stay deterministic
Python code. The existing pick scoring pipeline remains intact.

Catalog records use canonical sport, league, event, team, player and market IDs,
with provider-native aliases attached as observations. Immutable normalized
snapshots are separate from current state. A raw provider archive is retained for
replay and is available to authenticated app users as requested, but ingestion
removes credentials, cookies, signed URLs, session identifiers and other secrets.
Raw content has size limits, retention, source warnings and audit records.

Defaults: daily run at 06:00 UTC; bounded free-tier provider quotas; normalized
history retained 2 years; raw payloads retained 180 days; markets refreshed every
15 minutes, injuries and projected lineups every 2 hours, weather every 3 hours,
stable event facts daily, and historical form every 24 hours. All are configurable.

## Issue sequence

1. Epic and ADR
2. Canonical catalog contracts
3. Local catalog storage and migrations
4. Provider and normalization interfaces
5. Deterministic match importance scoring
6. Worker scheduler, durable leases and job states
7. LangGraph catalog workflow and checkpointing
8. Soccer adapter
9. Basketball adapter
10. MLB/baseball adapter
11. NFL adapter
12. Freshness tiers and selective refresh
13. Catalog-first pick/slate integration
14. Catalog API and Streamlit UI
15. Raw archive governance and access controls
16. Diagnostics, testing, performance and rollout

Sports can proceed in parallel after contracts and provider interfaces land.
Each issue must preserve idempotency, explicit unknown/conflicting states,
provider provenance, partial completion and existing pick/slate compatibility.

## Acceptance gates

- Daily jobs are resumable, quota-bounded and cannot run concurrently for the same date.
- Stable canonical IDs connect observations across providers and days.
- User requests avoid unnecessary network calls and expose freshness/confidence.
- Provider failures never become successful empty catalog snapshots.
- Raw archive data is redacted at ingestion and never enters diagnostics or ordinary logs.
- Existing scoring remains deterministic and all existing tests continue to pass.
- Catalog reads, refreshes, storage growth, stale fields and dropped work are observable.
- Rollout starts in shadow mode and retains a flag to fall back to live collection.

## GitHub tracking

- Epic: [#309](https://github.com/tlacahuepec/Colmillo-Picks/issues/309)
- [#310](https://github.com/tlacahuepec/Colmillo-Picks/issues/310) — canonical contracts and freshness states
- [#311](https://github.com/tlacahuepec/Colmillo-Picks/issues/311) — local catalog storage and migrations
- [#312](https://github.com/tlacahuepec/Colmillo-Picks/issues/312) — provider ports and normalization
- [#313](https://github.com/tlacahuepec/Colmillo-Picks/issues/313) — deterministic match importance scoring
- [#314](https://github.com/tlacahuepec/Colmillo-Picks/issues/314) — scheduler, leases and job states
- [#315](https://github.com/tlacahuepec/Colmillo-Picks/issues/315) — deterministic LangGraph workflow
- [#316](https://github.com/tlacahuepec/Colmillo-Picks/issues/316) — soccer catalog adapter
- [#317](https://github.com/tlacahuepec/Colmillo-Picks/issues/317) — basketball catalog adapter
- [#318](https://github.com/tlacahuepec/Colmillo-Picks/issues/318) — MLB/baseball catalog adapter
- [#319](https://github.com/tlacahuepec/Colmillo-Picks/issues/319) — NFL catalog adapter
- [#320](https://github.com/tlacahuepec/Colmillo-Picks/issues/320) — freshness and selective refresh
- [#321](https://github.com/tlacahuepec/Colmillo-Picks/issues/321) — catalog-first pick/slate integration
- [#322](https://github.com/tlacahuepec/Colmillo-Picks/issues/322) — catalog API and UI
- [#323](https://github.com/tlacahuepec/Colmillo-Picks/issues/323) — raw archive governance
- [#324](https://github.com/tlacahuepec/Colmillo-Picks/issues/324) — diagnostics and operational health
- [#325](https://github.com/tlacahuepec/Colmillo-Picks/issues/325) — tests, benchmarks and rollout

See the GitHub epic and child issues for implementation ownership and acceptance details.
