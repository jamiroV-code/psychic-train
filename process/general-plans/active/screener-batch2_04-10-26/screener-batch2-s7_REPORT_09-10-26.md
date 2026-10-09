# T38 / S7 report: BTC leg chart, D-14 estimate, regime cache-only fix

## 1 Task ID

T38, batch 2, slice S7. Branch `claude/t38-s7-btc-leg-chart` from `main` at 8858469 (S6 merge). Code commit 7e824e8.

## 2 Outcome

**needs_input.** Every G-S7 gate that covers this slice's own code passes: G-S7-1..7 and G-S7-9, and the new Playwright test. G-S7-8 is red on one EXISTING test: `screener.spec.ts` "ctrl-wheel zooms, drag pans, double-click resets, plain wheel does not zoom" (S6). This slice's layout change causes it, and the test is not in the slice's "Existing tests that break" table (none expected). Per gate convention 6 and the envelope I did not edit it; see heading 9 for the cause and the options. P-S7-1 (live PC check) stays a user probe.

## 3 Summary

- `api/analytics/regime/btc_legs.py` (new): `build_btc_leg_chart(as_of)` and a pure `assemble_btc_leg_chart(inputs, now)`. Bars = every cached BTC `1d` bar, with first bar, last bar and count. Legs run from a confirmed boundary's `date` to the next confirmed boundary, and the current leg runs to the last bar. The stretch before the first confirmed boundary is not a leg, and unconfirmed candidates never start one. Estimate heading `Estimate (rule over the numbers shown)`, with two labels that are never merged:
  - AGE uses integer comparisons on twice the median (`6a < 2m`, `6a < 4m`, exact for half-day medians) and needs 3 earlier completed legs, else N/A with the count.
  - COMPOSITE uses the latest `diff(14)` against T = 0.5 x `Series.std()` (ddof 1, NaN dropped). A NaN std (fewer than 2 changes), std = 0 (advisory k) or a missing composite gives N/A with a reason, never `flat`.
  - Rule strings are written in Python only. Every input (age_days, median_days, ratio, earlier lengths; change_14d, T, std, n, composite date) is in the payload.
- `leg_boundary.py`: `_leg_inputs(as_of, *, always_read_btc=False)` returns `LegInputs` (variant, composite, candidates, confirmations, BTC result). `compute_current_leg_state` uses it and behaves as before; for example, BTC is not read when the composite is unavailable, unless the chart asks. `liquidity_composite` and `ccxt_adapter` are still module attributes, and the legs path reads only `.df`.
- `routers/regime.py`: new `GET /api/regime/btc-legs`. It and `/legs` run inside `reads_cache_only_if_running()` (C8, S8 open item a). Accepted residual: FRED and DefiLlama may still fetch on TTL expiry.
- `api/models/regime.py`: new response models (`BtcLegChartResponse` and children), closed enums `AgeLabel`, `CompositeChangeLabel`. `web/lib/types/btc-legs.ts` mirrors them by hand; a contract test parses every `export interface`.
- Web:
  - `BtcLegChart` sits above the board. It has its own fetch (injectable `fetchData`), states its span (`Daily BTC, <first> to <last> UTC, <n> bars (all cached history)`), and shows the current-leg readouts (`btc-current-leg-*`) and `LegEstimate` (`leg-estimate`).
  - The island uses `timeframe="1d"` and the S6 zoom and pan, plus additive `bands` (two alternating tints) and `markers` on `simple-lines.svelte`.
  - `btc-leg-lines.ts` holds the pure builders.
- No backfill code (Q6).

## 4 Files changed

All inside Owned (the S7-scope command prints nothing): `api/analytics/regime/{btc_legs,leg_boundary}.py`, `api/routers/regime.py`, `api/models/regime.py`, `api/tests/analytics/test_btc_legs.py`, `api/tests/routers/test_btc_legs_router.py`, `web/lib/types/btc-legs.ts`, `web/lib/api/regime.ts`, `web/lib/btc-leg-lines.ts`, `web/lib/island-loader.ts`, `web/islands/simple-lines.svelte`, `web/components/screener/{BtcLegChart,LegEstimate}.tsx`, `web/components/screener/__tests__/BtcLegChart.test.tsx`, `web/lib/__tests__/btc-leg-lines.test.ts`, `web/app/screener/page.tsx`, `web/app/globals.css`, `web/e2e/screener.spec.ts` (one new test appended, no existing test edited), and this report.

## 5 Commits

- 7e824e8 feat(screener): T38 S7 BTC leg chart, D-14 estimate, cache-only regime reads
- (this report) docs(process): T38 S7 worker report

## 6 Tests run

