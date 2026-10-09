# T37 / S6 report: chart interaction, crisp axes, spaghetti chart

## 1 Task ID

T37 (batch 2, slice S6). Branch `claude/t37-s6-chart-interaction`, based on origin/main 928389c (contains the S4 merge 69fedd2; later commits are data snapshots).

## 2 Outcome

done (review items: P-S6-1 is a user-PC probe; AC-S6-6 is the accepted residual, backlog note written)

## 3 Summary

- `GET /api/screener/spaghetti?timeframe=` (C5): last 200 bars (28 for 1w) of each coin's own frame, percent from the window's first close, 60-bar availability rule, explicit `reason` for no-data, BTC and HYPE always in `references`, Z timestamps, read wrapped in `reads_cache_only_if_running()`. The old per-window endpoint, its models, builder, constants, component, line builder and tests are deleted.
- `web/lib/chart-viewport.ts`: pure range math (zoomAt, pan, pinchFactor, isDoubleTap, shouldHandleWheel, touchActionFor, clamp, 5-bar minimum).
- `simple-lines.svelte`: Ctrl/Cmd+wheel zoom (non-passive listener, plain wheel untouched), two-pointer pinch, drag pan while zoomed, double-click/double-tap (300 ms) and `chart-reset` button reset, zoom reset when the series prop changes, y re-fit to visible points, `utcAxis` for the visible span, `data-zoomed` / `data-visible-from` / `data-visible-to`, axes in `<Svg>`, lines in `<Canvas>`, right padding from the widest tick label, optional `highlight` prop (nearest line thicker).
- `SpaghettiChart` inside `ScreenerBoard`, following the board timeframe: legend toggles (`spaghetti-toggle-<SYM>`, `aria-pressed`, memory only), span text, per-coin notes, `spaghetti-error`; references thicker in `SERIES.primary`/`SERIES.secondary`, coins cycle the other six slots. `page.tsx` renders the board only.

## 4 Files changed

API: `api/models/screener.py`, `api/analytics/screener_board.py`, `api/routers/screener.py`, `api/tests/routers/test_spaghetti.py` (new), `api/tests/routers/test_board_integration.py` (renamed test, same count), `api/tests/routers/test_relative_performance.py` (deleted).
Web: `web/islands/simple-lines.svelte`, `web/lib/chart-viewport.ts` (new), `web/lib/spaghetti-lines.ts` (new), `web/lib/island-loader.ts`, `web/lib/chart-palette.ts` (comment), `web/lib/format-unavailable-reason.ts` (comment), `web/lib/types/screener.ts`, `web/lib/api/screener.ts`, `web/components/screener/SpaghettiChart.tsx` (new), `web/components/screener/ScreenerBoard.tsx`, `web/app/screener/page.tsx`, `web/app/globals.css`, deleted component, line builder and component test; tests `web/lib/__tests__/chart-viewport.test.ts`, `web/lib/__tests__/spaghetti-lines.test.ts`, `web/components/screener/__tests__/SpaghettiChart.test.tsx` (new), `ScreenerBoard.test.tsx` (stub in all 8 renders + follow-the-timeframe test), `web/e2e/screener.spec.ts` (test 7 rewritten, tests 8-9 new), `web/e2e/contrast.spec.ts` (line 121 selector only).
Process: `process/general-plans/backlog/spaghetti-toggle-persistence_NOTE_09-10-26.md`, this report.
Not touched: `MiniChart.tsx` (already passes `timeframe`), `chart-time-format.ts` and its test.

## 5 Commits

- e6e90fe feat(screener): T37 S6 chart zoom/pan/reset, SVG axes, spaghetti chart
- (this report) docs(process): T37 S6 worker report
Branch `claude/t37-s6-chart-interaction`.

## 6 Tests run

Baselines at 928389c, 2026-10-09T06:05Z: pytest 929 passed / 2 skipped / 5 deselected / 0 xfailed; vitest 226 passed in 30 files. Match the envelope.

Red-first (stubs written, untouched source), 928389c, 2026-10-09T06:08:47Z:
- G-S6-1 `UV_FROZEN=1 uv run --project api pytest api/tests/routers/test_spaghetti.py -q`: 8 failed (NotImplementedError stubs).
- `pnpm --filter web test`: 21 failed (10 + 5 + 6 stubs), 226 passed, 33 files.

Final gates, commit e6e90fe, 2026-10-09T06:18:37Z to 06:21:14Z (each once after the last source edit):

