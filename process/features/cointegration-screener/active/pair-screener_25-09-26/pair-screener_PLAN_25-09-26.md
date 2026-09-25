---
name: plan:pair-screener
description: "Cointegration / pair screener v1 — ranked pair table + per-pair spread detail for a hand-curated crypto universe"
date: 25-09-26
feature: cointegration-screener
---

# Pair Screener v1 — Cointegration Screener

**Date**: 25-09-26
**Complexity**: Complex (standard complex — one authoritative plan, sequential RFCs)
**Status**: ⏳ PLANNED — nothing in `process/features/cointegration-screener/active/pair-screener_25-09-26/` has started
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
| RFC-001 | Universe file + loader + deep-fetch script (+ statsmodels dependency, Stage-0 smoke check) | ⏳ PLANNED |
| RFC-002 | Stats engine (`stats.py`) + golden-value tests | ⏳ PLANNED |
| RFC-003 | Pydantic models + response serializer + router + perf-smoke | ⏳ PLANNED |
| RFC-004 | Web table + detail view + vitest formatters | ⏳ PLANNED |
| RFC-005 | Playwright `pairs.spec.ts` + screener-isolation proof | ⏳ PLANNED |

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

### RFC-003: Endpoint

- **What happens**: `api/models/pairs.py` (Pydantic), `api/analytics/cointegration/pairs_response.py`
  (orchestrator + BH correction across the full universe), `api/routers/pairs.py`
  (`GET /api/pairs`, `GET /api/pairs/{a}/{b}` with server-side universe validation), registered in
  `api/main.py`.
- **Integration points**: router → `pairs_response.py` → `stats.py` → cache reads only.
- **Test**: pytest router contract tests (shape, 404/422 on invalid symbols, no NaN/0 stand-ins);
  perf-smoke timing `GET /api/pairs` against the real deep-fetched ~190-pair cache.
- **Verify**: `curl` both endpoints; perf-smoke output pasted into the phase report.
- **Done when**: user reviews the perf-smoke number and endpoint shapes and agrees.

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
  `ccxt_adapter.fetch_ohlcv(symbol, "1d", limit=DEEP_LOOKBACK_LIMIT)` per universe coin, prints a
  coverage table (symbol, status, rows, first date, last date).

### `api/analytics/cointegration/stats.py` (new)

- **Responsibilities**: pure functions over per-coin `DataFrame`s → per-pair result. Log-price
  transform; static OLS hedge ratio both directions; `statsmodels.tsa.stattools.coint` both
  directions; AR(1) half-life; z-score; per-pair `status`/`reason`; `MIN_OVERLAP_DAYS` gate.
  One orchestrator `compute_pair_stats(df_a, df_b, symbol_a, symbol_b) -> PairStatsResult`.
- **Key flows**: two coins' cached daily OHLCV → inner-join on date (overlap) → gate on
  `MIN_OVERLAP_DAYS` → log prices → both-direction OLS/EG → Johansen → half-life → z-score.

### `api/analytics/cointegration/pairs_response.py` (new)

- **Responsibilities**: enumerate all `C(n,2)` pairs from the universe; call `stats.py` per pair;
  collect raw p-values from pairs with `status == "ok"`; run `multipletests(..., method='fdr_bh')`;
  assemble the full table response (including `insufficient_overlap`/`coin_unavailable` rows, never
  dropped) and single-pair detail responses.

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

