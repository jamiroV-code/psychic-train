# T223 chart slice report

Date: 2026-11-06. Branch `claude/t223-btc-momentum-chart`, stacked on the Windows repair commit (PR #242) over T222 (PR #241).

## Changes
- `web/islands/simple-lines.svelte`: separate `signalPoints` layer (not a `SimpleLineMarker`), positioned from the chart's visible x domain and the visible y domain, same padding as the Chart; clipped to the visible plot; `data-signal-count` on the overlay, `data-testid=btc-signal-point` with `data-kind`/`data-timestamp` per point.
- `web/islands/entry.js`: `signalPoints` registered in `SIMPLE_LINES_KEYS` so props arriving after mount update the chart.
- `web/lib/island-loader.ts`: `SimpleLineSignalPoint`, optional `signalPoints`.
- `web/lib/btc-leg-lines.ts`: `signalPoints()` and `signalText()` builders (no numeric recomputation; points carry the API's `price`).
- `web/components/screener/BtcLegChart.tsx`: passes points to the island; visually hidden `ul[data-testid=btc-signal-list]` gives screen readers one line per signal.
- `web/app/globals.css`: up triangle (BUY) and down triangle (SELL); shape differs, not only colour.
- `api/scripts/seed_e2e_cache.py`: BTC 1d E2E fixture is now a hand-designed ramp-then-decline (bars 0-299 rising, then -1.5 a bar) whose expected events (BUY bar 252; SELL bars 344, 388, 476) are written in the seeder and exported in the manifest as `btc_signals`.
- `api/tests/routers/test_btc_legs_router.py`: the S7 vocabulary guard exempts BUY/SELL/signal in `web/lib/btc-leg-lines.ts` and `BtcLegChart.tsx` (BTC chart only); `LegEstimate.tsx` stays strict.
- Tests: `btc-leg-lines.test.ts` (builders), `BtcLegChart.test.tsx` (props reach the island beside bands and markers; accessible list; empty case), `e2e/screener.spec.ts` (seeded FastAPI to React to Svelte).

## Verification
- Vitest full: 67 files, 642 tests passed. `tsc --noEmit`: exit 0. `pnpm build:islands`: built.
- Seeded Playwright, BTC specs: 2 passed. API `signals` equal the manifest events (hand-designed oracle agrees with the production calculator); markers inside the plot box, ordered by x and y; Ctrl+wheel zoom drops out-of-range markers; double-click reset restores all four; band and boundary counts unchanged.
- Full Playwright run (refresh worker off): 87 passed, 3 failed (`daily-data-gap`, two `narrative` 375px horizontal-scroll specs). The same three fail on the base without T223 changes: pre-existing, unrelated.
- Full API gate, disposable same-process-isolated snapshot: 3722 passed, 5 skipped, 0 failed.
- Independent review (T223Review): CHANGES_REQUESTED once, for the vocabulary guard; fixed as above. Positioning, collapsed axis, key uniqueness, accessibility and seeder checks passed.

## Open
- User visual confirmation of the chart (zoomed and panned markers).
- Decisions sync (D-2 scoped exception) belongs to UPDATE PROCESS, not done here.
- Strict external-consumer inventory for the additive `signals` field before deploy.
