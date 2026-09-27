# Customer complaints investigation and story backlog

Date: 2026-09-20. Scope: page-state retention, NFL search/generation, Diagnostics Hub match identity, Best Today Slate, and untitled Pick History entries.

## Executive assessment

The complaints are supported by defects in the current checkout and by saved local runs. They are not explained by one missing NFL feature or one broken page. The main problems are lost UI state, inconsistent result contracts, unreliable discovery/collection, and failure paths that hide the evidence needed to explain a run.

The most immediate repairs are to preserve match identity, stop caching provider failures as high-confidence results, recover from transient NFL provider errors, retain failed slate details, and consistently distinguish completed work from useful recommendations. Navigation and polling need a coordinated repair because retaining a form alone will not reconnect a user to a running job.

There are **18 implementation stories** below, with priorities, boundaries, dependencies, and acceptance tests. This document is an investigation and implementation backlog; it does not implement the application fixes.

## Scope, evidence, and limits

- Inspected branch `feat/react-material-ui-redesign`, base commit `28d4a20` (`docs: record Track 1 completion in next-steps plan (#357)`), including the existing uncommitted changes. The React frontend, migration issue documents, and several backend additions were untracked at inspection time. Findings describe this working copy, not a verified deployed release.
- The README identifies React as the default UI. The named customer screens match that UI. Investigation followed React -> API -> orchestration/provider -> persistence/diagnostics. Deployment identity and whether every customer uses this build remain unverified.
- Queried `colmillo.db`, `diagnostics.db`, and `data/catalog.db` using SQLite URI `mode=ro`. Numbers below are local database observations, not production-wide rates. These databases include older development/history records; no customer-level attribution is available.
- Ran the existing focused backend suite, full frontend suite, production frontend build, and small deterministic probes. No live paid generation or catalog-refresh jobs were submitted. No live customer browser session or current NFL schedule was independently verified.
- Earlier planning described NFL as unimplemented. Current code and saved runs supersede that historical implementation status: NFL discovery, player props, game bets, scoring, and manual grading now exist. The previously agreed scope includes both game bets and expanded player props.

Evidence labels used below: **Observed** = saved data or executed probe; **Confirmed code path** = directly established in source; **Risk / needs replay** = plausible behavior that still needs a controlled integration or deployed replay.

## Complaint-to-story map

| Customer complaint | Findings | Stories |
|---|---|---|
| Moving between pages does not retain state | Pages unmount; forms, selections, discovery results, and grading drafts live inside the page. Job observation is also page-bound. | NAV-01, NAV-02, SLATE-02 |
| NFL search does not work | Discovery has returned matches, but an invalid-JSON error was cached for four hours as high confidence. Collection also fails or excludes all offers. Empty results do not explain which stage failed. | DISC-01, DISC-02, TIME-01, NFL-01, NFL-02, NFL-03 |
| Diagnostics does not identify the match | Team names exist in diagnostic operations but are not rendered. A slate's child match operations cannot be followed from the slate detail. Event timestamp contract also differs. | DIAG-01, DIAG-02, API-01 |
| Best Today Slate totally fails | The two latest NFL slates truly failed. Match-level evidence was not saved into their slate records. UI polling and result labels add independent failure modes. | NFL-01, NFL-02, SLATE-01, SLATE-02, SLATE-03, STATUS-01 |
| Pick History says Untitled Match | Structured non-soccer requests omit `match_query`; persistence defaults it to an empty string; the list API forwards it unchanged. | HIS-01 |
| Additional issue found during investigation | Saving an unedited grading form records every ungraded pick as a win. | HIS-02 |

## Findings and root causes

### F1. Page navigation destroys useful working state

