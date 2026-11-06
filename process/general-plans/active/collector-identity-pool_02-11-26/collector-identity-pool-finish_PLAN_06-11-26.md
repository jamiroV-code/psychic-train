---
name: plan:collector-identity-pool-finish
description: "Finish plan for the X (twscrape) + Reddit collector: S-X hardening (query-id drift, per-account 404 isolation, suspended code 64, cookie jar), B3 behaviour measures, real-Chrome cookie harvest helper, Reddit Arctic Shift archive method plus owner-gated live fallbacks, daily report, status UI, runbook/probes/doctor/scheduled tasks, and one runnable end-to-end acceptance on synthetic fixtures."
date: 06-11-26
feature: narrative-baskets
---

# Collector identity pool: FINISH plan (X + Reddit working system, no feature cuts)

Date: 06-11-26
Complexity: Complex (standard complex by envelope: one authoritative plan file, executed in slice waves; each slice re-researches at its Stage 0 before code)
Context router: process/context/all-context.md (test commands and tiers: process/context/tests/all-tests.md and process/context/operating-instructions.md)
Selected SPEC: collector-identity-pool_SPEC_02-11-26.md (this folder); canonical collector SPEC: process/general-plans/active/narrative-baskets_02-10-26/narrative-baskets-xreddit-collector_SPEC_21-10-26.md
Supersedes for EXECUTE of the remaining work: collector-identity-pool_PLAN_02-11-26.md Part B3 and Part C (those sections stay as history and as parameter authority where this plan says so)
Worktree of record for the code: `C:/Users/jamir/.herdr/worktrees/my_site/wt-b2-validate`, branch `claude/b2-validate`, B2 present as uncommitted completed work.

Status: PLANNED (PLAN phase only; nothing in this file is built; VALIDATE pending). Phase markers used below: ⏳ PLANNED, 🔨 CODE DONE, 🧪 TESTING, ✅ VERIFIED, 🚧 BLOCKED. B2 itself is 🔨 CODE DONE with automated acceptance PASSED WITH CAVEATS (VALIDATE-B2 §20) and live release 🚧 BLOCKED on owner inputs; this plan does not change that.

## Quick links

