---
name: report:chain-growth-rfc-005-stage0
description: "RFC-5 Stage 0 — /onchain frontend design proposal against the implemented RFC-4 contract"
date: 25-09-26
metadata:
  node_type: memory
  type: report
  feature: onchain-activity
  phase: RFC-5-stage0
---

# RFC-5 Stage 0 — `/onchain` frontend design

**TL;DR:** The implemented RFC-4 API supports every approved decision with no backend change. One real
design constraint: the comparison is rebased server-side at `start`, so changing the visible range must
**re-fetch with `?start=`**. It must not rebase in TypeScript, because Python computes and TS only
renders. Three decisions are needed from the user: the route name, the default range, and the Robinhood
comparison default. No source or test files were changed.

## 1. Contract confirmed (implemented, not the plan draft)
- `GET /api/onchain/growth?metric=active_addresses|transactions&start=YYYY-MM-DD` returns `OnchainGrowthResponse`:
  - top-level fields: `generated_utc, metric, grid_dates, attribution, params, chains[], comparison`.
  - `ChainGrowth` fields: `id, label, launch_date, limited_history, status (ok|stale|unavailable), unavailable_reason, history_start_date, series, floor_ramp, cross_check`.
  - `series` fields: `source, method, attribution, redistributable, max_gap_days, last_as_of_utc, points[{date, value, ema7, ema28, gap_before, pre_launch}]`.
  - `floor_ramp` fields: `state (not-enough-history|floor|ramping|declining|neutral), events[{floor_date, ramp_date}], min_history_days, history_days, gate_met_on`.
  - `cross_check` fields: `source:"l2beat", redistributable, display_only, latest_common_date, latest_divergence_pct, median_abs_divergence_pct_90d`. It is present only for `transactions`.
  - `comparison` fields: `normalization_method, alternative_method, start_date, log_scale_default, series[{chain_id, rebase_date, rebased_late, index_values[], pct_above_low_values[]}]`. The arrays align to `grid_dates`, and there is no raw-value field.
- `GET /api/onchain/chains` returns `{chains:[{id,label,enabled,launch_date,limited_history,metrics[{metric,source,unavailable_reason}],cross_check_source}]}`.
- The page shows 6 live chains (ethereum, base, arbitrum, optimism, polygon, robinhood) and 3 unavailable ones (solana, bnb, tron → `source-unavailable`). Disabled chains are omitted by the API.
- The attribution string is `"Source: growthepie, https://www.growthepie.com."`. It comes from the payload's `attribution` field, so it matches RFC-1's text verbatim (E6).

## 2. Page wireframe
```
[H1 On-chain participant growth]   Metric: (Active addresses | Transactions)   Range: [6M][1Y*][2Y][All]
[Method note — visible text: "Daily values from growthepie; EMA7/EMA28 smoothing; floor = 180-day low,
 ramp = +25% sustained 14 days (params from API). Not comparable across chains in raw units."]
[Stale banner if any chain status=stale: "Data for X last updated N days ago"]

== Comparison (normalised) ==========================================
 Toggle: (Index = 100 at range start* | % above 180-day low)   [x] Log scale (default from API)
 One overlay chart, 6 lines, legend with chain colour + "rebased late (DATE)" tag where rebased_late
 Caption: normalization_method / alternative_method in plain words
======================================================================

== Per-chain panels (grid 2 or 3 columns, raw values, own y-axis) ====
 [Ethereum]  source: growthepie · method: unique addresses/UTC day   [state: Near floor|Ramping|…]
   chart: raw value (thin) + EMA28 (bold); pre-launch band shaded; floor ▼ / ramp ▲ markers
   readout on hover: date, raw, EMA7, EMA28   · L2BEAT check: -0.05% (90d median |%| 0.05) [tx only]
   badges: Personal-use only (if !redistributable) · Stale (if status=stale)
 [Robinhood Chain]  "Limited history — floor/ramp markers from 2027-01-10" (from gate_met_on)
 … Base, Arbitrum, Optimism, Polygon
 [Solana] [BNB Chain] [Tron]  -> "Source unavailable" cards, no chart, no zero
======================================================================
Footer: Source: growthepie, https://www.growthepie.com.  (link; CC BY 4.0)  · L2BEAT used as display-only cross-check
```

