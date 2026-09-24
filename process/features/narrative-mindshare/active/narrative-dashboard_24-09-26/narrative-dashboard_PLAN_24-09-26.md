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

Status: CONDITIONAL
Date: 24-09-26
date: 2026-09-24
generated-by: outer-pvl

Parallel strategy: sequential
Rationale: 6 RFCs with a mostly-linear dependency chain (RFC-4/RFC-5 are the only parallel pair,
both gated behind RFC-3), one feature folder, no independent cross-package workstreams that need
mid-run coordination — dominant signal is sequential dependency, same shape as the regime
dashboard's own validate-contract, which this plan is structurally modelled on.

Test gates (C3 5-column table):

| criterion id | behavior | strategy | proving test | gap-resolution |
|---|---|---|---|---|
| AC-1 | `GET /api/narrative/categories` byte-identical for BTC/ETH/HYPE before/after | Fully-Automated | `api/tests/routers/test_narrative_categories_contract.py` | B |
| AC-1 | `/screener` narrative strip/confidence badge unaffected | Hybrid | `pnpm --filter web test` (`NarrativeStrip.test.tsx`, `ConfidenceBadge.test.tsx`, both pre-existing, re-run unmodified) | B |
| AC-2 | history chart built from archived points, not a single reading | Fully-Automated | `api/tests/analytics/test_history.py` (real cache round-trip) | B |
| AC-3 | nightly workflow dry-run, no duplicate on same-day re-run, Reddit-unset path clean | Hybrid | `api/tests/scripts/test_snapshot_narrative.py` | B |
| AC-3 | scheduled trigger actually fires on `narrative-snapshot.yml`'s cron | Agent-Probe | user checks archive after nightly runs (mirrors LiqTide AC-3 precedent) | A |
| AC-4 | pytrends `interest_over_time()` backfill, golden rows, forward-write-wins dedup | Fully-Automated | `api/tests/scripts/test_backfill_pytrends_history.py` | B |
| AC-5 | comparison view ranking on seeded fixture | Agent-Probe | vitest component probe + manual walkthrough | B |
| AC-6 | change-in-attention view distinct from a level ranking | Agent-Probe | vitest component probe + manual walkthrough | B |
| AC-7 | exchange proxy fails safely, explicit `unavailable` on fetch failure | Fully-Automated | `api/tests/data/test_hyperliquid_narrative_adapter.py`, `api/tests/analytics/test_exchange_attention.py` | B |
| AC-8 | widened map coverage; unmapped coin still `None` | Fully-Automated | `api/tests/analytics/test_mapping.py` (extend) | B |
| AC-9 | one source down never takes down the rest of the dashboard | Fully-Automated | `api/tests/routers/test_narrative_history.py` | B |
| AC-10 | no raw cross-source level comparison; within-source normalisation boundary asserted | Fully-Automated | `api/tests/analytics/test_history.py`, `test_exchange_attention.py` | B |
| AC-11 | data-quality caveat visible on every dashboard view | Agent-Probe | vitest `__tests__/*` + manual walkthrough | B |
| AC-12 | real frontend/backend boundary proof on seeded fixture | Fully-Automated | `cd web && pnpm test:e2e` (`web/e2e/narrative.spec.ts`) | B |
| AC-12 | real-cache user walkthrough against live providers | Agent-Probe | user, own machine (egress proxy blocks providers here — same as regime dashboard AC-11 precedent) | A |

C-4 reconciliation: `strategy` values above are Fully-Automated / Hybrid / Agent-Probe only;
Known-Gap is not used as a strategy anywhere in this table — every behavior above has a proving
gate (gap-resolution B = fixed by this plan's own checklist; A = proven directly, Agent-Probe rows
are proven by the user, not deferred).

Failing stubs (Fully-Automated rows; replace during EXECUTE):

