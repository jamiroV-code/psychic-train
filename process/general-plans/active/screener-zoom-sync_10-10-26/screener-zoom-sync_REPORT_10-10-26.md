---
name: report:screener-zoom-sync
description: "T44 - small charts share one zoom; reset-zoom button removed on the small charts only"
date: 10-10-26
---
# T44 screener zoom sync - report

Status: done (draft PR, not merged). Branch `claude/t44-zoom-sync-fix` from origin/main 960758a.

## What changed
- Small charts (the per-coin mini charts on the screener board) share one zoom held in `ScreenerBoard` state. Zoom, pan or double-click reset on any one is applied to all; each chart clamps the shared range into its own data (`keepRange`). A live update keeps the shared zoom; a timeframe change resets it.
- Reset-zoom button removed ONLY on the small charts (per the user's correction). The spaghetti, BTC leg and drill-down charts keep their button and their own independent zoom, unchanged. Double-click / double-tap still resets everywhere.

## Files changed
- `web/islands/simple-lines.svelte` - new optional props `linkedRange`, `onRangeChange`; `setRange` reports user zoom/pan/reset; button hidden when linked.
- `web/islands/entry.js` - two new live prop keys.
- `web/lib/island-loader.ts` - `ChartRange` type and the two optional props.
- `web/components/chart/MiniChart.tsx` - optional `range`/`onRangeChange` pass-through (drill-down passes none, so unchanged).
- `web/components/screener/CoinPanel.tsx` - same pass-through (props at ~L15-17, MiniChart call ~L56-62).
- `web/components/screener/ScreenerBoard.tsx` - shared range state (~L41-49) and two props on CoinPanel (~L101-102).
- Tests: new `web/components/screener/__tests__/ScreenerBoardLinkedZoom.test.tsx` (3 tests), +1 in `web/lib/__tests__/chart-viewport.test.ts` (clamp on shorter series), `web/e2e/screener.spec.ts` (ETH follows BTC zoom/pan/reset, no button on small charts, spaghetti button kept), `web/e2e/live-refresh.spec.ts` (the second coin now follows BTC's zoom instead of staying unzoomed).

## Test counts
- vitest: 331 in 42 files -> 335 in 43 files, all green.
- tsc --noEmit: 0. build:islands: ok.
- e2e (seeded, SCREENER_REFRESH_WORKER=0): 72 in 8 -> 72 in 8, all green.
- pytest: skipped, nothing under api/ touched.
- git diff --check clean; ASCII only.

## Not verified
- Real browser feel (smoothness of linked pan across many coins) - the user's check.
- Svelte island logic is covered by e2e only (jsdom does not draw it).

## needs_input
None. Note: an unrelated uncommitted edit to `process/general-plans/active/screener-batch3_09-10-26/screener-batch3_PLAN_09-10-26.md` was present in the worktree; not mine, not committed.
