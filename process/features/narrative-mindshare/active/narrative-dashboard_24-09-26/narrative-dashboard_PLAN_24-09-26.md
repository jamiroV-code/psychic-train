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
**Status**: ⏳ PLANNED — no RFC started
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
| RFC-1 | Data foundation: category map JSON + history read/write | ⏳ PLANNED |
| RFC-2 | Exchange (Hyperliquid) adapter + pytrends historical backfill script | ⏳ PLANNED — depends on RFC-1 |
| RFC-3 | `GET /api/narrative/history` endpoint + comparison/change maths | ⏳ PLANNED — depends on RFC-1, RFC-2 |
| RFC-4 | Nightly forward-archive workflow | ⏳ PLANNED — depends on RFC-3; **can run in parallel with RFC-5** |
| RFC-5 | `/narrative` page — history charts, comparison, change-in-attention, caveat | ⏳ PLANNED — depends on RFC-3; **can run in parallel with RFC-4** |
| RFC-6 | End-to-end proof + AC-12 real-cache handoff | ⏳ PLANNED — depends on RFC-4 and RFC-5 |

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
string value in an existing, untyped column — no migration). Existing date-based dedup already
prevents overwrite; the backfill script must never overwrite an already-archived (forward-written)
point with a backfilled one — forward-written points always win on conflict.

**Rationale**: Standing Rule ("numbers are never silently wrong") plus "one source of numerical
truth" — reusing the exact writer the backend already trusts avoids a second, drifting history path.

**Implications**: `write_narrative_point`'s existing signature is unmodified; the backfill script
calls it directly, checking `read_narrative_series` first to skip dates that already have a
forward-written (non-backfilled) point.

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
under an explicit "unmapped" bucket, never dropped). `redistributable=true` (Hyperliquid's public
market data, no ToS restriction found at RFC-2 Stage 0 — confirm and record).

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
explicitly surfaced, not silently accepted.

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

All RFCs ⏳ PLANNED. Nothing in `process/features/narrative-mindshare/active/narrative-dashboard_24-09-26/`
has started implementation.

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
- Confirm `read_narrative_series`/`write_narrative_point`'s exact signature and dedup behavior
  (does a repeated write for the same date overwrite or skip? — confirm before RFC-2's backfill
  logic depends on it).
- Surface **OQ-4** explicitly: which newly-mapped coins (beyond BTC/ETH/HYPE) would see their
  `/screener` `narrative_state` change, and get explicit user sign-off before implementing.

**Stages**
1. `api/data/narrative_category_map.json` — new curated map, approved content from Stage 0.
2. `mapping.py::load_category_map()` — loads the JSON (same pattern as
   `trigger.load_seed_categories`); `map_coin_to_category` reads from it; unmapped still returns
   `None`.
3. `api/data/narrative_categories.json` — widened seed list (if Stage 0 approved new categories).
4. Contract snapshot test: `GET /api/narrative/categories` output for BTC/ETH/HYPE fixed inputs,
   captured before this RFC and re-asserted after.

**Post-Phase Testing**
- Test file: `api/tests/analytics/test_mapping.py` (extend) — widened map covers Stage 0's list;
  unmapped coin still `None`; JSON load failure degrades to empty map (not a crash).
- Test file: `api/tests/routers/test_narrative_categories_contract.py` (new) — byte-identical
  response for BTC/ETH/HYPE before/after.
- Run: `uv run --project api pytest api/ -q`.
- Verification query:
  ```
  uv run --project api python -c "import duckdb; print(duckdb.sql(\"select * from 'api/data/cache/narrative/pytrends/ai.parquet'\"))"
  ```

**Verification Checklist**
- [ ] Manual test passed
- [ ] Data in storage verified (query output pasted)
- [ ] Error handling confirmed
- [ ] User confirmed the widened map (and OQ-4 sign-off) before implementation

**Acceptance Criteria**: AC-1, AC-8.
**What's Functional Now**: wider map, contract-proven unchanged `/categories` behavior.
**Ready For**: RFC-2.

