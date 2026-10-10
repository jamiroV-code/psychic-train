# S11b report: live polling, freshness strip, in-place chart updates

## 1. Task ID

T43 (batch 4, slice S11b). Branch `claude/t43-s11b-live-updates` from `main` a2fd4b5 (S11a merged).

## 2. Outcome

PASS on every gate G-S11b-1..11. Seeded e2e G-S11b-9 (24 passed) and G-S11b-10 (72 passed in 8 files) ran on the head code SHA 6e0190d. Counts match the plan arithmetic and the envelope's expected end (pytest 1016, vitest 331 in 42 files, e2e 72 in 8 files). No needs_input, no blocker. Not merged: the PR waits for the planner.

## 3. Summary

- `LivePoller` (`web/lib/live-poll.ts`, pure): one check at `start()`, the next 60 s after the previous one settles (setTimeout chain), 10 s abort per check (raced, so a fetch that ignores its signal still settles), waits of 120, 240, 300, 300 s after consecutive failures, reset on success. Hidden tab cancels the timer, the clock ticker and the check in flight without moving any snapshot; visible runs one check at once. Listens on `document.addEventListener("visibilitychange", ...)`; the constructor touches no `document` or `window`. Snapshots `{tick, dataVersion}`, `{phase, failures, lastGood}`, `{nowMs}`, stable between changes. Server clock = last server instant + `performance.now()` elapsed; 30 s ticker while visible.
- `LiveProvider` (one poller per page via `useRef`, stable context) with `useLiveData`, `useLiveStatus`, `useLiveClock` (all `useSyncExternalStore` with a server snapshot). No provider: `{0, 0}` and null, nothing refetches.
- Board and open drill-down refetch on `tick`, spaghetti and BTC charts on `dataVersion`. Success: `setX(prev => shareStructure(prev, next, VOLATILE))` and the error cleared; failure keeps the data and shows the existing error element. `DrillDownView` shows `drilldown-error` above the retained chart; `ScreenerBoard` keys it by symbol; `CoinPanel` is `React.memo`.
- `shareStructure` (`web/lib/same-data.ts`) returns `prev` itself when equal ignoring `server_time`, `fetched_at`, `clock_skew_seconds` at any depth, else `next` with equal subtrees replaced by the previous objects.
- `useSimpleLines(ref, props, mountKey)` mounts once per key with the latest props and sends later props to `handle.update`; a handle without `update` is re-mounted. `entry.js` returns `Object.assign(dispose, { update })` over `live-props.svelte.js` (a `$state.raw` object behind getters). The island resets zoom only when the timeframe or the line keys change and carries a zoom through new data with `keepRange` (new, in `chart-viewport.ts`).
- `FreshnessStrip` (first inside `LiveProvider` on `/screener`): refreshed, next, checked, overdue, failure, zone and help lines in Brussels time by the server clock; worker-off, first-refresh, failed-pairs and backoff copy; a visually hidden polite announcer that changes only on a state change. Captions age against the live clock (`freshnessCaption(fields, nowMs?)`).
- Backlog notes written: `screener-passive-polls_NOTE_10-10-26.md`, `screener-live-ondemand-states-contrast_NOTE_10-10-26.md`.

## 4. Files

New: `web/lib/{live-poll,refresh-strip,same-data,use-simple-lines}.ts`, `web/lib/api/refresh.ts`, `web/components/screener/{LiveProvider,FreshnessStrip}.tsx`, `web/islands/live-props.svelte.js`, tests `web/lib/__tests__/{live-poll,refresh-strip,same-data,refresh-api}.test.ts`, `web/lib/__tests__/use-simple-lines.test.tsx`, `web/components/screener/__tests__/{FreshnessStrip,ScreenerBoardLive}.test.tsx`, `web/e2e/live-refresh.spec.ts`, the two backlog notes, this report.

Edited: `web/lib/{chart-viewport,island-loader,chart-freshness}.ts`, `web/islands/{simple-lines.svelte,entry.js}`, `web/components/chart/{ChartFreshness,MiniChart}.tsx`, `web/components/screener/{ScreenerBoard,SpaghettiChart,BtcLegChart,DrillDownView,CoinPanel}.tsx`, `web/app/screener/page.tsx`, `web/app/globals.css`, tests `web/lib/__tests__/{chart-viewport,chart-freshness}.test.ts` (+4, +2 added, none changed).

All inside Owned; nothing in `api/`, no S11a file, no fixture, no existing test edited beyond the listed additions.

## 5. Commits

- 438e804 T43 / S11b: 60 s live polling, freshness strip, in-place chart updates
- 6e0190d T43 / S11b: typed island mock; strip variable renamed for the word gate
- (this report) process: S11b report

## 6. Tests run (SHA, UTC)

