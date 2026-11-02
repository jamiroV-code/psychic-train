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

Status: PLANNED; VALIDATE pending. Nothing built. Big goal: daily data on every eligible coin; this plan builds the account pool and per-account identity that goal needs.

## Overview

The X pool already picks the least recently used account, keeps per-account state, waits out in-flight locks, marks suspended or logged-out accounts inactive and fails a unit over to another account. What it lacks, and what Stage 0 adds, is: (1) a daily read limit per account, so no account carries more than its share; (2) a rest period before a newly added account is used; (3) per-account figures in the status box (reads used against limit, cookie age, state); (4) a warning when the active accounts cannot finish the day's universe; (5) a daily coverage report (eligible, stored, exact, estimated, missing). Part A has no browser, no proxy and no new dependency. Part B (below) gives each account its own proxy, user agent and connection style, also without a browser. The global daily budget and every existing protection stay.

## Goals and Success Metrics

SPEC AC4, AC5 (sizing warning; adding an account is already a settings change), AC6, AC7, AC12, AC13, AC14 and AC18 for the X source. Success: an account at its cap is skipped with a reason; a lost account's coin-day is read by another account and counted once; a new account is unused until its rest has passed and the owner marks it ready; the status box and the sources data show per-account state; all existing X pool tests stay green.

## Acceptance Criteria

- Per-account cap: reads charged per account per UTC day; at the cap the account is not selectable; when all active accounts are at their cap X waits for the next UTC day exactly as a spent global budget does.
- No coin-day is split across accounts; a unit that crosses an account's cap finishes on that account and the next selection skips it.
- Rest period: an account added to an existing pool state starts resting, is unused until rest_days have passed and the owner runs the ready command; a first-ever state file, and accounts already present, are not affected.
- Loss: a locked, logged-out or suspended account's unfinished coin-day goes to another account and is counted once; the status shows the loss.
- Sizing: with the active accounts' caps and the eligible-coin count, the sources data reports whether the day can finish and the shortfall.
- Status: per account label, state, reason, reads today, cap, last used, cookie age; unknown values read unknown, never healthy or zero.
- Coverage: yesterday's eligible, stored, exact, estimated and missing counts with reasons; missing never zero.
- All optional behaviour off: with no per-account cap set the collector behaves exactly as today.

## Phase Completion Rules

PLANNED means nothing built. CODE DONE is not VERIFIED. A phase is complete only with a payload-to-screen check, boundary and error cases, evidence that existing pool behaviour is unchanged, and owner confirmation. Missing browser evidence is a gap, not a pass. No live accounts, live cache or live collector are touched by tests.

## Execution Brief

1. Pool state and rules (backend): per-account daily counter and cap, rest state, skip-at-cap selection, all-at-cap wait. Test with fake clock and fake reader.
2. Accounting and failover wiring: charge reads to the account that spent them; retry a lost account's coin-day on another account once; keep the global budget as the ceiling.
3. Sizing and coverage: compute capacity versus need and the yesterday coverage report from files only.
4. Sources data and status box: per-account list, sizing warning and coverage lines; web formats only.
5. Owner command: a ready command for resting accounts; documented.

## Scope

In: X source only; the config keys, state, accounting, status object, status box and one owner command. Out of Part A: everything in Part B. Out of this plan: browser or cookie renewal (Stage 2), proxy gateway (Stage 3), Reddit browser method (Stage 4), any change to which coins are collected, scoring, or the Reddit collector.

## Assumptions and Constraints

- Per-account limit default is OFF (no limit), so today's behaviour is unchanged until the owner sets it. The owner chooses the value after the lifecycle test and real signals (SPEC Q1).
- Accounts already in the state file keep working. The rest rule applies only to a label added to an existing state file.
- The existing exact-key validation of the pool state file must accept new keys and still read older files (setdefault migration, like `rate_limit_seen`).
- Reads are counted as the library loaded them, as the global budget already does; the cap is our own safety limit, not X's.
- Test cache roots, ports and fixtures are isolated; the live API, site and collector are not started, stopped or read by tests. attention_queries.json is not edited (defaults live in code); the owner's local account edit in the main folder stays untouched.
- One heavy test or build at a time (8 GiB host).