| Gate | SHA | UTC | Result |
|---|---|---|---|
| Red, G-S7-1 on stubs (untouched base) | 8858469 | 2026-10-09T06:52:10Z | 17 failed (all NotImplementedError stubs) |
| Red, vitest on stubs | 8858469 | 2026-10-09T06:52:38Z | 12 failed, 239 passed (251) in 34 files (2 failed, 32 passed); baseline 239 in 32 confirmed |
| Red, full pytest on stubs | 8858469 | about 06:55Z | 17 failed, 934 passed, 2 skipped, 5 deselected; baseline 934 confirmed |
| Behavioural red: both cache-only tests against the base `routers/regime.py` | 8858469 + new code | 2026-10-09T06:55:57Z | 2 failed: `assert ['exchange'] == []` for `/btc-legs` and `/legs` |
| G-S7-1 | 7e824e8 tree | 2026-10-09T07:01:08Z | 17 passed |
| G-S7-2 | 7e824e8 tree | 2026-10-09T07:03:22Z | 951 passed, 2 skipped, 5 deselected, 0 xfailed; `test_leg_boundary.py` 13 passed unedited, `test_legs_shape_unchanged` passed |
| G-S7-3 | 7e824e8 tree | about 06:59Z | 251 passed in 34 files |
| G-S7-4 tsc | 7e824e8 tree | about 06:59Z | exit 0 |
| G-S7-5 build:islands | 7e824e8 tree | about 06:59Z | exit 0 |
| G-S7-6 `git diff --check` | 7e824e8 tree | 2026-10-09T07:01:08Z | exit 0, no output |
| G-S7-7 S7-scope, FORBIDDEN, S-secret-scan | 7e824e8 | 2026-10-09T07:01:25Z | print nothing |
| G-S7-8 seeded E2E `screener.spec.ts` | 7e824e8 tree | about 07:00Z | **9 passed, 1 failed**: the new BTC leg test passes; the S6 "ctrl-wheel zooms ..." test fails (heading 9) |
| G-S7-8 control: same test with `page.tsx` reverted to base | 8858469 page | about 07:00Z | 1 passed (proves this slice's layout change causes it) |
| G-S7-9 FIXTURES, S7-verdict-words | 7e824e8 | 2026-10-09T07:01:25Z | print nothing |

## 7 Tests NOT run

- P-S7-1 (live PC check with the real worker and real cache): a user probe, as the envelope says.
- G-S7-8 was run, but not green (heading 9).

## 8 Deviations

- Bands spike (Design 4): bands and markers are drawn as absolutely positioned elements under the plot inside `simple-lines.svelte`, not as LayerChart `Rect` marks. They are placed from the same x domain and padding the `Chart` uses, so they follow zoom and pan. Reason: the repo's scout hook blocks reading layerchart's package source, so `Rect`'s pixel and scale props could not be checked offline, and this way needs no LayerChart API. It is still option (1) in spirit (shaded bands, not the per-leg line colouring or the table fallback). `build:islands` passes; jsdom never mounts the island, so bands are proven only by G-S7-8 and P-S7-1, as the plan says.
- The chart payload carries `reason` also when `available=true` and the composite is unavailable ("composite unavailable: no boundaries can be detected"), so zero legs are always explained.

## 9 Blockers

**G-S7-8: existing S6 E2E test broken by the new layout (needs_input).**

- **Test:** `web/e2e/screener.spec.ts` "ctrl-wheel zooms, drag pans, double-click resets, plain wheel does not zoom". It fails in `exerciseZoom` on the coin-box plot: after Ctrl + wheel, `data-zoomed` is `"false"`.
- **Cause:** the BTC leg chart now sits above the board (Design 4), so the page is taller and scrolled when the coin plot is scrolled into view. The test's "plain wheel does not zoom" step (`wheel(0, -400)`) now really scrolls the page. The following Ctrl + wheel is sent at the pre-scroll coordinates `cx, cy`, which no longer lie over the plot. Before S7 the page could not scroll further up at that point, so the coordinates stayed valid. Control run: with `page.tsx` reverted to base, the test passes.
- **Not a product defect:** zoom itself works (the same helper passes on the spaghetti plot once it is reached, and S6 unit tests are green).
- **Options for the planner:**
  - (a) Sanction a one-line edit to `exerciseZoom`: re-read `plot.boundingBox()` after the plain wheel, before the Ctrl + wheel. This is the recommended fix: it removes a coordinate assumption the test should not make.
  - (b) Place `BtcLegChart` below the board instead of above it. That conflicts with the S7 Goal and Design 4, which say "screener top" and "above the board".
  - (c) Accept G-S7-8 as red for now and let P-S7-1 cover it.

**Spike result (Design 4 fallback chain):** see heading 8. Option (1)-equivalent overlay bands; AC-S7-3 rests on G-S7-8 (new test green) and P-S7-1.

## 10 Follow-up

- Resolve the G-S7-8 blocker (option a, b or c above); then re-run G-S7-8 only.
- P-S7-1 on the PC: with the real worker running, neither `/api/regime/legs` nor `/api/regime/btc-legs` calls the exchange for BTC bars, and the span line states the deep-history range actually cached.

## 11 Context cost

- Files read beyond the envelope set: none of the on-demand protocol docs. For conventions and patterns I read code only: the S6 report headings (format), `refresh_worker.reads_cache_only_if_running`, `ccxt_adapter.fetch_ohlcv`, `test_spaghetti.py` (contract-test pattern), `SpaghettiChart.tsx`, `simple-lines.svelte`, `island-loader.ts`, `globals.css` (simple-lines block), `screener.spec.ts`.
- Subagents: none spawned (capped lane unused; 0 of 3, 0 USD).
- About 55 tool calls, about 25 minutes wall time; 2 full pytest runs, 2 full E2E runs plus 2 single-test E2E runs, 0 CI polls so far.
