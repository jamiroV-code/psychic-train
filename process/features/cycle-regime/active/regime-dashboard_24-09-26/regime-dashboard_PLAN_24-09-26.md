# Regime Dashboard — Six Liquidity Components + Tide Index on One Synced Timeline

**Date**: 24-09-26
**Complexity**: Complex (standard complex — one authoritative plan, sequential RFCs)
**Status**: ⏳ PLANNED — VALIDATE CONDITIONAL (accepted 24-09-26)
**Feature folder**: `process/features/cycle-regime/`
**Owner**: Jamiro (user) · executor: vc harness agents

> **TL;DR** — Build `/regime`: six stacked, time-synced charts (net liquidity, stablecoin supply,
> broad dollar, ON-RRP, spot-ETF flows, BTC dominance) plus a tide-index panel, 3+ years visible by
> default, every value drillable to its source and formula. LiqTide's own history is too short
> (~2024-09 at best, and our archive holds **one day**), so the six components are reproduced from
> free primaries in Python and LiqTide's published score is shown next to our reproduction, not
> instead of it. Two components have honest depth gaps (ETF flows start 2024-01-11; BTC dominance
> has no free deep history) and are shown as "not applicable / no data", never zero-filled.

---

## Overview

The cycle-regime feature has been `not-started` since setup, but most of its inputs already exist
because the momentum screener's RFC-002 built them: `fred_adapter.py` (WALCL, WTREGEN, RRPONTSYD,
DTWEXBGS, WRESBAL — keyless, decades deep), `defillama_adapter.py` (stablecoin supply since
2017-11-29), `liqtide_adapter.py` (daily append-only archive) and `liquidity_composite.py` (a
4-part z-scored composite used for leg-boundary detection).

This plan turns those inputs into the learnable research interface described in the regime
dashboard spec: one row per LiqTide component, one composite row, a single shared time axis,
synchronized zoom and crosshair, and a readout that shows every component's value at the hovered
date. It follows the north-star rules: the data layer is fixed and never reshaped, nothing is drawn
on the charts beyond the data itself, nothing learns about the user, and no directional call is
made. The insights text box is **not** built here (build-order step 2) — this plan only reserves
its layout column so adding it later does not move the charts.

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
| RFC-001 | LiqTide raw archive, history backfill + source research | 🧪 TESTING — live payload replayed OK (24-09-26); awaiting pytest on PC + scheduled task |
| RFC-002 | Component maths (six impulses + reproduced composite) | 🔨 CODE DONE (24-09-26) — real-data check: 5/6 components exact, r = 0.964 vs published |
| RFC-003 | Spot-ETF flows adapter (conditional on RFC-001 Stage 0) | 🔨 CODE DONE (24-09-26) — Farside cached 2024-01-11 → 2026-09-23 (677 days); 256 passed; see RFC-003 phase report |
| RFC-004 | `GET /api/regime/components` endpoint | 🔨 CODE DONE (24-09-26) — 20 endpoint tests green; live run: ETF 8 / BTC-dom 117 pts match RFC-002 |
| RFC-005 | `/regime` page — stacked synced charts, readout, drill-down | 🔨 CODE DONE (24-09-26) — vitest 63/63 (40 + 23 new), tsc + `next build` clean, E3 sync proven; browser probe screenshot in task folder |
| RFC-006 | End-to-end proof + user walkthrough | ⏳ PLANNED |

---

## 1. Context and Goals

**Why now.** The north-star build order puts "keep the data layer solid" first. The regime
dashboard is the one data-layer area with no screen at all, and its inputs are mostly already
cached. It is also the input surface the insights engine will scan later (divergences between
usually-linked series, lead/lag) — those scans are only verifiable if the user can go to the
listed dates on these charts.

**Context loaded for this plan** (per `process/context/all-context.md` routing):

- `process/context/all-context.md` — repo state, adapters, ADR-1 leg-boundary amendments
- `process/context/data-sources/all-data-sources.md` — LiqTide methodology table, Standing Rule 8
- `process/context/tests/all-tests.md` — runners, commands, "green does not mean verified" lesson
- `process/features/cycle-regime/_GUIDE.md` — target locations, provisional-vs-settled label rule
- `api/data/liqtide_adapter.py`, `api/analytics/regime/liquidity_composite.py`,
  `api/data/fred_adapter.py`, `api/data/cache.py`, `api/routers/regime.py`, `api/models/regime.py`
- `web/components/screener/RelativePerformanceChart.tsx`, `web/lib/api/screener.ts`,
  `web/components/screener/DeadDataNotice.tsx`

**Research findings that shape this plan (24-09-26, from the repo):**

| Finding | Consequence |
|---|---|
| LiqTide `metrics` history only reaches ~2024-09 (net liquidity, dollar) / ~2025-06 (btc_dom) — confirmed at RFC-002 Stage 0 of the momentum screener | Cannot reach 3 years from LiqTide alone → reproduce components from primaries (ADR-1) |
| `api/data/cache/liqtide/` holds a single file, `2026-09-20.parquet` | Nothing runs the snapshot daily → schedule it (ADR-4) |
| The archived row keeps only flattened current values (`tide_score`, 4 metrics) — `raw` JSON, `tide_series`, `tide_index.components/weights/value/label` are dropped | Derived history LiqTide publishes today is being lost → archive raw JSON (ADR-4) |
| Archived `tide_score` is `-0.0701` for 2026-09-20 — not on the 0–100 scale the spec describes | Which field is the 0–100 index (`value` vs `score`) must be confirmed at Stage 0 before plotting |
| No free, keyless, deep BTC-dominance history (CoinGecko historical global chart is paid-tier) | BTC-dominance panel starts where data starts; earlier dates show "no data" (ADR-2) |
| No ETF-flows adapter exists; spot BTC ETFs launched 2024-01-11 | Pre-launch dates are "not applicable", distinct from "unavailable" (ADR-2) |
| `liquidity_composite.build_reduced_composite` feeds `leg_boundary.py` | Must not be modified by this plan (Blast Radius) |

**Goals**

1. See all six components and the composite for 3+ years on one synced time axis, and scroll back
   to each component's earliest data.
2. Hover any date → exact values of all six components plus composite, with source and as-of date.
3. Click any panel → the full calculation chain (source series IDs, transform, window, weight,
   coverage, last fetch, status).
4. See where our reproduced composite and LiqTide's published score agree or disagree, as numbers.
5. Never lose another day of LiqTide's derived output.

**Success metrics**