## 3. Components (`web/components/onchain/`)
| Component | Role |
|---|---|
| `OnchainDashboard` | Fetches data (with an injected `fetchData(metric, start)` for tests). Owns the metric, range and comparison-mode state, the sync object, and the loading, error and empty states. |
| `MetricSelector`, `RangePicker` | Controlled inputs. A range change re-fetches with `start`. |
| `ComparisonOverlay` | Its prop type is `ComparisonSeries[]`, with no raw field, so AC-13 is enforced at the type level. It has the index/pct toggle, the log toggle and the `rebased_late` legend tag. |
| `ChainPanel` | Draws the raw value and EMA28 lines on its own axis. It adds a pre-launch shaded band, floor and ramp markers, and a hover readout. It uses `toSegmentedSeriesData` to break lines at `gap_before`. |
| `FloorRampStateLabel` | Maps the state to a label. It shows "Near floor" only when the API state is `floor` (D3 is already applied server-side), and "Not enough history" when the gate has not been met. |
| `SourceMethodBadge` | Shows the source and method as visible text on the panel header, not only on hover (AC-2). |
| `LimitedHistoryFlag` | Shows the Robinhood copy, using `gate_met_on`. |
| `CrossCheckNote` | Shows the L2BEAT divergence as display-only text. It renders nothing when the field is null. |
| `UnavailableChainCard` | Shows the chain label and the reason copy. |
| `SourceAttributionFooter` | Renders `response.attribution` as a link once, whenever any growthepie series is shown (E6). |

Reused as-is: `RedistributionBadge` (narrative), `regime-chart-sync.ts`, `regime-line-segments.ts`.

Lib files: `web/lib/api/onchain.ts`, `web/lib/types/onchain.ts` (hand-mirrored from the pydantic models), and `web/lib/onchain-view-model.ts`. The view model is a pure mapping from the response to panel and overlay props, with no maths beyond mapping `grid_dates` to times. `format-unavailable-reason.ts` gains an additive `formatOnchainReason` sibling covering `source-unavailable`, `no-archived-data`, `stale` and unknown codes shown verbatim. This follows the narrative precedent, where a sibling function was added instead of widening the screener union.

## 4. Technical decisions (made here)
- **Sync:** the per-chain panels sync time range and crosshair with each other, using `createChartSync` on `grid_dates` as in the regime precedent. The comparison overlay is **not** in the sync group. Its range is the fetched window starting at `start`, and a different y-meaning (index) would confuse a shared readout.
- **Range picker:** the options are 6M / 1Y / 2Y / All, and the default is **1Y**, matching the API's `DEFAULT_RANGE_DAYS=365`. A range change does two things:
  - it re-fetches `?start=`, so the rebase happens in Python;
  - it sets the panels' visible range.
  - "All" sends `start` = the first grid date, so every chain is `rebased_late` at its own first point. The chart labels this.
  - The metric switch re-fetches. The previous data stays shown with a "Loading…" overlay, so the page does not blank.
- **Log scale:** the initial value is `comparison.log_scale_default` (true), using the lightweight-charts `PriceScaleMode.Logarithmic`. No precedent exists in the repo, so this is new. In `% above 180-day low` mode, log is forced off and the toggle is disabled, because the values can be 0. The API already returns null for non-positive index values.
- **Pre-launch shading:** only Polygon has pre-launch points on the real cache (launch_date 2020-05-30), but the rule is general.
  - Points with `pre_launch` are drawn in a muted grey line.
  - A band marks the pre-launch period.
  - EMA lines start at the launch date, because the API returns null for pre-launch EMAs.
- **Markers:** floor ▼ and ramp ▲ series markers are taken from `floor_ramp.events`. They are never computed in TS.
- **Colours:** stable per chain, keyed by chain `id` in a constant map. Six categorical hues from an Okabe-Ito-style colour-blind-safe set: ethereum `#0072B2`, base `#56B4E9`, arbitrum `#009E73`, optimism `#D55E00`, polygon `#CC79A7`, robinhood `#E69F00`. The panel header uses the same colour, so the overlay and the panels link visually. The **`dataviz` skill was not found** in `.claude/skills` or on disk, so this choice follows general colour-blind-safe guidance, not the skill.
- **States:**
  - loading: `onchain-loading`.
  - fetch error: `onchain-error`, with a retry button.
  - every chain unavailable: `onchain-empty`.
  - per chain `stale`: an amber badge "Stale — last updated N days ago", computed from `last_as_of_utc`. The number of days is display arithmetic on a timestamp, not an analytic.
  - an overlay series that is null throughout the range: a legend entry "no data in range".
- **Home link:** add `<Link href="/onchain" data-testid="home-link-onchain">Open the on-chain growth dashboard</Link>` to `web/app/page.tsx`. This is additive.

