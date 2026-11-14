---
name: plan:btc-momentum-signals
description: "Single-stream standard-complex plan for daily BTC momentum markers on the existing BTC legs chart."
date: 02-11-26
feature: charting-indicators
metadata:
  node_type: plan
  type: implementation-plan
---
# BTC Momentum Signals — PLAN (02-11-26)

**Date**: 02-11-26  
**Complexity**: Complex — standard single execution stream (not a phase program)  
**Status**: ⏳ PLANNED — plan only; EXECUTE not authorized  
**Execution model:** One coherent RFC implementation spanning Python API and React/Svelte chart rendering, followed by integrated verification.

## Overview

Add BUY/SELL event markers to the existing BTC daily legs price chart, using the approved `Segment Momentum (3 Votes)` model and completed UTC daily closes. The FastAPI response will add typed signal data computed in Python from the endpoint's existing BTC bars; the chart will render each point at its signal candle's timestamp and close without changing existing price, leg bands, boundary markers, estimate, or readouts. This is intentionally one bounded feature and one authoritative plan. The user's daily-only decision explicitly defers SPEC AC7's non-daily chart clause; no timeframe control or generic multi-timeframe behavior is included. This is the user-authorized D-2 exception for this BTC chart only, not a general permission for generated calls or trading functionality.

## Quick Links

