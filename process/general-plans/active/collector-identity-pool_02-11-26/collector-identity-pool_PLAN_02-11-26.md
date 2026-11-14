---
name: plan:collector-identity-pool-stage0
description: "Collector identity pool: Part A (Stage 0) per-account daily cap, sequential handoff, rest period, per-account status and coverage; Part B (Stage 1) fixed proxy, fixed user agent and browser-like connection style per account. No browser."
date: 02-11-26
feature: narrative-baskets
---

# Collector identity pool: Part A (Stage 0) calm and per-account, Part B (Stage 1) identity per account

Date: 02-11-26
Complexity: Simple (one execution stream, one worker)
Context router: process/context/all-context.md
Selected SPEC: collector-identity-pool_SPEC_02-11-26.md in this folder (draft PR #232, still in owner review; Q1-Q6 open). This plan builds Stages 0 and 1 of its Build Order, in two parts executed one after the other (Part B only after Part A is merged). Stages 2 to 4 are parked behind their triggers.

Status: Part A VALIDATED with corrections applied (Gate: PASS after the corrections below; Part B not yet validated). Nothing built. Big goal: daily data on every eligible coin; this plan builds the account pool and per-account identity that goal needs.

## Overview

The X pool already picks the least recently used account, keeps per-account state, waits out in-flight locks, marks suspended or logged-out accounts inactive and fails a unit over to another account. What it lacks, and what Stage 0 adds, is: (1) a daily read limit per account, so no account carries more than its share; (2) a rest period before a newly added account is used; (3) per-account figures in the status box (reads used against limit, cookie age, state); (4) a warning when the active accounts cannot finish the day's universe; (5) a daily coverage report (eligible, stored, exact, estimated, missing). Part A has no browser, no proxy and no new dependency. Part B (below) gives each account its own proxy, user agent and connection style, also without a browser. The global daily budget and every existing protection stay.

## Goals and Success Metrics

SPEC AC4, AC5 (sizing warning; adding an account is already a settings change), AC6, AC7, AC12, AC13, AC14 and AC18 for the X source. Success: an account at its cap is skipped with a reason; a lost account's coin-day is read by another account and counted once; a new account is unused until its rest has passed and the owner marks it ready; the status box and the sources data show per-account state; all existing X pool tests stay green.

## Acceptance Criteria

- Per-account cap: reads charged per account per UTC day, per page, as the library loaded them; at the cap the account is not selectable; when every active account is at its cap and none waits for an in-flight lock, X returns `budget_spent` and waits for the next UTC day exactly as a spent global budget does (no new pause reason).
- No coin-day is split across accounts; a unit that crosses an account's cap finishes on that account and the next selection skips it.
- Rest period (off by default, `x_account_rest_days` 0): when set above 0, a label added to an existing pool state starts resting, is unused until rest_days have passed and the owner runs the ready command, and is selectable from the next UTC day so it joins that day's canary; a first-ever state file and accounts already present are not affected.
- Loss: a locked, logged-out or suspended account's unfinished coin-day goes to another account and is counted once; the status shows the loss.
- Sizing: with the active accounts' caps and the eligible-coin count, the sources data reports whether the day can finish and the shortfall.
- Status: per account label, state, reason, reads today, cap, rest, ready, last used, cookie age, shown through the existing per-account health; reads today is unknown (not zero) until a real reset; a missing cap means no limit, not unknown.
- Coverage: yesterday's eligible (fetched plus missing), stored, exact (fetched minus capped), estimated (capped) and missing counts with reasons, from the existing completeness fields; missing never zero.
- All optional behaviour off: with no per-account cap set the collector behaves exactly as today.

## Phase Completion Rules

PLANNED means nothing built. CODE DONE is not VERIFIED. A phase is complete only with a payload-to-screen check, boundary and error cases, evidence that existing pool behaviour is unchanged, and owner confirmation. Missing browser evidence is a gap, not a pass. No live accounts, live cache or live collector are touched by tests.

## Execution Brief

1. Pool state and rules (backend): per-account daily counter and cap, rest state, skip-at-cap selection, all-at-cap wait. Test with fake clock and fake reader.
2. Accounting and failover wiring: charge reads to the account that spent them per page (units including curl pages, and canaries), never again from the unit outcome; retry a lost account's coin-day on another account once; the per-account reads of a restarted unit sum to the global used; keep the global budget as the ceiling.
3. Sizing and coverage: compute capacity versus need and the yesterday coverage report from files only.
4. Sources data and status box: per-account list, sizing warning and coverage lines; web formats only.
5. Owner command: a ready command for resting accounts; documented.

## Scope

In: X source only; the config keys, state, accounting, status object, status box and one owner command. Out of Part A: everything in Part B. Out of this plan: browser or cookie renewal (Stage 2), proxy gateway (Stage 3), Reddit browser method (Stage 4), any change to which coins are collected, scoring, or the Reddit collector.

## Assumptions and Constraints

- Per-account limit and rest are both OFF by default (limit none, rest 0 days), so today's behaviour is unchanged until the owner sets them (SPEC AC12). The owner chooses the limit from real signals (SPEC Q1).
- Accounts already in the state file keep working (migrated accounts are grandfathered). The rest rule applies only to a label added to an existing state file. Rollback note: older code rejects a state file that has the new account keys (exact-key check), so a revert must strip `reads_day`, `reads_used` and `rest_until`.
- The existing exact-key validation of the pool state file must accept new keys and still read older files (setdefault migration, like `rate_limit_seen`).
- Reads are counted as the library loaded them, as the global budget already does; the cap is our own safety limit, not X's.
- Test cache roots, ports and fixtures are isolated; the live API, site and collector are not started, stopped or read by tests. attention_queries.json is not edited (defaults live in code); the owner's local account edit in the main folder stays untouched.
- One heavy test or build at a time (8 GiB host).

## Functional Requirements

Config: two optional settings in the collector block, in a separate optional defaults map merged into the allowed keys and validated on their own (limit: none or an integer of at least 1; rest days: an integer of at least 0). They are NOT added to the required X defaults, so the committed queries file keeps loading. Pool state per account: `reads_day` (ISO date or null, checked separately, not a time key), `reads_used` (integer of at least 0), `rest_until` (a time key). Loading sets defaults for them (null, 0, null) before the exact-key check; a fresh account starts with `reads_used` 0; the counter resets only when today is after `reads_day`. The owner's ready mark is NOT in the pool file (the running collector would overwrite it): `--mark-ready LABEL` writes `account_ready.json` atomically in the accounts folder.

Selection: least recently used among accounts that are active, rested, ready (when rest applies) and under their cap. Cap and rest are worked out inside the account-state function and reported as `("locked", "account_cap")` and `("locked", "resting")`; the stored state set is unchanged. Reads are charged to the account per page where units and canaries already count reads, never again from the unit outcome; overshoot is at most one unit's pages.

All accounts at cap: where the code reaches the no-usable-account pause, an in-flight lock wait still wins; otherwise, if an active account is only at its cap, the source is marked spent and returns `budget_spent`. No new pause reason.

Sizing is computed by the X stream and written next to the existing schedule facts (the API reads files, it does not rebuild the queue): per-unit reads = pages needed for the sample size times the page size (worst case page cap times page size); capacity = the smaller of the global room and the sum of the remaining caps of selectable accounts; need = yesterday's queued coin-days times per-unit reads plus pending canary pages; the older backlog is reported separately. XPool receives the cap, rest days and ready marks at its three construction sites (collector stream, sources reader, reader status).

## Touchpoints

Existing: api/data/attention/x_pool.py (state, migration, selection, accounting), api/data/attention/web_queries.py (optional settings), api/data/attention/twscrape_reader.py (`--mark-ready` in the mutually exclusive group, ready file, pool construction), api/data/attention_pc_refresh.py (X stream: all-at-cap, sizing facts, pool construction), api/analytics/attention/sources.py and api/models/discovery.py (extend the existing per-account health: reads today, cap, rest until, ready; reuse completeness fields; collector sizing as optional trailing fields), web/lib/types/discovery.ts (optional fields only), web/lib/source-health.ts, web/components/narrative/CollectorStatus.tsx and DiscoverySourcesPanel.tsx, deploy/README.md.
New: api/tests/data/attention/test_x_pool.py (new file; pool tests currently live in test_x_reader.py); an optional pure helper api/data/attention/x_capacity.py (if added it must be listed in the X modules of tests/tooling_guards/test_pc_collector_guards.py and import neither twscrape nor curl_cffi).
Tests to extend: api/tests/data/attention/test_x_reader.py, test_twscrape_reader.py (the exact accounts dict at about line 816 and the pool-size checks), test_web_queries.py, test_x_window.py (it asserts the required keys are in the file), api/tests/data/test_attention_pc_refresh.py, test_attention_pc_refresh_collector.py, test_attention_pc_refresh_stream.py, api/tests/analytics/attention/test_sources.py and test_sources_health.py (old-format pool file fixture guards the migration), api/tests/routers/test_discovery.py (exact keys: new fields drop when null, so the set does not change), api/tests/tooling_guards/test_x_reader_guards.py and test_pc_collector_guards.py, web/lib/__tests__/source-health.test.ts, web/components/narrative/__tests__/CollectorStatus.test.tsx and DiscoverySourcesPanel.test.tsx.
Do not touch: PR-owned files of other sessions; discovery scoring; Reddit modules; .github; dependency files; api/data/attention_queries.json.

## Public Contracts

No second per-account list: the existing `sources[xsearch].health.accounts` entries gain optional `reads_today`, `cap`, `rest_until`, `ready` (declared on the model, otherwise they would be silently dropped; allowed state values unchanged). The collector object gains optional trailing sizing fields that drop when null. TypeScript fields are optional so existing fixtures still type-check. Pool state file: new keys with a backward-compatible load. New CLI flag in the existing reader module, label only, refuses unconfigured labels, never reads secrets. No new route, no new dependency.

## Blast Radius

X source only: pool state and selection, accounting, sources data, one UI component, tests. Risk class: data-collection correctness (RT3). A defect could stop X reading or double-count reads; mitigated by default-off behaviour, fake-clock tests and CI.

## Implementation Checklist

- [ ] Confirm origin/main state and open-PR ownership; isolated worktree; do not touch the main folder, the live site or the collector.
- [ ] Red tests first (committed failing): cap skip, all-at-cap wait, no-split, loss failover counted once, rest gate, state migration from the old file, status object states, sizing, coverage, unknown-never-ok.
- [ ] Extend pool state, validation and selection; keep old state files loading.
- [ ] Charge reads to the account that spent them; wire the cap into unit selection and the all-at-cap wait.
- [ ] Add capacity and coverage helpers and the collector object fields.
- [ ] Add the owner ready command and document it in deploy/README.md.
- [ ] Extend the status box (per-account lines, sizing warning, coverage); vitest cases for each state.
- [ ] Update exact-key contract tests deliberately; list every replaced test with its reason.
- [ ] Isolated smoke: fake reader, fake clock, temp cache; show cap skip, failover, rest gate, status object. One bounded browser check of the status box at 375, 768 and 1280 if memory allows; otherwise report not run.
- [ ] Targeted tests, then one consolidated run; draft PR; wait for CI on the final head; report. No merge, no deploy.

## Verification Evidence

| Gate / Scenario | Strategy | Proves SPEC criterion |
|---|---|---|
| Account at cap skipped; all-at-cap waits for next UTC day; global ceiling holds | Fully-Automated | AC4 |
| Coin-day never split; unit crossing the cap finishes on its account | Fully-Automated | AC4 |
| Lost, locked or suspended account: coin-day read by another account once | Fully-Automated | AC6 |
| Resting account unused until rest passed and ready marked; old state files and first-ever state unaffected | Fully-Automated | AC7 |
| Adding a label by settings; sizing warning names the shortfall | Fully-Automated | AC5 |
| Option off: collector behaves exactly as today; existing pool suites unchanged and green | Fully-Automated | AC12, AC18 |
| Status object and box: per-account states, unknown never ok or zero | Fully-Automated | AC13 |
| Coverage report: eligible, stored, exact, estimated, missing with reasons; missing never zero | Fully-Automated | AC14 |
| Seeded status box at 375, 768, 1280 | Fully-Automated (bounded, memory permitting) | AC13 |

Commands (VALIDATE binds exact paths): `UV_FROZEN=1 uv run --project api pytest <the files named under Touchpoints> -q`; then once at the end api/tests/data/attention, api/tests/analytics/attention, api/tests/data/test_attention_pc_refresh*.py, api/tests/tooling_guards; in web/ `pnpm exec vitest run components/narrative/__tests__/CollectorStatus.test.tsx`, `pnpm test`, `pnpm exec tsc --noEmit --incremental false`. Known Windows-host failures (about 40 router tests, test_universe_classes end-to-end, plot-ink.test.ts) are judged by Linux CI. Read process/context/tests/all-tests.md and operating-instructions.md before finalizing commands.

## Part B: Stage 1, identity per account (SPEC AC9–AC13, AC17–AC20)

**Status: B1 VALIDATED with corrections (02-11-26); B2 and B3 VALIDATE pending.** This revision supersedes the BLOCKED Part B of 02-11-26; it does not change Part A. Part A's text and PASS are historical, not evidence that B works. Part A must be merged before B; each part below is independently executable and reviewable against its stated dependency, with its own red tests and evidence. No B source changes or live probes are authorized by this docs revision. Obtain VALIDATE v2 and the owner's ENTER EXECUTE MODE for the selected part.

TL;DR: B1 establishes wire identity, B2 binds admitted private routes to accounts, B3 measures behaviour without changing data semantics. The library has account-level identity fields; the application wrapper must deliberately provision and reconcile them. It does not already accept a per-reader proxy and UA contract.

### Shared boundaries and decisions (02-11-26)

- Evasion/identity is in scope; no money; owner supplies a private proxy list outside the repo, one URL per line. Free public proxies are only a disposable-account experiment first. Never probe real accounts without the separately approved bounded comparison.
- Accounts share work evenly (least recently used), rest one week before ready eligibility, and retain the global ceiling. Build only what evidence requires. Each optional measure has an independent switch, health signal and removal decision after a recorded trial.
- Default remains plain until the real-account comparison establishes no extra challenges, then browser-like transport becomes the documented default. A process restart is required to change backend.
- No Reddit implementation, scoring, .github, dependency-file changes, local `api/data/attention_queries.json` edits or live collector restarts. New settings go into Part A's **optional defaults map**, never required `X_DEFAULTS`.
- Public status extends **`sources[xsearch].health.accounts[]`**, not a second collector list. Python and TypeScript fields are optional; absent measurements are unknown, never healthy/zero. Status reads files only.

### B1 — transport identity and feasibility gate

**Dependency / deliverable:** execute after Part A; B1 can ship with proxy routing disabled. Deliver a maintained application-owned adapter in `twscrape_reader.py`, not an untracked site-packages patch, plus offline wire proof and the separately approved comparison. B2 consumes this adapter.

#### Touchpoints

`api/data/attention/twscrape_reader.py` (adapter, provisioning, bootstrap cache, start order, fallback child and secret boundary), `api/data/attention/x_reader.py` (backend-aware guards and retry policy), `api/data/attention/web_queries.py` (optional mode/identity config), `api/data/attention_pc_refresh.py` (reader lifecycle); `deploy/start-collector.ps1`, `deploy/README.md`; tests `test_twscrape_reader.py`, `test_x_reader.py`, `test_web_queries.py` and the two tooling guards listed in the amendments checklist. Canonical collector SPEC amendments below are a B1 deliverable; do not edit its historical decisions away.

#### Public Contracts

- `x_connection_style`: enum `plain|curl`, default `plain` until the comparison decision; `x_identity_enabled`: bool false; `x_account_identities`: object default `{}`, keyed by configured label, each containing `accept_language`, owner-declared `region` and IANA `timezone`, plus the transport identity: for `plain` a nonempty literal `user_agent`; for `curl` an exact `impersonation_target` (browser family and version such as chrome131; never a moving alias) from the targets installed curl_cffi offers, with the wire user agent derived from it. Reject unknown labels, invalid values and duplicate effective identities when enabled. UA does not itself prove geography.
- Freeze backend selection once at collector startup, **before library load or any client construction**. Preserve `REQUIRED_ENV`, telemetry/log-level/no-account protections and global `PROXY_VARS` rejection. Never mutate `TWS_HTTP_BACKEND` per account. The launcher must pass only the validated selected mode instead of unconditionally clearing it; child setup uses the same validated contract.
- Existing `curl_status` verifies distribution name/version, wheel tag, platform and a recorded hash against lock/allowlist. It **does not hash installed binaries**. Refuse curl startup when this installed-distribution check fails; do not claim binary integrity.
- Installed HTTPX uses literal account UA, but curl strips it and chooses an impersonation UA. Bootstrap makes its own `@chrome` client; generator cache is process-wide and keyed only by username. Measured on 02-11-26 (loopback, installed twscrape and curl_cffi 0.16.3): the plain backend sent the supplied user agent; the curl backend ignored it and sent its profile's own (Chrome 150 on macOS) while keeping Accept-Language. Under curl the identity is therefore the per-account impersonation target, not a literal string; a literal user agent that contradicts the target's TLS profile would be a detectable mismatch and is not sent. The adapter must wrap both GraphQL and bootstrap client factories (the two imported factory references, installed lazily by the application wrapper; no library edit), apply the account's exact target to both, carry the account through async-context-local state (bootstrap receives no username; no mutable process-global current account) and scope or invalidate the generator cache by effective identity revision rather than username alone. Keep the pinned upstream compatibility assertions and fail startup if hooks/signatures no longer match. Do not assume storing a DB string proves a wire header.
- Feasibility gate precedes cutover: loopback capture of GraphQL **and** bootstrap, redirects and fallback, for two identities, both backends, restart and identity change. Verify actual outgoing UA/Accept-Language, proxy route when supplied, bootstrap isolation and TLS-profile/header compatibility. If the pinned backend cannot preserve this contract through a maintained wrapper, B1 is BLOCKED: return for a dependency/design decision, not a false AC19 pass.
- AC19 honestly proves a fixed **observed outgoing identity (literal UA for plain, impersonation target and derived UA for curl) and route** on the enumerated request paths, not complete browser fingerprint stability, global uniqueness on the internet, or ban avoidance. A region-neutral UA is acceptable; timezone is explicit identity metadata, not an invented HTTP header. Record which protocol fields exist, which are sent and which cannot be verified.
- Cookie refresh must reapply/reconcile identity after upstream clears headers; preserve cookies, active state, locks and counters. Never use upstream `@chrome` seeded selection as proof of a unique literal UA.
- Plain mode retains one qualifying curl fallback per UTC day pool-wide, with charged pages, canary and cursor continuation. Normal curl does **not** retry curl as a backend fallback. A fallback child reconstructs the same effective identity from label/DB and the private assignment resolver (B2), invalidates stale bootstrap cache, and refuses missing required routing. No credentials in argv or child environment.

#### Checklist and red tests

- [ ] Commit red tests for stripped literal UA, independent bootstrap `@chrome`, username-cache collision, refresh identity loss and pre-verification client creation.
- [ ] Implement maintained adapter and compatibility refusal; capture actual outgoing headers for both paths, both modes, restart and identity change. An unsupported override is a gate failure.
- [ ] Freeze/verify backend before construction, amend launcher and child reconstruction; test normal curl refusal and no curl-on-curl retry, plain pool-wide daily fallback and cursor/read accounting.
- [ ] Test independent identity switch and all-off baseline; record UA mismatch rate, bootstrap failures and challenge/canary outcomes as health signals.
- [ ] Deliver B1's dated canonical SPEC/guard/module-contract/deploy documentation amendments below.
- [ ] After offline proof, seek separate owner approval for a budgeted two-real-account, both-style comparison recording challenge counts, result counts, canary agreement and spent reads. Record ordering/time confounds; static review is not this evidence. If no extra challenges, record curl default under Q8; otherwise retain plain and report.

#### Verification Evidence

| Gate / Scenario | Strategy | Proves SPEC criterion |
|---|---|---|
| GraphQL/bootstrap wire UA, languages, isolated cache; restart/refresh; compatibility refusal | Fully-Automated | AC19, AC10, AC18 |
| Verified mode before every client; launcher; unverified curl refused; plain daily retry versus no curl-on-curl | Fully-Automated | AC20, AC18 |
| Fallback child same identity; no credential argv/env/output | Fully-Automated | AC19, AC17 |
| Identity and transport switches independently off/on; all-off baseline; health unknown until observed | Fully-Automated | AC12, AC13 |
| Two real accounts, two styles, counts/challenges/canaries; documented default decision | Agent-Probe (separate owner approval required) | AC11, AC20 |

**Risks / blast radius:** RT3 reader/bootstrap/launcher cutover; upstream private hooks can drift and curl headers can contradict TLS profile. Compatibility assertions and wire tests gate deployment; no claim that imitation prevents challenges. B1 cannot enable proxy-required operation before B2.

### B2 — fixed per-account proxy, admission and quarantine

**Dependency / deliverable:** B1 adapter merged and validated. B2 is independently executable with behaviour switches off. Deliver private assignment resolver, sequential admission boundary, safe lifecycle, migrated health and status.

#### Touchpoints

New pure `api/data/attention/x_proxy.py`; lazy network execution in `api/data/attention/twscrape_reader.py`; `api/data/attention/x_pool.py` (state and eligibility), `api/data/attention_pc_refresh.py` (`XStream` reader cache), `api/data/attention/web_queries.py`; `api/analytics/attention/sources.py`, `api/models/discovery.py`, `web/lib/types/discovery.ts`, `web/lib/source-health.ts`, `web/components/narrative/CollectorStatus.tsx`; `deploy/README.md`; `test_x_proxy.py` and the explicit amendment suite below. No network or X-library imports in pure `x_proxy.py`; add it to guard `X_MODULES`.

#### Public Contracts — files, configuration and secrets

- Optional keys: `x_proxy_required` bool false, `x_proxy_list_path` nonempty absolute string or null (default null), `x_proxy_assignments_path` same (default null), `x_proxy_admission_max_age_seconds` integer 1–86400 default 86400, `x_proxy_health_interval_seconds` positive integer default 900, `x_proxy_quarantine_seconds` positive integer default 3600. Reject empty strings, partial path pairs and unknown labels. Proxy-required mode needs an assignment for every enabled account and never goes direct. Direct mode is explicit (`required=false`, both paths null), reported as `direct`; a bad configured list is not direct mode.
- Owner-managed assignment JSON is separate from one-URL-per-line private list: `version:1`, `lines` map of opaque UUID to positive 1-based line number, and `accounts` map of configured label to `{proxy_id, expected_ip, region, timezone, accept_language}`. No URLs/credentials in assignment, pool state or public config. No duplicate IDs, line numbers, assignments or active expected exits. `expected_ip` is a validated IP, region/locale/timezone are explicit owner values, cross-checked with identity and admission observations.
- Opaque IDs are **not URL hashes or credential fragments**. Owner retains IDs and adjusts line numbers on reorder; removed IDs fail closed. Snapshot both files at a unit boundary; any file content/revision change invalidates admission and effective identity even if label/ID is unchanged. Never persist a credential-derived digest; use a collector-generated revision token. Missing/reordered-without-reconciled mapping is blocked by expected-exit verification, not silently accepted.
- Private files must be outside repo, owner readable only; enforce POSIX modes where supported and Windows owner-only ACL inspection. If ACLs cannot be verified, refuse proxy mode with an actionable nonsecret reason; do not claim POSIX modes prove Windows protection.
- Credentials exist only in short-lived private resolver/transport memory, **not upstream account DB proxy fields**, state, logs, status, exceptions/chains, reports, child env/argv or captured output. Child reloads private paths through trusted configuration using label/opaque ID, not a URL argument. Upstream logger filtering/redaction is installed before provisioning/client creation; disable unsafe upstream formatting and map network/parse errors to fixed reason codes before chaining or logging. Redact raw responses and captured child streams too. Test unique credential markers at warning/error and exception boundaries; do not merely rely on our `map_exception`.

#### Public Contracts — sequential bounded admission and lifecycle

1. Resolve and validate private assignment locally; reject empty/missing/invalid/quarantined candidates. One check and one proxy at a time, no parallel fan-out. Each network step has 5-second connect and 10-second total deadline, no implicit retry; admission attempt bounded to 60 seconds.
2. Through the assigned route, verify HTTPS using normal trusted roots, no `verify=false`, custom proxy CA or accepted interception; fixture tests cover bad certificates. This checks the configured trust policy, not proof of absence of every possible trusted-CA interception.
3. Exit echo over verified HTTPS must match expected IP and differ from all active account exits. Region uses configured expected region plus observed provider metadata; disagreement/unknown required region blocks. Language and timezone are owner-declared, validated against that region; report metadata provenance/time rather than asserting exact geolocation.
4. Check timestamped Spamhaus DROP and FireHOL cached inputs with source URL, fetch time and content digest. Refresh only over verified HTTPS with validated parsers; effective max age is the configured value capped at 24 hours. Future-dated, malformed, absent or stale required cache blocks admission. No stale-while-failing pass.
5. Optional free reputation provider is disabled by default; if configured, key remains private and check becomes required. Provider contract/threshold must be explicit before enablement (default reject any reported abuse/block flag); timeout, quota, unknown schema or unavailable provider blocks, never silently skips. No paid provider.
6. Compare a configured known plain-page fixture to a trusted versioned digest and expected content/redirect origin, rejecting injected or changed content. Baseline and echo endpoints, parsers, certificates and provider responses are fake-client injectable; no live calls in automated tests. Real accuracy/route behaviour needs the separate approved disposable probe.

Admission cache is keyed by opaque proxy ID and effective identity revision, stores only safe outcomes/timestamps/reason codes, and expires at the earliest required-input expiry or configured max age. Re-run on exit change, files/identity change, health failure or expiry. Health rechecks are bounded by the same scheduler and budgeted control counters; X blocks are account signals, not proof the proxy died.

Single collector-owned writer extends each pool account with `proxy_id` (string|null), `identity_revision` (opaque string|null), `proxy_health` (`unknown|healthy|quarantined` default unknown), `proxy_checked_at` and `proxy_quarantine_until` (UTC timestamp|null), `proxy_reason` (allowlisted code|null), `proxy_changed_at` (UTC timestamp|null). No expected IP/URL/credentials in pool state. `setdefault` migration occurs **before exact-key validation**; reject wrong types/unknown keys; retain Part A fields. Atomic writes; owner assignments never rewritten by collector snapshots. Rollback while collector stopped: back up state privately, strip exactly these seven B2 keys, preserve all Part A keys, restore old reader/config together. Test old/new/corrupt states and rollback round-trip; never restore secret URLs.

`XStream` cache key becomes label + effective identity revision + UA/backend/private-file revision, not label alone. Close/rebuild readers and bootstrap generators only at a unit boundary; invalidate and rerun the account canary before storing more data after identity change. Mid-unit route failure discards partial sample, charges spent reads, and restarts the whole coin-day on an eligible account; no cross-identity sample aggregation. Distinguish suspension/login from proxy failure.

On proxy failure quarantine until timestamp, alert with label/opaque ID/reason, and wake at the earliest health/quarantine/other eligibility deadline (not unconditionally midnight or `budget_spent`). Replacement must pass all checks, be unassigned and coherent. Atomic activation records opaque IP-change event/time, not IP/URL, before rebuild/canary. If none qualifies, pause only that account. Least-recently-used handoff and global/page accounting remain intact.

Status uses `sources[xsearch].health.accounts[]`: optional `proxy_id`, `proxy_state` (`direct|unknown|healthy|quarantined|blocked`), `proxy_reason`, `proxy_checked_at`, `proxy_quarantine_until`, `region`, `connection_style`, `identity_revision`; omit unavailable values, render unknown explicitly. API/status readers never trigger checks or write state.

#### Checklist and red tests

- [ ] Red tests: sticky distinct assignments, reorder/removal, empty URL, duplicate/missing/unknown labels, private ACL unavailable, identity mismatch and direct-mode distinction.
- [ ] Red fake-client admission tests: every ordered step, timeout/deadline, stale/future/malformed caches, provider unavailable, injected page, exit collision/change and region unknown.
- [ ] Loopback no-direct-leak tests for GraphQL, bootstrap, redirects and fallback child; unavailable proxy must produce no direct connection. Test upstream logs/chained exceptions/child output with secret markers.
- [ ] Implement pure resolver/state logic and lazy network reader boundary, optional config and exact-key migration/rollback. Preserve all pure-core, Reddit, telemetry and global-proxy guards.
- [ ] Implement cache-key recreation, unit-boundary failover/canary, quarantine/wake-up, safe status and frontend formatter. Assert spent reads stay charged, discarded samples never store and no candidate only pauses affected account.
- [ ] Deliver B2's canonical SPEC amendments, private-file/ACL setup and rollback instructions; status payload-to-screen fixtures at 375/768/1280.

#### Verification Evidence

| Gate / Scenario | Strategy | Proves SPEC criterion |
|---|---|---|
| Sequential bounded admission, certificates, exit uniqueness, injection, provider and cache policy | Fully-Automated | AC9, AC10 |
| Loopback GraphQL/bootstrap/redirect/child route; empty/missing/dead proxy never direct | Fully-Automated | AC9, AC19 |
| Sticky ID, reordering, quarantine/replacement/wake-up, no candidate and suspension distinction | Fully-Automated | AC9, AC6 |
| Reader recreated/canary rerun at identity change; discard/restart; charges sum globally | Fully-Automated | AC18, AC4, AC19 |
| Exact-key migration, rollback, assignment ownership and independent route switch/all-off | Fully-Automated | AC12, AC18 |
| Credentials absent DB/state/logs/exceptions/child env/argv/output; ACL refusal | Fully-Automated | AC17 |
| Optional Python/TS health payload through formatter and seeded UI widths | Fully-Automated | AC13 |
| Real route/provider quality and Windows private ACL behaviour | Hybrid (offline assertions plus separately approved host probe) | AC9, AC10, AC17 |

**Risks / blast radius:** RT3 routing/security, account state and status across Python/web. A no-direct test on one path is not proof for others. Public proxies may intercept, fail or be blocked; no production use before disposable-account evidence. Provider uncertainty fails closed and may reduce coverage; missing stays missing. Static ACL tests do not establish live Windows permissions.

### B3 — independently switchable behaviour measures

**Dependency / deliverable:** Part A plus B1/B2 contracts, and the stripped-page fix rebased/merged. Another session owns raw-page classification, strike, canary and failover paths in `api/data/attention/x_pool.py`; coordinate or rebase before touching them. B3 consumes its authoritative stripped-page strike signal, never reclassifies raw pages or turns legitimate sparse results into proxy rotation.

#### Touchpoints

`api/data/attention_pc_refresh.py` (`XStream`, `_next_due`, mixed-work scheduling), `api/data/attention/x_pool.py` (eligibility/effective caps), `api/data/attention/twscrape_reader.py` (approved ordinary calls), `api/data/attention/x_reader.py`, `api/data/attention/web_queries.py`; existing sources/models/web status fields and formatter; `deploy/README.md`; `test_x_pool.py`, `test_x_reader.py`, `test_twscrape_reader.py`, `test_web_queries.py`, all three `test_attention_pc_refresh*.py`, sources/router/UI tests and both tooling guards.

#### Public Contracts

All five optional bools default false: `x_quiet_hours_enabled`, `x_mixed_traffic_enabled`, `x_variation_enabled`, `x_adaptive_cooldown_enabled`, `x_warmup_enabled`. Configuration is in the optional map; unknown labels/types rejected. Identity/proxy/transport switches remain independent; disabling behaviour never disables safety, canary or global ceiling.

| Measure | Executable rule and bounded parameters | Health signal / off contract |
|---|---|---|
| Quiet hours | `x_account_quiet_hours` map default `{}`; each configured label has IANA timezone and distinct `HH:MM` start/end. Windows may cross midnight. `_next_due` returns first instant outside quiet hours combined with max of locks/rest/cooldown and caps/UTC rollover. DST folds/gaps use zone-aware next eligible instant. Never abandon pending UTC coin-days or bypass canary. | Quiet deferrals, next eligible time, completed coin-days and challenges per account; off ignores windows and keeps existing scheduling. |
| Mixed traffic | Only `user_by_login`, `tweet_details`, `user_tweets` via explicit wrapper allowlist and owner-configured public target IDs/logins (`x_mixed_targets`, default empty) are approved. No home timeline, login, account creation, writes or additional endpoints. At most one ordinary call per 20 completed coin units, at most 3 calls/account/UTC day, `user_tweets` one page/20 items. Reserve 20 read units per call, charge max(20, actual upstream page read units) to account AND global counters at page callback, never outcome again; refuse when room <20, suppress subsequent work if actual charge exhausts room. Charge even failures; no unbounded paging/retry. | Ordinary calls/charged units, challenge/canary rates and displaced coin coverage; never write coin values, completeness, history or author ledger. Off means zero ordinary calls. |
| Variation | Deterministically seeded per label/UTC day for reproducible tests: select only page sizes 10 or 20 within configured reader/page caps, pause multiplier 1.0–1.2 (never below base pacing), shuffle only equally due coins within the same target UTC day. Keep query filters and coin matching unchanged, account for actual pages and requested page units. | Page size/pause distribution, reads per completed unit and exact/estimated/missing ratio; off retains original size/order/pause. No query-token mutation. |
| Adaptive cooldown | Consume stripped-page fix's confirmed-strike signal/threshold without redefining it; challenge pauses account for owner intervention, no timed retry. Rate-limit remaining <=1 waits until reported reset (or 15 minutes when absent). Three consecutive non-canary units with raw result count <25% of that account's previous seven successful comparable units (minimum seven observations) trigger 1-hour account cooldown; reset shrink run on recovery. Confirmed stripped strike cooldown is 1 hour or the fix's longer lock. | Persist reason/deadline, confirmed strikes, shrink-run, last warning and handoffs; off adds no B3 cooldown but retains upstream locks, stripped-page safety and mandatory challenge pause. Never rotate proxy merely for shrink/strike. |
| Warm-up | After configured one-week rest **and ready eligibility** (next UTC canary day), effective account cap = min(configured cap, 100 for first 2 eligible UTC days, 200 for next 2, 400 for next 3, configured cap thereafter). No finite cap: ladder supplies finite caps then removes itself. Persist start UTC day only when eligible; downtime does not reset start. Keep Part A grandfathered labels out of ladder, global ceiling unchanged; do not reset progress on cookie/route refresh. | Stage/effective cap/reads and warnings per stage; off uses existing account cap/rest/ready rules. |

B3 pool additions: `warmup_start_day` (ISO date|null default null), `behaviour_cooldown_until` (UTC timestamp|null default null), `behaviour_reason` (allowlisted code|null default null), `shrink_run` (nonnegative int default 0), `result_history` (last seven `{day, count, query_class}` nonsecret records default `[]`). Defaults before exact-key checks; validate bounded length/counts. Single writer; rollback strips exactly these five keys while stopped, retaining A/B2 fields. Stripped-page counters remain owned by the fix, not duplicated. Ordinary-call counts use per-day accounting with optional `mixed_day` (ISO date|null) and `mixed_calls` (nonnegative int default 0); migrate and strip these two on rollback too.

#### Checklist and red tests

- [ ] Red tests for **each** switch independently on/off plus all-off against the Part A baseline; health never inferred from an unset switch.
- [ ] Quiet midnight/DST `_next_due`, lock/cap/rest/canary precedence, last-window loss and UTC backlog regression.
- [ ] Mixed precise allowlist, budget reservation/page charging/failure, hard three-call cap, no coin/history writes; retain forbidden API-method guards.
- [ ] Variation fake-seed bounds, pacing floor, UTC/filter/order preservation, actual read charges and exact/estimated regressions.
- [ ] Cooldown confirmed strike versus sparse/empty pages, shrink minimum history, challenge and rate-reset precedence, per-account handoff; no proxy rotation or raw-page reimplementation.
- [ ] Warm-up ready/rest/day boundaries, persistence/restart, grandfathering and finite/global ceilings; exact-key migration/rollback.
- [ ] Record independent health deltas versus all-off trial (counts, challenges, missing days, spent reads); remove measures without benefit rather than adding speculative ones. No claim of efficacy from unit tests alone.

#### Verification Evidence

| Gate / Scenario | Strategy | Proves SPEC criterion |
|---|---|---|
| Quiet switch, midnight/DST/next-due precedence and deferral health | Fully-Automated | AC12, AC18 |
| Mixed switch, exact allowlist, account/global charges and no data writes | Fully-Automated | AC12, AC4, AC18 |
| Variation switch, bounded size/pause/order, UTC/filter/labels preserved | Fully-Automated | AC12, AC18 |
| Adaptive switch, authoritative strikes, shrink/challenge/rate thresholds, handoff health | Fully-Automated | AC12, AC6, AC13, AC18 |
| Warm-up switch, post-ready eligibility ladder, persistence and ceilings | Fully-Automated | AC12, AC7, AC4 |
| Every independent switch plus all-off Part A baseline, migrations/rollback and safe health UI | Fully-Automated | AC12, AC13, AC18 |
| Recorded benefit/removal decision per measure against all-off baseline | Agent-Probe (separate bounded owner-approved trial) | AC12 |

**Risks / blast radius:** RT3 scheduler/accounting/state correctness; ordinary traffic spends coverage capacity, variation can change sampling, quiet hours can miss deadlines and warning heuristics can penalize sparse coins. Bounded calls, strict UTC regressions and measured independent trials are gates. Do not amend stripped-page semantics in this work.

#### B1 VALIDATE (02-11-26): Gate PASS with these corrections applied

A read-only reviewer plus a measured loopback check ran against current code. Corrections applied above: AC19 and the identity setting now state that curl identity is an exact impersonation target; the adapter seam is two lazily installed factory references with async-context account state; the earlier BLOCKED items (UA claim, wrong status path, startup order) are resolved in this text. Instructions for EXECUTE:

- V1: before choosing targets, measure offline which user agent, client hints, Accept-Language and header order each candidate target (for example chrome131, safari170, firefox133, edge101) really sends on loopback; do not assume. Pass an exact version target; aliases move with upgrades.
- V2: Accept-Language is kept by the curl backend; the library hard-codes `x-twitter-client-language: en` separately (`account.py` 73-77): test the sent headers and do not claim timezone coherence in B1 (timezone is metadata; coherence with a route belongs to B2).
- V3: startup order: validate platform, distribution, wheel tag, lock/hash and install record BEFORE the library loads and before `lib.API(...)` (`twscrape_reader.py` 527-540, 712-744); the backend variable is read on every client creation (`http.py` 241-276), so the wrapper binds the selected backend and rejects unverified curl on every creation path; the fallback child verifies its own identity (836-852).
- V4: TLS fingerprint: an HTTP echo proves headers only. A local raw TCP listener can capture a ClientHello for an offline JA3-style parser; if that parser is not built, record TLS verification as unperformed, not passed.
- V5: tests to replace deliberately, with the reason each time (not blind deletion): test_twscrape_reader.py about 268-285, 304-333, 561-606; test_x_reader.py about 178-235, 251-285, 678-696, 839-868, 955 on; tooling_guards/test_x_reader_guards.py about 156-176, 204-210; test_pc_collector_guards.py about 26-28, 122-134 (only where B1 conflicts; keep the pure-core and no-network guards at about 201-233).
- V6: commands (not run): `UV_FROZEN=1 uv run --project api pytest api/tests/data/attention/test_twscrape_reader.py api/tests/data/attention/test_x_reader.py api/tests/tooling_guards/test_x_reader_guards.py api/tests/tooling_guards/test_pc_collector_guards.py -q`, add any new offline transport test file explicitly, then `UV_FROZEN=1 uv run --project api pytest api/tests/data/attention api/tests/tooling_guards -q`.
- V7: the owner-approved live comparison needs its own approval and a predefined protocol: matched queries and windows, order, per-account and global read ceilings, stopping rules on challenge or rate limit, setup and bootstrap requests counted against the budget, both styles on each of two accounts with other identity settings unchanged; record timestamp, commit, package and target, anonymized account, style, query and window id, order, budget before and after, attempted and completed reads, challenges and errors, result counts and canary agreement; no cookies, proxy credentials or raw responses; a tiny sample proves little, and an inconclusive result is recorded as such.
- V8: stripped-page overlap: the strike and cool-down paths in `x_pool.py` are merged (PR #236); B1 does not touch them.

#### Camoufox feature review (03-11-26, docs only; source https://camoufox.com/features/; nothing built)

Our collector is HTTP-only (twscrape), so browser-surface spoofing (canvas, fonts, WebGL, audio, `navigator.webdriver`, WebRTC, cursor) is Part C only. Lessons adopted for the HTTP mission:
- Coherence beats variety: every identity field must agree (UA, hints and platform come from one exact target; language, region and timezone from one declared region). B1 enforces UA/language/region; follow-up B1.1: cross-check target platform against declared timezone/region plausibility and reject contradictions.
- Language from the target region's speaker distribution, not a copied default: an owner config choice when each account's `accept_language` is set (B1 needs no code).
- Region-derived defaults and exit-versus-declared checks belong to B2 admission (AC10).
- B1.2: verify TLS/HTTP-2 fingerprints with a small reviewed local ClientHello/JA3 capture; until then TLS stays recorded as NOT verified.
- Part C gate: any browser must be proven on the wire to send nothing outside its assigned route (WebRTC, DNS prefetch, addons), with a loopback proof like B1's.
- Humanised behaviour maps to B3 pacing/order variation, switchable and measured.

#### Authorized B1 follow-ups implemented 03-11-26 (supersedes the ambiguous platform/geography wording above)

- B1.1 uses the existing `x_identity_enabled` switch (still false); no additional runtime networking or switch. OS does **not** determine timezone or country. Reject only explicit contradictions: declared uppercase alpha-2 region versus a known tzdb country-table entry; primary language tag's explicit alpha-2 region versus declaration; recognizable literal UA platform versus the four B1 wire-observed targets (chrome131/safari170/firefox133 macOS, edge101 Windows) or explicit `_android`/`_ios` suffixes. Platform-neutral UA and unmeasured target platforms remain unknown, not rejected.
- Use the union of local IANA `zone.tab` and `zone1970.tab` country memberships, including shared zones (Europe/Zurich includes CH, DE, LI). System `TZPATH` tables take precedence per table, otherwise installed `tzdata` resources; enabled validation refuses when no country tables exist. No added dependency. Valid aliases or neutral zones absent from the tables remain unknown. No unique timezone-to-country claim, offset heuristic, speaker-distribution rule, IP geolocation, DST scheduling or route admission. A regional primary language is an explicit configured identity claim; secondary preferences and regionless primary languages do not assert residence.
- B1.2 test-only tooling in `api/tests/data/attention/test_identity_fingerprint.py` captures bounded raw ClientHello records on TCP loopback and HTTP/2 initial SETTINGS over a separately negotiated loopback TLS connection with a temporary trusted certificate. Four exact B1 targets observed. Certificate/key are temporary and removed; no secrets/accounts/proxy/external endpoint. Parsers cover length bounds, fragmentation, GREASE filtering, extension order and ordered SETTINGS.
- Evidence: `collector-identity-pool_WIRE-B1-FOLLOWUPS_03-11-26.json`; mechanism verdict: `collector-identity-pool_FEASIBILITY_03-11-26.md`; execution/CI: `collector-identity-pool_REPORT-B1-FOLLOWUPS_03-11-26.md` in this folder. Observed bytes/settings are **not** published browser baseline data: no reference browser captured, JA4 computed, matching guarantee, cross-host stability or live acceptance established. B1's historical NOT-PERFORMED remains accurate for its execution; this adds only the bounded new evidence.


### Deliberate test and documentation amendments (B1/B2/B3)

These are required replacements/extensions with reasons, not blanket deletion of guards. Line numbers refer to the validation snapshot; rebase to current definitions before execution.

- [ ] B1/B2: `api/tests/data/attention/test_twscrape_reader.py:268-285,304-333,559-613,628-712,779-845`: preserve global proxy rejection; replace old per-account proxy/UA refusal with narrow identity acceptance; child identity/mode, verified normal curl, refresh and status.
- [ ] B1/B2: `api/tests/data/attention/test_x_reader.py:231-248,677-697,838-889,954+`: explicit environment matrix, backend-aware fallback and pool-wide plain daily limit.
- [ ] B1/B2/B3: `api/tests/tooling_guards/test_x_reader_guards.py:105-110,162-179,217-223` and `31-33,165-178`: permit only approved API args/methods and lazy adapter boundary; replace curl-only-child assumption; retain pins/dependency/debug/login/account creation/lock-reset/telemetry bans.
- [ ] B2/B3: `api/tests/tooling_guards/test_pc_collector_guards.py:21-28,56-75,122-134,173-187,199-248`: add pure `x_proxy.py` to `X_MODULES`; narrow evasion/fixed-hour exceptions only for approved identity and scheduler paths; retain pure-network and Reddit protections.
- [ ] B2: add `api/tests/data/attention/test_x_proxy.py` for admission, secrets, list/assignment, bounded fake clients and rollback; extend `test_x_pool.py`, `test_web_queries.py` and the three `api/tests/data/test_attention_pc_refresh*.py` files for identity-aware lifecycle, wake-up and accounting.
- [ ] B2/B3: extend `api/tests/analytics/attention/test_sources.py`, `test_sources_health.py`, `api/tests/routers/test_discovery.py`, `web/lib/__tests__/source-health.test.ts`, `web/components/narrative/__tests__/CollectorStatus.test.tsx` for optional safe health and unknown states.
- [ ] B1/B2 deliver the **canonical collector SPEC** amendments, dated **02-11-26 superseding decision**, to rules **5, 8, 17–20**, **AC41, AC46, AC53, AC55**, proxy/evasion non-goals and **Q24/Q30**. Locate exact canonical text during execution and preserve it as history, not a silent rewrite. Superseding text: “Owner permits measured per-account fixed private proxies, literal wire-verified UA and process-lifetime verified browser-like transport; global proxy environment remains forbidden. Pure cores remain network-free; lazy network and the maintained identity adapter are limited to the reader boundary. Plain mode retains bounded child curl fallback; verified normal curl is allowed with no curl-on-curl fallback. Unverified curl refuses startup. Proxy-required accounts never go direct; all traffic, bootstrap and children reconstruct the same admitted identity. Behaviour exceptions are only the B3 allowlist and scheduler measures, independently switchable and measured; no login/account creation, debug, telemetry, budget or completeness exemptions.” B1 owns transport/purity wording; B2 owns admission/secrets/state/status; B3 supplies only its enumerated scheduler/ordinary-call exceptions. Canonical AC numbers are separate from this SPEC's AC1–AC20.
- [ ] Update reader/pool module contracts, `deploy/README.md`, `deploy/start-collector.ps1` instructions and stale Part A/B handoff; document private files, cache/provider policy, ACL refusal, restart, rollback and real-probe approval.

### Part B execution verification commands (planned, not run)

In PowerShell set `$env:UV_FROZEN = "1"`. After red-to-green work, run `uv run --project api --frozen pytest api/tests/data/attention/test_twscrape_reader.py api/tests/data/attention/test_x_reader.py api/tests/data/attention/test_x_proxy.py api/tests/data/attention/test_x_pool.py api/tests/data/attention/test_web_queries.py api/tests/data/test_attention_pc_refresh.py api/tests/data/test_attention_pc_refresh_collector.py api/tests/data/test_attention_pc_refresh_stream.py api/tests/tooling_guards/test_x_reader_guards.py api/tests/tooling_guards/test_pc_collector_guards.py api/tests/analytics/attention/test_sources.py api/tests/analytics/attention/test_sources_health.py api/tests/routers/test_discovery.py -q`, then one consolidated `uv run --project api --frozen pytest api/ -q`. For B1 omit not-yet-created B2 tests, documenting the boundary. In `web/`, `pnpm exec vitest run lib/__tests__/source-health.test.ts components/narrative/__tests__/CollectorStatus.test.tsx`, then `pnpm test`, `pnpm exec tsc --noEmit --incremental false`, `pnpm build:islands`.

Use isolated fixture/cache/ports and seeded UI at explicit 375/768/1280 viewports; `D18_E2E=1` changes the backend harness, not just memory. Reported historical host failures (about 40 Windows router failures, `test_universe_classes` end-to-end, `plot-ink.test.ts`) are **not independently verified here**. Do not rerun merely to confirm them or automatically blame new failures on them. Final-head Linux CI proves its supported gates, not Windows ACLs, live proxies or browser acceptance.

## Part C: research addendum, not an execution plan (02-11-26)

**Status: RESEARCH; no Part C PLAN or execution authorized.** Source: `agent://RedditBrowserResearch` (full read-only report, no live Reddit/proxy/cache requests). Identity route/no official API application is decided. Preferred architecture is **shared per-subreddit chronological post and comment collection once for all 66 coins**, followed by existing local matching/deduplication/author-cap rules. Search is a separately labelled fallback/cross-check, not silent supplementation.

### Findings and honest promise

“Complete daily data for 66 coins” means all 66 receive a justified value from **one explicitly defined, successfully traversed visible surface**, scoped to the chosen 12 subreddits and UTC day. It does not mean every mention, private/deleted/invisible content, complete search-index recall or uninterrupted availability. Missing prerequisites or blocked/capped traversal leave coin-days missing/partial, never fabricated zeros.

- Current `www` uses Shreddit custom elements/lazy fragments; feed/search selectors differ. Reports conflict on logged-out access. [Search-fragment implementation](https://github.com/mvanhorn/last30days-skill/blob/main/skills/last30days/scripts/lib/reddit_search.py) and [selector reference](https://github.com/six-ddc/browser-cli/blob/main/skills/browser-cli/references/sites/reddit.com.md) are mutable implementation reports, not Reddit availability guarantees; search implementation omits author/body and is insufficient for our rules.
- [June comment-fragment report](https://github.com/zoharbabin/web-researcher-mcp/issues/283) is superseded in relevance by [Redlib October 2026 failures](https://github.com/redlib-org/redlib/issues/591): listings and thread JSON can behave differently; HTTP 200 can be an empty shell. Mobile `gql-fed` evidence does not establish web GraphQL. Old Reddit is not a dependable logged-out fallback.
- [MediaNama, 01-10-26](https://www.medianama.com/2026/10/223-reddit-rss-feeds-public-api-bots/) and [TechRepublic, 02-10-26](https://www.techrepublic.com/article/news-reddit-rss-public-api-shutdown/) report RSS ending **13-11-26**. This is press evidence; direct Reddit announcement was not read. The [primary registration page](https://developers.reddit.com/app-registration) says removal for unregistered/unengaged apps starts **12 January 2027**, and remaining public API access ends **March 2027**, with no March day specified. These are distinct deadlines/source qualities.
- Post search `t=day` is rolling 24 hours, not yesterday UTC; filters/sort/scope must be observed, not inferred from URL. Comment search and within-thread search do not establish a complete chronological comment lane. Only opening new posts misses comments on old posts.
- [PRAW listing docs](https://praw.readthedocs.io/en/stable/code_overview/other/listinggenerator.html) warn most listings cap at 1,000 items; this is a risk bound, not a proven browser cap. Short DOM/no cursor/stopped spinner is not exhaustion. Traversal must reach day start or prove genuine exhaustion without a cap/login gate/lazy-load failure. Record cursor chains, raw timestamps/spans and stop reason; never bridge unseen intervals.
- Require stable `t3_/t1_` IDs, absolute UTC timestamps, full text (not previews), subreddit/author identity and canonical permalink; deleted/missing author is not a normal username and unknown deletion state stays unknown. Reject missing mandatory fields; DOM virtualization must not discard unrecorded cards.
- Use a separate method/completeness evaluator and method-window separation, first-write-wins and global ceilings. Do not inherit Atom/feed short-page or density-estimator assumptions. Current feed zero code requires canary plus trailing median <5; owner **option B** instead says canary passed + clearly complete short feed + some coin history. This is a decision awaiting its separate code amendment, not implemented behaviour, and not automatically a valid browser zero rule.
- Search cost: combined scope `66*K*P+H+A` loads; separate 12-subreddit searches `792*K*P+H+A` (kinds K, pages P, details H, controls A). Shared chronological cost `sum(polls,subreddits)(Pposts+Pcomments)+H+A`, independent of coin count: 12 polls ×12 subreddits ×2 one-page kinds =288 logical loads. Actual outbound requests include assets/fragments/telemetry and must be measured separately. Existing 250/150 feed budgets cannot be copied.
- Camoufox report found about 632 MB idle, 0.69–0.92 GB peaks, 13.4–33.3 second typical launches (43.2 first), changing canvas despite pinned config, a duplicate-profile launch hung 180 seconds, and uncaptured Mozilla/Fastly background traffic. One browser globally, profile lock **before launch**, memory floor, bounded lifecycle and network isolation remain evidence requirements, not solved properties.
- Old HTML/curl or Shreddit HTTP fragments may reduce cost but cannot solve login/access policy. Arctic Shift is a possible historical cross-check with no uptime guarantee; PullPush freshness, current availability and terms remain unverified. Neither proves complete live daily coverage; no archive adoption/terms acceptance here.

### Evidence required before a Part C PLAN

| Research gate | Required evidence / failure outcome |
|---|---|
| Availability matrix | Logged-out and (if separately approved) authenticated posts/comments/search for every subreddit, profile and route; record block/login/empty-shell outcomes, not HTTP status alone. |
| Fields | Stable IDs, full text, absolute timestamps, authors/deletion state and deduplication fixtures separately for feed/search/thread; missing mandatory fields fail closed. |
| Day traversal | Observe chronological sort and cursor pagination through UTC day start; distinguish exhaustion, server cap, DOM loss and lazy-load failure; retain chain/stop evidence. |
| Comments on old posts | Demonstrate chronological comment lane includes day-D comments on earlier posts, or explicitly narrow metric with owner approval. |
| Canary per lane | Posts success cannot certify comments/search. Define each canary's expected evidence, freshness, failure and zero gate. |
| Cost | Measure logical loads, actual request fan-out, expansion calls, pacing, daily ceiling and browser-time/launch/memory costs. |
| Profile isolation | Exclusive prelaunch locks, persistent identity/cookie separation, route verification, background connection containment, bounded close/recovery. |

Open decisions: posts-only versus posts+comments; chronological-visible metric versus search-index metric; authenticated fallback versus logged-out-only; per-subreddit versus verified combined scope; request/page/time ceilings and day-close delay; deleted/missing-author treatment; browser-specific zero evidence and estimator (if any); archives only as cross-check and unresolved terms. Do not silently resolve these with a narrower implementation.

Owner decisions carried forward: evasion/identity route; no official Reddit API application; no money; owner private one-proxy-per-line file with separate assignments; free public proxies disposable experiment first; browser-like style comparison on real accounts then default if no extra challenges; switchable/measured behaviour; zero option B; even per-account load; one-week rest; build only what evidence needs. Part C consumes identity lifecycle after Part B, but is not a requirement to build speculative X cookie renewal.

## Risks and Mitigations

A counter bug stops X early: default off, fake-clock tests. State file break: backward-compatible load and an old-file fixture. A resting account strands the pool: sizing warning and the grandfather rule for existing accounts. Status box overflow at 375 px: wrap and a width check. The owner's local config edit interferes with tests in a shared folder: tests use isolated config and never read the main folder.

Added by VALIDATE: an account marked ready mid-day would read values that all become missing (not canaried that day) while using its cap, so it is selectable only from the next UTC day. A resting account is not usable, so with two accounts the canary runs on one account without a comparison. Caps can end the day's spreading early because spreading uses the global budget: not a correctness bug. The older backlog can starve when capacity is below the coin count; sizing reports target day and backlog separately.

## Test Infra Improvement Notes

Known Windows-host failures (about 40 router tests, test_universe_classes end-to-end, plot-ink.test.ts) are unverified in the test context file: re-check on the host before blaming Part A. The bounded browser check needs explicit 375, 768 and 1280 viewports (the Playwright config only has the desktop project), the isolated cache root and ports of the existing config, worker flags off, and `D18_E2E=1` for a constrained host.

## Validate Contract

Gate: PASS for Part A after the corrections above. Two independent read-only reviewers (pool and accounting; status, UI and tests) ran on 02-11-26 against main at f5194a5c. As first written the plan was BLOCKED (required config keys would break the committed queries file; exact-key state validation and a state value outside the allowed set would break loading and the sources data; the owner's ready mark in the pool file would be overwritten by the running collector). All twelve proposed corrections and the scout's ten were applied above. Remaining instructions for EXECUTE:

- E1: re-check overlap on the shared files (discovery model, sources, web types, CollectorStatus) with `git diff --name-only origin/main...origin/<branch>` for every open branch at the start; the provider-fallback session's unpushed work is unknown, so keep Part A additions optional and trailing, and land Part A first.
- E2: red tests for: old state file without the new keys loads; a label added to an existing file rests (when rest days above 0) and a first-ever file does not; a restarted unit's reads split across both accounts and sum to the global used; all-at-cap gives `budget_spent` with no no-usable-account pause; a ready mark survives a running pass; an account marked ready joins the next UTC day's canary.
- E3: commands: `UV_FROZEN=1 uv run --project api pytest` on the touched files, then the focused directories, then `api/` once; in web/ `pnpm exec vitest run` on the touched files, `pnpm test`, `pnpm exec tsc --noEmit --incremental false`. CI is the judge for known host failures.
- Part B: **PLANNED, VALIDATE v2 pending** after the BLOCKED review. The B1 wire feasibility gate and B2 fail-closed admission contracts must pass before their respective cutovers. No implementation verification was performed by this docs revision.

## Resume and Execution Handoff

1. Selected plan: process/general-plans/active/collector-identity-pool_02-11-26/collector-identity-pool_PLAN_02-11-26.md; Part B v2 docs branch `claude/part-b-plan-v2`, based on merged main `ad1e0de8`.
2. Last completed phase: Part B PLAN corrected after BLOCKED validation; Part C research addendum only. Part A text above is preserved; inspect current merged Part A rather than re-executing its historical checklist.
3. Validate-contract status: Part A historical PASS unchanged; Part B **PLANNED, VALIDATE v2 pending**. Plan-artifact lint is not VALIDATE v2.
4. Supporting context: this SPEC; full `agent://PartBValidate` and `agent://RedditBrowserResearch` reports read for this revision. Source paths in their evidence are reviewer observations, not new runtime proof here.
5. Next step: VALIDATE v2 on B1/B2/B3, then explicit owner EXECUTE approval for B1. Rebase/coordinate with stripped-page owner before pool changes; independently record each part's red-to-green, state/error/UI evidence and remaining live gates. No Part C execution until its research gates and decisions produce an approved PLAN.

## Cursor and RIPER-5 Guidance

One plan only. VALIDATE before EXECUTE. Source changes need explicit approval. Do not build Stage 2 or later without their triggers in the SPEC Build Order being observed. Part B starts only after Part A is merged and the owner approves it.
