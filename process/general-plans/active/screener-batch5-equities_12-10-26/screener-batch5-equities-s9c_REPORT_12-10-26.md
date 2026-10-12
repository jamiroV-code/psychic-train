# T47 S9C worker report: /equities page by parameterised reuse

## 1. Task ID

T47, batch 5, slice S9C. Branch `claude/t47-s9c-equities-page` from main `23d7e43`.

## 2. Outcome

PASS. G-S9C-1..5 pass on code SHA `d72aefd`; seeded e2e guard ran on that SHA (31 passed). AC-S9C-1..6 covered.

## 3. Summary

- `ScreenerVariant` (`web/lib/screener-variant.ts`): `CRYPTO_VARIANT` carries today's literals (five timeframes, coin, `CAP_MESSAGE`, drill-down 4h); `EQUITIES_VARIANT` is 1d/1w, ticker, the server's equities cap text, drill-down 1d, `dateOnlyBars: true`. `countText()` for group counts.
- `VariantProvider` / `useVariant()` in a `"use client"` module; no provider means crypto.
- Board, panel, group, drill-down, add form and `ChartFreshness` read the variant: toolbar and default timeframe, loading/empty text, chips, group count/empty text, drill-down toggle and default, add-form labels/count/cap text, date-only caption and chip title.
- `web/lib/equities-freshness.ts`: `Latest daily bar 2026-10-09`, `Latest weekly bar, week of 2026-10-05`, ` (forming)`, chip title `1d candle from 2026-10-09`; date read from the ISO string, no clock.
- Client factories `createScreenerClient(base)`, `createWatchlistClient(base)`, `createLayoutClient(section)`, `createStatusFetcher(path)`; old named exports kept, bound to crypto paths, same errors and timeouts; `export function fetchChartView` kept.
- `web/lib/api/equities.ts`: module-level constants bound to `/api/equities`, section `equities`, `/api/equities/status`.
- `EquitiesScreener`: VariantProvider + LiveProvider(equities status, 60 s default) + FreshnessStrip + private-use note + ScreenerBoard with the equities clients. `/equities` server page (`title: "Equities"`, `<h1>Equities</h1>`). AppNav link after Screener. No BtcLegChart.

## 4. Files

22 (11 new, 11 edited), all in the S9C Owned list, plus this report.
New: `web/lib/screener-variant.ts`, `web/lib/equities-freshness.ts`, `web/lib/api/equities.ts`, `web/components/screener/VariantProvider.tsx`, `web/components/equities/EquitiesScreener.tsx`, `web/app/equities/page.tsx`, tests `web/lib/__tests__/{screener-variant,equities-api,equities-freshness}.test.ts`, `web/components/screener/__tests__/ScreenerVariant.test.tsx`, `web/components/equities/__tests__/EquitiesScreener.test.tsx`.
Edited: `web/components/screener/{ScreenerBoard,CoinPanel,CoinGroup,DrillDownView,AddCoinForm}.tsx`, `web/components/chart/ChartFreshness.tsx`, `web/lib/api/{screener,watchlist,layout,refresh}.ts`, `web/components/shell/AppNav.tsx`.
No existing test file edited; no forbidden file touched.

## 5. Commits

- `d72aefd` feat(equities): /equities page by parameterised reuse (T47 / S9C)
- report commit (this file)

## 6. Tests run (SHA, UTC)

| Gate | SHA | Time (UTC) | Result |
|---|---|---|---|
| Red run, G-S9C-1 paths on stubs | `23d7e43` + stubs | 2026-10-12T07:47 | 46 failed in 5 files (expected 46) |
| G-S9C-1 new files | `d72aefd` | 2026-10-12T07:51 | 46 passed in 5 files |
| G-S9C-2 crypto vitest guard | `d72aefd` | 2026-10-12T07:51 | 400 passed in 50 files; every pre-existing test file unedited |
| G-S9C-3 full vitest | `d72aefd` | 2026-10-12T07:52 | 446 passed in 55 files |
| G-S9C-3 tsc | `d72aefd` | 2026-10-12T07:52 | exit 0 |
| G-S9C-3 build:islands | `d72aefd` | 2026-10-12T07:52 | exit 0 |
| G-S9C-4 seeded e2e crypto guard (screener, layout, live-refresh, contrast, brussels-time) | `d72aefd` | 2026-10-12T07:52-07:53 | 31 passed (10+7+4+7+3) |
| G-S9C-5 api untouched, S-secret, diff --check, FORBIDDEN, FIXTURES, S9C-scope, S9-words, S9-utc, S9-nostore, S9-clock | `d72aefd` | 2026-10-12T07:54 | all print nothing; diff --check exit 0 |

Arithmetic: vitest 400 + 46 = 446 in 55 files (matches plan). Per file: variant 6, equities-api 12, equities-freshness 6, ScreenerVariant 14, EquitiesScreener 8.

## 7. Tests NOT run

- pytest: not run by design (no api change; G-S9C-5 api scan prints nothing).
- Equities e2e (`/equities` route in Playwright): S9D scope, not this slice.

## 8. Deviations

- `ScreenerVariant` has one field beyond the plan's list: `listName` ("the watchlist" / "the equities list"), used only by the empty-board line so the crypto text stays byte-identical without branching on `id`.
- `ChartFreshness` takes an optional `timeframe` prop (CoinPanel and DrillDownView pass it) so the date-only caption can say weekly vs daily. Crypto callers render as before.
- The add-form label is built from the variant noun (`Coin symbol` / `Ticker symbol`); crypto output unchanged.

## 9. Blockers

None.

## 10. Follow-up

- S9D: e2e for `/equities` (contrast route, spaghetti, drill-down).
- S9E: equities-specific strip text (last bar date, next expected refresh); this slice reuses `FreshnessStrip` unchanged, so the strip shows the generic refresh wording against `/api/equities/status`.
- The board section keeps `aria-label="Screener board"` on the equities page (not a heading; unchanged to keep crypto output identical).

## 11. Context cost

Read: CLAUDE.md, the envelope, plan lines 11, 30-66, 108-122, 155-189 (AC-S9C rows only, by grep), 242-269. Code read: the 11 edited files, LiveProvider, FreshnessStrip, chart-freshness, layout-state (grep), live-poll (grep), api/routers/equities.py, api/analytics/equities_board.py (to match date-only timestamps), two existing tests for patterns. No operating-instructions.md. No subagents used. Spend: measured by the planner.