[Overview](#overview) · [What changed since 02-11-26](#what-changed-since-the-02-11-26-plan-evidence-that-shapes-this-plan) · [Goals](#goals-and-success-metrics) · [Owner-only inputs](#what-only-the-owner-can-supply) · [Decisions](#architecture-decisions-final-for-this-plan) · [Slice table](#slice-table) · [Ordering](#ordering-parallelism-and-shared-file-ownership) · [Slices](#slice-specifications) · [Public Contracts](#public-contracts) · [E2E acceptance](#the-one-end-to-end-acceptance) · [Verification Evidence](#verification-evidence) · [Risks](#risks-and-mitigations) · [Owner decisions](#decisions-that-need-the-owner) · [Handoff](#resume-and-execution-handoff)

## Overview

The owner demands a finished, working data collection system: daily data for every eligible coin from X (twscrape) and Reddit, with no feature cuts and no unfinished results. Observed state on 06-11-26 (gap map `agent://GapMap`, read-only, nothing re-run): Part A (caps, rest, ready, sizing, coverage text, status UI) is implemented and merged; B1 (wire identity, backend verification) is merged (PR #239/#240, merge `febe7f44`); B2 (private per-account routes, admission, quarantine, HMAC child attestation, protected SQLite) is complete and locally tested on synthetic fixtures but uncommitted, live release blocked on owner inputs. Missing: B3 behaviour measures, any cookie renewal, any Reddit source that survives 13-11-26, any query-id drift handling, the AC14 daily report as a first-class artifact, the owner probe suite, a doctor/self-check, collector scheduled-task wiring, and an end-to-end proof.

The two research references of 06-11-26 change the plan materially: X query IDs may already be stale (SearchTimeline `vLHjqbDv7TPFMBkIIO1nOA` in the public bundle versus the pinned `BYppgupFFS2yqVmmRNjlsw`), and every anonymous Reddit surface except the Android GraphQL app API is dead or ending while RSS ends 13-11-26. This plan therefore (1) hardens the X reader against drift, per-account 404s and suspension, (2) builds B3 as five independently switchable and measured measures, (3) builds a harvest-only real-Chrome helper (never types credentials) for cookie renewal, (4) replaces the Reddit RSS/search methods with an Arctic Shift archive method as primary and two owner-gated live fallbacks, each a separately labelled method, (5) produces the AC14 daily report and the status UI for all of it, and (6) ships the runbook, probe suite, doctor and scheduled-task wiring, proved by ONE runnable end-to-end acceptance on synthetic fixtures (fake X over loopback TLS, fake Arctic Shift, synthetic accounts, fake Chrome over loopback CDP).

Everything buildable is built to completion against fixtures without any owner input. Only live evidence, accounts, proxies and the enabling decisions need the owner (section "What only the owner can supply"). Code that cannot be proven against the real service without the owner is gated by recorded probe evidence and default-off switches, never stubbed.

## What changed since the 02-11-26 plan (evidence that shapes this plan)

Evidence labels: [OBS] observed by the research worker first-hand, [3P] third party, [INF] inference. Full evidence is in `collector-identity-pool-reddit-research_REF_06-11-26.md` (REF-R) and `collector-identity-pool-x-research_REF_06-11-26.md` (REF-X).

| # | Finding | Consequence in this plan |
|---|---|---|
| 1 | REF-X §2.4 [OBS]: public bundle SearchTimeline ID `vLHjqbDv7TPFMBkIIO1nOA`, pin and upstream HEAD `BYppgupFFS2yqVmmRNjlsw`; 10 of 12 comparable pinned operations differ; upstream refreshed IDs 8 times 05-20..10-21 and not since; whether X still answers the old ID is [LIVE] | S-XHard builds a self-refreshing, canary-gated query-id handler with drift state, plus per-account isolation of 404s. No twscrape upgrade (nothing at HEAD is required, REF-X §2.5). |
| 2 | REF-X §2.2/§4.1 [3P, one reporter]: an empty-body 404 on SearchTimeline is byte-identical for a stale ID, a bad transaction ID and a per-account endpoint restriction | A per-account, per-endpoint 404 latch before the global drift streak (`DRIFT_STOP=3` in `x_pool.py:61`) can pause the whole stream. |
| 3 | REF-X §2.3 [OBS code]: the pin has no `(64) suspended` branch; ours has `INACTIVE_CODES` 88/326/32 only (`x_reader.py:54`) | Add `64` via `ApiError.errors` in our classifier; deactivate and fail over. |
| 4 | REF-X rec 8 [OBS offline]: the pinned curl path and our `CurlRouteClient` pattern (`Cookies(cookies)` then `.update(session.cookies)`) sends `ct0=OLD; ct0=NEW` | S-XHard fixes domain scoping and proves exactly one `ct0` on the wire. |
| 5 | REF-X §3 [OBS/3P]: twscrape HTTP login is dead (366/399, Castle token); only real headful Chrome minted tokens in one hobby project; failed login attempts can flag the account; locked accounts hit a palm-scan check | DO NOT build automated login. S-Cookie is harvest-only: real Chrome, one profile per account, the account's own route, CDP cookie read, never types credentials, stops at login/challenge, one account at a time, one harvest per account per day. |
| 5b | REF-X §3.2 [OBS/INF]: cookie `Expires` is not the limiting factor (400-day Chrome clamp); no evidence of scheduled forced re-login; `ct0` rotation unknown [LIVE] | Harvest is triggered by `x_login_required` or an optional age threshold; the cookie-age plus cause instrumentation answers the SPEC Stage 2 trigger with data. |
| 6 | REF-X §4.3 [OBS evidence absent]: quiet hours and warm-up have no primary or reproducible evidence | The owner still wants them (SPEC AC12). They are built as switchable measured measures, default off, with an offline benefit/removal report; no efficacy claim. |
| 7 | REF-R §2: RSS ends 2026-11-13; new API access requests ended 2026-10-31; API removal begins 2027-01-12; public API ends "March 2027"; anonymous `.json` 403 since 2026-10-28 (comments since 10-20); Shreddit fragments blocked anonymously | The RSS methods `reddit_web` / `reddit_stream` die 13-11-26. They stay in code and report their blocked state; they are not the future. |
| 8 | REF-R §3 [CODE/ISSUE, public instance badge OBS 06-11]: only the Android app GraphQL (`gql-fed.reddit.com`, app-only token) answers anonymously; no subreddit-wide comment stream | S-RGQL: an owner-gated live fallback, honestly labelled partial for comments. |
| 9 | REF-R §1 O5-O11 [OBS]: Arctic Shift live; posts near real time; comments sweep-based, lag median 41-65 min, tail 337 min on 25-samples; IDs non-monotonic since 2026-10-21 (page by `created_utc`); aggregate day buckets look Europe/Berlin; busy subs return HTTP 422 `Timeout. Maybe slow down` | S-RArchive is the primary Reddit method: raw paging by `created_utc`, local matching, explicit timezone calibration, two-pass day close, 422 handling, monthly dump reconciliation. |
| 10 | REF-R §5 [CODE/ISSUE, conflicting]: cookie HTTP needs a browser-matching TLS/HTTP stack; logged-in listings/search refused to emulated cookie sessions (Nov 2026 probe) but worked in a real Chrome (vendor, 10-18, n=1) | S-RBrowser (logged-in real Chrome, intercepting the page's own network responses) is the second owner-gated fallback; evidence conflicts, so it is gated on probe P2. |
| 11 | Canonical SPEC AC36/AC34 (read this session): the existing archive rules allow ONLY ID endpoints (`/api/posts/ids`, `/api/comments/ids`) for optional engagement enrichment, and `test_reddit_collector_guards.py` guards it. No archive client exists in code (grep: only the guard file mentions arctic) | A dated superseding amendment (S-Canon) and a deliberate guard amendment are required before the archive counting method may call search endpoints. |
| 12 | `registry._known_at_time` (read this session) drops points collected after D+1; archive values settle at D+2 | S-RCore adds a per-method known-lag so point-in-time safety stays exact instead of silently dropping the whole archive series. |

## Goals and Success Metrics

Primary goal: every eligible coin has a stored, correctly labelled daily value from X and from Reddit, every day, or an honest "missing" with a reason; the owner sees it in the status box and in a daily report; the system runs unattended on the owner's PC and tells the owner exactly what to do when it cannot.

| Metric | Target (proved on synthetic fixtures by the E2E; real-world values are owner-measured) |
|---|---|
| X coverage | All eligible coins have a value or a reason per UTC day; with N accounts at per-account cap C the sizing warning is exact; loss of an account costs only its in-flight coin-day |
| X resilience | Stale query ID, per-account 404, suspended account, expired cookie each end in a defined, tested state; none ends in a stream-wide pause without a real second opinion |
| Reddit coverage | Each eligible coin-day gets a value from the archive method after its day-close, or a missing reason; methods never merge |
| Reporting | `daily_report_<day>.json` plus status card; 100% stored is stated only when eligible == stored; missing never rendered as zero |
| Ops | `collector_doctor` returns PASS/WARN/FAIL/UNKNOWN for every owner input and subsystem in one command; scheduled tasks registered by script; probe suite records evidence under strict budgets |
| Safety | No secrets in repo, logs, status, reports, argv or env; all optional measures default off and all-off equals today's behaviour (AC12, AC18) |

## Acceptance Criteria

Program-level criteria (each maps to the SPEC ACs in the coverage map under Verification Evidence; slice-level criteria are in each specification, IDs XH-, BH-, CK-, RC-, AR-, GQ-, BR-, RP-, ST-, OP-).

- FA-1 X reliability: a stale query ID, a per-account 404, a suspended account (code 64) and an expired cookie each end in their defined, tested state with no stream-wide pause unless a second opinion confirms drift; every coin-day is read once or reported missing with a reason (SPEC AC2, AC3, AC6, AC18, AC19).
- FA-2 Cookie renewal without credentials: harvest-only real-Chrome helper, one browser machine-wide, one account at a time, never types credentials, stops at login/challenge with an owner-action state; no cookie value in any log, state or argv (AC1, AC2, AC3, AC8, AC17).
- FA-3 Behaviour measures: five independent switches, each with health and an offline benefit/removal report; all-off equals Part A behaviour (AC12).
- FA-4 Reddit: the archive method is separate, labelled, two-pass settled, first-write-wins, zero only under option B, reconciled monthly; live fallbacks are separate, labelled, owner-gated by fresh probe records; methods never merge (AC15, AC14, AC18).
- FA-5 Reporting: a daily report per UTC day with eligible/stored/exact/estimated/missing and reasons; missing never zero; 100% only when eligible == stored (AC14); status box shows every new state, unknown never healthy or zero (AC13).
- FA-6 Operability: one-command doctor, probe suite with dry-run default and budgets, scheduled-task registration script, runbook with exact owner inputs (AC11, AC16, AC17, AC20).
- FA-7 One runnable end-to-end acceptance proves a full daily cycle (steps C1-C15) on synthetic services with zero skips and no secret in any artifact; its limits are stated (AC1-AC20 integration).
- FA-8 Nothing requires the owner to finish the code: owner inputs only enable, evidence or supply accounts/routes, and missing inputs are reported, never defaulted unsafely.

## Phase Completion Rules

A slice is NOT complete until:

1. **Integration Test** - works with the neighbouring slices' real modules (not mocks of them) on synthetic fixtures.
2. **Manual Test** - the owner (or a recorded agent-probe where the SPEC says Agent-Probe) can perform the action with the documented command.
3. **Data Verification** - the files, pool state, store points and completeness documents it writes are inspected and quoted in its report (paths and example content, no secrets).
4. **Error Handling** - every failure kind in the slice is exercised and ends in its defined state (missing, paused with reason, owner action), never a fabricated zero or a silent direct connection.
5. **User Confirmation** - the owner says it works.

Status meanings: ⏳ PLANNED, 🔨 CODE DONE (written, not end-to-end tested), 🧪 TESTING, ✅ VERIFIED (tested AND owner confirmed), 🚧 BLOCKED. Fixture success is never VERIFIED for anything that needs a live account, route, provider, Chrome or Reddit surface: those stay "CODE DONE + fixture-proven, live evidence pending" until the matching owner probe is recorded. After each slice document: [ ] what was tested manually, [ ] data verified (file path + example), [ ] errors met and fixed, [ ] owner confirmation. No live accounts, live cache or live collector are touched by tests; one heavy test or build at a time (8 GiB host).

## What only the owner can supply

The code for every slice is complete without these. These are inputs and decisions that no agent can produce; each has a doctor check that reports it missing.

| Owner input | Needed for | Doctor check / safe behaviour while missing |
|---|---|---|
| Throwaway X accounts (genuinely owner-created; arithmetic: about 4, worst case 6, accounts for 72 coins at 800 reads each, SPEC Constraints) with manual logins and the one-week rest | X coverage | `accounts_sizing`: WARN with shortfall in reads; with fewer accounts the day finishes partially and the report says missing, not zero |
| One private proxy per X account (list, assignments, policy, service SID, ACL set per B2) or an explicit decision to run direct/off | One account one IP (SPEC rule) | Proxy-required with missing files refuses admission, never goes direct (B2); doctor lists exact missing files |
| Installed real Chrome or Edge path, a private profile root outside the repo, and one manual login per account in its own profile | S-Cookie, S-RBrowser | `browser_path`, `profile_root_acl`, `profile_logged_in` checks; harvest refuses without them |
| Private owner query config path (collector block with the keys in Public Contracts) | Everything configured | Launcher refuses; doctor validates strict schema |
| Arctic Shift monthly dump file (manual download or torrent) for reconciliation | Archive measured completeness | `reconcile` state `waiting_for_dump`; values are unaffected |
| Approval to run each live probe (PX1-PX6, PR1-PR6) and the real two-account transport comparison | Evidence, default decisions (AC11, AC20), owner-gated Reddit fallbacks | Probes default to dry-run: they print the exact requests and budgets and send nothing without `--approve <probe-id>` |
| Enabling decisions: `reddit_archive_enabled`, `x_queryid_mode`, each B3 switch, harvest, any live Reddit fallback | Turning features on | Everything defaults off; doctor recommends from recorded evidence, never flips |
| Optional: ipapi selection and its terms, Spamhaus/FireHOL terms review | B2 metadata/blocklists | Unselected provider: region is owner-declared provenance (B2 contract) |

## Non-goals and constraints (carried, plus new)

- No account creation, purchases, captcha solving, main/Premium accounts, redistribution of any browser, bought data, or paid APIs. No twscrape upgrade. No dependency-file changes (`api/pyproject.toml`, `uv.lock`, `web/package.json`): the CDP client uses `websockets` already present through `uvicorn[standard]`, memory checks use stdlib/ctypes. If a slice proves it truly needs a new dependency it STOPS and reports to the owner.
- Stage 3 V2Ray gateway stays parked by its own SPEC constraint (a trigger the doctor measures). See "Decisions that need the owner", item 2.
- Reddit official API application: not available (closed to new owners 2026-10-31); the owner decision 02-11-26 "no application" stands.
- The B2 contracts (admission, quarantine, HMAC child attestation, protected SQLite, exact-key state, lock, resource limits) are inputs, not re-opened. Changes to the child work envelope are the ONE security-relevant protocol change here (query id, see XH-3) and require a security re-read at VALIDATE.
- Browser = installed real Chrome/Edge (Chromium over CDP), not Camoufox (REF-X §3.1: Camoufox fails the Castle check and is heavy per our own probe; this supersedes SPEC Stage 2/4 wording about Camoufox, recorded by S-Canon).
- `.github/` changes only if a slice needs them and then minimal, guard-tested (owner standing permission 02-11-26). The plan expects none.

## Architecture decisions (final for this plan)

1. **One plan, slice waves.** The envelope asks for ONE plan file. Execution is by slice, each preceded by its own Stage 0 read-only re-research and ended by a slice report; the plan never hands EXECUTE the whole program at once (next instruction names the first slices).
2. **Config first, status last.** All new optional settings are declared once (Public Contracts) and validated by S-Config before any consumer slice; all status/UI plumbing is owned by S-Status after the contract is fixed. This removes the two biggest shared-file collisions (`web_queries.py` and the status stack).
3. **Method separation is structural.** Each Reddit method has its own source id, store, method string, completeness document, request budget, state, label and status row. `pick_impl` chooses ONE method per window and never mixes (AC14, AC15). Counts only, no text, hashed authors (existing salt), deletion-compliant.
4. **First-write-wins is preserved.** The research suggested overwriting with the larger later value; that contradicts AC18. The archive method instead keeps provisional pass files outside the store and commits a day exactly once, when two passes at least 24 h apart agree within a tolerance (or the close window ends and the coin-day is missing). Later dump reconciliation is a separate measured-completeness report, never a rewrite.
5. **Gated live fallbacks.** Anything that needs live evidence to be trusted (anonymous GraphQL, logged-in browser, query-id auto adoption, harvest on real Chrome) is built fully, tested on fixtures, default off, and where it touches Reddit it additionally refuses to run without a fresh recorded owner probe record of the matching probe id. Missing probe evidence yields state `needs_probe`, not a guess.
6. **Fail closed, say why.** Every refusal has an allowlisted reason code that reaches the status box; unknown renders "unknown", never healthy or zero.
7. **Safety rails never depend on a switch.** Global ceilings, per-account caps, canary, challenge pause, login/debug/telemetry protections, route fail-closed and zero-vs-missing rules stay active regardless of any new switch.
8. **Serialization.** One browser process machine-wide (cross-process lock before launch), one account harvested at a time, one probe at a time, one heavy test run at a time.

## Slice table

| Slice | Name | RT tier | Size (INFERENCE) | Depends on | New / owned files (summary) | SPEC ACs |
|---|---|---|---|---|---|---|
| S-Land | Land B2 (commit, draft PR, CI) | RT4 gate | S | owner approval | none new (commit of existing B2 work) | AC9, AC10, AC17, AC19, AC20 (existing) |
| S-Canon | Superseding canonical-SPEC and context amendments | RT0 | S | none | canonical collector SPEC (append-only notes), `process/context/*` notes | AC18 |
| S-Config | All new optional settings and validation | RT2 | S-M | S-Land | `web_queries.py`, `test_web_queries.py`, `test_x_window.py` fixture touch | AC12, AC16, AC18 |
| S-XHard | X hardening: query IDs, 404 isolation, code 64, cookie jar | RT4 (touches child protocol, cookies) | M-L | S-Land, S-Config | `x_queryids.py`, `x_queryids_fetch.py`, edits in `x_reader.py`, `x_pool.py`, `twscrape_reader.py`, `x_proxy_curl.py`, `x_proxy_child.py`, `x_proxy_snapshot.py` | AC3, AC6, AC17, AC18, AC19 |
| S-B3 | Five behaviour measures + offline benefit report | RT3 | L | S-XHard (x_pool chain) | `x_quiet.py`, `x_behaviour.py`, `x_behaviour_report.py`, edits in `x_pool.py`, `attention_pc_refresh.py`, `twscrape_reader.py` | AC12, AC4, AC6, AC7, AC13, AC18 |
| S-Browser | Single-instance Chrome host + CDP client | RT4 (runtime, secrets) | M-L | S-Config | `browser_host.py`, `browser_cdp.py`, fake-browser fixtures, new guard file | AC1, AC8, AC17 |
| S-Cookie | Harvest-only cookie helper | RT4 | M-L | S-Browser, S-XHard, S-B3 (pool chain) | `x_harvest.py`, edits in `twscrape_reader.py`, `x_pool.py`, `attention_pc_refresh.py` | AC1, AC2, AC3, AC8, AC17 |
| S-RCore | Reddit method core, registry, registration seam | RT3 | M | S-Config | `reddit_core.py`, edits in `registry.py`, `web_queries.py` (none; consumes S-Config), `attention_pc_refresh.py` seam | AC15, AC18 |
| S-RArchive | Arctic Shift archive method | RT3 | L | S-RCore | `arctic_shift.py`, `reddit_archive.py`, `reddit_archive_reconcile.py`, probe PR4 runner part | AC15, AC14, AC18 |
| S-RGQL | Anonymous GraphQL live fallback (owner-gated) | RT3 | L | S-RCore | `reddit_gql.py`, `reddit_live.py` (lanes), fake gql server fixture | AC15, AC17 |
| S-RBrowser | Logged-in Chrome live fallback (owner-gated) | RT4 | L | S-RCore, S-Browser | `reddit_browser.py`, fake CDP Reddit fixtures | AC15, AC8, AC17 |
| S-Report | AC14 daily report | RT3 | M | S-RCore, Part A coverage | `daily_report.py`, `api/scripts/attention_daily_report.py` | AC14 |
| S-Status | Status contract: API models + web UI + seeded browser | RT3 + RT1 | M-L | contract only (can start with S-Config) | `sources.py`, `models/discovery.py`, web types/formatter/components/e2e | AC13, AC14, AC12 |
| S-Ops | Runbook, probe suite, doctor, scheduled tasks, examples | RT4 (deploy/runtime) | L | all backend slices for final content | `deploy/*`, `api/scripts/collector_doctor.py`, `api/scripts/probe_owner.py` | AC11, AC16, AC17, AC20 |
| S-E2E | The one end-to-end acceptance | RT4 | L | all | `api/tests/cycle/*`, `web/e2e/collector-cycle.spec.ts`, driver | AC1-AC20 (integration) |
| G-FINAL | RT4 evidence pack, owner acceptance, closeout | RT4 gate | S | S-E2E | reports only | all |

Size: S about one worker session, M two, L three or more (INFERENCE from comparable B1/B2 slices; B2 alone took several sessions). Split a slice that exceeds roughly 12 non-test files or 1,500 diff lines.

## Ordering, parallelism and shared-file ownership

Waves (a wave starts when its dependencies have landed on the integration branch; slices inside a wave run in parallel in separate worktrees with separate caches and ports):

| Wave | Slices | Notes |
|---|---|---|
| W0 | S-Land, S-Canon | Parallel. S-Land is the gate for all code slices because the B2 work is uncommitted and touches the same files. |
| W1 | S-Config first (short), then in parallel: S-XHard, S-Browser, S-RCore, S-Status (UI against the fixed contract) | Critical path for the owner: S-XHard (IDs may be stale now) and S-RCore → S-RArchive (RSS ends 13-11-26; archive backfill covers the gap, labelled backfilled). |
| W2 | S-B3 (after S-XHard on `x_pool.py`), S-Cookie (after S-Browser and S-XHard), S-RArchive, S-RGQL, S-RBrowser, S-Report | `x_pool.py` chain: S-XHard → S-B3 → S-Cookie. `attention_pc_refresh.py` chain: S-XHard (tiny) → S-B3 → S-Cookie → S-RCore seam → S-Report hook (each edit is small; the second to land rebases). |
| W3 | S-Status finish, S-Ops | Docs and scripts integrate the final field and key names. |
| W4 | S-E2E, then G-FINAL | One consolidated verification run by Main. |

Critical path (INFERENCE): S-Land → S-Config → S-RCore → S-RArchive → S-Report → S-Ops → S-E2E. X path: S-XHard → S-B3 → S-Cookie.

Shared-file ownership (a slice edits only what the matrix gives it; anything else is a request to the owning slice or a follow-up after it lands):

| File(s) | Owner chain (in order) | Rule |
|---|---|---|
| `api/data/attention/web_queries.py`, `api/tests/data/attention/test_web_queries.py`, `test_x_window.py` | S-Config only | Later slices need a new key → follow-up edit to S-Config's section, rebased; never a parallel edit. |
| `api/data/attention/x_pool.py`, `test_x_pool.py` | S-XHard → S-B3 → S-Cookie | Each adds exact-key pool keys with `setdefault` migration BEFORE the exact-key check and its rollback strip list (cumulative list in Public Contracts). |
| `api/data/attention/x_reader.py`, `twscrape_reader.py`, `x_proxy_curl.py`, `x_proxy_child.py`, `x_proxy_snapshot.py` and their tests | S-XHard → S-B3 → S-Cookie | `x_proxy_*` are B2 files: edit only what XH-3/XH-6 name. |
| `api/data/attention_pc_refresh.py`, three `test_attention_pc_refresh*.py` | S-XHard → S-B3 → S-Cookie → S-RCore (registration seam only) → S-Report (rollover hook only) | Keep each edit under about 40 lines; rebase on the previous. |
| `api/data/attention/registry.py`, `reddit_*` new modules | S-RCore creates seams; S-RArchive/S-RGQL/S-RBrowser add their own files only | Registry edits only in S-RCore. |
| `api/analytics/attention/sources.py`, `api/models/discovery.py`, `web/lib/types/discovery.ts`, `web/lib/source-health.ts`, `web/components/narrative/CollectorStatus.tsx`, `DiscoverySourcesPanel.tsx`, `web/e2e/collector-status.spec.ts` and their tests | S-Status only | Backend slices write nonsecret health into their own files/pool state in the shapes of the Public Contracts; S-Status maps them. |
| `api/tests/tooling_guards/test_x_reader_guards.py`, `test_pc_collector_guards.py` | S-XHard → S-B3 → S-Cookie | Deliberate, reasoned amendments only (list in each slice). |
| `api/tests/tooling_guards/test_reddit_collector_guards.py` | S-RCore → S-RArchive → S-RGQL → S-RBrowser | Same rule. |
| `api/tests/tooling_guards/test_browser_host_guards.py` (new) | S-Browser | |
| `deploy/README.md`, `deploy/start-collector.ps1`, `deploy/config.example.psd1`, `deploy/*.ps1` new, `deploy/examples/` | S-Ops only | Other slices put their ≤ 40-line README fragment in their slice report; S-Ops integrates. |
| Canonical collector SPEC and `process/context/*` | S-Canon (early), G-FINAL (closeout) | Append dated notes, never rewrite history. |

## Slice specifications

Each slice: Stage 0 (read-only re-research; present and stop only if a plan assumption is wrong), then red tests, implementation, slice report `collector-identity-pool-finish-<slice>_REPORT_<date>.md` in this folder. Commands are listed for the Main verifier and are NOT run by this PLAN. Backend command stem: `UV_FROZEN=1 uv run --project api --frozen --group xreader pytest <files> -q`; web: in `web/`, `pnpm exec vitest run <files>`, `pnpm exec tsc --noEmit --incremental false`.

### S-Land: land B2 ⏳

Gate, not code. The worktree has uncommitted completed B2 (git status: modified pool/reader/status/web files; untracked `x_proxy*.py` and tests). Steps: owner approves commit; commit on `claude/b2-validate` in coherent commits; open a draft PR; CI must pass on the final head; the one known unrelated failure (baseline equities Windows path-separator test, VALIDATE-B2 §20) is recorded, not waived. B2 live release stays BLOCKED. AC: B2 reachable from the integration branch; the rest of this plan rebases on it. Do not start code slices that edit B2 files before this lands (the collision risk is the point of the gate).

### S-Canon: superseding amendments ⏳ (RT0, docs only)

Append dated notes to the canonical collector SPEC (history preserved), and context docs:
- Reddit counting archive method may call the archive search endpoints `/api/posts/search` and `/api/comments/search` (supersedes AC36 for the counting method only; the optional ID-endpoint enrichment rules AC33-AC36 stay as written); spacing, cap, breaker and fail-closed rules of AC34 apply to the counting method with the values in Public Contracts.
- Reddit method set and `reddit_impl_order` default; AC3 zero rule **option B** for the archive method (canary passed + complete traversal + coin has history; definition in S-RCore); feed methods keep their trailing-median rule and are retired with the feed.
- Stage 2/4 browser decision: installed real Chrome/Edge over CDP, harvest-only for X, no credential typing, Camoufox not adopted; Stage 3 gateway parked.
- B3 scheduler exceptions (quiet hours, mixed approved calls) and the query-id refresh/static-asset fetch as the only new outbound X-side request class beyond reads.
- Evasion/identity wording for the two owner-gated Reddit live methods, including the plain statement that anonymous GraphQL impersonates Reddit's Android app and logged-in access risks the account (Rule 8 per REF-R §4); owner-gated.
AC: every later guard amendment cites one of these notes. Verification: `node .claude/skills/vc-generate-plan/scripts/validate-plan-artifact.mjs` on this plan, `git diff --check`.

### S-Config: settings and validation ⏳ (RT2)

Adds every key in "Public Contracts → configuration" to the optional defaults map, `CollectorConfig`, strict validation (types, ranges, enums, absolute-path rules, label regex, unknown keys rejected) and `as_dict()` round trip, none required, none in required `X_DEFAULTS`, so the committed queries file keeps loading. All defaults off. Cross-key rules: harvest enabled requires `x_browser_path`, `x_browser_profiles_dir` and a profile for every harvest account; `reddit_live_method != off` requires its probe-gate keys; `reddit_archive_dump_dir` absolute or null; archive timing ordering (`first pass < close delay`); `x_account_quiet_hours` labels must be configured accounts.
Tests: extend `test_web_queries.py` (each key valid/invalid, defaults, round trip, old file loads), `test_x_window.py` fixture touch (it asserts the required keys in the file). AC: all-defaults config behaves exactly as the committed file does today (AC12 all-off baseline test).

### S-XHard: X hardening ⏳ (RT4)

Owned files: new `api/data/attention/x_queryids.py` (pure: bundle parser, pinned table, state model, adoption rules), new `x_queryids_fetch.py` (lazy network: bounded static fetch), edits to `x_reader.py` (codes, 404 classification), `x_pool.py` (404 latch, query-id canary hook), `twscrape_reader.py` (binding of the active ID, error codes, cookie jar via the identity adapter), `x_proxy_curl.py` (jar), `x_proxy_child.py`/`x_proxy_snapshot.py` (envelope field), `attention_pc_refresh.py` (tiny: pass the state to the unit/canary), guards, tests.

- **XH-1 Query-ID registry.** Pure table of pinned operation IDs derived from the pinned commit (SearchTimeline `BYppgupFFS2yqVmmRNjlsw` for `63f61a5`; REF-X §2.4) and a persisted nonsecret state file `<cache>/attention/_pc_state/x_queryids.json` (`version`, per operation `{active:{id,source: pinned|bundle, adopted_at}, candidate:{id,seen_at,rejected_until,reason}|null}`, `last_check`, `bundle_sha256`, `check_state`). Only operations the reader actually uses are tracked (SearchTimeline; the three B3 ordinary calls `UserByScreenName`/`UserTweets`/`TweetDetail` if S-B3 mixed traffic is on). `x_queryid_mode` `off`: pinned only, zero fetches, state file untouched.
- **XH-2 Bounded sentinel.** Modes `sentinel` and `auto` run at most `x_queryid_static_budget_per_day` (default 6) unauthenticated static GETs per UTC day through the B2 one-shot client (no X cookies, no account, honest identity, no redirects, no retry, 4 MiB response cap, 10 s/request, URLs from fixed constants whose exact discovery path (embed page → main bundle) Stage 0 re-verifies against REF-X §2.4 and records), parses `queryId`/`operationName` pairs, compares with state, records `candidate`, never touches the pool. A blocked or malformed fetch sets `check_state` `unknown`/`blocked` (never "ok" and never "stale"). Doctor and status show `unknown` honestly. Note: in proxy-required mode the fetch uses the one-shot client with the direct/off predicate only if the owner's policy `allowed_origins` includes the static origins; otherwise `check_state` `refused_by_policy` (no hidden egress).
- **XH-3 Canary-gated adoption (mode `auto`).** A candidate becomes active only after a canary unit run with the candidate ID passes the existing canary decision (`x_pool` canary, `x_canary_min_results`, overlap/tolerance); rejection sets `rejected_until` = +24 h with an allowlisted reason. When the active ID produces confirmed drift (404 after XH-4 isolation, `gql_outdated`, `xclid_parse` unaffected) and a candidate exists, the candidate is tried by the canary BEFORE `DRIFT_STOP` pauses the stream; if it passes it is adopted and the pause never happens; otherwise the existing pause stands. The active ID is bound at the unit boundary by replacing the library's module-level operation constant through the same lazy, signature-asserting wrapper style the identity adapter uses (`search_raw` reads `OP_SearchTimeline` at call time in the pinned `twscrape/api.py:287-288`, observed this session); compatibility assertion refuses startup if the hook shape differs. The fallback child receives the ID in the attested work envelope: add one exact-key field `query_id` (nullable string, `[A-Za-z0-9_-]{16,32}`) as a further framed HMAC field and bump the framing domain to `collector-b2-child-v2`; both ends ship together; negative tests: tamper, absent, malformed, v1 refused. Without this the fallback child would silently run the pinned ID exactly when refresh is active.
- **XH-4 Per-account 404 isolation.** A `not_found` (empty-body 404, `XCLID_404_PREFIX`) no longer immediately feeds `drift_streak`. Rule: on the first 404 for account A on SearchTimeline, if at least one other active, selectable account exists, rerun the SAME unit once on it (charged normally, coin-day counted once). If the second account succeeds: A is marked endpoint-restricted for SearchTimeline (pool keys `endpoint_404_day`, `endpoint_404_count`; second distinct-day strike or `count >= 2` locks A for 24 h as `("locked","endpoint_404")`, reason code `x_endpoint_404`); drift streak not incremented. If the second account also 404s: drift (existing path, then XH-3). With a single active account there is no second opinion: behaviour unchanged. Never rotate a proxy for this.
- **XH-5 Suspended code 64.** Add `64: "x_account_suspended"` to `INACTIVE_CODES`; carry the allowlisted integer codes from `ApiError.errors` through `ReaderFailure` (currently `map_exception` returns a bare `api` kind, `twscrape_reader.py:687-688`); deactivate, fail the coin-day over once, count once, status shows it. No other code is added without evidence.
- **XH-6 Cookie jar.** Build the jar so cookies are scoped to `.x.com` and a refreshed `ct0` REPLACES the old one (REF-X rec 8; upstream PR #363 semantics) on the identity adapter's curl and httpx paths and in `CurlRouteClient`. Wire test: the fake X server asserts exactly one `ct0` in each `Cookie` header and equality with `x-csrf-token`, for both backends, GraphQL and bootstrap, after a cookie refresh. Observe-only counter `ct0_rotations_seen` (a `Set-Cookie: ct0` that differs from the stored value) appears in health (unknown until observed); adoption of a rotated `ct0` is NOT automatic (evidence absent, REF-X §3.2); S-Cookie's harvest is the supported way to update stored cookies.
- **XH-7 Backfill honesty.** No code change; `x_backfill_days` above 7 gets a doctor WARN (REF-X rec 10: 7 days is the practical search horizon).

Tests (red first): `test_x_queryids.py` (parser on a synthetic minimal bundle, state transitions, adoption rules, off-mode no-fetch), `test_x_queryid_fetch.py` (loopback fake static origin: budget, caps, redirect refusal, blocked/malformed = unknown), extend `test_x_pool.py` (404 isolation with 1, 2, 3 accounts; `endpoint_404_*` migration and rollback; drift still pauses when both 404; candidate-before-pause), `test_x_reader.py` (code 64), `test_twscrape_reader.py` and `test_identity_transport.py` (single `ct0`, ID binding, child `query_id`), `test_x_proxy_*` envelope v2 cases, guards (static fetch module allowed network, pure registry no network). Deliberate amendments, each with a reason: guard lists of network modules; any test asserting `DRIFT_STOP` immediately on first 404; child protocol exact-key tests (v1 → v2).
Done when: stale ID, per-account 404, suspended account and refreshed cookie each end in their tested state; all-off equals today's behaviour; no secret appears in the state file, logs or child output (marker scan).

### S-B3: behaviour measures ⏳ (RT3)

Authority for parameters, switches and rollback: collector-identity-pool_PLAN_02-11-26.md "Part B → B3" (Public Contracts table, pool additions, red-test list). This slice implements that contract unchanged except for the additions below. Owned files: new pure `x_quiet.py` (zoneinfo window math, DST fold/gap), `x_behaviour.py` (pure rules: effective cap ladder, variation seeding, cooldown decisions, mixed-call budget), `x_behaviour_report.py` (offline analyzer), edits in `x_pool.py` (eligibility, effective cap, keys), `attention_pc_refresh.py` (`_next_due`, mixed scheduling), `twscrape_reader.py` (the three approved ordinary calls through the explicit wrapper allowlist), `x_reader.py`, tests, guards.

Five switches (all default false, independent, each with its own health): `x_quiet_hours_enabled`, `x_mixed_traffic_enabled`, `x_variation_enabled`, `x_adaptive_cooldown_enabled`, `x_warmup_enabled`. Additions: (a) Evidence status stated in code docstrings, status text and doctor: quiet hours and warm-up have no primary evidence (REF-X §4.3); health must show deltas, never claim efficacy. (b) `x_behaviour_report`: a local, read-only analyzer over pool state, completeness documents, charge counters and challenge/cooldown history that, for any date range, compares "all measures off" days with "measure X on" days (counts per account, challenges, locked/paused days, missing coin-days, spent reads, shrink events) and prints a keep/remove/inconclusive recommendation with the sample size; "inconclusive" is the default below a stated minimum (7 comparable days per arm). CLI: `python -m api.data.attention.x_behaviour_report --from D --to D`. The SPEC's "measures that show no benefit are removed" rule is then actionable by data. (c) The guard `fixed_hour_offenders` in `test_pc_collector_guards.py` (AC28: nothing compares the clock to an hour of day) is amended narrowly: only `x_quiet.py` may build hour/minute windows, only through zone-aware math, only when the switch is read; the rest of the guard is unchanged. (d) Adaptive cooldown consumes the stripped-page strike signal merged in PR #236 and does not reclassify raw pages.

Pool keys added (cumulative list in Public Contracts): `warmup_start_day`, `behaviour_cooldown_until`, `behaviour_reason`, `shrink_run`, `result_history`, `mixed_day`, `mixed_calls`. Tests per the B3 red-test list (each switch independently on/off plus all-off baseline; quiet midnight/DST; mixed allowlist/budget/no-coin-writes; variation bounds; cooldown precedence; warm-up boundaries; migration/rollback) plus analyzer tests on synthetic multi-day histories.
Done when: every measure has a switch, health and an offline report row; all-off baseline test equals Part A behaviour; no measure can bypass the global ceiling, canary or challenge pause.

### S-Browser: single-instance Chrome host and CDP client ⏳ (RT4)

New files: `api/data/attention/browser_host.py` (lifecycle, locks, memory, flags, route binding), `api/data/attention/browser_cdp.py` (CDP over loopback websocket with a method allowlist), fixtures `api/tests/data/attention/browser_fake.py` (in-process fake Chrome: serves `DevToolsActivePort`, a loopback CDP endpoint, canned cookie jars and pages), tests, new guard file `api/tests/tooling_guards/test_browser_host_guards.py`. No `pyproject`/lock change: `websockets` is already locked via `uvicorn[standard]`; memory via `ctypes` (`GlobalMemoryStatusEx` on Windows, `/proc/meminfo` elsewhere).

- **BH-1 Single instance (AC8).** A cross-process exclusive lock (same OS lock primitive as the pool state lock in `x_proxy_private.state_lock`) on `<cache>/attention/_pc_state/browser.lock` acquired BEFORE launch; a second acquirer gets `browser_busy` immediately (the Camoufox probe hung 180 s on a double-open, SPEC Background). A per-profile lock file inside the profile root is also taken before launch.
- **BH-2 Memory floor (AC8).** Refuse launch when free physical memory is below `browser_memory_floor_mb` (default 1536) with reason `low_memory`; sample the child tree's RSS while running and kill it above `browser_rss_ceiling_mb` (default 1200), reason `rss_ceiling`. The reading source is injected for tests; unreadable memory = refuse, not allow.
- **BH-3 Launch.** Executable from `x_browser_path` (Chrome or Edge, absolute, must exist, version read recorded); `--user-data-dir` = `<x_browser_profiles_dir>/<profile name>` (one per account; two accounts mapping to one directory is a config error, AC1); profile root passes the same private-ACL verification as the B2 private root on Windows (`x_proxy_private.verify_private` reused read-only, outside the repository, AC17); non-default user-data-dir only (Chrome 136+ ignores the debug port for the default directory, REF-X §3.4); `--remote-debugging-port=0` bound to 127.0.0.1 and the real port read from `DevToolsActivePort`. Fixed flag set: no first-run/sync/component-update/background-networking/domain-reliability/default-browser-check, QUIC disabled, `--force-webrtc-ip-handling-policy=disable_non_proxied_udp`, `--proxy-server` from the admitted route (and `--proxy-bypass-list` empty), one visible window. The spawn function is a constructor-injected callable (default `subprocess`), the same dependency-injection pattern as `_default_x_start`, so tests never need a production fixture switch.
- **BH-4 Route binding.** Proxy-required accounts launch only with their admitted route (fresh admission snapshot via the B2 runtime) and otherwise refuse `proxy_not_admitted`; credentials for an authenticated HTTPS proxy are answered through CDP `Fetch.authRequired`/`continueWithAuth` from the private resolver's in-memory value; never in argv, env, files, logs or exceptions. Direct launch only under the explicit direct/off predicate. No home-connection fallback, no retry on another IP.
- **BH-5 CDP allowlist.** The client sends only an explicit method allowlist per role (`harvest`: `Target.*` open/close tab, `Page.enable/navigate`, `Network.enable/getCookies`, `Storage.getCookies`, `Fetch.enable/authRequired handling`, `Browser.close`, `Runtime.evaluate` restricted to the literal expression `location.href`; `reddit_read`: additionally `Network.responseReceived`/`getResponseBody` events and a bounded scroll expression). Anything else raises before sending. No `Input.*` in the harvest role (the "never types credentials" guarantee is a tested allowlist, not a promise). Frame size, event count and total bytes are bounded.
- **BH-6 Lifecycle.** Hard wall-clock timeout; on exit or timeout kill the whole process tree (Windows `taskkill /T /F` by pid through an injected runner), verify it is gone, release locks in `finally`; no orphan on exception.
- **BH-7 Secrets.** No cookie value, proxy credential or profile path in logs/exceptions; typed safe failure reasons.
Tests: lock contention (two acquirers), low-memory refusal with injected reader, RSS kill, exact argv assertion (flags present, nothing secret), allowlist rejection of `Input.dispatchKeyEvent` and `Runtime.evaluate` of anything but the literal, proxy-required refusal without admission, no-orphan on exception, profile-dir uniqueness/ACL refusal, secret-marker scan of captured logs and argv.
Done when: the fake-browser acceptance passes with zero skips and the guard file proves the allowlist and no-input property statically. Real Chrome behaviour (RSS, flags accepted, proxy auth) is probe PX6, not claimed here.

### S-Cookie: harvest-only cookie helper ⏳ (RT4)

New `api/data/attention/x_harvest.py`; edits in `twscrape_reader.py` (`--harvest-cookies LABEL [--interactive]` CLI, `refresh_from_harvest`), `x_pool.py` (harvest keys and the `x_login_required` hook), `attention_pc_refresh.py` (unit-boundary trigger), guards, tests. Uses S-Browser; touches no credential.

- **CK-1 Procedure (the only one).** At a unit boundary, never during that account's unit, one account at a time, behind the global browser lock: launch real Chrome with that account's profile through that account's route; open `https://x.com/home` in the existing profile; wait up to `x_harvest_timeout_s`; read the final URL via the literal `location.href`. LOGGED IN iff the final path is `/home` AND CDP returns `auth_token` and `ct0` for `.x.com`. Otherwise (login, `/i/flow/*`, `/account/access`, `/i/palm-liveness`, consent, unknown): STOP, close the browser, set the account's pool state to paused with reason `x_login_required` and `harvest_state=needs_owner`; do nothing else, never retry, never switch IP.
- **CK-2 Triggers.** (a) pool pause `x_login_required` with `x_cookie_harvest_enabled`; (b) optional age threshold `x_cookie_refresh_age_days` (null = off) using the recorded cookie age (`cookie_ages`); (c) owner command. At most one harvest per account per UTC day (`harvest_day`), enforced even across restarts.
- **CK-3 Hand-off.** Validate cookie names/lengths/charset; upsert through the existing `refresh_cookies` path and the B2 protected DB hook (atomic, ACL-verified); reconcile identity (cookies, locks and counters preserved); evict that account's reader/bootstrap cache; schedule a canary (same mechanism as a changed route revision); update `cookie_ages`. Cookie values live only in memory and the DB hook; logs carry age and reason class only (AC2).
- **CK-4 Interactive owner login helper.** `--harvest-cookies LABEL --interactive` opens the visible window on the account's route; the OWNER types credentials, 2FA and challenges by hand; the helper only polls the URL (read-only) up to a timeout, then harvests as CK-1. It never fills a field.
- **CK-5 Never types credentials.** Enforced by BH-5 allowlist at runtime and a static guard asserting `x_harvest.py` references no `Input.` method and no credential/TOTP/IMAP symbol; the pin's login features stay excluded (existing guard).
- **CK-6 Evidence instrumentation.** Record cookie age and reason class at the moment an account goes `x_login_required` versus `x_account_suspended` so the SPEC Stage 2 trigger is answered by data (REF-X §3.5 step 1); shown in health and the daily report.
- **CK-7 Limits.** Browser time ≤ `x_harvest_timeout_s` (default 120, max 300); RSS ceiling and memory floor from BH-2; `x_cookie_harvest_enabled` false means none of this runs.
Tests: harvest success (fake Chrome returns jar, DB upserted, canary scheduled, one `ct0`), logged-out and each challenge URL stop with `x_login_required` and no second attempt, day limit across restart, never during a unit, owner-interactive polling, secret marker scan (no cookie value in logs/state/argv/env), AC1 profile isolation (two accounts two directories), AC8 inherited refusals, pool-key migration/rollback.
Done when: an expired-cookie fixture account is harvested back to service with a passing canary and an un-harvestable one is paused with the owner-action state, both visible in health. Real Chrome behaviour is probe PX6.

### S-RCore: Reddit method core ⏳ (RT3)

New `api/data/attention/reddit_core.py` (pure, no network): shared contracts all non-feed Reddit methods use.
- **RC-1 Method registry.** Method ids and stores: `reddit_archive`, `reddit_live_gql`, `reddit_live_browser` (the existing `reddit_web`, `reddit_stream` unchanged). Update `registry.SOURCE_IMPLS["reddit"]`, `PC_STORES`, `REDDIT_METHODS` consumers and `reddit_impl_order` default to `["reddit_archive","reddit_web","reddit_stream","reddit_live_gql","reddit_live_browser"]`; `pick_impl` stays "first method with enough points in the window, never mixed" (AC14/AC15). Note: the first window the archive wins is after its backfill/min-points; a series discontinuity at the method switch is shown in status, never smoothed.
- **RC-2 Evidence model.** `LaneEvidence` (per subreddit, per kind `posts|comments`: traversal reached day start/end, stop reason from a closed allowlist: `exhausted`, `cap`, `error`, `breaker`, `stale_ingest`, `bounds_violation`, `unknown`), `DaySettle` evaluator (a coin-day is writable only when every required lane is `exhausted` over the whole UTC day and the method's settle rule holds), and the shared completeness document shape (same top-level keys as `reddit_stream` completeness: `day, method, settled, coverage, canary_ok, partial, attempted, fetched, missing{reason:count}, coins{sym:{reason,value}}`, plus `lanes`, `passes`, `lag_hours`). Reason allowlist includes the existing ones plus `archive_unsettled`, `lane_incomplete`, `needs_probe`, `method_disabled`, `ingest_stalled`, `bounds_violation`, `request_cap`.
- **RC-3 Zero rule option B.** A coin-day value of 0 is stored only when (i) the method canary passed (archive: ingest freshness check on the monitored subreddits plus passed calibration; live: its lane canary), (ii) every required lane was fully traversed for the day, and (iii) the coin has history: at least `reddit_zero_min_history_days` (default 7) days with a stored positive value in ANY labelled Reddit method within the last 28 days (used ONLY as an eligibility gate, never as a value, so methods are not merged). Otherwise the coin-day is `zero_unverified` missing, never 0. This is the owner's option B of 02-11-26 applied to the new methods; applying it to the dying feed methods is parked (decision 3).
- **RC-4 Commit.** Wrapper over `web_evidence.commit_day` with the method id, first-write-wins untouched, backfilled flag for archive backfill.
- **RC-5 Known lag.** `registry._known_at_time` gains a per-method lag (`reddit_archive`: close delay in whole days) so a value collected at D+2 counts as known at D+lag, not dropped; default lag 1 unchanged for every other source (all-off equals today). Stage 0 reads `analytics/attention/discovery.py:475-498` first; if the caller semantics make a different rule correct, S-RCore reports it before changing anything.
- **RC-6 Budget helper.** Persisted per-method daily request counter and breaker (three consecutive failed units open it until UTC midnight, persisted over restart, AC34 style).
- **RC-7 Privacy.** Items reduce immediately to `{id, kind, subreddit, created_utc, author_hash, coins[]}` using the existing salted hasher; item text is never stored or logged; items whose body/author are `[deleted]`/`[removed]` follow the existing `_NO_AUTHOR` handling and are excluded from counts.
- **RC-8 Registration seam.** One small edit in `attention_pc_refresh.py`: `pc_sources()` and the worker construct a `Stream` per ENABLED non-feed method from a list owned by `reddit_core`, each with its own thread, state and budget (no change when none enabled).
Tests: `test_reddit_core.py` (lane/settle/zero-rule tables, allowlists, no-text persistence, known-lag, breaker persistence), registry tests, pick-impl never-mixes test across all five methods, guard amendments (new pure module in the pure-module list).
Done when: a synthetic method plugged into the core produces completeness documents and values that the existing Discovery reader consumes without code change (AC15, AC18).

### S-RArchive: Arctic Shift archive method ⏳ (RT3; primary Reddit method)

New: `api/data/attention/arctic_shift.py` (lazy network adapter), `reddit_archive.py` (traversal, passes, settle, commit; plugs into S-RCore), `reddit_archive_reconcile.py` (dump reconciliation CLI), tests, a loopback fake service fixture `api/tests/data/attention/arctic_fake.py`. Source semantics follow REF-R §6-§8; the research verdict stands: primary = archive, owner-gated enabling.

- **AR-1 Adapter.** Fixed host `https://arctic-shift.photon-reddit.com` (no configurable URL), endpoints `/api/posts/search` and `/api/comments/search` only, honest user agent, one-shot bounded client (B2 pattern: no redirects, no ambient proxy/CA, 30 s timeout, 8 MiB body cap), spacing ≥ `reddit_archive_page_delay_s` (default 3 s). Paging ascending by `created_utc` with explicit UTC bounds; the next page starts at the last item's `created_utc` with a 1-second overlap and de-duplication by id (IDs are non-monotonic since 2026-10-21, REF-R §2); Stage 0 reads the archive API README and records whether `after`/`before` are inclusive and the accepted formats; the fake models both semantics.
- **AR-2 Timezone calibration (REF-R O11).** Aggregate day buckets looked Europe/Berlin. The method never uses aggregates. Before each pass the adapter fetches a bounded one-hour window on a monitored subreddit and asserts every returned `created_utc` lies in `[after, before)`; a violation fails the pass with `bounds_violation` (fail closed, no guessing). Local bucketing by `created_utc` to UTC days only.
- **AR-3 Lanes and traversal.** Per eligible subreddit × kind (`posts`, `comments`): traverse the whole UTC day D; a lane is `exhausted` only when a page returns no items at or after the last cursor with the request window fully consumed, no page cap (`reddit_archive_max_pages_per_unit`) hit, and no unresolved error; a page cap, 422 or breaker leaves the lane `cap`/`error` and the day unsettled.
- **AR-4 Errors and breaker.** HTTP 422 `Timeout. Maybe slow down`, 429, 5xx and timeouts: wait `reddit_archive_backoff_s` (default 60) and retry that page once; a second failure ends the unit (`error`); three consecutive failed units open the breaker for the rest of the UTC day (persisted, AC34 style); the daily request counter (`reddit_archive_daily_request_cap`, default 1500) ends the pass `request_cap`. No retry loops, no parallel requests.
- **AR-5 Two-pass day close and settle.** Pass 1 at end(D)+`close_delay/2`, final pass at end(D)+`reddit_archive_close_delay_hours` (default 48 h, min 24). A day settles when two complete passes at least 24 h apart agree within `reddit_archive_stable_growth` (default 1%) on per-lane item counts and per-coin raw match counts; passes continue daily up to `reddit_archive_max_close_days` (default 5) and otherwise the coin-days stay missing `archive_unsettled`. Provisional pass files live under `<cache>/attention/_pc_state/reddit_archive/` and are never read by Discovery. The value is committed once at settle (first-write-wins), through S-RCore. Comments arrive late by design (median 41-65 min, tail 337 min on small samples, REF-R O8), so the final pass at 48 h sees them; the tolerance and delay are owner-tunable and calibrated by probe PR4.
- **AR-6 Ingest freshness canary.** Before each pass, the newest comment on each of `reddit_archive_monitor_subreddits` (default the first three configured) must be younger than `reddit_archive_stall_hours` (default 3 h) relative to the pass clock; otherwise `ingest_stalled`, no value, trigger recorded. This doubles as the zero-rule canary (RC-3).
- **AR-7 Counting.** Local matching with the existing `reddit_metrics` (word boundary, name-only coins, ambiguity list, author cap `reddit_author_cap`), per coin per day; per-day completeness document records both raw match counts (pre author cap) and capped counts; no server aggregates, no text stored.
- **AR-8 Backfill.** `reddit_archive_backfill_days` (default 28, 0 = off), spread over days within the request cap, rows flagged `backfilled` (excluded from point-in-time reads by the existing rule); fills the trailing history the zero rule and `pick_impl` need and covers the gap when RSS dies.
- **AR-9 Reconciliation.** `python -m api.data.attention.reddit_archive_reconcile --month YYYY-MM [--dump PATH]`: streams the owner's monthly dump (`.jsonl`, or `.zst` through a `zstd` executable on PATH; no new dependency; missing `zstd` is a reported prerequisite, never a silent skip), counts items in the configured subreddits and coin matches with the same matcher, compares with our settled per-day lane and raw-match counts, writes `reddit_archive_reconcile_<month>.json` (shortfall % per subreddit/kind and per coin, measured completeness). It NEVER rewrites stored values. Shortfall above `reddit_archive_shortfall_alarm_pct` (default 10) sets archive health `degraded` and shows the fallback-trigger text.
- **AR-10 Health and fallback triggers.** From local files only: ingest stall, lag above `reddit_archive_lag_alarm_hours` (default 6 h) two consecutive days, breaker open, request-cap days, reconcile shortfall, bounds violations. When a trigger holds, status says "archive degraded: <reason>; consider the live fallback (needs probe)". The code never auto-enables a fallback.
- **AR-11 Deletion compliance.** Counts and salted author hashes only; pass files hold no text; documented in the runbook with the Reddit rule (REF-R §4).
Tests: `test_arctic_shift.py` (paging with both bound semantics, overlap dedupe, non-monotonic IDs, bounds violation, 422/429/5xx single retry, breaker persistence, request cap, host/path allowlist, size cap), `test_reddit_archive.py` (two-pass settle table: growth within/over tolerance, late comments, max-close-days, ingest stall, lane cap, zero rule, backfill labelling, first-write-wins untouched, no text in files), `test_reddit_archive_reconcile.py` (jsonl and `zstd` runner injection, shortfall math), guard amendments in `test_reddit_collector_guards.py`: allow ONLY the two search endpoints in `arctic_shift.py`; keep the ban on reddit.com JSON endpoints and browser user-agent strings for every other Reddit module.
Done when: against the fake service a 3-day simulation commits each day once at its settle with correct labelled values and every missing reason exercised (AC15, AC14 inputs, AC18).

### S-RGQL: anonymous GraphQL live fallback ⏳ (RT3; owner-gated)

New `api/data/attention/reddit_gql.py` (surface adapter) and `reddit_live.py` (lane traversal and coverage shared with S-RBrowser), fake loopback server `reddit_gql_fake.py`. Honest scope: this surface impersonates Reddit's Android app (copied client id, persisted-query hashes, app-version headers) which Reddit's Rule 8 prohibits (REF-R §4); it worked publicly 2026-10-23..11-06 and can be closed at any time; comments exist only for threads we open (no sub-wide comment stream, REF-R §3).
- **GQ-1 Gate.** Runs only if `reddit_live_method == gql_anon` AND a probe record for PR1 exists, is younger than `reddit_live_probe_max_age_days` (default 7), passed, and its recorded `ops_sha256` equals the current ops file; otherwise state `needs_probe` (status + doctor), nothing sent.
- **GQ-2 Versioned operations file.** Persisted-query hashes, client id and header set are DATA in an owner-editable private JSON (`reddit_live_ops_path`), schema-validated (exact keys, bounds), never hard-coded in the repo and never containing a secret. Stage 0 reads the public Redlib fork sources (`gql.rs`, REF-R §11) to capture request and response SHAPES into a short REF and into the fake server; the ops file shipped as `deploy/examples/reddit_gql_ops.example.json` carries documented placeholders that the doctor reports as "not populated", because the real hashes drift per app release and must come from the owner's PR1 evidence. A hash the server rejects sets `ops_stale` (owner action), never a retry storm.
- **GQ-3 Lanes.** Posts lane: traverse each eligible subreddit's `new` feed by cursor back to the UTC day start (stable `t3_` ids, absolute timestamps, full text). Comments lane: open threads that are new or have new comments inside the day (cursor paging within a thread, depth and per-request bounds from the ops file); coverage = share of known active threads opened this day; threads on old posts that never reappear in the posts feed are the declared limitation, labelled `comments_scope: threads_opened`. A coin-day value needs posts lane `exhausted` and comments coverage ≥ `reddit_live_min_thread_coverage` (default 0.8) per S-RCore; otherwise missing `lane_incomplete`.
- **GQ-4 Budget.** Hard `reddit_live_daily_request_cap` (default 600, the reported per-token budget), per-token budget tracked, spacing from config, one pass at a time, breaker as RC-6.
- **GQ-5 Identity.** App-only token, no account; honest about it in the label `reddit_live_gql`; token and any header value never logged or persisted beyond memory.
Tests: fake server with cursors, thread comments, rejected hash, block page, empty shell (HTTP 200 with no data = failure, not zero), token budget, no-probe refusal, stale-probe refusal, ops file hash binding, request cap, traversal stop reasons, no text persistence, guard exemption limited to `reddit_gql.py` and reasoned in the test.
Done when: the fixture flow commits only labelled `reddit_live_gql` values under the gate and refuses without it.

### S-RBrowser: logged-in Chrome live fallback ⏳ (RT4; owner-gated)

New `api/data/attention/reddit_browser.py`; uses S-Browser (`reddit_read` role) and `reddit_live.py` lanes. At most `reddit_browser_accounts` (≤ 2) owner-created throwaway Reddit accounts, each with its own profile, its own admitted route (B2 resolver; account labels in the assignment file), a one-week rest and ready mark (same gates as X accounts), never the owner's main account.
- **BR-1 Gate.** `reddit_live_method == browser` AND a fresh passed PR2 probe record (same age rule as GQ-1) AND the profile is logged in (read-only URL check, no credential typing, same stop-at-challenge rule as CK-1).
- **BR-2 Read mechanism.** Navigate `https://www.reddit.com/r/<sub>/new/` and thread pages in the account profile; capture the page's OWN network responses through CDP (`Network.responseReceived`/`getResponseBody`) and parse the JSON bodies; never parse a virtualized DOM (REF-R §3: short DOM is not exhaustion). Scrolling uses the bounded scroll expression of the allowlist. Traversal evidence is the observed cursor chain to the day start; DOM-only evidence is not accepted.
- **BR-3 Budget and lifecycle.** Navigation cap `reddit_live_daily_request_cap`, ≤ 20 browser minutes/day, one browser machine-wide (shared lock with X harvest), memory floor and RSS ceiling from S-Browser, serialized after any pending X harvest.
- **BR-4 Honesty.** Label `reddit_live_browser`; same lanes and coverage rules as GQ-3 (comments on old posts are the declared limitation); never merged with other methods.
Tests: fake CDP Reddit pages serving canned response bodies (synthetic), gate refusals, logged-out stop, cursor-chain traversal and stop reasons, allowlist enforcement, memory/lock sharing with harvest, secret markers.
Done when: fixture flow commits `reddit_live_browser` values under the gate; PR2 is the only evidence that the real site behaves this way.

### S-Report: AC14 daily report ⏳ (RT3)

New pure `api/analytics/attention/daily_report.py` and `api/scripts/attention_daily_report.py`; hook at UTC rollover in `attention_pc_refresh.py` (writes only, file-only, no network).
- **RP-1 Content** per source and per method for the report day D (default yesterday UTC): eligible (stored + missing), stored, exact (stored − capped), estimated (capped), missing with a reason histogram and the per-coin list, plus per-account X facts (reads, cap, handoffs, quarantines, cookie age, harvest state), Reddit method facts (lanes, passes, lag, request count, breaker), query-id state, and the trigger signals the SPEC Build Order asks the status box to record (challenges, shrinking results, cookie age, limits hit, proxy health). Reddit methods are listed separately and the method Discovery would pick is marked; they are never summed.
- **RP-2 Rules (AC14).** `missing` is never rendered as zero; `100% stored` is printed only when eligible == stored and eligible > 0; unknown evidence prints `unknown`; an absent completeness document yields "no data for D", not 0 of 0.
- **RP-3 Artifacts.** `<cache>/attention/_reports/daily_report_<D>.json` (schema-versioned) and a plain-text rendering `daily_report_<D>.txt`; written once per day idempotently, rewritten only to add late-settled Reddit days (archive days settle 2 days later; the report for D is updated when D settles and says when).
- **RP-4 CLI.** `python -m api.scripts.attention_daily_report [--day D] [--print]` (reads files only).
Tests: `test_daily_report.py` (full, partial, all-missing, unknown, capped/exact/estimated arithmetic, 100% only when all stored, method separation, late-settle update), CLI tests.
Done when: the E2E produces the report for the simulated day with every field exercised.

### S-Status: status contract, API and UI ⏳ (RT3 + RT1)

Owns the status stack (see ownership matrix). Implements the field contract in Public Contracts: `sources[xsearch].health.accounts[]` additions (endpoint state, behaviour block, harvest block, ct0 rotation count), `sources[xsearch].health.queryids`, `sources[reddit].health.methods[]`, `collector.daily_report` summary, doctor summary (read from `<cache>/attention/_reports/doctor.json`). Python and TypeScript fields optional; absent → "unknown", never healthy or zero; reasons are allowlisted; no private paths, IPs, URLs, cookies or credentials; API reads files only (no network, no writes, no admission). Web: formatter (`source-health.ts`), `CollectorStatus.tsx` (new lines/rows wrap at 375 px), `DiscoverySourcesPanel.tsx`.
Tests: `test_sources*.py`, `test_discovery.py` exact-key contract updated deliberately, `source-health.test.ts`, component tests, and a seeded real-server Playwright spec at 375/768/1280 (extend `collector_status_e2e.py`; real seeded backend state, not intercepted responses) covering every new state, missing/legacy fields, unknown text, secret absence and no horizontal overflow. Known Windows-host failures are judged by Linux CI (all-tests.md).
Done when: every new health field renders from a real seeded API response at three viewports.

### S-Ops: runbook, probes, doctor, scheduled tasks ⏳ (RT4)

Owns `deploy/*` and the two scripts. Nothing here starts, restarts or probes anything live by itself.
- **OP-1 Runbook** (`deploy/README.md`, plus `deploy/examples/*.example.json|psd1` with synthetic values and an `INPUTS` checklist): the owner-inputs table above with exact file names and formats (queries collector block with all new keys, private proxy list/assignments/policy from the B2 section, profile root, browser path, accounts), enabling order (1 accounts+rest, 2 routes, 3 archive, 4 report, 5 query-id `sentinel` then `auto`, 6 harvest, 7 B3 one measure at a time with the trial report, 8 live Reddit fallbacks only on a trigger), rollback per slice (the cumulative key-strip list), restart and update rules, the Reddit date calendar (13-11-26, 12-01-27, March 2027) and the fallback triggers, deletion-compliance note.
- **OP-2 Probe suite** `python -m api.scripts.probe_owner <probe-id> [--approve <probe-id>]`, one probe at a time, each with a printed exact request list and budget in dry-run (default; nothing sent), a `--approve` execution that enforces the budget, stops on challenge/429/block, redacts, and writes a nonsecret record `<cache>/attention/_probes/<id>_<date>.json` (`{probe_id, date, commit, egress_class, outcome, summary, ops_sha256?}`) that the gates read:

| Probe | Purpose (evidence it produces) | Max requests / limits |
|---|---|---|
| PX1 queryid-sentinel | Compare pinned vs public-bundle operation IDs; no account | ≤ 6 static GETs |
| PX2 queryid-live | Does the old pinned ID still answer; does the bundle ID answer (one account) | ≤ 4 reads on one healthy account |
| PX3 account-capability | One known-good query per account plus `UserByScreenName` (per-account 404 check; actual `x-rate-limit-limit`) | ≤ 2 per account |
| PX4 ct0 | Does `Set-Cookie: ct0` appear; does a stored old `ct0` still work in a fresh process | ≤ 3 on one account |
| PX5 x-compare | The B1 V7 real-account transport comparison protocol (plain vs curl; matched queries/windows; order counterbalanced; budgets; stop on challenge; setup counted); result writes the default-decision record (AC11, AC20) | per protocol, own approval |
| PX6 harvest-real | One real-Chrome harvest on one account: final-URL class, cookie names present (no values), RSS peak, flags accepted, proxy auth path | 1 launch, ≤ 180 s |
| PR1 gql-anon | REF-R P1: token mint, `new` feed per subreddit to previous day start, `PostComments`, search, 48 h repeat and post-13-11 repeat; records `ops_sha256` | ≤ 120 requests/run |
| PR2 browser-reddit | REF-R P2: one owner account, scroll to day start, thread open, network call inventory, relaunch identity | ≤ 15 navigations |
| PR3 cookie-http | REF-R P3: which cookie-HTTP surfaces answer (informational; no method is built on it) | ≤ 20 |
| PR4 archive | REF-R P4: bounds/timezone, lag over 48 h, two-pass growth, page counts per subreddit/day, 422 rate; produces recommended `close_delay`/tolerance | ≤ 400 requests/run, spaced |
| PR5 proxy-exit | Exit class check for a candidate proxy against PR1/PR4 requests | ≤ 10 |
| PR6 durability | 7-day read-only durability summary from local files (challenges, 429s, forced re-logins) for a disposable account/IP | 0 requests (analysis) |

- **OP-3 Doctor** `python -m api.scripts.collector_doctor [--json] [--live] [--selftest]` and `deploy/doctor.ps1` wrapper; exit 0 all PASS, 1 any WARN, 2 any FAIL; every check returns PASS/WARN/FAIL/UNKNOWN with a reason and a fix hint, never a secret. Offline by default (`--live` adds only the bounded read-only checks the owner approves). Checks: queries config strict validation and enabled-feature consistency; uv/env guards; pin and curl verification (existing); accounts and sizing shortfall (existing capacity) plus the SPEC arithmetic (about 4, worst 6 accounts); rest/ready; cookie ages and harvest state; proxy files/policy/assignments, private-root ACL (Windows), admission freshness, quarantines; query-id state and `x_backfill_days > 7` warning; browser path/version, profile root ACL and uniqueness, free memory vs floor; disk space on the cache root; archive health and fallback triggers; reconcile state; probe records present/fresh/failed; Reddit date calendar; scheduled tasks registered and their state; collector heartbeat age; last daily report completeness; Stage 3 trigger measurement (routes needed vs list capacity, route formats) printed with "gateway not built: trigger not met/met"; `--selftest` runs the E2E acceptance (below). Writes `<cache>/attention/_reports/doctor.json` for the status box. Pure check functions are unit-tested with injected readers.
- **OP-4 Scheduled tasks** `deploy/register-collector-tasks.ps1 [-Remove]` (idempotent, current user, no elevation, mirrors the README snippet and `register-tasks.ps1` conventions): `mysite-collector` (at logon, restart 3×/1 min, `MultipleInstances IgnoreNew`), `mysite-collector-doctor` (daily, writes the report json), `mysite-archive-reconcile` (daily trigger, the script self-gates to "due" after the 13th and exits 0 with state `waiting_for_dump` when no dump is present; `New-ScheduledTaskTrigger` has no monthly mode). `start-collector.ps1` gains `-Doctor` pre-flight. Shape tests only (`api/tests/deploy/test_deploy_collector_shape.py` pattern): PowerShell was not available to write these; every script carries the existing "UNRUN" note until the owner's first run records the result.
- **OP-5 Stage 3 guard.** A tiny guard test asserts no gateway key, module or setting exists and the collector needs none (AC16 by absence), so any future gateway work must update the guard deliberately.
Tests: doctor unit tests per check (fixtures for each state), probe dry-run output and budget-enforcement tests against loopback fakes, shape tests for ps1/psd1, README section assertions (key names in README exist in `web_queries`), no-secret scan over generated records.
Done when: on the E2E's synthetic cache the doctor returns expected states; on an empty owner environment it lists every missing input; every probe dry-run prints its exact plan.

### S-E2E: the one end-to-end acceptance ⏳ (RT4) — see next section

### G-FINAL: closeout ⏳

Evidence pack per `vc-risk-evidence-pack` (RT4), consolidated Main run, owner acceptance of the status box and the doctor, record of which live probes the owner has and has not run, UPDATE-PROCESS (`process/context` current-state and data-sources notes, context changelog), then the owner decides archiving the task folder to `completed/`. Honest status vocabulary: fixture-proven features are "CODE DONE, fixture-proven"; "VERIFIED" only per Phase Completion Rule 5.

## The one end-to-end acceptance

One command (Main or the owner; the doctor's `--selftest` calls it):

```
UV_FROZEN=1 uv run --project api --frozen --group xreader python -m api.tests.cycle.acceptance [--ui]
```

It runs the pytest module `api/tests/cycle/test_daily_cycle.py` (also collected by a normal `pytest api/` run), writes `cycle_report.json` (scenario → observed result, no secrets) and exits 0 only if every scenario passes with zero skips. `--ui` additionally starts the real FastAPI app against the cycle's cache and runs `web/e2e/collector-cycle.spec.ts` at 375/768/1280. No live network: only loopback sockets with the test-only host mapping and ephemeral OpenSSL-signed trust roots already used by `api/tests/data/attention/proxy_wire_fixture.py` (B2 precedent; no production fixture switch, no bypass). Virtual clock and virtual wait are injected into `AttentionPcWorker` (existing `clock`/wait parameters), so three UTC days run in minutes of real time while TLS, sockets, SQLite, the child process and files are real. Budget: ≤ 180 s, ≤ 1 GiB, one heavy run at a time.

Synthetic world (all names and cookies are obviously synthetic markers):
- Universe: 14 X-eligible coins (2 on the X ambiguity list), 10 Reddit-eligible coins, 4 subreddits; 5 synthetic X accounts `acc_a..acc_e` with per-account proxy routes through a fake CONNECT proxy and assignments/policy files built by the B2 test helpers; `acc_e` added to an existing state so it rests.
- Fake X over loopback TLS (hosts mapped: `x.com` page + signing script for bootstrap, GraphQL `SearchTimeline` with per-cookie behaviour, a static asset origin for the query-id sentinel): server-side query ID that rotates mid-day; `acc_b` answers 404 for SearchTimeline regardless of ID; `acc_c` answers `(64)` after N reads; `acc_a`'s session expires (login redirect) mid-day; rate-limit headers; duplicate-`ct0` detection on every request.
- Fake Chrome (S-Browser fixture) with a jar for `acc_a` after "owner login" state, and a logged-out profile for another account.
- Fake Arctic Shift over loopback TLS: posts near real time, comments with sweep lag and late back-fill, both bound semantics selectable, a `bounds_violation` toggle, HTTP 422 injection, ingest-stall toggle; deterministic content with known per-coin mention counts. Fake monthly dump (`.jsonl`) for reconciliation.
- Fake gql-fed server and a synthetic recorded probe record for the owner-gated fallback sub-scenario.

Timeline and assertions (each is a named scenario in `cycle_report.json`):

| Step | Simulated event | Must be observed |
|---|---|---|
| C1 | Day 1 start, all optional measures off (baseline) | Behaviour equals Part A all-off baseline (AC12/AC18); canary passes; units spread; global ceiling respected |
| C2 | `acc_a` reaches its per-account cap | Skipped with `account_cap`; next coin-day goes to the next account; no coin-day split; total ≤ global ceiling (AC4) |
| C3 | Server rotates the SearchTimeline ID | 404s after isolation → candidate from the fake bundle → canary on candidate passes → adopted; NO `DRIFT_STOP` pause; child `query_id` carries it (XH-2/3) |
| C4 | `acc_b` 404s on a valid ID | Second account succeeds on the same unit; `acc_b` locked `endpoint_404`; drift streak unchanged; coin-day counted once (XH-4, AC6) |
| C5 | `acc_c` returns `(64)` | Deactivated `x_account_suspended`; its in-flight coin-day read by another account once; no double count (XH-5, AC6) |
| C6 | `acc_a` cookie expires | `x_login_required` pause → harvest with fake Chrome → single `ct0` on the wire → canary → back in service; second harvest same day refused; logged-out account stops with `needs_owner` and no retry (S-Cookie, AC2, AC3) |
| C7 | `acc_e` rest and ready | Unused until rest and ready mark; joins the next UTC day's canary (AC7) |
| C8 | Proxy of one account quarantined | Replacement admitted per B2; no direct connection ever observed on the fake (loopback egress log) (AC9) |
| C9 | Day 2 with all five B3 measures on (second run, one switch at a time and all together) | Quiet deferral, mixed calls only on the allowlist with charges, bounded variation, cooldown handoff, warm-up ladder; health per measure; benefit report runs; coin values never written by mixed calls (AC12) |
| C10 | Reddit archive days D1..D3 | Day D1 pass 1 provisional only; final pass at +48 h commits once; late comments raise the second pass within tolerance; 422 handled once then recovered; `ingest_stalled` and `bounds_violation` days commit nothing and show missing reasons; zero stored only under option B; first-write-wins intact; reconcile report measures shortfall against the fake dump (AC15) |
| C11 | Archive stalled for 2 days | Health `degraded`, fallback-trigger text; live fallbacks refuse without a probe record (`needs_probe`); with the synthetic fresh record and switch the fake gql method runs and is labelled `reddit_live_gql`, never merged (AC15) |
| C12 | Day close | `daily_report_<D>.json/txt` exist; eligible/stored/exact/estimated/missing add up; missing never zero; 100% only when all stored; late-settled Reddit day updates the earlier report (AC14) |
| C13 | Status and doctor | Real `/api/narrative/sources` reflects every state above with `unknown` for absent data; `collector_doctor --json` returns the expected PASS/WARN/FAIL for the synthetic world; `--ui` screenshots at 375/768/1280 without overflow (AC13) |
| C14 | Secrets | Marker scan over repo, cache, logs, state, reports, child argv/env/output, status JSON finds no cookie, token, proxy credential or key (AC17) |
| C15 | Regression | Existing collector suites unchanged and green (AC18) |

Doing the E2E proves the system's logic and wiring on synthetic services. It does NOT prove: real X or Reddit behaviour, real Chrome behaviour, real route quality or Windows deployment ACLs, ban avoidance. Those are the owner probes and the B2 release gate, recorded in G-FINAL.

## Public Contracts

### Configuration (collector block of the owner query file; all optional; defaults shown; validation in S-Config)

| Group | Key: default | Rule |
|---|---|---|
| X query IDs | `x_queryid_mode`: `off` (`off|sentinel|auto`); `x_queryid_static_budget_per_day`: 6 (1-12) | off = pinned only, zero fetches |
| X harvest | `x_cookie_harvest_enabled`: false; `x_browser_path`: null (absolute); `x_browser_profiles_dir`: null (absolute, private root); `x_account_profiles`: {} (label → profile dir name `[a-z0-9_]{1,24}`, unique); `x_cookie_refresh_age_days`: null (int ≥ 1); `x_harvest_timeout_s`: 120 (30-300); `browser_memory_floor_mb`: 1536 (≥ 512); `browser_rss_ceiling_mb`: 1200 (≥ 400) | enabled requires path, dir and a profile per harvest account |
| X B3 | `x_quiet_hours_enabled`, `x_mixed_traffic_enabled`, `x_variation_enabled`, `x_adaptive_cooldown_enabled`, `x_warmup_enabled`: false; `x_account_quiet_hours`: {}; `x_mixed_targets`: [] | per the B3 contract in the 02-11-26 PLAN |
| Reddit archive | `reddit_archive_enabled`: false; `reddit_archive_close_delay_hours`: 48 (24-96); `reddit_archive_stable_growth`: 0.01 (0-0.2); `reddit_archive_max_close_days`: 5 (2-14); `reddit_archive_page_delay_s`: 3 (≥ 1); `reddit_archive_backoff_s`: 60 (≥ 10); `reddit_archive_daily_request_cap`: 1500 (≥ 50); `reddit_archive_max_pages_per_unit`: 150 (≥ 5); `reddit_archive_backfill_days`: 28 (0-60); `reddit_archive_monitor_subreddits`: first 3 configured; `reddit_archive_stall_hours`: 3; `reddit_archive_lag_alarm_hours`: 6; `reddit_archive_shortfall_alarm_pct`: 10; `reddit_archive_dump_dir`: null (absolute) | |
| Reddit shared | `reddit_zero_min_history_days`: 7 (≥ 1); `reddit_impl_order`: archive, web, stream, live_gql, live_browser (default changed) | |
| Reddit live | `reddit_live_method`: `off` (`off|gql_anon|browser`); `reddit_live_probe_max_age_days`: 7; `reddit_live_daily_request_cap`: 600; `reddit_live_min_thread_coverage`: 0.8; `reddit_live_ops_path`: null (absolute); `reddit_browser_accounts`: [] (≤ 2 of `{label, profile, proxy_id?}`) | method ≠ off requires its gate inputs |

### Files and state (nonsecret unless stated; all under the cache root except private files)

`<cache>/attention/_pc_state/x_queryids.json`; `.../browser.lock`; `.../reddit_archive/<day>.pass<n>.json.gz` and `settled/<day>.json`; per-method request counters/breakers; `<cache>/attention/_reports/daily_report_<D>.json|txt`, `doctor.json`, `reddit_archive_reconcile_<month>.json`; `<cache>/attention/_probes/<id>_<date>.json`. Private (outside repo, verified-private ACL on Windows): browser profiles, B2 private files, the owner query file, `reddit_live_ops_path`.

### Pool state keys added by this plan (exact-key; each slice migrates with `setdefault` BEFORE the exact-key check and strips on rollback)

S-XHard: `endpoint_404_day` (ISO date|null), `endpoint_404_count` (int ≥ 0). S-B3: `warmup_start_day`, `behaviour_cooldown_until`, `behaviour_reason`, `shrink_run`, `result_history`, `mixed_day`, `mixed_calls`. S-Cookie: `harvest_day` (ISO|null), `harvest_state` (`none|ok|needs_owner|refused|failed`), `harvest_reason` (allowlisted code|null). Cumulative rollback strip list (collector stopped, backed up): these 12 keys, on top of the existing Part A (3) and B2 (7 + `proxy_provider_budget`) lists.

### Child protocol (security-relevant)

`query_id` added to the attested work envelope with framing domain `collector-b2-child-v2` (XH-3); everything else in the B2 envelope, limits and replay/stale-reply rules is unchanged.

### Health fields (S-Status; optional, allowlisted, unknown explicit)

`health.accounts[]`: `endpoint_state` (`ok|restricted|unknown`), `behaviour{quiet_until, cooldown_until, cooldown_reason, warmup_stage, effective_cap, mixed_calls_today}`, `harvest{state, reason, last_at}`, `ct0_rotations_seen`. `health.queryids{mode, state(ok|candidate|stale|unknown|blocked|refused_by_policy), active_source, active_age_days, last_check}`. `sources[reddit].health.methods[]{method, label, state(ok|degraded|needs_probe|disabled|blocked|unknown), reason, last_settled_day, lanes, lag_hours, requests_today, cap}`. `collector.daily_report{day, per_source_method{eligible, stored, exact, estimated, missing, reasons}, complete(bool|null)}`. `collector.doctor{state, checked_at, failures, warnings}`. No expected IPs, URLs, cookies, tokens, private paths, usernames.

### New CLIs

`--harvest-cookies LABEL [--interactive]` (reader module), `python -m api.data.attention.x_behaviour_report`, `python -m api.data.attention.reddit_archive_reconcile`, `python -m api.scripts.attention_daily_report`, `python -m api.scripts.collector_doctor`, `python -m api.scripts.probe_owner`, `python -m api.tests.cycle.acceptance`, `deploy/register-collector-tasks.ps1`, `deploy/doctor.ps1`. No new HTTP route, no new dependency.

## Touchpoints

Existing (read or edited per the ownership matrix): `api/data/attention/{x_pool,x_reader,twscrape_reader,web_queries,registry,x_proxy_curl,x_proxy_child,x_proxy_snapshot,x_proxy_private,x_proxy_runtime}.py`, `api/data/attention_pc_refresh.py`, `api/data/attention_collector.py` (read), `api/analytics/attention/sources.py`, `api/models/discovery.py`, `api/scripts/probe_pc_sources.py` (read, coexists with `probe_owner.py`), `web/lib/types/discovery.ts`, `web/lib/source-health.ts`, `web/components/narrative/CollectorStatus.tsx`, `DiscoverySourcesPanel.tsx`, `web/e2e/collector-status.spec.ts`, `deploy/README.md`, `deploy/start-collector.ps1`, `deploy/config.example.psd1`, `deploy/register-tasks.ps1` (pattern), canonical collector SPEC, tests named per slice and the three guard files.
New: `x_queryids.py`, `x_queryids_fetch.py`, `x_quiet.py`, `x_behaviour.py`, `x_behaviour_report.py`, `browser_host.py`, `browser_cdp.py`, `x_harvest.py`, `reddit_core.py`, `arctic_shift.py`, `reddit_archive.py`, `reddit_archive_reconcile.py`, `reddit_gql.py`, `reddit_live.py`, `reddit_browser.py` (all under `api/data/attention/`), `api/analytics/attention/daily_report.py`, `api/scripts/{attention_daily_report,collector_doctor,probe_owner}.py`, `api/tests/cycle/`, `web/e2e/collector-cycle.spec.ts`, `deploy/{register-collector-tasks,doctor}.ps1`, `deploy/examples/`.
Do not touch: `.github/` (none expected), dependency files, `api/data/attention_queries.json` (committed defaults), discovery scoring, other sessions' PR-owned files, the live cache, the live collector, the owner's main-folder edits.

## Blast Radius

Package scope: `api/data/attention/*` (X reader, pool, Reddit methods, browser host), `api/analytics`, `api/models`, `api/scripts`, `web` status UI, `deploy`. Roughly 15 new modules, 10 edited modules, 3 guard files, 12-20 test files, one protocol change (child envelope v2). Risk class RT3 for logic, RT4 for secrets/runtime/deploy slices (S-XHard, S-Browser, S-Cookie, S-RBrowser, S-Ops, S-E2E). Failure modes with most damage: stopping X incorrectly (drift/404 logic), double-counting reads or coin-days (accounting), a silent direct connection (route), a secret in a log/state/argv, a fabricated zero (Reddit rules), a browser left running on an 8 GiB host. Mitigations: default-off switches, all-off baseline tests, fail-closed reasons, marker scans, fixed budgets, and the single consolidated verification.

## Budgets

| Budget | Value | Enforced by |
|---|---|---|
| X reads | global `x_daily_post_budget` (default 800) and per-account `x_account_daily_cap` (owner sets; SPEC proposal 800) remain ceilings; B3 ordinary calls ≤ 3/account/day and 20 read units reserved per call | existing + S-B3 |
| Query-id static GETs | ≤ 6/day, 4 MiB each, 10 s each | S-XHard |
| Browser | 1 process machine-wide; ≤ 180 s per harvest (max 300); free memory ≥ 1536 MB to launch; RSS ≤ 1200 MB; Reddit browser ≤ 20 min/day | S-Browser |
| Archive | ≤ 1500 requests/day, ≥ 3 s spacing, ≤ 150 pages per lane-pass, one retry per page, breaker after 3 failed units; estimated need ≈ 400 requests per pass-day (INFERENCE from 1,115 comments/12 pages on r/Bitcoin, larger subs unmeasured; PR4 measures) | S-RArchive |
| Live GQL | ≤ 600 requests/day (reported per-token budget) | S-RGQL |
| Probes | per the probe table, one at a time, approval required | S-Ops |
| E2E | ≤ 180 s, ≤ 1 GiB, zero skips | S-E2E |
| Engineering | per-slice size S/M/L above; split past about 12 non-test files or 1,500 diff lines; one heavy test run at a time; subagents never run builds or suites mid-flight; Main verifies once after landing | Orchestration |

## Verification Evidence

| Gate / Scenario | Strategy | Proves SPEC criterion |
|---|---|---|
| B2 committed, CI green on final head (known unrelated failure recorded) | Hybrid (CI judge for Linux, no Windows ACL claim) | AC9, AC10, AC17, AC19, AC20 (existing) |
| Config keys validate, defaults off, old file loads, all-off baseline | Fully-Automated | AC12, AC16, AC18 |
| Query-id registry/sentinel/adoption, off-mode no fetch, child `query_id` v2 | Fully-Automated | AC18, AC19, AC17 |
| 404 isolation (1/2/3 accounts), code 64 deactivation and failover, no double count | Fully-Automated | AC3, AC6, AC18 |
| Single `ct0` and `.x.com` scope on the wire, both backends, after refresh | Fully-Automated | AC2, AC19 |
| Quiet/mixed/variation/cooldown/warm-up switches, health, all-off baseline, migrations | Fully-Automated | AC12, AC4, AC6, AC7, AC13, AC18 |
| Per-measure benefit/removal decision from a real trial | Agent-Probe (owner-approved bounded trial; analyzer proven on synthetic history) | AC12 |
| Browser host: single instance, memory floor, RSS kill, argv/allowlist/no-input, route binding, ACL, no orphan | Fully-Automated | AC1, AC8, AC17 |
| Harvest success/stop/limits/never-types-credentials/secret scan/profile isolation | Fully-Automated | AC1, AC2, AC3, AC8, AC17 |
| Real Chrome harvest, RSS, flags, proxy auth (PX6) | Agent-Probe (justified: needs the owner's Chrome, account and route) | AC1, AC2, AC8 |
| Reddit core: lanes, settle, zero rule B, no merge, known lag, no-text persistence | Fully-Automated | AC15, AC18 |
| Archive adapter and two-pass settle on the fake service (bounds, 422, breaker, caps, late comments, reconcile) | Fully-Automated | AC15, AC14, AC18 |
| Real Arctic Shift behaviour: bounds/tz, lag, growth, page counts (PR4) | Agent-Probe (justified: live third-party service) | AC15 |
| GraphQL/browser live fallbacks: gate refusals, lanes, caps, honest labels, on fixtures | Fully-Automated | AC15, AC17, AC8 |
| Real Reddit surfaces (PR1, PR2, PR3, PR5) | Agent-Probe (owner-gated live) | AC15 |
| Daily report arithmetic, missing-not-zero, 100% rule, method separation, late update | Fully-Automated | AC14 |
| Status/API/UI fields, unknown-never-ok, no secrets, 375/768/1280 on a real seeded server | Fully-Automated (bounded, memory permitting) | AC13, AC14, AC12 |
| Doctor checks, probe dry-runs and budgets, ps1 shape, README keys exist in code, gateway-absent guard | Fully-Automated | AC11, AC16, AC17, AC20 |
| Real two-account transport comparison (PX5) | Agent-Probe (separate owner approval) | AC11, AC20 |
| End-to-end daily cycle C1-C15 on synthetic services | Fully-Automated | AC1-AC20 integration (AC9-AC11, AC19-AC20 live parts excluded) |
| Existing collector suites unchanged | Fully-Automated | AC18 |

SPEC AC coverage map: AC1 S-Browser/S-Cookie/E2E; AC2 S-Cookie/S-XHard; AC3 S-Cookie/S-XHard; AC4 existing + S-B3; AC5 existing + S-Ops doctor; AC6 existing + S-XHard/S-B3; AC7 existing + S-B3; AC8 S-Browser; AC9/AC10 B2 (existing) + S-E2E C8; AC11 S-Ops PX5; AC12 S-B3/S-XHard/S-Config; AC13 S-Status; AC14 S-Report; AC15 S-RCore/S-RArchive/S-RGQL/S-RBrowser; AC16 S-Ops guard; AC17 every slice + S-E2E C14; AC18 every slice + S-E2E C15; AC19/AC20 B1 (existing) + S-XHard + PX5.

Commands (Main runs once after landing; the plan does not run them): per slice the focused files with the stem in "Slice specifications", then once `UV_FROZEN=1 uv run --project api --frozen --group xreader pytest api/ -q -rs`; in `web/`: `pnpm exec vitest run <touched>`, `pnpm test`, `pnpm exec tsc --noEmit --incremental false`, `pnpm build:islands`; then the E2E command above with `--ui`; seeded Playwright at 375/768/1280 per `collector-status.spec.ts` conventions (`D18_E2E=1` changes the backend harness on a constrained host). Known Windows-host failures (about 40 router tests, `test_universe_classes` end-to-end, `plot-ink.test.ts`, the baseline equities path-separator test) are judged by Linux CI and are not re-run merely to confirm them. Read `process/context/tests/all-tests.md` and `operating-instructions.md` before finalizing commands (VALIDATE binds exact paths).

## Implementation Checklist

Per-slice checklists are in each specification; the program-level order is:

- [ ] S-Land: owner approves; commit B2; draft PR; CI green on final head; record the unrelated failure.
- [ ] S-Canon: append dated superseding notes (archive search endpoints, Reddit methods and zero rule B, browser decision, B3 exceptions, query-id fetch).
- [ ] S-Config: all keys, validation, all-defaults baseline test.
- [ ] S-XHard: red tests → registry/sentinel/adoption, 404 isolation, code 64, cookie jar, child envelope v2, guards.
- [ ] S-Browser: red tests → host, CDP allowlist, fake browser, guard file.
- [ ] S-RCore: red tests → core contracts, registry, known lag, registration seam.
- [ ] S-Status: contract fields in API and UI against fixtures (can run beside the backend slices).
- [ ] S-B3: five measures with switches, health, analyzer.
- [ ] S-Cookie: harvest procedure, interactive helper, triggers, instrumentation.
- [ ] S-RArchive: adapter, traversal, two-pass settle, backfill, reconcile, health.
- [ ] S-RGQL and S-RBrowser: gated live fallbacks with honest labels.
- [ ] S-Report: daily report builder, files, CLI, rollover hook.
- [ ] S-Status finish; S-Ops: runbook, examples, probes, doctor, scheduled tasks, shape tests.
- [ ] S-E2E: fixtures, scenarios C1-C15, driver, UI spec.
- [ ] One consolidated Main verification; evidence pack; owner acceptance; closeout.

## Risks and Mitigations

| Risk | Mitigation |
|---|---|
| Arctic Shift is a single-maintainer volunteer service with no SLA; reuse of scraped Reddit data is a grey area; post-March-2027 future unknown; Reddit pressures dump hosting (REF-R §6) | Owner decision 1; method labelled and separate; health triggers; two owner-gated live fallbacks; reconciliation measures real completeness; counts-only storage |
| Archive values land at D+2: Discovery's newest Reddit point is two days old; the day-close tolerance may be mis-tuned | Stated in status and runbook; delay and tolerance are config; PR4 measures; known-lag keeps point-in-time exact |
| Query-id auto adoption picks a wrong ID | Canary gate, 24 h rejection memory, mode `off` default, pause path unchanged, probe PX2 |
| 404 isolation hides real drift | Only delays the decision by one second-opinion attempt; both 404 = drift; single-account unchanged |
| Harvest on real Chrome behaves differently from the fake (flags, proxy auth, page states) | Fails closed to `needs_owner`; PX6 probe before enabling; allowlisted read-only CDP; one harvest/account/day |
| Real Chrome RSS and Windows process-tree kill unverified on 8 GiB | Memory floor and RSS ceiling kill; PX6 records RSS; one browser only |
| Live Reddit adapters cannot be validated without the owner; surfaces perishable (REF-R §3, §5 evidence conflicts) | Default off; probe-record gate with `ops_sha256` binding; honest labels; code proven on fixtures only and reported as such |
| Guards (evasion vocabulary, AC28 fixed hour, network-import lists, archive ID-only rule) conflict with new modules | Reasoned, narrow, per-module amendments listed in each slice; the rest of every guard unchanged |
| Shared-file collisions | Ownership matrix, chains, config-first, status-last, files ≤ 40-line seam edits |
| Child envelope change (v2) weakens attestation | Security re-read at VALIDATE; tamper/absent/malformed/v1 tests; HMAC framing otherwise unchanged |
| B3 measures harm coverage or show no benefit (no evidence, REF-X §4.3) | Default off; one at a time; offline report with inconclusive default; removal rule |
| Owner never supplies proxies/accounts | Doctor and status say so; direct/off remains an explicit mode; missing is reported as shortfall/missing, never zero |
| All accounts lost | Defined state (missing + owner action), report shows it; no retry storm |
| E2E fixture realism (fake X cannot prove real X) | Scoped claims in the plan; probes are the live evidence |
| Linux CI cannot prove Windows ACL, Chrome or Task Scheduler | Windows paths covered by B2's native-temp tests, shape tests and owner first-run recording |
| twscrape pin drift (no upgrade) | Compatibility assertions at startup refuse on hook change; query-id sentinel; research says nothing at HEAD is required |

## Decisions that need the owner

Genuinely owner-only (no default can substitute):

1. **Reddit primary route reversal.** The 02-11-26 owner decision chose the identity/evasion route for Reddit. Research says that route is the most dangerous and least proven; the only free, live, sub-wide source needing no Reddit identity from us is Arctic Shift (unofficial third-party archive, volunteer, no SLA, legal grey area, may end March 2027). Confirm Arctic Shift as the primary Reddit method (switch `reddit_archive_enabled` stays off until you flip it). If you decline, the plan's live fallbacks become primary and carry the account/Rule 8 risk.
2. **Stage 3 V2Ray gateway.** Parked by its own SPEC constraint (build only on a measured trigger; AC16 satisfied by absence plus a guard). Confirm it stays parked; the doctor measures the trigger. If you want it built regardless, that is a separate plan.
3. **Feed zero rule (option B on the old Reddit feed methods)** is parked because the feeds die 13-11-26; confirm you do not want that small change.

Owner supplies/approves (not decisions the plan can make): everything in "What only the owner can supply", each probe approval, and each enabling switch.

Defaults the plan chose without needing you (change by config): archive close delay 48 h / stability tolerance 1%; zero-rule history = 7 positive days in any labelled Reddit method as an eligibility gate; per-account cap proposal 800 (SPEC Q1, your call once data exists); B3 measures, harvest, query-id refresh and live fallbacks all off.

## Test Infra Improvement Notes

(none identified yet; updated during PVL/EVL. Known up front: the end-to-end fixture needs an OpenSSL executable like the B2 transport fixture; Linux CI does not prove Windows ACLs, Chrome or Task Scheduler.)

## Validate Contract

(placeholder — vc-validate-agent writes this section before EXECUTE)

## Resume and Execution Handoff

1. Selected plan file: `process/general-plans/active/collector-identity-pool_02-11-26/collector-identity-pool-finish_PLAN_06-11-26.md` (worktree `wt-b2-validate`, branch `claude/b2-validate`). History it builds on: collector-identity-pool_PLAN_02-11-26.md (Part A, B1, B2, B3, Part C addendum), SPEC, VALIDATE-B2, b2 backend acceptance, REF-R, REF-X, gap map `agent://GapMap` (not saved as a file; its findings are folded into this plan).
2. Last completed phase: PLAN written (this file); no source edited.
3. Validate-contract status: pending (PLAN artifact lint is not VALIDATE).
4. Supporting context loaded for this plan: SPEC; existing PLAN sections A/B1/B2/B3/C; VALIDATE-B2 §20; REF-R; REF-X; GapMap; canonical collector SPEC (AC34-AC36, superseding notes); `deploy/README.md`, `deploy/start-collector.ps1`, `deploy/register-tasks.ps1`; `attention_pc_refresh.py`, `x_pool.py`, `x_reader.py`, `twscrape_reader.py` (map_exception), `web_queries.py`, `registry.py`, `reddit_stream.py`, `reddit_web.py`, `pyproject.toml`, test layout and guard files.
5. Next step: VALIDATE this plan (independent reviewers: X slices incl. child envelope v2 and guards; Reddit slices incl. archive settle rules and `known_at_time`; browser/harvest security; ops/E2E feasibility; shared-file ownership), then owner decisions 1-3, then EXECUTE W0 only (S-Land with owner approval, S-Canon), then W1. A fresh agent resuming mid-execution reads: this plan's slice table and ownership matrix, the last slice report in this folder, and `git status` of `wt-b2-validate` before touching any shared file.

## Cursor and RIPER-5 Guidance

Next Step: RIPER-5 VALIDATE on this plan, then ENTER EXECUTE MODE for W0 only (S-Land needs the owner's commit approval; S-Canon is docs-only). Each later slice starts with its own Stage 0 read-only research and presents findings before code if any plan assumption is wrong. Never hand EXECUTE the whole program at once; after each slice STOP and verify (Phase Completion Rules) before the next wave. Cursor Plan mode: import the Implementation Checklist per slice; update status markers per slice; do not mark anything ✅ VERIFIED without owner confirmation. Reminder: each phase requires verification before proceeding to the next.