- Default view shows ≥ 3 years for net liquidity, stablecoin supply, broad dollar and ON-RRP.
- Zoom from full range to a single month on all seven panels together with no visible lag
  (target: < 100 ms per interaction on the user's machine).
- 0 zero-filled or interpolated values anywhere; every gap is labelled with its reason.
- Raw LiqTide archive gains one file per day without manual action.

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
`api/data/cache/**.parquet` file (or the raw JSON archive), with the query and its output pasted
into the phase report.

---

## 1.5 Execution Brief

### RFC-001: Data foundation (archive + backfill + source research)

- **What happens**: Stage 0 answers the open source questions (LiqTide field semantics,
  `tide_series` depth, Farside usability, BTC-dominance alternatives). Then the adapter starts
  archiving the raw JSON daily, backfills whatever history today's payload carries, and the snapshot
  is scheduled.
- **Integration points**: `liqtide_adapter.fetch_latest` → `cache.write_liqtide_raw` → new
  `cache/liqtide/raw/{date}.json`; Windows Task Scheduler → `snapshot_liqtide.py`.
- **Test**: run the snapshot twice on the same day; second run must not overwrite.
- **Verify**: list `cache/liqtide/raw/`, open the JSON, count `tide_series` points and first date.
- **Done when**: user sees a new raw file appear the next morning without running anything.

### RFC-002 – RFC-003: Component maths + ETF flows

- **What happens**: a new `analytics/regime/components.py` computes each of the six impulses and a
  reproduced composite from cached primaries; RFC-003 adds a Farside adapter if Stage 0 cleared it.
- **Integration points**: reads `fred_adapter`, `defillama_adapter`, LiqTide raw archive, new ETF
  adapter; writes nothing to the leg-boundary path.
- **Test**: pytest golden values on synthetic series; Hybrid cross-check vs LiqTide's published
  per-component values for archived dates.
- **Verify**: print first/last date and row count per component from a live-cache run.
- **Done when**: user reviews the coverage table (component × first date × gaps) and agrees.

### RFC-004 – RFC-005: Endpoint + page

- **What happens**: `GET /api/regime/components` returns all series with metadata; `/regime`
  renders seven stacked lightweight-charts instances with synced range + crosshair, a readout row,
  and a drill-down per panel.
- **Integration points**: `routers/regime.py` → `components.py`; `web/lib/api/regime.ts` →
  `web/components/regime/*`.
- **Test**: vitest component tests with injected fetchers; manual zoom/hover/drill-down.
- **Verify**: `curl` the endpoint and check lengths/first dates match the RFC-002 coverage table.
- **Done when**: user opens `/regime`, zooms, hovers, drills into two panels and confirms.

### RFC-006: End-to-end proof

- **What happens**: Playwright spec against a seeded fixture cache exercises the real
  frontend/backend boundary; user walkthrough against the real cache.
- **Test**: `cd web && pnpm test:e2e`.
- **Done when**: E2E green and the user completes the walkthrough checklist.

### Expected Outcome

- `/regime` shows six component panels + one composite panel on one shared, synced time axis,
  3 years visible by default, scrollable to each series' earliest point.
- Hover readout lists all seven values for the hovered date, each with source + as-of date.
- Each panel's drill-down shows the full calculation chain; gaps carry a reason.
- Composite panel shows LiqTide's published index (where it exists) and our reproduction as two
  labelled lines; agreement stats are in the drill-down, as numbers only.
- LiqTide raw JSON archived daily, automatically.
- The leg-boundary path and screener are byte-for-byte unaffected.

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

### Example phase execution (RFC-002)

```
Agent (Step 1): Reads liquidity_composite.py, fred_adapter.py, defillama_adapter.py, RFC-001
  Stage 0 findings. Reports: "RRPONTSYD is daily (business days); WALCL/WTREGEN are weekly and
  fetch_net_liquidity already carries them as-of the latest weekly release onto RRP's daily rows —
  reuse that, labelled. Windows must be calendar-based: 28 rows of business days is ~5.5 weeks.
  LiqTide normalisation to −1..+1 is not published; proposing clip(z, ±3)/3 with a 90-obs warm-up."
  → STOPS. Waits.
User: "Approved."
Agent (Step 2): Lists functions, signatures, golden-value fixtures. → Waits for approval.
User: "Go."
Agent (Step 3): Implements components.py + tests.
Agent (Step 4): Runs `uv run --project api pytest api/tests/analytics/test_components.py -q`
  → 18 passed; prints live coverage table.
Agent (Step 5): What's Functional Now / What Was Tested / What You Can Test / Ready For RFC-003.
User: "Coverage table looks right." → RFC-002 ✅ VERIFIED.
```

---

## 2. Non-Goals and Constraints

**Non-goals**

- The insights text box and any scanning (build-order steps 2–4) — only the layout slot is reserved.
- Regime labels invented by this project. Only LiqTide's own label is shown, only on LiqTide's
  own line, marked as LiqTide's.
- Any marker, band, highlight or annotation on the charts (north-star Rule 1).
- Changing `build_reduced_composite`, `build_full_composite`, `leg_boundary.py` or the screener.
- Leg-boundary overlays on these panels (they belong on price charts per design principles).
- Equities, hosting, auth, notifications.

**Constraints**

- All maths in Python; TypeScript renders only.
- Every provider behind an adapter in `api/data/`; no provider name in a route or component
  (metadata strings like `source: "FRED WALCL"` are data, not code paths).
- Free, keyless sources only; attribution shown for LiqTide.
- Insufficient data → explicit state, never NaN, zero or interpolation. The only alignment allowed
  is as-of (value of the latest release on or before a date), and it is always labelled.
- Local only: API on `127.0.0.1:8000`, web on `localhost:3000`.
- Personal use; any Farside data use must be checked against its terms at Stage 0 and recorded
  in the adapter's redistribution flag.

---

## 3. Architecture Decisions (Final)

### ADR-1: Reproduce the six components from primaries; show LiqTide beside, not instead

**Decision**: compute every component's impulse in `api/analytics/regime/components.py` from
cached primary series. Show LiqTide's published tide index as a second, labelled line on the
composite panel for the dates where it exists.

**Rationale**: LiqTide's own history is ~2 years at best and our archive is 1 day; the spec needs
3+ years. The data-sources doc already names reproduction as the migration path. Showing both
lines makes disagreement visible instead of choosing for the user.

**Implications**: the reproduced composite is labelled "reproduced (this app)" and its
normalisation is documented in the drill-down; it is never presented as LiqTide's number.

### ADR-2: Source and depth per component

| # | Component | Weight | Transform | Source (adapter) | Expected earliest | Gap state |
|---|---|---|---|---|---|---|
| 1 | Net liquidity | 30% | 4-week change of WALCL − WDTGAL − RRPONTSYD×1000 on the Wednesday grid (amended at RFC-002: WDTGAL, the Wednesday level, matches LiqTide exactly; WTREGEN is a weekly average) | FRED (`fred_adapter.fetch_series`) | 2008-10 (RRP coverage) | — |
| 2 | Stablecoin supply | 25% | 7-day % change | DefiLlama (`defillama_adapter`) | 2017-11-29 | — |
| 3 | Broad dollar (inverted) | 15% | −1 × 1-month % change of DTWEXBGS | FRED (`fred_adapter`) | 2006 | — |
| 4 | ON-RRP release | 10% | −1 × 4-week change of RRPONTSYD (a falling RRP releases liquidity) | FRED (`fred_adapter`) | 2013 | — |
| 5 | Spot-ETF flows | 10% | 5-day sum of daily net flows | Farside (new adapter, RFC-003) — if Stage 0 clears it | 2024-01-11 | before launch: `not_applicable`; adapter blocked: `unavailable` |
| 6 | BTC dominance (inverted) | 10% | −1 × 30-day change | LiqTide `metrics.btc_dom.series` backfill + daily archive | ~2025-06 | before first point: `no_data` |

Source deviations from LiqTide's table are deliberate and shown in the drill-down: broad dollar
uses FRED DTWEXBGS (LiqTide uses Stooq); ON-RRP uses FRED RRPONTSYD (LiqTide uses the NY Fed
Markets API — the same underlying operation). Sign conventions for rows 3, 4 and 6 are confirmed
against LiqTide's published `tide_index.components` at RFC-002 Stage 0 before being fixed.

### ADR-3: Panel value = the impulse that enters the composite; raw level in readout + drill-down

**Decision**: each panel plots the transformed impulse (the thing the composite weights). The
hover readout and drill-down also show the raw level (e.g. net liquidity in $bn) and the
normalised −1..+1 contribution.

**Rationale**: the dashboard exists to see which component moves first before the composite
shifts; that comparison only works on the same quantities the composite uses. Raw levels stay one
hover away, so nothing is hidden.

**Open to user at VALIDATE**: if raw levels should be the plotted line instead, this is a
one-constant change in RFC-005 (the API returns both).

### ADR-4: Archive LiqTide's raw JSON daily and schedule the snapshot

**Decision**: add `cache/liqtide/raw/{date}.json` (append-only, git-tracked like the parquet
archive), written by `liqtide_adapter.fetch_latest` alongside the existing row. One-off backfill
from today's payload of `tide_series` and every `metrics.*.series` into
`cache/liqtide/backfill/{date}.parquet`. Schedule `snapshot_liqtide.py` daily at 03:00 Europe/Brussels
via Windows Task Scheduler (after LiqTide's ~22:45 UTC refresh). The scheduled snapshot is the
**only** path that fetches LiqTide; the endpoint and `components.py` read the archive only, because
`fetch_latest` is network-first (3 retries × 10 s) and would stall the page when LiqTide is slow
(VALIDATE P1).

**Rationale**: Standing Rule 8 — derived history is not recoverable later. Today only 7 fields are
kept per day and the published series/weights are thrown away.

**Implications**: `.gitignore` carve-out already covers `api/data/cache/liqtide/`; confirm the
`raw/` subfolder is included. Scheduling is a manual user step documented in the Ops Runbook
(no CI exists; local-only deployment).

### ADR-5: Reproduced composite — weights, normalisation, coverage

- Weights: 30/25/15/10/10/10 (LiqTide's published table).
- **Normalisation (amended 24-09-26, user-approved at RFC-002 Stage 0):** each component =
  `sign × tanh(impulse / scale)` — LiqTide's own (unpublished) formula, reverse-engineered from the
  2026-09-24 payload's `signals` and matching all six published components to 4 decimals. Scales:
  net liquidity $150bn, stablecoins 1%, dollar 2% (inverted), ON-RRP $75bn (inverted), ETF flows
  $1bn, BTC dominance 2pp (inverted). This replaces the earlier expanding-z-score assumption; the
  90-obs warm-up (VALIDATE P6) is no longer needed. Composite = 50 + 50 × Σ(wᵢ·xᵢ)/Σ(wᵢ present).
  Each component enters the composite only while its latest value is at most `fresh_days` old
  (FRED's H.4.1 and H.10 lag about a week). Re-checked daily by `check_component_reproduction.py`.
- Missing components: weights renormalised over present components; coverage % returned per date;
  dates below 60% coverage (reusing `AVAILABILITY_WEIGHT_THRESHOLD`'s value and rationale) return
  `unavailable`. Pre-2024 dates carry 80% coverage (no ETF, no BTC dominance) and are shown with
  that coverage stated.
- Implemented in the new module; the existing reduced/full composites are untouched.

### ADR-6: One endpoint, full history, metadata inline

`GET /api/regime/components` returns all seven series in one response (≈ 6 × 2,000 daily points —
well under 1 MB), plus per-series metadata. The frontend sets the default visible range to the last
3 years. LiqTide data comes from the archive only (no live call). FRED and DefiLlama go through
their existing cache-first adapters (6 h TTL); a failed refresh serves the cached series with
`status: "stale"`. The response also carries `grid_dates`, the union of all series' dates (ADR-7).

### ADR-7: Seven chart instances, synced by time range and crosshair

One `createChart` per panel (the `MiniChart` small-multiples pattern), synced with
`timeScale().subscribeVisibleTimeRangeChange` → `setVisibleRange` on the others, and
`subscribeCrosshairMove` → `setCrosshairPosition`. **Shared date grid (VALIDATE P3):**
lightweight-charts clamps a visible range to each chart's own data, so panels that start on
different dates (net liquidity 2002, BTC dominance ~2025) would drift apart. Every panel is fed the
same `grid_dates`; dates where a component has no value become whitespace points (`{ time }`, no
value) — visibly empty, never filled — so range and crosshair line up exactly. A single readout row above the stack shows the
hovered date's values. A reserved right-hand column (empty) holds the future insights text box so
adding it later does not reflow the charts.

---

## 5. High-level Data Flow

```
FRED fredgraph.csv ──► fred_adapter ──► cache/liquidity/{WALCL,WTREGEN,RRPONTSYD,DTWEXBGS}.parquet ─┐
DefiLlama ───────────► defillama_adapter ──► cache/liquidity/stablecoin_supply.parquet ─────────────┤
Farside (if cleared) ► etf_flows_adapter ──► cache/etf_flows/btc_spot.parquet ──────────────────────┤
LiqTide latest.json ─► liqtide_adapter ──► cache/liqtide/{date}.parquet (existing)                  │
                                     └───► cache/liqtide/raw/{date}.json (new, append-only)          │
                                     └───► cache/liqtide/backfill/{date}.parquet (one-off)  ─────────┤
                                                                                                    ▼
                                            analytics/regime/components.py
                                  (six impulses, normalised contributions, reproduced composite,
                                   LiqTide published index, coverage, agreement stats)
                                                                                                    │
                                              routers/regime.py  GET /api/regime/components ◄───────┘
                                                                                                    │
                                     web/lib/api/regime.ts ──► web/app/regime/page.tsx
                                     ──► RegimeDashboard (7 synced ComponentPanels + Readout + DrillDown)
```

---

## 6. Security Posture

Unchanged: API bound to `127.0.0.1`, CORS limited to `localhost:3000` (plus the E2E override).
No keys, no credentials, no user data. The Farside adapter (if built) sends a plain GET with a
descriptive User-Agent and respects its rate/robots rules recorded at Stage 0.

---

## 7. Component Details

### `api/analytics/regime/components.py` (new)

- **Responsibilities**: build each component's impulse series, raw level, normalised contribution;
  reproduced composite with coverage; LiqTide published index series; agreement stats over the
  overlap window (Pearson r, mean absolute difference, n days). Pure functions over DataFrames;
  one orchestrator `build_regime_components(date_range=None) -> RegimeComponentsResult`.
- **Key flows**: adapters → per-component calendar-window impulse → sign × tanh(impulse/scale) → weighted sum.
- **Future**: the insights engine reads `RegimeComponentsResult` directly (no second maths path).

### `api/data/etf_flows_adapter.py` (new, conditional)

- Same contract as other adapters: typed result, `status: ok | unavailable | stale`, never raises,
  cache-first with TTL, `redistributable: bool` recorded.

### `web/components/regime/RegimeDashboard.tsx` (new)

- Fetches once, owns sync state, lays out Readout + 7 `ComponentPanel`s + reserved insights column.

### `web/components/regime/ComponentPanel.tsx` (new)

- One `createChart`; header with name, weight, source, as-of, status; click header → `DrillDown`.
- Gap states rendered via `DeadDataNotice` with reasons `not_applicable | no_data | unavailable | stale`.

### `web/components/regime/Readout.tsx` (new)

- Row of seven cells: value, raw level, contribution, as-of date for the hovered date; last date
  when not hovering.

### `web/components/regime/DrillDown.tsx` (new)

- Calculation chain: source series IDs, transform formula, window, weight, first/last date, point
  count, last fetch time, status + reason; for the composite panel, coverage and agreement stats.

---

## 11. API Surface

### `GET /api/regime/components`

Query: `start` (ISO date, optional), `end` (ISO date, optional). Default: full history.

```json
{
  "generated_utc": "2026-09-24T18:00:00Z",
  "grid_dates": ["2002-12-18", "...", "2026-09-23"],
  "components": [
    {
      "id": "net_liquidity",
      "label": "Net liquidity (4-week change)",
      "weight": 0.30,
      "source": "FRED: WALCL − WDTGAL − RRPONTSYD×1000",
      "transform": "level(t) − level(t − 28 days); contribution = tanh(Δ / $150bn)",
      "frequency": "weekly (Wednesday, H.4.1)",
      "unit": "USD",
      "notes": [],
      "status": "ok",
      "reason": null,
      "first_date": "2002-12-18",
      "last_date": "2026-09-17",
      "last_fetched_utc": "2026-09-24T06:00:00Z",
      "points": [
        { "date": "2023-09-27", "value": -41200000000.0, "raw": 7102400000000.0, "contribution": -0.27 }
      ]
    }
  ],
  "composite": {
    "reproduced": {
      "label": "Reproduced tide index (this app)",
      "normalisation": "sign·tanh(impulse/scale); 50 + 50·Σw·x / Σw_present",
      "points": [ { "date": "2023-09-27", "value": 46.8, "coverage": 0.8 } ]
    },
    "published": {
      "label": "LiqTide tide index (published)",
      "attribution": "Data: LiqTide (liqtide.com)",
      "status": "ok",
      "points": [ { "date": "2024-09-02", "value": 52.0, "regime_label": "neutral" } ]
    },
    "agreement": { "overlap_days": 380, "pearson_r": 0.71, "mean_abs_diff": 6.4,
                   "full_coverage_days": 90, "full_coverage_mean_abs_diff": 2.1 }
  }
}
```

(Numbers above are illustrative shape only.) `status` per component ∈
`ok | stale | unavailable | not_applicable | no_data`; `points` never contains null or 0 as a
stand-in — dates without a value are simply absent and `reason` explains the gap range.

Status rules (RFC-004, see `components.status_for_range`): `not_applicable` when the requested
`end` is before the component's first possible date (ETF flows: 2024-01-11); with no ETF data at
all the status is `unavailable` (reason names the Farside status — RFC-003 merged: Farside primary, LiqTide archive fills gaps) and `notes` still say pre-launch
dates are not applicable. A component whose data exists but has no points inside the requested
window is `no_data`. `composite.published.status` is `ok` when it has points, else `unavailable`.
`start > end` or a malformed date → 422. `agreement` is whole-history (not window-filtered).
`last_fetched_utc` = newest cache-file write among the component's inputs (LiqTide-derived:
latest raw archive file); null only when nothing is cached. Responses are gzip-compressed when
the client accepts it.

---

## 12. Infrastructure Deployment

Local only. New scheduled task (user creates once, see Ops Runbook): Windows Task Scheduler,
daily 03:00, `uv run --project api python api/scripts/snapshot_liqtide.py`.

## 12b. Storage Schema (Parquet files)

| Path | Columns | Write mode |
|---|---|---|
| `cache/liqtide/raw/{date}.json` | full upstream JSON | append-only, never overwritten |
| `cache/liqtide/backfill/{date}.parquet` | `series_key, date, value` | written once per backfill run |
| `cache/etf_flows/btc_spot.parquet` | `date, net_flow_usd_m` | overwrite-merge (dedupe on date) |
| existing `cache/liqtide/{date}.parquet` | unchanged | unchanged |

---

## 13. Phased Delivery Plan

### Current Status

All RFCs ⏳ PLANNED. Nothing in `process/features/cycle-regime/` has started.

Each RFC below carries: Overview, Implementation Summary, Files, **Test Procedure**,
**Verification Queries**, **Done Criteria**, What's Functional Now, Ready For.

## 14. Features List (MoSCoW)

| ID | Feature | Priority |
|---|---|---|
| F-1 | Six component panels, synced time axis, 3y default | Must |
| F-2 | Composite panel: reproduced + LiqTide published lines | Must |
| F-3 | Hover readout with all values + as-of | Must |
| F-4 | Per-panel drill-down with calculation chain | Must |
| F-5 | Honest gap states (not_applicable / no_data / unavailable / stale) | Must |
| F-6 | Raw LiqTide archive + scheduled snapshot | Must |
| F-7 | Spot-ETF flows panel with real data | Should (depends on Stage 0) |
| F-8 | Agreement stats reproduced vs published | Should |
| F-9 | Reserved insights column | Should |
| F-10 | Keyboard zoom/pan shortcuts | Could |
| F-11 | Invented regime labels, markers, overlays | Won't |

---

## 15. RFCs

### RFC-001: LiqTide raw archive, history backfill + source research

**Summary**: stop losing LiqTide's derived output, recover whatever history today's payload
carries, and answer the source questions that gate RFC-002/003.
**Dependencies**: none.

**Stage 0: Pre-Phase Research** (present and STOP)
- Fetch one live payload with `fetch_latest(dry_run=True)`; report: which field is the 0–100
  index (`tide_index.value` vs `.score`), `tide_series` first date and point count, first date and
  frequency of every `metrics.*.series`, shape of `tide_index.components` (are they −1..+1?).
- Re-read LiqTide's methodology page for the normalisation function and component sign conventions.
- Farside: is there a stable table/CSV for spot BTC ETF daily flows, what do robots.txt and terms
  permit, how far back. Record verdict: `build | skip`.
- BTC dominance: re-check for any free, keyless daily history deeper than LiqTide's (record
  "none found" with what was checked if so).
- Confirm `.gitignore` negation covers `api/data/cache/liqtide/raw/`.

**Stages**
1. `cache.py`: `liqtide_raw_path(date)`, `write_liqtide_raw(date, raw)` (no-overwrite),
   `read_liqtide_raw(date)`.
2. `liqtide_adapter.fetch_latest`: when a fresh payload parses and `dry_run` is false, also write
   raw JSON. Existing parquet write unchanged.
3. `api/scripts/backfill_liqtide_series.py`: extract `tide_series` + `metrics.*.series` from the
   latest raw JSON into `backfill/{date}.parquet`; idempotent.
4. Ops Runbook entry for the Task Scheduler job; user creates it.

**Post-Phase Testing**
- Test file: `api/tests/data/test_liqtide_raw_archive.py` — raw written once; second write same
  date is a no-op; `dry_run` writes nothing; malformed payload writes nothing.
- Test file: `api/tests/scripts/test_backfill_liqtide_series.py` — synthetic payload → expected
  rows; missing series key → skipped, not zero.
- Run: `uv run --project api pytest api/ -q` — all green, no regressions vs 179 passed baseline.
- Manual: run `uv run --project api python api/scripts/snapshot_liqtide.py` twice; run backfill.
- Verification queries:
  ```
  uv run --project api python -c "import duckdb; print(duckdb.sql(\"select series_key, min(date), max(date), count(*) from 'api/data/cache/liqtide/backfill/*.parquet' group by 1\"))"
  ```
  and list `api/data/cache/liqtide/raw/`.
- Error scenarios: LiqTide down (no raw written, cached parquet path unchanged); disk file exists
  (not overwritten).

**Verification Checklist**
- [ ] Manual test passed
- [ ] Data in storage verified (query output pasted)
- [ ] Error handling confirmed
- [ ] User confirmed working (raw file appeared next morning via the scheduled task)

**Acceptance Criteria**: AC-1, AC-2 (see Acceptance Criteria).
**What's Functional Now**: every day's full LiqTide payload is kept; recoverable history is on disk.
**Ready For**: RFC-002.

**Implementation Checklist**
- [ ] Stage 0 findings presented; user approved
- [ ] Add raw archive helpers to `cache.py` + tests
- [ ] Wire raw write into `fetch_latest` + tests
- [ ] Add `backfill_liqtide_series.py` + tests
- [ ] `uv run --project api pytest api/ -q` green
- [ ] Task Scheduler job created by user; next-day file confirmed

### RFC-002: Component maths (six impulses + reproduced composite)

**Summary**: new `analytics/regime/components.py` implementing ADR-2/3/5.
**Dependencies**: RFC-001 (field semantics, sign conventions, btc_dom backfill).

**Stage 0**: read `liquidity_composite.py` transforms and `_zscore`; confirm frequency and
business-day row structure of each input; present proposed signatures, the calendar-window helper
and normalisation. STOP.

**Stages**
1. Per-component builders returning `DataFrame[date, value, raw]` + metadata. Every window is a
   **calendar** window: change = value(date) − value as of (date − N calendar days) via
   `merge_asof(direction="backward")`, never `pct_change(periods=N)` on business-day rows
   (VALIDATE P4). Net liquidity reuses `fred_adapter.fetch_net_liquidity`'s as-of daily series,
   labelled as such (P5); no other fill.
2. Normalisation (sign × tanh(impulse/scale), ADR-5 as amended) → `contribution`.
3. Reproduced composite with coverage and 60% floor.
4. Published index series from backfill + daily archive (the field chosen at RFC-001 Stage 0).
5. Agreement stats over overlap.
6. ETF component reads the RFC-003 adapter if present; otherwise returns `unavailable` with the
   Stage 0 reason; pre-2024-01-11 is `not_applicable` regardless.

**Post-Phase Testing**
- Test file: `api/tests/analytics/test_components.py` — golden values on hand-computed synthetic
  series for each transform and sign; calendar windows correct across a business-day fixture with
  a holiday gap; no fill beyond labelled as-of alignment; 90-obs warm-up; coverage/renormalisation;
  60% floor → unavailable; clip at ±3; no NaN/0 in outputs; ETF `not_applicable` before launch.
- Hybrid gate: for each date in the raw archive, compare our per-component contribution sign with
  LiqTide's `tide_index.components`; report matches/mismatches (not asserted to be equal).
- Run: `uv run --project api pytest api/tests/analytics/test_components.py -q`, then full suite.
- Verification query: a script prints the coverage table (component, first_date, last_date,
  n_points, gaps) from the live cache.

**Verification Checklist**
- [ ] Manual test passed (coverage table reviewed)
- [ ] Data verified (table pasted into report)
- [ ] Error handling confirmed (one adapter forced unavailable → component `unavailable`, composite coverage drops)
- [ ] User confirmed working

**Acceptance Criteria**: AC-3, AC-4, AC-5.
**What's Functional Now**: all six components and both composite lines computable from cache.
**Ready For**: RFC-003 (or RFC-004 if Farside verdict was `skip`).

**Implementation Checklist**
- [ ] Stage 0 findings presented; user approved
- [ ] Component builders + golden tests
- [ ] Normalisation + tests
- [ ] Reproduced composite + coverage + tests
- [ ] Published series + agreement stats + tests
- [ ] Hybrid sign cross-check run and reported
- [ ] Full `pytest` green; `leg_boundary`/`liquidity_composite` tests unchanged and green

### RFC-003: Spot-ETF flows adapter (conditional)

**Summary**: build `api/data/etf_flows_adapter.py` only if RFC-001 Stage 0 verdict is `build`.
If `skip`, mark this RFC ✅ VERIFIED-as-skipped with user confirmation and the reason recorded.
**Dependencies**: RFC-001 verdict.

**Stages**: fetch with backoff → parse → cache merge → typed result with `redistributable=false`
unless terms say otherwise → wire into RFC-002's ETF builder.

**Post-Phase Testing**
- `api/tests/data/test_etf_flows_adapter.py` — fixture parse, malformed row skipped, timeout →
  `unavailable`, cache fallback → `stale`.
- Integration (opt-in): `uv run --project api pytest api/ -m integration -k etf`.
- Verification query: DuckDB `select min(date), max(date), count(*) from 'api/data/cache/etf_flows/btc_spot.parquet'`.

**Verification Checklist**
- [x] Manual test passed (one live request, `ok`, 677 rows — 24-09-26)
- [x] Data verified (DuckDB: min 2024-01-11, max 2026-09-23, 677; only US holidays + today missing)
- [x] Error handling confirmed (timeout/challenge/layout → `unavailable`, cache → `stale` in tests; real bad-URL run → `unavailable`)
- [ ] User confirmed working

**Acceptance Criteria**: AC-6.
**Ready For**: RFC-004.

### RFC-004: `GET /api/regime/components`

**Summary**: Pydantic models + router endpoint per §11.
**Dependencies**: RFC-002 (RFC-003 optional).

**Stages**: models in `api/models/regime.py` (additive) → route in `routers/regime.py` (additive;
`/legs` unchanged; no call to `liqtide_adapter.fetch_latest` — test asserts it) → `start`/`end` filtering → stale/unavailable passthrough.

**Post-Phase Testing**
- `api/tests/routers/test_regime_components.py` — shape, no null/0 stand-ins, date filtering,
  one adapter down → 200 with that component `unavailable`, `/legs` still returns its old shape.
  Use `fastapi.testclient.TestClient` if installable (the sandbox note in `test_regime.py`
  documents the fallback).
- Manual: `uv run --project api uvicorn api.main:app --host 127.0.0.1 --port 8000`, then
  `curl "http://127.0.0.1:8000/api/regime/components" | python -m json.tool | head -80`.
- Verification: point counts and first dates in the response match the RFC-002 coverage table.
- Timing: response time on warm cache recorded (target < 1 s).

**Verification Checklist**
- [ ] Manual test passed
- [ ] Data verified (counts match)
- [ ] Error handling confirmed
- [ ] User confirmed working

**Acceptance Criteria**: AC-7.
**Ready For**: RFC-005.

**RFC-004 Stage 0 decisions (user, 24-09-26):**
1. `not_applicable` is a real status; ETF is `not_applicable` when `end` < 2024-01-11, else
   `unavailable` (RFC-003 not built) with notes stating pre-launch dates are not applicable.
2. `last_fetched_utc` per component = newest cache mtime of its inputs, computed at serialization.
3. `composite.agreement` includes `full_coverage_days` and `full_coverage_mean_abs_diff`.
4. Published status `ok`/`unavailable`; attribution "Data: LiqTide (liqtide.com)"; `label` →
   `regime_label`; reproduced label + normalisation strings fixed.
5. `GZipMiddleware(minimum_size=1000)` in `api/main.py`.
6. §11 example updated to match code (WDTGAL, weekly H.4.1, real transform, extra fields).

RFC-003 status at this point: not started — user chose to proceed to RFC-004 first (not skipped).
Report: `regime-dashboard_24-09-26-RFC-004-phase-report.md`.

### RFC-005: `/regime` page

**Summary**: ADR-7 layout and behaviour.
**Dependencies**: RFC-004.

**Stage 0**: read `MiniChart.tsx`, `RelativePerformanceChart.tsx`, `DeadDataNotice`; confirm the
lightweight-charts v5 sync APIs against the installed version; present. STOP.

**Stages**
1. `web/lib/types/regime.ts`, `web/lib/api/regime.ts` (reuse `getJson` pattern).
2. `ComponentPanel` (one chart, header, gap notice, click → drill-down).
3. `RegimeDashboard` (fetch once, range + crosshair sync, default 3y range, reserved column).
   Every panel's series is built on the shared `grid_dates` with whitespace points for missing
   dates. Prove sync on two panels with different first dates before building all seven (E3).
4. `Readout`, `DrillDown`.
5. `web/app/regime/page.tsx`; link from `web/app/page.tsx`.

**Post-Phase Testing**
- vitest files under `web/components/regime/__tests__/`: panels render one per component; gap
  reasons render text; drill-down lists source/transform/weight; readout shows last date when not
  hovering; injected fetcher error → `DeadDataNotice`; exactly seven `createChart` calls; every
  panel receives `grid_dates.length` points (whitespace where no value); sync subscriptions wired
  and unsubscribed on unmount. The `lightweight-charts` vi.mock gains `timeScale()` with
  `subscribeVisibleTimeRangeChange`/`unsubscribeVisibleTimeRangeChange`/`setVisibleRange` and
  `subscribeCrosshairMove`/`unsubscribeCrosshairMove`/`setCrosshairPosition`.
- Run: `pnpm --filter web test` (the known `e2e/` collection noise is not a regression).
- Manual: open `http://localhost:3000/regime`; confirm 3y default; zoom one panel → all follow;
  hover → readout updates; click two headers → drill-downs correct; ETF panel shows
  "not applicable before 2024-01-11"; BTC dominance shows its first-data date.
- Error scenario: stop the API → page shows a clear notice, no blank charts.

**Verification Checklist**
- [ ] Manual test passed
- [ ] Data verified (readout values spot-checked against curl for 3 dates)
- [ ] Error handling confirmed
- [ ] User confirmed working

**Acceptance Criteria**: AC-8, AC-9, AC-10.
**Ready For**: RFC-006.

**RFC-005 decisions (user-approved at Stage 0, 24-09-26; implemented):**
1. Panels plot the impulse (`value`); raw level + contribution shown in the readout and drill-down.
2. Composite = 7th panel: one chart, two labelled lines ("Reproduced tide index (this app)",
   "LiqTide tide index (published)") plus "Data: LiqTide (liqtide.com)". LiqTide's `regime_label`
   appears only in the readout cell / drill-down for the published line, marked as LiqTide's.
3. Readout: one row above the stack, 8 cells; value, raw level + contribution (components),
   coverage (reproduced), date. Not hovering → latest grid date. Whitespace → "no value", never 0.
4. Drill-down reuses `DrillDownView`'s inline `role="dialog"` + Close pattern; composite drill-down
   shows normalisation, coverage rule and all five agreement stats.
5. Default visible range = last 3 calendar years before the last grid date (logical index range).
6. Value formatting via `web/lib/format-regime-value.ts`, driven by each component's `unit`.
7. Reserved right column: fixed 280px grid column, empty, `aria-hidden`.
8. Screener's hard-coded palette; no theme toggle.
Sync is LOGICAL-range (`subscribeVisibleLogicalRangeChange` / `setVisibleLogicalRange`) rather than
the time-range calls named in ADR-7 — exact on the shared grid, see the RFC-005 phase report.

### RFC-006: End-to-end proof + user walkthrough

**Summary**: prove the real frontend/backend boundary, per the all-tests "green ≠ verified" lesson.
**Dependencies**: RFC-005.

**Stages**: extend `api/scripts/seed_e2e_cache.py` with synthetic FRED (WALCL, WTREGEN, RRPONTSYD,
DTWEXBGS), DefiLlama, LiqTide archive row + raw JSON and (if built) ETF fixtures, written through the
same `cache.write_*` functions the adapters use and with a fresh mtime inside the 6 h TTL so the API
never reaches the network (VALIDATE P8) → `web/e2e/regime.spec.ts` → user walkthrough.

**Post-Phase Testing**
- `cd web && pnpm test:e2e` — new spec: seven panels render from a real request; after a zoom on
  one panel all seven report the same visible time range; one seeded gap shows its reason. Existing screener spec unaffected (the backlogged cold-start flake
  is known; see `board-endpoint-cold-start-latency_20-09-26.md`).
- Walkthrough checklist run by the user against the real cache (design-principles checklist).

**Verification Checklist**
- [ ] E2E green
- [ ] Data verified against real cache
- [ ] Error handling confirmed
- [ ] User confirmed working

**Acceptance Criteria**: AC-11.
**What's Functional Now**: the regime dashboard, end to end.

---

## 16. Rules (for this project)

- Python owns all numbers; the frontend formats but never computes.
- No interpolation or zero-fill; the only alignment is as-of (latest release on or before a date), always labelled.
- Every window is a calendar window, never a row count.
- Every value carries its source and as-of; every gap carries a reason.
- Nothing drawn on charts except the series themselves and the crosshair.
- No change to layout based on data or behaviour; panel order is fixed (ADR-2 order).
- New adapters follow the typed-result, never-raise, cache-first pattern.

## 17. Verification (Comprehensive Review)

### Gap Analysis

- BTC dominance depth (~2025-06) is a hard free-data limit; the panel will be short. Accepted and
  shown honestly; revisit if a free source appears.
- ETF flows depend on Farside being usable; the plan is complete either way (RFC-003 conditional).
- The reproduced composite's normalisation is an assumption until LiqTide publishes theirs; the
  agreement stats make any drift visible.
- The scheduled snapshot depends on the PC being on at 03:00; Task Scheduler "run as soon as
  possible after a missed start" must be ticked.

### Quality Assessment

| Dimension | Score | Reason |
|---|---|---|
| Fit to north-star | 9/10 | Pure data layer; no calls, no overlays, no user learning |
| Data honesty | 9/10 | Every gap typed; reproduction labelled; agreement shown |
| Risk | 7/10 | Two external unknowns (Farside, LiqTide field semantics) gated at Stage 0 |
| Testability | 8/10 | Golden values + Hybrid cross-check + E2E |

## 18. Change Management

Any scope change mid-flight: classify (New / Modify / Remove / Scope / Technical / Timeline),
list impacted RFCs and files, choose immediate / schedule / defer, update this plan's ADRs and
Status Strip, then continue. Most likely triggers: Farside verdict flips; user prefers raw levels
as the plotted line (ADR-3); LiqTide changes its payload.

## 19. Ops Runbook

- **Daily snapshot**: Task Scheduler → Create Task → trigger daily 03:00 → action: the
  **absolute path** to `uv.exe` (find it with `where uv`; Task Scheduler does not use your shell's
  PATH), args `run --project api python api/scripts/snapshot_liqtide.py`, "Start in" = repo root → Settings: "Run task as soon as possible after a scheduled start is missed".
- **Check archive health**: `uv run --project api python api/scripts/snapshot_liqtide.py --coverage`.
- **Refresh primaries**: `uv run --project api python api/scripts/backfill_primaries.py`.
- **Start app**: API `uv run --project api uvicorn api.main:app --host 127.0.0.1 --port 8000`;
  web `pnpm --filter web dev`; open `http://localhost:3000/regime`.

## 20. Acceptance Criteria (Versioned)

### V1.0

- **AC-1** Each day's LiqTide payload is saved as raw JSON exactly once; re-runs never overwrite.
- **AC-2** History carried in today's payload (`tide_series`, `metrics.*.series`) is on disk with
  first/last dates reported.
- **AC-3** All six component impulses match hand-computed golden values on synthetic inputs.
- **AC-4** No output contains NaN, null or 0 as a stand-in; no fill beyond labelled as-of alignment; windows are calendar-based.
- **AC-5** Reproduced composite reports coverage per date and is `unavailable` below 60%.
- **AC-6** ETF flows are real data from 2024-01-11 if Farside cleared, else `unavailable` with the
  recorded reason; before 2024-01-11 always `not_applicable`.
- **AC-7** `GET /api/regime/components` returns the §11 shape; one failed source degrades only its
  component; `/api/regime/legs` is unchanged.
- **AC-8** `/regime` shows seven panels, 3 years visible by default, zoom and crosshair synced.
- **AC-9** Hover readout shows all seven values with as-of dates; drill-down shows the full chain.
- **AC-10** Every gap renders a readable reason; nothing is drawn on charts beyond the series.
- **AC-11** Playwright proves the real boundary; user completes the walkthrough and confirms.

## 21. Future Work

- Insights text box in the reserved column (build-order step 2) reading `RegimeComponentsResult`.
- Divergence and lead/lag scans over these components (build-order step 3).
- Swap LiqTide btc_dom for a deeper free source if one appears.
- Revisit Stooq DXY vs FRED DTWEXBGS if the user wants LiqTide's exact dollar input.

---

## Touchpoints

| Area | Files | Change |
|---|---|---|
| API data | `api/data/cache.py` | add raw-archive helpers (additive) |
| API data | `api/data/liqtide_adapter.py` | write raw JSON on fresh fetch (additive) |
| API data | `api/data/etf_flows_adapter.py` | new (conditional) |
| API analytics | `api/analytics/regime/components.py` | new |
| API models/router | `api/models/regime.py`, `api/routers/regime.py` | additive models + route |
| API scripts | `api/scripts/backfill_liqtide_series.py` (new), `api/scripts/seed_e2e_cache.py` (extend) | |
| API tests | `api/tests/data/test_liqtide_raw_archive.py`, `api/tests/scripts/test_backfill_liqtide_series.py`, `api/tests/analytics/test_components.py`, `api/tests/data/test_etf_flows_adapter.py`, `api/tests/routers/test_regime_components.py` | new |
| Web | `web/lib/types/regime.ts`, `web/lib/api/regime.ts`, `web/components/regime/*`, `web/app/regime/page.tsx`, `web/app/page.tsx` (link) | new + one-line link |
| Web tests | `web/components/regime/__tests__/*`, `web/e2e/regime.spec.ts` | new |
| Cache | `api/data/cache/liqtide/raw/`, `backfill/*.parquet`, `api/data/cache/etf_flows/` | new data |
| Context | `process/features/cycle-regime/_GUIDE.md`, `process/context/all-context.md`, `all-data-sources.md`, `all-tests.md` | UPDATE PROCESS after EXECUTE |

Read-only: `liquidity_composite.py`, `leg_boundary.py`, `fred_adapter.py`, `defillama_adapter.py`,
`MiniChart.tsx`, `RelativePerformanceChart.tsx`, `DeadDataNotice.tsx`.

## Public Contracts

- **New**: `GET /api/regime/components` (§11 shape); `RegimeComponentsResult` Python dataclass;
  `etf_flows_adapter.fetch_btc_spot_flows()` typed result.
- **Extended, backward-compatible**: `liqtide_adapter.fetch_latest` gains a raw-JSON side effect
  (not on `dry_run`); return type unchanged. `cache.py` gains functions only.
- **Must stay identical**: `GET /api/regime/legs` response, `LegBoundaryResponse`,
  `CurrentLegState`, `build_reduced_composite`, `build_full_composite`, `select_composite_variant`,
  all screener endpoints.

## Blast Radius

- ~20 new files, 5 modified files (all additive), across `api/` and `web/`.
- Risk class: **low-medium**. Low for existing features (additive only, leg path untouched);
  medium for new external dependency (Farside) and LiqTide payload assumptions — both gated at
  RFC-001 Stage 0 and isolated behind adapters.
- Regression guard: full `pytest` and `vitest` suites plus existing Playwright screener spec run
  at RFC-004, RFC-005 and RFC-006.

## Verification Evidence

| Gate / Scenario | Strategy | Proves SPEC criterion |
|---|---|---|
| Raw archive write-once + dry-run no-write (`test_liqtide_raw_archive.py`) | Fully-Automated | AC-1 |
| Next-morning raw file from scheduled task | Agent-Probe (user checks folder) | AC-1 |
| Backfill extraction (`test_backfill_liqtide_series.py`) + DuckDB coverage query | Hybrid | AC-2 |
| Golden values per transform (`test_components.py`) | Fully-Automated | AC-3 |
| No NaN/0 stand-ins, calendar windows, as-of only (`test_components.py`) | Fully-Automated | AC-4 |
| Coverage + 60% floor (`test_components.py`) | Fully-Automated | AC-5 |
| Sign cross-check vs LiqTide `tide_index.components` | Hybrid | AC-3 (sign conventions) |
| ETF adapter fixtures + opt-in integration | Hybrid | AC-6 |
| Endpoint shape/degradation/`/legs` unchanged (`test_regime_components.py`) | Fully-Automated | AC-7 |
| curl counts vs coverage table | Agent-Probe | AC-7 |
| vitest regime components | Fully-Automated | AC-8, AC-9, AC-10 |
| Manual zoom/hover/drill-down on real cache | Agent-Probe (user) | AC-8, AC-9, AC-10 |
| Playwright `regime.spec.ts` on seeded cache | Fully-Automated | AC-11 |
| User walkthrough (design-principles checklist) | Agent-Probe (user) | AC-11 |

Commands and runners per `process/context/tests/all-tests.md`:
`uv run --project api pytest api/ -q` · `pnpm --filter web test` · `cd web && pnpm test:e2e`.

## Test Infra Improvement Notes

(none identified yet)

## Resume and Execution Handoff

1. **Selected plan file**: `process/features/cycle-regime/active/regime-dashboard_24-09-26/regime-dashboard_PLAN_24-09-26.md`
2. **Last completed phase or step**: VALIDATE complete 24-09-26 (CONDITIONAL, accepted); no RFC started.
3. **Validate-contract status**: written 24-09-26 — CONDITIONAL, see `## Validate Contract` and
   `regime-dashboard-validate_REPORT_24-09-26.md` in this folder.
4. **Supporting context files loaded**: `process/context/all-context.md`,
   `process/context/data-sources/all-data-sources.md`, `process/context/tests/all-tests.md`,
   `process/features/cycle-regime/_GUIDE.md`, plus the code files listed under 1. Context and Goals.
5. **Next step for a fresh agent**: RFC-001 is 🔨 CODE DONE. Read
   `regime-dashboard-rfc001-stage0_REPORT_24-09-26.md` and `regime-dashboard_24-09-26-RFC-001-phase-report.md`
   in this folder. Wait for the user's Step 4 outputs (pytest, snapshot ×2, backfill, next-morning
   raw file); mark ✅ VERIFIED only on user confirmation, then start RFC-002 Stage 0.

**Snapshot scheduling (found 24-09-26 while committing):** a GitHub Actions workflow
(`.github/workflows/liqtide-snapshot.yml`, daily 23:30 UTC) already runs `snapshot_liqtide.py`
and commits `api/data/cache/liqtide/` — it captured 09-21 … 09-24. With this commit it will also
archive the raw JSON. The Windows Task Scheduler job in the Ops Runbook is therefore **not
needed**; pull before working locally, since the workflow pushes to `main` daily.

**RFC-002 (24-09-26):** 🔨 CODE DONE — see `regime-dashboard-rfc002-stage0_REPORT_24-09-26.md` and
`regime-dashboard_24-09-26-RFC-002-phase-report.md`. Next: user confirms, then RFC-003 (Farside probe).

**RFC-003 (24-09-26):** 🔨 CODE DONE — see `regime-dashboard_24-09-26-RFC-003-phase-report.md`.
`api/data/etf_flows_adapter.py` (stdlib `html.parser`, `redistributable=false`, at most one request
per UTC day) feeds `components.build_etf_flows` (Farside first, LiqTide archive fills gaps). Next:
user confirms (optionally runs `uv run --project api pytest api/ -m integration -k etf`), then RFC-004.

**RFC-004 (24-09-26):** 🔨 CODE DONE — see `regime-dashboard_24-09-26-RFC-004-phase-report.md`.
RFC-003 was built in a parallel session (see above). Next: user runs the RFC-004 checks on
the PC (pytest + curl with a populated FRED/DefiLlama cache), then RFC-005 (`/regime` page).

**RFC-005 (24-09-26):** 🔨 CODE DONE — see `regime-dashboard_24-09-26-RFC-005-phase-report.md`.
Next: user runs the RFC-005 PC checklist (zoom/hover/drill-down/stop-API) with a populated cache;
then RFC-006 (end-to-end proof, incl. `web/e2e/regime.spec.ts`).

**RFC-001 Stage 0 decisions (user, 24-09-26):** Farside = build, personal use only
(`redistributable=false`, probe first in RFC-003); snapshot at 03:00 Brussels; archive row gains
`tide_value` + `tide_label`. Deviation: backfill lives in `cache/liqtide/backfill/` (not beside the
daily rows) because `read_liqtide_history` globs `liqtide/*.parquet`.

Reports for each RFC go in this same task folder as
`regime-dashboard_24-09-26-RFC-00N-phase-report.md`.

## Validate Contract

Status: CONDITIONAL
Date: 24-09-26
date: 2026-09-24
generated-by: outer-pvl

Parallel strategy: sequential
Rationale: 6 strictly dependent RFCs, 2 packages, no independent workstreams; dominant signal = sequential dependency (each RFC needs the previous Stage 0 or outputs).

Test gates (C3 5-column table):

| criterion id | behavior | strategy | proving test | gap-resolution |
|---|---|---|---|---|
| AC-1 | raw JSON written once, never overwritten, skipped on dry run | Fully-Automated | `api/tests/data/test_liqtide_raw_archive.py` | B |
| AC-1 | scheduled task produces next-day file | Agent-Probe | user lists `api/data/cache/liqtide/raw/` next morning | A |
| AC-2 | payload history extracted to backfill parquet | Hybrid | `api/tests/scripts/test_backfill_liqtide_series.py` + DuckDB coverage query on live payload | B |
| AC-3 | six transforms match golden values with calendar windows | Fully-Automated | `api/tests/analytics/test_components.py` | B |
| AC-3 | sign conventions match LiqTide published components | Hybrid | sign cross-check over archived raw payloads | B |
| AC-4 | no NaN/0 stand-ins; as-of alignment only, labelled | Fully-Automated | `api/tests/analytics/test_components.py` | B |
| AC-5 | coverage, 60% floor, 90-obs warm-up | Fully-Automated | `api/tests/analytics/test_components.py` | B |
| AC-6 | ETF flows parse and degrade honestly | Hybrid | `api/tests/data/test_etf_flows_adapter.py` + `uv run --project api pytest api/ -m integration -k etf` | B |
| AC-7 | endpoint shape, degradation, `/legs` unchanged, no live LiqTide call | Fully-Automated | `api/tests/routers/test_regime_components.py` | B |
| AC-8/9/10 | panels, readout, drill-down, gap text, grid padding, sync wiring | Fully-Automated | `pnpm --filter web test` (`web/components/regime/__tests__/*`) | B |
| AC-8 | seven panels share one visible range after zoom | Fully-Automated | `cd web && pnpm test:e2e` (`web/e2e/regime.spec.ts`) | B |
| AC-11 | real-cache walkthrough | Agent-Probe | user walkthrough (design-principles checklist) | A |

Failing stubs (Fully-Automated rows; replace during EXECUTE):

```python
def test_raw_archive_write_once_and_dry_run_skips(): raise NotImplementedError("TDD stub: raw JSON written once, never overwritten, skipped on dry run")
def test_components_golden_values_calendar_windows(): raise NotImplementedError("TDD stub: six transforms match golden values with calendar windows")
def test_components_no_standins_asof_only(): raise NotImplementedError("TDD stub: no NaN/0 stand-ins; as-of alignment only")
def test_composite_coverage_floor_and_warmup(): raise NotImplementedError("TDD stub: coverage, 60% floor, 90-obs warm-up")
def test_components_endpoint_shape_and_no_live_liqtide(): raise NotImplementedError("TDD stub: endpoint shape, degradation, /legs unchanged, no live LiqTide call")
```

```ts
test("should render seven panels on the shared grid with sync wired", () => { throw new Error("NOT IMPLEMENTED — TDD stub: panels, readout, drill-down, gap text, grid padding, sync wiring") });
test("should keep all seven panels on one visible range after zoom", () => { throw new Error("NOT IMPLEMENTED — TDD stub: E2E synced range") });
```

Legacy line form:
- LiqTide archive: Fully-automated: `uv run --project api pytest api/tests/data/test_liqtide_raw_archive.py -q` | agent-probe: next-day raw file
- Component maths: Fully-automated: `uv run --project api pytest api/tests/analytics/test_components.py -q` | hybrid: sign cross-check vs LiqTide components
- ETF flows: hybrid: `uv run --project api pytest api/ -m integration -k etf` + fixture tests
- Endpoint: Fully-automated: `uv run --project api pytest api/tests/routers/test_regime_components.py -q`
- Frontend: Fully-automated: `pnpm --filter web test` | Fully-automated: `cd web && pnpm test:e2e` | agent-probe: user walkthrough

Dimension findings:
- Infra fit: CONCERN — `fetch_latest` is network-first; endpoint now archive-only (P1); Task Scheduler uses absolute `uv.exe` path (P2); cold-start timing recorded (E1)
- Test coverage: CONCERN — `isolated_cache` is opt-in, raw write must not reach the live tracked archive (E2); vitest mock extended for sync APIs (P3)
- Breaking changes: PASS — all changes additive; `/api/regime/legs` and both existing composites untouched
- Security surface: PASS — no keys, local bind unchanged; Farside terms gated at RFC-001 Stage 0; fredapi (would add a key) not adopted
- RFC-001 feasibility: CONCERN — live payload shape is a feasibility probe (kept as Stage 0); opportunistic endpoint fetch removed
- RFC-002 feasibility: CONCERN — row-count windows on business-day rows (P4), as-of net liquidity reused and labelled (P5), 90-obs warm-up (P6)
- RFC-003 feasibility: PASS — gated on Stage 0 verdict
- RFC-004 feasibility: CONCERN — archive-only LiqTide read (P1), cold/warm timing (E1)
- RFC-005 feasibility: CONCERN — range clamping across different first dates; shared `grid_dates` + whitespace points (P3), prove on two panels first (E3)
- RFC-006 feasibility: CONCERN — seeder must write fresh liquidity/LiqTide fixtures via `cache.write_*` (P8)

Execute-agent instructions:
- E1: record cold and warm response time for `/api/regime/components`; if cold > 10 s, append to `process/general-plans/backlog/board-endpoint-cold-start-latency_20-09-26.md`, do not block (RFC-004 Step 4)
- E2: grep `api/tests` for `fetch_latest` / `write_liqtide` callers; each must use `isolated_cache` before the raw write is wired (RFC-001 Step 3 entry)
- E3: prove range + crosshair sync on two panels with different first dates before building all seven (RFC-005 Stage 0)

Open gaps:
- Existing `liquidity_composite._roc` row-count windows: known-gap: documented as NEW PLAN REQUIRED — see backlog/liquidity-composite-calendar-windows_24-09-26.md
- Point-in-time FRED (ALFRED) data for insights backtests: known-gap: documented as NEW PLAN REQUIRED — see process/features/cycle-regime/backlog/fredapi-alfred-vintages_24-09-26.md

What this coverage does NOT prove:
- Raw archive tests: not that LiqTide keeps its payload shape; not that the PC is on at 03:00 (Agent-Probe only)
- Component golden tests: not that our normalisation equals LiqTide's (unpublished) — only sign agreement and published-vs-reproduced stats
- ETF tests: not Farside availability beyond the day of the integration run
- Endpoint tests: not cold-cache latency on the user's network (E1 records it)
- vitest: not real canvas rendering or real sync behaviour (jsdom mock)
- Playwright: seeded synthetic data only; real-data correctness rests on the user walkthrough

Gate: CONDITIONAL (concerns noted, user accepted)
Accepted by: user (Jamiro), 24-09-26 — accepted concerns: P1 archive-only LiqTide read; P2 absolute uv path; P3 shared date grid; P4 calendar windows; P5 as-of net liquidity; P6 90-obs warm-up; P8 E2E seeding; E1–E3 execute instructions; two backlog known-gaps

## Autonomous Goal Block

```
SESSION GOAL: Build the /regime dashboard per process/features/cycle-regime/active/regime-dashboard_24-09-26/regime-dashboard_PLAN_24-09-26.md — six liquidity components + reproduced and published tide index on one synced, shared-grid time axis, 3y default, every value drillable, gaps labelled, nothing drawn on charts.
AUTONOMY RULES: Execute one RFC at a time in order RFC-001..RFC-006. Each RFC: Stage 0 research -> present findings -> STOP for user approval -> implement -> run the RFC's test stage -> phase report in the task folder -> STOP for user confirmation. Follow Validate Contract execute instructions E1-E3. Tests that touch the cache must use the isolated_cache fixture.
HARD STOPS: any change to leg_boundary.py, build_reduced_composite, build_full_composite or /api/regime/legs; any live LiqTide call outside snapshot_liqtide.py; any API key; any write into api/data/cache/ from tests; Farside use before the Stage 0 terms verdict; any marker/overlay/label drawn on charts; any failing test left red.
NEXT PHASE: RFC-001 Stage 0 only (live payload inspection with dry_run=True, methodology re-read, Farside and BTC-dominance source checks).
CONTRACT SUMMARY: CONDITIONAL, 0 blocking, 7 concerns folded into plan (P1-P8) + E1-E3; 2 backlog known-gaps.
EXECUTE START: ENTER EXECUTE MODE for RFC-001 Stage 0 of regime-dashboard_PLAN_24-09-26.md
Reference for latest state: process/features/cycle-regime/active/regime-dashboard_24-09-26/regime-dashboard_PLAN_24-09-26.md
```

---

## Cursor + RIPER-5 Guidance

- **Cursor Plan mode**: import each RFC's Implementation Checklist; execute one RFC at a time;
  after each, update the Status Strip and "What's Functional Now". **After each phase, run the
  verification checklist before proceeding.**
- **RIPER-5**: RESEARCH → INNOVATE → PLAN (this file) → VALIDATE → EXECUTE one RFC → VERIFY →
  REVIEW. If scope changes, run Change Management and update this file first.

**Next Step**: VALIDATE done (CONDITIONAL, accepted). ENTER EXECUTE MODE for **RFC-001
Stage 0 only**. Each phase requires verification and user confirmation before the next begins.