**Confirmed code path.** [App.tsx](../../frontend/src/App.tsx#L43) switches between different page components. Each page owns its state through `useState`; navigating away unmounts the page. Examples include the Generate form and suggestions at [GeneratePage.tsx](../../frontend/src/pages/GeneratePage.tsx#L113), slate form/selection at [BestTodayPage.tsx](../../frontend/src/pages/BestTodayPage.tsx#L84), and History filters/selection/grading at [HistoryPage.tsx](../../frontend/src/pages/HistoryPage.tsx#L62).

Only the tab is represented in the URL. Diagnostic operation identity is held in `App` memory, so refreshing a diagnostic deep link loses that target. History and Best Today automatically choose the first result on a new mount. Unsaved outcome edits are also lost when selection changes.

The existing [QueryClientProvider](../../frontend/src/main.tsx#L12) does not solve this: the investigated pages call the API directly and retain results in page state. Prefer a shared view-state layer for drafts/filters and keyed query state for server records. Keeping all pages mounted may be a tactical option, but it would also retain background polling and is not a complete refresh/resume design.

### F2. Async observation is fragile and can show the wrong record

**Confirmed code paths; selection-race manifestations need replay.** Generate's recursive `setTimeout` loop has no unmount cleanup or request cancellation and stops after 150 polls, nominally 300 seconds ([GeneratePage.tsx](../../frontend/src/pages/GeneratePage.tsx#L238)). The backend job may keep running after the UI times out or disappears.

Best Today clears its interval on unmount, but does not persist selected job identity. Its polling catch silently stops polling without displaying an error. Selecting a completed slate does not clear an existing interval for a different running slate; that old interval can later overwrite the selected detail. `setInterval` can overlap slow requests. Unawaited auto-selection in `loadRecentSlates`, followed by explicit selection after submission, introduces another response-order race ([BestTodayPage.tsx](../../frontend/src/pages/BestTodayPage.tsx#L120)).

History and Diagnostics also apply detail responses without checking that the selected ID is still current. Diagnostics catches detail failures silently and can retain completeness information from a previous selection. These are related ownership/cancellation problems, not reasons to stop backend work when changing tabs.

### F3. History titles are missing at creation, not just rendering

**Observed and confirmed code path.** The database contained 106 pick records. All 70 structured non-soccer records had blank titles: 39 NFL, 16 basketball, and 15 baseball. All 70 still contained both team names in `request_json`, making a read-time repair possible without regenerating picks or guessing match identity.

The structured branch in [_handle_structured_picks](../../services/api/main.py#L693) constructs a request with teams/date/sport, but no `match_query`. [create_pending_pick_run](../../services/api/db.py#L299) writes an empty string when that field is absent. [_row_to_summary](../../services/api/main.py#L522) and the detail serializer return that field unchanged. [HistoryPage.tsx](../../frontend/src/pages/HistoryPage.tsx#L361) falls back to `Untitled Match`; its selected report heading can be blank too.

Example: `6c89daa5-3791-40b8-803b-0dc5e6eb7d06`, created at `2026-09-20 17:09:54` UTC, has a blank title but request teams `Saints` and `Ravens`. This is evidence of stored identity, not independent confirmation that the requested fixture exists.

### F4. NFL discovery errors can become persistent misleading results

**Observed and confirmed code path.** Cache key `discovery:2026-09-20:nfl:soccer:10:utc` was created at `06:38:14` UTC and expired at `10:40:02` UTC. It stored zero NFL matches and `Gemini returned invalid JSON: No valid JSON object found: line 1 column 1 (char 0)`, with confidence `high`. This was earlier than the noon complaint; it proves the failure mechanism, not that this exact cache entry caused the noon session.

The endpoint [saves all responses for four hours with confidence high](../../services/api/main.py#L1380), including per-sport errors. Cache hits return immediately without rerunning kickoff/eligibility filtering or finishing diagnostics with the stored result's outcome. The [cache key](../../services/api/main.py#L583) omits provider/model and uses `utc` for an omitted timezone even though NFL resolves that omission to the configured zone or America/Chicago.

Later saved cache entries contain 3 and 10 NFL matches with no discovery error, so the evidence does **not** support a blanket conclusion that NFL discovery always returns nothing. Those entries prove returned suggestions, not their factual accuracy or downstream pick availability. A cache entry generated before kickoff can continue suggesting started games until expiry because its response is returned unchanged.

### F5. A discovery suggestion is less verified than the NFL collector requires

**Observed probe and confirmed code path.** [_normalize_sport_result](../../skills/soccer-prop-picks/scripts/match_discovery.py#L221) filters NFL by kickoff, local date, and league. It does not establish provider-backed fixture evidence. `_normalize_match` accepts model-provided sources and allows no sources; team strings are not proof of a fixture. A synthetic future NFL matchup with zero sources survived normalization. The same synthetic response with a missing kickoff became zero matches while retaining `data_quality.status=ok` and `error=null`.

The NFL collector independently verifies fixture identity, date, and citations before collecting offers. Across 20 saved NFL runs with outcome `no_picks`, nine had a fixture-verification exclusion and eleven had an offer/data-qualification exclusion. Nine of those 20 also recorded at least one offer citation rejection. These reason counts overlap and are not a distribution of unique underlying causes.

This explains why a user can receive a suggestion, click Run, and receive no usable picks. It does not establish whether every rejected fixture/offer was wrong or whether evidence was available but lost during extraction. That distinction needs captured-provider replay under NFL-02/NFL-03. Relaxing citation checks or manufacturing odds would hide the defect rather than repair it.

### F6. NFL collection has demonstrated transport and extraction failures

**Observed and confirmed code path.** Of 39 local NFL runs: 11 had outcome `failed`, 20 `no_picks`, seven `success` with a total of 24 scored picks, and one legacy `success` record had no outcome and zero picks. Do not interpret `28 status=success` as 28 successful recommendation runs.

Diagnostic events recorded `RemoteProtocolError` in Gemini research and extraction, schema `ValidationError`, and missing-citation failures. The new [research_then_extract](../../skills/soccer-prop-picks/scripts/llm/gemini_client.py#L293) path performs two direct SDK calls without the application's retry loop used by `generate_structured`. Configuring `max_retries` on the client therefore does not apply that application-level retry policy to this path. Any SDK-internal retries are outside what this inspection established.

[NflCollector](../../skills/soccer-prop-picks/scripts/nfl_collection.py#L292) validates fixture/context, parses entities, then collects both game and player offer groups. [NflModule](../../skills/soccer-prop-picks/scripts/nfl_module.py#L35) distinguishes provider failure from no qualified picks, but exposes a generic collection message to callers. Both market groups are collected even when the slate later scores only one requested group, adding avoidable provider work. Some malformed entries are deliberately skipped, while invalid top-level context can abort the entire collection.

### F7. The latest Best Today failures are real, and their details were discarded

**Observed.** The latest two saved slates both requested NFL only, three matches, and September 20:

| Slate ID | Created UTC | Duration | Child outcomes | Persisted slate detail |
|---|---|---|---|---|
| `aa9b8193-7286-4cab-97f8-68804d7bced4` | 17:02:47 | 281,504 ms | Falcons/Panthers: no picks; Chiefs/Colts: failed; Cowboys/Commanders: failed | Failed at aggregation; zero match records; attempted/succeeded counts null |
| `d0c12515-2789-43ea-82a3-70beb1a77414` | 16:45:02 | 416,906 ms | Chiefs/Colts: failed; Cowboys/Commanders: no picks; 49ers/Dolphins: no picks | Failed at aggregation; zero match records; attempted/succeeded counts null |

For the latest slate, the Chiefs/Colts child recorded a `RemoteProtocolError` during extraction and the Cowboys/Commanders child recorded one during research. Their operation IDs are `061ee1af-b7d3-4ce4-a589-1914a9975444` and `1cf3844b-17cd-4da6-abd7-8b38b910e2ba`. These are local provider-event observations; the precise remote/proxy/network origin of the transport error remains unresolved.

**Confirmed code path.** [execute_slate_job](../../services/api/slate_orchestration.py#L37) constructs per-match results. When there are no candidates and any match/discovery failure, [_execute_slate_record](../../services/api/main.py#L1091) invokes [mark_slate_failed](../../services/api/db.py#L781), which persists only status/error/latency. It does not save the already-computed `match_runs`, attempt counts, discovery duration, or token counts. The UI cannot render details that the record never saved.

Discovery errors are reduced to a count in `SlateResult`; their sport-specific reason text is not persisted as a structured discovery summary. Child diagnostics survive separately, but slate match summaries do not contain child operation IDs. Earlier slates have usable candidates, so Best Today is not universally broken; the two most recent failures are still a concrete customer-impacting incident pattern.

### F8. Execution status and result outcome are confused throughout the UI

**Observed and confirmed code path.** [mark_slate_success](../../services/api/db.py#L741) writes `status=success` when processing completes, with `outcome=partial` or `no_picks` as appropriate. Pick persistence uses the same lifecycle/result distinction. The backend therefore does not need to be changed simply to make all empty results read `failed`.

History and recent slate badges display `status`. Best Today's partial banner checks `status=partial` or failed/pending match rows, so it can miss partiality caused only by discovery failures. Its type declarations and tests include terminal statuses that are primarily represented by `outcome` in real API data. Three recent saved slates had `status=success,outcome=partial`.

Define the product display contract explicitly: lifecycle controls polling; outcome controls recommendation messaging. A completed, evidence-backed no-pick decision is valid, but a fixture that could not be verified must say so rather than imply that a useful analysis succeeded.

### F9. Diagnostics has identity data but does not show it; related contracts also drift

**Observed and confirmed code path.** Diagnostic operations have `home_team`, `away_team`, `sport`, and match date in metadata. [DiagnosticsPage](../../frontend/src/pages/DiagnosticsPage.tsx#L330) renders operation ID, sport, duration, and outcome; neither its table nor summary renders team names. Slate parent operations legitimately have no single team pair, so they need a dated slate label and links to child matches rather than fabricated teams.

The backend stores `parent_operation_id`, but list filtering supports only operation ID/sport/outcome/service/since. The frontend requests only 20 operations and offers no page navigation. Opening a parent operation fetches its own events, not the child matches' events. Thus, the root slate export/detail is not a complete traversal of the slate execution tree.

The event wire field is `ts` ([services/diagnostics.py](../../services/diagnostics.py#L570)); the frontend type and renderer expect `timestamp` ([DiagnosticsPage.tsx](../../frontend/src/pages/DiagnosticsPage.tsx#L454)). A serialization probe confirmed `ts` remains `ts` after sanitization. Existing UI tests fabricate `timestamp`. Real events can therefore display invalid time text. Missing summaries default to `The operation completed successfully.` even when that conclusion is unsupported. The health card measures diagnostic storage availability, not end-to-end provider or worker readiness.

### F10. Date handling creates a separate evening-boundary defect

**Observed probe and confirmed code path.** Generate and Best Today use `new Date().toISOString().split("T")[0]` as today's date, and do not send the optional timezone. At `2026-09-21T00:30:00Z`, that expression chooses September 21 while America/Chicago's date is September 20. A Node probe reproduced those two dates. NFL's backend filtering otherwise interprets an omitted timezone as configured/local Chicago time.

This is a confirmed evening defect but is **not** a direct explanation for a complaint at noon Chicago time. Its scope includes defaults, requests, kickoff display, cache identity, refresh-after-midnight behavior, and historical run dates.

### F11. History can manufacture wins through defaults

**Confirmed code path; no claim of actual customer data corruption.** [HistoryPage.tsx](../../frontend/src/pages/HistoryPage.tsx#L170) maps every scored pick to an outcome and uses `gradingValues[rank] || "win"`. The form uses the same default. Clicking Save without changing the controls records wins for every previously ungraded pick, and grading one pick can submit wins for untouched others.

This is an additional trust issue discovered in the requested history investigation. It should be repaired promptly; do not retroactively change stored grades without evidence of their origin.

## Why existing tests passed

Executed on this working copy:

| Verification | Result | What it establishes |
|---|---|---|
| Focused Python discovery/NFL/slate/diagnostic suites | 113 passed; 10 warnings | Existing isolated backend contracts pass |
| Full frontend `npm.cmd test -- --reporter=dot` | 9 files, 50 tests passed | Existing mocked component/client expectations pass |
| Frontend `npm.cmd run build` | Passed | TypeScript and production bundling succeed |
| Discovery normalization probe | Uncited future fixture accepted; missing kickoff silently produced empty/ok | Evidence and rejection-reason gap reproduced |
| Diagnostics serialization probe | Output contained `ts`, no `timestamp` | Timestamp mismatch reproduced |
| UTC/local-date probe | UI September 21, Chicago September 20 | Date-boundary mismatch reproduced |

Frontend tests/build first encountered sandbox directory-read denial; both succeeded when rerun with approved escalation. Test output also reported jsdom's unimplemented document navigation. Build reported an approximately 866 kB minified JS chunk; performance splitting is follow-up work, not an established cause of these complaints.

Artifact validation found 18 unique story IDs and 26 valid local source/document links. The worktree-wide whitespace check reported an existing extra blank line at EOF in `llm/intelligence_prompt_builder.py`; that unrelated file was not edited for this audit. This is not a claim that the entire repository quality gate is green.

The tests do not exercise a tab round trip with drafts or a running job. History fixtures always supply a title. Diagnostic fixtures supply a timestamp field unlike the backend. The slate test named “polls until completion” returns completed detail immediately and does not require a queued -> running -> terminal transition. API mocks usually return full slate details for list calls even though the real list endpoint returns summaries. NFL provider tests use controlled data and do not establish live provider availability or evidence yield.

[The previous migration backlog](../issues/README.md) marks all 14 items Done. Treat these new stories as follow-up acceptance gaps; those completed labels are not proof that the customer journeys work. In particular, ISSUE-07/08, ISSUE-09/10, ISSUE-11/12, and ISSUE-13 overlap the affected screens. Do not reopen every old item or duplicate its original scope indiscriminately.

## Implementation stories

Priorities: **P1** = immediate customer functionality/trust; **P2** = reliability/completeness follow-up. No P0 incident severity is asserted without deployed impact verification. Sizes S/M/L are relative change sizes, not delivery-date commitments. All stories start as **Proposed**.

### HIS-01 — Give every stored run a stable match title (implemented in working tree)

- **P1 / M.** As a customer, I can identify new and old matches in History before opening them.
- **Scope:** Shared backend display-identity builder; list/detail response fields; title generation for new structured requests; safe read-time fallback for old records. Render title plus sport/date in History. Preserve existing nonblank legacy queries. Prefer additive fields over repurposing a raw user query as a canonical fixture ID.
- **Acceptance:** All four sports have nonempty list/detail titles from submission onward, including failed/no-pick runs. The 70 recoverable blank records display their stored teams without regeneration. Missing/malformed identity falls back to a dated run label plus short ID, never invented teams. No database rewrite is necessary for initial recovery.
- **Tests:** Structured submission -> list -> detail for each sport; legacy row; blank row with valid request; malformed JSON/absent teams. Assert selected heading and list title agree.
- **Files:** `services/api/main.py`, `services/api/db.py`, frontend `api/types.ts`, `HistoryPage.tsx`.
- **Dependencies:** None. Coordinate shared response definitions with API-01.

### HIS-02 — Grade only outcomes the customer explicitly selects (implemented in working tree)

- **P1 / S.** As a customer, saving one grade never marks untouched picks as winners.
- **Scope:** Introduce ungraded form state; submit only deliberately graded rows; preserve existing stored grades and identify unsaved edits.
- **Acceptance:** Initial form has no implied wins. Saving untouched form performs no write. Grading one row submits that row only. Reload shows the stored grade. Failed save preserves edits. Existing outcomes are not rewritten simply because a page was opened.
- **Tests:** Zero changes, one changed row, existing grades, failed save, multi-row edit; verify hit-rate changes reflect only accepted grades.
- **Files:** `HistoryPage.tsx`, related component/API outcome tests.
- **Dependencies:** None; NAV-01 subsequently preserves grading drafts across navigation.

### NAV-01 — Retain page state across navigation and reload

- **P1 / M.** As a customer, I can leave a page and return to the same work. **Implemented in the working tree.**
- **Scope:** Shared view state for Generate draft/suggestions, slate form/selection, History filters/page/selection/grading drafts, and Diagnostics filters/selection. Apply the same explicit policy to Catalog and Grounding Audit controls. Put shareable selection/filter identity in the URL; version short-lived session drafts. Do not store secrets or large telemetry/provider payloads in draft storage.
- **Acceptance:** A -> B -> A and browser Back/Forward preserve selections and drafts. Reload restores supported draft fields and selected resource IDs, then refetches server data. Changed date invalidates stale suggestions; a new calendar day does not silently repurpose an old draft. There is an explicit reset action.
- **Tests:** App-level navigation round trips, refresh hydration, malformed/old session schema, selected item outside the first results page, unsaved grading draft.
- **Files:** `App.tsx`, shared state/hooks, affected pages.
- **Dependencies:** None; pair with NAV-02 for running jobs. Coordinate History draft shape with HIS-02.

### NAV-02 — Resume pick jobs and reject stale async responses

- **Implementation status:** Pick and slate observers now reconnect from persisted accepted IDs, stop on unmount or selection changes, prevent overlapping slate polls, and discard stale History/Diagnostics detail responses. Explicit Retry controls and dedicated deferred-response coverage remain follow-up work.
- **P1 / M.** As a customer, leaving a page does not lose my job or cause another result to appear under its selection.
- **Scope:** Key server state by resource ID; capture accepted pick/operation IDs immediately; cancel observers/requests on unmount and selection change; reconnect without resubmitting. Use single-flight, bounded polling with explicit retry/resume feedback. Apply stale-response guards to History and Diagnostics detail loads.
- **Acceptance:** Background job survives navigation; returning/reloading fetches the same ID. Timeout means observation timed out, not that backend execution failed. A delayed response for A never overwrites selected B. A network failure exposes Retry and History/Diagnostics links. No duplicate create request is issued during hydration or React StrictMode.
- **Tests:** Deferred A/B responses, unmount while polling, reload while queued, long-running job, one transient poll failure, double-click submission.
- **Files:** Generate page, shared job/query hooks, History/Diagnostics selection loaders, API client.
- **Dependencies:** NAV-01 for persisted IDs; STATUS-01 for lifecycle mapping. SLATE-02 adopts the same observer primitives.

### TIME-01 — Use one explicit date timezone throughout the journey

- **Implementation status:** The frontend now uses an explicit `America/Chicago` default for customer calendar dates (rather than UTC midnight) and sends it with discovery, manual picks, cache discard, and Best Today requests. Midnight-boundary coverage passes. A selectable customer timezone remains a future preference enhancement.
- **P1 / S.** As a customer in Chicago, “today” and a selected fixture date mean the same day on every screen.
- **Scope:** Central local-date helper and timezone setting/default; explicit timezone on discovery, manual/suggested picks, and slate requests; consistent kickoff display/cache key semantics.
- **Acceptance:** Chicago 19:30 on September 20 defaults to September 20 even after UTC midnight. Late NFL kickoff on the next UTC day remains on its local game date. Discovery, Use Match, Run, and Best Today carry identical date context. Existing historical records retain their original event dates.
- **Tests:** UTC/local-midnight boundary, DST transition, explicit nondefault zone, invalid zone, cached response after kickoff.
- **Files:** Generate/Best Today pages, request types, backend date/cache helpers.
- **Dependencies:** None; resolve default-zone policy before finalizing DISC-01's cache format.

### DISC-01 — Make discovery caching reflect quality and eligibility

- **Implementation status:** Implemented in the working tree: partial/provider-error responses are returned but never cached; the following request can recover the failed sport. Healthy match results retain the four-hour high-confidence cache, while healthy empty schedules use a fifteen-minute medium-confidence cache. Recovery is covered by API regression tests.
- **P1 / M.** As a customer, retrying discovery can recover from an error and never reoffers started games as fresh suggestions.
- **Scope:** Cache policy by per-sport outcome; protect last known good data; short/backoff caching for transient failures if needed; honest quality labels; effective timezone/provider/model/version in cache identity; kickoff filtering on cache reads. Preserve force-refresh/discard behavior.
- **Acceptance:** Invalid-JSON/provider errors are not saved as four-hour high-confidence successes. Cached empty/error outcomes retain their meaning in both UI and diagnostics. Successful sports survive another sport's failure. Started matches disappear from cached suggestions. Provider/model or timezone changes cannot reuse an incompatible entry. Old cache versions are ignored safely.
- **Tests:** Error -> retry -> success, partial response, expired response, kickoff crossing, provider/model/zone separation, cache-hit diagnostic outcome, concurrent refresh requests.
- **Files:** `main.py` discovery routes/helpers, `catalog/storage.py`, discovery endpoint tests.
- **Dependencies:** TIME-01 for effective timezone; DISC-02 supplies richer per-sport quality when available.

### DISC-02 — Distinguish verified fixtures from unavailable discovery

- **P1 / M.** As a customer, I know whether no matches exist, discovery failed, or suggestions could not be verified.
- **Scope:** Validate and preserve fixture provenance from actual provider evidence; canonical teams/league/date; structured per-sport outcomes and filter reason counts. Clearly label or withhold unverified suggestions. Use the same discovery result contract for Generate and slate orchestration.
- **Acceptance:** Missing kickoff, unsupported league, wrong date, already-started game, no citations, malformed output, and genuinely empty schedule are distinguishable. A model-authored URL alone does not establish provider grounding. Rejected items do not leave an unexplained empty `ok` response. The interface does not claim fixture truth solely because text normalization succeeded.
- **Tests:** Synthetic uncited fixture from this audit; missing kickoff; all filtered; verified empty schedule; mixed valid/invalid entries; actual sanitized provider-envelope fixtures with grounding metadata.
- **Files:** `match_discovery.py`, prompt builder, discovery response models, Generate page, slate discovery adapter.
- **Dependencies:** API-01 coordinates response types. Existing catalog can be reused only where identity/provenance/freshness contracts match; a catalog rewrite is not required for this story.

### NFL-01 — Recover boundedly from transient research/extraction failures

- **Implementation status:** Implemented in the working tree: research and extraction have separate bounded transport retries, emit stage/attempt retry telemetry, preserve the original research evidence for extraction retries, and fail permanently without retrying auth/schema-like errors. Deterministic replay coverage includes each retry phase and non-retryable failure.
- **P1 / M.** As a customer, one temporary provider disconnect does not discard an otherwise recoverable NFL analysis.
- **Scope:** Apply explicit timeout/retry classification to `research_then_extract`; retry research and extraction independently; preserve valid research evidence for extraction retry; emit attempt/stage/error metadata. Keep requests within a total time/cost budget.
- **Acceptance:** A transient research or extraction transport failure can recover in a deterministic retry test. Permanent auth/schema errors do not loop indefinitely. Retry does not replace original citations with extraction-generated links. Exhaustion produces a typed, actionable failure. Both manual Generate and Best Today use the policy.
- **Tests:** `RemoteProtocolError` then success for each phase; timeout exhaustion; nonretryable response; extraction retry retains original evidence and accurate usage/attempt counts.
- **Files:** `llm/gemini_client.py`, NFL provider adapter, provider instrumentation/tests.
- **Dependencies:** None. Provider/network root cause still needs controlled deployed observation; successful local mocks cannot prove remote recovery.

### NFL-02 — Improve NFL extraction and offer coverage without weakening evidence rules

- **Implementation status:** Implemented in the working tree: clear provider market aliases normalize before validation; malformed, unsupported, and uncited offers become bounded structured rejections without discarding valid offers; malformed offer responses remain honest group unavailability; game-only requests skip the player-offer call. Focused NFL and pipeline tests cover the new recovery boundaries.
- **P1 / L; split into a context-normalization slice and an offer-group slice if needed.** As a customer, available verified data survives harmless format differences, and unsupported data is explained.
- **Scope:** Replay sanitized failures; classify malformed context vs malformed entity/offer; normalize supported enum/shape aliases deliberately; retain offer rejection fields and citation mappings. Collect only the requested player/game groups where possible. Keep context needed by both groups shared.
- **Acceptance:** Recoverable format variants do not abort unrelated valid entities. Unsupported or uncited data stays excluded. All existing seven player markets plus moneyline/spread/total remain represented in the matrix. Game-only requests do not depend on a player-offer call. Every rejected offer has a structured reason; partial useful coverage survives unrelated group failure.
- **Tests:** Invalid top-level fixture vs one invalid player/offer; missing citations; mismatched fixture; research-to-extraction URL mapping; each market group; current sample with some valid and some malformed offers.
- **Files:** `nfl_collection.py`, `nfl_module.py`, provider replay fixtures, slate dependency builder.
- **Dependencies:** NFL-01; coordinate DISC-02 fixture identity. Do not lower scoring thresholds merely to increase output counts.

### NFL-03 — Explain the difference between unverified input and a valid no-pick decision

- **P1 / M.** As a customer, an NFL result tells me what prevented recommendations and what I can do next.
- **Implementation status:** Implemented in the working tree: a bounded NFL recommendation summary now distinguishes unverified fixtures, provider failure, unavailable offers, insufficient supported data, and a legitimate threshold no-pick. It is persisted with successful runs, exposed in traces/reports, carried to NFL slate match rows, and rendered on Generate and History.
- **Scope:** Preserve typed exclusions/coverage summaries through Generate, saved History, slate match results, and diagnostics; separate unverified fixture, unavailable offers, insufficient supported data, provider failure, and no qualifying selection. Record counts without exposing raw prompts or secrets.
- **Acceptance:** The nine fixture-verification cases and eleven offer/data cases represented in this audit would receive different explanations. Customers see a useful action appropriate to the reason, and retries are not promised to fix a legitimate no-pick decision. Raw pipeline completion is not presented as successful recommendations.
- **Tests:** Replay each reason family; mixed group coverage; available offers but no directional support; no duplicated/conflicting messages across screens.
- **Files:** NFL trace/report adapters, API summaries, Generate/History/slate detail panels.
- **Dependencies:** NFL-02, STATUS-01; SLATE-01 for persistent match summaries.

### SLATE-01 — Persist the complete result even when a slate fails

- **Implementation status:** Implemented in the working tree: aggregation failures now persist candidates, every completed match run, discovery timing, match counts, and token usage in the same terminal failure write. Failed detail responses can therefore explain attempted matches instead of showing an empty slate shell. Database/API/orchestration regression tests pass.
- **P1 / M.** As a customer, a failed slate still tells me which matches were attempted and why each failed or produced no picks.
- **Scope:** One terminal persistence operation for candidates, match results, discovery results, counts, durations, usage, and outcome, including failed aggregation. Add child operation IDs to match summaries. Keep useful partial candidates on mixed outcomes.
- **Acceptance:** Replaying each of the two recent failed slate shapes saves three match rows and nonnull attempt counts. Per-sport discovery failures survive even if no matches were attempted. Error stage reflects the failing stage rather than always becoming discovery/aggregation. Existing incomplete rows show “details not recorded”; they are not represented as zero attempts. Recover historical details from retained diagnostics only when unambiguous.
- **Tests:** All provider failures; no-picks plus failures; only discovery errors; mixed successful sports; successful empty schedule; DB/API round trip preserving all fields; transactional final write.
- **Files:** `slate_orchestration.py`, `main.py`, `db.py`, slate response models/tests.
- **Dependencies:** None for preservation; DIAG-01 uses new child IDs. Coordinate database/API fields with API-01.

### SLATE-02 — Make slate selection and polling reliable

- **Implementation status:** Implemented in the working tree: accepted slate IDs are selected before the rail refresh; stale details and overlapping polls are rejected; list/detail/poll failures show Retry or Resume observation actions. The transient-list-error retry path has component coverage.
- **P1 / M.** As a customer, Best Today follows my selected slate and reports interrupted observation visibly.
- **Scope:** Use the shared resource observer; stop old intervals before every selection, prevent overlapping requests, guard late responses, and remove competing implicit/explicit selection after create. Render request/poll/detail errors with retry. Retain accepted operation ID before detail arrives.
- **Acceptance:** Selecting completed B while A runs never lets A replace B's detail. A slow poll never overlaps another poll for that resource. An API failure does not silently stop the progress display. Create selects the newly accepted ID regardless of list-refresh order. Navigation/reload resumes that ID without creating another job.
- **Tests:** A-running -> B-complete with delayed A terminal response; list/create race; transient 500; slow request; unmount/reload; terminal no-picks result using real lifecycle/outcome fields.
- **Files:** `BestTodayPage.tsx`, shared observer, component tests.
- **Dependencies:** NAV-02, STATUS-01. Avoid a separate incompatible polling framework.

### SLATE-03 — Expose incremental progress and bounded execution

- **P2 / M.** As a customer, a multi-minute slate shows useful progress and remains understandable after interruption.
- **Scope:** Persist progress after discovery and each match; expose stage/completed/remaining counts and heartbeat; define total/provider budgets and interrupted-job behavior. Use bounded concurrency only after client evidence/usage state is isolated; the current shared discovery/NFL client has mutable last-response state.
- **Acceptance:** A four-to-seven-minute run is visibly progressing; completed match results can be inspected before the whole slate ends. A stopped worker is distinguishable from a slow provider. Restart/resume cannot duplicate completed work or misattribute citations. Budget exhaustion retains finished results and explains unfinished ones.
- **Tests:** Slow synthetic match, provider hang, worker interruption, resume/idempotency, per-match checkpoint recovery, isolated evidence under any introduced concurrency.
- **Files:** Slate orchestration, DB/job layer, status response, Best Today progress panel.
- **Dependencies:** SLATE-01, SLATE-02, NFL-01. This is a reliability enhancement; neither latest failed slate was still queued at inspection.

### STATUS-01 — Separate execution lifecycle from recommendation outcome everywhere

- **Implementation status:** Core frontend mapping is implemented in the working tree and is used by History, Generate, and Best Today: no-pick results do not appear as recommendations, partial outcomes remain warning states, and legacy success records retain a compatible label. Diagnostics/API-wide adoption remains coordinated with API-01.
- **P1 / S.** As a customer, “completed” does not imply picks exist or that every sport succeeded.
- **Scope:** One shared mapping for pending/queued/running/terminal lifecycle and success/partial/no_picks/failed outcome; use it in Generate, History, slate list/detail, and diagnostics links. Maintain compatibility with legacy rows missing outcome.
- **Acceptance:** `status=success,outcome=no_picks` displays a no-pick result and stops polling. `status=success,outcome=partial` displays partial even when match rows have no failures but discovery did. A legacy empty record has an honest unknown/empty label. Badges and report text do not contradict each other.
- **Tests:** Cross-product of lifecycle/outcome, null legacy outcome, real failed-slate shape, discovery-only partiality, no-pick completion.
- **Files:** Shared frontend result mapping, `api/types.ts`, relevant screens/tests.
- **Dependencies:** None; publish this small contract before NAV-02/SLATE-02/NFL-03 integration.

### DIAG-01 — Make diagnostic operations identifiable and connected

- **Implementation status:** Initial identity rendering is implemented in the working tree: Diagnostics list and detail now show `home vs away`, sport, and a truthful sport-plus-short-ID fallback. Slate child-operation persistence/navigation remains dependent on the additive SLATE/API contract work.
- **P1 / M.** As a customer, I can identify the match and follow a failed slate to the affected child match.
- **Scope:** Render teams, sport/league when available, event date, operation type, and short ID. Add parent/child navigation and bounded child listing/filtering. A slate label uses date/sports; discovery uses its requested date/sports where recorded. Older records receive honest fallback labels.
- **Acceptance:** Both list and detail show matchup identity when present. Clicking a slate's failed match opens that exact child operation. Parent/child context survives URL reload. Parent export/detail states whether child events are included and offers access to them. Missing single-match identity is not filled with unrelated teams.
- **Tests:** Single pick, slate parent with three children, discovery operation, legacy summary, missing metadata, deep-link refresh, child pagination.
- **Files:** Diagnostics UI/types, diagnostics routes/store query, slate match summaries.
- **Dependencies:** SLATE-01 for direct child IDs; NAV-01 for URLs. Initial team-name rendering can ship independently.

### DIAG-02 — Make the timeline, refresh, and failure messaging trustworthy

- **P2 / M.** As a customer, diagnostic times and messages reflect the selected operation and all retained evidence is reachable.
- **Scope:** Map wire `ts` correctly; remove optimistic success fallback; show detail-load errors; reset completeness/events on selection; page through operations and events; refresh active operations; distinguish diagnostic-storage health from pipeline readiness.
- **Acceptance:** Real serialized events show valid timestamps. A failed operation with no summary never says it completed successfully. Selection cannot show a previous operation's events/completeness. Operations beyond the first 20 and events beyond the first 100 are reachable with truncation/retention messaging intact. Refresh preserves current selection where valid.
- **Tests:** Backend-produced event envelope, missing summary/time, detail failure/retry, response-order race, active refresh, operation/event pagination, truncated export.
- **Files:** Diagnostics page/client/types and route-contract tests.
- **Dependencies:** NAV-02 response guards; API-01 wire contracts. Keep privileged admin controls outside this repair unless their own behavior is explicitly scoped.

### API-01 — Align frontend types and mocks with real response shapes

- **P1 / M.** As a maintainer, tests fail when the API and customer screens disagree.
- **Scope:** Separate slate summary/detail types; represent nullable counts/durations and actual lifecycle/outcome values; type diagnostic event timestamps and parent links; add response-contract fixtures exported from isolated API tests. Prefer generated definitions or one explicit, tested adapter over unchecked casts.
- **Acceptance:** List mocks contain list fields, not fabricated detail-only data. Diagnostic fixtures use the actual wire envelope. Nullable failed-slate counts do not appear as actual zero activity. Contract checks flag renamed/missing fields and prevent a fixture-only success path from passing as end-to-end coverage.
- **Tests:** Backend serializer -> frontend adapter fixture checks for list/detail/status/events; legacy rows; failed/no-pick/partial records. Keep provider calls mocked in ordinary CI.
- **Files:** Frontend client/types/fixtures, backend API contract tests, CI contract step if needed.
- **Dependencies:** Coordinate additive contracts with HIS-01, SLATE-01, STATUS-01, and DIAG-01; one owner should sequence edits to shared model files.

### QA-01 — Gate release on the five customer journeys

- **P1 / M.** As a customer, these complaints remain fixed when a new UI/API build ships.
- **Scope:** App-level navigation and real HTTP integration journeys backed by isolated DBs and controlled providers; sanitized provider-envelope replay; a bounded deployed smoke check with known upcoming fixture and documented build identity. Update old issue links with the regression evidence rather than simply changing their status labels.
- **Acceptance:** Each complaint has a failing-before/passing-after test or documented deterministic reproduction. Cover NFL player props and game bets, one other sport, empty schedule, provider failure, partial slate, long-running job, history identity, explicit grading, and diagnostics child navigation. Release evidence records UI/API commit, timezone, worker mode, operation IDs, and actual outcomes.
- **Tests:** User navigates away mid-job and returns; discovers a fixture and runs it; creates NFL-only and mixed-sport slates; opens untitled legacy record; follows failure to matching diagnostics; retries transient failure without duplicate submission. A valid no-pick outcome may pass if honestly explained; requiring a wager every time is not a quality criterion.
- **Files:** App integration/E2E tests, sanitized replay fixtures, release checklist, related `docs/issues` entries.
- **Dependencies:** Regression tests can begin immediately; full release gate follows the P1 fixes. Live provider verification remains distinct from mocked CI success.

## Delivery sequence and ownership

| Phase | Recommended order | Exit evidence |
|---|---|---|
| 1: Restore identity and honest results | HIS-01, HIS-02, STATUS-01; SLATE-01; initial DIAG-01 team labels; TIME-01 and DISC-01 | Existing blank records identifiable; untouched grades do not become wins; failed slate details retained; no high-confidence long-lived error cache |
| 2: Stabilize the customer workflows | NAV-01 -> NAV-02 -> SLATE-02; NFL-01 -> NFL-02 -> NFL-03; DISC-02; finish DIAG-01; API-01 throughout | Navigation/resume and live-shaped contracts verified; replayed NFL failures recover or produce an explicit, accurate result |
| 3: Close the reliability/acceptance gaps | DIAG-02, SLATE-03, full QA-01 acceptance gate | Timelines/progress usable, all relevant evidence reachable, deployed build verified against the complaints |

Keep each PR focused. `services/api/main.py`, `services/api/db.py`, frontend `api/types.ts`, and the affected page files are shared edit hotspots; sequence their contract changes before dependent UI work. Do not merge a broad state rewrite, NFL provider repair, and database result-model change as one slice. Larger stories should be split along the boundaries identified above if a review becomes difficult.

Recommended first slice: **HIS-01**, because the cause is deterministic, all 70 affected local records are recoverable from existing data, and it restores basic customer navigation without a provider dependency. In the same immediate priority queue, **HIS-02**, **SLATE-01**, **DISC-01**, and **NFL-01** address trust and the most concrete failure mechanisms.

## Release validation and remaining uncertainty

1. Confirm the deployed UI/API build and worker configuration; reproduce with a recorded operation ID and explicit timezone. Do not assume the local snapshot is the customer deployment.
2. Use isolated tests to prove identity recovery, cache correctness, stale-response rejection, accurate outcomes, and failure-detail persistence before replaying paid provider requests.
3. Replay sanitized research/extraction envelopes from a transport failure, malformed context, missing citations, and an eligible offer. Determine whether citation rejection reflects genuinely unsupported evidence or a mapping defect.
4. Run bounded live checks for a verified upcoming NFL fixture and a mixed slate. Measure discovery success, fixture verification, offer qualification, recommendation yield, and provider failure separately. Record latency by stage and retain operation IDs.
5. Verify browser navigation/refresh, slow network, failure/retry, no-pick explanations, and history/diagnostic links with actual HTTP responses. Automated unit-test success alone does not close QA-01.

Unresolved: the exact provider/network origin of `RemoteProtocolError`; the proportion of rejected NFL offers that could be recovered through normalization/provenance repair; whether customer “search” refers to discovery, manual Generate, or both; and the deployed build's relationship to this dirty worktree. The report covers both discovery and generation so work can begin without waiting on that terminology.

## Reproducibility notes

Run from the repository root:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_nfl_discovery.py tests/test_nfl_collection.py tests/api/test_nfl_acceptance.py tests/test_match_discovery.py tests/api/test_match_discovery_endpoint.py tests/test_slate_orchestration.py tests/test_slate_db.py tests/api/test_slate_endpoint.py tests/api/test_diagnostics.py
```

Run from `frontend`:

```powershell
npm.cmd test -- --reporter=dot
npm.cmd run build
```

Useful read-only SQL against a copy or a SQLite connection opened with URI `mode=ro`:

```sql
-- Blank-title extent and identity recoverability.
SELECT sport, status, COUNT(*) AS runs,
       SUM(match_query = '') AS blank_titles
FROM picks_history GROUP BY sport, status;

SELECT COUNT(*) AS blank_titles,
       SUM(json_extract(request_json, '$.home_team') IS NOT NULL
           AND json_extract(request_json, '$.away_team') IS NOT NULL) AS recoverable
FROM picks_history WHERE match_query = '';

-- Completion is different from useful recommendations.
SELECT status, outcome, COUNT(*) AS runs,
       SUM(json_array_length(scores_json)) AS scored_picks
FROM picks_history WHERE sport = 'nfl' GROUP BY status, outcome;

-- Failed slates should not lose already attempted matches.
SELECT id, created_at, status, outcome, matches_attempted, matches_succeeded,
       json_array_length(match_runs_json) AS saved_match_runs,
       error_stage, error_message, latency_ms
FROM slate_runs ORDER BY created_at DESC LIMIT 5;

-- Against diagnostics.db: retained child operations for the latest failed slate.
SELECT operation_id, home_team, away_team, outcome, duration_ms
FROM operations
WHERE parent_operation_id = 'aa9b8193-7286-4cab-97f8-68804d7bced4';
```

For normalization replay, call `_normalize_sport_result` with sport `nfl`, requested date `2099-09-20`, timezone `America/Chicago`, and `grouped_by_sport.nfl.matches` containing one synthetic fixture with `league=nfl`, `kickoff_utc=2099-09-20T18:00:00Z`, and `sources=[]`. Current code retains it. Set kickoff to null and `data_quality.status=ok`; current code returns zero matches, no error, and the unchanged `ok` quality. These are synthetic tests, not claims about a real 2099 schedule.

For timestamp replay, pass an event with `ts=2026-09-20T17:02:47+00:00` through `sanitize_diagnostics`; the serialized field remains `ts`. For date replay, compare the UI's ISO date expression with `Intl.DateTimeFormat('en-CA', {timeZone: 'America/Chicago'})` at `2026-09-21T00:30:00Z`.