## Functional Requirements

Config (collector block, defaults in code): `x_account_daily_reads` (integer or off), `x_account_rest_days` (default 7). State per account: `reads_day`, `reads_used`, `rest_until`, `ready` (owner-marked). Selection: least recently used among active, rested, under-cap accounts; reason codes `account_cap` and `resting`. A shared helper computes capacity: sum of remaining caps of active accounts against need = remaining eligible coin-days x sample size + canary reads. The sources data gains `collector.x_accounts` (list) and `collector.x_coverage` and `collector.x_sizing`. Owner command: `python -m api.data.attention.twscrape_reader --mark-ready <label>`.

## Touchpoints

Existing: api/data/attention/x_pool.py (state, select, accounting), api/data/attention/web_queries.py (config keys, validation), api/data/attention/twscrape_reader.py (ready command, cookie age reuse), api/data/attention_pc_refresh.py (XStream: all-at-cap wait, sizing inputs), api/analytics/attention/sources.py and api/models/discovery.py (collector object), web/lib/types/discovery.ts, web/components/narrative/CollectorStatus.tsx.
New: none required beyond tests; a small pure helper for capacity/coverage may live in x_pool.py or a new api/data/attention/x_capacity.py.
Tests: api/tests/data/attention/test_x_pool.py (and sibling pool tests), api/tests/data/attention/test_web_queries.py, api/tests/data/test_attention_pc_refresh*.py, api/tests/analytics/attention/test_sources.py, api/tests/routers/test_discovery.py (exact keys, deliberately), web/components/narrative/__tests__/CollectorStatus.test.tsx.
Do not touch: PR-owned files of other sessions; discovery scoring; Reddit modules; .github; dependency files.

## Public Contracts

`GET /api/narrative/sources` collector object gains optional `x_accounts`, `x_coverage`, `x_sizing`; all nullable, absent for older payloads; the web tolerates absence. Pool state file gains keys with a backward-compatible load. New config keys are optional with safe defaults; unknown-key validation in web_queries must accept them. New CLI flag on the existing reader module. No new route, no new dependency.

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

## Part B: Stage 1, identity per account (SPEC AC9, AC10, AC11, AC19, AC20)

Starts only after Part A is merged; its own VALIDATE and the owner's ENTER EXECUTE MODE are required. No browser is used: each account's reader already accepts its own proxy and user agent, and the library has a browser-imitating backend.