## 5. Vitest list (injected-fetcher fixtures, `web/components/onchain/__tests__/`)
1. The dashboard renders 6 panels and 3 unavailable cards. No card shows a numeric zero.
2. The metric switch calls `fetchData` with `transactions`. A range change calls it with the expected `start`.
3. `SourceMethodBadge` text is visible in the DOM without hover (AC-2).
4. The attribution footer shows the exact text and href. It is absent when no growthepie series is present.
5. For Robinhood, the limited-history copy includes `2027-01-10` from the fixture's `gate_met_on`.
6. The state label maps each of the 5 states. "Near floor" appears only for `floor`.
7. The overlay starts in log mode when `log_scale_default` is true. The pct toggle disables log. Series with `rebased_late` show the tag.
8. A type-level AC-13 check: a `@ts-expect-error` test that passing raw points to `ComparisonOverlay` fails tsc.
9. The stale badge renders for `status=stale`. `RedistributionBadge` renders when `redistributable=false`.
10. The cross-check note renders only for tx fixtures and is labelled display-only.
11. The view model: `gap_before` produces a line break, pre-launch points split out, and markers map from events (in `web/lib/__tests__/onchain-view-model.test.ts`).
12. `formatOnchainReason` cases.

The gates are `pnpm --filter web test` and `pnpm --filter web exec tsc --noEmit`.

## 6. data-testids for RFC-6 Playwright
`onchain-dashboard`, `onchain-loading`, `onchain-error`, `onchain-empty`, `onchain-metric-{active_addresses|transactions}`, `onchain-range-{6m|1y|2y|all}`, `onchain-method-note`, `onchain-stale-banner`, `onchain-comparison`, `onchain-comparison-mode-{index|pct}`, `onchain-comparison-log-toggle`, `onchain-legend-{id}`, `onchain-rebased-late-{id}`, `onchain-panel-{id}`, `onchain-panel-{id}-source`, `onchain-panel-{id}-state` (with `data-state`), `onchain-panel-{id}-readout`, `onchain-panel-{id}-limited-history`, `onchain-panel-{id}-stale`, `onchain-panel-{id}-redistribution`, `onchain-panel-{id}-crosscheck`, `onchain-unavailable-{id}`, `onchain-attribution`, `home-link-onchain`. Charts also expose `data-visible-range` via `visibleRangeAttribute`, as in the regime precedent.

## 7. Plan-text conflicts (the reports and the task override the plan; within blast radius)
1. **Route and folder names:** the plan says `/onchain-activity` and `components/onchain-activity/`, and the task says `/onchain`. The API prefix is `/api/onchain`. Proposed: `/onchain` and `onchain` names everywhere. **This needs the user's confirmation (Q1).**
2. **Metrics:** the plan says 3 metrics (AC-1) and a Dune `new_addresses` metric. Under the locked fallback (E4), only 2 metrics exist. AC-1 renders the 2 that exist, and new addresses are absent, not shown as unavailable.
3. **Polygon:** the P2 fallback listed Polygon as unavailable, but RFC-2..4 source it from growthepie (D4 launch date). The implemented reality wins, so Polygon gets a live panel.
4. **Plan-named `UnavailableReason` variants** (`dune-credit-exhausted`, `insufficient-history`) are not emitted by the API. Only a sibling formatter is added.
5. **The plan's `DrillDown` component is folded into the `ChainPanel` hover readout.** The raw value, EMA7 and EMA28 are shown on hover, which is AC-5. The regime DrillDown drawer adds no data here. This is a reversible technical call. If a drawer is wanted, it is one extra component.
6. **Rebase location:** the task says "index=100 at the visible-range start". This is implemented as a re-fetch with `start`, not a client-side rebase.

## 8. Decisions needed from the user
- **Q1: route.** Use `/onchain` (recommended, matching the task and the API prefix) or the plan's `/onchain-activity`?
- **Q2: default range.** 1Y (recommended, the API default) or 2Y? With 1Y, Robinhood is `rebased_late` in both options, because it launched on 2026-07-01.
- **Q3: Robinhood in the overlay.** Include it with the `rebased late` tag (recommended; this is honest) or hide it by default until 2027-01-10?

## Closeout
- Files written: this report only. No source or test edits.
- Open items: `CONTEXT_PARTIAL: dataviz skill` was not found, so the palette choice rests on general guidance. RFC-4's `harness/rfc-004/review-decision.json` is still PENDING, and that is not an RFC-5 blocker.
- Next: the user answers Q1–Q3, then RFC-5 implementation starts. The strategy is a single sequential opus agent. Parallel subagents are not worth it, because the components share the view model and types.