```python
def test_narrative_categories_contract_byte_identical(): raise NotImplementedError("TDD stub: GET /api/narrative/categories byte-identical for BTC/ETH/HYPE before/after")
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

Dimension findings:
- Infra fit: PASS — no container/infra/proxy surface touched; `GET /api/narrative/history` inherits the existing global `GZipMiddleware` for free (confirmed in `api/main.py`); the new nightly workflow mirrors `.github/workflows/liqtide-snapshot.yml`'s checkout/setup-uv/run/commit shape exactly, including `permissions: contents: write` — no new infra pattern introduced.
- Test coverage: CONCERN — see Layer 2 RFC-1/RFC-2 findings below (E1, E2); AC-3/AC-12's live-provider portions are structurally Agent-Probe in this sandbox (egress proxy blocks Google Trends/Reddit/CoinGecko/Hyperliquid, confirmed by the regime dashboard's identical AC-11 precedent) — declared as such in the plan's own Verification Evidence table already, not a new gap.
- Breaking changes: PASS — mechanically confirmed by reading `api/routers/narrative.py` and `api/analytics/narrative/trigger.py::assemble_narrative_categories` directly: the `/categories` code path never calls `mapping.py` at all (no per-coin lookup happens in that response), so widening `COIN_CATEGORY_MAP`/moving it to JSON cannot change `/categories`' shape or content by construction, independent of the contract snapshot test — the test is real (a byte-identical assertion for BTC/ETH/HYPE) and this mechanical fact makes it sufficient, not merely reassuring. `map_coin_to_category` only reaches `screener_board.py`'s per-coin `narrative_state` (OQ-4's own scope), confirming OQ-4 is correctly the only real risk surface and is already gated as a hard user sign-off at RFC-1 Stage 0.
- Security surface: PASS — no new secret required to ship (Hyperliquid via keyless `ccxt_adapter._exchange()`; Reddit's two existing optional secrets unchanged); local bind (`127.0.0.1`) and CORS scope unchanged; new nightly workflow's `contents: write` permission mirrors the already-running `liqtide-snapshot.yml` exactly, not a new permission pattern.
- RFC-1 feasibility: CONCERN — mechanically feasible (`api/tests/analytics/test_mapping.py` already exists to extend; `map_coin_to_category`'s contract is unchanged by the JSON swap). Gap: `api/data/watchlist.json` does not exist in this sandbox (gitignored, personal data) — RFC-1 Stage 0's "read the real watchlist" step cannot execute here; see E1.
- RFC-2 feasibility: CONCERN — Hyperliquid `fetch_tickers()` volume-share approach mechanically CONFIRMED during this VALIDATE pass by reading the installed `ccxt` 4.5.78 package directly (not a live call, no `needs-live-provider` opt-in required): `ccxt.hyperliquid().has['fetchTickers'] is True`; `fetch_tickers(symbols=None)` returns all market tickers per its own docstring ("all market tickers are returned if not assigned"); `parse_ticker` maps Hyperliquid's `dayNtlVlm` field to the unified `quoteVolume` field per symbol — exactly what RFC-2's volume-share formula needs. RFC-2 Stage 0 can treat this as settled and does not need to re-derive it live; only the redistribution/ToS confirmation remains genuinely open there. Two real gaps found: (a) ADR-2's claim that "existing date-based dedup already prevents overwrite" is inaccurate — fixed directly in this VALIDATE pass, see Plan updates applied below; (b) the new-listing diff has no defined day-1 behavior (no prior snapshot to diff against) — see E2.
- RFC-3 feasibility: PASS — `grid_dates`/`gap_before`/`max_gap_days` pattern is proven end-to-end on `/regime` already (`api/analytics/regime/components.py`, `components_response.py`); reusing the shape (not the code, per the RFC's own Stage 0 framing) is mechanically straightforward; `get_history` sharing only `load_seed_categories` with `get_categories` is grep-verifiable once written.
- RFC-4 feasibility: PASS — `.gitignore`'s existing `api/data/cache/*` + `!api/data/cache/liqtide/` carve-out mechanic (confirmed by reading `.gitignore` directly, including its own inline comment explaining "parent must be excluded per-entry") extends cleanly to `!api/data/cache/narrative/`; nested `cache/narrative/exchange/` needs no separate negation, mirroring how `liqtide/`'s contents are already included with only the one parent-level negation line. Workflow file mechanically mirrors `liqtide-snapshot.yml` line for line.
- RFC-5 feasibility: PASS — `RegimeDashboard.tsx`/`DeadDataNotice.tsx`/`format-unavailable-reason.ts` fetch-once and degraded-state patterns are proven and directly reusable; `format-unavailable-reason.ts`'s `switch` statement is a clean, low-risk extension point for the new `credentials-not-configured` case (mechanically confirmed by reading the file: one new `case` arm).
- RFC-6 feasibility: PASS — `seed_e2e_cache.py`'s `_guard()` (refuses to run without an explicit, non-default `SCREENER_CACHE_ROOT`) and its `SCREENER_WATCHLIST_PATH` `{"coins": [...]}` shape (confirmed against `watchlist.py::_load_raw`'s actual parsing contract, directly addressing Standing Lesson #7) are real, reusable safety mechanisms — `build_narrative_fixture`/`seed_narrative` can follow the exact same shape.

Execute-agent instructions:
- E1: RFC-1 Stage 0 — if `api/data/watchlist.json` is absent on the machine running Stage 0 (confirmed absent in this VALIDATE sandbox; it is gitignored, personal data), do not silently treat `read_watchlist()`'s resulting empty list as "nothing to map." Stop and ask the user directly for their current watchlist content (or defer Stage 0 to a session on the user's own machine) before proposing the widened category/map list.
- E2: RFC-2 `exchange_attention.py`'s new-listing diff has no prior day's market-list snapshot on its first run. Implement an explicit "no baseline yet" state for day one (e.g. `new_listing_count: null` with a distinct status/reason), never a bare `0` — a real zero-diff and "nothing to compare against yet" are different facts and the project's "numbers are never silently wrong" rule applies here exactly as it does to the three existing sources.
- E3: this plan adds a new public API surface (`GET /api/narrative/history`) and a new deploy/runtime surface (`.github/workflows/narrative-snapshot.yml`, scheduled job with `contents: write` pushing to `main`) — both are High-Risk Execution Handoff classes (`process/development-protocols/orchestration.md`). Produce the manual-first evidence pack (`vc-risk-evidence-pack`: `risk-gate.json`, `context-snippets.json`, `verification.json`, `review-decision.json`) inside this task folder's `harness/` subdirectory before treating RFC-3/RFC-4 as finalize-ready. Auto-stop rule applies — do not report those RFCs DONE with the work implied fully proven until the pack exists.
- E4: RFC-1 Stage 0's OQ-4 sign-off (which newly-mapped coins would see their `/screener` `narrative_state` change) must be presented and explicitly approved by the user before any map file beyond BTC/ETH/HYPE is written — this was already a plan requirement; restated here because it is a hard execute-agent gate, not an optional courtesy.

Open gaps: none carried to backlog — all findings above are either mechanically resolved during this VALIDATE pass (RFC-2 ccxt feasibility, ADR-2 wording), folded into the plan as execute-agent instructions (E1-E4), or already correctly scoped as Agent-Probe/user-only in the plan's own Verification Evidence table (AC-3's cron-firing portion, AC-12's live-provider portion).

What this coverage does NOT prove:
- Contract snapshot test: not that `screener_board.py`'s per-coin `narrative_state` is unaffected by the widened map for newly-mapped coins beyond BTC/ETH/HYPE — that change is intended (OQ-4) and gated on explicit user sign-off, not proven "unchanged" by this gate.
- History/composite tests: not that the composite/rank/delta maths matches any external ground truth — narrative attention has no authoritative source to check against; only internal consistency (skipna-mean coverage rule, normalisation boundary) is proven.
- Nightly workflow hybrid test: not that GitHub Actions cron actually fires on schedule in production, and not that Reddit secrets (if the user later adds them) work end-to-end — only the unset-credentials path and no-duplicate-on-rerun behavior are proven.
- Backfill test: not that `pytrends.interest_over_time()` still works at all (it is unofficial/archived since April 2025, per `pytrends_adapter.py`'s own module docstring) — only that IF it returns data, the rows are written correctly and forward-written dates are skipped.
- Hyperliquid adapter/exchange-attention tests: not that Hyperliquid's real `fetch_tickers()` payload matches the fixture shape used in tests forever — only that the shape confirmed during this VALIDATE pass (read from the installed `ccxt` 4.5.78 source) is handled correctly today; an opt-in `integration`-marked test against the real exchange is the ongoing pin for this (per Standing Lesson #1).
- vitest component/caveat tests: not real canvas rendering or real cross-panel behavior (jsdom).
- Playwright E2E: seeded synthetic fixture data only; real-data correctness rests entirely on the AC-12 user walkthrough.

Gate: CONDITIONAL (concerns noted, folded into plan fixes + execute-agent instructions, no unresolved FAILs)
Accepted by: session (autonomous, automatic-mode VALIDATE pass per user's "go") — accepted concerns:
ADR-2 dedup-wording inaccuracy (fixed directly in this pass, see plan's ADR-2); E1 watchlist.json
sandbox gap; E2 new-listing day-1 undefined state; E3 risk-evidence-pack requirement for the new
public API + scheduled-workflow surfaces; E4 restated OQ-4 hard gate. No item blocks EXECUTE start
on RFC-1 Stage 0 — E1 only blocks proceeding past Stage 0 if the real watchlist remains unavailable.



## Autonomous Goal Block

```
SESSION GOAL: Build /narrative per process/features/narrative-mindshare/active/narrative-dashboard_24-09-26/narrative-dashboard_PLAN_24-09-26.md -- per-category attention history, comparison view, change-in-attention view, a display-only Hyperliquid volume/listing proxy, and a widened coin-to-category map, fed by a nightly forward-archive workflow, while GET /api/narrative/categories and /screener's narrative strip stay byte-identical.
Charter + umbrella plan: N/A -- single plan (no umbrella/Stable Program Goal exists for narrative-mindshare)
AUTONOMY RULES: Execute one RFC at a time in order RFC-1..RFC-6 (RFC-4/RFC-5 may run in parallel sessions once RFC-3 is VERIFIED). Each RFC: Stage 0 research -> present findings -> STOP for user approval -> implement -> run the RFC's test stage -> phase report in this task folder -> STOP for user confirmation. Follow Validate Contract execute-agent instructions E1-E4. Tests touching the real cache must use the isolated_cache fixture.
HARD STOPS: any byte-level change to GET /api/narrative/categories or NarrativeStrip.tsx/confidence-badge behavior; wiring the exchange proxy into trigger.compute_trigger (ADR-6 forbids this); writing narrative_category_map.json beyond BTC/ETH/HYPE without explicit OQ-4 user sign-off (E4); any live network call to pytrends/Reddit/CoinGecko/Hyperliquid from a test; any API key or secret added; any failing test left red.
TEST GATES: uv run --project api pytest api/ -q | pnpm --filter web test | cd web && pnpm test:e2e -- full commands and per-criterion mapping in this plan's Validate Contract Test gates table.
VALIDATE CONTRACT: inline in this plan, ## Validate Contract section -- Gate: CONDITIONAL, accepted by session (automatic mode), 24-09-26.
Next phase: EXECUTE -- RFC-1 Stage 0 only (read the real watchlist per E1, propose widened category/map, surface OQ-4 for explicit sign-off, then STOP for approval before any implementation).
EXECUTE START: ENTER EXECUTE MODE for RFC-1 Stage 0 of narrative-dashboard_PLAN_24-09-26.md
Reference for latest state: process/features/narrative-mindshare/active/narrative-dashboard_24-09-26/narrative-dashboard_PLAN_24-09-26.md
```
