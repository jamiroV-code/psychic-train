---
name: plan:pair-screener
description: "Cointegration / pair screener v1 — ranked pair table + per-pair spread detail for a hand-curated crypto universe"
date: 25-09-26
feature: cointegration-screener
---

# Pair Screener v1 — Cointegration Screener

**Date**: 25-09-26
**Complexity**: Complex (standard complex — one authoritative plan, sequential RFCs)
**Status**: ✅ VERIFIED — all 5 RFCs code-complete, EVL-confirmed, and user-approved; archived at
UPDATE PROCESS (28-09-26)
**Feature folder**: `process/features/cointegration-screener/`
**Owner**: Jamiro (user) · executor: vc harness agents

> **TL;DR** — Build `/pairs`: a new, independent screen that tests every pair from a hand-curated
> list of ~18 large liquid crypto coins for cointegration (Engle-Granger both directions + Johansen
> as a second opinion), ranks by BH-corrected p-value, and shows a per-pair detail view with the
> spread chart, z-score and half-life. All maths is whole-history (in-sample) diagnostic, not a live
> signal. Zero shared code, data, or runtime state with the momentum screener (`/screener`).

---

## Overview

The cointegration-screener feature folder has held only a `_GUIDE.md` placeholder since setup. This
plan builds its first real feature: a statistically rigorous second lens for finding pair-trade
candidates, following the same "new route, new router, new analytics module, explicit unavailable
states, gzip'd typed response" pattern the regime dashboard established
(`process/features/cycle-regime/completed/regime-dashboard_24-09-26/`). Unlike the regime dashboard,
this feature reads real-time-computed on-request statistics from a manually-deep-fetched cache — no
results cache, no scheduled job, no shared adapter singleton with the momentum screener.

The SPEC (`pair-screener_SPEC_25-09-26.md`, locked, same task folder) and the user's INNOVATE
decisions (recorded below as ADRs) are the two upstream inputs to this plan; every RFC below traces
back to specific acceptance criteria (AC-1..AC-12) in that SPEC.

## Quick Links

