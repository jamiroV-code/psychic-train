---
phase: rfc-005-onchain-frontend
date: 2026-09-26
status: COMPLETE
feature: onchain-activity
plan: process/features/onchain-activity/active/chain-growth_25-09-26/chain-growth_PLAN_25-09-26.md
---

# RFC-5 — `/onchain` frontend: report

**TL;DR:** `/onchain` is built to the Stage 0 report and the user decisions of 2026-09-26: route `/onchain`, default range 1Y, and Robinhood tagged "late start".
- The page has six synced raw panels, one normalised overlay, and cards for the unavailable chains. It also shows the source/method on each panel, the growthepie CC BY footer, stale and redistribution badges, and the L2BEAT divergence as display-only text.
- Gates:
  - web vitest: **138 passed, 19 files** (baseline 110/16; +28 tests, +3 files).
  - `tsc --noEmit`: exit 0.
  - api suite: 511 passed / 5 deselected (unchanged).
- The palette validates in both modes.
- Not committed. The Playwright spec is not written; it belongs to RFC-6.

## What Was Done
| File | What |
|---|---|
| `web/app/onchain/page.tsx` | New route. |
| `web/app/page.tsx` | Additive home link `home-link-onchain`. |
| `web/lib/types/onchain.ts` | Mirrors `api/models/onchain_activity.py` field for field. |
| `web/lib/api/onchain.ts` | `fetchOnchainGrowth(metric, start?)` and `fetchOnchainChains()`, using the regime `getJson` pattern. |
| `web/lib/onchain-view-model.ts` | Pure mapping: grid alignment, splitting out pre-launch points, markers from `floor_ramp.events`, range→`start`, stale days, copy, fixed chain colours, text tokens. It contains no analytics. |
| `web/lib/format-unavailable-reason.ts` | Additive sibling `formatOnchainReason`; screener and narrative functions untouched. |
| `web/components/onchain/` | `OnchainDashboard`, `ChainPanel`, `ComparisonOverlay`, `MetricSelector`, `RangePicker`, `FloorRampStateLabel`, `SourceMethodBadge`, `LimitedHistoryFlag`, `CrossCheckNote`, `UnavailableChainCard`, `SourceAttributionFooter`. |
| `web/test/mocks/onchain-lightweight-charts.ts` | Re-exports the shared mock, plus `AreaSeries`, `PriceScaleMode` and `createSeriesMarkers`. The shared mock is unchanged. |
| Tests | `components/onchain/__tests__/{OnchainDashboard,ComparisonOverlay}.test.tsx` + `fixtures.ts`, and `lib/__tests__/onchain-view-model.test.ts`. |

Reused as-is (no edits):
- `RedistributionBadge`
- `createChartSync`, `isoDateToUtcSeconds`, `visibleRangeAttribute`
- `toSegmentedSeriesData`, `lineBreakIndices`

No narrative, regime or screener component changed.

### Behaviour as built
- **Range:** there is one filter row with 1Y (default), 2Y, 5Y and All.
  - The first load sends no `start`, so the API default of 365 days applies.
  - After that, each metric or range change re-fetches with `?start=`, computed as the last grid date minus 365/730/1825 calendar days; "All" uses the first grid date.
  - The comparison rebase is always done in Python.
  - While a refetch runs, the previous render stays at 50% opacity (no skeleton), and stale responses are dropped by a request sequence counter.
- **Panels:**
  - Each panel shows the daily value as a thin line in the chain colour at 45% alpha and the EMA28 as a 2px line, on the chain's own single y-axis.
  - Pre-launch points are drawn as a muted grey shaded area, with the visible note "before launch (date), not used in analytics".
  - Floor ▲ and ramp ● markers come from the API.
  - Lines break at `gap_before`.
  - The panels share one sync group for time range and crosshair, starting at `comparison.start_date`.
  - The hover readout shows date, raw value, EMA7 and EMA28. This is the drill-down folded into the hover, as decided.
- **Overlay:**
  - It is one chart with one y-axis and 2px lines in fixed chain colours.
  - Index mode uses a log scale by default (the value comes from `log_scale_default`).
  - In "% above 180-day low" mode, the linear scale is forced and the log toggle is disabled.
  - The legend shows each chain's colour as a short line, the label in ink, and a direct endpoint label with its latest value; a series with no values shows "no data in range" instead.
  - A "late start (date)" tag appears where `rebased_late` is true.
  - The crosshair tooltip lists every chain at the hovered date.
  - A table view is included; this is the palette's relief rule.
  - The overlay is not in the panel sync group.