- [Context and goals](#1-context-and-goals)
- [Execution brief](#2-execution-brief)
- [Scope and decisions](#3-scope-and-final-implementation-choices)
- [Contracts and touchpoints](#4-touchpoints)
- [Checklist and gates](#5-implementation-checklist)
- [Verification evidence](#6-verification-evidence)
- [Risks and handoff](#7-risks-and-mitigations)
- [Validate Contract](#validate-contract)

## 1. Context and Goals

The BTC legs panel already receives daily BTC closes from `GET /api/regime/btc-legs`. Add visual-only signals from that same data path. All numerical computation remains in Python, chart code renders only the response, and existing legs visualization/readouts/estimate are preserved unchanged. The API already assembles BTC bars even when composite data is unavailable; momentum signals depend solely on BTC daily candles and must not depend on composite status, candidates, confirmations, or leg boundaries.

### Goals and success criteria

- Correctly calculate the supplied three non-overlapping segments, vote score, daily SMA filter and allocation transitions using completed daily bars only.
- Return chronological, signal-bar-anchored BUY/SELL points, with no signal for unchanged target, missing inputs, warm-up or invalid gaps.
- Display the point at its own daily close (not next day's open), with chart scales, zoom/pan and visible clipping respected.
- Preserve all current chart features and maintain one API read/request.
- No orders, trade simulation, allocation values, performance statistics, or new controls.

## 2. Execution Brief

### One execution stream: model, contract, chart, integration proof

**What happens:** implement the pure daily signal calculation, add it to the existing BTC legs response and TypeScript mirror, extend the simple-lines island with a distinct price-anchored marker layer, and connect that layer from `BtcLegChart`. Integrate through seeded FastAPI/browser data and verify existing leg presentation remains intact.

**Integration points:** cached BTC 1d bars → `assemble_btc_leg_chart` (single read; independent of composite) → additive response `signals` → `fetchBtcLegs` → `BtcLegChart` → `SimpleLinesProps` → LayerChart coordinate scales and overlay. Do not change vertical boundary markers.

**Automated test:** hand-calculated API golden scenarios; router schema/cache-isolation contract; frontend component and island render/interaction behavior; seeded Playwright path crossing FastAPI through the real React/Svelte chart. Test cache access only via `isolated_cache`, with no provider/network calls.

**Manual test:** run seeded stack with refresh worker off and Playwright browser binary configured; open the screener BTC legs chart, verify BUY/SELL positions on correct daily close, zoom/pan through points and back, then compare existing bands, boundaries, readouts and estimate with baseline behavior. Check unavailable/warm-up conditions do not fabricate markers and composite-unavailable BTC-only computation still works.

**Verify data/state:** inspect the actual `/api/regime/btc-legs` JSON and assert sorted `{kind,timestamp,price}` signal items; no database writes or new storage are expected. For deterministic unit tests use exact expected timestamps/prices and target-transition scenarios, not just field-presence checks.

**Done when:** all gates are green, manual/browser scenario confirms correct anchoring and unchanged existing overlays, failures are handled without fabricated signal data, and user visually confirms the BTC chart. This plan itself does not authorize EXECUTE.

### Expected outcome

- One response provides the existing BTC legs data and a chronological list of signal events.
- The chart visibly places BUY/SELL on the close of the daily candle that generated the target change.
- Existing legs bands, vertical boundary marks, price line, leg readouts and estimate are preserved.
- Scope stays daily-only, long-only and visual-only.

## 3. Scope and Final Implementation Choices

### In scope

- Python calculation and Pydantic response model addition for BTC daily signals.
- TypeScript response type and chart/island point rendering contract.
- UPDATE PROCESS records the scoped D-2 exception in `process/context/decisions.md` only after EXECUTE and EVL, before finalization or archive. During PLAN, this task-local Decision Log below records the exception required by the frozen SPEC; this does not synchronize or modify canonical context.

- Editing the SPEC, changing leg definition/drawing, endpoints/providers/cache retention, adding timeframe selection or non-daily support.
- Trades, order placement, simulation, shorting, allocation display, backtest/performance metrics, new controls, or signal outputs beyond this BTC chart.
- Any general relaxation of D-2.

### Decision Log

- **2026-11-02 — BTC-only D-2 exception:** The user authorized BUY/SELL visual markers on the BTC daily legs chart only. No generated signals elsewhere; no orders or trade execution. This task-local record satisfies the frozen SPEC's planning/implementation logging requirement. Synchronize this scoped decision to `process/context/decisions.md` during UPDATE PROCESS, after EXECUTE+EVL and before finalization/archive.

### Final implementation choices

1. **Daily-only inputs.** Existing chart and API BTC data are 1d. Both momentum and daily SMA use completed UTC daily bars. The explicit user choice supersedes only the non-daily clause of SPEC AC7 for this feature; record AC7's non-daily behavior as deferred and do not modify SPEC. No selector, chart timeframe contract, or mixed-timeframe API is added.
2. **Single existing endpoint.** Add a `signals` list to `BtcLegChartResponse`, populated by the pure calculation over this response's BTC bars. Make the additive field default-safe (empty list for older/other response construction paths) and migrate all in-repo model/type/callsite/test fixtures. No second read or endpoint. Signal computation is independent of composite availability. This is additive only for external clients that tolerate unknown response fields: `default=[]` protects model construction, not wire compatibility. Known out-of-repository consumers are unknown and are not proven by in-repo search. Before deployment, inventory known external consumers and document the release/consumer notice; if any strict consumer would reject the field, pause for an explicit owner decision. Keep the existing endpoint; do not add a compatibility shim or versioning path without approval.
3. **Signal payload.** Minimal event item: `kind: "BUY" | "SELL"`, `timestamp: ISO UTC string`, `price: float`. Chronologically sorted, one event per changed target. The x timestamp remains the source bar's original chart timestamp; `price` is that same completed bar's close. No allocation/score returned.
4. **Model defaults, auto behavior and validation.** The internal Python calculator accepts model settings rather than adding UI controls. Defaults match the supplied Pine script: segment ends 3/6/12 months; `barsPerMonth=21`, yielding lengths 63/126/252 daily bars; vote scale 1.73; max exposure 98%; SMA 200; below-MA scale 0.5; MA filter enabled. If `barsPerMonth=0`, resolve the crypto auto value to 30 bars/month (90/180/360); the default API invocation explicitly uses 21. Validate segment endpoints are strictly increasing before calculating; reject non-increasing endpoints. For close at index `i`: seg1=`close[i]/close[i-len1]-1`; seg2=`close[i-len1]/close[i-len2]-1`; seg3=`close[i-len2]/close[i-len3]-1`. Score counts positive segment returns. Base target=`min(score*(100/3)*1.73,98)` and multiply by 0.5 below the 200-day SMA. Emit BUY on target increase and SELL on decrease; first eligible positive target compares against zero. Same target emits nothing; target is never negative. SMA equality does not apply the below-MA multiplier (only strictly below SMA does). No lookahead.
5. **Warm-up, UTC date range, forming bars and gaps.** Require 253 consecutive completed closes for the default 252-bar maximum lookback and the 200 SMA; `barsPerMonth=0` resolves to 30 for crypto, making the maximum length 360 and requiring 361 consecutive completed closes. Pine input literals are interpreted as UTC instants for this feature: inclusive `startDate=2006-01-01T00:00:00Z`, exclusive `endDate=2170-12-31T23:59:00Z`. Since daily bar timestamps are UTC opens, `2170-12-31T00:00:00Z` is the last daily open in range and `2171-01-01T00:00:00Z` is the first daily open out of range. `inDateRange` gates active/target state, not indicator history: valid pre-start daily bars may feed lookback and SMA warm-up, but emit no signal before start. At the first active in-range bar, compare against inactive target zero and emit BUY only if calculated target is positive. At the first daily bar open at/after exclusive end, emit one SELL at that bar's own timestamp and close only if the prior target was positive; remain inactive and emit no later events. The end-boundary SELL additionally requires a valid finite-positive close and a unique UTC daily row. Normalize every timestamp to UTC before stable ordering, exact-timestamp/date grouping, daily-contiguity checks, and serialization; use `freshness.as_utc` semantics (naive timestamps mean UTC; aware timestamps convert to UTC) and `freshness.iso_z` for UTC seconds with trailing `Z`. A valid timestamp with invalid/non-finite/non-positive price, duplicate exact timestamp, or multiple rows for one UTC date is a data break: emit no event on those rows, invalidate every row in a duplicate UTC-date group (never choose first/last), clear comparison baseline to zero, and require full contiguous valid warm-up from the next valid daily row. If an invalid/duplicate row is the first post-end candidate, suppress the SELL rather than infer an event from another row in that date/group; remain inactive afterward. Missing UTC dates are also data breaks; never synthesize zero prices or a gap SELL. A daily bar is eligible only once its UTC interval completes: `bar_open + 1 day <= now`, matching `freshness.is_partial` (`bar_open + timeframe > now`); include it at exact midnight completion. Existing BTC display series may continue unchanged. Cap target at 98%; emit BUY for target increase, SELL for decrease, none for unchanged target; no lookahead.
6. **Distinct chart point layer.** Add an optional signal point contract separately from `SimpleLineMarker` vertical boundary markers; use same x/y plot scales and domains, zoom/pan and clipping, without altering current bands/markers. Render close-anchored BUY/SELL glyph/text visibly and accessibly; do not hide the only meaningful signal values in an `aria-hidden` overlay. Preserve existing accessibility label and communicate signal value in an accessible description/label.
7. **No retention expansion.** `freshness.py` uses `TAIL_LIMIT["1d"] = 500` and daily retention is not trimmed. The default lookbacks require 253 completed closes. Keep this as-is; if actual endpoint bars cannot satisfy warm-up, show no signals until sufficient valid completed history exists rather than silently shortening lookbacks.

### Acceptance criteria mapped to SPEC

- **AC1, AC2:** golden scenarios confirm segment formulas and defaults; test internal settings `barsPerMonth=0` resolves to crypto 30 (90/180/360), default API invocation remains 21 (63/126/252), and reject non-increasing segment endpoints, alongside MA/scaling/cap behavior.
- **AC3, AC4:** target transitions confirm first zero-to-positive BUY, partial increase BUY, partial decrease/full exit SELL, unchanged target no marker, no negative target/short.
- **AC5:** exact original signal-bar timestamp/close, sequential causal evaluation, no lookahead or next-bar shift.
- **AC6:** insufficient history, missing SMA/close, forming bar, gaps, invalid closes and inactive/unready range emit no false marker.
- **AC7:** daily-only momentum and daily SMA both consume BTC 1d bars on the existing chart. **Deferred by user decision:** AC7's non-daily displayed-timeframe/mixed-timeframe clause; no non-daily support in this plan.
- **AC8:** old price, legs/bands, vertical boundaries, estimate/readouts unchanged alongside new markers.
- **AC9:** only signal kind/time/price for new layer; no trade/execution/equity/backtest/allocation UI or fields.

## Touchpoints

### Planned source/test touchpoints

- `api/analytics/regime/btc_legs.py` — calculate/attach signals while assembling existing BTC response; BTC-only dependency.
- `api/models/regime.py` — typed signal item and additive `signals` field on `BtcLegChartResponse`.
- `api/tests/analytics/test_btc_legs.py` — golden values, transition, forming-bar, gap and warm-up tests.
- `api/tests/routers/test_btc_legs_router.py` — response serialization/model parity, cache-only behavior and composite independence; narrowly update vocabulary guard at lines 183–199 to permit BTC-only BUY/SELL while preserving unrelated signal/verdict protections and asserting no leak.
- `api/tests/routers/test_btc_legs_router.py` — extend Pydantic/TypeScript parity coverage for signal event model and constrained kind; require event contract validation for finite positive price and valid UTC timestamp.
- `web/lib/types/btc-legs.ts` — TypeScript contract mirror.
- `web/lib/__tests__/btc-leg-lines.test.ts` — full response fixture; inspect relevant partial fixture in `ScreenerBoardLive.test.tsx` during EXECUTE.
- `web/lib/island-loader.ts` — distinct optional signal point props; do not overload `SimpleLineMarker`.
- `web/islands/entry.js` — explicitly register `signalPoints` in `SIMPLE_LINES_KEYS`; test that signal props arriving after island mount update/render.
- `web/components/screener/BtcLegChart.tsx` — pass signals to chart while preserving existing series/bands/markers/readouts.
- `web/islands/simple-lines.svelte` — signal point positioning with shared x/y scales, zoom/pan and clipping; accessible signal representation; retain boundary overlay behavior.
- `web/components/screener/__tests__/BtcLegChart.test.tsx` — component contract test with both existing overlays and signal points.
- Existing island test convention, if one is present for `simple-lines.svelte`; otherwise prove update/render through the seeded browser E2E and component contract without introducing a second chart implementation.
- `process/context/decisions.md` — UPDATE PROCESS entry synchronizing the scoped D-2 exception after EXECUTE and EVL, before finalization/archive. The dated task-local Decision Log above is the planning record; do not edit canonical context during PLAN or EXECUTE.

## Public Contracts

### Existing endpoint (additive)

`GET /api/regime/btc-legs` retains all current fields and behavior and adds:

```json
"signals": [
  {"kind": "BUY", "timestamp": "2026-01-01T00:00:00Z", "price": 90000.0}
]
```

- `signals` is always present, default `[]`; it is sorted ascending by timestamp.
- `kind` is exactly `BUY` or `SELL`; `timestamp` is the signal bar's UTC chart timestamp, `price` that same completed bar's close.
- No target allocation, score, trade, order, or strategy statistics appear.
- When BTC data unavailable, return `signals: []`; when composite unavailable but BTC daily bars are available, compute normally.
- Existing caller and exact response/model-field parity tests must be updated to include this intentional additive contract; ensure all in-repo API and TypeScript consumers are migrated.

### Chart island contract

Add a separate optional point array (e.g. `signalPoints`) to `SimpleLinesProps`, each with timestamp, numeric y value, and constrained kind. It is not a vertical `SimpleLineMarker`. It must render using the chart's x/y domains and scales, clipping to visible plot bounds, reacting to zoom/pan/data updates. Absent or empty means no signal layer; all existing simple-lines consumers continue unchanged.

## Blast Radius

| Area | Change | Risk / boundary |
|---|---|---|
| BTC signal math | Pure deterministic Python calculation on existing 1d bars | High correctness impact: off-by-one, warm-up, gaps and forming candle could misdate signals |
| FastAPI/Pydantic response | Add `signals` to existing endpoint schema | Public API shape change; additive/default-safe; update exact model/response parity assertions and all callers |
| BTC chart wrapper/types | Thread typed signals into existing island | Maintain one fetch; avoid disrupting readouts and current overlays |
| Shared simple-lines island | Add optional point layer | Shared chart runtime; preserve old markers/bands/viewport and constrain visual change to supplied points |
| Browser integration | Seeded cache→FastAPI→React/Svelte | Proves real boundary; no network, refresh worker off; CI does not run Playwright |
| Product policy | One BTC chart exception | D-2 exception must remain narrowly scoped; no other bullish/bearish outputs or execution |

### High-risk coverage classification

The response schema is an external API contract; minimum hybrid coverage is the deterministic seeded browser/API boundary test in addition to unit tests. No authentication, secrets, migration, deletion or runtime deployment behavior changes are planned.

## 5. Implementation Checklist

Single RFC execution stream; items are ordered, atomic code-and-test work. Each implementation item is followed by its test proof; no phase-program approval pauses apply. After the integrated execution, stop for verification and user confirmation; do not proceed to additional scope.

### RFC-001 — Daily signal response and price-anchored chart

- [ ] Implement pure BTC daily calculation using exact three-segment formulas, 21 bars/month defaults, 1.73 vote scale, 98% cap, SMA-200 and 0.5 below-MA scale; add hand-computed golden tests for each vote state and SMA behavior.
- [ ] Implement an internal calculator/settings parameter with script defaults; test default `barsPerMonth=21`, crypto auto `barsPerMonth=0 → 30`, derived horizon lengths, and rejection of duplicate/reversed segment endpoints. Do not add user-facing controls; API invocation explicitly selects default 21.
- [ ] Define signal event Pydantic model and default-safe `signals` response field; update router/model-field parity tests to assert exact serialized values, Pydantic/TypeScript event-model parity, constrained `kind` (`BUY`/`SELL`), finite positive price, valid UTC timestamp, and empty/unavailable behavior. Add full response fixture in `web/lib/__tests__/btc-leg-lines.test.ts`; inspect/update relevant partial fixture in `ScreenerBoardLive.test.tsx`.
- [ ] Integrate from assembled BTC bars only; test that unavailable composite does not block signals and cache-touching fixtures use `isolated_cache` with no network.
- [ ] Exclude a forming UTC daily bar only while `bar_open + 1 day > now`, matching `freshness.is_partial`; include at exact completion equality. Keep BTC display series unchanged. Interpret Pine date literals as UTC instants; test inclusive start `2006-01-01T00:00:00Z`, exclusive end `2170-12-31T23:59:00Z`, last in-range daily open `2170-12-31T00:00:00Z`, and first out-of-range daily open `2171-01-01T00:00:00Z`. Cover pre-start valid warm-up without pre-start signals, first active comparison against zero, and exact one-time end SELL at the first out-of-range bar's own time/close only when prior target is positive.
- [ ] Normalize all timestamps to UTC before stable ordering/grouping, consistent with `freshness.as_utc` (naive means UTC; aware converts to UTC) and `freshness.iso_z` (UTC seconds, trailing `Z`); retain `freshness.is_partial` completion semantics. Test invalid timestamp/price, duplicate exact timestamp/date and missing UTC dates as data breaks: emit no event on invalid/duplicate rows, invalidate every row in a duplicate UTC-date group, reset baseline and fully re-warm from next valid row; never synthesize zero or gap SELL. Add exact end-boundary invalid-price and duplicate-date-group tests: these suppress the SELL if the invalid/duplicate row/group is the first post-end candidate, and remain inactive afterward.
- [ ] Add typed frontend mirror and separate point prop; update component contract test to confirm signal pass-through while price, bands, vertical boundaries, leg readouts and estimate remain present.
- [ ] Implement island point layer using shared plot scale/domain, visible-domain clipping and pan/zoom; test old vertical boundary markers remain unchanged and signal points use close y coordinates. Ensure accessible signal text/description works despite island `role="img"` and existing `aria-hidden` overlays; do not rely solely on inaccessible overlay labels. Use existing island-render test convention if available, otherwise existing test surface.
- [ ] Add regression proving signal props arriving after island mount update/render; explicitly register `signalPoints` in `web/islands/entry.js` `SIMPLE_LINES_KEYS`.
- [ ] During PLAN, retain the dated task-local Decision Log above as the record of the authorized scoped exception. Only during UPDATE PROCESS, after EXECUTE and EVL and before finalization/archive, synchronize that decision to `process/context/decisions.md`; no canonical context edit during PLAN or EXECUTE.
- [ ] During authorized implementation, refresh `process/features/charting-indicators/_GUIDE.md` stale charting-indicators source map/status; do not add generic outdated chart/API endpoints.
- [ ] Complete RT4 verification and high-risk evidence pack before handoff/finalize: after all changes, run `uv run --project api pytest api/ -q`, `pnpm --filter web test`, `pnpm --filter web exec tsc --noEmit --incremental false`, `cd web && pnpm build:islands`, and seeded Playwright E2E using existing config and Windows-compatible invocation (PowerShell environment assignment only if bundled browser is unavailable); invoke `vc-risk-evidence-pack` for the public API contract change and populate the five evidence artifacts in this task folder's `harness/` directory, including explicit reviewer decision. Obtain user acceptance or recorded agent-probe before reporting complete.

## Verification Evidence

| Gate / Scenario | Strategy | Proves SPEC criterion |
|---|---|---|
| Segment-return and vote golden values (positive, negative, zero returns) | Fully-automated pytest; hand-computed expected values and segment boundaries | AC1 |
| Supplied defaults and allocation transform (21 bars/month, 63/126/252; SMA-200; vote scale 1.73; cap 98; below-MA 0.5; invalid horizon ordering where configurable) | Fully-automated pytest boundary/golden cases | AC2 |
| Internal settings default and auto behavior; strict endpoint ordering | Fully-automated pytest for default 21, crypto zero→30, derived lengths and invalid duplicate/reversed endpoints | AC2 |
| First positive target, partial increase, unchanged target | Fully-automated pytest event sequence and exact event values | AC3 |
| Partial decrease, move to zero, target nonnegative and no short | Fully-automated pytest transition and bounds assertions | AC4 |
| Signal bar timestamp and price; causal sequential input; forming bar excluded | Fully-automated pytest asserting original UTC timestamp/close and no next-bar shift/lookahead | AC5 |
| Insufficient lookback, missing SMA/close, invalid values, gap/reset/re-warm, inactive range | Fully-automated pytest; UTC literal oracles (2006-01-01T00:00:00Z inclusive; 2170-12-31T23:59:00Z exclusive; 2170-12-31T00:00:00Z last in-range daily open; 2171-01-01T00:00:00Z first out-of-range open); exact first-out-of-range one-time SELL only for prior positive target and valid finite-positive close on a unique UTC daily row; invalid-price and duplicate-date-group first candidates suppress SELL; all duplicate-date rows invalidated, baseline reset and full re-warm; no fabricated event | AC6 |
| Existing 1d momentum and SMA both daily; AC7 non-daily clause explicitly deferred by user decision | API golden test plus plan scope decision; no selector/mixed-TF behavior | AC7 (daily-only scoped portion; non-daily deferred) |
| Chart displays signals together with existing line, bands, vertical boundaries, readouts and estimate | Fully-automated Vitest component test and island behavior/render test where convention exists | AC8 |
| No order, allocation, stats or execution fields/UI | Response schema assertion plus component/API surface assertions | AC9 |
| Response contract, actual route serialization, cache-only and composite isolation | Hybrid seeded API/browser contract test; pytest with `isolated_cache`; no network | AC3–AC6, AC8–AC9 |
| Real API → React → Svelte chart and viewport behavior | Hybrid seeded Playwright with refresh worker off and a deterministic, signal-specific BTC fixture/manifest containing both BUY and SELL | Exact endpoint `signals` equality to an expected `{kind,timestamp,price}` oracle defined independently of the production calculator; verify UTC source-bar timestamps and same-bar closes; assert each marker in an observable, accessibly named chart representation; explicitly exclude the still-open final bar while retaining enough completed warm-up bars; verify zoom/pan/reset, clipping, current overlays/readouts/estimate | AC5, AC8–AC9 |
| Visual leg-preservation and legible/accessibly named signal markers | Agent probe/manual user check on screener; inspect zoomed and panned points and screen-reader-readable labeling | AC8–AC9 |
| Public API contract change requires RT4 risk evidence pack | Before finalize, invoke `vc-risk-evidence-pack`; store `risk-gate.json`, `context-snippets.json`, `verification.json`, `review-decision.json`, and `adversarial-validation.json` under task-folder `harness/`; do not claim complete without reviewer decision | RT4 / AC8–AC9 |
| Strict external consumer compatibility and deployment gate | Before deployment, inventory known out-of-repository consumers and document release/consumer notice; if any strict consumer rejects unknown fields, pause for explicit owner decision. In-repo search does not prove external consumers exist | Public API contract |
| RT4 suite, seeded Playwright, risk evidence and acceptance all green | Full required gates once after final edit; risk-pack validator per skill; manual user acceptance or recorded agent-probe | AC1–AC9 |

### Test stages and commands

Commands follow `operating-instructions.md`; exact targeted unit invocations are not specified because the repository config does not establish a targeted invocation convention. The exact full RT4 suites listed below are authoritative final gates; run them once after all changes:

- API: `uv run --project api pytest api/ -q`
- Web unit: `pnpm --filter web test` — full Vitest suite, component and island behavior.
- TypeScript: `pnpm --filter web exec tsc --noEmit --incremental false`
- Chart island build: `cd web && pnpm build:islands`
- RT4 high-risk evidence pack, colocated at `process/features/charting-indicators/active/btc-momentum-signals_02-11-26/harness/`: invoke `vc-risk-evidence-pack`; produce `risk-gate.json`, `context-snippets.json`, `verification.json`, `review-decision.json`, and `adversarial-validation.json`, following `.claude/skills/vc-risk-evidence-pack/SKILL.md`. All five artifacts and explicit review decision are required before finalizing/handing off implementation.
- Seeded browser E2E (not in CI): PowerShell from the repository root: `$env:SCREENER_REFRESH_WORKER='0'; Set-Location web; pnpm test:e2e -- screener`. Use the existing Playwright config and a self-checking fixture manifest containing signal-specific expected BUY and SELL events independently of the production calculator. Assert exact endpoint `signals` equality to the `{kind,timestamp,price}` oracle, UTC source-bar timestamp and same-bar close; assert both markers in an observable, accessibly named chart representation; exclude the still-open final bar while retaining sufficient completed warm-up bars; and verify zoom/pan/reset, clipping, and current overlays/readouts/estimate. The manifest must block network/provider fetch-through. Set `$env:PLAYWRIGHT_CHROMIUM_PATH` only if the bundled browser is unavailable.
Pass means all selected/full suites succeed; golden assertions prove exact computation, API test proves serialized response and isolation, component/island evidence proves visual contract, and seeded E2E proves the live application boundary. A 200 response or type/build success alone is not completion. Respect RT4's one-run-after-last-edit budget and no-rerun rule; do not use network tests.

### Phase Completion Rules

This is one execution stream, not multiple separately gated phases. The feature is not complete until:

1. **Integration test:** seeded browser crosses real FastAPI and chart rendering and checks signals and preserved existing chart features.
2. **Manual test:** user can open the chart and inspect close-anchored signals and zoom/pan behavior.
3. **Data verification:** endpoint JSON values and timestamps match deterministic expected signal events; no database/cache writes beyond isolated test fixtures.
4. **Error handling:** unavailable, warm-up, missing-bar and gap cases produce no fabricated marker and do not break existing chart data.
5. **User confirmation:** user visually confirms the integrated chart behavior.

Status meanings: ⏳ PLANNED — not started; 🔨 CODE DONE — written, not E2E tested; 🧪 TESTING — being tested; ✅ VERIFIED — tested and user-confirmed; 🚧 BLOCKED — issue prevents completion. After execution, record manual test, data/API evidence, errors fixed, and user confirmation. Do not mark ✅ VERIFIED based solely on build/typecheck/HTTP response.

### Test Infra Improvement Notes

(none identified yet)

## 7. Risks and Mitigations

| Risk | Mitigation |
|---|---|
| Off-by-one segment index or using 0/30 bars-per-month instead of selected default 21 | Pin hand-computed segment return/target golden sequences; explicitly assert index positions 63/126/252 |
| Internal model configuration accidentally becomes user-facing | Keep calculator parameters internal; add no controls; test 21 default and 0→30 behavior only in Python | AC2 |
| Cached last candle is still forming | Determine UTC completion at calculation time, exclude forming candle from signals only; leave displayed bars intact; test cutoff boundary |
| Missing, invalid or duplicate bars treated as zero/continuation or a boundary SELL | Normalize UTC before stable ordering/grouping; invalidate all rows on duplicate UTC dates; invalid price/duplicate first post-end candidate suppresses SELL; reset baseline and require contiguous re-warm; do not emit invented SELL on data loss |
| Insufficient 1d history | Need at least 253 completed closes; no lookback shortening or retention expansion; no signals until ready |
| Composite or legs state accidentally gates calculation | Test BTC signals under composite-unavailable route inputs |
| Marker implemented as vertical boundary line or wrong y mapping | Separate point contract; test same plot x/y scale, visible domain, clipping and viewport changes |
| Additive schema breaks exact parity/callers | Update all in-repo response fixtures, API parity tests and TS mirror; preserve default `[]` for response constructors |
| Broader D-2 exception leaks | The dated task-local Decision Log records BTC daily legs chart only, BUY/SELL visual markers, no generated signals elsewhere and no orders/trade execution; synchronize the canonical decision only in UPDATE PROCESS after EXECUTE+EVL and before finalization/archive |
| E2E skipped due to worker/cache/browser setup | Use seeded fixture validated against route reader, `SCREENER_REFRESH_WORKER=0`, `PLAYWRIGHT_CHROMIUM_PATH`; explicitly run locally since CI omits Playwright |

## Resume and Execution Handoff

- **Plan path:** `process/features/charting-indicators/active/btc-momentum-signals_02-11-26/btc-momentum-signals_PLAN_02-11-26.md`
- **Last completed phase/step:** VALIDATE — current V6 outer-PVL contract after accepted P1–P3; no feature tests or source changes.
- **Validate-contract status:** current outer-PVL PASS contract below; plan coverage only, not implementation evidence. No feature tests were run. The user explicitly authorized EXECUTE on 2026-11-03; implementation has not auto-started.
 
- **Supporting context files:** `process/context/all-context.md`; `process/context/tests/all-tests.md`; `process/context/architecture.md`; `process/context/operating-instructions.md`; `process/context/north-star.md`; `process/features/charting-indicators/active/btc-momentum-signals_02-11-26/btc-momentum-signals_SPEC_02-11-26.md`; `process/features/charting-indicators/_GUIDE.md`; `.claude/skills/vc-generate-plan/references/generate-plan.md`; `.claude/skills/vc-generate-plan/references/example-complex-prd.md`; `.claude/skills/vc-test-coverage-plan/SKILL.md`; `.claude/skills/vc-frontend-design/SKILL.md`; `.claude/skills/vc-scenario/SKILL.md`.
- **Next step for a fresh agent:** EXECUTE is explicitly authorized by the user on 2026-11-03; no standing autonomy exists and execution has not auto-started. Proceed only within that authorization and this plan's scope.
- **RT4 handoff gate:** because the endpoint response is a public API contract change, implementation must complete `vc-risk-evidence-pack` and its colocated evidence artifacts/reviewer decision, all RT4 suites including seeded Playwright, and user acceptance or a recorded agent-probe before reporting completion. This PLAN-only handoff does not create the pack or constitute validation.
- Before implementation handoff/finalize, apply `.claude/skills/vc-risk-evidence-pack/SKILL.md` and complete all five required pack artifacts in `process/features/charting-indicators/active/btc-momentum-signals_02-11-26/harness/`, including `adversarial-validation.json` and an explicit reviewer decision. Run all RT4 gates and obtain user acceptance or a recorded agent-probe.

## Cursor + RIPER-5 Guidance

- **Cursor Plan mode:** import this plan and execute the single RFC checklist in order; retain this file as the authoritative plan and update its status only as work is actually verified.
- **RIPER-5:** RESEARCH → INNOVATE → PLAN are complete for this scope. Wait for explicit owner authorization before EXECUTE; during EXECUTE implement exactly these choices, report any contract mismatch before deviation, and stop for verification and user confirmation.
- **Scope control:** if non-daily support, leg redesign, allocation display, strategy statistics or any additional signal surface is proposed, pause; it is not authorized by this plan. D-2 override is BTC chart only.
- The feature has one integrated execution stream, not phase-program RFC approvals. Final verification remains mandatory before claiming completion.

## Validate Contract

Status: PASS
Date: 03-11-26
date: 2026-11-03
generated-by: outer-pvl
supersedes: 2026-11-02 (outer-pvl) — outer PVL has current evidence

Parallel strategy: parallel-subagents
Rationale: 3/7 signals; dominant signals S2 public API/schema, S6 public API risk, and S7 five-plus files; independent dimension and feasibility review warranted parallel review.

Test gates (C3 5-column table — additive; implementation gates are planned, not run in VALIDATE):

| criterion id | behavior | strategy | proving test | gap-resolution |
|---|---|---|---|---|
| AC1–AC2 | Segment formulas, vote/default settings, SMA, allocation transform and invalid horizons | Fully-Automated | `uv run --project api pytest api/ -q` — golden/boundary cases | B |
| AC3–AC4 | Target transitions, bounds and no short | Fully-Automated | `uv run --project api pytest api/ -q` — exact event sequences | B |
| AC5–AC6 | Signal-bar timestamps/prices, causal ordering, warm-up, invalid data and gaps | Fully-Automated | `uv run --project api pytest api/ -q` — UTC, forming-bar, gap and boundary cases | B |
| AC7 | Daily-only momentum/SMA; non-daily clause deferred | Fully-Automated | `uv run --project api pytest api/ -q` — daily inputs; plan records deferred clause | B |
| AC8–AC9 | Signal rendering while preserving chart features; no trade/execution surface | Fully-Automated | `pnpm --filter web test` — component/island contract | B |
| AC3–AC6, AC8–AC9 | Seeded live API-to-chart behavior, observable markers and viewport | Hybrid | PowerShell seeded Playwright command in Section 5; independent BUY/SELL oracle, exact API equality and accessible marker assertions | B |
| AC5, AC8–AC9 | Close anchoring, accessibility, viewport and preserved visual features | Agent-Probe | Manual/agent review of seeded chart; user visual acceptance or recorded probe | B |
| Public API contract | Known external consumer compatibility and deployment notice | Agent-Probe | Pre-deployment inventory; document notice and pause for owner decision if strict client incompatible | C |

gap-resolution legend:
- A — proven now (gate passes in this cycle)
- B — fixed in this plan (gate added by this plan's checklist)
- C — deferred to a named later phase/plan
- D — backlog test-building stub (named residual; keep-active; continue)

C-4 reconciliation: the strategy column contains only Fully-Automated, Hybrid, or Agent-Probe proving strategies. Known-Gap is not a proving strategy; any named residual would be carried via gap-resolution D. No D residual is recorded.

Legacy line form (retained for existing consumers):
- Signal calculation and API: Fully-automated: `uv run --project api pytest api/ -q` | hybrid: seeded API/browser contract in Section 5 | agent-probe: not applicable to deterministic API math | known-gap: external consumer inventory remains a pre-deployment gate.
- Chart contract: Fully-automated: `pnpm --filter web test` | hybrid: seeded Playwright in Section 5 | agent-probe: manual/agent visual review | known-gap: no runtime chart behavior was exercised in VALIDATE.

Dimension findings:
- Infra fit: PASS — plan identifies existing BTC bars/API/cache and chart surfaces; test commands use established project suites.
- Test coverage: PASS — original seeded E2E concern (independent signal-specific oracle and observable marker assertions) was resolved by accepted P1–P3; tests remain planned and were not run.
- Breaking changes: PASS — additive response field and explicit external-consumer inventory/release gate are documented.
- Security surface: PASS — no authentication, secrets, permissions, or provider/network behavior changes are in scope; seeded tests must block network fetch-through.
- RFC-001 feasibility: PASS — touchpoints and ordered implementation/test gates are identified; no implementation feasibility is claimed as runtime evidence.

Open gaps: external consumers are not established by in-repo search and require pre-deployment inventory/notice; no implementation behavior or runtime was exercised; RT4 suites, seeded E2E, risk evidence pack, and user/agent visual evidence remain execution-time gates; SPEC AC7 non-daily clause is deferred by the user's daily-only decision.

What This Coverage Does NOT Prove:
- No feature tests, build, runtime, API request, browser execution, or implementation behavior was exercised in VALIDATE.
- Planned unit/component tests do not yet prove the implementation passes AC1–AC9.
- Planned seeded Playwright does not yet prove actual endpoint serialization, signal marker rendering/accessibility, zoom/pan/clipping, or preservation of existing overlays.
- No manual visual acceptance, external-consumer compatibility, deployment readiness, or risk-evidence-pack completion is established by this PASS.
- The PASS is limited to plan coverage and disposition of the five independent review findings; it is not implementation evidence.

Gate: PASS (no FAILs, plan updated)
Accepted by: user — 2026-11-03; accepted P1–P3, resolving the test-coverage concern.

## Autonomous Goal Block

SESSION GOAL: Implement RFC-001 exactly as specified in this authoritative single-feature plan, within the user's explicit authorization.
Charter + umbrella plan: N/A — single plan
Autonomy: There is no standing autonomy. The user explicitly authorized EXECUTE on 2026-11-03; this authorization does not auto-start implementation.
Hard stop conditions/safety constraints: Do not expand scope beyond BTC daily chart signals. Do not add non-daily behavior, other signal surfaces, allocation display, strategy statistics, orders, or trade execution. Stop on any contract mismatch and report it before deviation. Do not claim completion without the required tests, risk evidence, integration/manual verification, and user acceptance described in the plan.
Next phase: EXECUTE is explicitly authorized by the user on 2026-11-03, but has not auto-started.
Validate contract: Current V6 outer-PVL PASS; plan coverage only, not implementation verification. No feature tests were run in VALIDATE.
Execute start: User explicitly authorized EXECUTE on 2026-11-03. No standing autonomy exists; authorization has not auto-started implementation.
