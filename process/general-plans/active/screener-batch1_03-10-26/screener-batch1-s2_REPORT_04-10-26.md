# T34 / S2 current-candle chips and chart labels: worker report (04-10-26)

## 1 Task ID

T34 (screener batch 1, slice S2: current-candle gain chips and chart labels). Branch `claude/t34-s2-chips-labels`, from `main` 161e7be (S1 merged, PR #34).

## 2 Outcome

done (status `review`). Gates G-S2-1 to G-S2-10 pass on 67038b1 (code head; this report commit only adds this file). P-S2-1 is a user-PC probe and is not claimed. The U3 spike passed at step 1, so AC-S2-3r is not held at review by fallback 3 (see heading 9). Not merged.

## 3 Summary

- **Contract (additive):** `GainChip {pct, open_ts, is_partial, stale, reason}` in `api/models/screener.py`. `CoinPanel.gain_by_timeframe: dict[Timeframe, GainChip]` defaults to `{}`. `percent_change_by_timeframe` stays and is filled from each chip's `pct`. The TS mirror (`GainChip`, `CoinPanel.gain_by_timeframe: Record<Timeframe, GainChip>`) moves in lockstep.
- **Formula:** `api/analytics/indicators/gain.py` is the single source of truth. A chip is the newest bar of its timeframe, `(close - open) / open x 100`. `open_ts` is that bar's open (with `Z`), and `is_partial` and `stale` come from `freshness` against the skew-corrected reference time.
  - 1w: the newest bucket of `ccxt_adapter._derive_weekly_from_daily`. It is N/A (`insufficient-history`) unless that bucket's Monday row exists and has a non-NaN open. Staleness is judged on the newest daily bar.
  - N/A with a reason, never 0, for: an empty frame (reason taken from the adapter status), a NaN or non-positive open, a NaN close, or a non-finite result. A flat candle reads a real 0.0.
- **Removed:** `compute_percent_change`, `compute_percent_change_by_timeframe` and `PCT_CHANGE_MIN_BARS` from `momentum.py`, and the golden test that covered them.
- **Board:** `build_coin_panel` builds the chips from the five frames it already fetches.
- **Web axis:**
  - `chart-time-format.ts` is pure. It formats with `Intl.DateTimeFormat` in `timeZone: "UTC"` and generates its own UTC-aligned ticks: whole UTC steps, weeks on Mondays, months on the 1st. No d3 import, because `@types/d3-scale` is absent and `package.json` is not owned.
  - The `simple-lines` island takes an optional `timeframe`. With it, the axis uses `scaleUtc` plus `ticks` (a `Date[]`) and `format` from `utcAxis`. Without it, the axis is the old `scaleTime` with `ticks={4}`, so `RelativePerformanceChart` is unchanged.
  - `MiniChart` and `island-loader` forward the optional prop. `ScreenerBoard` passes `board.timeframe` to `CoinPanel`, and `DrillDownView` passes `view.timeframe`.
- **Caption:** `chart-freshness.ts` and `ChartFreshness.tsx` render, for example, `Last bar 2026-10-03 14:15 UTC, opened 7 min ago (forming)` (closed: `..., 22 min ago`). Age is measured from the bar's open against the payload `server_time`. A plain `stale` marker (`data-testid="stale-marker"`) appears under the chart in the coin panel and the drill-down.
- **Chips:** they read `gain_by_timeframe`. An N/A chip carries `data-reason` and a title with the reason copy.
- **E2E test 4:** every chip value is `N/A` or matches `^[+-]?\d+\.\d%$`, `chart-unavailable` is still visible, and the API's `gain_by_timeframe` for THIN has a `pct` or a `reason` for every timeframe (D8). The edit stays inside test 4; the response type is cast locally.

## 4 Files changed

New: `api/analytics/indicators/gain.py`, `api/tests/analytics/test_gain.py`, `api/tests/routers/test_screener_gain_contract.py`, `web/lib/chart-time-format.ts`, `web/lib/chart-freshness.ts`, `web/components/chart/ChartFreshness.tsx`, `web/lib/__tests__/chart-time-format.test.ts`, `web/lib/__tests__/chart-freshness.test.ts`, `web/components/chart/__tests__/ChartFreshness.test.tsx`.

Modified:
- `api/analytics/indicators/momentum.py`: deletions only.
- `api/analytics/screener_board.py`
- `api/models/screener.py`
- `api/tests/analytics/test_momentum.py`: golden test and import removed.
- `api/tests/routers/test_screener.py`
  - `_df`: open = previous close.
  - The ETH bearish base goes from 50 to 500, so no price goes non-positive. A non-positive open is an N/A chip, so the old base would have made ETH's 1d chip N/A, not negative.
  - Added `gain_by_timeframe` assertions; the thin-slot test still asserts `None`.
- `web/lib/types/screener.ts`, `web/lib/island-loader.ts`, `web/islands/simple-lines.svelte`, `web/components/chart/MiniChart.tsx`
- `web/components/screener/CoinPanel.tsx`, `DrillDownView.tsx`, `ScreenerBoard.tsx`
- `web/components/screener/__tests__/ScreenerBoard.test.tsx`, `DrillDownView.test.tsx`
- `web/e2e/screener.spec.ts`: test 4 only.

All of these are on the S2 Owned list (the S2-scope command prints nothing).

## 5 Commits

- 4b68b79 T34 S2: current-candle gain chips and UTC chart labels
- 67038b1 T34 S2: NaN Monday open and non-finite pct give N/A; contract test derives TS types from the model
- (this report)

## 6 Tests run

Baseline at 161e7be (step 1, 2026-10-04T01:54Z): pytest 931 passed, 2 skipped, 5 deselected, 0 xfailed; vitest 223 passed in 30 files; tsc exit 0; islands exit 0. The web deps first needed `pnpm install --frozen-lockfile` inside `web/`; no lockfile changed.

Red run (TDD stubs on the base code, 161e7be + stubs, 2026-10-04T01:59:45Z): G-S2-1 gave 13 failed, 19 passed (11 `test_gain` and 2 contract stubs raising NotImplementedError). The three new vitest files gave 3 failed.

Final runs, SHA 67038b1:

| Gate | UTC | Result |
|---|---|---|
| G-S2-1 | 2026-10-04T02:09:33Z | 31 passed, 0 failed; `test_gain.py` 11 + contract 2 collected (13); `test_percent_change_by_timeframe_golden_values` absent (grep count 0) |
| G-S2-2 | 2026-10-04T02:10:04Z | 943 passed, 2 skipped, 5 deselected, 0 xfailed = baseline 931 + 12 |
| G-S2-3 | 2026-10-04T02:09:36Z | 33 files, 245 tests passed; `RelativePerformanceChart.test.tsx` untouched, 9 passed |
| G-S2-4 | 2026-10-04T02:09:48Z | TZ=Pacific/Kiritimati: 1 file, 10 tests passed |
| G-S2-5 | 2026-10-04T02:09:49Z | tsc exit 0 |
| G-S2-6 | 2026-10-04T02:09:54Z | `pnpm build:islands` exit 0 |
| G-S2-7 | 2026-10-04T02:10:00Z | `git diff --check` exit 0; S2-scope and FORBIDDEN print nothing |
| G-S2-8 | 2026-10-04T02:12:55Z | screener.spec.ts 7/7 passed (the command as written also ran every other spec: 63/63 passed, see heading 8) |
| G-S2-9 | 2026-10-04T02:10:00Z | S2-dangling prints nothing |
| G-S2-10 | 2026-10-04T02:10:00Z | FIXTURES prints nothing |

Full-suite budget: two full pytest runs (baseline, G-S2-2). Fix cycles used: 1 (reviewer findings, heading 10), within the budget of 2.

## 7 Tests NOT run

- P-S2-1 (user PC: live BTC chips against the exchange candle; UTC ticks, caption and `stale` marker after stopping the API). Not claimed.
- AC-S2-5 (chips equal the exchange chart) rests on P-S2-1.

## 8 Deviations

- G-S2-8: `pnpm test:e2e -- screener.spec.ts` passes the literal `--` through to Playwright, which then runs every spec, not only screener.spec.ts. All 63 passed. This is recorded, not changed: the gate command is the planner's.
- The tick helper is a small hand-rolled UTC tick generator in `chart-time-format.ts`, not d3's `scaleUtc().ticks()`, because `@types/d3-scale` is not a dependency and `package.json` is not owned. The island still uses d3's `scaleUtc` as the scale.
- `ETH` fixture base in `test_screener.py` changed from 50 to 500 (heading 4). The momentum and trend assertions still hold (FAIL, down).
- The reason mapping in `gain.py` also maps adapter status `stale` with no data to `source-unavailable`. This mirrors `screener_board._STATUS_TO_REASON`; the plan names only `bad_symbol`/`unavailable`. It only applies to empty frames.

## 9 Blockers

None.

U3 spike outcome: **step 1 succeeded; no fallback applied.** After implementing the UTC axis, `pnpm build:islands` gave exit 0. I then ran a throwaway spec (not committed, deleted) against the seeded E2E stack with the chromium-1194 path and read the PNGs:
- Board, 1d chart: x labels `Jul 25`, `Jan 26`, `Jul 26` (span over 365 days, `MMM YY`).
- Board, 1h chart: `30 Sep`, `02 Oct`, `04 Oct` (day-boundary ticks, `DD MMM`).
- Drill-down, 4h: `21 Sep`, `28 Sep` (Monday-aligned).
- The caption appears under each chart.

LayerChart's `Axis` took the `format` function and the `ticks` array with `scaleUtc`. No backlog stub was written. Cosmetic: the rightmost tick label can clip at the plot edge (for example `04 Oc`). That is axis layout, left for S6 with B8. AC-S2-3r remains an Agent-Probe; P-S2-1 (2) still confirms it on the PC.

## 10 Follow-up

The read-only reviewer reported no blocking defects. Fixed in 67038b1:
1. A NaN Monday open made the 1w chip silently use Tuesday's open. Now N/A, with a test case in `test_chip_1w_without_monday_bar_is_na`.
2. A non-finite pct (`close=inf`) is now N/A, tested in `test_nan_or_zero_open_is_na`, along with an unsorted-frame case.
3. The contract test now keeps the TS optional marker and derives the expected TS types from the pydantic annotations, so drift on either side fails it.

Left as is, for the planner:
- `server_time` (raw host now) vs the skew-corrected reference used for `is_partial`/`stale`. This predates S2 (S1 `_chart_series` does the same); the caption may disagree slightly only when skew is non-zero.
- `gain_by_timeframe` defaults to `{}` in Python, while TS declares it required. The board always fills all five keys; the default exists only to keep the change additive for direct constructors.
- `test_percent_change_by_timeframe_equals_chip_pct` proves wiring and serialization, not the values; the values are proven in `test_gain.py`.
- The island's no-timeframe path (old axis) has no unit test. It is covered indirectly by the unchanged, green `RelativePerformanceChart` vitest and e2e test 7.

## 11 Context cost

Files loaded: CLAUDE.md, the envelope, plan lines 36-56, 97-128, 270-276, 308-323, 353-371 and 391-396, and the S1 report headings (for the template only). operating-instructions.md was not opened.

Subagents (capped lane, 1 of 3): one `vc-code-reviewer` (sonnet), read-only, covering Python/TS lockstep and coverage honesty. About 77k tokens, 15 tool uses. No `vc-tester` was spawned: the worker ran every gate once after its last code edit (heading 6).