- **States:**
  - The page has loading, error-with-retry and empty states (no live chain; the footer and overlay are hidden).
  - A refetch error keeps the previous data shown with a retry button.
  - Stale data shows a per-panel badge and a page banner ("last updated N days ago").
  - Unavailable chains get a card with the reason copy and never a zero.
- **AC-2:** `SourceMethodBadge` is visible panel text, and the method note is built from the API `params`.
- **E6:** the footer renders `response.attribution` verbatim ("Source: growthepie, https://www.growthepie.com."), with the URL as a link, once per page.
- **AC-13 (frontend):** `ComparisonOverlay.series` has the type `ComparisonSeries & {points?/value?/values?/raw?: never}`. Two `@ts-expect-error` cases in `ComparisonOverlay.test.tsx` are enforced by `tsc`, because an unused expect-error would itself fail.

## Colour (dataviz palette.md, fixed per entity)
Chain colours follow the chain, never its rank. The slot order is: ethereum 1, base 2, arbitrum 3, optimism 4, polygon 5, robinhood 6. Unknown chains get muted `#898781`, never a generated 7th hue. Text uses ink tokens (`#0b0b0b` / `#52514e` / `#898781`), never series colours.

`validate_palette.js "#2a78d6,#eb6834,#1baf7a,#eda100,#e87ba4,#008300" --mode light`:
```
[PASS] Lightness band         all 6 inside L 0.43–0.77
[PASS] Chroma floor           all 6 >= 0.1
[PASS] CVD separation         worst adjacent #eda100↔#1baf7a ΔE 9.1 (protan) · tritan 5.8
[PASS] Normal-vision floor    worst adjacent #e87ba4↔#eda100 ΔE 19.6 (normal)
[WARN] Contrast vs surface    below 3:1 — relief required (visible labels or table view): #1baf7a 2.74, #eda100 2.11, #e87ba4 2.62
→ ALL CHECKS PASS
```
`validate_palette.js "#3987e5,#d95926,#199e70,#c98500,#d55181,#008300" --mode dark`:
```
[PASS] Lightness band / Chroma floor / CVD (worst #c98500↔#199e70 ΔE 8.4) / Normal-vision (ΔE 19.3) / Contrast (all >= 3:1)
→ ALL CHECKS PASS
```
- There are no FAILs.
- The light-mode contrast WARN is handled by the relief rule: legend text labels with direct endpoint values, and the table view.
- The overlay is a line chart, so the adjacent-pair list applies.
- In the small multiples, each panel shows one chain's colour, so colours never compete within one plot.
- The page renders light only (the app has no dark theme). The dark values are mapped in `chainColor(id, "dark")` for when a theme is added.

## Test Gate Outcomes
| Gate | Result |
|---|---|
| `pnpm --filter web test` (run as `pnpm test` in `web/`) | **138 passed, 19 files** (110/16 before) |
| `pnpm --filter web exec tsc --noEmit` | exit 0; `web/tsconfig.tsbuildinfo` restored with `git checkout` |
| `uv run --project api pytest api/ -q` | **511 passed, 5 deselected** (unchanged) |

The 28 new tests cover:
- 6 panels and 3 unavailable cards (no zero);
- the fetch calls for the metric and range `start`;
- the dimmed refetch;
- AC-2 visible source/method;
- the E6 footer text and href, and its absence when no chain is live;
- the empty state;
- the Robinhood `2027-01-10` copy;
- all 5 state labels ("Near floor" only for `floor`);
- the stale badge and banner;
- the redistribution badge;
- the cross-check (tx only, display-only);
- pre-launch shading, API markers and gap breaks;
- the crosshair sync (the overlay stays out of it);
- error and retry;
- log default on/off, pct mode forcing linear;
- the `late start` tag;
- 2px lines in fixed colours on one axis;
- endpoint labels and the all-series tooltip;
- the visible range from `start_date` and the table view;
- the AC-13 compile-time check;
- the view model (slots, alignment, pre-launch split, markers, `rangeStart` including the leap year, visible range, stale days, copy);
- `formatOnchainReason`.

