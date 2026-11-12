---
name: plan:narrative-dashboard
description: "Standalone /narrative attention dashboard — history archive, exchange-volume proxy, wider coin map, nightly forward archive, comparison + change-in-attention views"
date: 24-09-26
feature: narrative-mindshare
---

[MODE: PLAN]

# Narrative Dashboard — History, Comparison, and a Fourth Attention Proxy

**Date**: 24-09-26
**Complexity**: Complex (standard complex — one authoritative plan, 6 sequential/semi-parallel RFCs)
**Status**: 🔨 CODE DONE — all 6 RFCs implemented, EVL-confirmed, committed and pushed
  (branch `claude/kind-tesla-tat3vo`, HEAD `7ef8eb3`). Not ✅ VERIFIED: AC-3 (cron firing),
  AC-12 (real-cache walkthrough), and two manual-first risk-pack review decisions
  (`harness/review-decision.json`, `harness/rfc-004/review-decision.json`) are pending on the
  user's own machine — see the amended Resume and Execution Handoff below. Plan stays in `active/`.
**Feature folder**: `process/features/narrative-mindshare/`
**Owner**: Jamiro (user) · executor: vc harness agents

> **TL;DR** — Build `/narrative`: a real-time-growing history chart per tracked category (not
> today's-only snapshot), a side-by-side comparison view, and a change-in-attention view, fed by
> the existing pytrends/Reddit/CoinGecko sources (unchanged maths) plus a new keyless Hyperliquid
> volume/new-listing proxy (display-only — never wired into the existing trigger/confirm pipeline,
> to guarantee `/screener`'s narrative contract stays byte-identical). History accumulates forward
> from a new nightly GitHub Actions workflow, the same pattern as `liqtide-snapshot.yml`; pytrends'
> own `interest_over_time()` backfills its own chart on day one, no other source is backfilled. The
> coin-to-category map widens past BTC/ETH/HYPE, sized against the real watchlist at RFC-1 Stage 0.

---

## Overview

The narrative/mindshare backend already exists — it shipped as momentum-screener RFC-003, not as
its own feature, and has never had a screen of its own. This plan graduates it: same backend code,
same `/screener` contract, new `/narrative` dashboard reading a history that already silently
accumulates in `cache.py::narrative_series_path` every time the backend is queried, just never
surfaced. Two new signals are added on top (exchange volume/new-listing activity, a wider coin
map) and the whole thing is fed by a scheduled nightly archive job.

The single hardest constraint in this plan is **AC-1**: nothing built here may change
`GET /api/narrative/categories`'s response shape or `/screener`'s narrative strip/confidence-badge
behavior by even one byte. Every RFC below is designed around that constraint first.

> **AC-1 amendment (25-09-26, narrative-keyword-keying fix — additive note only).** The AC-1
> byte-identical contract test (`api/tests/routers/test_narrative_categories_contract.py`) was
> validated against a seed that wrote pytrends/reddit history under the category id. The real
> adapters archive those two sources under the search keyword (`keywords[0]`), and
> `trigger.py::compute_narrative_categories` read them back by category id — so in production it
> always saw empty pytrends/reddit history. The test's seed matched the buggy read key, which masked
> the bug. The keyword-keying plan
> (`process/features/narrative-mindshare/active/narrative-keyword-keying_25-09-26/narrative-keyword-keying_PLAN_25-09-26.md`)
> fixed the reader (pytrends/reddit by keyword, coingecko by category id), moved the seed to
> keyword-keyed rows, and re-ran the golden fixture regeneration: the fixture came out
> **byte-identical**, because the old stubbed seed already produced the corrected 3-source values.
> Before/after evidence: `narrative-keyword-keying_DIFF_25-09-26.md` in that task folder. No
> `LEGACY_COIN_CATEGORY_MAP` / `mapping.py` change and no change to any AC-1 conclusion about
> mapping.

## Quick Links

- [1. Context and Goals](#1-context-and-goals)
- [Phase Completion Rules](#phase-completion-rules)
- [1.5 Execution Brief](#15-execution-brief)
- [Phased Execution Workflow](#phased-execution-workflow)
- [2. Non-Goals and Constraints](#2-non-goals-and-constraints)
- [3. Architecture Decisions (Final)](#3-architecture-decisions-final)
- [5. High-level Data Flow](#5-high-level-data-flow)
- [11. API Surface](#11-api-surface)
- [13. Phased Delivery Plan](#13-phased-delivery-plan)
- [15. RFCs](#15-rfcs)
- [Touchpoints](#touchpoints) · [Public Contracts](#public-contracts) · [Blast Radius](#blast-radius)
- [Verification Evidence](#verification-evidence) · [Resume and Execution Handoff](#resume-and-execution-handoff)

### Status Strip

| RFC | Title | Status |
|---|---|---|
| RFC-1 | Data foundation: category map JSON + history read/write | 🔨 CODE DONE — EVL-confirmed 24-09-26 (option B: curated JSON drives only `/history`/`/narrative`; legacy 3-coin map frozen for `/categories`/`/screener`) |
| RFC-2 | Exchange (Hyperliquid) adapter + pytrends historical backfill script | 🔨 CODE DONE — EVL-confirmed 24-09-26 (redistributable=False pending Hyperliquid terms check; real Hyperliquid/pytrends run is a user-PC step) |
| RFC-3 | `GET /api/narrative/history` endpoint + comparison/change maths | 🔨 CODE DONE — EVL-confirmed 24-09-26 (`harness/review-decision.json` PENDING user) |
| RFC-4 | Nightly forward-archive workflow | 🔨 CODE DONE — EVL-confirmed 24-09-26 (`harness/rfc-004/review-decision.json` PENDING user; first `workflow_dispatch` + AC-3 cron confirmation are user-PC steps after merge to `main`) |
| RFC-5 | `/narrative` page — history charts, comparison, change-in-attention, caveat | 🔨 CODE DONE — EVL-confirmed 24-09-26 |
| RFC-6 | End-to-end proof + AC-12 real-cache handoff | 🔨 CODE DONE — EVL-confirmed 24-09-26 (26/26 Playwright x2; found and fixed a real day-2 HTTP 500 in `/history`, see Post-EXECUTE Amendments). AC-12's live-provider portion is a user-PC step. |

---

## 1. Context and Goals

**Why now.** The narrative backend has been silently writing a growing time series to
`cache/narrative/{source}/{category}.parquet` since it shipped (`write_narrative_point`) and it has
never been shown to the user. This is the lowest-risk kind of feature graduation: no maths change
to the thing already in production, purely additive read/display surface, plus two bounded new
inputs (exchange proxy, wider map) that the SPEC explicitly scoped to free/keyless/display-safe.

**Context loaded for this plan** (per `process/context/all-context.md` routing):

- `process/context/all-context.md` — repo state, redistribution posture, testing lesson
- `process/context/data-sources/all-data-sources.md` — narrative "weakest link" framing, ccxt
  singleton pattern, Standing Rule 8 (forward-archive, never lose a day)
- `process/context/tests/all-tests.md` — runners, exact commands, "green ≠ verified" lesson
- `process/context/planning/all-planning.md` — complex-plan shape calibration
- `process/features/narrative-mindshare/_GUIDE.md` — scope, free-proxy-only constraint
- `process/features/cycle-regime/active/regime-dashboard_24-09-26/regime-dashboard_PLAN_24-09-26.md`
  — direct structural precedent (Status Strip, ADRs, RFC shape, Ops Runbook, Resume/Handoff)
- `api/data/cache.py` (narrative section), `api/analytics/narrative/{scoring,trigger,mapping}.py`,
  `api/routers/narrative.py`, `api/models/narrative.py`, `api/data/narrative_categories.json`
- `api/data/{pytrends,reddit,coingecko,ccxt}_adapter.py`, `api/data/watchlist.py`
- `api/scripts/{snapshot_liqtide.py,seed_e2e_cache.py}`, `.github/workflows/liqtide-snapshot.yml`,
  `api/main.py` (GZipMiddleware already global — new endpoint gets it for free)
- `web/components/regime/*`, `web/components/screener/NarrativeStrip.tsx`,
  `web/lib/{api,types}/*`, `web/lib/format-unavailable-reason.ts`, `web/e2e/regime.spec.ts`

**Research findings that shape this plan (24-09-26, from the repo):**

| Finding | Consequence |
|---|---|
| `cache.py::narrative_series_path`/`write_narrative_point` already write `date, raw_value, normalized_value, source_status` per (source, category) — forward-accumulating, already exists | History storage needs **zero schema change**; RFC-1 reuses it (Decision 2) |
| `pytrends_adapter.fetch_trend` uses only the latest point today; `pytrends.interest_over_time()` (unofficial lib) returns a real historical series when it succeeds | Basis for AC-4 backfill (Decision 2, RFC-2) |
| `COIN_CATEGORY_MAP` in `mapping.py` is a 3-entry Python dict (`BTC`, `ETH`, `HYPE`) | Move to curated JSON, size against `watchlist.read_watchlist()` at RFC-1 Stage 0 (Decision 7) |
| `routers/narrative.py` is a thin wrapper; `trigger.compute_trigger`/`assemble_narrative_categories` own the maths that produces `GET /api/narrative/categories`'s exact shape | A new `/history` endpoint must be a **separate function/router path**, sharing only `load_seed_categories`, so nothing touches the `/categories` code path (Decision 4) |
| `ccxt_adapter._exchange()` is already a thread-safe lazy singleton (fixed 19-09-26 cold-start issue) wrapping Hyperliquid | Reuse it for the new exchange proxy instead of a second exchange client (Decision 6) |
| `.gitignore` already carves out `api/data/cache/liqtide/` from the blanket `api/data/cache/*` ignore, with the exact same "parent must be per-entry excluded" mechanic documented inline | The new narrative nightly archive needs the identical carve-out pattern for `api/data/cache/narrative/` (RFC-4) |
| `format-unavailable-reason.ts` is the one shared place display copy for degraded states lives, driven by a `UnavailableReason` union | The new Reddit-nightly reason `credentials-not-configured` needs to be added there, not hand-rolled in a component (Decision 8) |
| `api/main.py` already has `GZipMiddleware(minimum_size=1000)` applied globally (RFC-004 decision 5 of the regime dashboard) | The new `/history` endpoint gets gzip automatically; nothing to add |
| `seed_e2e_cache.py` already has a `_guard()` + isolated `SCREENER_CACHE_ROOT`/`SCREENER_WATCHLIST_PATH` pattern and a `build_regime_fixture`-style per-feature builder | RFC-6 adds `build_narrative_fixture`/`seed_narrative` following that exact shape, not a new isolation mechanism |
| Widening `COIN_CATEGORY_MAP` changes `map_coin_to_category` for any newly-mapped coin, and `screener_board.py` reads that mapping into each coin's `narrative_state` | AC-1 only requires **BTC/ETH/HYPE** stay byte-identical — newly-mapped coins' screener badges WILL change. This is flagged as **Open Question OQ-4** below, not silently accepted |

**Goals**

1. Every tracked category (seed + auto-flagged) shows a real, growing attention-history chart from
   day one forward — not a single number.
2. See relative standing across all tracked categories at a glance, and which categories are
   gaining/losing attention fastest.
3. Add one more, price-independent attention signal (exchange volume/new-listing) without touching
   the existing trigger/confirm pipeline or its API contract.
4. Cover more of the user's actual watchlist in the coin-to-category map.
5. Never let `/screener`'s existing behavior drift by even one byte.
6. Never lose a day of narrative history once the nightly archive starts running.

**Success metrics**

- `GET /api/narrative/categories` response is byte-identical before/after this plan on a fixed
  input (contract snapshot test).
- `/narrative` renders a chart per tracked category built from ≥1 archived day, growing daily.
- A forced single-source failure (e.g. Reddit unconfigured) never blanks the dashboard or any other
  source's chart.
- Nightly workflow commits at least one new archive file per day once merged (confirmed by the user
  after a few nightly runs, same AC-3 shape as the regime dashboard's AC-1).

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

### RFC-1: Data foundation (category map JSON + history read/write)

- **What happens**: Stage 0 reads the real watchlist and proposes the widened category list + coin
  map for approval. Then `mapping.py` loads a new curated JSON instead of a hard-coded dict, and a
  thin `narrative_history` module wraps the existing `cache.narrative_series_path`/
  `write_narrative_point`/`read_narrative_series` functions with no schema change.
- **Integration points**: `mapping.load_category_map()` replaces `COIN_CATEGORY_MAP` constant
  lookups; `trigger.compute_trigger`, `screener_board.py` and `routers/narrative.py` are
  **unchanged callers** — same function signatures, same return shape.
- **Test**: contract snapshot of `GET /api/narrative/categories` before/after; unmapped coin still
  returns `None`.
- **Verify**: DuckDB read of one existing `narrative/{source}/{category}.parquet` file, row count.
- **Done when**: user reviews the widened map + category list and agrees; contract test green.

### RFC-2: Exchange adapter + pytrends backfill

- **What happens**: Stage 0 settles the exact Hyperliquid volume/new-listing formula. A new
  `hyperliquid_narrative_adapter.py` (or an addition to `ccxt_adapter.py` — decided at Stage 0)
  computes per-category volume share via `_exchange().fetch_tickers()` once/day and new-listing
  detection by diffing daily market-list snapshots. A new `backfill_pytrends_history.py` script
  calls `interest_over_time()` and writes rows with `source_status="backfilled"`.
- **Integration points**: reuses `ccxt_adapter._exchange()` singleton; writes through
  `cache.write_narrative_point` (no new cache surface).
- **Test**: pytest fixture-based tests for volume-share math and new-listing diff; opt-in
  integration test against the real exchange.
- **Verify**: run the backfill script against real pytrends (if reachable) and print rows written.
- **Done when**: user reviews the coverage table (source × category × first date).

### RFC-3: `/api/narrative/history` endpoint + maths

- **What happens**: new Pydantic models + router function returning grid-aligned history for every
  tracked category and source, plus comparison (relative standing = rank of per-category composite)
  and change-in-attention (rolling delta) values. Composite = skipna mean of within-source-
  normalised sources (mirrors `trigger.py`'s pattern, not a new normalisation rule).
- **Integration points**: new `routers/narrative.py::get_history` (separate function from
  `get_categories`); shares only `trigger.load_seed_categories`.
- **Test**: pytest golden values for composite/rank/delta; endpoint shape + degradation tests;
  contract snapshot re-run to prove `/categories` untouched.
- **Verify**: curl the new endpoint, check grid_dates/gap_before shape matches the regime pattern.
- **Done when**: user reviews sample output for 2+ categories.

### RFC-4: Nightly forward-archive workflow

- **What happens**: `.github/workflows/narrative-snapshot.yml` (new, same cron/commit pattern as
  `liqtide-snapshot.yml`) runs a new `api/scripts/snapshot_narrative.py` daily, fetching all four
  sources for every tracked category and writing one point per (source, category) via the existing
  `write_narrative_point`. `.gitignore` gets the `api/data/cache/narrative/` carve-out.
- **Integration points**: none beyond the writer functions RFC-1/RFC-2 already exposed.
- **Test**: run the script twice same day, second run doesn't duplicate; Reddit-unset path returns
  `credentials-not-configured` cleanly.
- **Verify**: dry-run output + a manual `workflow_dispatch` (or local run) showing new archive rows.
- **Done when**: user confirms the workflow file and runs it once manually.

### RFC-5: `/narrative` page

- **What happens**: `web/app/narrative/page.tsx` + `web/components/narrative/*` — one history chart
  per tracked category (soft-capped, overflow list), a comparison view, a change-in-attention view,
  `DataQualityCaveat` on every view, reusing `DeadDataNotice` for degraded sources.
- **Integration points**: `web/lib/api/narrative.ts`, `web/lib/types/narrative.ts` (new); no change
  to `NarrativeStrip.tsx` or any `/screener` component.
- **Test**: vitest per-component; injected-fetcher error states.
- **Verify**: manual browser walkthrough with seeded cache.
- **Done when**: user opens `/narrative`, sees all views, confirms caveat visible everywhere.

### RFC-6: End-to-end proof + AC-12 handoff

- **What happens**: `seed_e2e_cache.py` extended with a `build_narrative_fixture`/`seed_narrative`
  builder (multi-day history, one seeded gap, Reddit unset); `web/e2e/narrative.spec.ts` proves the
  real frontend/backend boundary. AC-3 (cron) and AC-12 (real-cache walkthrough) are handed to the
  user, same shape as the regime dashboard's AC-11.
- **Test**: `cd web && pnpm test:e2e`.
- **Done when**: E2E green here; user completes AC-3/AC-12 on their own machine.

### Expected Outcome

- `/narrative` shows one growing history chart per tracked category, a comparison view, and a
  change-in-attention view, all carrying a visible data-quality caveat.
- A new exchange-volume/listing signal is visible on the dashboard, computed honestly, never fed
  into the existing `/categories` trigger pipeline.
- The coin-to-category map covers more of the user's real watchlist; unmapped coins show an
  explicit state.
- `GET /api/narrative/categories` and `/screener`'s narrative strip are provably unchanged.
- A nightly job archives one point per (source, category) per day, automatically.

---

## Phased Execution Workflow

**IMPORTANT**: This plan uses a phase-by-phase execution model with built-in verification gates.
For each RFC:

- **Step 1: Pre-Phase Research** — read the existing code patterns named in the RFC's Stage 0,
  identify blockers, present findings to the user. **CRITICAL: present findings and STOP. Wait for
  user approval before Step 2. Do NOT bundle research + implementation into one agent call.**
- **Step 2: Detailed Planning** — exact files, exact functions, success criteria; get approval.
- **Step 3: Implementation** — execute the approved steps exactly; no deviations without a
  Change Management entry.
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

RFC-4 and RFC-5 may run in parallel sessions once RFC-3 is ✅ VERIFIED (both depend only on the
`/history` endpoint's shape, not on each other). RFC-6 waits for both.

---

## 2. Non-Goals and Constraints

**Non-goals**

- Any change to how `trigger.compute_trigger`, `scoring.normalize_within_source`, or the confirm
  logic compute a value.
- Any change to the confidence-badge weighting on `/screener`.
- Backfilling real history for Reddit, CoinGecko trending, or the exchange proxy — none has a
  usable historical endpoint (SPEC Out of Scope).
- Wiring the exchange proxy into `compute_trigger` as a fourth source — it is display-only in this
  plan (see ADR-6).
- Any paid narrative/social vendor.
- A directional call derived from narrative strength.
- Backtesting narrative against the 2017/2020-21 cycles (already ruled out in the momentum-screener
  SPEC).

**Constraints**

- All maths in Python; TypeScript renders only.
- Every provider behind an adapter in `api/data/`.
- Free, keyless sources only.
- Insufficient data → explicit state, never NaN/zero/interpolation.
- Normalize within source; never compare raw levels across providers.
- Narrative carries lower weight than price signals wherever combined elsewhere (unchanged).
- Redistribution flag recorded per source, including the new exchange proxy.
- `GET /api/narrative/categories` and `/screener`'s narrative strip stay byte-compatible.
- History is forward-archived, not retroactively reconstructed, except pytrends' own
  `interest_over_time()` window (locked user decision).
- This is a feature-folder graduation, not a rewrite — RFC-003 files stay in place; only docs
  record the ownership change (Decision 1).

---

## 3. Architecture Decisions (Final)

### ADR-1: RFC-003 files stay in place; docs record ownership change

**Decision**: no file under `api/analytics/narrative/`, `api/data/{pytrends,reddit,coingecko}_adapter.py`,
`api/routers/narrative.py`, or `api/models/narrative.py` moves or is renamed. `_GUIDE.md` and
`all-context.md` are updated to record that `narrative-mindshare` is now the planning/documentation
owner of that surface.

**Rationale**: SPEC Out of Scope explicitly forbids relocating shipped source files; the graduation
is organizational, not structural.

### ADR-2: History reuses `cache.py`'s existing writer/reader; no schema change

**Decision**: `narrative_series_path`/`write_narrative_point`/`read_narrative_series` are reused
as-is. The pytrends historical backfill writes rows with `source_status="backfilled"` (a plain
string value in an existing, untyped column — no migration). The backfill script must never
overwrite an already-archived (forward-written) point with a backfilled one — forward-written
points always win on conflict.

**Rationale**: Standing Rule ("numbers are never silently wrong") plus "one source of numerical
truth" — reusing the exact writer the backend already trusts avoids a second, drifting history path.

**Implications**: `write_narrative_point`'s existing signature is unmodified; the backfill script
calls it directly, checking `read_narrative_series` first to skip dates that already have a
forward-written (non-backfilled) point. **VALIDATE correction (24-09-26):** `write_narrative_point`'s
own dedup (`drop_duplicates(subset="date", keep="last")` after a non-stable `sort_values`) provides
NO source-priority guarantee on its own — it does not know "forward" from "backfilled" and, for two
rows sharing a date, which one survives is not reliably insertion-order-preserving. The
forward-wins guarantee described above is enforced **entirely** by the backfill script's own
read-before-write skip check, not by anything inside `write_narrative_point` itself. Do not treat
the writer as safe to call unconditionally for a date that might already be archived.

### ADR-3: Nightly archive is a new, separate workflow

**Decision**: `.github/workflows/narrative-snapshot.yml` (new file, does not touch
`liqtide-snapshot.yml`), running `api/scripts/snapshot_narrative.py` on its own cron, committing
`api/data/cache/narrative/` to `main`. `.gitignore` gains the same per-entry carve-out pattern used
for `api/data/cache/liqtide/` (`api/data/cache/*` + `!api/data/cache/narrative/`).

**Rationale**: keeps the two archive jobs independently schedulable/debuggable and mirrors the only
proven precedent in this repo exactly (Standing Rule 8).

### ADR-4: `/history` endpoint is a separate function and model set from `/categories`

**Decision**: `routers/narrative.py` gains a second route function, `get_history`, backed by a new
`analytics/narrative/history.py` module. It shares only `trigger.load_seed_categories` with the
existing `/categories` path — no shared response-assembly code. New models
(`NarrativeHistorySeries`, `NarrativeHistoryPoint`, `NarrativeComparisonEntry`,
`NarrativeChangeEntry`) live in `api/models/narrative.py`, additive to the file.

Response shape follows the regime dashboard's proven pattern: a shared `grid_dates` union across
all series, per-point `gap_before: bool`, per-series `max_gap_days`, and per-source
`availability`/`trust_weight`/`redistributable` metadata. Gzip is inherited from the existing
global `GZipMiddleware` — no per-route change needed.

**Rationale**: AC-1 requires zero risk to the existing endpoint's code path; a shared assembly
function is exactly the kind of coupling that could leak a shape change. `grid_dates`/`gap_before`
is a proven pattern already validated end-to-end on `/regime`.

### ADR-5: Composite, relative standing, and change-in-attention maths

**Decision**:
- Per-category composite = skipna mean of that category's within-source-normalised source values
  for the date (reuses `scoring.normalize_within_source`; mirrors `trigger.py`'s
  already-established pattern of combining per-source normalised series, not a new rule).
- Relative standing (comparison view) = rank of each category's composite among all tracked
  categories for the latest available date, recomputed per date requested.
- Change-in-attention = rolling delta of the composite over a fixed recent window (7 calendar days,
  matching `CONFIRMATION_SUSTAINED_DAYS`'s existing 10-day scale order of magnitude without
  reusing that exact constant, since this is a display metric, not a trigger).
- All in Python (`analytics/narrative/history.py`); TypeScript only renders the numbers it receives.

**Rationale**: reuses proven per-source normalisation instead of inventing a second scoring rule;
keeps "one source of numerical truth" intact.

### ADR-6: Exchange (Hyperliquid) proxy is display-only, never a 4th trigger source

**Decision**: the new exchange-volume/new-listing signal is computed in a new module
(`analytics/narrative/exchange_attention.py`) reading a new adapter (`api/data/
hyperliquid_narrative_adapter.py`, thin wrapper reusing `ccxt_adapter._exchange()`). It feeds
**only** the new `/history` endpoint's per-category source list — it is never passed into
`trigger.compute_trigger` and never appears in `GET /api/narrative/categories`'s response.
`fetch_tickers()` is called at most once/day (nightly job); per-category volume share =
category's aggregate 24h quote volume across its mapped coins ÷ total 24h quote volume across all
tracked coins; new-listing count = coins present in today's Hyperliquid market list but absent from
yesterday's daily snapshot, attributed to their mapped category (unmapped new listings recorded
under an explicit "unmapped" bucket, never dropped). **Day-1 / no-baseline behavior (E2)**: on the
first run, there is no prior day's market-list snapshot to diff against — `new_listing_count` MUST
be `null` with a distinct status/reason (e.g. `status: "unavailable"`, `reason: "no-baseline-yet"`),
never a bare `0`. A real zero-diff and "nothing to compare against yet" are different facts, and the
"numbers are never silently wrong" rule applies here exactly as it does to the three existing
sources. `redistributable=true` (Hyperliquid's public market data, no ToS restriction found at
RFC-2 Stage 0 — confirm and record).

**Rationale**: the orchestrator's INNOVATE decision is explicit — wiring this into
`compute_trigger` would change `/categories`' `source_availability`/`trust_weight` shape and risk
AC-1. Keeping it display-only in the `/history` path removes that risk entirely while still
satisfying AC-7 ("a fourth attention source... computed with the same failure discipline").

**Implications**: AC-7's failure discipline (explicit `unavailable`, never silent zero) applies to
this new module's own typed result, independently of the existing three sources' `TriggerResult`
shape.

### ADR-7: Coin-to-category map moves to curated JSON, sized against the real watchlist

**Decision**: `api/data/narrative_category_map.json` (new file, shape
`{"BTC": "store-of-value", "ETH": "l2s", ...}`) replaces the hard-coded `COIN_CATEGORY_MAP` dict.
`mapping.py::map_coin_to_category` loads it via a new `load_category_map()` function (same
load-shared-file pattern as `load_seed_categories`); an unmapped coin still returns `None`
(unchanged contract). At RFC-1 Stage 0, the agent reads `watchlist.read_watchlist()`'s real content
and proposes the widened map + any new category entries for `narrative_categories.json` for user
approval before implementation.

**Rationale**: SPEC AC-8 requires wider coverage; Decision Summary Decision 7 requires proof that
BTC/ETH/HYPE stay unchanged — moving to a data file (not touching the lookup contract) makes that
proof mechanical (a snapshot test of the three existing keys).

**Implications**: see Open Question **OQ-4** below — this decision widens map coverage but does
**not** decide whether newly-mapped coins' screener badges are allowed to change; that is
explicitly surfaced, not silently accepted. **VALIDATE correction (PVL cycle 1, 24-09-26):**
`map_coin_to_category` is not only reached via `screener_board.py`. `trigger.py::compute_narrative_categories`
— the function that directly backs `GET /api/narrative/categories` — also calls
`mapping.map_coin_to_category(symbol)` inside its CoinGecko trending-count loop (one call per
trending symbol, per seed category, to compute that category's `trending_count`, which is archived
and feeds `compute_trigger`'s composite/triggered/confirmed/trust_weight for that category). Today
only `l2s` (via `ETH`/`HYPE`) has a seed-category member; widening the map into `l2s` — or into any
other seed category once it gains a member — can change that category's `trending_count` on any day
a newly-mapped coin appears in CoinGecko's live trending list, which changes `/categories`' own
response, not just `screener_board.py`'s `narrative_state`. OQ-4's sign-off scope is corrected below
to cover this.

### ADR-8: Reddit in the nightly job degrades honestly, with a distinct reason

**Decision**: the nightly snapshot script calls the existing Reddit adapter exactly as the live
endpoint does — no new secret is required to ship. When `REDDIT_CLIENT_ID`/`REDDIT_CLIENT_SECRET`
are unset (the default in CI), the archived point for that source/category/day carries
`source_status="unavailable"` with the display reason `credentials-not-configured`, a new entry
added to `format-unavailable-reason.ts`'s mapping. If the user later wants Reddit history archived
from day one, the two secrets are documented as an optional GitHub Actions secret in the Ops
Runbook — a manual, off-repo step this plan cannot perform.

**Rationale**: resolves SPEC OQ-3 exactly as scoped — the existing adapter's degrade-cleanly
behavior is reused, not re-implemented.

### ADR-9: `/narrative` page layout — synced-panel pattern reused, soft cap on category panels

**Decision**: `web/app/narrative/page.tsx` + `web/components/narrative/{NarrativeDashboard,
CategoryHistoryPanel, ComparisonView, ChangeInAttentionView, DataQualityCaveat}.tsx`, mirroring the
regime dashboard's fetch-once/own-sync-state pattern (`RegimeDashboard.tsx` precedent) but with
independent (non-synced) chart instances per category — narrative categories are not a single
shared time axis the way regime components are, so cross-panel zoom/crosshair sync is not required
by the SPEC. `DeadDataNotice` is reused for any degraded source; a new shared
`DataQualityCaveat.tsx` component (not `DeadDataNotice`, which is per-series, not per-view) renders
the plain-language caveat and is included on every one of the three views (history, comparison,
change-in-attention), satisfying AC-11 mechanically.

**Soft cap**: the dashboard shows the **top 10** tracked categories by latest composite value as
individual history panels by default (seed categories always included regardless of rank, per
ADR-3 in the regime plan's own precedent for "never hide a triggered category"); any category
beyond 10 is available through an expandable "+N more categories" list below the panel grid that
renders the same panel component on demand — never a silently dropped category.

`NarrativeStrip.tsx` on `/screener` is not touched by any file in this RFC.

**Rationale**: independent panels avoid inventing a forced shared time axis across categories that
may start on very different dates (a seed category vs. a category auto-flagged yesterday); the
soft cap keeps the default view usable as the tracked-category list grows past the SPEC's OQ-1
answer, without ever hiding data — it is one click away, not gone.

### ADR-10: Tests cross the real cache boundary; AC-3/AC-12 are agent-probe/manual

**Decision**: pytest for the new history/exchange maths round-trips through the real
`cache.write_narrative_point`/`read_narrative_series` functions (Standing Lesson #7's fixture rule)
rather than hand-built in-memory series only; at least one test writes a narrative point and reads
it back through the real Parquet/DuckDB boundary (mirroring `test_cache_timezone.py`'s template) to
guard against ADR-6's timezone-boundary defect recurring for a fifth cached-reader class. vitest
covers component rendering/error states. `web/e2e/narrative.spec.ts` runs against a seeded fixture
cache exactly like `regime.spec.ts`. AC-3 (the scheduled trigger firing) and AC-12 (real-provider
walkthrough) cannot be proven in this sandboxed container (egress proxy blocks all four providers,
confirmed by the regime dashboard's AC-11 precedent) and are Agent-Probe/manual, handed to the user
in the Resume and Execution Handoff.

**Rationale**: directly follows the SPEC's own `proven by`/`strategy` declarations for AC-3/AC-4/
AC-12 and the project's Standing Lesson table (#5, #7) about testing at the boundary data actually
crosses.

---

## 5. High-level Data Flow

```
Google Trends (pytrends) ──► pytrends_adapter ─────────────────────────────┐
Reddit ──────────────────► reddit_adapter (unset creds → unavailable,      │
                                            reason credentials-not-configured)
CoinGecko trending ──────► coingecko_adapter ───────────────────────────────┤
Hyperliquid (ccxt) ───────► hyperliquid_narrative_adapter (NEW, display-only)┤
                                                                             │
        all four ──► cache.write_narrative_point (EXISTING, no schema change)
                          cache/narrative/{source}/{category}.parquet ──────┤
                                                                             ▼
                           analytics/narrative/history.py  (NEW)
              (per-category composite, relative standing/rank, change-in-attention,
               grid_dates union, gap_before/max_gap_days, redistributable per source)
                                                                             │
                    routers/narrative.py::get_history  GET /api/narrative/history (NEW)
                                                                             │
                                                        (UNCHANGED, separate code path)
        trigger.compute_trigger / assemble_narrative_categories ──► GET /api/narrative/categories
                                                        └──► /screener NarrativeStrip.tsx
                                                                             │
                          web/lib/api/narrative.ts ──► web/app/narrative/page.tsx
                          ──► NarrativeDashboard (history panels + comparison + change view
                                + DataQualityCaveat on every view)

Nightly (new, separate from liqtide-snapshot.yml):
  .github/workflows/narrative-snapshot.yml ──► snapshot_narrative.py ──► write_narrative_point
                                                                       (all 4 sources × N categories)

One-off, RFC-2:
  backfill_pytrends_history.py ──► pytrends interest_over_time() ──► write_narrative_point
                                                            (source_status="backfilled")
```

---

## 6. Security Posture

Unchanged: API bound to `127.0.0.1`, CORS limited to `localhost:3000` (plus the E2E override). No
new keys required to ship; Reddit's two existing optional secrets are unchanged. The new
Hyperliquid adapter reuses the existing keyless `ccxt_adapter._exchange()` singleton — no new
credentials, no new outbound provider identity.

---

## 7. Component Details

### `api/analytics/narrative/history.py` (new)

- Responsibilities: per-category composite, comparison ranking, change-in-attention delta,
  grid_dates union, gap flags, redistributable metadata assembly. Pure functions over DataFrames;
  one orchestrator `build_narrative_history(category_ids=None, date_range=None) -> NarrativeHistoryResult`.

### `api/analytics/narrative/exchange_attention.py` (new)

- Responsibilities: per-category volume share, new-listing diff detection. Typed result, never
  raises, `status: ok | unavailable`.

### `api/data/hyperliquid_narrative_adapter.py` (new)

- Thin wrapper around `ccxt_adapter._exchange()`; `fetch_daily_market_snapshot() -> ExchangeSnapshotResult`.

### `api/data/narrative_category_map.json` (new)

- Curated `{symbol: category_id}` map, sized at RFC-1 Stage 0 against the real watchlist.

### `web/components/narrative/NarrativeDashboard.tsx` (new)

- Fetches `/api/narrative/history` once; lays out history panels (soft-capped to 10 + expandable),
  `ComparisonView`, `ChangeInAttentionView`, `DataQualityCaveat` on each.

### `web/components/narrative/CategoryHistoryPanel.tsx` (new)

- One `createChart` per category; gap states via `DeadDataNotice`.

### `web/components/narrative/{ComparisonView,ChangeInAttentionView,DataQualityCaveat}.tsx` (new)

- Comparison: ranked bar/list of current composite per category. Change view: ranked delta list.
  Caveat: plain-language, static text component included on every view.

---

## 11. API Surface

### `GET /api/narrative/history`

Query: `categories` (comma-separated ids, optional — default all tracked), `start`/`end` (ISO
date, optional). Default: full history.

```json
{
  "generated_utc": "2026-09-24T18:00:00Z",
  "grid_dates": ["2026-09-24", "..."],
  "series": [
    {
      "category_id": "ai",
      "label": "AI",
      "source": "pytrends",
      "redistributable": false,
      "status": "ok",
      "reason": null,
      "first_date": "2026-09-10",
      "last_date": "2026-09-24",
      "max_gap_days": 2,
      "points": [
        { "date": "2026-09-24", "raw_value": 62.0, "normalized_value": 0.71,
          "source_status": "fresh", "gap_before": false }
      ]
    }
  ],
  "composite": {
    "points": [
      { "date": "2026-09-24", "category_id": "ai", "value": 0.68, "coverage": 0.75, "gap_before": false }
    ]
  },
  "comparison": {
    "as_of": "2026-09-24",
    "entries": [ { "category_id": "ai", "rank": 1, "value": 0.68 } ]
  },
  "change_in_attention": {
    "window_days": 7,
    "entries": [ { "category_id": "ai", "delta": 0.14, "rank": 1 } ]
  }
}
```

(Numbers illustrative only.) `status` per series ∈ `ok | stale | unavailable | presumed-dead`;
`points` never contains null/0 as a stand-in — a missing date is simply absent, `reason` names it.
The exchange-proxy series' `new_listing_count` field is `null` (never `0`) on its first run with
`status: "unavailable"` / `reason: "no-baseline-yet"` when no prior day's market-list snapshot
exists yet to diff against (E2) — this is distinct from a genuine zero-diff day, which reports
`new_listing_count: 0` with `status: "ok"`.
Composite/comparison/change entries are `unavailable` for a category whose composite coverage is
too thin (mirrors ADR-5's skipna-mean rule: a category with zero available sources for a date has
no composite point for that date, not a zero). `start > end` or malformed date → 422.

`GET /api/narrative/categories` is **not modified by this RFC** — no line of that response
changes shape, ordering, or content for a fixed input (proven by the contract snapshot test, ADR-4).

---

## 12. Infrastructure Deployment

Local only for the app. New scheduled workflow (repo-hosted, no user action beyond merge):
`.github/workflows/narrative-snapshot.yml`, GitHub Actions cron, same commit-back pattern as
`liqtide-snapshot.yml`.

## 12b. Storage Schema (Parquet files)

| Path | Columns | Write mode |
|---|---|---|
| existing `cache/narrative/{source}/{category}.parquet` | `date, raw_value, normalized_value, source_status` | unchanged (reused, no schema change) |
| `cache/narrative/exchange/{category}.parquet` (new) | `date, volume_share, new_listing_count, status` | append-only, forward-written |

---

## 13. Phased Delivery Plan

### Current Status

**Amended by UPDATE PROCESS, 24-09-26.** All 6 RFCs are code-complete, EVL-confirmed, and
committed/pushed to branch `claude/kind-tesla-tat3vo` (HEAD `7ef8eb3`, 58 files changed,
+5536/-4). Final gate counts: `pytest api/ -q` 392 passed / 3 deselected; `pnpm --filter web test`
110 passed (16 files); `tsc --noEmit` exit 0; `cd web && pnpm test:e2e` 26/26 passed, run twice
(14 new `narrative.spec.ts` + 6 `regime.spec.ts` + 6 `screener.spec.ts`). `git diff` on
`trigger.py`/`screener_board.py`/`NarrativeStrip.tsx`/`liqtide-snapshot.yml` is empty — AC-1
byte-compatibility and workflow isolation both hold.

Not yet done: two manual-first risk-pack review decisions are `PENDING`
(`harness/review-decision.json` for RFC-3's new public API surface,
`harness/rfc-004/review-decision.json` for RFC-4's new `contents: write` scheduled workflow), and
AC-3 (cron actually firing) / AC-12 (real-cache walkthrough) require the user's own machine — this
container's egress proxy blocks Google Trends, Reddit, CoinGecko and Hyperliquid with a 403/timeout
(same constraint as the regime dashboard's AC-11 precedent). The plan stays in `active/` until
those land — see the amended Resume and Execution Handoff below for the exact checklist.

Each RFC below carries: Summary, Dependencies, Stage 0, Stages, Post-Phase Testing, Verification
Checklist, Acceptance Criteria, What's Functional Now, Ready For, Implementation Checklist.

## 14. Features List (MoSCoW)

| ID | Feature | Priority |
|---|---|---|
| F-1 | Per-category growing history chart | Must |
| F-2 | Side-by-side comparison view | Must |
| F-3 | Change-in-attention view | Must |
| F-4 | Exchange volume/new-listing proxy, display-only | Must |
| F-5 | Widened coin-to-category map, honest "no mapping" state | Must |
| F-6 | Nightly forward-archive workflow | Must |
| F-7 | Visible data-quality caveat on every view | Must |
| F-8 | `/screener` and `/categories` byte-compatibility proof | Must |
| F-9 | pytrends historical backfill on day one | Should |
| F-10 | Soft-cap overflow list for many categories | Should |
| F-11 | Exchange proxy wired into `/categories` trigger pipeline | Won't (ADR-6) |
| F-12 | Backfilled real history for Reddit/CoinGecko/exchange | Won't |

---

## 15. RFCs

### RFC-1: Data foundation (category map JSON + history read/write)

**Summary**: widen the coin-to-category map into a curated, watchlist-sized JSON file; confirm the
existing `cache.py` narrative writer/reader needs no schema change.
**Dependencies**: none.

**Stage 0: Pre-Phase Research** (present and STOP)
- Read `watchlist.read_watchlist()`'s real content; propose the widened `narrative_categories.json`
  seed list and `narrative_category_map.json` map for every currently-watchlisted coin.
- **Hard gate (E1)**: if `read_watchlist()` returns an empty list, or `api/data/watchlist.json` is
  absent on the machine running this Stage 0, STOP immediately — do not treat the empty/absent
  result as "nothing to map." Ask the user directly for their current watchlist content, or defer
  this entire Stage 0 to a session on the user's own machine. Do not propose a widened map or
  category list from a fallback, default, or previously-seen watchlist.
- Confirm `read_narrative_series`/`write_narrative_point`'s exact signature and dedup behavior
  (does a repeated write for the same date overwrite or skip? — confirm before RFC-2's backfill
  logic depends on it).
- Surface **OQ-4** explicitly: which newly-mapped coins (beyond BTC/ETH/HYPE) would see their
  `/screener` `narrative_state` change, AND which seed categories (currently only `l2s`) would gain
  a member coin and could therefore see `GET /api/narrative/categories`' own
  `trending_count`/composite/triggered/confirmed/trust_weight shift on a day that coin appears in
  CoinGecko's live trending list — get explicit user sign-off on both before implementing.
- **Hard gate (E4)**: nothing beyond BTC/ETH/HYPE is written to `narrative_category_map.json` (or
  any newly-widened `narrative_categories.json` entries) until the user has explicitly approved the
  newly-mapped coin list, the resulting `/screener` `narrative_state` values shown for each, AND the
  list of seed categories (by id) that gain a member coin as a result. This is a hard execute-agent
  gate, not an optional courtesy.

**Stages**
1. `api/data/narrative_category_map.json` — new curated map, approved content from Stage 0.
2. `mapping.py::load_category_map()` — loads the JSON (same pattern as
   `trigger.load_seed_categories`); `map_coin_to_category` reads from it; unmapped still returns
   `None`.
3. `api/data/narrative_categories.json` — widened seed list (if Stage 0 approved new categories).
4. Contract snapshot test: `GET /api/narrative/categories`'s full response (all seed categories:
   ai/rwa/l2s/memecoins, not a BTC/ETH/HYPE-filtered subset) for fixed/mocked pytrends/reddit/
   CoinGecko-trending inputs, captured before this RFC and re-asserted byte-identical after —
   including at least one scenario where the mocked trending fixture contains a newly-mapped coin,
   to prove the assertion is meaningful (see ADR-7 Implications / OQ-4 correction).

**Post-Phase Testing**
- Test file: `api/tests/analytics/test_mapping.py` (extend) — widened map covers Stage 0's list;
  unmapped coin still `None`; JSON load failure degrades to empty map (not a crash).
- Test file: `api/tests/routers/test_narrative_categories_contract.py` (new) — byte-identical full
  response before/after, including a scenario where a newly-mapped coin appears in the mocked
  CoinGecko-trending fixture for the `l2s` seed category (or whichever seed category(s) gained a
  member at RFC-1 Stage 0), proving the test would catch `trending_count`/composite drift, not only
  a filtered BTC/ETH/HYPE comparison.
- Run: `uv run --project api pytest api/ -q`.
- Verification query:
  ```
  uv run --project api python -c "import duckdb; print(duckdb.sql(\"select * from 'api/data/cache/narrative/pytrends/ai.parquet'\"))"
  ```

**Verification Checklist**
- [ ] Manual test passed
- [ ] Data in storage verified (query output pasted)
- [ ] Error handling confirmed
- [ ] Watchlist read confirmed non-empty (or user supplied watchlist directly / Stage 0 deferred to
      user's own machine per E1 hard gate) — never proceeded on an empty/absent-watchlist result
- [ ] User confirmed the widened map, the resulting screener badges, AND the seed-category
      exposure list (OQ-4 sign-off, corrected scope) before implementation

**Acceptance Criteria**: AC-1, AC-8.
**What's Functional Now**: wider map, contract-proven unchanged `/categories` behavior.
**Ready For**: RFC-2.

**Implementation Checklist**
- [ ] E1 hard gate: watchlist confirmed non-empty/present before any proposal (STOP and ask user if
      empty or absent — never guessed)
- [ ] Stage 0 findings + OQ-4 presented; user approved
- [ ] E4 hard gate: explicit user sign-off on newly-mapped coins beyond BTC/ETH/HYPE received before
      `narrative_category_map.json` is written with any entry beyond BTC/ETH/HYPE
- [ ] `narrative_category_map.json` + `load_category_map()` + tests
- [ ] Contract snapshot test added and green — covers the full `/categories` response and the
      newly-mapped-coin-in-trending scenario (E5)
- [ ] Full `pytest` green

### RFC-2: Exchange adapter + pytrends historical backfill

**Summary**: `hyperliquid_narrative_adapter.py` + `exchange_attention.py` (ADR-6); a one-off
`backfill_pytrends_history.py` script (ADR-2).
**Dependencies**: RFC-1 (category map).

**Stage 0**: read `ccxt_adapter._exchange()` and its lock/singleton pattern; confirm
`fetch_tickers()`'s real return shape for Hyperliquid; settle the exact volume-share and
new-listing-diff formula; confirm Hyperliquid's terms permit this use (redistributable flag).
Confirm `pytrends.interest_over_time()`'s real column/index shape. Present and STOP.

**Stages**
1. `hyperliquid_narrative_adapter.py`: typed result, never raises, `status: ok | unavailable`,
   `redistributable` recorded.
2. `exchange_attention.py`: volume-share + new-listing diff (reads yesterday's snapshot from
   `cache/narrative/exchange/`, diffs against today's). Day-1/no-baseline case (E2): when no prior
   snapshot exists, return `new_listing_count=None` with `status="unavailable"`,
   `reason="no-baseline-yet"` — never `0`.
3. `backfill_pytrends_history.py`: fetch → per-date rows via `write_narrative_point(...,
   source_status="backfilled")`, skipping any date already forward-written.

**Post-Phase Testing**
- `api/tests/data/test_hyperliquid_narrative_adapter.py` — fixture parse, timeout → `unavailable`.
- `api/tests/analytics/test_exchange_attention.py` — golden volume-share values; new-listing diff
  on synthetic snapshots; unmapped new listing → explicit "unmapped" bucket, never dropped; **day-1
  case (E2)**: no prior snapshot present → `new_listing_count` is `None`/`status="unavailable"`/
  `reason="no-baseline-yet"`, never `0`, and is distinguishable from a genuine zero-diff day.
- `api/tests/scripts/test_backfill_pytrends_history.py` — synthetic payload → rows written;
  already-forward-written date is skipped, not overwritten.
- Opt-in: `uv run --project api pytest api/ -m integration -k hyperliquid`.
- Verify: DuckDB `select min(date), max(date), count(*) from 'api/data/cache/narrative/exchange/*.parquet'`.

**Verification Checklist**
- [ ] Manual test passed
- [ ] Data verified (query output pasted)
- [ ] Error handling confirmed (forced timeout → `unavailable`, never a silent zero share)
- [ ] User confirmed working

**Acceptance Criteria**: AC-4, AC-7.
**Ready For**: RFC-3.

### RFC-3: `GET /api/narrative/history` endpoint + comparison/change maths

**Summary**: `analytics/narrative/history.py` (ADR-5) + new router function/models (ADR-4).
**Dependencies**: RFC-1, RFC-2.

**Stage 0**: confirm the grid_dates/gap_before pattern against `api/analytics/regime/components.py`'s
implementation (reuse the shape, not the code — different package); settle the 7-day
change-in-attention window against Stage 0 review. Present and STOP.

**Stages**
1. `history.py`: composite, comparison, change-in-attention, grid assembly.
2. `api/models/narrative.py`: additive models per §11.
3. `routers/narrative.py::get_history` — additive route; `get_categories` untouched (grep-verified
   no shared code beyond `load_seed_categories`).
4. `start`/`end`/`categories` query filtering.

**Post-Phase Testing**
- `api/tests/analytics/test_history.py` — golden composite/rank/delta values on synthetic series;
  skipna-mean coverage rule; one source down → composite still computes over remaining sources;
  all sources down for a date → no composite point (not a zero).
- `api/tests/routers/test_narrative_history.py` — shape, filtering, one source `unavailable` →
  200 with that series flagged, other series unaffected; re-run of the RFC-1 contract snapshot
  test confirming `/categories` still byte-identical.
- Run: `uv run --project api pytest api/ -q`.
- Manual: `curl "http://127.0.0.1:8000/api/narrative/history" | python -m json.tool | head -80`.

**Verification Checklist**
- [ ] Manual test passed
- [ ] Data verified (counts/shape match RFC-2 coverage)
- [ ] Error handling confirmed
- [ ] User confirmed working
- [ ] **E3 risk-evidence-pack**: `GET /api/narrative/history` is a new public API surface
      (High-Risk Execution Handoff class per `process/development-protocols/orchestration.md`).
      Produce the manual-first `vc-risk-evidence-pack` artifacts (`risk-gate.json`,
      `context-snippets.json`, `verification.json`, `review-decision.json`) inside this task
      folder's `harness/` subdirectory before RFC-3 is treated as finalize-ready — this is a done
      criterion for RFC-3, not optional cleanup.

**Acceptance Criteria**: AC-2, AC-5, AC-6, AC-9, AC-10.
**Ready For**: RFC-4 and RFC-5 (parallel).

### RFC-4: Nightly forward-archive workflow

**Summary**: `.github/workflows/narrative-snapshot.yml` + `api/scripts/snapshot_narrative.py`
(ADR-3, ADR-8).
**Dependencies**: RFC-3. Can run in parallel with RFC-5.

**Stages**
1. `snapshot_narrative.py`: fetch all four sources for every tracked category, write via
   `write_narrative_point`; Reddit-unset path writes `unavailable`/`credentials-not-configured`
   cleanly (no crash, no skipped run).
2. `.github/workflows/narrative-snapshot.yml`: cron (a time offset from LiqTide's, e.g. `15 23 * * *`,
   confirmed at Stage 0 against provider rate-limit guidance), `workflow_dispatch`, commit-back
   pattern identical to `liqtide-snapshot.yml`.
3. `.gitignore`: add `!api/data/cache/narrative/` carve-out (same per-entry mechanic).
4. Ops Runbook entry: optional `REDDIT_CLIENT_ID`/`REDDIT_CLIENT_SECRET` GitHub Actions secrets.

**Post-Phase Testing**
- `api/tests/scripts/test_snapshot_narrative.py` — run twice same day, second run doesn't
  duplicate; Reddit-unset → clean `credentials-not-configured` rows, script still exits 0.
- Manual: run the script locally twice; trigger `workflow_dispatch` once (or dry-run equivalent).
- Verification query: DuckDB row counts per `cache/narrative/{source}/{category}.parquet` before/after.

**Verification Checklist**
- [ ] Manual test passed
- [ ] Data verified (query output pasted)
- [ ] Error handling confirmed (Reddit unset case)
- [ ] User confirmed working (workflow file reviewed, one run triggered)
- [ ] **E3 risk-evidence-pack**: `.github/workflows/narrative-snapshot.yml` is a new deploy/runtime
      surface (scheduled job with `contents: write` pushing to `main` — High-Risk Execution Handoff
      class). Produce the manual-first `vc-risk-evidence-pack` artifacts (`risk-gate.json`,
      `context-snippets.json`, `verification.json`, `review-decision.json`) inside this task
      folder's `harness/` subdirectory before RFC-4 is treated as finalize-ready — this is a done
      criterion for RFC-4, not optional cleanup.

**Acceptance Criteria**: AC-3.
**Ready For**: RFC-6 (after RFC-5 also lands).

### RFC-5: `/narrative` page

**Summary**: ADR-9 layout — independent history panels (soft-capped), comparison view,
change-in-attention view, caveat on every view.
**Dependencies**: RFC-3. Can run in parallel with RFC-4.

**Stage 0**: read `RegimeDashboard.tsx`/`ComponentPanel.tsx`/`DeadDataNotice.tsx` for the
fetch-once/typed-fetcher pattern; confirm `format-unavailable-reason.ts`'s extension point for
`credentials-not-configured`. Present and STOP.

**Stages**
1. `web/lib/types/narrative.ts`, `web/lib/api/narrative.ts`.
2. `CategoryHistoryPanel.tsx`, `ComparisonView.tsx`, `ChangeInAttentionView.tsx`,
   `DataQualityCaveat.tsx`.
3. `NarrativeDashboard.tsx` (soft cap + expandable overflow list).
4. `web/app/narrative/page.tsx`; link from `web/app/page.tsx`.
5. `format-unavailable-reason.ts`: add `credentials-not-configured` case and a `no-baseline-yet`
   case (E2 — exchange proxy's day-1 new-listing state, distinct plain-language copy from the
   generic "unavailable" text, e.g. "not enough history yet to detect new listings").

**Post-Phase Testing**
- vitest under `web/components/narrative/__tests__/`: one panel per tracked category up to the
  soft cap; overflow list renders remaining categories on demand; caveat present on all three
  views; injected fetcher error → `DeadDataNotice`; `credentials-not-configured` renders its own
  copy, not the generic "unavailable" text; **`no-baseline-yet` (E2) renders its own copy**, not a
  bare `0` and not the generic "unavailable" text, for the exchange proxy's day-1 new-listing state.
- Run: `pnpm --filter web test`.
- Manual: open `http://localhost:3000/narrative`; confirm caveat visible on every view; confirm
  `NarrativeStrip.tsx` on `/screener` renders unchanged.

**Verification Checklist**
- [ ] Manual test passed
- [ ] Data verified (spot-checked against curl)
- [ ] Error handling confirmed
- [ ] User confirmed working

**Acceptance Criteria**: AC-5, AC-6, AC-11.
**Ready For**: RFC-6 (after RFC-4 also lands).

### RFC-6: End-to-end proof + AC-12 handoff

**Summary**: prove the real frontend/backend boundary (Standing Lesson #8); hand AC-3/AC-12 to the
user.
**Dependencies**: RFC-4, RFC-5.

**Stages**: extend `seed_e2e_cache.py` with `build_narrative_fixture`/`seed_narrative` (multi-day
history per source/category, one seeded gap, Reddit unset, exchange snapshot pair for a new-listing
diff) written through the real `cache.write_*` functions → `web/e2e/narrative.spec.ts`.

**Post-Phase Testing**
- `cd web && pnpm test:e2e` — new spec: history panels render from a real request; comparison view
  ranks match a hand-computed expectation on the seeded fixture; change-in-attention view shows the
  seeded delta; Reddit source shows `credentials-not-configured` text; a seeded gap renders its
  reason. Existing screener/regime specs unaffected.
- Walkthrough checklist run by the user against the real cache (see Resume and Execution Handoff).

**Verification Checklist**
- [ ] E2E green
- [ ] Data verified against seeded cache
- [ ] Error handling confirmed
- [ ] User confirmed working (AC-3/AC-12 on their own machine)

**Acceptance Criteria**: AC-12 (E2E portion; AC-12's live-provider portion is user-run).
**What's Functional Now**: the narrative dashboard, end to end.

---

## 16. Rules (for this project)

- Python owns all numbers; the frontend formats but never computes.
- No interpolation or zero-fill; forward archive only, except pytrends' own backfill window.
- Every value carries its source and as-of; every gap carries a reason.
- Normalize within source; cross-source comparison compares normalized/derived values only.
- No change to `GET /api/narrative/categories`, `NarrativeStrip.tsx`, or the confidence badge.
- New adapters follow the typed-result, never-raise, cache-first pattern.

## 17. Verification (Comprehensive Review)

### Gap Analysis

- OQ-4 (widened map changes some coins' screener badges) is resolved by explicit user sign-off at
  RFC-1 Stage 0, not silently accepted — see Open Questions below.
- The exchange proxy's Hyperliquid terms must be confirmed at RFC-2 Stage 0 before any
  `redistributable=true` claim is finalized.
- The nightly workflow depends on GitHub Actions being enabled and unblocked for this repo — same
  dependency `liqtide-snapshot.yml` already has, not a new risk.
- Change-in-attention's 7-day window is a display-metric choice, not derived from any existing
  constant; revisit if the user wants a different window after seeing real data.

### Quality Assessment

| Dimension | Score | Reason |
|---|---|---|
| Fit to north-star | 9/10 | No calls, no overlays, confidence-only framing preserved |
| AC-1 safety | 9/10 | Separate router function/models, contract snapshot test, no shared assembly code |
| Data honesty | 9/10 | Every gap typed; exchange proxy explicitly labelled display-only |
| Risk | 7/10 | Two external unknowns (Hyperliquid terms, pytrends backfill shape) gated at Stage 0 |
| Testability | 8/10 | Golden values + real cache round-trip + E2E |

## 18. Change Management

Any scope change mid-flight: classify (New / Modify / Remove / Scope / Technical / Timeline), list
impacted RFCs and files, choose immediate / schedule / defer, update this plan's ADRs and Status
Strip, then continue. Most likely triggers: Hyperliquid terms disallow redistribution; OQ-4
resolution changes the map scope; pytrends' `interest_over_time()` shape differs from expectation.

## 19. Ops Runbook

- **Daily narrative snapshot**: automatic via `.github/workflows/narrative-snapshot.yml` — no user
  action once merged (mirrors the LiqTide workflow; no Windows Task Scheduler needed).
- **Optional Reddit history from day one**: add `REDDIT_CLIENT_ID`/`REDDIT_CLIENT_SECRET` as GitHub
  Actions repo secrets (Settings → Secrets and variables → Actions); without them the nightly job
  still runs cleanly, Reddit rows read `credentials-not-configured`.
- **Manual pytrends backfill**: `uv run --project api python api/scripts/backfill_pytrends_history.py`.
- **Check archive health**: DuckDB queries per §12b paths.
- **Start app**: API `uv run --project api uvicorn api.main:app --host 127.0.0.1 --port 8000`; web
  `pnpm --filter web dev`; open `http://localhost:3000/narrative`.

## 20. Acceptance Criteria (Versioned)

### V1.0

- **AC-1** `GET /api/narrative/categories` byte-identical; `/screener` narrative strip/confidence
  badge unaffected.
- **AC-2** `/narrative` renders a real, growing per-category history chart from archived points.
- **AC-3** Nightly scheduled job archives one point per (source, category) per day.
- **AC-4** pytrends' own historical window seeds its chart on day one.
- **AC-5** Sectors comparable side by side at once.
- **AC-6** Change-in-attention view distinct from a level ranking.
- **AC-7** Exchange proxy exists, fails safely, explicit `unavailable` on fetch failure.
- **AC-8** Coin-to-category map covers more of the watchlist; unmapped coin shows explicit state.
- **AC-9** One source's failure never takes down the rest of the dashboard.
- **AC-10** No raw cross-source level comparison anywhere.
- **AC-11** Visible data-quality caveat on every dashboard view.
- **AC-12** Real-cache user walkthrough confirms all of the above against live data.

## 21. Future Work

- Widen the exchange proxy to a second exchange for cross-checking, if Hyperliquid coverage proves
  thin for some tracked categories.
- Revisit whether the exchange proxy should ever become a 4th trigger source, behind a new,
  explicitly-versioned `/categories` contract (would require its own SPEC).
- Auto-flagged emerging categories beyond the curated seed list (mentioned in SPEC flow diagram,
  not scoped by any AC here — needs its own SPEC if pursued).

---

## Touchpoints

| Area | Files | Change |
|---|---|---|
| API data | `api/data/narrative_category_map.json` | new |
| API data | `api/data/narrative_categories.json` | widened (additive entries, Stage 0 approved) |
| API data | `api/data/hyperliquid_narrative_adapter.py` | new |
| API analytics | `api/analytics/narrative/mapping.py` | modify: load JSON instead of hard-coded dict |
| API analytics | `api/analytics/narrative/history.py`, `api/analytics/narrative/exchange_attention.py` | new |
| API models/router | `api/models/narrative.py` (additive), `api/routers/narrative.py` (additive `get_history`) | |
| API scripts | `api/scripts/backfill_pytrends_history.py` (new), `api/scripts/snapshot_narrative.py` (new), `api/scripts/seed_e2e_cache.py` (extend) | |
| API tests | `api/tests/analytics/{test_mapping.py (extend), test_history.py, test_exchange_attention.py}`, `api/tests/data/test_hyperliquid_narrative_adapter.py`, `api/tests/routers/{test_narrative_categories_contract.py, test_narrative_history.py}`, `api/tests/scripts/{test_backfill_pytrends_history.py, test_snapshot_narrative.py}` | new |
| Workflow | `.github/workflows/narrative-snapshot.yml` | new |
| Config | `.gitignore` | add `!api/data/cache/narrative/` carve-out |
| Web | `web/lib/types/narrative.ts`, `web/lib/api/narrative.ts`, `web/components/narrative/*`, `web/app/narrative/page.tsx`, `web/app/page.tsx` (link), `web/lib/format-unavailable-reason.ts` (add `credentials-not-configured`) | new + small additive edits |
| Web tests | `web/components/narrative/__tests__/*`, `web/e2e/narrative.spec.ts` | new |
| Cache | `api/data/cache/narrative/exchange/`, existing `cache/narrative/{source}/` (reused, no schema change) | new data path |
| Context | `process/features/narrative-mindshare/_GUIDE.md`, `process/context/all-context.md`, `data-sources/all-data-sources.md` | UPDATE PROCESS after EXECUTE |

Read-only: `api/analytics/narrative/scoring.py`, `api/analytics/narrative/trigger.py` (its
`compute_trigger`/`assemble_narrative_categories` functions are called, never modified),
`api/data/{pytrends,reddit,coingecko}_adapter.py`, `api/data/ccxt_adapter.py` (`_exchange()` called,
not modified), `web/components/screener/NarrativeStrip.tsx`, `api/main.py` (GZipMiddleware already
global — no change needed).

## Public Contracts

- **New**: `GET /api/narrative/history` (§11 shape, including the exchange-proxy series'
  `new_listing_count: int | null` field — `null`/`status="unavailable"`/`reason="no-baseline-yet"`
  on day one, never `0`, per E2); `NarrativeHistoryResult` Python dataclass;
  `hyperliquid_narrative_adapter.fetch_daily_market_snapshot()` typed result;
  `mapping.load_category_map()`.
- **Extended, backward-compatible**: `api/data/narrative_categories.json` gains entries (additive);
  `cache.write_narrative_point` callers gain a new caller (`backfill_pytrends_history.py`,
  `snapshot_narrative.py`) — signature unchanged.
- **Must stay byte-identical**: `GET /api/narrative/categories`, `NarrativeCategory` model,
  `trigger.compute_trigger`, `trigger.assemble_narrative_categories`, `scoring.normalize_within_source`,
  `mapping.map_coin_to_category`'s return contract (curated lookup or `None`), `NarrativeStrip.tsx`,
  the confidence-badge weighting in `screener_board.py`.

## Blast Radius

- ~18 new files, 5 modified files (JSON widen, `mapping.py` load-source swap, `.gitignore`,
  `format-unavailable-reason.ts`, `web/app/page.tsx` link) across `api/` and `web/`.
- Risk class: **low-medium**. Low for `/screener`/`/categories` (proven via contract snapshot test,
  never touched by shared code); medium for the new external dependency (Hyperliquid `fetch_tickers`
  volume/listing semantics) and the coin-map widening's screener-badge side effect (OQ-4, gated on
  explicit user sign-off at RFC-1 Stage 0).
- Regression guard: full `pytest` and `vitest` suites plus the existing Playwright screener and
  regime specs run at RFC-3, RFC-5 and RFC-6; the contract snapshot test re-run at RFC-1 and RFC-3.

## Verification Evidence

| Gate / Scenario | Strategy | Proves SPEC criterion |
|---|---|---|
| Contract snapshot: `/categories` byte-identical for BTC/ETH/HYPE (`test_narrative_categories_contract.py`) | Fully-Automated | AC-1 |
| History accumulation via real cache round-trip (`test_history.py`, reused `narrative_series_path`) | Fully-Automated | AC-2 |
| Nightly workflow dry-run + no-duplicate-on-rerun (`test_snapshot_narrative.py`) | Hybrid | AC-3 |
| Workflow actually firing on schedule | Agent-Probe (user checks archive after nightly runs) | AC-3 |
| pytrends backfill golden rows + forward-write-wins dedup (`test_backfill_pytrends_history.py`) | Fully-Automated | AC-4 |
| Comparison view ranking on seeded fixture | Agent-Probe | AC-5 |
| Change-in-attention view on seeded fixture | Agent-Probe | AC-6 |
| Exchange adapter fixture failure → explicit `unavailable` (`test_hyperliquid_narrative_adapter.py`, `test_exchange_attention.py`) | Fully-Automated | AC-7 |
| Widened map coverage + explicit unmapped state (`test_mapping.py`) | Fully-Automated | AC-8 |
| One source down → other sources/rest of dashboard unaffected (`test_narrative_history.py`) | Fully-Automated | AC-9 |
| Within-source normalisation boundary asserted (`test_history.py`, `test_exchange_attention.py`) | Fully-Automated | AC-10 |
| Caveat rendered on all three views (vitest `__tests__/*`) | Agent-Probe | AC-11 |
| `web/e2e/narrative.spec.ts` on seeded cache | Fully-Automated | AC-12 (E2E portion) |
| User walkthrough on real machine | Agent-Probe (user) | AC-12 (live-provider portion) |

Commands and runners per `process/context/tests/all-tests.md`:
`uv run --project api pytest api/ -q` · `pnpm --filter web test` · `cd web && pnpm test:e2e`.

## Test Infra Improvement Notes

(none identified yet)

## Resume and Execution Handoff

**Amended by UPDATE PROCESS, 24-09-26 — supersedes the paragraph below, kept for history.**

1. **Selected plan file**: `process/features/narrative-mindshare/active/narrative-dashboard_24-09-26/narrative-dashboard_PLAN_24-09-26.md`
2. **Last completed phase or step**: all 6 RFCs implemented and EVL-confirmed 24-09-26; committed
   and pushed (branch `claude/kind-tesla-tat3vo`, HEAD `7ef8eb3`). Plan/SPEC/context reconciliation
   done this UPDATE PROCESS pass; plan stays in `active/` pending the user-PC steps below.
3. **Validate-contract status**: PASS (unchanged — `## Validate Contract` below, PVL cycle 1
   re-validate, 24-09-26). No re-validate was needed during EXECUTE.
4. **Supporting context files loaded this pass**: `process/context/all-context.md`,
   `process/context/data-sources/all-data-sources.md`, `process/context/tests/all-tests.md`,
   `process/features/narrative-mindshare/_GUIDE.md`, this SPEC, all 6
   `narrative-dashboard_RFC-00N_REPORT_24-09-26.md` files, the two `*-stage0_REPORT_*.md` files that
   have one, `narrative-dashboard-pvl-iteration-001_REPORT_24-09-26.md`,
   `narrative-dashboard-evl-iteration-001_REPORT_24-09-26.md`, and `results.tsv`.
5. **Next step for a fresh agent (user-PC checklist, exact commands from the RFC-6 report)**:
   1. Merge/push the branch to `main`; confirm GitHub Settings → Actions → General has Actions
      enabled and Workflow permissions = Read and write.
   2. **AC-3**: `gh workflow run narrative-snapshot.yml --ref main` then `gh run watch` (or the
      Actions tab → "narrative-snapshot" → Run workflow). Expect exit 0 (or exit 2 with a warning)
      and a bot commit touching only `api/data/cache/narrative/`. The next day after 23:00 UTC,
      confirm a second bot commit, then `git pull` and
      `uv run --project api python -m api.scripts.snapshot_narrative --verify-only`.
   3. Local sanity: `uv run --project api --with pytrends python -m api.scripts.snapshot_narrative --dry-run`,
      then the same command without `--dry-run` run twice (second run skips everything), then
      `--verify-only`.
   4. Hyperliquid integration test: `uv run --project api pytest api/tests/data/test_hyperliquid_narrative_adapter.py -m integration -q`.
   5. **AC-4 pytrends backfill**: `uv run --project api --with pytrends python api/scripts/backfill_pytrends_history.py --dry-run`,
      review, then run again without `--dry-run`.
   6. **Hyperliquid terms check**: read Hyperliquid's ToU/API docs on redistributing market data. If
      they allow it, set `HYPERLIQUID_REDISTRIBUTABLE = True` in `api/data/hyperliquid_narrative_adapter.py`
      and re-run `uv run --project api pytest api/ -q`; otherwise leave it `False`.
   7. **AC-12 real-cache walkthrough**: `uv run --project api uvicorn api.main:app --host 127.0.0.1 --port 8000`
      and `pnpm --filter web dev`; open `http://localhost:3000/narrative` and confirm the caveat on
      every view, growing per-category charts, dashed backfill lines with orange mixed-scale dots,
      comparison/change tables with "—" + reason where missing, Reddit showing "no archived data"
      (unless secrets + the workflow `env:` edit are added), Hyperliquid volume/new-listing text, and
      the personal-use badges; then open `http://localhost:3000/screener` and confirm the narrative
      strip is unchanged.
   8. **Two review decisions** (manual-first risk packs — set `"decision"` to `approved`,
      `approved-with-concerns`, or `rejected`, with rationale + timestamp):
      `harness/review-decision.json` (RFC-3, `/history` public API) and
      `harness/rfc-004/review-decision.json` (RFC-4 workflow: `contents: write`, pushes to `main`,
      no secrets). Both are `PENDING` with `mustStopBeforeFinalize: true`.
   9. Optional: Reddit history from day one needs BOTH the `REDDIT_CLIENT_ID`/`REDDIT_CLIENT_SECRET`
      repo secrets AND a two-line `env:` mapping added to `narrative-snapshot.yml` — the workflow
      deliberately maps no secrets today, so adding the secrets alone does nothing (RFC-4 finding).
   Once all of the above are done, re-enter UPDATE PROCESS to archive this plan to `completed/`.

**Open Questions carried from SPEC, plus one new question raised during PLAN:**
- **OQ-1** (category/coin-map scope) — resolved procedurally: RFC-1 Stage 0 reads the real
  watchlist and proposes the concrete list; not resolved with placeholder values in this plan
  because the real watchlist content is dynamic data this PLAN session should not guess at.
- **OQ-2** (exchange choice/formula) — narrowed by the Decision Summary to Hyperliquid via the
  existing `ccxt_adapter` singleton (ADR-6); the exact volume-share/new-listing formula is finalized
  at RFC-2 Stage 0.
- **OQ-3** (Reddit nightly credentials) — resolved (ADR-8): no secret required to ship; optional
  secret documented in the Ops Runbook.
- **OQ-4 (new, raised during PLAN; scope corrected at PVL cycle 1 re-validate, 24-09-26)** —
  widening `COIN_CATEGORY_MAP` (via ADR-7) will change `screener_board.py`'s `narrative_state`
  output for any newly-mapped coin beyond BTC/ETH/HYPE (which AC-1 protects explicitly). This is a
  real, intended side effect of US-5/AC-8, but it is not only a `/screener` display change: any
  newly-mapped coin whose category already has (or gains) a seed-category presence — today only
  `l2s`, via `ETH`/`HYPE` — can also shift that category's `trending_count`/composite/
  triggered/confirmed/trust_weight inside `GET /api/narrative/categories`' own response on any day
  the coin appears in CoinGecko's live trending list (`trigger.py::compute_narrative_categories`
  calls `mapping.map_coin_to_category` directly; see ADR-7 Implications). **Do not silently
  proceed** — RFC-1 Stage 0 must present the exact list of newly-mapped coins, their resulting
  screener narrative badges, AND which seed categories (by id) gain a member coin, for explicit
  user approval before implementation, separate from (but alongside) the category-list approval.
  The contract snapshot test (RFC-1 Stage 1.4) must assert the full `/categories` response
  (all seed categories, not a BTC/ETH/HYPE-filtered subset) is byte-identical under a fixed/mocked
  CoinGecko-trending fixture, and must include at least one scenario where a newly-mapped coin is
  present in that fixture, to prove the test would actually catch this drift rather than passing
  vacuously on a fixture that happens to omit the newly-mapped coins.

Reports for each RFC go in this same task folder as
`narrative-dashboard_RFC-00N_REPORT_24-09-26.md` (the actual naming used; corrects the
`narrative-dashboard_24-09-26-RFC-N-phase-report.md` form written above during PLAN).

## Validate Contract

Status: PASS
Date: 24-09-26
date: 2026-09-24
generated-by: outer-pvl
supersedes: 2026-09-24 (outer-pvl) — PVL cycle 1 re-validate has current evidence

Parallel strategy: sequential
Rationale: 6 RFCs with a mostly-linear dependency chain (RFC-4/RFC-5 are the only parallel pair,
both gated behind RFC-3), one feature folder, no independent cross-package workstreams that need
mid-run coordination — dominant signal is sequential dependency, same shape as the regime
dashboard's own validate-contract, which this plan is structurally modelled on.

Test gates (C3 5-column table):

| criterion id | behavior | strategy | proving test | gap-resolution |
|---|---|---|---|---|
| AC-1 | `GET /api/narrative/categories` byte-identical, full response, incl. a newly-mapped-coin-in-trending scenario (E5) | Fully-Automated | `api/tests/routers/test_narrative_categories_contract.py` | B |
| AC-1 | `/screener` narrative strip/confidence badge unaffected | Hybrid | `pnpm --filter web test` (`NarrativeStrip.test.tsx`, `ConfidenceBadge.test.tsx`, both pre-existing, re-run unmodified) | B |
| AC-2 | history chart built from archived points, not a single reading | Fully-Automated | `api/tests/analytics/test_history.py` (real cache round-trip) | B |
| AC-3 | nightly workflow dry-run, no duplicate on same-day re-run, Reddit-unset path clean | Hybrid | `api/tests/scripts/test_snapshot_narrative.py` | B |
| AC-3 | scheduled trigger actually fires on `narrative-snapshot.yml`'s cron | Agent-Probe | user checks archive after nightly runs (mirrors LiqTide AC-3 precedent; plan gate, structurally user/machine-only) | A |
| AC-4 | pytrends `interest_over_time()` backfill, golden rows, forward-write-wins dedup | Fully-Automated | `api/tests/scripts/test_backfill_pytrends_history.py` | B |
| AC-5 | comparison view ranking on seeded fixture | Agent-Probe | vitest component probe + manual walkthrough | B |
| AC-6 | change-in-attention view distinct from a level ranking | Agent-Probe | vitest component probe + manual walkthrough | B |
| AC-7 | exchange proxy fails safely, explicit `unavailable` on fetch failure | Fully-Automated | `api/tests/data/test_hyperliquid_narrative_adapter.py`, `api/tests/analytics/test_exchange_attention.py` | B |
| AC-8 | widened map coverage; unmapped coin still `None` | Fully-Automated | `api/tests/analytics/test_mapping.py` (extend) | B |
| AC-9 | one source down never takes down the rest of the dashboard | Fully-Automated | `api/tests/routers/test_narrative_history.py` | B |
| AC-10 | no raw cross-source level comparison; within-source normalisation boundary asserted | Fully-Automated | `api/tests/analytics/test_history.py`, `test_exchange_attention.py` | B |
| AC-11 | data-quality caveat visible on every dashboard view | Agent-Probe | vitest `__tests__/*` + manual walkthrough | B |
| AC-12 | real frontend/backend boundary proof on seeded fixture | Fully-Automated | `cd web && pnpm test:e2e` (`web/e2e/narrative.spec.ts`) | B |
| AC-12 | real-cache user walkthrough against live providers | Agent-Probe | user, own machine (egress proxy blocks providers here — same as regime dashboard AC-11 precedent; plan gate, structurally user/machine-only) | A |

C-4 reconciliation: `strategy` values above are Fully-Automated / Hybrid / Agent-Probe only;
Known-Gap is not used as a strategy anywhere in this table — every behavior above has a proving
gate (gap-resolution B = fixed by this plan's own checklist; A = proven directly, Agent-Probe rows
are proven by the user, not deferred).

Failing stubs (Fully-Automated rows; replace during EXECUTE):

```python
def test_narrative_categories_contract_byte_identical(): raise NotImplementedError("TDD stub: GET /api/narrative/categories byte-identical, full response, before/after")
def test_narrative_categories_contract_newly_mapped_coin_in_trending(): raise NotImplementedError("TDD stub (E5): mocked CoinGecko-trending fixture contains a newly-mapped l2s coin -> proves the contract test would catch trending_count/composite drift, not just a BTC/ETH/HYPE-filtered comparison")
def test_history_accumulates_from_real_cache_round_trip(): raise NotImplementedError("TDD stub: history chart built from archived points via real cache.write_narrative_point/read_narrative_series round trip")
def test_pytrends_backfill_golden_rows_and_forward_write_wins(): raise NotImplementedError("TDD stub: pytrends backfill golden rows; a date already forward-written is skipped, never overwritten")
def test_hyperliquid_adapter_timeout_returns_unavailable(): raise NotImplementedError("TDD stub: hyperliquid_narrative_adapter fetch failure -> explicit unavailable, never a silent zero")
def test_exchange_attention_volume_share_and_new_listing_diff(): raise NotImplementedError("TDD stub: golden volume-share values; new-listing diff on synthetic snapshots; unmapped listing -> explicit unmapped bucket")
def test_mapping_widened_coverage_and_unmapped_none(): raise NotImplementedError("TDD stub: widened category map covers Stage 0 list; unmapped coin still returns None")
def test_narrative_history_one_source_down_isolates_failure(): raise NotImplementedError("TDD stub: one source unavailable -> 200 with that series flagged, other series/composite unaffected")
```

```ts
test("should render a caveat on every narrative dashboard view", () => { throw new Error("NOT IMPLEMENTED — TDD stub: data-quality caveat visible on history/comparison/change-in-attention views") });
test("should show the real narrative frontend/backend boundary on a seeded fixture", () => { throw new Error("NOT IMPLEMENTED — TDD stub: web/e2e/narrative.spec.ts real request/response round trip") });
```

Legacy line form:
- Contract snapshot: Fully-automated: `uv run --project api pytest api/tests/routers/test_narrative_categories_contract.py -q`
- History/composite maths: Fully-automated: `uv run --project api pytest api/tests/analytics/test_history.py -q`
- Exchange proxy: Fully-automated: `uv run --project api pytest api/tests/data/test_hyperliquid_narrative_adapter.py api/tests/analytics/test_exchange_attention.py -q`
- Nightly workflow: hybrid: `uv run --project api pytest api/tests/scripts/test_snapshot_narrative.py -q` | agent-probe: archive check after nightly runs
- Backfill: Fully-automated: `uv run --project api pytest api/tests/scripts/test_backfill_pytrends_history.py -q`
- Full backend suite: Fully-automated: `uv run --project api pytest api/ -q`
- Frontend: Fully-automated: `pnpm --filter web test` | Fully-automated: `cd web && pnpm test:e2e` | agent-probe: user walkthrough

Plan updates applied (this re-validate pass, PVL cycle 1 re-validate, 24-09-26):

| # | What changed | Where in plan | Why |
|---|---|---|---|
| P1 | ADR-7 Implications: added VALIDATE correction that `trigger.py::compute_narrative_categories` (which backs `GET /api/narrative/categories`) calls `mapping.map_coin_to_category` inside its CoinGecko trending-count loop — the map is not only reached via `screener_board.py` | ADR-7 | Direct code read of `trigger.py` line 194 (`compute_narrative_categories`) shows this call; the prior pass's "mapping.py is never reached by /categories" claim (see below) was factually wrong |
| P2 | OQ-4: widened scope to cover `/categories`' own seed-category exposure (today only `l2s`, via ETH/HYPE), not only `/screener`'s `narrative_state`; requires the contract snapshot test to include a newly-mapped-coin-in-trending scenario | Open Questions — OQ-4 | Same root cause as P1 — OQ-4 as originally scoped only asked about screener badges, missing the `/categories` exposure path |
| P3 | RFC-1 Stage 0: OQ-4 sign-off bullet now also asks which seed categories gain a member coin | RFC-1 Stage 0 | Makes the Stage-0 approval step concretely cover the corrected OQ-4 scope |
| P4 | RFC-1 E4 hard gate: sign-off now also covers the seed-category exposure list, not only screener badges | RFC-1 Stage 0, E4 hard gate | Keeps E4 (already a hard execute-agent gate) as the single mechanism closing this finding — no new gate invented |
| P5 | RFC-1 Stage 1.4: contract snapshot test spec now requires the full `/categories` response (all 4 seed categories) under a fixed/mocked trending fixture, plus a newly-mapped-coin-in-trending scenario, instead of a BTC/ETH/HYPE-filtered comparison | RFC-1 Stages | A BTC/ETH/HYPE-filtered assertion cannot detect `l2s` composite drift from a newly-mapped, non-BTC/ETH/HYPE coin |
| P6 | RFC-1 Post-Phase Testing: test-file description updated to match P5 | RFC-1 Post-Phase Testing | Keeps the test-file description and the Stage description in sync |
| P7 | RFC-1 Implementation Checklist: contract-snapshot checklist item now references the E5 scenario explicitly | RFC-1 Implementation Checklist | Makes the new requirement checkable at EXECUTE time |
| P8 | RFC-1 Verification Checklist: OQ-4 sign-off checklist item now names the seed-category exposure list explicitly | RFC-1 Verification Checklist | Same as P7, for the Verification Checklist copy of the sign-off gate |

Prior-pass plan update for reference (already applied, unchanged this cycle): ADR-2's dedup-wording
correction (`write_narrative_point`'s own dedup provides no source-priority guarantee; the
forward-wins rule is enforced entirely by the backfill script's own read-before-write skip check).

Dimension findings:
- Infra fit: PASS — no container/infra/proxy surface touched; `GET /api/narrative/history` inherits the existing global `GZipMiddleware` for free (confirmed in `api/main.py`); the new nightly workflow mirrors `.github/workflows/liqtide-snapshot.yml`'s checkout/setup-uv/run/commit shape exactly, including `permissions: contents: write` — no new infra pattern introduced.
- Test coverage: PASS — E1 (watchlist gap) and E2 (new-listing day-1 state) from the first-pass CONDITIONAL are now folded into RFC-1/RFC-2/RFC-5 as concrete, testable requirements (hard gates, pytest cases, vitest cases, frontend copy) — verified present in this re-validate. E5 (this pass's new finding, see Plan updates applied) is likewise folded in as a concrete test requirement, not left open. AC-3/AC-12's live-provider portions remain structurally Agent-Probe in this sandbox (egress proxy blocks Google Trends/Reddit/CoinGecko/Hyperliquid, confirmed by the regime dashboard's identical AC-11 precedent) and AC-3's cron-firing portion is likewise Agent-Probe/user-only — both are declared plan gates in the plan's own Verification Evidence table, not validate concerns, and do not block PASS.
- Breaking changes: PASS (corrected this pass) — the first-pass claim that "the `/categories` code path never calls `mapping.py` at all" is factually wrong: `trigger.py::compute_narrative_categories` (which directly backs `GET /api/narrative/categories`) calls `mapping.map_coin_to_category(symbol)` inside its CoinGecko trending-count loop, and that count feeds `compute_trigger`'s composite for the matching seed category. Confirmed by direct read of `trigger.py` lines 27, 192-196 and `mapping.py`'s current 3-entry map (`BTC`→`store-of-value` — not a seed category, so BTC never reaches `/categories`; `ETH`/`HYPE`→`l2s`, which IS a seed category). This is now corrected in ADR-7/OQ-4/RFC-1 (P1-P8 above): OQ-4's sign-off scope and the contract snapshot test both now explicitly cover this exposure, closing the gap as a concrete plan requirement (gap-resolution B) rather than leaving it as an unstated assumption. `map_coin_to_category`'s own contract (curated lookup or `None`) is still unchanged by the JSON swap — only the *set of coins it recognizes* grows, which is exactly what ADR-7/AC-8 intend.
- Security surface: PASS — no new secret required to ship (Hyperliquid via keyless `ccxt_adapter._exchange()`; Reddit's two existing optional secrets unchanged); local bind (`127.0.0.1`) and CORS scope unchanged; new nightly workflow's `contents: write` permission mirrors the already-running `liqtide-snapshot.yml` exactly, not a new permission pattern.
- RFC-1 feasibility: PASS — mechanically feasible (`api/tests/analytics/test_mapping.py` already exists to extend; `map_coin_to_category`'s contract is unchanged by the JSON swap). `api/data/watchlist.json` remains absent in this sandbox (gitignored, personal data) — this is E1's own scenario, already a hard Stage-0 gate (stop and ask the user / defer to the user's machine), not a validate concern; confirmed the gate text is concrete and unconditional (no fallback-to-default path exists in the RFC-1 text). The new E5 requirement (contract snapshot test covers the full response + a newly-mapped-coin-in-trending scenario) is folded into RFC-1 Stages/Post-Phase Testing/Implementation Checklist this pass.
- RFC-2 feasibility: PASS — Hyperliquid `fetch_tickers()` volume-share approach re-confirmed this pass by reading the installed `ccxt` 4.5.78 package directly (`ccxt.hyperliquid().has['fetchTickers'] is True`; `parse_ticker` maps `dayNtlVlm` -> unified `quoteVolume`, confirmed by grepping the installed source): `'quoteVolume': self.safe_number(ticker, 'dayNtlVlm')`. RFC-2 Stage 0 can treat this as settled; only the redistribution/ToS confirmation remains genuinely open there (expected Stage-0 scope, not a validate concern). E2's day-1 no-baseline state is present in ADR-6, API Surface, Public Contracts, RFC-2 Stages/Post-Phase Testing, RFC-5 Stages/Post-Phase Testing — verified concrete and testable across the full stack (backend typed result, pytest, contract doc, frontend copy, vitest) this pass.
- RFC-3 feasibility: PASS — `grid_dates`/`gap_before`/`max_gap_days` pattern is proven end-to-end on `/regime` already (`api/analytics/regime/components.py`, `components_response.py`); reusing the shape (not the code, per the RFC's own Stage 0 framing) is mechanically straightforward; `get_history` sharing only `load_seed_categories` with `get_categories` is grep-verifiable once written. E3 risk-evidence-pack done-criterion present and concrete (harness/ artifact list named).
- RFC-4 feasibility: PASS — `.gitignore`'s existing `api/data/cache/*` + `!api/data/cache/liqtide/` carve-out mechanic (confirmed by reading `.gitignore` directly, including its own inline comment explaining "parent must be excluded per-entry") extends cleanly to `!api/data/cache/narrative/`; nested `cache/narrative/exchange/` needs no separate negation, mirroring how `liqtide/`'s contents are already included with only the one parent-level negation line. Workflow file mechanically mirrors `liqtide-snapshot.yml` line for line. E3 risk-evidence-pack done-criterion present and concrete.
- RFC-5 feasibility: PASS — `RegimeDashboard.tsx`/`DeadDataNotice.tsx`/`format-unavailable-reason.ts` fetch-once and degraded-state patterns are proven and directly reusable; `format-unavailable-reason.ts`'s `switch` statement is a clean, low-risk extension point for both the new `credentials-not-configured` case and E2's `no-baseline-yet` case (mechanically confirmed by reading the file: two new `case` arms, both already named in RFC-5 Stage 5).
- RFC-6 feasibility: PASS — `seed_e2e_cache.py`'s `_guard()` (refuses to run without an explicit, non-default `SCREENER_CACHE_ROOT`) and its `SCREENER_WATCHLIST_PATH` `{"coins": [...]}` shape (confirmed against `watchlist.py::_load_raw`'s actual parsing contract, directly addressing Standing Lesson #7) are real, reusable safety mechanisms — `build_narrative_fixture`/`seed_narrative` can follow the exact same shape.

Execute-agent instructions:
- E1: RFC-1 Stage 0 — if `api/data/watchlist.json` is absent on the machine running Stage 0 (confirmed absent in this VALIDATE sandbox; it is gitignored, personal data), do not silently treat `read_watchlist()`'s resulting empty list as "nothing to map." Stop and ask the user directly for their current watchlist content (or defer Stage 0 to a session on the user's own machine) before proposing the widened category/map list.
- E2: RFC-2 `exchange_attention.py`'s new-listing diff has no prior day's market-list snapshot on its first run. Implement an explicit "no baseline yet" state for day one (e.g. `new_listing_count: null` with a distinct status/reason), never a bare `0` — a real zero-diff and "nothing to compare against yet" are different facts and the project's "numbers are never silently wrong" rule applies here exactly as it does to the three existing sources.
- E3: this plan adds a new public API surface (`GET /api/narrative/history`) and a new deploy/runtime surface (`.github/workflows/narrative-snapshot.yml`, scheduled job with `contents: write` pushing to `main`) — both are High-Risk Execution Handoff classes (`process/development-protocols/orchestration.md`). Produce the manual-first evidence pack (`vc-risk-evidence-pack`: `risk-gate.json`, `context-snippets.json`, `verification.json`, `review-decision.json`) inside this task folder's `harness/` subdirectory before treating RFC-3/RFC-4 as finalize-ready. Auto-stop rule applies — do not report those RFCs DONE with the work implied fully proven until the pack exists.
- E4: RFC-1 Stage 0's OQ-4 sign-off — which newly-mapped coins would see their `/screener` `narrative_state` change, AND which seed categories (by id) gain a member coin and could shift `GET /api/narrative/categories`' own `trending_count`/composite/triggered/confirmed/trust_weight — must be presented and explicitly approved by the user before any map file beyond BTC/ETH/HYPE is written. This was already a plan requirement (screener-badge scope only); this pass widens it to also cover the `/categories` exposure path found in E5/P1-P4. It remains a hard execute-agent gate, not an optional courtesy.
- E5 (new this pass): the RFC-1 contract snapshot test (`api/tests/routers/test_narrative_categories_contract.py`) must assert the FULL `GET /api/narrative/categories` response (all 4 seed categories: ai/rwa/l2s/memecoins) is byte-identical before/after, under a fixed/mocked pytrends/reddit/CoinGecko-trending fixture — not a response filtered down to BTC/ETH/HYPE-named fields, since those are coin symbols, not category ids, and the endpoint's response is category-shaped. The test MUST include at least one case where the mocked CoinGecko-trending fixture contains a coin newly added to `narrative_category_map.json` for a seed category that already has (or gains) a member — today only `l2s`, via ETH/HYPE — and assert what the response does in that case, so the test provably would catch `trending_count`/composite drift rather than passing vacuously on a fixture that happens to omit the newly-mapped coins.

Open gaps: none carried to backlog — all findings from this pass and the prior pass are either
mechanically resolved during a VALIDATE pass (RFC-2 ccxt feasibility, ADR-2 wording, this pass's
E5/mapping.py finding), folded into the plan as execute-agent instructions (E1-E5), or already
correctly scoped as Agent-Probe/user-only plan gates in the plan's own Verification Evidence table
(AC-3's cron-firing portion, AC-12's live-provider portion).

What this coverage does NOT prove:
- Contract snapshot test: not that `screener_board.py`'s per-coin `narrative_state` is unaffected by the widened map for newly-mapped coins beyond BTC/ETH/HYPE — that change is intended (OQ-4) and gated on explicit user sign-off, not proven "unchanged" by this gate. Also not that a newly-mapped coin's category will NEVER shift `/categories`' own output going forward — only that the specific fixture scenarios exercised at RFC-1 (including the E5 newly-mapped-coin-in-trending case) behave as specified; a real, live CoinGecko trending list on any future day can still include a different newly-mapped coin than the one tested, which is exactly why OQ-4's sign-off (not just this test) is the actual control on whether widening into an already-seeded category is acceptable.
- History/composite tests: not that the composite/rank/delta maths matches any external ground truth — narrative attention has no authoritative source to check against; only internal consistency (skipna-mean coverage rule, normalisation boundary) is proven.
- Nightly workflow hybrid test: not that GitHub Actions cron actually fires on schedule in production, and not that Reddit secrets (if the user later adds them) work end-to-end — only the unset-credentials path and no-duplicate-on-rerun behavior are proven.
- Backfill test: not that `pytrends.interest_over_time()` still works at all (it is unofficial/archived since April 2025, per `pytrends_adapter.py`'s own module docstring) — only that IF it returns data, the rows are written correctly and forward-written dates are skipped.
- Hyperliquid adapter/exchange-attention tests: not that Hyperliquid's real `fetch_tickers()` payload matches the fixture shape used in tests forever — only that the shape confirmed during this and the prior VALIDATE pass (read from the installed `ccxt` 4.5.78 source) is handled correctly today; an opt-in `integration`-marked test against the real exchange is the ongoing pin for this (per Standing Lesson #1).
- vitest component/caveat tests: not real canvas rendering or real cross-panel behavior (jsdom).
- Playwright E2E: seeded synthetic fixture data only; real-data correctness rests entirely on the AC-12 user walkthrough.

Gate: PASS (no FAILs, no unresolved CONCERNs — E1-E4 from the first-pass CONDITIONAL are confirmed
folded into concrete, testable plan requirements; this pass's own new finding (E5, the
`/categories`-calls-`mapping.py` correction) is fixed directly in the plan text, per the same
mechanism used for the ADR-2 correction in the first VALIDATE pass. AC-1/AC-3/AC-12's user- or
machine-only portions and the E1/OQ-4 sign-off gates are declared plan gates in the plan's own
Verification Evidence table and RFC-1 Stage 0, not open validate concerns, and do not block PASS.)

## Autonomous Goal Block

```
SESSION GOAL: Build /narrative per process/features/narrative-mindshare/active/narrative-dashboard_24-09-26/narrative-dashboard_PLAN_24-09-26.md -- per-category attention history, comparison view, change-in-attention view, a display-only Hyperliquid volume/listing proxy, and a widened coin-to-category map, fed by a nightly forward-archive workflow, while GET /api/narrative/categories and /screener's narrative strip stay byte-identical.
Charter + umbrella plan: N/A -- single plan (no umbrella/Stable Program Goal exists for narrative-mindshare)
AUTONOMY RULES: Execute one RFC at a time in order RFC-1..RFC-6 (RFC-4/RFC-5 may run in parallel sessions once RFC-3 is VERIFIED). Each RFC: Stage 0 research -> present findings -> STOP for user approval -> implement -> run the RFC's test stage -> phase report in this task folder -> STOP for user confirmation. Follow Validate Contract execute-agent instructions E1-E5. Tests touching the real cache must use the isolated_cache fixture.
HARD STOPS: any byte-level change to GET /api/narrative/categories or NarrativeStrip.tsx/confidence-badge behavior; wiring the exchange proxy into trigger.compute_trigger (ADR-6 forbids this); writing narrative_category_map.json beyond BTC/ETH/HYPE without explicit OQ-4 user sign-off (E4); any live network call to pytrends/Reddit/CoinGecko/Hyperliquid from a test; any API key or secret added; any failing test left red.
TEST GATES: uv run --project api pytest api/ -q | pnpm --filter web test | cd web && pnpm test:e2e -- full commands and per-criterion mapping in this plan's Validate Contract Test gates table.
VALIDATE CONTRACT: inline in this plan, ## Validate Contract section -- Gate: PASS, PVL cycle 1 re-validate complete, 24-09-26.
Next phase: EXECUTE -- RFC-1 Stage 0 only (read the real watchlist per E1, propose widened category/map, surface OQ-4 for explicit sign-off, then STOP for approval before any implementation).
EXECUTE START: ENTER EXECUTE MODE for RFC-1 Stage 0 of narrative-dashboard_PLAN_24-09-26.md
Reference for latest state: process/features/narrative-mindshare/active/narrative-dashboard_24-09-26/narrative-dashboard_PLAN_24-09-26.md
```

(Historical — EXECUTE is now complete for all 6 RFCs; see §Current Status and the amended Resume
and Execution Handoff above for the live state.)

---

## Post-EXECUTE Amendments (UPDATE PROCESS, 24-09-26)

All 6 RFCs shipped with real, user-approved deviations from this plan's original text. This
section is the durable record; the numbered sections above (ADRs, §11, §12b, §19) are left as
originally written for history and corrected here rather than silently rewritten in place.

**AC-1 / OQ-4 resolution (RFC-1, user decision "option B"):** AC-1 stayed strict, but the
mechanism differs from ADR-7's original design. `mapping.py::map_coin_to_category` (the function
`trigger.py`/`screener_board.py` actually call) stays on the **frozen legacy 3-coin map**
(`LEGACY_COIN_CATEGORY_MAP`, unchanged) — `/categories` and `/screener` are proven byte-identical
against a pre-change snapshot, including a scenario where a newly-mapped coin appears in the
mocked CoinGecko-trending fixture. The new curated JSON (`narrative_category_map.json`, 32
entries: l2s 9, ai 7, rwa 7, memecoins 8, plus grandfathered BTC→store-of-value) drives a
**separate, new function**, `mapping.map_coin_to_narrative_category(symbol) -> (category_id |
None, narrative_only)`, used only by `/history` and `/narrative`. Coins present only in the new
map show a `narrative_only` label. E1's gate resolved to option 3 (a curated well-known-coin list
per seed category, not literally sized against the real watchlist — the user approved the proposed
32-coin list as-is, with the explicit ask that it stay editable; the `_GUIDE.md` "How to edit the
narrative map" note documents this). OQ-1 resolved: seed categories stayed the existing 4 (ai, rwa,
l2s, memecoins) — no new seed categories were added. OQ-2 resolved: Hyperliquid via the existing
`ccxt_adapter._exchange()` singleton (ADR-6's direction), formula below. OQ-3 resolved: ADR-8's
original "archive an explicit `unavailable`/`credentials-not-configured` row" design was replaced
during RFC-4 (see below) by "write no row at all" — the display reason correspondingly differs.

**ADR-2 (history reuse) — confirmed as written**, no further correction beyond the one already
inline (forward-wins is enforced by the backfill script's read-before-write skip, not by
`write_narrative_point`'s own dedup).

**ADR-6 (exchange proxy) corrections (RFC-2):**
- **Denominator (D1):** not "all tracked coins" as ADR-6 said — the volume-share denominator is
  all active, non-HIP-3 Hyperliquid perps, plus an explicit `unmapped` bucket that is part of the
  total (shares sum to 1).
- **`redistributable` (D4):** `False`, not `true` as ADR-6 assumed — Hyperliquid's terms were never
  confirmed at RFC-2 Stage 0 (container egress blocked the check). `HYPERLIQUID_REDISTRIBUTABLE` in
  `api/data/hyperliquid_narrative_adapter.py` is a single constant; flip it to `True` only after the
  user reads Hyperliquid's ToU/API docs (user-PC step 6 in the Resume and Execution Handoff).
- **Symbol resolution:** ccxt upper-cases the `k`-prefixed base for meme perps (e.g. `kPEPE` →
  `KPEPE`); the resolver in `exchange_attention.py` handles `base == SYM` or `baseName ==
  "k"+SYM`. `ccxt_adapter.resolve_market_symbol` itself was not touched — out of RFC-2's scope.
- **New-listing diff (D3):** append-only market-snapshot JSON (`cache/narrative/exchange/markets/{date}.json`)
  plus a `baseline_date` field recording which prior day a diff was taken against. RFC-2's known
  gap, not fixed: if Hyperliquid is unavailable on the first attempt of a day, `run_daily`'s
  append-only write still records that day as `unavailable`; a later same-day successful retry
  stays `unavailable` (first-observation-wins). Flagged as a follow-up stub, not fixed this program.
- **Real verification unrun:** no live Hyperliquid payload and no real pytrends run have happened
  (container proxy blocks both); user-PC steps 3-5 in the Resume and Execution Handoff.

**ADR-7 title/scope correction:** "Coin-to-category map moves to curated JSON, sized against the
real watchlist" is only half true after option B — see the AC-1/OQ-4 resolution above. The curated
JSON does NOT replace `COIN_CATEGORY_MAP`'s lookup contract for `/categories`/`/screener` (that
map is frozen); it feeds a new, parallel lookup path used only by `/history`/`/narrative`.

**§11 API Surface — actual shape differs from the plan's flat `series[]` sketch (RFC-3):** the real
`GET /api/narrative/history` response is **category-first**, not the flat per-series list shown in
§11's illustrative JSON. Each category carries `variant`, `in_composite`, `mixed_scale`,
`coverage`, `sources_present`, `redistributable_all`, and a `coins` list (narrative-only flagging).
`trust_weight` is per composite point, not per source. Ranking happens only at `as_of` (latest
composite date ≤ `end`), scoped to the requested categories — no per-date rank history. An extra
composite slot, `coingecko-narrative`, sits alongside `pytrends`/`reddit`/`exchange_volume_share`;
the **legacy CoinGecko-trending count is shown for reference (labelled "CoinGecko trending
(legacy-map count)") but excluded from the composite** — user decision D1(a), RFC-3. `pytrends` has
two separate variants, `nightly-7d` and `backfill-269d`, each normalised on its own; a composite
point using a `backfill-269d` value (or a change figure spanning one) is flagged `mixed_scale`
because the two variants are on different Google-Trends request scales and are not directly
comparable (RFC-2's Forward Preview note, applied in RFC-3 as D2(a)). `redistributable` is `False`
for every source pending Hyperliquid's terms check.

**§12b Storage Schema — corrected (RFC-2, RFC-3):**

| Path | Columns | Write mode | Note |
|---|---|---|---|
| existing `cache/narrative/{source}/{category}.parquet` | `date, raw_value, normalized_value, source_status` | unchanged | **Keying correction:** `pytrends` and `reddit` are keyed by **keyword** (`source, keywords[0]`, e.g. `pytrends/AI crypto.parquet`), not by category id as the plan assumed (`pytrends/ai.parquet`) — this is how the pre-existing forward writers (`pytrends_adapter.py`, `reddit_adapter.py`) already worked; RFC-2's backfill and RFC-3/RFC-4's readers/writers all key the same way. `coingecko` (legacy) and the new `coingecko-narrative` are keyed by category id. |
| `cache/narrative/exchange/{category}.parquet` (RFC-2, actual columns) | `date, volume_share, volume_status, volume_reason, new_listing_count, listing_status, listing_reason, baseline_date` | append-only, forward-written, never rewrites an existing date | Volume and listing have separate statuses/reasons because day 1 has a valid volume share but no listing baseline (E2) |
| `cache/narrative/exchange/markets/{date}.json` (new, not in original §12b) | full daily market-list snapshot | append-only, never overwritten | Used by the new-listing diff to compare against the prior day |
| `cache/narrative/coingecko-narrative/{category}.parquet` (new, not in original §12b) | `date, raw_value, normalized_value, source_status` | written by RFC-4's nightly script via `map_coin_to_narrative_category` counts | Composite slot; excluded from the legacy `/categories` trigger path |

**Reddit "no-archived-data" — corrects ADR-8 (RFC-4, RFC-6):** ADR-8 originally said the nightly
job would archive an explicit `source_status="unavailable"` row with reason
`credentials-not-configured` when Reddit creds are unset. The actual RFC-4 implementation (C1) is
stricter: **no row is written at all** for Reddit when `REDDIT_CLIENT_ID`/`REDDIT_CLIENT_SECRET`
are unset — the script prints a `reddit: unavailable (credentials-not-configured)` summary line to
the job log only. Because no row exists, `/history` and `/narrative` show Reddit's absence as
**`no-archived-data`**, not `credentials-not-configured` (RFC-6's e2e spec and vitest assert
`no-archived-data`; `format-unavailable-reason.ts` carries both reason strings — one for a fetch
that ran and failed, one for a fetch that never ran).

**§19 Ops Runbook corrections (RFC-2, RFC-4):**
- pytrends is **not** a project dependency — every pytrends command needs `--with pytrends`:
  `uv run --project api --with pytrends python api/scripts/backfill_pytrends_history.py [--dry-run]`
  and `uv run --project api --with pytrends python -m api.scripts.snapshot_narrative [--dry-run]`.
  The plan's original Ops Runbook line omitted `--with pytrends`.
- **Optional Reddit history from day one needs two changes, not one.** Adding the
  `REDDIT_CLIENT_ID`/`REDDIT_CLIENT_SECRET` GitHub Actions secrets is not sufficient by itself — the
  workflow (`narrative-snapshot.yml`) deliberately maps zero secrets into the job's `env`, so a
  second, manual two-line `env:` edit to the workflow file is also required. The original Ops
  Runbook line implied the secrets alone were enough.
- The nightly workflow's cron is `0 23 * * *` (not the `15 23 * * *` placeholder the plan's RFC-4
  Stage description suggested), 30 minutes ahead of LiqTide's `30 23 * * *`, with its own
  `concurrency: narrative-snapshot` group (not shared with LiqTide's).

**Known bug queued as a separate follow-up (RFC-3, not fixed in this program):**
`trigger.py::compute_narrative_categories` (line 206) reads
`cache.read_narrative_series(source, category_id)` for pytrends/reddit/coingecko — i.e. by
**category id**, not by the keyword key those adapters actually write under (see the §12b keying
correction above). Effect: `/categories`' own trigger never reads the archived pytrends/reddit
history back — it effectively runs on CoinGecko alone. This predates this program (RFC-003 of
momentum-screener) and was found, not caused, here. Fixing it would change `/categories`' output,
so it requires its own deliberate AC-1 contract re-baseline and user sign-off — explicitly **not**
folded into this program. Backlog note owner: orchestrator, to queue as a separate plan.

**D1 product fix inside RFC-3's blast radius (RFC-6):** `api/analytics/narrative/history.py`'s
`_exchange_frames` built columns from Python `str`/`None` lists; current pandas infers a
NaN-backed `StringDtype` for such a list, turning `None` into `NaN`, which
`NarrativeHistoryPoint.reason: str | None` then rejected — a 500 on `/history` as soon as one
exchange series holds a day with a listing reason and a day without (i.e. from day 2 of the nightly
archive onward). Fixed by building those columns as `pd.Series(..., dtype=object)` instead, which
preserves `None`. Caught by RFC-6's `web/e2e/narrative.spec.ts` (a real defect no earlier layer's
coverage could reach — vitest uses injected fixtures, RFC-3's own tests used single-row/all-None
reasons); a regression test now pins it. See `process/context/tests/all-tests.md` for the
generalized Standing Lesson entry.

**Verification Evidence table — additions, not replacements:** every row in the plan's original
table still holds; add that RFC-6's e2e run is the actual AC-12 (E2E portion) proof, at 26/26 x2,
and that it is what found and fixed the D1 defect above — a concrete instance of this project's
"green does not mean verified" Standing Lesson, closed the same session it was found.