- [1. Context and Goals](#1-context-and-goals)
- [Phase Completion Rules](#phase-completion-rules)
- [1.5 Execution Brief](#15-execution-brief)
- [Phased Execution Workflow](#phased-execution-workflow)
- [2. Non-Goals and Constraints](#2-non-goals-and-constraints)
- [3. Architecture Decisions (Final)](#3-architecture-decisions-final)
- [5. High-level Data Flow](#5-high-level-data-flow)
- [7. Component Details](#7-component-details)
- [11. API Surface](#11-api-surface)
- [13. Phased Delivery Plan](#13-phased-delivery-plan)
- [15. RFCs](#15-rfcs)
- [Touchpoints](#touchpoints) · [Public Contracts](#public-contracts) · [Blast Radius](#blast-radius)
- [Verification Evidence](#verification-evidence) · [Resume and Execution Handoff](#resume-and-execution-handoff)

### Status Strip

| RFC | Title | Status |
|---|---|---|
| RFC-001 | Universe file + loader + deep-fetch script (+ statsmodels dependency, Stage-0 smoke check) | ✅ VERIFIED |
| RFC-002 | Stats engine (`stats.py`) + golden-value tests | ✅ VERIFIED |
| RFC-003 | Pydantic models + response serializer + router + perf-smoke | ✅ VERIFIED — see `pair-screener_RFC-003_REPORT_27-09-26.md` |
| RFC-004 | Web table + detail view + vitest formatters | ✅ VERIFIED — see `pair-screener_RFC-004_REPORT_27-09-26.md` |
| RFC-005 | Playwright `pairs.spec.ts` + screener-isolation proof | ✅ VERIFIED — see `pair-screener_RFC-005_REPORT_28-09-26.md` + EVL cycle 6 (tie-break fix) |

**All 5 RFCs user-approved 28-09-26.** Real-data result (18-coin universe, 153 pairs, all `ok`):
21 pairs have raw EG p < 0.05; 0 are significant after BH correction at the 5% level (closest is
DOGE/BCH, raw 0.00057 → BH-corrected 0.087). `compute_pairs.py` runs in ~56 s; the read-path
(`GET /api/pairs`) p95 is 135-232 ms. Final gates: pytest 486 passed / 3 deselected; vitest 153
passed across 19 files (3 consecutive green runs); `tsc --noEmit` exit 0; Playwright 35/35, run
twice (26 existing + 9 new `pairs.spec.ts`), plus a `pairs.spec.ts`-only repeat-each run at 90/90;
isolation diff vs pre-feature commit `35e646f` empty for `screener`/`regime`/`narrative` surfaces.

---

## 1. Context and Goals

**Why now.** The momentum screener and the regime dashboard both exist; this is the first build in
the third of the four listed product areas (`cointegration-screener`), and the SPEC is locked with
all open questions resolved by the user's explicit INNOVATE decisions (below). Nothing blocks
starting.

**Context loaded for this plan** (per `process/context/all-context.md` routing):

- `process/context/all-context.md` — repo state, adapters, open questions (incl. the
  momentum-screener/general-plans-vs-features routing question, not touched by this plan)
- `process/context/tests/all-tests.md` — runners, commands, Standing Lesson (green ≠ verified),
  `isolated_cache` fixture requirement, known cold-start-latency gap
- `process/context/data-sources/all-data-sources.md` — provider licensing/free-tier rules
- `process/features/cointegration-screener/_GUIDE.md` — stale (still names `screener.py`/
  `web/app/screener/` as this feature's target; corrected by this plan's UPDATE PROCESS item, §18)
- `api/data/ccxt_adapter.py`, `api/data/cache.py`, `api/scripts/backfill_primaries.py`,
  `api/scripts/seed_e2e_cache.py`, `api/routers/regime.py`, `api/models/regime.py`, `api/main.py`,
  `api/pyproject.toml`
- `web/components/regime/`, `web/lib/api/regime.ts`, `web/e2e/regime.spec.ts` (structural precedent)
- `.claude/skills/vc-generate-plan/references/example-complex-prd.md`

**Research findings that shape this plan (25-09-26):**

| Finding | Consequence |
|---|---|
| `ccxt_adapter.fetch_ohlcv` already accepts `limit=` and resolves bare tickers to Hyperliquid market symbols via `resolve_market_symbol`; `DEEP_LOOKBACK_LIMIT = 5000` is defined but has zero callers anywhere in the codebase | This feature is `DEEP_LOOKBACK_LIMIT`'s first consumer — call `fetch_ohlcv(symbol, "1d", limit=DEEP_LOOKBACK_LIMIT)` from a new script, exactly mirroring `backfill_primaries.py`'s pattern |
| `fetch_ohlcv` is cache-first and merges new bars onto whatever is cached (`pd.concat` + write); it does not distinguish "shallow momentum cache" from "deep pair-screener cache" — same `cache/ohlcv/{SYMBOL}/1d.parquet` file | A deep fetch for a pair-universe coin that overlaps the momentum watchlist (e.g. BTC, ETH) will *extend* the same cache file the momentum screener reads, not create a separate one — this is fine (same coin, same OHLCV, more history is strictly better) but must be called out explicitly so AC-11 ("deep fetch does not implicitly run or invalidate the momentum screener's cache") is tested as "cache extended, not truncated/replaced", not "byte-identical" |
| `api/pyproject.toml` has no `statsmodels`; `arch` is intentionally NOT being added (INNOVATE decision 11 — SPEC named it, this session corrects that as scope) | RFC-001 Stage 0 adds `statsmodels>=0.14` via `uv add --project api`, updates `uv.lock`, and does a golden import/signature smoke check before any stats code is written |
| `api/data/watchlist.py` and `api/routers/screener.py` are the momentum screener's exclusive surface; `api/analytics/regime/` is the regime dashboard's | This feature's new files must never import from either — the isolation proof (RFC-005, AC-9/AC-10) is a `git diff`/import-graph check, not just "tests still pass" |
| `api/main.py` registers routers additively (`app.include_router(...)`); `GZipMiddleware(minimum_size=1000)` is already app-wide | RFC-003 adds one `app.include_router(pairs.router)` line; no new middleware needed |
| `seed_e2e_cache.py` already has a documented pattern (safety guard on `SCREENER_CACHE_ROOT`, manifest JSON, symbol/bar-count constants) that RFC-005 extends rather than duplicates | Add a `pairs` section to the same script and manifest, not a second seeder |
| `all-tests.md` Standing Lesson item 7 ("a fixture writer must be checked against its reader's actual parsing contract") and item 8 ("a green suite that never crosses a boundary proves nothing about that boundary") apply directly here — this is a brand-new router+page pair | RFC-005's Playwright spec is non-negotiable; RFC-003's perf-smoke step must run against the real deep-fetched cache, not synthetic data, at least once |

**Goals**

1. See every pair from the curated coin list ranked by statistical strength, with no pair ever
   silently missing.
2. See two independent test opinions (Engle-Granger, Johansen) side by side per pair, never merged.
3. Drill into any pair's spread, z-score, half-life and sample window.
4. Never see a NaN, a silent zero, or an undisclosed partial-sample statistic.
5. Prove, mechanically, that this feature never touches the momentum screener's code, cache, or
   runtime state.

**Success metrics**

- Table renders in well under human patience (perf-smoke threshold, RFC-003) against the real
  ~190-pair deep-fetched cache — not a fresh-fetch-per-request path.
- 100% of pairs from the universe appear as exactly one row (AC-1) on every load.
- 0 pairs with a hidden partial-sample statistic; every insufficient/unavailable pair states why.
- Existing momentum-screener pytest + vitest + Playwright suites pass unchanged after this ships.

---

## Phase Completion Rules

A phase is NOT complete until:

1. **Integration Test** - Works with other system pieces
2. **Manual Test** - User can perform the action
3. **Data Verification** - Database/state changes confirmed
4. **Error Handling** - Failure cases handled gracefully
5. **User Confirmation** - User says "it works"

Status meanings:
- ⏳ PLANNED - Not started
- 🔨 CODE DONE - Written but not E2E tested
- 🧪 TESTING - Currently being tested
- ✅ VERIFIED - Tested AND confirmed working
- 🚧 BLOCKED - Has issues

After each phase, document:
- [ ] What was tested manually
- [ ] Data verified in storage (Parquet/DuckDB query + result shown)
- [ ] Errors encountered and fixed
- [ ] User confirmation received

"Data verified in DB" in this repo means a DuckDB or pandas read of the relevant
`api/data/cache/**.parquet` file, with the query and its output pasted into the phase report.

---

## 1.5 Execution Brief

### RFC-001: Universe file + loader + deep-fetch script

- **What happens**: Stage 0 adds `statsmodels>=0.14` and runs a golden import/signature smoke check
  (`coint`, `coint_johansen`, `multipletests`). Then a new hand-editable universe JSON, its loader,
  and a deep-fetch script (mirroring `backfill_primaries.py`) using `DEEP_LOOKBACK_LIMIT=5000`.
- **Integration points**: `api/data/pairs_universe.json` (new, read-only at runtime) → new loader →
  `api/scripts/backfill_pairs_universe.py` → `ccxt_adapter.fetch_ohlcv(..., limit=DEEP_LOOKBACK_LIMIT)`
  → existing `cache/ohlcv/{SYMBOL}/1d.parquet`.
- **Test**: pair-enumeration unit test; loader-isolation unit test (AC-9); deep-fetch integration
  test with `isolated_cache` confirming momentum-screener's shallow cache file is untouched (AC-11).
- **Verify**: DuckDB query listing row counts and date ranges per coin's `1d.parquet` after a real
  deep fetch.
- **Done when**: user reviews the universe list and the per-coin coverage table and agrees.

### RFC-002: Stats engine

- **What happens**: `api/analytics/cointegration/stats.py` computes, per pair: log-price transform,
  static OLS hedge ratio (both directions), Engle-Granger both directions (min-p ranks), Johansen
  trace stat/critical value/rank, AR(1) half-life (or `not_mean_reverting`), z-score, BH correction
  across all sufficiently-overlapping pairs.
- **Integration points**: reads cached OHLCV via `ccxt_adapter`/`cache.read_ohlcv`; writes nothing.
- **Test**: golden-value pytest on hand-computed synthetic fixtures (cointegrated pair,
  non-cointegrated pair, non-mean-reverting pair, short-overlap pair).
- **Verify**: print a coverage/result table from a live-cache run (after RFC-001's deep fetch).
- **Done when**: user reviews the golden-value results and the live coverage table and agrees.

### RFC-003: Endpoint + compute/persist script + staleness (amended post-Stage-0, see ADR-8 Amendments)

- **What happens**: `api/scripts/compute_pairs.py` (new — runs `pairs_response.py`'s per-pair
  compute + BH correction over the whole universe and writes `api/data/cache/pairs/results.parquet`
  + `provenance.json`); `api/models/pairs.py` (Pydantic, + `computation_status`/`stale_reason`
  fields); `api/analytics/cointegration/pairs_response.py` (now split into a compute path used by
  `compute_pairs.py` and a read path used by the router — see Stages below); `api/routers/pairs.py`
  (`GET /api/pairs`, `GET /api/pairs/{a}/{b}`, reads the persisted cache + provenance, never
  recomputes), registered in `api/main.py`.
- **Integration points**: `compute_pairs.py` → `pairs_response.py` (compute path) → `stats.py` →
  cache reads → `results.parquet`/`provenance.json` writes. Router → `pairs_response.py` (read
  path) → `results.parquet`/`provenance.json` reads only; router never calls `stats.py`.
- **Test**: pytest router contract tests (shape, 404/422 on invalid symbols, no NaN/0 stand-ins,
  the three `computation_status` states); read-path timing gate on `GET /api/pairs` (now
  trivially fast — a persisted-file read, not a compute); a separate, informational
  `compute_pairs.py` runtime record (~46 s, not gated against 3 s — it is a script, not a request).
- **Verify**: `curl` both endpoints; run `compute_pairs.py` once for real and paste its runtime +
  the resulting `provenance.json` into the phase report.
- **Done when**: user reviews the read-path timing, the compute-script runtime, and endpoint shapes
  (including the staleness banner behavior) and agrees.

### RFC-004: Web

- **What happens**: `web/app/pairs/page.tsx` (table, default sort BH-corrected p ascending, sample
  length per row, explicit insufficient/unavailable rows) + `web/app/pairs/[a]/[b]/page.tsx` (or
  equivalent detail route — spread chart via `lightweight-charts`, both EG directions, Johansen,
  half-life state, whole-history disclosure copy).
- **Integration points**: `web/lib/api/pairs.ts` → `web/components/pairs/*`.
- **Test**: vitest for `web/lib/format-*.ts` pair formatters + component render tests with injected
  fetchers (insufficient/unavailable/disagreement rows).
- **Verify**: manual load of `/pairs` and a detail page against a running API with a seeded cache.
- **Done when**: user reviews the table and one detail page and agrees.

### RFC-005: End-to-end proof + isolation proof

- **What happens**: extend `api/scripts/seed_e2e_cache.py`'s manifest with a `pairs` fixture section
  (synthetic deep-history OHLCV for a small universe subset, including one cointegrated pair, one
  not, one thin-overlap pair); `web/e2e/pairs.spec.ts`; re-run existing momentum-screener
  pytest+vitest+Playwright suites and a `git diff` showing zero edits to `screener.py`/
  `watchlist.py`/`screener.spec.ts`.
- **Test**: `cd web && pnpm test:e2e` (both specs); `uv run --project api pytest api/ -q` (full
  suite green, no screener regressions).
- **Done when**: E2E green, isolation proof pasted into the phase report, and the user confirms the
  real-cache walkthrough (manual, known-gap in this container — see AC coverage below).

### Expected Outcome

- `/pairs` lists every pair from the universe (≈100-190 rows for 15-20 coins), ranked by
  BH-corrected p-value, insufficient-history pairs sorted to the bottom with no stats shown.
- Detail view shows the spread chart, current z-score, half-life state, both EG directions, Johansen,
  and the sample window, all labelled whole-history/in-sample.
- The momentum screener is provably unaffected — no shared files, no shared cache keys, tests green.
- `statsmodels` is a new dependency; `arch` is explicitly NOT added.

---

## Phased Execution Workflow

**IMPORTANT**: This plan uses a phase-by-phase execution model with built-in verification gates.
For each RFC:

- **Step 1: Pre-Phase Research** — read the existing code patterns named in the RFC's Stage 0,
  identify blockers, present findings to the user. **CRITICAL: present findings and STOP. Wait for
  user approval before Step 2. Do NOT bundle research + implementation into one agent call.**
- **Step 2: Detailed Planning** — exact files, exact functions, success criteria; get approval.
- **Step 3: Implementation** — execute the approved steps exactly; no deviations without a Change
  Management entry.
- **Step 4: Testing & Verification** — run the RFC's test stage and verification queries, paste
  outputs into the phase report.
- **Step 5: User Confirmation** — present:
  ```
  **What's Functional Now**: what the user can do/see after this stage
  **What Was Tested**: verification performed (pytest output, DuckDB query, curl, screenshots)
  **What You Can Test**: exact commands / URLs / clicks
  **Ready For**: next RFC
  ```
  The user tests, confirms, and approves moving on.

**CRITICAL: Do NOT proceed to the next RFC until the current one is ✅ VERIFIED.**

---

## 2. Non-Goals and Constraints

**Non-goals** (mirrors SPEC Out Of Scope)

- Equity pairs (crypto-only v1).
- Any change to `/screener`, `api/routers/screener.py`, `api/data/watchlist.py`.
- Automatic/algorithmic universe selection or a browser-based universe editor.
- A combined "tradability score" collapsing EG + Johansen + half-life/z-score into one number.
- Trade execution, alerting, position-sizing.
- Backtesting historical pair-trade performance.
- Continuous/scheduled re-screening — v1 is on-request compute from a manually-deep-fetched cache.
- Stablecoins in the universe.

**Constraints**

- Crypto only, via `api/data/ccxt_adapter.py`. No new market-data provider.
- New route (`/pairs`), new router (`api/routers/pairs.py`) — never imports from
  `api/routers/screener.py`.
- New hand-editable universe list distinct from `api/data/watchlist.py`.
- History depth: `DEEP_LOOKBACK_LIMIT = 5000` daily bars, one-time manually-triggered fetch.
- Minimum overlap: `MIN_OVERLAP_DAYS = 365` (named constant, INNOVATE decision 6).
- Ranking: BH-corrected Engle-Granger p-value (min-p direction) primary; Johansen always shown
  separately; half-life and z-score shown alongside, never folded into a score.
- New dependency: `statsmodels>=0.14`. `arch` explicitly NOT added (SPEC scope correction).
- One source of numerical truth: all statistics computed in Python; TypeScript formats/renders only.
- Numbers never silently wrong: explicit unavailable/insufficient states, no NaN, no zero-fill, no
  undisclosed truncation.
- Testing convention: every statistic needs a hand-computed golden-value test
  (`all-tests.md` Standing Lesson item 4); any test driving `fetch_ohlcv` uses `isolated_cache`.
- Feature isolation: momentum screener's code, cache footprint, config, runtime state fully
  untouched (AC-10, AC-11).

---

## 3. Architecture Decisions (Final)

These ADRs record the user's INNOVATE decisions (approved via "go") as fixed inputs to this plan,
with the rejected alternative named for each.

### ADR-1: Log prices, not levels

**Decision**: all cointegration regressions and spread calculations use `ln(price)`, not raw price
levels.
**Rejected**: raw levels — rejected because pair spreads on raw levels are dominated by the
higher-priced coin's absolute scale rather than proportional co-movement, and log-price spreads are
the standard in the pair-trading literature this feature is modeling itself on.
**Implications**: every downstream number (hedge ratio, spread, z-score) is in log-space; the UI
must not present the hedge ratio as a raw price ratio.

### ADR-2: Static OLS hedge ratio, whole-sample, symmetric EG test, whole-history diagnostics

**Decision (2a)**: hedge ratio is a single static OLS coefficient fit over the full overlapping
sample — not rolling, not Kalman-filtered.
**Rejected**: rolling-window or Kalman-filter hedge ratios — rejected as unnecessary complexity for
a v1 screening tool where the output is a diagnostic snapshot, not a live-updating trading signal;
SPEC's Out Of Scope already excludes backtesting/live signals, so a time-varying hedge ratio has no
consumer in this feature.

**Decision (2b)**: Engle-Granger runs BOTH directions (A~B and B~A); the table ranks on the
minimum-p direction; both directions are shown in the detail view; UI copy discloses the resulting
mild optimism bias (taking the min of two correlated tests inflates significance slightly versus a
single pre-committed direction).
**Rejected**: a fixed convention (e.g. "always regress the higher-market-cap coin as dependent") —
rejected because Engle-Granger is not direction-symmetric and a fixed convention would silently
under-detect cointegration in pairs where the "natural" direction is the weaker one; running both
and disclosing the bias is more honest than hiding a directional choice.

**Decision (2c)**: spread, z-score and half-life are labelled explicitly as whole-history (in-sample)
diagnostics, not live trading signals.
**Rejected**: presenting them without qualification — rejected because it would imply forward
predictive validity these numbers do not have; this directly serves the SPEC's "confidence over
direction" house rule and the "never a verdict" Out Of Scope item.

### ADR-3: Half-life via AR(1) OLS, explicit non-mean-reverting state

**Decision**: half-life = OLS regression of Δspread on lagged spread (AR(1)); `HL = −ln(2)/β`. When
β ≥ 0 (spread is not mean-reverting under this model), the pair enters an explicit
`not_mean_reverting` state — no numeric half-life is shown.
**Rejected**: forcing a number regardless of sign (e.g. `abs(HL)` or clamping) — rejected because a
non-negative β means the AR(1) model does not support mean reversion at all; showing a number would
be exactly the "silently wrong number" this project's house rule forbids.

### ADR-4: Z-score = latest spread vs full-sample mean/std

**Decision**: current z-score is `(latest_spread − mean(spread)) / std(spread)` over the full
overlapping sample (the same sample the EG/Johansen tests use).
**Rejected**: a rolling lookback window (e.g. trailing 90 days) for the z-score baseline — rejected
for internal consistency with ADR-2c's whole-history framing; mixing a whole-history hedge
ratio/half-life with a rolling z-score baseline would make the "how stretched is it right now"
number inconsistent with the "is this pair cointegrated at all" numbers on the same row.

### ADR-5: Johansen via `coint_johansen`, fixed order/lag

**Decision**: `statsmodels.tsa.vector_ar.vecm.coint_johansen(data, det_order=0, k_ar_diff=1)`;
report the trace statistic for rank=0, the 95% critical value, and a boolean `rank_at_least_1` (trace
stat exceeds the 95% critical value).
**Rejected**: letting `k_ar_diff` vary per pair via an automatic lag-selection criterion (e.g. AIC) —
rejected for v1 to keep every pair's Johansen result comparable under one fixed specification; an
automatic per-pair lag order would make the table's "second opinion" column methodologically
inconsistent row to row, undermining the "two independent opinions, compare them" goal.

### ADR-6: MIN_OVERLAP_DAYS = 365, named constant

**Decision**: a pair needs ≥365 days of overlapping daily bars to be tested at all. Named constant
`MIN_OVERLAP_DAYS = 365` in `stats.py`, following the `MIN_BARS_REQUIRED` precedent in
`ccxt_adapter.py`.
**Rejected**: a shorter minimum (e.g. 180 days) — rejected because Engle-Granger and Johansen are
both asymptotic tests whose small-sample behavior is unreliable well under a year of daily data;
SPEC locked "~1 year" as the order of magnitude and 365 is the exact, documented number.

### ADR-7: Per-pair status vocabulary — `ok` / `insufficient_overlap` / `coin_unavailable`

**Decision**: each pair's top-level `status` is one of `ok`, `insufficient_overlap`,
`coin_unavailable`, with a free-text `reason` field. ccxt's `unavailable`/`stale`/`bad_symbol`
values are folded into `reason` text under `coin_unavailable`, not surfaced as separate top-level
statuses. Within an `ok` pair, `half_life` carries its own sub-state: `computed` or
`not_mean_reverting` (ADR-3).
**Rejected**: reusing ccxt's flat vocabulary directly as the pair's status (SPEC open question) —
rejected because a pair involves TWO coins and ccxt's vocabulary is per-symbol; a pair-level status
needs its own small vocabulary that names the two pair-specific failure modes (not enough shared
history vs. one coin being unfetchable) rather than forcing the UI to interpret two separate
per-coin ccxt statuses per row.

### ADR-8: Deep fetch = manual script; stats computed on-request, no results cache; BH via `fdr_bh`

**Decision**: the deep history fetch is a manually-run script
(`api/scripts/backfill_pairs_universe.py`, mirroring `backfill_primaries.py`, using
`DEEP_LOOKBACK_LIMIT=5000`, daily bars only). Statistics are computed on each `GET /api/pairs`
request, router → analytics → cached parquet reads, with NO results cache/precompute layer.
Benjamini-Hochberg correction (`statsmodels.stats.multitest.multipletests(..., method='fdr_bh')`) is
applied across all pairs with sufficient overlap in that request's universe.
**Rejected**: a scheduled/cron recomputation (SPEC Out Of Scope, already ruled out) and a
precomputed results-cache file (considered for performance) — rejected because at ≤190 pairs,
one-time statsmodels calls per request is expected to be fast enough (RFC-003's perf-smoke step
sets and measures against an explicit threshold); a results cache would add a second stale-data
surface and invalidation problem for no proven need. If the perf-smoke measurement blows the
threshold, RFC-003's fallback is an in-process TTL cache (seconds-to-minutes), never a
precompute/schedule.

### ADR-8 Amendment (Post-Stage-0, RFC-002 findings, 25-09-26): Precompute after backfill, not on-request

**Trigger**: RFC-002 Stage 0 measured the full 153-pair on-request compute against the real
deep-fetched cache: **46.0 s total** (p95 513 ms/pair) with `coint()`'s default `autolag='aic'`
(~98% of runtime is the Engle-Granger AIC lag search, run twice per pair); **7.6 s** with
`autolag=None`; Johansen is cheap (~5 ms/pair). The RFC-003 target is p95 < 3 s warm. See
`pair-screener_RFC-002-stage0_REPORT_25-09-26.md` §5 for the full timing table. This amendment
**supersedes** ADR-8's original "on-request compute, no results cache" decision above (kept verbatim
for history, not deleted) and its "Rejected: ... a precomputed results-cache file" clause.

**New decision (D1, user-approved in chat)**: statistics are precomputed after backfill by a
dedicated script, `api/scripts/compute_pairs.py` (a new, separate script — not folded into
`backfill_pairs_universe.py`; see rationale below), and persisted to a git-ignored cache. The API
only reads the persisted cache; it never computes on request. `coint()` keeps its default
`autolag='aic'` (per-pair accuracy over speed, now that compute is offline); `autolag` is a single
named module constant `stats.py::EG_AUTOLAG = "aic"` so this choice stays a one-line change.

**Why a separate script, not a step inside `backfill_pairs_universe.py`**: backfill (network-bound,
rarely needed — deep history barely changes day to day) and compute (CPU-bound, should re-run
whenever the universe or price cache changes) have different refresh cadences. Folding them together
would force every universe edit to re-run the network fetch, and every fresh deep fetch to re-run
compute even when only more history was wanted. `compute_pairs.py` takes no CLI args, reads the
current `pairs_universe.json` + cached OHLCV, computes every pair via `stats.compute_pair_stats` +
`pairs_response.py`'s BH correction, and writes the results cache — the second manually-run script
in this feature, documented in §19 Ops Runbook.

**Persisted cache (git-ignored, see §12b for the full schema)**: `api/data/cache/pairs/results.parquet`
(one row per pair, all `PairSummary` fields) plus a per-pair spread store for the detail endpoint
(exact layout — single list-column vs. `api/data/cache/pairs/spreads/{A}_{B}.parquet` per pair —
decided at RFC-003 Stage 0 and recorded in its phase report; either is acceptable as long as the
detail endpoint's read is O(1) file lookups, never a recompute) plus a
`api/data/cache/pairs/provenance.json` sidecar (see the Staleness amendment below).

**Measured timings (evidence, from RFC-002 Stage 0 report §5)**:

| Config | 153 pairs total | per-pair mean | p95 | EG share |
|---|---|---|---|---|
| `coint` default `autolag="aic"` (chosen for the compute script) | 46.0 s | 296 ms | 513 ms | ~98% |
| `coint(..., autolag=None)` (named-constant fallback only) | 7.6 s | 44 ms | 63 ms | ~82% |
| Johansen alone | — | ~5 ms | — | — |

**Rejected alternatives**:
- **Startup warm cache** (compute once when the API process starts) — rejected because every API
  restart would pay the ~46 s cost synchronously (or need a background-thread warmup with its own
  "not ready yet" state), and it does not handle "universe changed, needs a refresh" any better than
  an explicit script; a manually-run script keeps the compute step visible and user-controlled,
  matching this feature's "no scheduler, user-run scripts" pattern (ADR-8 original, RFC-001's
  backfill script).
- **`autolag=None` as the primary path** — rejected because it shifts EG p-values (a real
  statistical decision, not just a performance one) for a speedup no longer needed once compute is
  offline; kept as the named-constant fallback if `compute_pairs.py`'s runtime ever becomes a
  problem (e.g. the universe grows well past 20 coins).
- **Slow first load** (accept ~46 s on the first `GET /api/pairs` after backfill, in-process-cache
  thereafter — the RFC-002 Stage 0 report's original D1 lean, option a+d) — rejected in chat in
  favor of precompute: an unpredictable first-request latency is a worse experience than a visible,
  deliberate script run, and it reintroduces the "silently slow / silently stale in-process cache"
  ambiguity ADR-8's original text was trying to avoid.

**Compute-path isolation and cache path resolution (added at PVL supplement, 26-09-26, closes
Execute-Agent Instructions E5/E6):**
- The compute path (`compute_pairs.py` and `pairs_response.py`'s compute-path function) reads
  per-coin OHLCV **only** via `api.data.cache.read_ohlcv(symbol, "1d")`. It **never** calls
  `ccxt_adapter.fetch_ohlcv` — the compute path makes zero network calls, matching this amendment's
  "CPU-bound, offline" premise. A missing or empty `read_ohlcv` result for a universe coin maps to
  per-pair `status: "coin_unavailable"` (ADR-7), with a `reason` naming the coin; it is never
  treated as silently-stale usable data. Too few shared trading-day rows between two coins'
  `read_ohlcv` frames (below `MIN_OVERLAP_DAYS`) maps to `status: "insufficient_overlap"`
  (ADR-6/ADR-7), same as today — unaffected by this note, restated here for completeness since both
  statuses originate in the same compute-path read.
- Every pairs-cache path (`results.parquet`, `provenance.json`, and any per-pair
  `spreads/*.parquet`) is resolved through `cache.CACHE_ROOT`, read at call time — never a
  hardcoded path and never a module-level constant bound once at import time. This matches the
  existing convention for every other cache subdirectory (`ohlcv_path()`, `liqtide_payload_path()`,
  `liquidity_series_path()`, `narrative_series_path()`, all in `api/data/cache.py`, all built from
  `CACHE_ROOT` inside the function body). Concretely: `api/data/cache.py` gains additive helpers
  `pairs_results_path()`, `pairs_provenance_path()`, and `pairs_spread_path(symbol_a, symbol_b)`
  (or equivalent), each returning `CACHE_ROOT / "pairs" / ...` computed at call time — mirroring
  `ohlcv_path()`'s exact shape. These are additive-only edits to `cache.py`; every existing
  `cache.py` function is unchanged. `pairs_response.py` calls these helpers rather than
  constructing paths itself, so the `isolated_cache` fixture's
  `monkeypatch.setattr(cache, "CACHE_ROOT", tmp_path)` correctly redirects all pairs-cache
  reads/writes during tests — the same defect class `conftest.py`'s own docstring names ("an
  unredirected module-level constant").

### ADR-8 Amendment — Staleness and Provenance (numbers are never silently wrong)

**Decision**: every write of the persisted results cache also writes `provenance.json`:

```json
{
  "computed_at": "2026-09-26T14:00:00Z",
  "universe": ["BTC", "ETH", "..."],
  "per_coin_last_bar_date": {"BTC": "2026-09-25", "ETH": "2026-09-25"},
  "per_coin_bar_count": {"BTC": 1820, "ETH": 1820},
  "statsmodels_version": "0.15.0",
  "eg_autolag": "aic"
}
```

On every `GET /api/pairs`/`GET /api/pairs/{a}/{b}` request, the router compares this provenance
against (a) the CURRENT `pairs_universe.json` (set equality), (b) each universe coin's CURRENT
`cache/ohlcv/{SYMBOL}/1d.parquet` (max date newer than `per_coin_last_bar_date`, OR bar count
increased), **and (c) [added at PVL supplement, 26-09-26, closes Execute-Agent Instruction E7] the
CURRENTLY-INSTALLED `statsmodels.__version__` against provenance's `statsmodels_version`, and the
CURRENT `stats.py::EG_AUTOLAG` constant against provenance's `eg_autolag`** — a mismatch on either
means the persisted results were computed under a different statistics configuration than is
currently running, and must not be silently reported as `fresh`. This closes the gap where
`provenance.json` recorded these two fields but nothing ever compared them. Four top-level
`computation_status` triggers now feed the same three-value enum below — a small closed enum plus a
free-text reason, matching ADR-7's per-pair vocabulary style, never a silent default:

| `computation_status` | Meaning | API behavior | UI |
|---|---|---|---|
| `fresh` | provenance matches current universe + cache | 200, full `pairs` array | normal table |
| `stale` | universe changed, OR any universe coin's cache is newer than provenance, OR the installed `statsmodels_version`/`eg_autolag` no longer matches provenance (added at PVL supplement, 26-09-26) | 200, full `pairs` array (last-known-good rows) + `stale_reason` naming what changed | banner: "results are stale — [reason]; run `compute_pairs.py` to refresh" |
| `results_unavailable` | no `results.parquet`/`provenance.json` exists yet (fresh clone, first run, or E2E fixture not seeded) | 200, `pairs: []`, `computation_status: "results_unavailable"` | banner: "no results yet — run `compute_pairs.py`" |

The API **never** serves `results.parquet` rows for a coin list that does not match the current
universe, and never silently drops the staleness signal — a `stale` response still serves the
last-known-good rows (labelled stale), it does not substitute or hide anything. This mirrors ADR-7's
"never silently wrong" framing and the project house rule (`all-context.md` Key Patterns: "Numbers
are never silently wrong").

**Rejected**: silently recomputing on-request when stale is detected — rejected because that
reintroduces the exact 46 s on-request cost the decision above just eliminated, and makes staleness
invisible (a slow request would just look slow, not flagged as stale). Serving stale results with no
`computation_status` flag at all — rejected as a direct violation of "numbers never silently wrong."

### ADR-9: API shape — two endpoints, server-side universe validation

**Decision**: `GET /api/pairs` (table summary, all pairs) + `GET /api/pairs/{a}/{b}` (detail,
including the full spread series). `{a}` and `{b}` are validated against the universe list
server-side; a symbol not in the universe returns 404 (not found in this universe) or 422
(malformed) per RFC-003's exact contract. App-wide `GZipMiddleware` already covers both.
**Rejected**: a single endpoint returning the full spread series for every pair on every table load
— rejected as unnecessarily large payloads (a year+ of daily bars × ~190 pairs) for a screen whose
primary view only needs summary statistics; splitting matches the regime dashboard's "big payload
only when the user drills in" pattern is NOT used here (regime sends everything in one shot because
it needs synced charts) — this feature's two-endpoint split is a deliberate divergence, justified by
the table/detail UX split (SPEC flow diagram) rather than a synced multi-panel view.

### ADR-10: Module layout

**Decision**: `api/analytics/cointegration/{stats.py, pairs_response.py}`, `api/models/pairs.py`,
`api/routers/pairs.py` (registered in `api/main.py`), `api/data/pairs_universe.json` + a small
loader module, `web/app/pairs/`, `web/components/pairs/`, `web/lib/api/pairs.ts`,
`web/lib/types/pairs.ts`.
**Rejected**: reusing `api/analytics/regime/` or `api/data/watchlist.py` module boundaries —
rejected because those modules belong to different features per this project's "providers/analytics
live behind their own adapters/modules" convention (`all-context.md` Key Patterns), and reuse would
directly violate AC-9/AC-10's isolation requirement.

---

## 5. High-level Data Flow

```
api/data/pairs_universe.json (hand-edited, ~15-20 coins) ──► pairs_universe loader
                                                                       │
User runs: backfill_pairs_universe.py (manual, one-time/occasional)  │
    │                                                                 │
    ▼                                                                 │
ccxt_adapter.fetch_ohlcv(symbol, "1d", limit=DEEP_LOOKBACK_LIMIT) ──► cache/ohlcv/{SYMBOL}/1d.parquet
                                                                       │ (existing file, extended)
                                                                       │
                                        analytics/cointegration/stats.py
                              (log prices, static OLS hedge ratio both directions,
                               EG both directions + min-p rank, Johansen trace/crit/rank,
                               AR(1) half-life or not_mean_reverting, z-score, per-pair status)
                                                                       │
                                analytics/cointegration/pairs_response.py
                                    (BH correction across sufficient-overlap pairs,
                                     universe enumeration, per-pair response assembly)
                                                                       │
                              routers/pairs.py  GET /api/pairs
                                                 GET /api/pairs/{a}/{b}  ◄── universe-validated
                                                                       │
                                     web/lib/api/pairs.ts ──► web/app/pairs/page.tsx (table)
                                                          ──► web/app/pairs/[a]/[b]/page.tsx (detail)
```

---

## 6. Security Posture

Unchanged from the rest of the app: API bound to `127.0.0.1`, CORS limited to `localhost:3000` (plus
the E2E override). No keys, no credentials, no user data. `pairs_universe.json` is a local,
hand-edited file with no user-facing edit UI in v1 (SPEC Out Of Scope).

---

## 7. Component Details

### `api/data/pairs_universe.json` + loader (new)

- A flat JSON array (or `{"coins": [...]}` object — decided at RFC-001 Step 2) of ~15-20 ticker
  strings, structurally and physically separate from `api/data/watchlist.py`'s storage.
- Loader is a small pure function: read file → list of tickers → validated for duplicates/stablecoins
  at load time (warn, don't silently drop).

### `api/scripts/backfill_pairs_universe.py` (new)

- Mirrors `backfill_primaries.py`'s structure: no CLI args, idempotent, calls
  `ccxt_adapter.fetch_ohlcv(symbol, "1d", since=<explicit early date>, limit=DEEP_LOOKBACK_LIMIT)`
  per universe coin, with defensive cap-hit pagination, prints a coverage table (symbol, status,
  rows, first date, last date).

### `api/scripts/compute_pairs.py` (new, RFC-003, added by the ADR-8 Amendment)

- No CLI args, idempotent (safe to re-run any time). Calls `pairs_response.py`'s compute path over
  the full current universe; writes `api/data/cache/pairs/results.parquet` +
  `api/data/cache/pairs/provenance.json`; prints elapsed time + a per-status pair-count summary.
  Separate from `backfill_pairs_universe.py` because backfill (network) and compute (CPU) refresh
  on different cadences — see the ADR-8 Amendment for the full rationale.
- **Network isolation (added at PVL supplement, 26-09-26):** reads OHLCV exclusively via
  `cache.read_ohlcv` (through `pairs_response.py`'s compute path) — never calls
  `ccxt_adapter.fetch_ohlcv`. Writes resolve `api/data/cache/pairs/` paths via `cache.py`'s new
  additive `pairs_results_path()`/`pairs_provenance_path()` helpers (never a hardcoded path), so
  the script is fully isolatable under `isolated_cache` in tests. See the ADR-8 Amendment's
  "Compute-path isolation and cache path resolution" note above for the full rationale.

### `api/analytics/cointegration/stats.py` (new, pure — persistence-unaware; RFC-002)

- **Responsibilities**: pure functions over per-coin `DataFrame`s → per-pair result. Log-price
  transform; static OLS hedge ratio both directions; `statsmodels.tsa.stattools.coint` both
  directions (named constant `EG_AUTOLAG = "aic"`, D1); AR(1) half-life; z-score (both computed
  from the min-p/rank-driving EG direction's spread, D3); per-pair `status`/`reason`;
  `MIN_OVERLAP_DAYS` gate. `coint_johansen` called inside a scoped `ComplexWarning` suppression
  with a `max|imag(eig)| > 1e-9` numerical-instability guard (D2). One orchestrator
  `compute_pair_stats(df_a, df_b, symbol_a, symbol_b) -> PairStatsResult`. This module knows
  nothing about the results cache or provenance — see `pairs_response.py` below for persistence.
- **Key flows**: two coins' cached daily OHLCV → inner-join on date (overlap) → gate on
  `MIN_OVERLAP_DAYS` → log prices → both-direction OLS/EG → Johansen → half-life → z-score.

### `api/analytics/cointegration/pairs_response.py` (new, RFC-003, amended post-Stage-0)

- **Responsibilities — compute path** (called only by `api/scripts/compute_pairs.py`, never by the
  router): enumerate all `C(n,2)` pairs from the universe; read each coin's OHLCV **only** via
  `cache.read_ohlcv(symbol, "1d")` — never `ccxt_adapter.fetch_ohlcv` (added at PVL supplement,
  26-09-26; closes Execute-Agent Instruction E5); a missing/empty read maps the pair to
  `coin_unavailable` before `stats.py` is even called; call `stats.py` per pair; collect raw
  p-values from pairs with `status == "ok"`; run `multipletests(..., method='fdr_bh')`; assemble
  the full table response (including `insufficient_overlap`/`coin_unavailable` rows, never
  dropped) and per-pair spread data; write `api/data/cache/pairs/results.parquet` +
  `api/data/cache/pairs/provenance.json` via `cache.py`'s new `pairs_results_path()`/
  `pairs_provenance_path()` helpers (never a hardcoded or import-time-bound path — added at PVL
  supplement, 26-09-26; closes Execute-Agent Instruction E6).
- **Responsibilities — read path** (called only by `api/routers/pairs.py`): load
  `results.parquet` + `provenance.json` (via the same `cache.py` path helpers); compare against
  the current `pairs_universe.json`, each universe coin's current OHLCV cache, and (added at PVL
  supplement, 26-09-26; closes Execute-Agent Instruction E7) the currently-installed
  `statsmodels.__version__`/`stats.py::EG_AUTOLAG` against provenance's `statsmodels_version`/
  `eg_autolag`; return `(computation_status, stale_reason, pairs[])`. Never calls `stats.py` or
  `multipletests` — persisted-file reads only (see the ADR-8 Amendment).

### `api/models/pairs.py` (new)

- Pydantic models: `PairSummary`, `PairDetail`, `PairStatus` (enum: `ok | insufficient_overlap |
  coin_unavailable`), `HalfLifeState` (enum: `computed | not_mean_reverting`), `SpreadPoint`.

### `api/routers/pairs.py` (new)

- `GET /api/pairs` → `PairSummary[]`. `GET /api/pairs/{a}/{b}` → `PairDetail` (spread series
  included); 404 if `a` or `b` not in the universe, 422 if malformed.

### `web/components/pairs/*` (new)

- `PairsTable.tsx` (sortable, default BH-p ascending, insufficient rows sorted last, excluded from
  sort-by-p when not computed), `PairDetailView.tsx` (spread chart via `lightweight-charts`, both EG
  directions, Johansen block, half-life state, z-score, sample-window disclosure banner).

---

## 11. API Surface

### `GET /api/pairs`

Query: none (v1 — always returns the full current universe's pairs).

**Amended post-Stage-0 (ADR-8 Amendment — precompute + staleness)**: the response now carries a
top-level `computation_status` (`fresh | stale | results_unavailable`) and `stale_reason` (string,
`null` unless `stale`). `pairs: []` only when `computation_status == "results_unavailable"`;
otherwise `pairs` is the full last-known-good array (still 200, never 404/503 on staleness).

```json
{
  "generated_utc": "2026-09-25T18:00:00Z",
  "computation_status": "fresh",
  "stale_reason": null,
  "universe_size": 18,
  "pair_count": 153,
  "min_overlap_days": 365,
  "pairs": [
    {
      "coin_a": "BTC",
      "coin_b": "ETH",
      "status": "ok",
      "reason": null,
      "overlap_days": 1820,
      "sample_start": "2021-01-01",
      "sample_end": "2026-09-24",
      "eg_p_raw": 0.014,
      "eg_p_bh": 0.031,
      "eg_direction": "BTC~ETH",
      "eg_p_other_direction": 0.052,
      "johansen": { "trace_stat": 18.2, "crit_value_95": 15.5, "rank_at_least_1": true },
      "half_life": { "state": "computed", "days": 12.4 },
      "z_score": 1.83
    },
    {
      "coin_a": "BTC",
      "coin_b": "NEWLIST",
      "status": "insufficient_overlap",
      "reason": "only 240 days of overlapping history available, need 365",
      "overlap_days": 240,
      "sample_start": "2026-01-20",
      "sample_end": "2026-09-24",
      "eg_p_raw": null, "eg_p_bh": null, "johansen": null, "half_life": null, "z_score": null
    },
    {
      "coin_a": "ETH",
      "coin_b": "DELISTEDCOIN",
      "status": "coin_unavailable",
      "reason": "DELISTEDCOIN: bad_symbol — not found on Hyperliquid market list",
      "overlap_days": null, "sample_start": null, "sample_end": null,
      "eg_p_raw": null, "eg_p_bh": null, "johansen": null, "half_life": null, "z_score": null
    }
  ]
}
```

### `GET /api/pairs/{a}/{b}`

Same per-pair fields as above, plus `spread: SpreadPoint[]` (`{date, spread, z_score}` over the full
sample window), `hedge_ratio` (both directions), and `eg_p_other_direction`'s companion detail
(`eg_stat_other_direction`, etc.). `{a}`/`{b}` are validated against the universe (404 if either is
not a universe member; a pair with `status != "ok"` still returns 200 with `spread: []` and the same
`reason`/status fields as the table row — the detail view is where the user learns *why* a row has
no stats, not just *that* it doesn't).

Status rules: per-pair `status ∈ ok | insufficient_overlap | coin_unavailable`; within `ok`,
`half_life.state ∈ computed | not_mean_reverting`. No field is ever `NaN`, `0` as a stand-in, or
computed from a truncated sample without `reason` disclosure. `eg_p_bh` is `null` for any pair not
included in the BH correction's denominator (i.e. `status != "ok"`). Responses are gzip-compressed
via the existing app-wide `GZipMiddleware`. **Top-level `computation_status ∈ fresh | stale |
results_unavailable`** (ADR-8 Amendment) is a separate, response-level freshness signal — distinct
from per-pair `status` — describing whether the persisted results cache matches the current
universe/price cache; see the ADR-8 Amendment (§3 Architecture Decisions) for the full table.

**Tie-break rule (added post-EXECUTE, RFC-005 EVL cycle 6, 28-09-26, user decision — closes SPEC
AC-4's amendment):** `GET /api/pairs` sorts `ok` rows by `(eg_p_bh, eg_p_raw, coin_a, coin_b)` —
ties on the BH-corrected p-value break on the lower raw p-value, and ties on both break on coin
names alphabetically. `api/analytics/cointegration/pairs_response.py::_sorted_rows` previously
tie-broke on names only, so the API's order did not match the web page's own sort (which already
used raw-p as its first tie-break); the two are now identical. Rows with `status != "ok"` are
sorted separately by coin name and always appended after all `ok` rows, so their `None` statistics
are never part of a tie-break comparison. Covered by two new pytest cases in
`api/tests/routers/test_pairs.py` (ties on corrected p; ties on both p-values).

**Path-param edge cases (added PVL cycle 1, resolves CONCERN-2):**
- **Self-pair (`a == b`)**: `GET /api/pairs/{a}/{a}` returns **422** (`{"detail": "a and b must be different coins"}`) — a coin is never cointegration-tested against itself; this is never silently treated as a degenerate/self-cointegrated `ok` pair.
- **Ticker case-sensitivity**: matching is **case-insensitive** — both `{a}` and `{b}` are normalized to uppercase (`.upper()`) before universe lookup, so `GET /api/pairs/btc/eth` and `GET /api/pairs/BTC/ETH` resolve identically. The universe file itself stores uppercase tickers only; normalization happens once, in the router, before any lookup.
- **Unknown ticker**: after uppercasing, if either `{a}` or `{b}` is not a member of the loaded universe, return **404** (`{"detail": "<TICKER> is not in the pair-screener universe"}`). This is unchanged from the original plan's "404 on non-member symbol" behavior — restated here for precedence against the self-pair check (self-pair is checked first, since `a == b` is a structural error independent of universe membership).

---

## 12. Infrastructure Deployment

Local only, unchanged. The deep-fetch script is user-run, occasionally (no scheduler, per SPEC Out
Of Scope).

## 12b. Storage Schema (Parquet files)

**Amended post-Stage-0 (ADR-8 Amendment)**: the original "no results cache" line below no longer
holds — see the new `api/data/cache/pairs/` rows.

| Path | Columns | Write mode |
|---|---|---|
| `cache/ohlcv/{SYMBOL}/1d.parquet` (existing) | unchanged shape; extended with deeper history for universe coins | cache-first merge (existing `ccxt_adapter`/`cache.write_ohlcv` behavior, unmodified) |
| `api/data/pairs_universe.json` (new) | flat list/object of ticker strings | hand-edited only; no code writes it |
| `api/data/cache/pairs/results.parquet` (new, git-ignored) | one row per pair: all `PairSummary` fields (+ spread data, layout decided at RFC-003 Stage 0) | written only by `api/scripts/compute_pairs.py`; read-only to the router |
| `api/data/cache/pairs/spreads/{A}_{B}.parquet` (new, git-ignored, only if RFC-003 Stage 0 picks the per-pair-file layout) | `date, spread, z_score` per pair | written only by `compute_pairs.py`; read-only to the router |
| `api/data/cache/pairs/provenance.json` (new, git-ignored) | `computed_at, universe, per_coin_last_bar_date, per_coin_bar_count, statsmodels_version, eg_autolag` | written only by `compute_pairs.py`; read-only to the router |

`api/data/cache/pairs/` falls under the existing blanket `api/data/cache/*` gitignore rule
(confirmed against `.gitignore`) with no carve-out needed — unlike `liqtide/`/`narrative/`, this
cache is fully regenerable from `compute_pairs.py` and should never be git-tracked.

---

## 13. Phased Delivery Plan

### Current Status

All RFCs ✅ VERIFIED (28-09-26) — see the Status Strip above. This plan is archived to
`process/features/cointegration-screener/completed/pair-screener_25-09-26/`.

Each RFC below carries: Summary, Dependencies, Stage 0 (where applicable), Stages, Post-Phase
Testing, Verification Checklist, Acceptance Criteria, What's Functional Now, Ready For,
Implementation Checklist.

## 14. Features List (MoSCoW)

| ID | Feature | Priority |
|---|---|---|
| F-1 | Universe file + deep-fetch script | Must |
| F-2 | Stats engine (log prices, static OLS, both-direction EG, Johansen, AR(1) half-life, z-score, BH) | Must |
| F-3 | `GET /api/pairs` table endpoint | Must |
| F-4 | `GET /api/pairs/{a}/{b}` detail endpoint | Must |
| F-5 | `/pairs` table page, default BH-p sort, explicit insufficient/unavailable rows | Must |
| F-6 | Per-pair detail page: spread chart, both EG directions, Johansen, half-life state | Must |
| F-7 | Screener isolation proof (diff + suite re-run) | Must |
| F-8 | Playwright `pairs.spec.ts` on seeded fixtures | Must |
| F-9 | Perf-smoke on real deep-fetched cache | Should |
| F-10 | Real-cache user walkthrough (manual, known-gap in this container) | Should |
| F-11 | Combined "tradability score" | Won't |
| F-12 | Auto/algorithmic universe selection, browser universe editor | Won't |

---

## 15. RFCs

### RFC-001: Universe file + loader + deep-fetch script

**Summary**: hand-editable universe, its loader, and the deep-fetch script; add the `statsmodels`
dependency and smoke-check it before any stats code exists.
**Dependencies**: none.

**Stage 0: Pre-Phase Research** (present and STOP)
- Run `uv add --project api "statsmodels>=0.14"`; confirm `api/pyproject.toml` and `api/uv.lock`
  are updated; run a cheap-local golden smoke check: import `statsmodels.tsa.stattools.coint`,
  `statsmodels.tsa.vector_ar.vecm.coint_johansen`, `statsmodels.stats.multitest.multipletests`, and
  print each function's signature to confirm the exact keyword arguments this plan's ADRs assume
  (`det_order`, `k_ar_diff`, `method='fdr_bh'`).
- Propose the concrete coin universe for user confirmation: **BTC, ETH, SOL, HYPE, XRP, DOGE, ADA,
  AVAX, LINK, LTC, BCH, DOT, SUI, NEAR, APT, ARB, OP, ATOM** (18 coins → C(18,2) = 153 pairs) — large,
  liquid, non-stablecoin perps chosen for likely Hyperliquid listing and market depth. Each ticker
  must resolve via `ccxt_adapter.resolve_market_symbol` against the live Hyperliquid market list
  before being accepted into `pairs_universe.json`; any that fail resolution are reported and either
  dropped or swapped per user direction (this is the SPEC's AC-12 "unfetchable coin" path exercised
  at Stage 0, not deferred silently to runtime).
- Confirm `pairs_universe.json`'s exact shape (flat array vs. `{"coins": [...]}`) — recommend
  `{"coins": [...]}` for parity with `watchlist.py`'s reader shape, while keeping the file itself
  physically separate (AC-9).
- Read `ccxt_adapter.fetch_ohlcv`'s deep-fetch path (`limit=` argument, cache-merge behavior) and
  confirm the coverage-table script pattern from `backfill_primaries.py`.
- **Deep-fetch mechanism (added PVL cycle 1, resolves CONCERN-1 per feasibility VERDICT: VIABLE —
  see `pair-screener_FEASIBILITY_25-09-26.md`)**: `backfill_pairs_universe.py` must call the
  EXISTING public `ccxt_adapter.fetch_ohlcv(symbol, "1d", since=<epoch-0 or a fixed date safely
  before 2023>, limit=5000)` with an EXPLICIT early `since` for every universe coin — never
  `since=None`. An explicit `since` bypasses the adapter's warm-cache skip and most-recent-N
  default (against an already-populated cache, `since=None` would only top up forward from the
  last cached timestamp). The result merges into the existing shallow cache (BTC/ETH/HYPE/SOL at
  ~501 bars today) via the adapter's own `pd.concat` + `cache.write_ohlcv` sort/dedupe path — no
  cache reset/clear step is needed and `ccxt_adapter.py` stays fully read-only (its public
  signature already supports this call shape; no code change required).
- **Defensive pagination for a capped response**: Hyperliquid's `candleSnapshot` may silently cap
  the response below the requested window for an old `since`, and ccxt has no built-in pagination
  loop for this exchange. The script must detect a result whose length equals the returned cap and,
  if so, page forward by re-calling `fetch_ohlcv` with `since` advanced to the last bar's
  timestamp, repeating until either the cap is no longer hit or `now` is reached.
- **Per-coin logging**: the script must print a per-coin table of resulting bar count and first
  available date for every universe coin — this is the mechanical evidence E1 requires in the
  RFC-001 phase report.

**Stages**
1. `api/data/pairs_universe.json` with the user-confirmed, market-resolved coin list.
2. `api/data/pairs_universe.py` (or similar) — small loader: read JSON → list of tickers → warn on
   duplicates/known-stablecoin tickers at load time (does not import `watchlist.py`).
3. `api/scripts/backfill_pairs_universe.py` — mirrors `backfill_primaries.py`: no CLI args, calls
   `ccxt_adapter.fetch_ohlcv(symbol, "1d", since=<explicit early UTC date, e.g. 2020-01-01>,
   limit=DEEP_LOOKBACK_LIMIT)` per universe coin, with defensive cap-hit pagination, prints a
   coverage table. **(Corrected post-RFC-001, per `pair-screener_RFC-001_REPORT_25-09-26.md` → Plan
   Deviations: an explicit `since` is required — `since=None` only tops up forward from the last
   cached bar against an already-populated cache and never reaches deep history. This text was stale
   relative to the as-built script even before this amendment; corrected here, not re-litigated.)**

**Post-Phase Testing**
- Test file: `api/tests/data/test_pairs_universe.py` — pair-enumeration unit test (AC-1: `C(n,2)`
  rows, no dupes); loader-isolation test (AC-9: `pairs_universe` module does not import
  `api/data/watchlist.py`, asserted via module `sys.modules`/import-graph inspection, not just "no
  shared function calls").
- Test file: `api/tests/scripts/test_backfill_pairs_universe.py` — with `isolated_cache`:
  (a) seed a SHALLOW pre-existing cache (501 bars, mirroring the real BTC/ETH/HYPE/SOL state),
  mock the exchange client to return deep history when called with an explicit `since`, and
  assert the post-backfill cache's row count AND first available date actually reach the mocked
  deep start — not merely "row count increased" (resolves CONCERN-1 / E2); (b) assert the script's
  exchange calls never use `since=None` (inspect the mock's call args); (c) a second mocked test
  where the exchange response length equals a simulated cap, asserting the script pages forward
  (re-calls with an advanced `since`) rather than silently stopping short; (d) never touches
  `api/data/watchlist.json` (AC-11).
- Real-run hybrid verification (precondition: real Hyperliquid reachability from wherever RFC-001
  actually runs — user-PC if this container's egress is blocked, per the regime/narrative
  precedent): run the real script once and paste the per-coin bars-per-coin/first-date log into the
  RFC-001 phase report. Known-gaps carried from the feasibility VERDICT (recorded, not silently
  dropped): (1) whether Hyperliquid's real cap-hit behavior matches the mocked pagination test —
  the mocked test proves the script's OWN pagination logic is correct, not the live response shape;
  (2) real per-coin listing dates are unverified until this real run happens; (3) bulk
  rate-limit/backoff behavior under 18 sequential deep-fetch calls is unverified.
- Run: `uv run --project api pytest api/ -q` — full suite green, no regressions vs current baseline.
- Manual: run `uv run --project api python api/scripts/backfill_pairs_universe.py` once for real.
- Verification query:
  ```
  uv run --project api python -c "import duckdb; print(duckdb.sql(\"select * from (select '<SYMBOL>' as symbol, count(*) as rows, min(date) as first, max(date) as last from 'api/data/cache/ohlcv/<SYMBOL>/1d.parquet')\"))"
  ```
  run per universe coin (or a small wrapper script printing all 18 in one pass).
- Error scenarios: one universe coin resolved to `bad_symbol` at Stage 0 time is excluded from
  `pairs_universe.json` with the reason recorded in the phase report (not silently dropped — the
  Stage 0 finding itself is the disclosure).

**Verification Checklist**
- [x] Manual test passed (deep-fetch script run once for real — see phase report)
- [x] Data verified in storage (per-coin coverage query output pasted — see phase report)
- [ ] Error handling confirmed (a `bad_symbol` universe candidate excluded with reason recorded)
- [ ] User confirmed working (reviewed universe list + coverage table)

**Acceptance Criteria**: AC-1, AC-9, AC-11 (partial — deep-fetch mechanics; full AC-11 proof
completes at RFC-005's isolation re-run), AC-12 (partial — Stage 0 resolution check).
**What's Functional Now**: the universe exists, is deeply cached, and its provenance is documented.
**Ready For**: RFC-002.

**Implementation Checklist**
- [x] Stage 0 findings (statsmodels smoke check + universe list + market resolution) presented; user approved
- [x] `statsmodels>=0.14` added; `arch` confirmed NOT added (25-09-26, statsmodels 0.15.0 — see RFC-001 Stage 0 report)
- [x] `pairs_universe.json` + loader + isolation test
- [x] `backfill_pairs_universe.py` (explicit early `since`, never `since=None`; defensive
  cap-hit pagination; per-coin bars/first-date log) + tests (shallow-cache-collision, no-since=None
  assertion, mocked cap-hit pagination)
- [x] Real deep fetch run; per-coin bars-per-coin/first-date log + coverage table reviewed; three
  feasibility-VERDICT known-gaps (live cap behavior, real listing dates, rate-limit/backoff)
  recorded in the phase report
- [x] `uv run --project api pytest api/ -q` green

### RFC-002: Stats engine

**Summary**: `api/analytics/cointegration/stats.py` per ADR-1..ADR-6.
**Dependencies**: RFC-001 (universe + deep cache + statsmodels).

**Stage 0**: read `statsmodels.tsa.stattools.coint`, `coint_johansen`'s exact return shapes (via the
RFC-001 smoke check output); confirm the AR(1) half-life regression's exact `statsmodels.OLS` (or
`numpy.polyfit`) call shape; present the four planned synthetic golden fixtures (cointegrated pair,
non-cointegrated pair, non-mean-reverting pair, short-overlap pair) with their hand-derived expected
values before writing any test. STOP.

**Stage 0 findings and user decisions (25-09-26, see `pair-screener_RFC-002-stage0_REPORT_25-09-26.md`
for full evidence) — all approved in chat:**
- **D1 — performance**: see the ADR-8 Amendment above (precompute after backfill). `stats.py` keeps
  `coint`'s default `autolag='aic'`, exposed as a single named constant `EG_AUTOLAG = "aic"`.
- **D2 — ComplexWarning**: `coint_johansen`'s `j.eig` is `complex128` but the largest imaginary part
  is exactly `0.0` on all 153 real pairs and all four fixtures — the cast to real discards nothing.
  Approved: suppress `numpy.exceptions.ComplexWarning` only inside a `warnings.catch_warnings()`
  block scoped tightly around the `coint_johansen` call (comment pointing at this ADR), plus a guard
  — if `max(abs(j.eig.imag)) > 1e-9`, the pair's Johansen result is refused (treated as numerically
  unstable, not a silent number) rather than cast. This is never a blanket warning suppression.
- **D3 — which direction's spread drives the z-score/half-life/detail chart**: the lower-p-value EG
  direction (the rank-driving, min-p direction per ADR-2b) — not a fixed convention, not both
  averaged. `PairStatsResult.spread` and `PairStatsResult.eg_rank_direction` are the same direction.
- **D4 — result shape and fixtures**: the `EGResult`/`JohansenResult`/`HalfLife`/`PairStatsResult`
  dataclass shape and all four golden fixtures (§3 of the Stage 0 report) approved as designed,
  including fixture (c) [not-mean-reverting] intentionally NOT asserting on Johansen (its explosive
  spread produces a spurious `rank_at_least_1=True` — a known, documented property of the test, not
  a bug to fix). Golden-value provenance follows E4 (behavior-reference / validate-contract): EG
  p-values and the Johansen trace statistic use a reviewed pinned-statsmodels-output baseline
  (asymptotic test statistics, not independently hand-derivable); hedge ratio, AR(1) β, half-life
  and z-score use independent closed-form numpy golden values, checked separately from `stats.py`.

**Stages**
1. `compute_pair_stats(df_a, df_b, symbol_a, symbol_b) -> PairStatsResult` — inner-join on date,
   gate on `MIN_OVERLAP_DAYS = 365` (named constant), else `insufficient_overlap` with `reason`
   naming available/required day counts (AC-2).
2. Log-price transform (ADR-1); static OLS hedge ratio both directions (ADR-2a).
3. `coint()` both directions using the named `EG_AUTOLAG = "aic"` constant (D1); rank by min-p;
   record both p-values and which direction is the rank-driving one (ADR-2b, D3).
4. `coint_johansen(data, det_order=0, k_ar_diff=1)` inside a scoped `ComplexWarning` suppression
   with the `max|imag(eig)| > 1e-9` numerical-instability guard (D2) → trace stat (r=0), 95%
   critical value, `rank_at_least_1` boolean (ADR-5).
5. AR(1) half-life: OLS of `Δspread` on lagged `spread`; `HL = −ln(2)/β`; `β ≥ 0` →
   `not_mean_reverting` state, no number (ADR-3).
6. Z-score: latest spread vs. full-sample mean/std (ADR-4).
7. Per-pair `status`/`reason` per ADR-7 (`ok` / `insufficient_overlap` / `coin_unavailable`).

**Post-Phase Testing**
- Test file: `api/tests/analytics/test_cointegration_stats.py` — golden values on the four Stage-0
  fixtures: (a) synthetic cointegrated pair (constructed as `B = 2*A + stationary_noise` in
  log-space) — expect both-direction EG p-values low, Johansen `rank_at_least_1=True`, half-life
  `computed` with a plausible value; (b) synthetic random-walk, non-cointegrated pair — expect high
  EG p-values, Johansen `rank_at_least_1=False`; (c) synthetic pair with a trending (non-stationary)
  spread — expect `not_mean_reverting` (β ≥ 0), no half-life number; (d) synthetic pair with < 365
  days overlap — expect `insufficient_overlap`, no stats computed, `reason` names both day counts.
  Also: no NaN/inf in any numeric output field for any fixture; z-score/half-life untouched for
  `insufficient_overlap`/`coin_unavailable` pairs (AC-8). ComplexWarning guard test (D2): a
  synthetic case forcing `max|imag(eig)| > 1e-9` (or a monkeypatched `coint_johansen` return) asserts
  the pair's Johansen result is refused, not silently cast; a normal fixture asserts the warning is
  suppressed (no warning escapes `pytest`'s default `-W error` posture, if enabled) and the trace/crit
  values are the same float64 numbers as before the suppression was added.
- Run: `uv run --project api pytest api/tests/analytics/test_cointegration_stats.py -q`, then the
  full suite.
- Verification query: a small script (or pytest `-s` print) runs `compute_pair_stats` for 3-5 real
  pairs from the live deep-fetched cache (e.g. BTC-ETH, BTC-SOL, a thin-overlap pair if one exists in
  the confirmed universe) and prints the full result — pasted into the phase report as a live sanity
  check (Hybrid, not asserted equal to any external reference — there is no independent oracle for
  real crypto pairs, unlike the regime dashboard's LiqTide cross-check).

**Verification Checklist**
- [ ] Manual test passed (live 3-5 pair sanity print reviewed — see phase report)
- [x] Data verified (golden-value test output + live print pasted into report)
- [x] Error handling confirmed (all four fixture branches + no-NaN assertion in tests)
- [ ] User confirmed working (golden values + live sanity print reviewed and approved)

**Acceptance Criteria**: AC-2, AC-3, AC-5 (BH itself is RFC-003, but the raw-p-value input this
stage produces is what RFC-003's BH correction consumes), AC-6, AC-8.
**What's Functional Now**: every pair's full statistical result is computable from cache.
**Ready For**: RFC-003.

**Implementation Checklist**
- [x] Stage 0 findings (statsmodels return shapes + four fixture designs) presented; user approved
- [x] `compute_pair_stats` + golden fixture tests (all four branches)
- [x] No-NaN/no-stand-in assertion tests
- [x] Live 3-5 pair sanity print run and pasted into report
- [x] Full `pytest` green; RFC-001 tests unchanged and green

### RFC-003: Compute/persist script + Pydantic models + response serializer + router (AMENDED — see ADR-8 Amendments)

**Summary**: `api/scripts/compute_pairs.py` (new), `api/models/pairs.py`,
`api/analytics/cointegration/pairs_response.py` (compute path + read path), `api/routers/pairs.py`
per §11 and ADR-8 (Amendments)/ADR-9. **Persistence, staleness-detection and the compute script now
live in this RFC** — the cleaner split, since `pairs_response.py`'s orchestration layer already
owned "assemble the full-universe response" before this amendment, and the router's read-path
contract (provenance comparison, `computation_status`) is inseparable from the response shape it
already builds. `stats.py` (RFC-002) stays a pure, persistence-unaware function library — unchanged.
**Dependencies**: RFC-002.

**Stage 0**: read `api/models/regime.py` and `api/routers/regime.py` for the existing
Pydantic-model-plus-router pattern (typed status enums, gzip via app middleware, no new CORS/auth);
confirm `api/main.py`'s `include_router` wiring point; present the exact `PairSummary`/`PairDetail`
field lists (§11, including the amended `computation_status`/`stale_reason` fields) for user
confirmation. **Also confirm the path-param edge-case contract added at PVL cycle 1 (resolves
CONCERN-2, §11): self-pair (`a == b`) → 422; ticker matching normalized to uppercase before
universe lookup (case-insensitive); unknown ticker (after normalization) → 404, self-pair check
takes precedence over the unknown-ticker check.** **Decide and record the exact spread-series
storage layout** (single list-column in `results.parquet` vs. one
`api/data/cache/pairs/spreads/{A}_{B}.parquet` per pair — see the ADR-8 Amendment) — whichever keeps
the detail endpoint's read O(1) file lookups. STOP.

**Stages**
1. `api/models/pairs.py` — `PairStatus`, `HalfLifeState` enums; `PairSummary`, `PairDetail`,
   `SpreadPoint` models per §11, plus `ComputationStatus` enum (`fresh | stale |
   results_unavailable`) and the top-level `computation_status`/`stale_reason` response fields.
2. `api/analytics/cointegration/pairs_response.py` — **compute path** (called only by
   `compute_pairs.py`): enumerate `C(n,2)` pairs from the loaded universe; call
   `stats.compute_pair_stats` per pair; collect `ok`-pair raw EG p-values (min-p direction);
   `multipletests(raw_ps, method='fdr_bh')`; assemble `PairSummary[]` (every pair present, per
   AC-1) + per-pair spread data; write `results.parquet` + `provenance.json` (ADR-8 Amendment
   schema — `computed_at`, `universe`, `per_coin_last_bar_date`, `per_coin_bar_count`,
   `statsmodels_version`, `eg_autolag`). **Read path** (called by the router): load
   `results.parquet` + `provenance.json`; compare provenance against the current
   `pairs_universe.json` and each universe coin's current OHLCV cache; return
   `(computation_status, stale_reason | None, pairs: PairSummary[])`. The read path never calls
   `stats.py` or `multipletests` — it only reads persisted files.
3. `api/scripts/compute_pairs.py` (new) — no CLI args; calls `pairs_response.py`'s compute path;
   prints a summary (pair count, elapsed seconds, any `coin_unavailable`/`insufficient_overlap`
   counts) — mirrors `backfill_pairs_universe.py`'s no-args, idempotent, printed-summary pattern.
   Documented in §19 Ops Runbook as the second manually-run script.
4. `api/routers/pairs.py` — `GET /api/pairs`, `GET /api/pairs/{a}/{b}`, both calling
   `pairs_response.py`'s read path; server-side universe membership validation (404 on non-member
   symbol, 422 on malformed) — path params uppercased before lookup (case-insensitive matching);
   self-pair (`a == b`, post-uppercase) returns 422 before the universe-membership check runs (§11
   path-param edge cases). `results_unavailable`/`stale` are always 200 responses (never 404/503)
   with the `computation_status` field carrying the signal — see the ADR-8 Amendment table.
5. `api/main.py` — one additive `app.include_router(pairs.router)` line; no other change to this
   file.

**Post-Phase Testing**
- Test file: `api/tests/scripts/test_compute_pairs.py` (new) — with `isolated_cache`: running
  `compute_pairs.py` against a small seeded universe writes `results.parquet` with every pair
  present (AC-1) and a `provenance.json` whose `universe`/`per_coin_last_bar_date`/`per_coin_bar_count`
  match the seeded cache exactly; BH correction applied only across `ok` pairs (AC-5, golden
  raw-p-value set with hand-computed expected BH-adjusted set, mirroring the SPEC's AC-5
  language); re-running after adding a coin to the universe changes `provenance.json`'s `universe`
  field (proves staleness detection has something real to compare against).
- Test file: `api/tests/routers/test_pairs.py` — table shape read from a pre-seeded
  `results.parquet` (every pair present, AC-1); default response has no null-as-stand-in outside
  the documented `insufficient_overlap`/`coin_unavailable` cases; detail endpoint 404s on a
  non-universe symbol, 422 on malformed input; Johansen always present alongside EG for `ok`
  pairs, never merged (AC-6); `isolated_cache` used throughout.
- **Staleness/missing-results tests (new, ADR-8 Amendment; 5th case added at PVL supplement,
  26-09-26, closes Execute-Agent Instruction E7)**: (a) no `results.parquet`/`provenance.json`
  present → `GET /api/pairs` returns 200, `computation_status: "results_unavailable"`,
  `pairs: []` (never 404/503, never a stack trace); (b) `provenance.json` present but
  `pairs_universe.json` now names a coin not in `provenance.universe` → `stale`, `stale_reason`
  names the universe mismatch, `pairs` still returns the last-known-good rows; (c)
  `provenance.json` present but a universe coin's `cache/ohlcv/{SYMBOL}/1d.parquet` now has a
  later max-date than `per_coin_last_bar_date` → `stale`, `stale_reason` names the coin and the
  date gap; (d) fresh provenance matching current universe + cache → `fresh`, no `stale_reason`;
  (e) **NEW** — `provenance.json`'s `statsmodels_version` differs from the installed
  `statsmodels.__version__`, OR `provenance.json`'s `eg_autolag` differs from the current
  `stats.py::EG_AUTOLAG` constant → `stale`, `stale_reason` names which field mismatched and both
  the recorded and current value (e.g. "computed with statsmodels 0.15.0; installed 0.16.1 — re-run
  compute_pairs.py").
- **Compute-path network-isolation test (NEW, added at PVL supplement, 26-09-26, closes
  Execute-Agent Instruction E5)**: monkeypatch/patch `ccxt_adapter.fetch_ohlcv` (or the underlying
  exchange client) to raise on any call; run `compute_pairs.py`'s compute path over a small
  `isolated_cache`-seeded universe; assert the run completes successfully with no exception —
  proves the compute path never reaches the network, only `cache.read_ohlcv`.
- **Pairs-cache path isolation test (NEW, added at PVL supplement, 26-09-26, closes Execute-Agent
  Instruction E6)**: run `compute_pairs.py` against `isolated_cache` (a redirected `CACHE_ROOT`);
  assert `results.parquet`/`provenance.json` land under the isolated `CACHE_ROOT / "pairs"`
  directory (via `cache.pairs_results_path()`/`cache.pairs_provenance_path()`), never under the
  developer's real `api/data/cache/pairs/`.
- Path-param edge-case tests (added PVL cycle 1, resolves CONCERN-2): `GET /api/pairs/{a}/{a}`
  (self-pair, e.g. `BTC/BTC`) returns 422; `GET /api/pairs/btc/eth` (lowercase) resolves
  identically to `GET /api/pairs/BTC/ETH` (case-insensitive match, same response body); an unknown
  ticker after uppercasing (e.g. `GET /api/pairs/BTC/ZZZZ`) returns 404; a self-pair with an
  unknown ticker (e.g. `GET /api/pairs/zzzz/ZZZZ`) returns 422, not 404 (self-pair check
  precedence).
- **Read-path timing gate (Fully-Automated, replaces the old on-request perf-smoke)**: time
  `GET /api/pairs` warm (API running, `results.parquet` pre-seeded/pre-computed) via a script or
  manual `curl -w "%{time_total}"`; assert it is comfortably under the p95 < 3s target — a
  persisted-file read is expected to be milliseconds, so this is a real but trivially-met
  regression guard against an accidental future recompute-on-read bug, not a performance risk in
  itself.
- **Compute-script runtime record (informational, not gated)**: run `compute_pairs.py` once
  against the real deep-fetched cache; paste its elapsed time into the phase report (expected ~46
  s per the RFC-002 Stage 0 measurement, `EG_AUTOLAG="aic"`); this is evidence, not a pass/fail
  threshold — the whole point of the ADR-8 Amendment is that this cost is paid once, offline, by
  the user, not per-request.
- Run: `uv run --project api pytest api/tests/routers/test_pairs.py api/tests/scripts/test_compute_pairs.py -q`, then full suite.
- Verification: run `compute_pairs.py` once for real, then `curl "http://127.0.0.1:8000/api/pairs" | python -m json.tool | head -80` and
  `curl "http://127.0.0.1:8000/api/pairs/BTC/ETH" | python -m json.tool`; paste `provenance.json`'s
  contents into the phase report.

**Verification Checklist**
- [x] Manual test passed (curl both endpoints against real cache after running `compute_pairs.py`
  — see phase report)
- [x] Data verified (row counts match universe's `C(n,2)`; BH-corrected values spot-checked;
  `provenance.json` contents pasted)
- [x] Error handling confirmed (404/422 tests; `coin_unavailable`/`insufficient_overlap` rows
  render; `results_unavailable`/`stale` states tested and rendered)
- [ ] User confirmed working (read-path timing + compute-script runtime + endpoint output reviewed)

**Acceptance Criteria**: AC-1, AC-4 (sort ordering is RFC-004's UI concern but is validated here at
the data level — BH-p ascending is the array's natural consumption order), AC-5, AC-6, AC-8.
**What's Functional Now**: both endpoints serve real, precomputed data with an explicit
freshness/staleness signal.
**Ready For**: RFC-004.

**Implementation Checklist**
- [x] Stage 0 findings (field lists incl. `computation_status`/`stale_reason` + spread-storage
  layout decision) presented; user approved
- [x] `compute_pairs.py` + compute-path `pairs_response.py` + BH correction + provenance write +
  tests
- [x] Read-path `pairs_response.py` (provenance comparison, `fresh`/`stale`/`results_unavailable`)
  + tests (all four states)
- [x] Router + 404/422 handling (incl. self-pair 422, case-insensitive uppercase matching,
  unknown-ticker 404, self-pair-precedence-over-unknown-ticker) + tests
- [x] `api/main.py` one-line registration
- [x] Read-path timing gate green; compute-script runtime recorded (informational)
- [x] Full `pytest` green; regime/screener router tests unchanged and green

### RFC-004: Web table + detail view

**Summary**: `/pairs` table page + per-pair detail page per ADR-9/§7.
**Dependencies**: RFC-003.

**Stage 0**: read `web/components/regime/ComponentPanel.tsx`, `web/components/screener/
DeadDataNotice.tsx`, `web/lib/api/regime.ts` (fetch pattern), `web/lib/format-unavailable-reason.ts`
(existing gap-state-to-text formatter) to confirm reuse points; confirm exact detail-page route
shape (`web/app/pairs/[a]/[b]/page.tsx` vs. a query-param route) and the sort/table library
(recommend plain a sortable `<table>`, no new dependency, matching the screener's own table). STOP.

**Stages**
1. `web/lib/types/pairs.ts`, `web/lib/api/pairs.ts` (reuse the existing `getJson` pattern from
   `regime.ts`).
2. `web/lib/format-pairs-value.ts` — p-value, half-life, z-score, sample-window formatters (mirrors
   `format-regime-value.ts`).
3. `web/components/pairs/PairsTable.tsx` — default sort BH-p ascending; `insufficient_overlap`/
   `coin_unavailable` rows render via `DeadDataNotice`-style treatment, sorted to the bottom,
   excluded from the sort key entirely (not sorted as `Infinity` — a structurally separate group).
   Sample length (`overlap_days`) shown per row (AC-1, AC-2, AC-4).
4. `web/components/pairs/PairDetailView.tsx` — spread chart (`lightweight-charts`, one series over
   `sample_start..sample_end`), both EG directions (with the disclosed mild-optimism-bias copy per
   ADR-2b), Johansen block, half-life state (`computed` value or `not_mean_reverting` banner),
   current z-score, and a persistent "whole-history / in-sample diagnostic, not a live signal"
   banner (ADR-2c) (AC-6, AC-7).
5. `web/app/pairs/page.tsx`, `web/app/pairs/[a]/[b]/page.tsx`; link from `web/app/page.tsx`.

**Post-Phase Testing**
- vitest files under `web/lib/__tests__/` (formatter golden tests: p-value display, half-life
  `not_mean_reverting` banner text, sample-window text) and `web/components/pairs/__tests__/`
  (table renders `C(n,2)` rows from a fixture response; insufficient/unavailable rows render no stat
  columns and the correct reason text; default sort order verified against a shuffled fixture
  (AC-4); detail view renders both EG directions + Johansen simultaneously, never merged (AC-6);
  injected-fetcher error path renders an explicit unavailable state, not a blank/NaN (AC-8)).
- Run: `pnpm --filter web test`.
- Manual: `uv run --project api uvicorn api.main:app --host 127.0.0.1 --port 8000` +
  `pnpm --filter web dev`; open `http://localhost:3000/pairs`; confirm sort order, insufficient/
  unavailable rows, click into one `ok` pair and one `insufficient_overlap` pair.
- Error scenario: stop the API → page shows a clear notice, not a blank table.

**Verification Checklist**
- [x] Manual test passed (table + two detail pages reviewed against a running API) — agent walkthrough 28-09-26: `/pairs` (153 rows) + `/pairs/DOGE/BCH` + 404/422 detail pages; real data has no `insufficient_overlap` pair, so that detail state is covered by vitest only
- [x] Data verified (row values cross-checked against RFC-003's curl output) — top rows and DOGE/BCH detail match the RFC-003 report and live `GET /api/pairs`
- [x] Error handling confirmed (API-down notice; insufficient/unavailable rows render correctly) — API-down notice seen live; non-ok rows proven by vitest
- [ ] User confirmed working (table sort + detail views reviewed and approved)

**Acceptance Criteria**: AC-2 (row rendering), AC-4, AC-6, AC-7 (chart date range vs. displayed
sample window — proven fully in RFC-005's Playwright spec, spot-checked manually here), AC-8.
**Ready For**: RFC-005.

**Implementation Checklist**
- [x] Stage 0 findings (reuse points + route shape + table approach) presented; user approved
- [x] Types + API client + formatters + tests
- [x] `PairsTable` + tests
- [x] `PairDetailView` + tests
- [x] Pages wired + linked from home; manual walkthrough done
- [x] `pnpm --filter web test` green (153 passed / 19 files; tsc exit 0)

### RFC-005: End-to-end proof + isolation proof

**Summary**: prove the real frontend/backend boundary and prove the momentum screener is untouched,
per `all-tests.md`'s Standing Lesson (green ≠ verified) and the SPEC's AC-9/AC-10.
**Dependencies**: RFC-004.

**Stages**
1. Extend `api/scripts/seed_e2e_cache.py`'s manifest with a `pairs` fixture section: synthetic
   deep-history OHLCV (written through the same `cache.write_ohlcv` function the adapter uses, per
   `all-tests.md` Standing Lesson item 7 — never hand-rolled) for a small fixture universe (e.g.
   4-5 symbols) including at minimum: one constructed-cointegrated pair, one non-cointegrated pair,
   and one thin-overlap (`< MIN_OVERLAP_DAYS`) pair — plus a `pairs_universe.json` override path
   (`PAIRS_UNIVERSE_PATH` env var, following the `SCREENER_WATCHLIST_PATH`/`SCREENER_CACHE_ROOT`
   override precedent) so the E2E run never touches the real universe file. **Amended post-Stage-0
   (ADR-8 Amendment)**: the seeder must also produce PRECOMPUTED results — either by calling
   `pairs_response.py`'s compute path directly on the fixture universe/cache (preferred — same
   code path as production, no duplicate logic) and writing the fixture
   `results.parquet`/`provenance.json` under the `PAIRS_UNIVERSE_PATH`-scoped cache root, or by
   invoking `compute_pairs.py` itself against the seeded fixture cache. Whichever is chosen, the
   seeder must guarantee `computation_status == "fresh"` for the seeded fixture before
   `pairs.spec.ts` runs — an E2E spec asserting real table rows against a `results_unavailable`
   fixture would be a false-negative test, not a proof.
2. `web/e2e/pairs.spec.ts` — table renders the fixture universe's full pair count; default sort is
   BH-p ascending; the thin-overlap row shows its explicit reason and no stats; clicking an `ok`
   pair opens its detail page where the spread chart's rendered date range matches the displayed
   sample-window text (AC-7, proven end-to-end here, not just spot-checked); Johansen and EG both
   visible simultaneously on a pair seeded to disagree (AC-6); zero console errors.
3. **Isolation proof** (AC-9, AC-10, AC-11): re-run `uv run --project api pytest api/ -q` (full
   suite, all momentum-screener + regime + narrative tests included) and `pnpm --filter web test` +
   `cd web && pnpm test:e2e` (both `screener.spec.ts` and the new `pairs.spec.ts`) — all green, no
   regressions. Run `git diff --stat -- api/routers/screener.py api/data/watchlist.py
   web/app/screener/ api/analytics/regime/` and confirm the output is empty (zero lines changed).
   Paste both the diff command and its (empty) output into the phase report as the AC-10 proof
   artifact.
4. **Real-cache user walkthrough** (AC per below — manual, known known-gap in the agent container):
   note in the phase report, mirroring the regime dashboard's AC-11 precedent
   (`process/features/cycle-regime/completed/regime-dashboard_24-09-26/`), that this container's
   egress proxy may block live exchange access (confirmed pattern from the regime program: FRED/
   DefiLlama returned 403 through the proxy) — the RFC-001 deep fetch and any subsequent real-cache
   walkthrough of `/pairs` may need to run on the user's own PC if the container cannot reach
   Hyperliquid. Document whichever is true for this session in the phase report; if the container
   *can* reach Hyperliquid, run the walkthrough here and record it; if not, this becomes an explicit
   manual known-gap the plan stays in `active/` for, exactly as regime dashboard's AC-11 did.

**Post-Phase Testing**
- `cd web && pnpm test:e2e` — both `screener.spec.ts` (6, unchanged) and `pairs.spec.ts` (new) green.
- `uv run --project api pytest api/ -q` — full suite green, count compared against RFC-001's
  recorded baseline (no unexplained deselections or failures).
- `git diff --stat` isolation check (Stage 3 above) — empty output required.

**Verification Checklist**
- [x] E2E green (`pairs.spec.ts` + existing `screener.spec.ts`, run twice) — 35/35 twice, 28-09-26
- [x] Data verified (fixture manifest facts pasted; live-cache walkthrough outcome recorded either way)
- [x] Error handling confirmed (thin-overlap and unavailable rows render correctly in the E2E)
- [ ] User confirmed working (isolation diff reviewed; walkthrough outcome accepted)

**Acceptance Criteria**: AC-7 (full proof), AC-9, AC-10, AC-11 (full proof), AC-12 (E2E-level
`coin_unavailable` fixture case).
**What's Functional Now**: the pair screener, end to end, provably isolated from the momentum
screener.

**Implementation Checklist**
- [x] Seeder extended with `pairs` fixture section + override env var; tests for the seeder itself
- [x] `pairs.spec.ts` written and green, run twice
- [x] Full pytest + vitest + both Playwright specs green
- [x] `git diff --stat` isolation proof pasted into phase report (empty output)
- [x] Real-cache walkthrough outcome recorded (ran here, or deferred to user's PC as a known-gap) — API-level re-check ran here; visual walkthrough is RFC-004's

---

## 16. Rules (for this project)

- Python owns all numbers; the frontend formats but never computes (log prices, hedge ratios, EG/
  Johansen stats, half-life, z-score, BH correction all live in `api/analytics/cointegration/`).
- No interpolation or fill of any kind; a pair with insufficient data shows no stats, ever.
- Every statistic that could mislead if wrong gets a hand-computed golden-value test.
- Nothing is drawn on the spread chart beyond the spread series itself.
- The momentum screener's files, cache footprint, and runtime state are read-only to this feature.
- New adapters/modules follow the typed-result, never-raise, cache-first pattern already established
  by `ccxt_adapter.py`.

## 17. Verification (Comprehensive Review)

### Gap Analysis

- The real-cache user walkthrough may be blocked in this agent container by the same egress-proxy
  restriction documented for the regime dashboard (FRED/DefiLlama 403 through the proxy); Hyperliquid
  access is untested as of this plan's writing. RFC-005 documents whichever is true and, if blocked,
  this plan follows the regime-dashboard precedent: stays in `active/` until the user confirms on
  their own PC.
- The perf-smoke threshold (RFC-003 Stage 0) is a plan-time estimate, not yet measured against the
  real ~153-190-pair cache; if the on-request compute model (ADR-8) is too slow, the documented
  fallback (in-process TTL cache) is a same-RFC scope item, not a follow-up plan.
- Engle-Granger's mild optimism bias from taking the min of two directions (ADR-2b) is disclosed in
  the UI copy but not statistically corrected for — this is a deliberate, documented simplification
  for v1, not an oversight.
- No independent external oracle exists for real crypto pair cointegration results (unlike the
  regime dashboard's LiqTide cross-check) — RFC-002's live sanity print is Hybrid/eyeballed, not
  asserted equal to a reference.

### Quality Assessment

| Dimension | Score | Reason |
|---|---|---|
| Fit to north-star | 9/10 | Second independent lens; confidence-over-direction throughout; no verdict |
| Data honesty | 9/10 | Every gap typed (`insufficient_overlap`/`coin_unavailable`); no fill |
| Risk | 6/10 | New heavier dependency (statsmodels); on-request compute cost unmeasured until RFC-003 |
| Testability | 9/10 | Four golden-fixture branches + BH golden test + full isolation proof + E2E |

## 18. Change Management

Any scope change mid-flight: classify (New / Modify / Remove / Scope / Technical / Timeline), list
impacted RFCs and files, choose immediate / schedule / defer, update this plan's ADRs and Status
Strip, then continue. Most likely triggers: the confirmed coin universe changes after RFC-001 Stage
0 market-resolution; perf-smoke forces the ADR-8 fallback; the real-cache walkthrough surfaces a
data-quality issue in a specific pair.

**UPDATE PROCESS item (carried from SPEC Background) — DONE 28-09-26:**
`process/features/cointegration-screener/_GUIDE.md` (its "Key Source Files" section) named
`api/routers/screener.py` and `web/app/screener/` as this feature's target locations — a naming
collision predating this plan (those are the momentum screener's files). Corrected at UPDATE
PROCESS to point at this feature's actual new files
(`api/routers/pairs.py`, `web/app/pairs/`, `api/analytics/cointegration/`, etc.).

### Post-Stage-0 Amendment (RFC-002), 25-09-26

**Trigger**: RFC-002 Stage 0 measured the on-request compute path at ~46 s for 153 pairs against a
p95 < 3 s target (`pair-screener_RFC-002-stage0_REPORT_25-09-26.md`). User decisions in chat
(D1–D4, see the ADR-8 Amendments in §3) reverse ADR-8's original "on-request compute, no results
cache" decision to "precompute after backfill, API reads only," and add a staleness/provenance
contract (numbers are never silently wrong).

**Classification**: Technical (persistence/compute-model change) + Scope (new script, new cache
path, new response fields) — not a New/Remove/Timeline change; the product surface (`/pairs`,
the two endpoints, the SPEC's AC-1..AC-12) is unchanged.

**Impacted RFCs/files**: RFC-002 (Stage 0 decisions D2–D4 recorded, no code-path change — `stats.py`
stays pure); RFC-003 (materially rewritten — adds `compute_pairs.py`, splits
`pairs_response.py` into compute/read paths, adds `computation_status`/`stale_reason`, replaces the
on-request perf-smoke gate with a read-path timing gate + informational compute-script runtime
record); RFC-005 (seeder must also produce precomputed fixture results, not just fixture OHLCV).
New files: `api/scripts/compute_pairs.py`, `api/data/cache/pairs/results.parquet`,
`api/data/cache/pairs/provenance.json` (+ optional per-pair spread files) — all git-ignored under
the existing `api/data/cache/*` rule.

**Decision**: immediate — applied to this plan text now (this PLAN-supplement pass), before any
RFC-002/003/005 code is written (RFC-001 is already code-complete and unaffected; RFC-002 is
code-complete for the pure stats engine and unaffected — only its Stage-0-decisions record and
Post-Phase Testing gain the D2 ComplexWarning test, no `compute_pair_stats` signature change).

**This invalidates**: the portion of the Validate Contract covering ADR-8 (original "no results
cache" decision) and the RFC-003 Stage 0 perf-smoke threshold gate. See the Validate Contract
section below — the affected rows are marked "amended, pending re-validation"; the Gate verdict
line itself is left untouched for `vc-validate-agent` to re-check, not overwritten here.

## 19. Ops Runbook

- **Deep-fetch/refresh universe history**: `uv run --project api python api/scripts/backfill_pairs_universe.py`.
- **Edit the universe**: hand-edit `api/data/pairs_universe.json`; no restart required (loader reads
  at request time — confirmed at RFC-001 Stage 0, or documented as requiring a restart if the
  implementation reads once at import).
- **Start app**: API `uv run --project api uvicorn api.main:app --host 127.0.0.1 --port 8000`; web
  `pnpm --filter web dev`; open `http://localhost:3000/pairs`.

## 20. Acceptance Criteria (Versioned)

Mirrors the locked SPEC's AC-1..AC-12 verbatim (see
`pair-screener_SPEC_25-09-26.md` for full text); this plan's RFCs map to them as follows:

| SPEC AC | Proven by RFC |
|---|---|
| AC-1 (every pair, one row, no dupes) | RFC-001 (enumeration test), RFC-003 (endpoint shape) |
| AC-2 (insufficient-history explicit state, no stats) | RFC-002 (branch), RFC-004 (rendering) |
| AC-3 (golden-value match, documented tolerance) | RFC-002 |
| AC-4 (default sort BH-p ascending, live-computed) | RFC-003 (data level), RFC-004 (UI level) |
| AC-5 (BH correction, insufficient-history excluded from denominator) | RFC-002 (raw p), RFC-003 (BH) |
| AC-6 (Johansen always shown alongside EG, never merged) | RFC-002, RFC-003, RFC-004, RFC-005 |
| AC-7 (chart date range matches displayed sample window) | RFC-004 (manual), RFC-005 (Playwright) |
| AC-8 (no NaN/silent zero/undisclosed partial sample) | RFC-002, RFC-003, RFC-004 |
| AC-9 (universe is separate, hand-editable, structurally distinct from watchlist.py) | RFC-001 |
| AC-10 (momentum screener provably unmodified in behavior) | RFC-005 (isolation proof) |
| AC-11 (deep fetch is distinct, doesn't invalidate momentum cache) | RFC-001, RFC-005 (re-confirm) |
| AC-12 (unfetchable coin excluded with explicit reason, never silently dropped) | RFC-001 (Stage 0), RFC-002/003 (`coin_unavailable`), RFC-005 (E2E fixture) |

## 21. Future Work

- Rolling/Kalman-filter hedge ratio as an alternative diagnostic mode (ADR-2a's rejected alternative,
  deferred, not ruled impossible).
- Backtesting historical pair-trade performance (SPEC Out Of Scope for v1).
- Browser-based universe editor (SPEC Out Of Scope for v1).
- Scheduled/cron recomputation if the on-request compute model proves too slow at scale (ADR-8).
- Extending the universe beyond ~20 coins if the perf-smoke threshold has headroom.

---

## Touchpoints

| Area | Files | Change |
|---|---|---|
| API dependency | `api/pyproject.toml`, `api/uv.lock` | add `statsmodels>=0.14` (additive) |
| API data | `api/data/pairs_universe.json` (new), `api/data/pairs_universe.py` (new loader) | new |
| API scripts | `api/scripts/backfill_pairs_universe.py` (new), `api/scripts/compute_pairs.py` (new, ADR-8 Amendment), `api/scripts/seed_e2e_cache.py` (extend — fixture OHLCV + precomputed fixture results) | |
| API analytics | `api/analytics/cointegration/stats.py` (pure), `api/analytics/cointegration/pairs_response.py` (compute path + read path, ADR-8 Amendment) | new |
| API models/router | `api/models/pairs.py` (+ `ComputationStatus` enum, `computation_status`/`stale_reason` fields), `api/routers/pairs.py` | new |
| API main | `api/main.py` | one additive `include_router` line |
| API cache (new, ADR-8 Amendment) | `api/data/cache/pairs/results.parquet`, `api/data/cache/pairs/provenance.json` (+ optional per-pair spread files) — all git-ignored under `api/data/cache/*` | new, written only by `compute_pairs.py` |
| API cache helpers (NEW, PVL supplement 26-09-26, closes E6) | `api/data/cache.py` | additive only — new `pairs_results_path()`, `pairs_provenance_path()`, `pairs_spread_path()` helpers built from `CACHE_ROOT` at call time, mirroring `ohlcv_path()`; every existing `cache.py` function unchanged |
| API tests | `api/tests/data/test_pairs_universe.py`, `api/tests/scripts/test_backfill_pairs_universe.py`, `api/tests/scripts/test_compute_pairs.py` (new, ADR-8 Amendment; NEW rows added at PVL supplement 26-09-26: network-isolation test + isolated-`CACHE_ROOT` pairs-output-path test), `api/tests/analytics/test_cointegration_stats.py`, `api/tests/routers/test_pairs.py` (NEW staleness case at PVL supplement 26-09-26: `statsmodels_version`/`eg_autolag` mismatch) | new |
| Web | `web/lib/types/pairs.ts`, `web/lib/api/pairs.ts`, `web/lib/format-pairs-value.ts`, `web/components/pairs/*`, `web/app/pairs/page.tsx`, `web/app/pairs/[a]/[b]/page.tsx`, `web/app/page.tsx` (link) | new + one-line link |
| Web tests | `web/lib/__tests__/format-pairs-value.test.ts`, `web/components/pairs/__tests__/*`, `web/e2e/pairs.spec.ts` | new |
| Cache | `api/data/cache/ohlcv/{SYMBOL}/1d.parquet` (existing files) | extended with deeper history for universe coins only |
| Context | `process/features/cointegration-screener/_GUIDE.md`, `process/context/all-context.md`, `all-tests.md` | UPDATE PROCESS after RFC-005 |

**Must NOT change (hard blast-radius exclusion, verified by RFC-005's `git diff --stat`):**
`api/routers/screener.py`, `api/data/watchlist.py`, `web/app/screener/**`, `api/analytics/regime/**`.

Read-only: `api/data/ccxt_adapter.py` (deep-fetch and market-resolution calls only, no edits;
compute path never calls it — see the ADR-8 Amendment's compute-path isolation note), `web/lib/api/regime.ts`
(structural precedent only).

`api/data/cache.py` is now (PVL supplement, 26-09-26, closes E6) an **additive-edit** touchpoint,
not read-only — see the "API cache helpers" Touchpoints row above. Its existing functions
(`read_ohlcv`, `write_ohlcv`, `ohlcv_path`, etc.) remain unchanged; only new `pairs_*` path
helpers are added, in the same style as the existing `liqtide_*`/`narrative_*` helpers.

## Public Contracts

- **New**: `GET /api/pairs` (§11 shape, amended with `computation_status`/`stale_reason`),
  `GET /api/pairs/{a}/{b}` (§11 shape); `compute_pair_stats()` Python function (unchanged,
  RFC-002); `pairs_universe` loader's public read function; `api/scripts/compute_pairs.py` as a
  user-run entrypoint (ADR-8 Amendment); `cache.py::pairs_results_path()` /
  `pairs_provenance_path()` / `pairs_spread_path()` (NEW, PVL supplement 26-09-26, closes E6 —
  additive, internal helpers, not a public API surface but listed here since they are new
  `cache.py` symbols).
- **Must stay identical**: `GET /api/screener/board`, `GET /api/regime/components`,
  `GET /api/regime/legs`, every existing narrative/watchlist endpoint, `watchlist.py`'s public
  functions, `ccxt_adapter.fetch_ohlcv`'s signature and return type (called, never modified).

## Blast Radius

- ~20-24 new files (was ~18-22; +2 for `api/scripts/compute_pairs.py` and
  `api/tests/scripts/test_compute_pairs.py`, ADR-8 Amendment), 3 modified files
  (`api/pyproject.toml`, `api/uv.lock`, `api/main.py` — all additive), across `api/` and `web/`.
  Extends (does not replace) existing OHLCV Parquet cache files for the ~18 universe coins; adds a
  new git-ignored cache directory `api/data/cache/pairs/` (results + provenance, ADR-8 Amendment).
- Risk class: **low-medium**, unchanged tier, but the risk shifted with the amendment rather than
  disappearing: **was** the new `statsmodels` dependency's runtime cost on the on-request compute
  path; **now** is (a) `compute_pairs.py`'s ~46 s runtime being a real but explicitly
  informational/non-gated cost paid once, offline, by the user, and (b) the staleness-detection
  logic itself being new, testable surface (provenance-vs-universe/cache comparison) that must
  never silently serve mismatched results — covered by RFC-003's new staleness test suite (see the
  ADR-8 Amendment and the amended RFC-003 Post-Phase Testing).
- Regression guard: full `pytest`, `vitest`, and both Playwright specs (screener + pairs) run at
  RFC-005, plus the explicit `git diff --stat` isolation proof against the four excluded paths above.

## Verification Evidence

| Gate / Scenario | Strategy | Proves SPEC criterion |
|---|---|---|
| Pair-enumeration unit test (`test_pairs_universe.py`) | Fully-Automated | AC-1 |
| Loader import-graph isolation test (`test_pairs_universe.py`) | Fully-Automated | AC-9 |
| Deep-fetch cache-extension test with `isolated_cache` (`test_backfill_pairs_universe.py`) | Fully-Automated | AC-11 |
| Live deep-fetch coverage table (per-coin DuckDB query) | Hybrid | AC-11 |
| Golden-value tests, all four branches (`test_cointegration_stats.py`) | Fully-Automated | AC-2, AC-3, AC-8 |
| Live 3-5 pair sanity print on real cache | Hybrid | AC-3 (real-data sanity, not asserted equal) |
| Table shape + BH correction golden test + no-NaN (`test_pairs.py`) | Fully-Automated | AC-1, AC-5, AC-8 |
| 404/422 on invalid symbol (`test_pairs.py`) | Fully-Automated | — (contract hardening, not a listed AC) |
| Perf-smoke on real deep-fetched cache | Hybrid | — (success metric, not a listed AC) |
| Sort-order test on shuffled fixture (vitest) | Fully-Automated | AC-4 |
| Table + detail component tests, insufficient/unavailable rendering (vitest) | Fully-Automated | AC-2, AC-6, AC-8 |
| Manual table + detail walkthrough against running API | Agent-Probe | AC-2, AC-4, AC-6, AC-7 |
| Playwright `pairs.spec.ts` on seeded fixtures | Fully-Automated | AC-1, AC-2, AC-6, AC-7, AC-12 |
| `git diff --stat` on the 4 excluded paths (empty output) | Fully-Automated | AC-10 |
| Full existing pytest + vitest + `screener.spec.ts` re-run green | Fully-Automated | AC-10 |
| Real-cache user walkthrough (user's PC if container egress blocked) | Agent-Probe (user) | AC-11 (full), AC-3 (real-world plausibility) |

Commands and runners per `process/context/tests/all-tests.md`:
`uv run --project api pytest api/ -q` · `pnpm --filter web test` · `cd web && pnpm test:e2e`.

## Test Infra Improvement Notes

(none identified yet)

## Post-EXECUTE Amendments (UPDATE PROCESS, 28-09-26)

All 5 RFCs are ✅ VERIFIED (user-approved in chat). This closeout pass reconciled the following
stale-text items flagged by the RFC reports for UPDATE PROCESS action:

1. **Tie-break rule (RFC-005 EVL cycle 6) — done.** `_sorted_rows` now sorts `ok` rows by
   `(eg_p_bh, eg_p_raw, coin_a, coin_b)`, matching the web page's order. Written into SPEC AC-4
   (Post-EXECUTE amendment) and this plan's §11 API Surface, above.
2. **RFC-001 `since=` wording (RFC-001 report + Stage-0 report Plan Deviations) — already
   reconciled in-plan.** §15 RFC-001 "Stages" item 3 and the Stage 0 research bullets above both
   carry the corrected explicit-`since` mechanism (`since=<explicit early UTC date>`, never
   `since=None`) with a "(Corrected post-RFC-001 ...)" note; no further edit needed this cycle —
   confirmed by re-reading the live text.
3. **`_GUIDE.md` naming collision (SPEC Background + this plan's §18) — done.** Corrected below /
   in the feature's `_GUIDE.md` to point at `api/routers/pairs.py`, `web/app/pairs/`,
   `api/analytics/cointegration/` instead of the momentum screener's files.
4. **Status Strip / Current Status / Resume and Execution Handoff — done.** All updated from
   "⏳ PLANNED" / "no RFC started" to ✅ VERIFIED with the final gate counts (see Status Strip).
5. **Other reported items, accepted as known-gaps, not plan edits:** the screener cold-start
   Playwright flake (pre-existing, `all-tests.md` backlog item, mitigated by a 15s expect timeout
   — not a pair-screener defect); the single unidentified intermittent vitest failure (not
   reproduced in 3 consecutive full runs); the Hyperliquid ~2020-08-19 apparent history floor and
   live cap-hit/rate-limit behavior (both carried in `all-data-sources.md`, see below); the
   Johansen-refused-row and no-significant-pairs banner paths being unit-tested only, not E2E
   (documented in RFC-005's spec header, accepted as sufficient coverage).

## Resume and Execution Handoff

**Superseded 28-09-26 (UPDATE PROCESS closeout) — kept for history, not deleted.** All 5 RFCs are
now ✅ VERIFIED and this plan is archived to
`process/features/cointegration-screener/completed/pair-screener_25-09-26/`. There is no next step
for this plan; see the plan's own Status Strip and the `pair-screener_25-09-26-RFC-005-phase-report`
/ EVL cycle 6 notes for the final state. The steps below describe the plan's state before EXECUTE
started and are retained as a record only.

1. **Selected plan file**: `process/features/cointegration-screener/active/pair-screener_25-09-26/pair-screener_PLAN_25-09-26.md`
2. **Last completed phase or step**: PLAN written 25-09-26; SPEC locked; INNOVATE decisions recorded
   as ADRs above. No RFC started. VALIDATE not yet run.
3. **Validate-contract status**: not yet written — placeholder below; `vc-validate-agent` writes
   this section before EXECUTE.
4. **Supporting context files loaded**: `process/context/all-context.md`,
   `process/context/tests/all-tests.md`, `process/context/data-sources/all-data-sources.md`,
   `process/features/cointegration-screener/_GUIDE.md` (noted stale — see §18), plus the code files
   listed under §1 Context and Goals.
5. **Next step for a fresh agent**: run VALIDATE on this plan (`ENTER VALIDATE MODE`). If PASS or
   accepted CONDITIONAL, start RFC-001 Stage 0 (statsmodels add + smoke check + universe proposal +
   market-symbol resolution check) and STOP for user approval before writing any code, per the
   Phased Execution Workflow above.

Reports for each RFC go in this same task folder as
`pair-screener_25-09-26-RFC-00N-phase-report.md`.

## Validate Contract

Status: PASS
Date: 26-09-26
date: 2026-09-26
generated-by: outer-pvl
supersedes: 2026-09-26 (outer-pvl, CONDITIONAL — pre-amd-1) — the amd-1 PVL-supplement cycle closed both open gaps (G1, G2) in plan text; this fresh outer-PVL re-validation pass (V1-V7, re-run from V1 per this plan's own §18/PVL-Supplement-Log note that only `vc-validate-agent` can move the gate) has current evidence and supersedes that CONDITIONAL contract.

Parallel strategy: sequential
Rationale: Unchanged from every prior contract on this plan: one Complex plan, 5 RFCs in a hard, explicitly STOP-gated dependency chain (each RFC's Dependencies field names the prior RFC; the Phased Execution Workflow requires a checkpoint between every RFC) — no independent, non-overlapping fan-out exists to parallelize. This re-validation pass itself also ran sequentially (sonnet): it re-checks one artifact (this plan file) against a small, fixed set of real source files (`api/data/cache.py`, `api/tests/conftest.py`, `api/data/ccxt_adapter.py`, `api/uv.lock`) — no independent sub-scopes. EXECUTE model: opus (one `vc-execute-agent` per RFC, in order), resuming at RFC-002 Stage 1 now that this contract is PASS.

Drift check (this session, worktree `my_project-main`, branch `main`, HEAD `be3aee1` — unchanged since the prior contract; zero new commits): working tree carries the same uncommitted/untracked set the prior contract's amd-1 cycle produced — the plan file (this ADR-8-Amendment supplement text), `results.tsv` (amd-0/amd-1 rows), and two untracked reports (`pair-screener_RFC-002-stage0_REPORT_25-09-26.md`, `pair-screener-pvl-iteration-002_REPORT_26-09-26.md`), all read directly this session. Directory scan this session confirms RFC-002+ code still does not exist (`api/analytics/cointegration/`, `api/routers/pairs.py`, `api/models/pairs.py`, `api/scripts/compute_pairs.py` all absent) — RFC-002 remains genuinely at Stage 0 (STOP), matching the Status Strip. RFC-001 is unaffected and unchanged: `api/data/pairs_universe.json`/`.py`, `api/scripts/backfill_pairs_universe.py`, and their tests still exist exactly as committed in `d5eb538`.

RFC-001 evidence re-confirmed this session (unchanged from the prior contract, re-checked, not re-derived): `git show --stat d5eb538` — 729 insertions across 7 files, all within the plan's own Touchpoints/Blast Radius list; no touch to any of the 4 hard-excluded paths or to `api/data/ccxt_adapter.py`. `api/data/cache/ohlcv/` holds 18 coin directories. AC-9/AC-11 mechanics remain proven in shipped code.

**New evidence gathered this session, specifically to verify G1 and G2 against real source (not just plan-text self-consistency):**
- Read `api/data/cache.py` directly. Confirmed: `CACHE_ROOT` is a module attribute (`DEFAULT_CACHE_ROOT` / `SCREENER_CACHE_ROOT` env override); every existing path helper — `ohlcv_path()`, `liqtide_payload_path()`, `liqtide_raw_path()`, `liqtide_backfill_path()`, `liquidity_series_path()`, `narrative_series_path()`, and the confirmed-boundaries path — builds `CACHE_ROOT / ...` **inside the function body**, read at call time, never bound at import. `write_ohlcv()` additionally calls `path.parent.mkdir(parents=True, exist_ok=True)` at write time, so a new cache subdirectory does not strictly need a `bootstrap_cache_dirs()` entry to work correctly (see the non-blocking note below). The plan's proposed `pairs_results_path()` / `pairs_provenance_path()` / `pairs_spread_path(symbol_a, symbol_b)` (ADR-8 Amendment §3, mirrored in §7, Touchpoints, Public Contracts) describe the exact real convention already in use, not an invented one — **G1's cache-helper claim is mechanically consistent with the current codebase.**
- Read `api/tests/conftest.py` directly. Confirmed the `isolated_cache` fixture does exactly `monkeypatch.setattr(cache, "CACHE_ROOT", tmp_path)` + `cache.bootstrap_cache_dirs()`, and its own docstring names "an unredirected module-level constant" as the defect class this fixture exists to prevent (the same defect class the plan's Gap-1 finding cited). The plan's planned "Pairs-cache path isolation test" (RFC-003 Post-Phase Testing) — asserting `results.parquet`/`provenance.json` land under the isolated `CACHE_ROOT / "pairs"` via the new helpers — is mechanically sound against this real fixture, not a guess. **G1's isolated-path-test claim is verified against the real fixture contract.**
- Read `api/data/ccxt_adapter.py` directly. Confirmed `fetch_ohlcv()` and `resolve_market_symbol()` exist as named, and that `read_ohlcv()`/`write_ohlcv()` live in `cache.py`, not in the adapter — so the plan's "compute path calls `cache.read_ohlcv`, never `ccxt_adapter.fetch_ohlcv`" instruction (ADR-8 Amendment compute-path isolation note, §7, RFC-003 Post-Phase Testing network-isolation test, Execute-Agent Instruction E5) names the correct real function boundary between the two modules. **G1's network-isolation claim is verified against the real module boundary.**
- Confirmed `statsmodels` 0.15.0 is the actually-installed version (`api/uv.lock`) — matches the plan's `provenance.json` worked example (§3 ADR-8 Amendment) and the RFC-002 Stage 0 report's own measured environment. **G2's worked example is internally consistent with the real installed dependency.**
- **Non-blocking implementation note (not a plan-text gap):** `cache.py::bootstrap_cache_dirs()`'s hardcoded subdirectory tuple (`"ohlcv", "liquidity", "liqtide", "legs", "narrative"`) does not yet list `"pairs"`. This does not block correct operation — `write_ohlcv()`'s precedent shows every write path in this codebase creates its own parent directory at write time — but RFC-003 Stage 1's `compute_pairs.py`/`pairs_response.py` write call sites should follow the same `path.parent.mkdir(parents=True, exist_ok=True)` pattern (or `bootstrap_cache_dirs()` should gain a `"pairs"` entry). Flagged here as an implementation nuance for RFC-003 Stage 1 to carry forward, not a re-opened gap.

**G1 verification result: CLOSED, verified against real source.** All three parts hold: (a) the compute path reads OHLCV only via `cache.read_ohlcv`, never `ccxt_adapter.fetch_ohlcv`, with a missing/empty read mapped to `coin_unavailable` — stated in the ADR-8 Amendment note (§3), §7 Component Details (`stats.py`, `pairs_response.py`, `compute_pairs.py`), and Execute-Agent Instruction E5; (b) the 3 additive `cache.py` helpers are named consistently across §3, §7, Touchpoints, and Public Contracts, and match the real `ohlcv_path()`/`liqtide_*`/`narrative_*` convention exactly (verified above, not assumed); (c) both a network-isolation test and an isolated-`CACHE_ROOT` path test are specified in RFC-003 Post-Phase Testing, each explicitly dated "PVL supplement, 26-09-26," and each is mechanically correct against the real `isolated_cache` fixture (verified above).

**G2 verification result: CLOSED, verified against real source.** The 5th staleness check — `provenance.json`'s `statsmodels_version` vs. the installed `statsmodels.__version__`, and `eg_autolag` vs. the current `stats.py::EG_AUTOLAG` constant, each with an explicit reason string — is specified in the ADR-8 Amendment — Staleness and Provenance section's updated `computation_status` table (`stale` row) and RFC-003 Post-Phase Testing case (e), which names `api/tests/routers/test_pairs.py` as the home for the new case, consistent with the existing cases (a)-(d) already planned for that same file. The worked `provenance.json` example's `statsmodels_version: "0.15.0"` matches the real installed version (verified above), so the staleness contract's own example is not a stale/invented number.

**No new gaps or regressions found this cycle.** Protected-file check (mechanical, `git status --short` this session): only `process/` artifacts are modified/untracked (the plan file, `results.tsv`, and the two reports named above) — zero changes to `api/routers/screener.py`, `api/data/watchlist.py`, `web/app/screener/**`, `api/analytics/regime/**`, or `api/data/ccxt_adapter.py`. `api/data/cache.py` itself is currently **unmodified** (0 diff) — its "additive-edit" touchpoint status is a forward-looking constraint for RFC-003 Stage 1 and has not yet been exercised; this is unchanged from the prior contract and is not a regression.

**Mechanical confirmation of the staleness contract's core claim (re-confirmed, not re-derived):** `api/data/cache.py::ohlcv_bar_count` (`SELECT COUNT(*)`) and `::ohlcv_last_refresh` (`SELECT MAX(timestamp)`) still exist exactly as the ADR-8 Amendment's staleness comparison needs — cheap, DuckDB-pushdown reads per universe coin, no full-cache load and no new `cache.py` code required for that half of the comparison.

Feasibility probe: none required this cycle. The original probe (`pair-screener_FEASIBILITY_25-09-26.md`, VIABLE) remains resolved and proven in shipped code (RFC-001). Every check this cycle (G1, G2, the protected-file scan) was answerable by reading `cache.py`, `conftest.py`, `ccxt_adapter.py`, and `uv.lock` directly — no untested runtime/library/IO behavior is in play. `VC-FEASIBILITY-PROBE-NEEDED` was considered and not triggered.

Test gates (C3 5-column table — ADDITIVE; existing consumers still parse the legacy line form below it):

| criterion id | behavior | strategy | proving test | gap-resolution |
|---|---|---|---|---|
| AC-1 | Every pair from curated list appears as exactly one row (C(n,2), no dupes) | Fully-Automated | `api/tests/data/test_pairs_universe.py::test_pair_enumeration` (shipped, RFC-001) + `api/tests/routers/test_pairs.py::test_table_shape` (pending, RFC-003) | A (universe half, shipped) / B (router half, RFC-003 checklist) |
| AC-9 | Universe loader structurally isolated from `watchlist.py` | Fully-Automated | `api/tests/data/test_pairs_universe.py` isolation test — shipped and green (RFC-001, part of the 420/3 baseline) | A |
| AC-11 (mechanics) | Deep-fetch script extends (not replaces) a pre-seeded cache via explicit-`since` calls; momentum-screener cache untouched | Fully-Automated | `api/tests/scripts/test_backfill_pairs_universe.py` (9 tests) — shipped and green | A |
| AC-11 (live) | Real per-coin coverage table after one live deep fetch | Hybrid | Done and evidenced — RFC-001 phase report's 18-coin table | A |
| AC-2, AC-3, AC-8 | Golden-value branches: cointegrated / non-cointegrated / not-mean-reverting / insufficient-overlap; no NaN/inf | Fully-Automated | `api/tests/analytics/test_cointegration_stats.py` (pending, RFC-002 Stage 1) — Stage 0 report confirms all 4 fixtures behave as designed and pins exact expected values | B (design proven; code pending) |
| AC-3 (real-data sanity) | Live 3-5 pair sanity print, eyeballed | Hybrid | RFC-002 phase-report print (pending) | B |
| AC-1, AC-5, AC-8 | Table shape + BH correction golden test + no-NaN | Fully-Automated | `api/tests/routers/test_pairs.py` (pending, RFC-003) | B |
| — (contract hardening) | 404 on invalid symbol; 422 on self-pair (precedence over unknown-ticker); case-insensitive matching | Fully-Automated | `api/tests/routers/test_pairs.py::test_self_pair_422` etc. (pending, RFC-003) | B |
| AC-4 | Table default sort ascending BH-p, insufficient rows excluded from sort key | Fully-Automated | `web/lib/__tests__/format-pairs-value.test.ts` (pending, RFC-004) | B |
| AC-2, AC-6, AC-8 | Table + detail component rendering | Fully-Automated | `web/components/pairs/__tests__/*` (pending, RFC-004) | B |
| AC-2, AC-4, AC-6, AC-7 | Manual table + detail walkthrough | Agent-Probe | RFC-004 manual walkthrough (pending) | B |
| AC-1, AC-2, AC-6, AC-7, AC-12 | Full E2E on seeded fixtures | Fully-Automated | `web/e2e/pairs.spec.ts` (pending, RFC-005) | B |
| AC-10 | `git diff --stat` on the 4 hard-excluded paths — empty output | Fully-Automated | RFC-005 isolation check (pending); RFC-001's own diff already independently confirms zero touches, one RFC early | A (partial, RFC-001) / B (full, RFC-005) |
| AC-10 | Full pytest+vitest+`screener.spec.ts` re-run green | Fully-Automated | RFC-001 baseline: 420/3, no regressions vs. 392/3 pre-RFC-001 | A (through RFC-001) / B (through RFC-005) |
| AC-11 (full) / AC-3 (real-world) | Real-cache user walkthrough | Agent-Probe (user) — known-gap in this container | User's own PC, RFC-005 Stage 4 | D — backlog, plan stays in `active/` |
| — (read-path timing) | `GET /api/pairs` warm read is comfortably < 3s p95 (persisted-file read, not a recompute) | Fully-Automated | RFC-003 phase-report timing gate (pending) — implemented as a pytest `TestClient`-timed assertion (E8) | B |
| — (compute-script runtime) | `compute_pairs.py`'s ~46s runtime is recorded, not gated | Informational | RFC-003 phase-report (pending) — magnitude already measured at Stage 0 | A (measured) / B (recorded in phase report) |
| — **G1, verified this cycle** — compute-path network isolation | `compute_pairs.py`/`pairs_response.py`'s compute path never makes a live network call — OHLCV ingestion for compute is a pure, offline cache read via `cache.read_ohlcv` only | Fully-Automated | ADR-8 Amendment "Compute-path isolation and cache path resolution" note + §7 + RFC-003 Post-Phase Testing network-isolation test | B — verified this cycle against real `cache.py`/`ccxt_adapter.py` source; code pending RFC-003 Stage 1 |
| — **G1, verified this cycle** — pairs-cache path resolution | 3 additive `cache.py` helpers (`pairs_results_path`/`pairs_provenance_path`/`pairs_spread_path`) resolve `CACHE_ROOT` at call time, isolatable by the `isolated_cache` fixture | Fully-Automated | §3 ADR-8 Amendment + §7 + Touchpoints + Public Contracts + RFC-003 Post-Phase Testing isolated-path test | B — verified this cycle against real `ohlcv_path()`/`conftest.py` conventions; code pending RFC-003 Stage 1 |
| — **G2, verified this cycle** — staleness-comparison completeness | `provenance.json` records `statsmodels_version`/`eg_autolag`; the 5th staleness check compares them against the currently-installed/configured values, `stale` (never silently `fresh`) on mismatch | Fully-Automated | ADR-8 Amendment — Staleness and Provenance (updated comparison rule + `computation_status` table) + RFC-003 Post-Phase Testing case (e) | B — verified this cycle against real `api/uv.lock` (statsmodels 0.15.0); code pending RFC-003 Stage 1 |

gap-resolution legend:
- A — proven now (gate passes in this cycle)
- B — fixed in this plan (gate added by this plan's checklist, or pending a same-cycle plan-supplement)
- C — deferred to a named later phase/plan
- D — backlog test-building stub (named residual; keep-active; continue)

C-4 reconciliation: every `strategy:` value above is one of the 3 proving strategies (Fully-Automated / Hybrid / Agent-Probe). The D-resolution row (real-cache walkthrough) carries a proving strategy (Agent-Probe, user-run) plus independent Fully-Automated mechanical coverage of the same underlying behavior (the shipped `isolated_cache` extension test) — a named residual with a resolution path, not an ungated behavior. Net gate is PASS: 0 FAILs, 0 CONCERNs — both of the prior cycle's CONCERNs (G1, G2) are now closed and independently verified against real source, not merely restated in plan text.

Legacy line form (retained so existing validate-contract consumers still parse):
- Universe/deep-fetch (RFC-001): `Fully-automated: uv run --project api pytest api/tests/data/ api/tests/scripts/ -q` (shipped, 164 passed/2 deselected) | `hybrid: real deep-fetch + DuckDB coverage query` (done, see RFC-001 phase report)
- Stats engine (RFC-002): `Fully-automated: uv run --project api pytest api/tests/analytics/test_cointegration_stats.py -q` (pending, Stage 0 design proven) | `hybrid: live 3-5 pair sanity print` (pending)
- API (RFC-003, amended scope): `Fully-automated: uv run --project api pytest api/tests/routers/test_pairs.py api/tests/scripts/test_compute_pairs.py -q` (pending — now includes the network-isolation test, the isolated-path test, and staleness case (e)) | `fully-automated: read-path timing gate` (pending) | `informational: compute_pairs.py runtime record` (~46s measured)
- Web (RFC-004): `Fully-automated: pnpm --filter web test` (pending) | `agent-probe: manual table + detail walkthrough` (pending)
- E2E + isolation (RFC-005): `Fully-automated: cd web && pnpm test:e2e` + `uv run --project api pytest api/ -q` (full suite) + `git diff --stat` isolation check (all pending) | `agent-probe: real-cache user walkthrough` (known-gap, user's PC)

Failing stubs: unchanged from the prior contract (AC-1, AC-9, AC-11 mechanics, AC-2/3/8, AC-1/5/8, contract hardening, AC-4, AC-2/6/8, AC-1/2/6/7/12, AC-10) — AC-1/AC-9/AC-11-mechanics stubs are moot (real tests shipped in RFC-001); the remainder still apply verbatim to RFC-002-005. See this file's git history (`be3aee1` and earlier) for the exact stub text.

Failing stub (compute-path network isolation, carried forward, still pending RFC-003 Stage 1):
```
test("should never call ccxt_adapter.fetch_ohlcv during compute_pairs.py — OHLCV ingestion for compute uses cache.read_ohlcv only", () => {
  throw new Error("NOT IMPLEMENTED — TDD stub: assert a mocked/patched ccxt_adapter.fetch_ohlcv is never invoked during a full compute_pairs.py run against a pre-seeded isolated_cache")
})
```

Failing stub (staleness-comparison completeness, carried forward, still pending RFC-003 Stage 1):
```
test("should mark computation_status stale (or document as an accepted known-gap) when provenance.statsmodels_version or eg_autolag no longer matches the running environment", () => {
  throw new Error("NOT IMPLEMENTED — TDD stub: test_pairs.py, 5th staleness case — dependency/constant drift, not just universe/cache drift")
})
```

Dimension findings:
- Infra fit: PASS — unchanged. Local-only FastAPI/Next.js dev, no container/port/proxy surface touched; one additive `include_router` line; `GZipMiddleware` already app-wide.
- Test coverage: PASS (upgraded from CONCERN) — both gaps from the prior cycle (compute-path network isolation; staleness-comparison completeness) are now specified in plan text AND verified this session against the real `cache.py`/`conftest.py`/`ccxt_adapter.py` conventions, not just internal plan-text consistency. RFC-001's shipped coverage remains excellent and unaffected.
- Breaking changes: PASS — unchanged. New router/models/analytics module only; `api/main.py`'s one added line stays additive; the `Must NOT change` list is independently confirmed by a real `git show --stat` diff for RFC-001 and by this session's `git status --short` scan for the current cycle.
- Security surface: PASS — unchanged. No auth/secrets/billing touched; local-only binding; `{a}`/`{b}` path params validated server-side before any downstream use.
- RFC-001 (Universe + deep-fetch): PASS, unchanged — proven in shipped code, 420/3 pytest baseline, isolation proof, `ccxt_adapter.py` confirmed unmodified.
- RFC-002 (Stats engine, Stage 0 done): PASS (upgraded from CONCERN) — the pure-statistics design (ADR-1/3/4/5, D1-D4) is sound and Stage-0-validated; Gap 1's compute-path OHLCV-source instruction is now explicit in plan text and verified against the real `cache.py`/`ccxt_adapter.py` module boundary. Ready for Stage 1.
- RFC-003 (Endpoint, amended scope): PASS (upgraded from CONCERN) — the precompute/persistence/staleness redesign (ADR-8 Amendment) is architecturally sound; both prior-cycle gaps (cache-path resolution mechanism, staleness-comparison completeness) are closed in plan text and verified this session against the real `ohlcv_path()`/`isolated_cache`/`uv.lock` conventions.
- RFC-004 (Web): PASS — unchanged, not in scope for this amendment.
- RFC-005 (E2E + isolation proof, amended scope): PASS — unchanged. The seeder's extension plan matches the confirmed `build_X_fixture`/`seed_X` pattern already used by the regime/narrative dashboards.

Open gaps:
- None new this cycle. Both of the prior cycle's material gaps (compute-path network isolation; persisted-cache path resolution) and the minor gap (staleness-comparison completeness) are CLOSED and independently verified against real source (see G1/G2 verification results above), not merely restated in plan text.
- Real-cache user walkthrough (AC-11 full, AC-3 real-world) — accepted known-gap, regime-dashboard precedent. Unaffected by this cycle. Not a CONCERN.
- 3 feasibility-VERDICT known-gaps (live cap-hit behavior, real listing dates, rate-limit/backoff) — carried forward unchanged, partially narrowed by RFC-001's real run (cap-hit never observed live, 0/18; rate-limit/backoff not stressed but 18/18 calls succeeded with no failures). Not a CONCERN.
- CONCERN-1 and CONCERN-2 from the original first-pass contract remain CLOSED, unaffected by this cycle.

What this coverage does NOT prove:
- Everything the prior contracts' "What this coverage does NOT prove" sections said still holds unchanged (BH procedure's false-discovery-rate control is not proven, only disclosed; the strengthened `isolated_cache` test proves script mechanics, not Hyperliquid's live response shape; the read-path timing gate proves one measurement, not concurrent-load behavior; `pairs.spec.ts` does not substitute for the real-cache walkthrough; the `git diff --stat` proof does not prove the absence of a future accidental shared import).
- This cycle's G1/G2 verification proves the PLAN TEXT correctly names real functions, real conventions, and a real installed dependency version — it does NOT prove the not-yet-written RFC-002/RFC-003 code will actually implement what the plan now says. That proof is deferred to RFC-002 Stage 1 (golden-fixture tests) and RFC-003 Stage 1 (network-isolation test, isolated-path test, staleness case (e)) actually running green, per the Test Gates table above (gap-resolution B rows).
- `bootstrap_cache_dirs()` not yet listing `"pairs"` is a non-blocking implementation nuance (see the drift-check note above) — it does not prove RFC-003's future write call sites will correctly create their own parent directories; that remains an RFC-003 Stage 1 implementation detail to get right.
- The mechanical confirmation that `cache.py::ohlcv_bar_count`/`ohlcv_last_refresh` are cheap does not prove the router's actual staleness-comparison code (not yet written) correctly interprets "bar count increased" OR "max date newer" (per the ADR-8 Amendment text) — this remains an RFC-003 implementation detail to get right and test explicitly.

Gate: PASS (0 FAILs, 0 CONCERNs — both prior-cycle CONCERNs (G1 compute-path isolation + cache-path resolution, G2 staleness-comparison completeness) are closed in plan text and independently verified against real source this cycle; RFC-001 remains shipped/PASS; RFC-002-005 remain plan-verified with code pending, each gated by a named Fully-Automated/Hybrid/Agent-Probe test per the Test Gates table; the one accepted known-gap (real-cache walkthrough) is a named residual with a resolution path, not an ungated behavior — net gate is not vacuously green)
Accepted by: N/A — Gate: PASS, no outstanding CONCERNs require acceptance. (All previously-accepted known-gaps — real-cache walkthrough, cap-hit-never-observed, 2020-08-19 history floor, rate limits — remain accepted, carried forward unchanged from the prior contracts.)

### Execute-Agent Instructions

| # | Instruction | Trigger condition | Status |
|---|---|---|---|
| E1-E3 | (RFC-001 mechanism, AC-11 test strengthening, self-pair/case-sensitivity contract) | — | **APPLIED AND SHIPPED** — RFC-001 is code-complete. No further action. |
| E4 | Golden-fixture provenance clarification (pinned baseline for EG/Johansen, hand-computed for AR1/hedge-ratio/z-score) | RFC-002 Stage 1 | **Confirmed correct in practice** — informational only. |
| E5 | Compute path must use `cache.read_ohlcv`, never `ccxt_adapter.fetch_ohlcv`; add the network-isolation test | Before RFC-002 Stage 1 | **CLOSED — verified against real source this cycle.** Plan text specifies the correct real module boundary (`cache.py` vs. `ccxt_adapter.py`, confirmed by direct read). Code pending RFC-002/RFC-003 Stage 1. |
| E6 | Decide and record how `api/data/cache/pairs/{results.parquet, provenance.json, spreads/}` paths are resolved (via `cache.py` helpers reading `CACHE_ROOT` at call time) | RFC-003 Stage 0 | **CLOSED — verified against real source this cycle.** `pairs_results_path()`/`pairs_provenance_path()`/`pairs_spread_path()` match the real `ohlcv_path()`/`liqtide_*`/`narrative_*` convention exactly (confirmed by direct read of `cache.py`). Code pending RFC-003 Stage 1. |
| E7 | Extend the staleness-comparison rule to flag `stale` on a `statsmodels_version`/`eg_autolag` mismatch (5th Post-Phase Testing case), or explicitly accept as known-gap | RFC-003 Stage 0 | **CLOSED — verified against real source this cycle.** The 5th check (case (e)) is specified; the worked `provenance.json` example's `statsmodels_version: "0.15.0"` matches the real installed version (confirmed via `api/uv.lock`). Code pending RFC-003 Stage 1. |
| E8 | RFC-003's read-path timing gate should be a pytest `TestClient`-timed assertion, not a manual `curl`, so "Fully-Automated" is literally accurate | RFC-003 Stage 0 | Non-blocking, low-cost wording fix — carried forward, still applies at RFC-003 Stage 0. |
| E9 (NEW, non-blocking) | RFC-003 Stage 1's `compute_pairs.py`/`pairs_response.py` write call sites for `pairs_results_path()`/`pairs_provenance_path()`/`pairs_spread_path()` should call `path.parent.mkdir(parents=True, exist_ok=True)` at write time (matching `write_ohlcv()`'s precedent), since `bootstrap_cache_dirs()` does not yet list a `"pairs"` subdirectory. | RFC-003 Stage 1 | Non-blocking implementation nuance found this cycle (see drift-check note above) — does not affect the Gate: PASS verdict. |

### Proposed Plan Updates

| # | What changes | Where in plan | Why | Status |
|---|---|---|---|---|
| P3 | Name `cache.read_ohlcv` (never `ccxt_adapter.fetch_ohlcv`) as the compute path's OHLCV source | `## 7. Component Details`, `stats.py`/`pairs_response.py`/`compute_pairs.py` responsibilities | Prevents `compute_pairs.py` from silently becoming network-dependent | **APPLIED AND VERIFIED against real source this cycle** |
| P4 | Specify `api/data/cache/pairs/` path resolution via `cache.CACHE_ROOT` (new `cache.py` helpers) | `## 3. Architecture Decisions (Final)`, ADR-8 Amendment / `## 12b. Storage Schema` | Prevents `isolated_cache` from silently failing to isolate `test_compute_pairs.py`'s writes | **APPLIED AND VERIFIED against real source this cycle** |
| P5 | Decide and record the statsmodels_version/eg_autolag staleness-comparison scope | `## 3. Architecture Decisions (Final)`, ADR-8 Amendment — Staleness and Provenance | Closes a silent-staleness gap in the mechanism built to prevent silent staleness | **APPLIED AND VERIFIED against real source this cycle** |
| P1, P2 (prior cycle) | RFC-001 deep-fetch mechanism; self-pair/case-sensitivity contract | RFC-001 Stage 0; RFC-003 Stage 0 | — | **APPLIED and SHIPPED (RFC-001 code-complete)** |

### Backlog Artifacts

| Artifact | Location | What it tracks |
|---|---|---|
| (none required — all gaps found across every cycle so far were either applied in-plan or are the one accepted known-gap, the real-cache user walkthrough) | — | — |

### PVL Supplement Log

**Cycle 1 (25-09-26)** and **Re-validation (25-09-26)** — unchanged from the prior contract; both CONCERN-1/CONCERN-2 remain closed, proven in shipped code (RFC-001).

**Amendment cycle (26-09-26) — re-validation of the Post-Stage-0 (ADR-8) Amendment:** found 2 new CONCERNs (G1: compute-path network isolation + cache-path resolution; G2: staleness-comparison completeness). Net gate CONDITIONAL. SUPPLEMENT REQUEST issued.

**Plan-supplement cycle amd-1 (26-09-26, PVL-supplement mode):** vc-plan-agent closed both gaps in plan text (ADR-8 Amendment note, §7, Touchpoints, Public Contracts, RFC-003 Post-Phase Testing new tests, updated `computation_status` table). `Gate: CONDITIONAL` left unchanged pending re-validation, per protocol.

**Re-validation cycle amd-2 (26-09-26) — this pass, V1-V7 re-run from V1:** independently verified both G1 and G2 against real source (`api/data/cache.py`, `api/tests/conftest.py`, `api/data/ccxt_adapter.py`, `api/uv.lock`), not just plan-text internal consistency — see the "New evidence gathered this session" block above. Both gaps CLOSED. No new gaps or regressions found; protected-file check clean (`git status --short`); all previously-accepted known-gaps carried forward unchanged. One non-blocking implementation nuance noted for RFC-003 Stage 1 (`bootstrap_cache_dirs()` missing a `"pairs"` entry — Execute-Agent Instruction E9, non-blocking). Net gate: **PASS**. RFC-002 Stage 1 may now proceed once `ENTER EXECUTE MODE` is given.

## Autonomous Goal Block

SESSION GOAL: Ship the pair-screener v1 (/pairs) — cointegration screen for a curated crypto universe.
Charter + umbrella plan: N/A — single plan, not a phase program. process/features/cointegration-screener/active/pair-screener_25-09-26/pair-screener_PLAN_25-09-26.md
Autonomy: standard RIPER-5 autonomy per process/development-protocols/orchestration.md — VALIDATE re-ran 26-09-26 (amd-2, V1-V7 from V1) after the amd-1 plan-supplement closed both gaps: Gate is PASS. RFC-001 is code-complete and unaffected. RFC-002 Stage 1 may now begin; EXECUTE still requires explicit ENTER EXECUTE MODE and the plan's own per-RFC STOP-and-approve checkpoints remain mandatory regardless of autonomy state.
Hard stop conditions / safety constraints:
- Never edit api/routers/screener.py, api/data/watchlist.py, web/app/screener/**, or api/analytics/regime/** (hard blast-radius exclusion, enforced by RFC-005's git diff --stat gate; RFC-001 already confirmed zero touches).
- Never edit api/data/ccxt_adapter.py (read-only; confirmed unmodified by RFC-001).
- The compute path (RFC-002/RFC-003) must never call ccxt_adapter.fetch_ohlcv — cache.read_ohlcv only, so compute_pairs.py stays offline/CPU-bound (new this cycle, see Execute-Agent Instruction E5).
- No new market-data provider; crypto-only v1.
Next phase: EXECUTE at RFC-002 Stage 1 (statsmodels return-shape confirmation already done at Stage 0 — Stage 1 begins with `compute_pair_stats` + the four golden fixtures), on ENTER EXECUTE MODE.
Validate contract: inline in this plan file, section "Validate Contract" above.
Execute start: uv run --project api pytest api/ -q (current baseline: 420 passed, 3 deselected, post-RFC-001) | pnpm --filter web test (baseline: 110 passed, 16 files) | cd web && pnpm test:e2e (baseline: 26/26) — full commands in process/context/tests/all-tests.md | high-risk pack: no (no auth/billing/migration/deploy surface touched)