| Gate | SHA | UTC | Result |
|---|---|---|---|
| Baseline vitest `pnpm test` | a2fd4b5 | 2026-10-10T12:44:55Z | 268 passed, 35 files |
| G-S11b-11 red, G-S11b-1 command with stubs | a2fd4b5 + stubs | 2026-10-10T12:45:44Z | 111 tests in 14 files: 63 failed, 48 passed |
| G-S11b-11 red, full `pnpm test` with stubs | a2fd4b5 + stubs | 2026-10-10T12:45:49Z | 331 in 42 files: 63 failed, 268 passed |
| G-S11b-1..5, 8 first run | 438e804 | 2026-10-10T13:01:31Z | G1 111/14 PASS, G2 331/42 PASS, G3 FAIL (TS2493 x3 in use-simple-lines.test.tsx), G4 PASS, G5 8 PASS, G8 FAIL (S11b-words: local variable `good` in refresh-strip.ts) |
| G-S11b-1 | 6e0190d | 2026-10-10T13:02:20Z | 111 passed in 14 files |
| G-S11b-2 | 6e0190d | 2026-10-10T13:02:26Z | 331 passed in 42 files |
| G-S11b-3 | 6e0190d | 2026-10-10T13:02:36Z | exit 0 |
| G-S11b-4 | 6e0190d | 2026-10-10T13:02:40Z | exit 0 |
| G-S11b-5 | 6e0190d | 2026-10-10T13:02:45Z | 8 passed |
| G-S11b-8 (S11b-utc, S11b-words, S11-nostore, S11-clock) | 6e0190d | 2026-10-10T13:02:49Z | print nothing |
| G-S11b-9 seeded e2e, 4 specs | 6e0190d | 2026-10-10T13:02:53Z | 24 passed (10 + 7 + 3 + 4) |
| G-S11b-10 seeded e2e, full suite | 6e0190d | 2026-10-10T13:04:09Z | 72 passed in 8 files |
| Full pytest `UV_FROZEN=1 uv run --project api pytest api -q` | 6e0190d | 2026-10-10T13:06:41Z | 1016 passed, 2 skipped, 5 deselected |
| G-S11b-6, G-S11b-7 | report commit | see the PR | run after the report commit (convention 9); results in the PR body |

Golden re-derivation (convention 10, by arithmetic, before the green run): 2026-10-03 is summer time (+02:00); summer time 2026 ends on the last Sunday of October, 25 Oct (31 Oct is a Saturday), at 01:00Z. So 12:15Z -> 14:15 CEST; 2026-10-25T00:50Z -> 02:50 CEST and 01:02Z -> 02:02 CET (12 min apart); 2026-10-02T21:50Z -> 23:50 CEST on 02 Oct, 14 h 28 min before 03 Oct 12:18Z (prints `14 h`); 2026-10-03T21:50Z -> 23:50 CEST 03 Oct vs server 22:01Z -> 00:01 CEST 04 Oct (prefix `03 Oct`, 11 min). One test fixture of mine had a wrong age (22:50Z to 01:02Z is 2 h 12 min, not 12 min); the fixture was corrected, the code was not changed.

## 7. Tests NOT run

- Probes P-S11-* (real display, a live 15-minute cycle with the worker on, a hidden tab in a real browser, request rate P-S11-5): user PC only, not claimed.
- CI does not run Playwright; G-S11b-9/10 ran here only.

## 8. Deviations

1. dataVersion baseline: the first settled check never raises `dataVersion`, even when the worker is not running (the plan's "every success while not running" read as "every success after the baseline"). Otherwise the spaghetti and BTC charts would refetch right after mount on every page load; tested in live-poll test 9.
2. Island zoom reset: the first approach (an `$effect` reading `timeframe` and the line keys, `range` written inside `untrack`) reset the zoom on every update, because the props are getters over one replaced object and Svelte tracks that object, not the value. The seeded zoom test (e2e test 3) caught it in a development run. Fix inside step 1 of the ladder: the effect builds a key from the timeframe and line keys and compares it with the previous key inside `untrack`. No `update(next)` export was needed.
3. Strip extra lines (failed pairs, backoff) render as plain strip items without testids; the listed testids are unchanged. `Refreshes are failing; retrying about <t>` uses `next_tick_at` (fallback: last answer + `backoff_seconds`).
4. e2e: tests 2 and 3 use `page.clock.install()` and `runFor(61_000)` (no real 61 s wait was needed); test 1 installs the clock only; test 4 uses the hidden/visible trick for failure and recovery. Test 3 adds one bar to BTC and to a second coin; the second (unzoomed) coin's `data-visible-to` proves the update landed while BTC keeps `data-zoomed`, `data-visible-from` and `scrollY`. Route handlers swallow a fulfil on a request the page already aborted (StrictMode's first check).
5. `ChartFreshness.tsx` gained `"use client"` (it now reads the live clock hook).
6. Environment: `web/node_modules` was absent; `pnpm install --frozen-lockfile` was run once (lockfile unchanged).
7. Development runs before the gate runs: `live-refresh.spec.ts` ran three times (a test-authoring wait fix, then the island fix in deviation 2). Gate fix cycle 1 of 2 used (G3 and G8 on 438e804, fixed in 6e0190d); no gate failed twice.

## 9. Blockers

None.

## 10. Follow-up

- Backlog `screener-live-ondemand-states-contrast_NOTE_10-10-26.md` (AC-S11b-8r Known-Gap: contrast of the overdue and failed variants).
- Backlog `screener-passive-polls_NOTE_10-10-26.md` (only if P-S11-5 shows too much traffic).
- Planner: re-validate the S5b plan after this merge (plan Hand-over to S5b).

## 11. Context cost

Files read beyond the WORKER set: `api/data/refresh_worker.py` (status fields, `backoff_seconds` and `disabled_reason` semantics), `api/tests/analytics/test_no_verdict_symbols.py` (TOKENS for convention 11), one existing backlog note for the format, and the web sources and tests the slice edits. No other context doc opened. Subagents: none. Dollar cost not measurable in-session.