```json
{
  "generated_utc": "2026-09-25T18:00:00Z",
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

Status rules: `status ∈ ok | insufficient_overlap | coin_unavailable`; within `ok`,
`half_life.state ∈ computed | not_mean_reverting`. No field is ever `NaN`, `0` as a stand-in, or
computed from a truncated sample without `reason` disclosure. `eg_p_bh` is `null` for any pair not
included in the BH correction's denominator (i.e. `status != "ok"`). Responses are gzip-compressed
via the existing app-wide `GZipMiddleware`.

**Path-param edge cases (added PVL cycle 1, resolves CONCERN-2):**
- **Self-pair (`a == b`)**: `GET /api/pairs/{a}/{a}` returns **422** (`{"detail": "a and b must be different coins"}`) — a coin is never cointegration-tested against itself; this is never silently treated as a degenerate/self-cointegrated `ok` pair.
- **Ticker case-sensitivity**: matching is **case-insensitive** — both `{a}` and `{b}` are normalized to uppercase (`.upper()`) before universe lookup, so `GET /api/pairs/btc/eth` and `GET /api/pairs/BTC/ETH` resolve identically. The universe file itself stores uppercase tickers only; normalization happens once, in the router, before any lookup.
- **Unknown ticker**: after uppercasing, if either `{a}` or `{b}` is not a member of the loaded universe, return **404** (`{"detail": "<TICKER> is not in the pair-screener universe"}`). This is unchanged from the original plan's "404 on non-member symbol" behavior — restated here for precedence against the self-pair check (self-pair is checked first, since `a == b` is a structural error independent of universe membership).

---

## 12. Infrastructure Deployment

Local only, unchanged. The deep-fetch script is user-run, occasionally (no scheduler, per SPEC Out
Of Scope).

## 12b. Storage Schema (Parquet files)

| Path | Columns | Write mode |
|---|---|---|
| `cache/ohlcv/{SYMBOL}/1d.parquet` (existing) | unchanged shape; extended with deeper history for universe coins | cache-first merge (existing `ccxt_adapter`/`cache.write_ohlcv` behavior, unmodified) |
| `api/data/pairs_universe.json` (new) | flat list/object of ticker strings | hand-edited only; no code writes it |

No new Parquet tables — this feature reads the existing OHLCV cache more deeply; it does not
introduce a new storage schema, and (per ADR-8) writes no results cache.

---

## 13. Phased Delivery Plan

### Current Status

All RFCs ⏳ PLANNED. Nothing in `process/features/cointegration-screener/active/pair-screener_25-09-26/`
has started beyond this plan and the locked SPEC.

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
   `ccxt_adapter.fetch_ohlcv(symbol, "1d", limit=DEEP_LOOKBACK_LIMIT)` per universe coin, prints a
   coverage table.

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

**Stages**
1. `compute_pair_stats(df_a, df_b, symbol_a, symbol_b) -> PairStatsResult` — inner-join on date,
   gate on `MIN_OVERLAP_DAYS = 365` (named constant), else `insufficient_overlap` with `reason`
   naming available/required day counts (AC-2).
2. Log-price transform (ADR-1); static OLS hedge ratio both directions (ADR-2a).
3. `coint()` both directions; rank by min-p; record both p-values and which direction is the
   rank-driving one (ADR-2b).
4. `coint_johansen(data, det_order=0, k_ar_diff=1)` → trace stat (r=0), 95% critical value,
   `rank_at_least_1` boolean (ADR-5).
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
  `insufficient_overlap`/`coin_unavailable` pairs (AC-8).
- Run: `uv run --project api pytest api/tests/analytics/test_cointegration_stats.py -q`, then the
  full suite.
- Verification query: a small script (or pytest `-s` print) runs `compute_pair_stats` for 3-5 real
  pairs from the live deep-fetched cache (e.g. BTC-ETH, BTC-SOL, a thin-overlap pair if one exists in
  the confirmed universe) and prints the full result — pasted into the phase report as a live sanity
  check (Hybrid, not asserted equal to any external reference — there is no independent oracle for
  real crypto pairs, unlike the regime dashboard's LiqTide cross-check).

**Verification Checklist**
- [ ] Manual test passed (live 3-5 pair sanity print reviewed — see phase report)
- [ ] Data verified (golden-value test output + live print pasted into report)
- [ ] Error handling confirmed (all four fixture branches + no-NaN assertion in tests)
- [ ] User confirmed working (golden values + live sanity print reviewed and approved)

**Acceptance Criteria**: AC-2, AC-3, AC-5 (BH itself is RFC-003, but the raw-p-value input this
stage produces is what RFC-003's BH correction consumes), AC-6, AC-8.
**What's Functional Now**: every pair's full statistical result is computable from cache.
**Ready For**: RFC-003.

**Implementation Checklist**
- [ ] Stage 0 findings (statsmodels return shapes + four fixture designs) presented; user approved
- [ ] `compute_pair_stats` + golden fixture tests (all four branches)
- [ ] No-NaN/no-stand-in assertion tests
- [ ] Live 3-5 pair sanity print run and pasted into report
- [ ] Full `pytest` green; RFC-001 tests unchanged and green

### RFC-003: Pydantic models + response serializer + router + perf-smoke

**Summary**: `api/models/pairs.py`, `api/analytics/cointegration/pairs_response.py`,
`api/routers/pairs.py` per §11 and ADR-8/ADR-9.
**Dependencies**: RFC-002.

**Stage 0**: read `api/models/regime.py` and `api/routers/regime.py` for the existing
Pydantic-model-plus-router pattern (typed status enums, gzip via app middleware, no new CORS/auth);
confirm `api/main.py`'s `include_router` wiring point; present the exact `PairSummary`/`PairDetail`
field lists (§11) and the perf-smoke threshold proposal (recommend: p95 < 3s warm-cache on the full
confirmed universe, matching the "no unbounded live network call" reasoning the momentum screener's
cold-start gap already documents) for user confirmation. **Also confirm the path-param edge-case
contract added at PVL cycle 1 (resolves CONCERN-2, §11): self-pair (`a == b`) → 422; ticker
matching normalized to uppercase before universe lookup (case-insensitive); unknown ticker (after
normalization) → 404, self-pair check takes precedence over the unknown-ticker check.** STOP.

**Stages**
1. `api/models/pairs.py` — `PairStatus`, `HalfLifeState` enums; `PairSummary`, `PairDetail`,
   `SpreadPoint` models per §11.
2. `api/analytics/cointegration/pairs_response.py` — enumerate `C(n,2)` pairs from the loaded
   universe; call `stats.compute_pair_stats` per pair; collect `ok`-pair raw EG p-values (min-p
   direction); `multipletests(raw_ps, method='fdr_bh')` (ADR-8); assemble `PairSummary[]` (every
   pair present, per AC-1) and single-pair `PairDetail` builder.
3. `api/routers/pairs.py` — `GET /api/pairs`, `GET /api/pairs/{a}/{b}` with server-side universe
   membership validation (404 on non-member symbol, 422 on malformed) — path params uppercased
   before lookup (case-insensitive matching); self-pair (`a == b`, post-uppercase) returns 422
   before the universe-membership check runs (§11 path-param edge cases).
4. `api/main.py` — one additive `app.include_router(pairs.router)` line; no other change to this
   file.

**Post-Phase Testing**
- Test file: `api/tests/routers/test_pairs.py` — table shape (every pair present, AC-1); BH
  correction applied only across `ok` pairs (AC-5, golden raw-p-value set with hand-computed
  expected BH-adjusted set, mirroring the SPEC's own AC-5 language); default response has no
  null-as-stand-in outside the documented `insufficient_overlap`/`coin_unavailable` cases; detail
  endpoint 404s on a non-universe symbol, 422 on malformed input; Johansen always present alongside
  EG for `ok` pairs, never merged (AC-6); `isolated_cache` used throughout.
- Path-param edge-case tests (added PVL cycle 1, resolves CONCERN-2): `GET /api/pairs/{a}/{a}`
  (self-pair, e.g. `BTC/BTC`) returns 422; `GET /api/pairs/btc/eth` (lowercase) resolves
  identically to `GET /api/pairs/BTC/ETH` (case-insensitive match, same response body); an unknown
  ticker after uppercasing (e.g. `GET /api/pairs/BTC/ZZZZ`) returns 404; a self-pair with an
  unknown ticker (e.g. `GET /api/pairs/zzzz/ZZZZ`) returns 422, not 404 (self-pair check
  precedence).
- Perf-smoke (Hybrid, precondition = real deep-fetched cache from RFC-001 must exist): time
  `GET /api/pairs` warm (API already running, cache populated) via a script or manual `curl -w
  "%{time_total}"`; record the number against the Stage-0-confirmed threshold. If it blows the
  threshold, apply the ADR-8 fallback (in-process TTL cache) and re-measure — do not silently accept
  a slow endpoint.
- Run: `uv run --project api pytest api/tests/routers/test_pairs.py -q`, then full suite.
- Verification: `curl "http://127.0.0.1:8000/api/pairs" | python -m json.tool | head -80` and
  `curl "http://127.0.0.1:8000/api/pairs/BTC/ETH" | python -m json.tool`.

**Verification Checklist**
- [ ] Manual test passed (curl both endpoints against real cache — see phase report)
- [ ] Data verified (row counts match universe's `C(n,2)`; BH-corrected values spot-checked)
- [ ] Error handling confirmed (404/422 tests; `coin_unavailable`/`insufficient_overlap` rows render)
- [ ] User confirmed working (perf-smoke number + endpoint output reviewed)

**Acceptance Criteria**: AC-1, AC-4 (sort ordering is RFC-004's UI concern but is validated here at
the data level — BH-p ascending is the array's natural consumption order), AC-5, AC-6, AC-8.
**What's Functional Now**: both endpoints serve real data from the deep-fetched cache.
**Ready For**: RFC-004.

**Implementation Checklist**
- [ ] Stage 0 findings (field lists + perf threshold) presented; user approved
- [ ] Models + response serializer + BH correction + tests
- [ ] Router + 404/422 handling (incl. self-pair 422, case-insensitive uppercase matching,
  unknown-ticker 404, self-pair-precedence-over-unknown-ticker) + tests
- [ ] `api/main.py` one-line registration
- [ ] Perf-smoke run against real cache; threshold met or fallback applied and re-measured
- [ ] Full `pytest` green; regime/screener router tests unchanged and green

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
- [ ] Manual test passed (table + two detail pages reviewed against a running API)
- [ ] Data verified (row values cross-checked against RFC-003's curl output)
- [ ] Error handling confirmed (API-down notice; insufficient/unavailable rows render correctly)
- [ ] User confirmed working (table sort + detail views reviewed and approved)

**Acceptance Criteria**: AC-2 (row rendering), AC-4, AC-6, AC-7 (chart date range vs. displayed
sample window — proven fully in RFC-005's Playwright spec, spot-checked manually here), AC-8.
**Ready For**: RFC-005.

**Implementation Checklist**
- [ ] Stage 0 findings (reuse points + route shape + table approach) presented; user approved
- [ ] Types + API client + formatters + tests
- [ ] `PairsTable` + tests
- [ ] `PairDetailView` + tests
- [ ] Pages wired + linked from home; manual walkthrough done
- [ ] `pnpm --filter web test` green

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
   override precedent) so the E2E run never touches the real universe file.
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
- [ ] E2E green (`pairs.spec.ts` + existing `screener.spec.ts`, run twice)
- [ ] Data verified (fixture manifest facts pasted; live-cache walkthrough outcome recorded either way)
- [ ] Error handling confirmed (thin-overlap and unavailable rows render correctly in the E2E)
- [ ] User confirmed working (isolation diff reviewed; walkthrough outcome accepted)

**Acceptance Criteria**: AC-7 (full proof), AC-9, AC-10, AC-11 (full proof), AC-12 (E2E-level
`coin_unavailable` fixture case).
**What's Functional Now**: the pair screener, end to end, provably isolated from the momentum
screener.

**Implementation Checklist**
- [ ] Seeder extended with `pairs` fixture section + override env var; tests for the seeder itself
- [ ] `pairs.spec.ts` written and green, run twice
- [ ] Full pytest + vitest + both Playwright specs green
- [ ] `git diff --stat` isolation proof pasted into phase report (empty output)
- [ ] Real-cache walkthrough outcome recorded (ran here, or deferred to user's PC as a known-gap)

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

**UPDATE PROCESS item (carried from SPEC Background, not actioned in this plan):**
`process/features/cointegration-screener/_GUIDE.md` (its "Key Source Files" section) still names
`api/routers/screener.py` and `web/app/screener/` as this feature's target locations — a naming
collision predating this plan (those are the momentum screener's files). UPDATE PROCESS after RFC-005
must correct `_GUIDE.md` to point at this feature's actual new files
(`api/routers/pairs.py`, `web/app/pairs/`, `api/analytics/cointegration/`, etc.).

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
| API scripts | `api/scripts/backfill_pairs_universe.py` (new), `api/scripts/seed_e2e_cache.py` (extend) | |
| API analytics | `api/analytics/cointegration/stats.py`, `api/analytics/cointegration/pairs_response.py` | new |
| API models/router | `api/models/pairs.py`, `api/routers/pairs.py` | new |
| API main | `api/main.py` | one additive `include_router` line |
| API tests | `api/tests/data/test_pairs_universe.py`, `api/tests/scripts/test_backfill_pairs_universe.py`, `api/tests/analytics/test_cointegration_stats.py`, `api/tests/routers/test_pairs.py` | new |
| Web | `web/lib/types/pairs.ts`, `web/lib/api/pairs.ts`, `web/lib/format-pairs-value.ts`, `web/components/pairs/*`, `web/app/pairs/page.tsx`, `web/app/pairs/[a]/[b]/page.tsx`, `web/app/page.tsx` (link) | new + one-line link |
| Web tests | `web/lib/__tests__/format-pairs-value.test.ts`, `web/components/pairs/__tests__/*`, `web/e2e/pairs.spec.ts` | new |
| Cache | `api/data/cache/ohlcv/{SYMBOL}/1d.parquet` (existing files) | extended with deeper history for universe coins only |
| Context | `process/features/cointegration-screener/_GUIDE.md`, `process/context/all-context.md`, `all-tests.md` | UPDATE PROCESS after RFC-005 |

**Must NOT change (hard blast-radius exclusion, verified by RFC-005's `git diff --stat`):**
`api/routers/screener.py`, `api/data/watchlist.py`, `web/app/screener/**`, `api/analytics/regime/**`.

Read-only: `api/data/ccxt_adapter.py` (deep-fetch and market-resolution calls only, no edits),
`api/data/cache.py` (`read_ohlcv`/`write_ohlcv` calls only, no edits), `web/lib/api/regime.ts`
(structural precedent only).

## Public Contracts

- **New**: `GET /api/pairs` (§11 shape), `GET /api/pairs/{a}/{b}` (§11 shape);
  `compute_pair_stats()` Python function; `pairs_universe` loader's public read function.
- **Must stay identical**: `GET /api/screener/board`, `GET /api/regime/components`,
  `GET /api/regime/legs`, every existing narrative/watchlist endpoint, `watchlist.py`'s public
  functions, `ccxt_adapter.fetch_ohlcv`'s signature and return type (called, never modified).

## Blast Radius

- ~18-22 new files, 3 modified files (`api/pyproject.toml`, `api/uv.lock`, `api/main.py` — all
  additive), across `api/` and `web/`. Extends (does not replace) existing OHLCV Parquet cache files
  for the ~18 universe coins.
- Risk class: **low-medium**. Low for existing features (new router/models/analytics module, no
  shared imports, additive dependency); medium for the new `statsmodels` dependency's runtime cost
  on the on-request compute path (ADR-8), gated by RFC-003's perf-smoke step and its documented
  fallback.
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

## Resume and Execution Handoff

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
Date: 25-09-26
date: 2026-09-25
generated-by: outer-pvl
supersedes: 2026-09-25 (outer-pvl) — outer-pvl has current evidence after PVL supplement cycle 1

Parallel strategy: sequential
Rationale: 3/7 signals present (S2 new public API surface, S6 public-API blast-radius entry, S7 18-22 files) — raw score lands in the MEDIUM/parallel-subagents band, but the work is a single Complex plan with 5 RFCs in a hard, explicitly STOP-gated dependency chain (each RFC's own "Dependencies" field names the prior RFC; the Phased Execution Workflow requires a user/PVL checkpoint between every RFC). No independent, non-overlapping fan-out exists inside this plan — sequential is the fit, not the raw signal count. This re-validation pass (post-PVL-cycle-1) ran as a single sequential synthesis (sonnet) for the same reason — the two open CONCERNs both traced to one artifact (this plan file) with no independent sub-scopes to parallelize. EXECUTE model: opus (one `vc-execute-agent` per RFC, in order).

Drift check (re-confirmed this session, branch `main`, HEAD `35e646f` — unchanged since the first-pass contract; no commits landed between cycles): all first-pass drift findings still hold verbatim (adapter/router/middleware/gitignore/workflow facts unchanged). This session additionally re-verified the CONCERN-1 fix mechanically against live source, not just against the feasibility VERDICT text: read `api/data/ccxt_adapter.py::fetch_ohlcv` directly (lines 312-393) and confirmed (a) the warm-cache skip at `if since is None and _cache_is_fresh(...)` only fires when `since is None` — an explicit `since` bypasses it unconditionally; (b) `effective_since = since` is used as-is when the caller passes `since` explicitly — the "top up from last cached bar" override at `if effective_since is None and not cached.empty` only fires when `since` is `None`; (c) `cache.write_ohlcv` (confirmed via `isolated_cache` fixture inspection, `api/tests/conftest.py` lines 26-34) merges via `pd.concat` + the cache module's own sort/dedupe, matching what RFC-001's rewritten Stage 0 assumes. This closes the residual doubt the first-pass contract's `VC-FEASIBILITY-PROBE-NEEDED` line had flagged (that pass could not run Python/uv at all) — the mechanism the plan now specifies is confirmed correct against the actual installed adapter, not just the feasibility VERDICT's offline ccxt-source reasoning. Also re-confirmed: `api/data/watchlist.json` is a real, separate file (not just `watchlist.py`) — the AC-11 test's "never touches `api/data/watchlist.json`" assertion target exists. Also re-confirmed: none of `api/tests/data/`, `api/tests/scripts/`, `api/tests/analytics/`, `api/tests/routers/` contain any `pairs`/`cointegration`-named test file yet, and `api/analytics/cointegration/`, `api/routers/pairs.py` do not exist yet — nothing has been implemented (Status Strip's "all RFCs ⏳ PLANNED" is accurate), so this is a clean pre-EXECUTE validation with no partial-implementation drift to reconcile. Other active plans referencing `fetch_ohlcv` (`momentum-screener_17-09-26/*`, `liqtide-snapshot-tooling_20-09-26`) are prior completed/verified work, not concurrent in-flight EXECUTE — no live conflict.

Feasibility probe: RESOLVED this cycle. `pair-screener_FEASIBILITY_25-09-26.md` — verdict VIABLE, re-confirmed against live `ccxt_adapter.py` source in this session (see Drift check above). The 3 named known-gaps from the VERDICT (live server-side cap-hit truncation behavior, real per-coin Hyperliquid listing dates, bulk rate-limit/backoff behavior under an 18-coin sequential loop) remain genuinely open — they are empirical facts no source read can establish — and are carried forward as accepted known-gaps with a Hybrid/user-PC real-run verification step (RFC-001's "Real-run hybrid verification" Post-Phase Testing item, gap-resolution B in the table below), not silently dropped and not blocking this PASS.

Test gates (C3 5-column table — ADDITIVE; existing consumers still parse the legacy line form below it):

| criterion id | behavior | strategy | proving test | gap-resolution |
|---|---|---|---|---|
| AC-1 | Every pair from curated list appears as exactly one row (C(n,2), no dupes) | Fully-Automated | `api/tests/data/test_pairs_universe.py::test_pair_enumeration` + `api/tests/routers/test_pairs.py::test_table_shape` | A |
| AC-9 | Universe loader structurally isolated from `watchlist.py` (no import, no shared function calls) | Fully-Automated | `api/tests/data/test_pairs_universe.py::test_loader_isolation` (`sys.modules`/import-graph assertion) | A |
| AC-11 (mechanics) | Deep-fetch script extends (not replaces) a pre-seeded cache via explicit-`since` (never `since=None`) calls; momentum-screener cache untouched | Fully-Automated | `api/tests/scripts/test_backfill_pairs_universe.py` with `isolated_cache` — seeds a SHALLOW 501-bar cache, mocks the exchange to return deep history on explicit-`since` calls, asserts post-backfill row count/date range reach the mocked deep start (not "row count increased"); asserts `since=None` is never used; mocked cap-hit pagination test (CONCERN-1 fully closed — resolved and re-confirmed against live adapter source this cycle) | A |
| AC-11 (live) | Real per-coin coverage table (row count, first/last date) after one live deep fetch | Hybrid — precondition: real Hyperliquid reachability from wherever RFC-001 actually runs | DuckDB coverage query output pasted into the RFC-001 phase report; carries the 3 feasibility-VERDICT known-gaps (cap-hit truncation, real listing dates, rate-limit/backoff) | B |
| AC-2, AC-3, AC-8 | Golden-value branches: cointegrated / non-cointegrated / not-mean-reverting / insufficient-overlap; no NaN/inf in any output field | Fully-Automated | `api/tests/analytics/test_cointegration_stats.py` (4 fixtures) | A |
| AC-3 (real-data sanity) | Live 3-5 pair sanity print on the real deep-fetched cache, eyeballed not asserted-equal (no independent oracle exists) | Hybrid — precondition: real deep-fetched cache from RFC-001 | RFC-002 phase-report print | B |
| AC-1, AC-5, AC-8 | Table shape + BH correction golden test (hand-computed raw-p → expected BH-adjusted set) + no-NaN/no-stand-in outside documented states | Fully-Automated | `api/tests/routers/test_pairs.py` | A |
| — (contract hardening) | 404 on invalid symbol; 422 on a self-pair (`a == b`, checked before universe-membership); ticker matching case-insensitive (uppercase-normalized before lookup) | Fully-Automated | `api/tests/routers/test_pairs.py::test_self_pair_422`, `::test_case_insensitive_match`, `::test_unknown_ticker_404`, `::test_self_pair_precedence_over_unknown` (CONCERN-2 fully closed — contract specified in §11, propagated to Stage 0/Stages/Post-Phase Testing) | A |
| — (perf, success metric) | p95 < 3s warm cache against the real ~153-190-pair deep-fetched cache | Hybrid — precondition: real deep-fetched cache + running API | RFC-003 phase-report timing output; ADR-8's in-process TTL-cache fallback + re-measure if threshold missed | B |
| AC-4 | Table default sort is live-computed ascending BH-p, not hardcoded to input order | Fully-Automated | `web/lib/__tests__/format-pairs-value.test.ts` (shuffled-fixture sort test) | A |
| AC-2, AC-6, AC-8 | Table + detail component rendering: insufficient/unavailable rows, both EG directions + Johansen simultaneous, injected-fetcher error path | Fully-Automated | `web/components/pairs/__tests__/*` | A |
| AC-2, AC-4, AC-6, AC-7 | Manual table + one `ok` + one `insufficient_overlap` detail-page walkthrough against a running API | Agent-Probe | RFC-004 manual walkthrough (phase report) | A |
| AC-1, AC-2, AC-6, AC-7, AC-12 | Full E2E: table renders fixture universe, default sort, thin-overlap row, chart date range == displayed sample window, Johansen+EG simultaneous, zero console errors | Fully-Automated | `web/e2e/pairs.spec.ts`, run twice | A |
| AC-10 | `git diff --stat` on the 4 hard-excluded paths (`screener.py`, `watchlist.py`, `web/app/screener/**`, `api/analytics/regime/**`) — empty output required | Fully-Automated | RFC-005 isolation check, pasted into phase report | A |
| AC-10 | Full existing `pytest`+`vitest`+`screener.spec.ts` re-run green, no regressions vs. the current baseline (392 passed/3 deselected pytest, 110/16 vitest, 26/26 Playwright — `screener.spec.ts` 6 of those 26) | Fully-Automated | RFC-005 full-suite re-run | A |
| AC-11 (full) / AC-3 (real-world) | Real-cache user walkthrough of `/pairs` against genuinely deep-fetched history | Agent-Probe (user) — known-gap in this container (egress blocks Hyperliquid; same precedent as the regime dashboard's AC-11 and the narrative dashboard's AC-3/AC-12) | User's own PC, per RFC-005 Stage 4 | D — backlog: plan stays in `active/` until the user confirms, exact precedent set by `regime-dashboard_24-09-26` |

gap-resolution legend:
- A — proven now (gate passes in this cycle)
- B — fixed in this plan (gate added by this plan's checklist)
- C — deferred to a named later phase/plan
- D — backlog test-building stub (named residual; keep-active; continue)

C-4 reconciliation: every `strategy:` value above is one of the 3 proving strategies (Fully-Automated / Hybrid / Agent-Probe). The one D-resolution row (real-cache walkthrough) still carries a proving strategy (Agent-Probe, user-run) plus separate Fully-Automated mechanical coverage of the same underlying behavior (the `isolated_cache` extension test) — this is a named residual with a resolution path, not an ungated behavior, so the net gate is not vacuously green on it.

Legacy line form (retained so existing validate-contract consumers still parse):
- Universe/deep-fetch (RFC-001): `Fully-automated: uv run --project api pytest api/tests/data/ api/tests/scripts/ -q` | `hybrid: real deep-fetch + DuckDB coverage query (needs Hyperliquid reachability)`
- Stats engine (RFC-002): `Fully-automated: uv run --project api pytest api/tests/analytics/test_cointegration_stats.py -q` | `hybrid: live 3-5 pair sanity print (needs real cache)`
- API (RFC-003): `Fully-automated: uv run --project api pytest api/tests/routers/test_pairs.py -q` | `hybrid: perf-smoke curl timing (needs real cache + running API)`
- Web (RFC-004): `Fully-automated: pnpm --filter web test` | `agent-probe: manual table + detail walkthrough`
- E2E + isolation (RFC-005): `Fully-automated: cd web && pnpm test:e2e` + `uv run --project api pytest api/ -q` (full suite) + `git diff --stat` isolation check | `agent-probe: real-cache user walkthrough (known-gap, user's PC)`

Failing stub (AC-1, pair enumeration):
```
test("should enumerate exactly C(n,2) pairs with no duplicates for the curated universe", () => {
  throw new Error("NOT IMPLEMENTED — TDD stub: pair-enumeration unit test, test_pairs_universe.py")
})
```

Failing stub (AC-9, loader isolation):
```
test("should not import or read api/data/watchlist.py from the pairs_universe loader module", () => {
  throw new Error("NOT IMPLEMENTED — TDD stub: loader import-graph isolation test, test_pairs_universe.py")
})
```

Failing stub (AC-11 mechanics, deep-fetch extension with shallow pre-seed):
```
test("should extend a pre-seeded SHALLOW (501-bar) cache to near-DEEP_LOOKBACK_LIMIT depth via explicit-since calls, not just append a few forward bars, and never call fetch_ohlcv with since=None", () => {
  throw new Error("NOT IMPLEMENTED — TDD stub: test_backfill_pairs_universe.py, shallow-cache-collision case, see resolved CONCERN-1")
})
```

Failing stub (AC-2/AC-3/AC-8, golden-value branches):
```
test("should match hand-derived EG/Johansen/half-life/z-score values on the 4 synthetic fixtures (cointegrated, non-cointegrated, not-mean-reverting, short-overlap) with no NaN in any field", () => {
  throw new Error("NOT IMPLEMENTED — TDD stub: test_cointegration_stats.py")
})
```

Failing stub (AC-1/AC-5/AC-8, table + BH):
```
test("should return every pair as one row and apply BH correction only across status==ok pairs, matching a hand-computed expected set", () => {
  throw new Error("NOT IMPLEMENTED — TDD stub: test_pairs.py")
})
```

Failing stub (contract hardening, self-pair + case sensitivity):
```
test("should 422 on GET /api/pairs/{a}/{a} (self-pair, precedence over unknown-ticker), 404 on an unknown ticker, and match case-insensitively via uppercase normalization", () => {
  throw new Error("NOT IMPLEMENTED — TDD stub: test_pairs.py, see resolved CONCERN-2")
})
```

Failing stub (AC-4, sort order):
```
test("should sort ascending by BH-corrected p-value on a shuffled fixture, insufficient rows excluded from the sort key", () => {
  throw new Error("NOT IMPLEMENTED — TDD stub: format-pairs-value.test.ts")
})
```

Failing stub (AC-2/AC-6/AC-8, component rendering):
```
test("should render insufficient/unavailable rows with no stat columns and both EG directions + Johansen simultaneously for an ok pair", () => {
  throw new Error("NOT IMPLEMENTED — TDD stub: web/components/pairs/__tests__/*")
})
```

Failing stub (AC-1/AC-2/AC-6/AC-7/AC-12, E2E):
```
test("pairs table renders fixture universe, default sort, thin-overlap disclosure, chart date range matches displayed sample window", () => {
  throw new Error("NOT IMPLEMENTED — TDD stub: web/e2e/pairs.spec.ts")
})
```

Failing stub (AC-10, isolation):
```
test("git diff --stat on screener.py/watchlist.py/web/app/screener/**/api/analytics/regime/** is empty after this feature ships", () => {
  throw new Error("NOT IMPLEMENTED — TDD stub: RFC-005 isolation proof")
})
```

Dimension findings:
- Infra fit: PASS — unchanged from first pass. Local-only FastAPI/Next.js dev, no container/port/proxy surface touched; one additive `include_router` line; no new middleware needed (`GZipMiddleware` already app-wide).
- Test coverage: PASS (upgraded from CONCERN) — both first-pass gaps are now closed in plan text and mechanically re-verified this session: the AC-11 mechanical test now explicitly seeds a shallow pre-existing cache, mocks explicit-`since` deep fetch, and asserts final depth (not "row count increased"), plus a `since=None`-never-used assertion and a mocked cap-hit pagination test (closes the original test-coverage gap around CONCERN-1); RFC-003's Post-Phase Testing now names 4 explicit self-pair/case-sensitivity router tests (closes the original gap around CONCERN-2). Coverage remains one of the more complete test plans in this repo (4 golden-value branches, BH golden test, no-NaN assertions, sort test, component tests, full E2E, isolation proof, satisfies Standing Lesson #4).
- Breaking changes: PASS — unchanged. New router/models/analytics module only; `api/main.py`'s one added line is additive; `Must NOT change` list is explicit and enforced by RFC-005's own `git diff --stat` gate; no shared imports found anywhere in the current tree (re-confirmed this session).
- Security surface: PASS — unchanged. No auth/secrets/billing touched; API stays bound to 127.0.0.1, CORS unchanged; `pairs_universe.json` is a local hand-edited file with no write endpoint; `{a}`/`{b}` path params are validated against a closed universe list server-side (self-pair 422 + uppercase normalization before lookup, per resolved CONCERN-2) before any downstream use — no injection/traversal surface introduced.
- RFC-001 (Universe + deep-fetch): PASS (upgraded from CONCERN) — CONCERN-1 fully resolved. RFC-001 Stage 0 now specifies the exact deep-fetch mechanism (explicit early `since`, never `since=None`, defensive cap-hit pagination, mandatory per-coin bars/first-date logging), matching the feasibility VERDICT (VIABLE) and independently re-confirmed this session against live `ccxt_adapter.py` source (see Drift check above) — the explicit-`since` path genuinely bypasses both the warm-cache skip and the top-up-only default that caused the original 4-coin (BTC/ETH/HYPE/SOL) shallow-cache collision. `ccxt_adapter.py` stays fully read-only as required.
- RFC-002 (Stats engine): PASS — unchanged. ADR-1/ADR-3/ADR-4 textbook-correct and internally consistent; ADR-5's fixed `det_order=0, k_ar_diff=1` specification is a defensible v1 simplification. E4 (golden-fixture clarification: pinned-baseline for EG/Johansen test statistics, hand-computed for AR(1)/hedge-ratio/z-score) remains a live, non-blocking execute-agent instruction for RFC-002 Stage 0.
- RFC-003 (Endpoint): PASS (upgraded from CONCERN) — CONCERN-2 fully resolved. `GET /api/pairs/{a}/{b}` path-param contract now fully specified in §11: self-pair (`a == b`) → 422 (checked first, precedence over unknown-ticker); ticker matching case-insensitive (uppercase-normalized before lookup); unknown ticker (post-normalization) → 404. Propagated into Stage 0, Stages, Post-Phase Testing (4 new test cases), and Implementation Checklist. Perf-smoke threshold (p95 < 3s, ~153 pairs, each needing 2-direction EG + Johansen + AR(1) OLS) remains a real, not-yet-measured risk — already correctly tiered Hybrid with an in-scope ADR-8 fallback (in-process TTL cache); this is a residual noted for visibility, not a gate blocker.
- RFC-004 (Web): PASS — unchanged. Reuse points (`ComponentPanel.tsx`, `DeadDataNotice.tsx`, `format-unavailable-reason.ts`, `regime.ts`'s fetch pattern) all confirmed to exist; no new dependency proposed.
- RFC-005 (E2E + isolation proof): PASS — unchanged. `seed_e2e_cache.py` already follows the guard→write-through-real-cache-functions→shared-manifest pattern (confirmed this session: `build_regime_fixture`/`seed_regime`, `build_narrative_fixture`/`seed_narrative` both present) that RFC-005's `pairs` section extends cleanly; real-cache-walkthrough known-gap correctly follows the regime-dashboard AC-11 precedent.

Open gaps:
- Perf-smoke threshold (p95 < 3s) — not yet measured; already correctly tiered Hybrid with an in-scope ADR-8 fallback (in-process TTL cache) — no action needed beyond what the plan already specifies. Not a CONCERN.
- Real-cache user walkthrough (AC-11 full, AC-3 real-world) — accepted known-gap per the regime-dashboard AC-11 / narrative-dashboard AC-3/AC-12 precedent (egress-blocked container); plan correctly stays in `active/` until the user confirms on their own PC. Not a CONCERN.
- 3 feasibility-VERDICT known-gaps (live server-side cap-hit truncation behavior, real per-coin Hyperliquid listing dates, bulk rate-limit/backoff under an 18-coin sequential loop) — accepted known-gaps, empirical facts no source read can establish; carried by RFC-001's Hybrid real-run gate (gap-resolution B), not silently dropped.
- CONCERN-1 and CONCERN-2 from the first-pass contract are CLOSED this cycle — no longer open gaps (see Dimension findings above and the PVL Supplement Log).

What this coverage does NOT prove:
- The `test_cointegration_stats.py` golden-value tests prove statsmodels output matches a pinned fixture computation — they do NOT prove the statistical PROCEDURE (min-of-both-directions EG ranking, then BH across those min-p's) controls the false-discovery rate at its nominal level; ADR-2b's "mild optimism bias" is disclosed in the UI, not statistically corrected, by deliberate v1 design.
- The strengthened `isolated_cache` deep-fetch test proves the SCRIPT'S cache-write mechanics are correct for a given mocked input (including the explicit-`since`/never-`None` and cap-hit-pagination behaviors) — it does NOT prove ccxt/Hyperliquid's LIVE response shape for those same code paths; that is exactly what RFC-001's Hybrid real-run gate and its 3 named known-gaps cover, not this unit test.
- The perf-smoke Hybrid gate proves ONE measured timing on ONE run against the real cache at plan-time hardware/network conditions — it does NOT prove the threshold holds under concurrent requests or after the universe grows (Future Work item, explicitly out of scope for v1).
- `pairs.spec.ts` (seeded-fixture E2E) proves the frontend/backend boundary and the seeded scenarios named in RFC-005 — it does NOT substitute for the real-cache walkthrough (AC-11 full), which is the only gate that exercises genuinely deep, non-synthetic history end to end.
- The `git diff --stat` isolation proof proves the 4 named paths are byte-unchanged — it does NOT prove the absence of new SHARED RUNTIME state (e.g. a future accidental import); AC-10's "no shared runtime state" claim rests on RFC-001/RFC-010's module-boundary design (ADR-10) plus the loader-isolation unit test, not on the diff check alone.

Gate: PASS (0 FAILs, 0 CONCERNs — both first-pass CONCERNs [CONCERN-1 material, CONCERN-2 minor] fully closed by PVL supplement cycle 1 and independently re-verified against live source this session; the previously-open feasibility probe is resolved [VIABLE, re-confirmed]; the vacuous-green check holds — every developed behavior in the test gates table carries a Fully-Automated, Hybrid, or Agent-Probe proving gate, with only accepted, named, non-blocking residuals [perf-smoke measurement, real-cache walkthrough, 3 feasibility known-gaps] carried forward as Hybrid/Agent-Probe/known-gap rows, not silent gaps)
Accepted by: session (autonomous, PVL re-validation) — Gate is PASS, no unresolved CONCERNs requiring acceptance. The 3 residuals above (perf-smoke measurement, real-cache walkthrough, feasibility known-gaps) were already accepted as documented, gated residuals in the first-pass contract and remain accepted unchanged.

### Execute-Agent Instructions

| # | Instruction | Trigger condition | Status |
|---|---|---|---|
| E1 | ~~Resolve CONCERN-1 before writing `backfill_pairs_universe.py`~~ | RFC-001 Stage 0, before Stage 1 | **APPLIED (PVL cycle 1)** — RFC-001 Stage 0 text now specifies the exact mechanism (explicit early `since`, never `since=None`, defensive cap-hit pagination, per-coin bars/first-date log), re-confirmed against live adapter source this cycle. Execute-agent still pastes the resulting per-coin bar count/date range into the RFC-001 phase report before Stage 0 findings are presented for approval — that evidence step remains live, only the "how" is no longer undetermined. |
| E2 | ~~Strengthen the AC-11 mechanical test~~ | RFC-001 Post-Phase Testing | **APPLIED (PVL cycle 1)** — plan text's Post-Phase Testing section already specifies the shallow-pre-seed + mocked-deep-history + final-depth-assertion design, plus the `since=None`-never-used and mocked-cap-hit-pagination sub-tests. |
| E3 | ~~Decide and test self-pair/case-sensitivity at RFC-003 Stage 0~~ | RFC-003 Stage 0 | **APPLIED (PVL cycle 1)** — §11, Stage 0, Stages, and Post-Phase Testing all now specify the full contract (422 self-pair, case-insensitive uppercase match, 404 unknown, self-pair precedence). |
| E4 | At RFC-002 Stage 0, when presenting the four golden-value fixture designs for `coint()`/`coint_johansen()`, make explicit that a hand-derived expected value means a fixed-seed, comfortably-clear-margin synthetic series (not borderline) with the exact statsmodels output pinned as the reviewed baseline — not independent hand-computation of an asymptotic test statistic. The AR(1) half-life, OLS hedge ratio, and z-score fixtures can and should be independently hand-computed. | RFC-002 Stage 0 | Still live — not yet incorporated into plan text; low-cost process guidance, non-blocking. |

### Proposed Plan Updates

| # | What changes | Where in plan | Why | Status |
|---|---|---|---|---|
| P1 | RFC-001 Stage 0 deep-fetch mechanism | RFC-001, Stage 0 | Prevents a silent partial-sample violation of AC-8 for 4 of 18 universe coins (~40% of pairs) | **APPLIED (PVL cycle 1)**, re-confirmed this cycle against live source |
| P2 | Self-pair/case-sensitivity contract | RFC-003, Stage 0 | Small, previously-unstated API contract gap | **APPLIED (PVL cycle 1)** |

### Backlog Artifacts

| Artifact | Location | What it tracks |
|---|---|---|
| (none required — CONCERN-1/CONCERN-2 were in-plan execute-agent instructions, both applied; no deferred work) | — | — |

### PVL Supplement Log

**Cycle 1 (25-09-26)** — addressed both CONCERNs from the first-pass validate-contract (`Gate: CONDITIONAL`):

- **CONCERN-1 (RFC-001, material)** — resolved using the feasibility VERDICT (`pair-screener_FEASIBILITY_25-09-26.md`, verdict: VIABLE). RFC-001 Stage 0 rewritten with the exact deep-fetch mechanism: explicit early `since` (never `since=None`), `limit=5000`, defensive page-forward pagination on a capped response, mandatory per-coin bars/first-date logging, `ccxt_adapter.py` stays read-only. RFC-001's AC-11 mechanical test strengthened to seed a shallow 501-bar cache, mock deep history, and assert final depth/first-date reaches the mocked deep start (not "row count increased"); added a `since=None`-never-used assertion and a mocked cap-hit pagination test. Added a real-run hybrid gate (bars-per-coin log, user-PC if egress blocked) and recorded the feasibility VERDICT's three uncertainties as named known-gaps, not silently dropped.
- **CONCERN-2 (RFC-003, minor)** — resolved by specifying the `GET /api/pairs/{a}/{b}` path-param contract in §11 API Surface: self-pair (`a == b`) → 422; ticker matching case-insensitive (uppercase-normalized before universe lookup); unknown ticker (post-normalization) → 404; self-pair check takes precedence over the unknown-ticker check. Propagated into RFC-003's Stage 0, Stages (router description), Post-Phase Testing (4 new test cases), and Implementation Checklist.
- Proposed Plan Updates P1 and P2 (above) are both marked APPLIED this cycle.
- Scope: no files outside this plan's existing blast radius were added; no new public API surface beyond the already-planned `GET /api/pairs`/`GET /api/pairs/{a}/{b}` endpoints; no new dependencies.
- Drift note: baseline test counts current as of `35e646f` (pytest 392/3, vitest 110/16, Playwright 26/26 incl. `screener.spec.ts`/`regime.spec.ts`/`narrative.spec.ts`) — unchanged (no code was written this cycle either).

**Re-validation (25-09-26, same session — this pass):** vc-validate-agent re-ran V1–V7 from V1 against the PVL-cycle-1-updated plan. Both CONCERNs independently re-verified as closed — CONCERN-1 by direct re-read of `api/data/ccxt_adapter.py::fetch_ohlcv`'s `since`/`effective_since`/`_cache_is_fresh` logic (not just re-reading the feasibility VERDICT text), CONCERN-2 by direct re-read of §11's path-param contract and its propagation into RFC-003's Stage 0/Stages/Post-Phase Testing. No new gaps found; no regressions found (isolation-relevant files/mechanisms — `main.py` router registration, `seed_e2e_cache.py` fixture pattern, `.gitignore` cache carve-outs, `watchlist.json` existence — all re-confirmed unchanged on disk). Net gate: **PASS**. Plan is ready for EXECUTE.

## Autonomous Goal Block

SESSION GOAL: Ship the pair-screener v1 (/pairs) — cointegration screen for a curated crypto universe.
Charter + umbrella plan: N/A — single plan, not a phase program. process/features/cointegration-screener/active/pair-screener_25-09-26/pair-screener_PLAN_25-09-26.md
Autonomy: standard RIPER-5 autonomy per process/development-protocols/orchestration.md — VALIDATE self-decided PASS this cycle (0 FAILs, 0 CONCERNs after PVL supplement cycle 1); EXECUTE still requires explicit ENTER EXECUTE MODE and the plan's own per-RFC STOP-and-approve checkpoints (Phased Execution Workflow) remain mandatory regardless of autonomy state.
Hard stop conditions / safety constraints:
- Never edit api/routers/screener.py, api/data/watchlist.py, web/app/screener/**, or api/analytics/regime/** (hard blast-radius exclusion, enforced by RFC-005's git diff --stat gate).
- Never edit api/data/ccxt_adapter.py (read-only; the deep-fetch mechanism lives entirely in the new backfill_pairs_universe.py).
- Paste the real per-coin bar-count/first-date evidence into the RFC-001 phase report before Stage 0 findings are presented for approval (E1 evidence step, still live even though the mechanism itself is now plan-text-settled).
- No new market-data provider; crypto-only v1 (equities explicitly out of scope, pending the separate LSE verification plan).
Next phase: EXECUTE MODE, starting RFC-001 Stage 0 (statsmodels add + smoke check + universe proposal + market-symbol resolution check) — STOP for user approval before writing any code, per the Phased Execution Workflow.
Validate contract: inline in this plan file, section "Validate Contract" above.
Execute start: uv run --project api pytest api/ -q (baseline: 392 passed, 3 deselected) | pnpm --filter web test (baseline: 110 passed, 16 files) | cd web && pnpm test:e2e (baseline: 26/26) — full commands in process/context/tests/all-tests.md | high-risk pack: no (no auth/billing/migration/deploy surface touched)