| Gate | Result |
|---|---|
| G-S6-1 test_spaghetti.py | 8 passed |
| G-S6-2 `UV_FROZEN=1 uv run --project api pytest api/ -q` | 934 passed, 2 skipped, 5 deselected, 0 xfailed |
| G-S6-3 `pnpm --filter web test` | 239 passed in 32 files |
| G-S6-4 tsc --noEmit | exit 0 |
| G-S6-5 `cd web && pnpm build:islands` | exit 0 |
| G-S6-6 `git diff --check origin/main...HEAD` | exit 0, no output |
| G-S6-7 S6-scope, FORBIDDEN, S-secret-scan | print nothing |
| G-S6-8 FIXTURES | prints nothing |
| G-S6-9 S6-dangling | prints nothing |
| G-S6-10 `cd web && SCREENER_REFRESH_WORKER=0 PLAYWRIGHT_CHROMIUM_PATH=/opt/pw-browsers/chromium-1194/chrome-linux/chrome pnpm test:e2e screener.spec.ts contrast.spec.ts` | 16 passed (screener 1-9, contrast 7 routes), 2026-10-09T06:15Z, working tree byte-identical to e6e90fe's source (run before the commit; nothing changed after it) |
| G-S6-11 | this heading (red run) and heading 9 (spike) |

E2E fix cycle (1 of 2): the first G-S6-10 run had 2 failures: test 7's `getByRole("img")` also matched LayerChart's SVG label nodes (fixed by targeting `.simple-lines`), and the contrast audit read the "━" reference glyph as text at 4.3:1 (fixed by the audited graphic glyph "▬"). Rerun: 16 passed.

## 7 Tests NOT run

- P-S6-1 (real DPR 2 display, phone pinch and one-finger pan): user-PC probe, per the envelope.
- E2E tests 8-9 were not run red on the untouched base. They were written after the island change, so the red state is by construction (the base had no `data-zoomed` hooks and drew axis text on canvas), not observed.
- Integration-marked pytest (`-m integration`): deselected by default, needs network.

## 8 Deviations

- Spike (a) settled by reading LayerChart 2.5.0's transform source, not by a browser run (see heading 9).
- `SpaghettiLine` extra field over C5: none. `SpaghettiResponse` matches C5 exactly. `bars` defaults to 0 and `stale` to false on unavailable lines.
- Island prop `highlight` (additive, optional) added to `mountSimpleLines` so the nearest-line emphasis is on for the spaghetti chart only.
- `globals.css`: the old note class was renamed to `.spaghetti-chart__note`; `.simple-lines*` and `.spaghetti-chart*` rules added. The `--series-N` block is untouched.

## 9 Blockers

None. Spike record (S6 design step 1):
- (a) LayerChart `transform`: REJECTED, custom path stands. In layerchart 2.5.0, `states/transform.svelte.js` handles a plain wheel as zoom/scroll and uses `ctrlKey` only as a pinch multiplier, so "plain wheel does not zoom" fails without overriding its wheel handling. One failed criterion is enough per the plan; criteria 2-6 were not run against it.
- (b) Layers: PASS. `<Svg>` axes and `<Canvas>` lines in one `Chart`; at DPR 2 the spaghetti plot holds 6 SVG `<text>` labels and the canvas still paints (E2E test 7 pixel count and test 9).
- (c) DPR: PASS. Spaghetti canvas `width` 2152 = round(1076 × 2); LayerChart sizes the backing store from `window.devicePixelRatio`. No all-SVG fallback needed; test 7 keeps the canvas pixel counter.
- PNGs (DPR 2, `deviceScaleFactor: 2`, read and checked: sharp labels, last label not clipped, lines drawn): `s6-spike-spaghetti-dpr2.png`, `s6-spike-coinbox-dpr2.png`, kept in the session scratchpad, not committed.

Registry update request: T37 S6 to review; AC-S6-6 remains CONDITIONAL until S5.

## 10 Follow-up

- S5: toggle persistence across reloads (`process/general-plans/backlog/spaghetti-toggle-persistence_NOTE_09-10-26.md`, AC-22 / AC-S6-6).
- User PC probe P-S6-1: Ctrl/Cmd+wheel, trackpad pinch, phone two-finger pinch and one-finger pan, text sharpness on a real DPR 2 screen.
- S7 bases on this merge: 934 pytest, 239 vitest in 32 files.

## 11 Context cost

Files loaded: CLAUDE.md, the envelope, the named plan line ranges. On demand (outside the WORKER set): `process/development-protocols/master-planner.md` section 9 only, for the report headings. Source files read for the change: the owned files plus `DeadDataNotice.tsx`, `CoinPanel.tsx` (one grep), `api/data/freshness.py` and `refresh_worker.py` (signatures), `test_screener_freshness_payload.py` (contract-test pattern), `playwright.config.ts`, `spread-chart.svelte`, the seeder's watchlist line.
Approximate tokens: about 200k in. Subagents: none spawned (capped lane unused). Tools: Bash, Read, Write, Edit, GitHub MCP.