**Implementation Checklist**
- [ ] Stage 0 findings + OQ-4 presented; user approved
- [ ] `narrative_category_map.json` + `load_category_map()` + tests
- [ ] Contract snapshot test added and green
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
   `cache/narrative/exchange/`, diffs against today's).
3. `backfill_pytrends_history.py`: fetch → per-date rows via `write_narrative_point(...,
   source_status="backfilled")`, skipping any date already forward-written.

**Post-Phase Testing**
- `api/tests/data/test_hyperliquid_narrative_adapter.py` — fixture parse, timeout → `unavailable`.
- `api/tests/analytics/test_exchange_attention.py` — golden volume-share values; new-listing diff
  on synthetic snapshots; unmapped new listing → explicit "unmapped" bucket, never dropped.
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
5. `format-unavailable-reason.ts`: add `credentials-not-configured` case.

**Post-Phase Testing**
- vitest under `web/components/narrative/__tests__/`: one panel per tracked category up to the
  soft cap; overflow list renders remaining categories on demand; caveat present on all three
  views; injected fetcher error → `DeadDataNotice`; `credentials-not-configured` renders its own
  copy, not the generic "unavailable" text.
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

- **New**: `GET /api/narrative/history` (§11 shape); `NarrativeHistoryResult` Python dataclass;
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

1. **Selected plan file**: `process/features/narrative-mindshare/active/narrative-dashboard_24-09-26/narrative-dashboard_PLAN_24-09-26.md`
2. **Last completed phase or step**: PLAN complete 24-09-26; VALIDATE not yet run; no RFC started.
3. **Validate-contract status**: pending — `vc-validate-agent` writes `## Validate Contract` before
   EXECUTE.
4. **Supporting context files loaded**: `process/context/all-context.md`,
   `process/context/data-sources/all-data-sources.md`, `process/context/tests/all-tests.md`,
   `process/context/planning/all-planning.md`, `process/features/narrative-mindshare/_GUIDE.md`,
   the narrative-dashboard SPEC in this same task folder, the regime dashboard PLAN as structural
   precedent, plus every source file named under §1 Context and Goals.
5. **Next step for a fresh agent**: run `ENTER VALIDATE MODE` on this plan. On PASS/CONDITIONAL
   acceptance, `ENTER EXECUTE MODE` for **RFC-1 Stage 0 only** (read the real watchlist, propose the
   widened category/map, surface OQ-4 for explicit sign-off, then STOP for approval before any
   implementation).

**Open Questions carried from SPEC, plus one new question raised during PLAN:**
- **OQ-1** (category/coin-map scope) — resolved procedurally: RFC-1 Stage 0 reads the real
  watchlist and proposes the concrete list; not resolved with placeholder values in this plan
  because the real watchlist content is dynamic data this PLAN session should not guess at.
- **OQ-2** (exchange choice/formula) — narrowed by the Decision Summary to Hyperliquid via the
  existing `ccxt_adapter` singleton (ADR-6); the exact volume-share/new-listing formula is finalized
  at RFC-2 Stage 0.
- **OQ-3** (Reddit nightly credentials) — resolved (ADR-8): no secret required to ship; optional
  secret documented in the Ops Runbook.
- **OQ-4 (new, raised during PLAN)** — widening `COIN_CATEGORY_MAP` (via ADR-7) will change
  `screener_board.py`'s `narrative_state` output for any newly-mapped coin beyond BTC/ETH/HYPE
  (which AC-1 protects explicitly). This is a real, intended side effect of US-5/AC-8, but it is a
  `/screener` display change nonetheless. **Do not silently proceed** — RFC-1 Stage 0 must present
  the exact list of newly-mapped coins and their resulting screener narrative badges for explicit
  user approval before implementation, separate from (but alongside) the category-list approval.

Reports for each RFC go in this same task folder as
`narrative-dashboard_24-09-26-RFC-N-phase-report.md`.

## Validate Contract

(placeholder — vc-validate-agent writes this section before EXECUTE)