**What it builds**
1. Proxy list and assignment: a private file outside the repository (one line per proxy, no credentials in the repository; Q7) and a settings map from account label to proxy. Each account keeps its proxy; the reader of that account is created with it. Home connection when none is set, and the status box says so.
2. Proxy health: a periodic check per proxy (alive, speed, answered by X's own page without a block); a failing proxy is quarantined with a cooldown; the account moves to the next healthy proxy in the list; an alert is raised; never a silent fallback to the home connection (the account pauses unless the owner allows it).
3. Pinned user agent per account: stored next to the account state, set on the account in its database and kept across restarts; the browser family it names selects the connection style.
4. Coherence check: the account's language and time-zone headers and user agent must agree with the proxy's region; a mismatch blocks that account's start with a reason code.
5. Connection style: a collector-wide setting for the browser-imitating backend, off by default; on only after the install record, wheel tag and hash of the imitation library are verified (the existing verification code is reused); the plain style stays available. A recorded comparison on the two real accounts (challenge, result count, canary agreement) decides the default (Q6, Q8).
6. Rule amendments: the environment guard allows per-account proxy settings but still refuses a global proxy variable; rule 19's fallback-only wording is amended; the SPEC and PLAN record the owner's decision.
7. Status box: per account proxy state (healthy, quarantined, none), region, and connection style.

**Touchpoints:** api/data/attention/twscrape_reader.py (per-account construction, environment guard, style switch), api/data/attention/x_reader.py (env problems), api/data/attention/web_queries.py (settings: proxy map, proxy file path, style flag), api/data/attention/x_pool.py (proxy state per account), a new small api/data/attention/x_proxy.py (list loading, health, quarantine, region check), api/analytics/attention/sources.py and api/models/discovery.py (fields), web/lib/types/discovery.ts and CollectorStatus.tsx, deploy/README.md (owner steps), the existing guards in api/tests/tooling_guards (deliberate amendment), tests under api/tests/data/attention. Not touched: Reddit, scoring, .github, dependency files (the imitation library is already in the locked optional group), the owner's local config.

**Public contracts:** new optional settings and state keys with backward-compatible loading; `collector.x_accounts[]` gains `proxy_state`, `region`, `connection_style`; no new route. Secrets: the proxy file path is a setting; contents never appear in logs, the status box or reports.

**Blast radius:** the X reader construction and the environment guard (RT3). A defect could stop X reads or leak the home IP; mitigated by default-off, a no-silent-fallback test and a fake proxy in tests.

**Checklist**
- [ ] Re-validate against current main and open PRs; isolated worktree; no live contact.
- [ ] Red tests: proxy assigned and sticky; dead proxy quarantined and replaced with alert; no silent home fallback; coherence mismatch blocks; user agent stable across restart and not shared; style off until verified, refused when unverified; global proxy variable still refused; secrets never logged.
- [ ] Implement the proxy module and per-account reader construction; the style switch; guard amendment with listed test replacements and reasons.
- [ ] Fake proxy server and fake reader smoke on loopback only; then one owner-approved live comparison of the two connection styles on the two real accounts, recorded as evidence (a separate step needing the owner's go; reads only, within the existing budget).
- [ ] Status box states and a bounded width check if memory allows.
- [ ] Consolidated run, draft PR, CI on the final head, report. No merge, no deploy.

**Verification Evidence (Part B)**

| Gate / Scenario | Strategy | Proves SPEC criterion |
|---|---|---|
| Sticky proxy per account; dead proxy quarantined, next healthy used, alert, cooldown | Fully-Automated | AC9 |
| No silent fallback to the home connection | Fully-Automated | AC9 |
| Region coherence blocks a mismatched account | Fully-Automated | AC10 |
| User agent stable across restart; no two accounts share IP and user agent | Fully-Automated | AC19 |
| Style off until installed files verified; refused when unverified; plain style available | Fully-Automated | AC20 |
| Two-style comparison on real accounts recorded with challenge and result counts | Agent-Probe (justified: needs live accounts) | AC11, AC20 |
| Secrets absent from logs, status box and reports | Fully-Automated | AC17 |

**Risks:** free proxies are unreliable and often blocked (quarantine and health checks; the home connection stays the safe default); a global environment variable switches the style for the whole process (so all accounts share it; documented); the live comparison costs reads and can draw a challenge (small, owner-approved, within budget).

## Risks and Mitigations

A counter bug stops X early: default off, fake-clock tests. State file break: backward-compatible load and an old-file fixture. A resting account strands the pool: sizing warning and the grandfather rule for existing accounts. Status box overflow at 375 px: wrap and a width check. The owner's local config edit interferes with tests in a shared folder: tests use isolated config and never read the main folder.

## Test Infra Improvement Notes

(none identified yet; VALIDATE records any.)

## Validate Contract

(placeholder, vc-validate-agent writes this section before EXECUTE)

## Resume and Execution Handoff

1. Selected plan: process/general-plans/active/collector-identity-pool_02-11-26/collector-identity-pool_PLAN_02-11-26.md (branch claude/identity-pool-spec, with the SPEC, draft PR #232).
2. Last completed phase: PLAN drafted (Part A and Part B; 02-11-26, identity stage moved up by the owner).
3. Validate-contract status: pending.
4. Supporting context: the SPEC and its Build Order; x_pool.py, web_queries.py, attention_pc_refresh.py (XStream), sources.py, CollectorStatus.tsx; the Camoufox probe report (docs only, PR #233, merged) for why Stage 1 is parked; tests context router.
5. Next step: VALIDATE Part A first (bind exact test paths, check overlap with open PRs and the provider-fallback session's screener and equities files, confirm state-file migration), then the owner's explicit ENTER EXECUTE MODE; one isolated worker, default model.

## Cursor and RIPER-5 Guidance

One plan only. VALIDATE before EXECUTE. Source changes need explicit approval. Do not build Stage 2 or later without their triggers in the SPEC Build Order being observed. Part B starts only after Part A is merged and the owner approves it.
