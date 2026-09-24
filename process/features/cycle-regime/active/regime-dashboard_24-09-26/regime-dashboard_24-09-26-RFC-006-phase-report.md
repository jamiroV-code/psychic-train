---
phase: rfc-006-end-to-end-proof
date: 2026-09-24
status: COMPLETE_WITH_GAPS
feature: cycle-regime
plan: process/features/cycle-regime/active/regime-dashboard_24-09-26/regime-dashboard_PLAN_24-09-26.md
---

# RFC-006 Phase Report — end-to-end proof

**Date**: 24-09-26
**Plan**: `regime-dashboard_PLAN_24-09-26.md` §15 RFC-006, AC-8, AC-11, Validate Contract P8
**Status**: 🔨 CODE DONE. Not ✅ VERIFIED until you run the AC-11 walkthrough below on the PC.

**TL;DR:** A real browser now proves `/regime` end to end: real page, real API client, real FastAPI
route, real adapters reading a seeded cache, no provider contacted. Playwright passed 12/12 twice
(6 new regime specs, 6 screener specs). vitest passed 75/75 five runs in a row, and the
"exactly seven charts" flake is fixed. tsc and `next build` are clean. pytest: 294 passed. What
remains is your walkthrough against the real cache.

## What's Functional Now

- `pnpm test:e2e` covers `/regime`: seven panels, 3-year default, zoom sync, hover readout, seeded
  gap, ETF not-applicable note, no console errors.
- `pnpm --filter web test` reports 0 failed files (Playwright specs no longer collected by vitest).
- Optional `PLAYWRIGHT_CHROMIUM_PATH` for machines whose installed Chromium build differs.

## What Was Done

| File | Purpose |
|---|---|
| `web/lib/regime-chart-sync.ts` | `SyncMember.element` (optional). Every range change (and the initial 3-year range) writes `data-visible-range` = `{from, to, fromDate, toDate}` on every member, source included. New export `visibleRangeAttribute` |
| `web/lib/regime-line-segments.ts` | New `lineBreakIndices(values, gapBefore)`: flagged points that have an earlier real point |
| `web/components/regime/ComponentPanel.tsx` | Passes its chart container to the sync group. Container gets `data-gap-count` / `data-gap-dates`. Data attributes only |
| `web/components/regime/__tests__/RegimeDashboard.test.tsx` | Flake fix: `waitFor` the 7 `createChart` calls (assertion still exactly 7); helper waits for charts before tests read them. 2 new tests (range attribute, gap attribute) |
| `web/lib/__tests__/regime-line-segments.test.ts` | 3 new `lineBreakIndices` tests |
| `web/vitest.config.ts` | `exclude: [...configDefaults.exclude, "e2e/**"]` |
| `web/playwright.config.ts` | `PLAYWRIGHT_CHROMIUM_PATH` → chromium `launchOptions.executablePath`, no-op when unset |
| `web/e2e/regime.spec.ts` | New: 6 specs (below) |
| `api/scripts/seed_e2e_cache.py` | New `build_regime_fixture` (pure) + `seed_regime` (writes through `cache.write_liquidity_series`, `etf_flows_adapter.merge_into_cache` / `_record_attempt("ok")`, `cache.write_liqtide_raw`, `cache.write_liqtide_payload`). Manifest gains a `regime` section |
| `api/tests/scripts/test_seed_e2e_cache.py` | New: 5 tests on the fixture's properties |
| `process/context/tests/all-tests.md` | E2E/vitest counts, `PLAYWRIGHT_CHROMIUM_PATH`, closed the vitest-collects-e2e gap |
| `process/general-plans/{backlog→completed}/vitest-config-e2e-exclude_19-09-26.md` | Marked RESOLVED and moved |
| plan | Status Strip, RFC-006 decisions 1–6, Resume handoff |

### What was seeded (isolated `SCREENER_CACHE_ROOT` only)

| Input | Shape | First date (days before today) |
|---|---|---|
| FRED `DTWEXBGS` | business days, **28-day hole starting today−400** | today−1520 |
| FRED `RRPONTSYD` | business days | today−1480 |
| FRED `WALCL` | Wednesdays | today−1460 |
| FRED `WDTGAL` | Wednesdays | today−1439 |
| DefiLlama `stablecoin_supply` | daily, UTC | today−1295 |
| Farside ETF parquet | business days from 2024-01-11 to yesterday + `YYYY-MM-DD|ok` marker for today | 2024-01-11 |
| LiqTide raw JSON + daily parquet row | last 5 days; weekly `tide_series` (2 years), daily `metrics.btc_dom.series` (450 days) | — |

All values are deterministic sine waves. FRED dates are UTC-aware, the same as `fred_adapter._parse_csv`.
The manifest (`web/e2e/.fixture-manifest.json`, gitignored) records `regime.input_first_dates`,
`regime.gap.{hole_start, hole_end_exclusive, expected_gap_date}`, `etf_first_date` and `panel_ids`.
The spec asserts against these.

## What Was Tested (exact outputs)

| Gate | Result |
|---|---|
| `PLAYWRIGHT_CHROMIUM_PATH=/opt/pw-browsers/chromium-1194/chrome-linux/chrome pnpm test:e2e` run 1 | `12 passed (32.9s)` |
| same, run 2 | `12 passed (34.2s)` |
| `pnpm --filter web test` ×5 | each `Test Files 12 passed (12)`, `Tests 75 passed (75)` |
| `pnpm --filter web exec tsc --noEmit` | clean |
| `pnpm --filter web build` | clean (`/regime` 5.5 kB); `web/tsconfig.tsbuildinfo` restored |
| `uv run --project api pytest api/ -q` | `294 passed, 2 deselected` |
| Real cache untouched | `git status api/data/cache/liqtide` clean; the only files under `api/data/cache/` are the 7 tracked ones |