## data-testids for RFC-6
- Page: `onchain-dashboard` (`data-metric`), `onchain-loading`, `onchain-error`, `onchain-retry`, `onchain-empty`, `onchain-refetching`, `onchain-filters`, `onchain-metric-{active_addresses|transactions}`, `onchain-range-{1y|2y|5y|all}` (`aria-checked`), `onchain-method-note`, `onchain-stale-banner`.
- Overlay: `onchain-comparison` (`data-mode`, `data-log-scale`), `onchain-comparison-mode-{index|pct}`, `onchain-comparison-log-toggle`, `onchain-comparison-method`, `onchain-comparison-legend`, `onchain-legend-{id}`, `onchain-rebased-late-{id}`, `onchain-comparison-chart` (`data-visible-range`), `onchain-comparison-readout`, `onchain-comparison-table`.
- Panels and footer:
  - `onchain-panels`;
  - `onchain-panel-{id}` and its sub-elements `-source`, `-state` (`data-state`), `-stale`, `-redistribution`, `-limited-history`, `-prelaunch`, `-readout`, `-crosscheck`, `-crosscheck-redistribution`;
  - `onchain-chart-{id}` (`data-gap-count`, `data-gap-dates`, `data-marker-count`, `data-visible-range`);
  - `onchain-unavailable-list`, `onchain-unavailable-{id}` (`data-reason`);
  - `onchain-attribution`, `onchain-attribution-text`;
  - `home-link-onchain`.

The Stage 0 list said range `6m`. The user's decision (Q2) made the options 1y/2y/5y/all instead.

## Plan Deviations (within blast radius; frontend-only, new files or additive)
1. The route and folder names are `/onchain` and `components/onchain/`, not the plan's `/onchain-activity` (user decision Q1).
2. There are 2 metrics, not 3: new addresses is dropped under the locked fallback (E4).
3. Polygon gets a live panel (RFC-2..4 reality).
4. The plan's `DrillDown` is folded into the hover readout (approved).
5. The comparison rebase happens on re-fetch with `start`, not client-side.
6. Additive test mock file `web/test/mocks/onchain-lightweight-charts.ts`: the shared mock lacks `createSeriesMarkers`, `AreaSeries` and `PriceScaleMode`, so a sibling file adds them instead of editing the shared mock.
7. Extra small components beyond the plan list: `MetricSelector`, `RangePicker`, `FloorRampStateLabel`, `CrossCheckNote`, `UnavailableChainCard`. All were named in the Stage 0 report.
8. The Stage 0 plan-named `UnavailableReason` variants are not added (the API doesn't emit them).

## What Was Skipped or Deferred
- The Playwright spec, E2E seeding and the context docs are RFC-6.
- The AC-3/AC-5 visual Agent-Probe against real data is RFC-6 / AC-14.
- Dark theme rendering: the app has no theme switch; the values are mapped but not wired.

## Test Infra Gaps Found
- jsdom has no canvas, so chart visuals (log axis appearance, shading, marker placement) are asserted only through mock options and calls. Visual judgment is RFC-6 Agent-Probe work.

## Closeout Packet
- Selected plan: `process/features/onchain-activity/active/chain-growth_25-09-26/chain-growth_PLAN_25-09-26.md`
- Finished: RFC-5 code and tests.
- Verified: vitest, tsc, api suite.
- Unverified: real-data visual (AC-14).
- Classification: **Keep in active/testing** until RFC-6.
- Next: RFC-6 Stage 0 (Playwright spec + seeded E2E), which uses the test ids above.

## Forward Preview
### Test Infra Found
- `web/test/mocks/onchain-lightweight-charts.ts` is the mock to use for any onchain component test. Import `markerCalls` to assert markers.
### Blast Radius Changes
- New: `web/{app/onchain,components/onchain}/`, `web/lib/{types,api}/onchain.ts`, `web/lib/onchain-view-model.ts`.
- Additive: `web/app/page.tsx`, `web/lib/format-unavailable-reason.ts`.
### Commands to Stay Green
- `cd web && pnpm test`
- `cd web && pnpm exec tsc --noEmit`, then `git checkout web/tsconfig.tsbuildinfo`
- `uv run --project api pytest api/ -q`
### Dependency Changes
- None. The lightweight-charts v5 `createSeriesMarkers` and `PriceScaleMode` exports are already in the installed package.

## API suite
`uv run --project api pytest api/ -q` → **511 passed, 5 deselected** (unchanged from the RFC-4 baseline).