The regime specs:
1. Seven panels render from a real `/api/regime/components` 200. All six components are `ok`. Every
   `last_fetched_utc` is ≤ the manifest `seeded_at`, so no provider was re-fetched.
2. Default range = the last 3 years (`fromDate` within 7 days after `last − 3y`, `toDate` = last grid
   date). All seven panels are identical.
3. A mouse wheel over the stablecoin canvas changes the range. All seven `data-visible-range` values
   then become equal and narrower.
4. Hovering the composite canvas sets `data-hovering=true` and moves the readout date to a grid date
   that is the same on every cell. Moving away returns it to the last date.
5. The API flags `gap_before` at the seeded `expected_gap_date`. No point falls inside the hole. The
   panel's `data-gap-dates` equals the API's flagged dates.
6. The ETF panel note says "Not applicable before 2024-01-11".
Every spec fails on any browser console error except the favicon 404.

## What You Can Test on the Windows PC

```powershell
git pull
cd api; uv sync; cd ..\web; pnpm install
pnpm exec playwright install chromium     # only if the e2e run says the browser executable is missing
pnpm test:e2e                             # expect 12 passed. PLAYWRIGHT_CHROMIUM_PATH is NOT needed there
pnpm test                                 # expect 12 files / 75 tests, 0 failed files
```

**AC-11 walkthrough against the real cache.** Start the API (`uv run --project api uvicorn api.main:app --port 8000`)
and the web app (`pnpm dev`), then open `http://localhost:3000/regime`:

- [ ] Default view shows about the last 3 years on all seven panels.
- [ ] Zoom (wheel) or drag one panel. All seven follow.
- [ ] Hover 3 dates and note the readout values. Compare each with
      `curl "http://127.0.0.1:8000/api/regime/components?start=YYYY-MM-DD&end=YYYY-MM-DD"` for that date
      (the `value`/`raw`/`contribution` of each component, plus reproduced/published).
- [ ] Click two panel headers. Each drill-down shows the right source, transform and weight.
- [ ] Find a real gap. BTC dominance has one from 2025-12-07 to 2026-08-03: no line should bridge it.
- [ ] Stop the API and reload. A clear "could not be loaded" notice appears, with no blank charts.
- [ ] Composite drill-down: note the published-vs-reproduced agreement numbers (overlap days, r,
      mean abs diff, full-coverage days/diff). RFC-002 measured r = 0.964.

## Deviations

1. **Seeder dates are UTC-aware.** The first seed used tz-naive FRED dates. `liquidity_composite`
   (used by `/api/regime/legs` and the screener board) then 500'd, because it merges FRED with the
   UTC DefiLlama series. The fix is in the seeder, matching the adapter's real shape. No app code
   changed. Covered by `test_fred_dates_are_utc_aware_like_the_adapter`.
2. **TGA series is `WDTGAL`, not `WTREGEN`.** The plan text names `WTREGEN`; `build_net_liquidity`
   reads `fred_adapter.TGA_WEDNESDAY` = `WDTGAL`, so that is what gets seeded.
3. **The hole produces two `gap_before` flags, not one.** The dollar impulse needs a value from 30
   days back, so change points also drop out for about a month after the hole, which makes a second
   flag. The spec asserts that the expected date is included and that the panel matches the API
   exactly. The pure pytest asserts exactly one flag on the raw series.
4. **`process/context/tests/all-tests.md` edited during EXECUTE.** This was user decision 3. The
   agent rules normally reserve context edits for UPDATE PROCESS.
5. **Flake-fix scope.** Besides the "seven createChart" test, the shared `renderDashboard` helper now
   also waits for the charts. This removes the same race from the other tests; no assertion was
   weakened.

## Test Infra Gaps Found

- If the seed runs just before 00:00 UTC and the API is queried after it, the ETF marker's date no
  longer matches "today". The adapter would then try Farside once, get a failure (no network in the
  sandbox), and report `stale`. That would make spec 1 fail. Very unlikely, and noted only.
- `@playwright/test` 1.63 expects Chromium build 1243. The sandbox only has 1194, so the sandbox
  needs `PLAYWRIGHT_CHROMIUM_PATH`.

## Closeout Packet

- Selected plan: `process/features/cycle-regime/active/regime-dashboard_24-09-26/regime-dashboard_PLAN_24-09-26.md`
- Finished: RFC-006 decisions 1–6 and the vitest flake fix.
- Verified: every automated gate above. Not verified: the AC-11 user walkthrough on the real cache.
- Classification: **Keep in active/testing** until you confirm the walkthrough.
- Nothing committed (as instructed).

## Forward Preview

- **Test Infra Found:** DOM hooks `data-visible-range`, `data-gap-dates`, `data-gap-count`. The manifest has a `regime` section.
- **Blast Radius Changes:** none beyond the files above. Adapters, `/legs`, `liquidity_composite.py`, `leg_boundary.py` and the screener components are unchanged.
- **Commands to Stay Green:** `pnpm test:e2e` (+ `PLAYWRIGHT_CHROMIUM_PATH` in the sandbox), `pnpm --filter web test`, `uv run --project api pytest api/ -q`.
- **Dependency Changes:** none.

**Ready For**: UPDATE PROCESS (after your walkthrough confirmation).
