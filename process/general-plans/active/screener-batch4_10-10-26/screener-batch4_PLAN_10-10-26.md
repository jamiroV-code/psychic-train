---
name: plan:screener-batch4
description: "Screener slice S11 (goes before S5b): Brussels time everywhere on the screener (axis, captions, spans), automatic page updates every 60 s that keep zoom and selection, and a freshness status strip. Two slices: S11a (status server_time, shared Brussels module, all labels) then S11b (poller, strip, in-place chart updates)"
date: 10-10-26
feature: general-plans
---

# Screener Batch 4: Brussels Time, Automatic Page Updates, Freshness Strip (S11a, S11b)

Date: 10-10-26
Status: PLANNED; PVL cycle 1 returned CONDITIONAL (0 FAIL, 7 CONCERN) and supplement cycle 1 folded F1-F7 and advisories a-j (10-10-26); validate-contract PENDING (skeleton below), no PASS stamp yet. Q1 (budget) RESOLVED 10-10-26: programme ceiling 75 USD. Code read at origin/main `1e7d337` (local HEAD `20a6c92` adds process files only; `git diff 1e7d337 HEAD -- api web` is empty). Baselines re-measured 10-10-26: pytest 996 passed, 2 skipped, 5 deselected (188 s); vitest 251 in 34 files; tsc 0; build:islands 0; `playwright test --list` 65 in 6 files; full seeded e2e 65 passed (2.6 min, worker off).
Folder index: this plan; PVL reports `screener-batch4-pvl-iteration-NNN_REPORT_<dd-mm-yy>.md` and `results.tsv` (written by VALIDATE); envelopes `screener-batch4-s11{a,b}_REF_<dd-mm-yy>.md` and slice reports `screener-batch4-s11{a,b}_REPORT_<dd-mm-yy>.md` (written by the planner and workers).
Complexity: COMPLEX (S11a then S11b, strictly sequential; one added field on a public endpoint, a display module used by every screener caption, a polling layer, a change to the shared chart island)

**TL;DR:** Every time on the screener will show in Brussels time (CET or CEST, offset shown) whatever the browser zone is. The page will check the server every 60 s while the tab is visible and update boxes, charts and the open drill-down in place, keeping zoom, scroll and selection. A strip at the top shows "Server refreshed, Next refresh, Page checked" with a plain overdue marker. S11a (25 touches) does the display and one status field; S11b (35 touches) adds polling, strip and in-place updates. The 100-touch rule alone would keep it one slice (60 touches); the worker read cap forces the split. Estimate 7.2-9.5 USD [estimate], accepted by the user under the new 75 USD programme ceiling (Q1 resolved).

Sources: user request and four option answers 10-10-26 (U1-U4; no separate SPEC file for this slice); SPEC `personal-tracker-realignment_SPEC_02-10-26.md` (its S2 UTC axis and caption decisions are superseded for DISPLAY by U3); batch 1 to 3 plans and PVL reports; `process/context/{current-state,architecture,operating-instructions,decisions}.md`, `tests/all-tests.md`; real code at `1e7d337`. Router: `process/context/all-context.md`.

Context Envelope: general-plans | PLAN | batch 4 (S11) | claude/pensive-albattani-ou0cgv | /home/user/psychic-train | tests | api/data/refresh_worker.py, web/ | this file | pytest then vitest then playwright | contract PENDING.

## Overview

Goal: the user can see, in Brussels time, that the screener is up to date, without pressing reload. Binding user decisions 10-10-26: U1 the page checks the server every 60 s quietly, keeps zoom, scroll, selection and layout state, pauses while the tab is hidden; U2 proof is a status strip at the top ("Server refreshed 14:15 (3 min ago), next refresh 14:30, page checked 14:17" with a plain overdue marker) plus the per-chart last-bar line in Brussels time and age; U3 time zone always Europe/Brussels with the offset shown (CET or CEST) whatever the browser says, DST handled; U4 this goes before S5b. Not chosen, not built: a refresh log in the drill-down. Non-goals: any change to data (candles still open at UTC boundaries, payload timestamps keep their `Z`), the worker beyond one status field, `api/data/{ccxt_adapter,cache,freshness,lse_adapter,equities_store}.py`, `deploy/**`, `api/scripts/**`, other pages, verdict or badge wording.

## Name check against the request and real code (read 10-10-26)

| Request or earlier plan says | Actual code | Plan consequence |
|---|---|---|
| what `GET /api/refresh/status` returns, and what the web reads | 10 keys (`running`, `disabled_reason`, `interval_seconds`, `last_tick_started`, `last_tick_finished`, `last_tick_ok`, `last_tick_failed`, `next_tick_at`, `queue_depth`, `backoff_seconds`), no clock; `test_refresh_router.py:73,84` asserts the key set EXACTLY; the web reads nothing (`grep -rn "refresh/status" web` is empty) | add `server_time`, edit `STATUS_KEYS`, `types/refresh.ts` (S11a); client (S11b) |
| does the page poll, does a data change keep zoom | no polling: `ScreenerBoard` has one effect keyed `[timeframe, fetchBoard]`; `page.tsx` renders `BtcLegChart` and `ScreenerBoard` as unrelated siblings. No zoom kept: `MiniChart`, `SpaghettiChart`, `BtcLegChart` re-mount the island in an effect keyed on the data arrays and `simple-lines.svelte` runs `$effect(() => { void series; range = null })`; board data changes at every worker tick | one provider above both, in-place update, narrower reset rule (S11b) |
| ticks every 900 s | `_loop` sets `next_tick_at` AFTER a tick ends (cycle = 900 s plus the tick duration); during a running tick it is already past | overdue needs a grace; the strip shows the real `next_tick_at` |
| a board read is free | with the worker on, a board GET is cache-only but calls the refresh hook for each pair failing `cache_is_fresh` (`FORMING_TTL` 15m 180 s, 1h 300 s, 4h and 1d 900 s) and the worker drains those between ticks: a page polled each minute refreshes 15m and 1h pairs every 3 to 5 min (about 0.7 fetches per minute per coin instead of 0.3) | accepted (fresher data; dedupe and the failed-pair rule bound it); `POLL_INTERVAL_MS`; P-S11-5; backlog stub |
| UTC wording | display: `chart-time-format.ts` (every axis label), `chart-freshness.ts`, `spaghetti-lines.ts`, `btc-leg-lines.ts`; comments in `CoinPanel.tsx`, `ChartFreshness.tsx`, `MiniChart.tsx`, `simple-lines.svelte`, `island-loader.ts`; HIDDEN: `CoinPanel.chipTitle` shows the raw `candle from 2026-10-03T00:00:00Z` in a tooltip | all converted, the tooltip too |
| `Intl` zone names and bad dates | `en-US` prints `GMT+2`, `en-GB` prints `CEST` (Node 22.22, ICU 77.1; Chromium may differ); `format(new Date("x"))` throws `RangeError` (verified) | abbreviation derived from the computed offset; every Brussels formatter returns `n/a` for an invalid date |
| ticks on whole UTC steps | `utcTicks` snaps to UTC, so 3 h, 6 h, 12 h ticks fall at 02:00, 08:00 Brussels time in summer and the day label flips at 02:00 CEST | ticks on the Brussels wall clock (C3) |
| the island imports `../lib/chart-time-format` | `vite.islands.config.mjs` has no `@/` alias; the only `@/` import there today is `import type` (erased) | `brussels-time.ts` and its importers use `./` paths; `build:islands` proves it |
| `ScreenerBoard` errors | `setError` on failure, never cleared by a later success | cleared on success (S11b) |

## Decisions locked for this batch

- **C1 Two slices, sequential, both before S5b.** S11a = status `server_time`, Brussels module, every label, no network behaviour change. S11b = poller, provider, strip, in-place chart updates; branches from `main` after the S11a merge. Reason: worker read cap, and the user sees the Brussels labels (their first complaint) first.
- **C2 Display module.** `web/lib/brussels-time.ts` is the only file that names `Europe/Brussels`. It uses one module-level `Intl.DateTimeFormat("en-US", { timeZone, hourCycle: "h23" })` instance with `formatToParts`; the offset is the zoned wall clock minus the instant (60 or 120 min); the abbreviation comes from the offset (60 CET, 120 CEST, anything else `+HH:MM`); `offsetLabel` is `+02:00`. Never `getHours` and the like, `toLocale*`, nor the browser zone or locale. Exports (names fixed): `DISPLAY_ZONE`, `offsetMinutes`, `zoneAbbr`, `offsetLabel`, `formatTime` (`16:15`), `formatDay` (`03 Oct`), `formatMonthYear` (`Oct 26`), `formatDate` (`2026-10-03`), `formatDateTime` (`2026-10-03 16:15`), `formatDateTimeZone` (`2026-10-03 16:15 CEST`), `formatTimeZone` (`16:15 CEST`), `dayKey`, `midnightOf`. An invalid date gives `n/a`.
- **C3 Ticks on the Brussels wall clock** (`chart-time-format.ts`: `brusselsTicks`, `formatBrusselsTicks`, `brusselsAxis` replace the `utc*` names; step tables and the 365-day year rule unchanged). Sub-day steps: instants on the 15-minute UTC grid whose Brussels minutes since midnight are a multiple of the step; in the repeated hour of 25 Oct only the first pass gets ticks (a candidate whose wall time is not later than the previous kept tick's wall time is skipped, whatever the step); the skipped hour of 29 Mar has none. Day, week and month steps sit on Brussels midnights (Mondays for weeks; the 2-day step keeps Brussels days with an even number since 1970-01-01, said in the module comment): `midnightOf(day)` = the UTC midnight of that date minus the offset in force 3 h before it (verified: 28, 29, 30 Mar 2026 give 23:00Z, 23:00Z, 22:00Z of the day before; 29 Mar is 23 h long and 25 Oct 25 h). Labels: intraday, the first tick of each Brussels day reads `DD MMM`, the others `HH:mm`; 1d and 1w read `DD MMM`, or `MMM YY` beyond 365 days.
- **C4 Text forms.** Caption `Last bar 2026-10-03 16:15 CEST, opened 7 min ago (forming)` or `Last bar 2026-10-03 16:00 CEST, 22 min ago`. Chip tooltip `1d candle from 2026-10-03 02:00 CEST (forming)`. Spans: `Last 28 weeks, 2026-03-23 to 2026-10-04 (Brussels time)`, `Daily BTC, 2026-01-01 to 2026-10-08 (Brussels time), 3 bars (all cached history)`; intraday `Last 27 hourly bars, 2026-10-09 14:00 to 2026-10-10 16:00 CEST`, across a clock change each end has its own abbreviation (`2026-10-25 02:00 CEST to 2026-10-25 04:00 CET`). Data semantics are unchanged: a daily candle still opens at 00:00 UTC, which reads 01:00 CET or 02:00 CEST (the probe says so). Leg dates are grid dates and stay plain dates.
- **C5 Status payload.** `refresh_worker.status()` gains exactly one key, `server_time` (`freshness.iso_z` of the worker's clock, or of `ccxt_adapter._now` when no worker is registered; null if the clock raises). No counters, no other key. The strip needs it so ages never use the browser clock.

## Gate conventions (both slices; batch 1 to 3 conventions kept)

1. Every pytest gate runs with `UV_FROZEN=1`. No slice edits a fixture. New tests are plain functions (no `it.each`, no parametrize). No slice reads or writes `api/data/*.json`.
2. A count that differs from the plan arithmetic stops the worker at `needs_input`; baselines are re-recorded at spawn.
   S11a baselines at `1e7d337`: pytest 996 passed/2 skipped/5 deselected/0 xfailed; vitest 251 in 34 files; tsc 0; islands 0; e2e screener+contrast 17, full 65 in 6 files.
   S11b starts from the S11a merge (999; 268 in 35 files; 68 in 7 files).
3. Web gates run inside `web/` (`pnpm --filter web` fails here). Log each gate run in heading 6 with SHA and UTC time.
4. Seeded e2e (CI does NOT run Playwright): `cd web && SCREENER_REFRESH_WORKER=0 PLAYWRIGHT_CHROMIUM_PATH=/opt/pw-browsers/chromium-1194/chrome-linux/chrome pnpm test:e2e <specs>` (no `--`). REQUIRED on the head SHA before any merge; NOT-RUN stops at `needs_input`. Never merge with an open `needs_input` or `blocker`.
5. Red-first: write the slice's new tests as stubs and the changed goldens as the NEW text, run the first gate on the untouched base, record the red run in heading 6, then write the real tests.
6. Hidden-break rule: an existing test may be edited only as listed in the slice's table; any other failing existing test stops the worker at `needs_input`.
7. Workers branch from `main`; max 2 fix cycles per gate, the same failure twice stops. A diff touching CLAUDE.md, AGENTS.md, README.md, `.claude/`, `.github/`, `deploy/` stops at `review`.
8. `git diff --check` exits 0; ASCII only in plan and report files. A real display, a live 15-minute cycle and a hidden tab in a real browser are probes (P-S11-*), never claimed by a worker. Known-Gap is a residual (backlog stub, gate stays CONDITIONAL), never a PASS.
9. The scope, FORBIDDEN, FIXTURES, secret and word commands read `git diff origin/main...HEAD`, so they run AFTER the commit (before it they print nothing for the wrong reason).
10. Date and DST goldens come from clock arithmetic. The worker re-derives each independently (arithmetic, not the new code) before the green run; a mismatch stops it at `needs_input`. Never paste program output into an expected value.
11. Gate-trap rules: new files contain no token of `api/tests/analytics/test_no_verdict_symbols.py::TOKENS`; no new testid starting `coin-panel-`; no new `role="group"`; no new heading; UI copy never contains `Momentum`, `Trend`, `Benchmark`, `Confidence`, `Narrative`; no browser storage; files the island imports (`brussels-time.ts`, `chart-time-format.ts`, `chart-viewport.ts`) import only relatively (no `@/` alias in the island build); comments in scanned files avoid the word `UTC` (say "the data's own clock").

## Split evidence and sequencing

Touches: S11a 25 (2 api, 2 new and 8 edited web source, 1 new, 1 rewritten and 8 edited vitest files, 1 new and 1 edited e2e, 1 report); S11b 35 (8 new and 14 edited source, 7 new and 2 edited vitest files, 1 e2e, 2 backlog stubs, 1 report); total 60 (54 distinct files). The 100-touch rule alone would keep it one slice. The split is forced by the worker read cap (36,000 B = CLAUDE.md 13,443 + envelope + plan ranges): the sub-range table (last block) holds S11a at 17,924 B and S11b at 20,435 B of plan ranges against 22,557 B (36,000 - 13,443) less the envelope, and the union is 34,940 B, 12,383 B over even with a zero-byte envelope. It also gives two proof boundaries: the labels first, then the polling risks (island update path, fake browser clock in e2e). Sequencing: S11a, merge, S11b, merge, then S5b after its re-validation; never parallel (S11b imports the S11a module and type). R12 is file-disjoint.

## Program budget and costs

Ceiling 75 USD (raised by the user 10-10-26, resolving Q1); about 45.1 USD spent and 29.9 USD left (planner figure 10-10-26); S5b needs 5.5-8 after this. Comparable slices: T32 5.58, T34 4.99, T35 4.15, T36 5.44, T37 4.97, T38 4.75 USD (worker only).

| Slice | Worker (opus) | Subagents (sonnet) | EVL tester | Total [estimate] | Basis |
|---|---|---|---|---|---|
| S11a | 2.2-3.0 | 0.3 | 0.5 | 3.0-3.8 | 25 touches, 17 new vitest and 10 changed goldens, 3 pytest, 3 e2e, 1 full pytest run, 90 tool calls |
| S11b | 3.2-4.4 | 0.4-0.6 | 0.6-0.7 | 4.2-5.7 | 35 touches, 63 new vitest, 4 e2e with a fake browser clock, a Svelte update path not yet run, 130 tool calls |
| S11 | | | | 7.2-9.5 | above the first 4-6 expectation; accepted with the 75 USD ceiling (Q1 resolved) |

At the top figure 20.4 USD would remain against S5b's 5.5-8. Capped-lane stops for this programme: ask above 5 USD (S11a) or 7 USD (S11b) or 75 USD in total; re-price S11b from the real S11a cost.

## S11a: status server_time, Brussels module, every label (RT3, capped subagent lane: yes)

**Goal:** `/api/refresh/status` carries `server_time`; every time the screener shows (axis ticks, last-bar captions, chip tooltips, span lines) is Europe/Brussels with CET or CEST; no word `UTC` is visible on `/screener`; no polling yet. Starts from `main` at the plan merge.

**Owned (exact):** `api/data/refresh_worker.py` (only `status()`), `api/tests/routers/test_refresh_router.py`; new `web/lib/brussels-time.ts`, `web/lib/types/refresh.ts`; edited `web/lib/{chart-time-format,chart-freshness,spaghetti-lines,btc-leg-lines,island-loader}.ts`, `web/components/screener/CoinPanel.tsx`, `web/components/chart/ChartFreshness.tsx`, `web/islands/simple-lines.svelte` (import rename and comments only); new tests `web/lib/__tests__/brussels-time.test.ts`, `web/e2e/brussels-time.spec.ts`; rewritten `web/lib/__tests__/chart-time-format.test.ts`; edited `web/lib/__tests__/{chart-freshness,spaghetti-lines,btc-leg-lines}.test.ts`, `web/components/chart/__tests__/ChartFreshness.test.tsx`, `web/components/screener/__tests__/{ScreenerBoard,DrillDownView,SpaghettiChart,BtcLegChart}.test.tsx`, `web/e2e/screener.spec.ts` (one line); report `screener-batch4-s11a_REPORT_<dd-mm-yy>.md`.
**Forbidden:** the FORBIDDEN list, every other `api/` and web file (S11b files), `web/islands/entry.js`.

**Design:**
1. `status()` (C5): one key added. `RefreshStatus` in `types/refresh.ts` mirrors all 11 keys one per line (nullable: `disabled_reason`, `last_tick_started`, `last_tick_finished`, `next_tick_at`, `server_time`), the closing `}` at column 0 (the contract test parses it).
2. `brussels-time.ts` (C2). `chart-time-format.ts` (C3) imports it as `./brussels-time`: keep `FIXED_STEPS`, `MONTH_STEPS`, `YEAR_SPAN_MS`. The island imports `brusselsAxis`; its `scaleUtc()` (a plain linear time scale with explicit ticks) stays.
3. `chart-freshness.ts` caption head uses `formatDateTimeZone`; `spaghettiSpanText` and `btcLegSpanText` follow C4; `CoinPanel.chipTitle` uses `formatDateTimeZone(open_ts)`; reword every `UTC` comment in the `S11a-utc` files and the stale axis comment in `island-loader.ts`.
4. The e2e spec forces `timezoneId: "Asia/Tokyo"` and `locale: "ja-JP"` and compares with an arithmetic oracle (EU rule: summer time from the last Sunday of March 01:00Z to the last Sunday of October 01:00Z), never with `Intl`.

**Existing tests that break (exact edits allowed):**

| Test | Why | Edit |
|---|---|---|
| `chart-time-format.test.ts` (10) | every golden is a UTC label; imports `utcAxis`, `formatUtc*` | rewritten as the 12 tests below |
| `chart-freshness.test.ts` tests 2 to 5 (lines 20-47) | goldens end in `UTC` | `Last bar 2026-10-03 16:15 CEST, opened 7 min ago (forming)`; `... 16:00 CEST, 22 min ago`; `Last bar 2020-01-01 01:00 CET, 2 d ago`; `Last bar 2026-10-03 02:00 CEST` |
| `ChartFreshness.test.tsx` lines 11, 18 | same | `... 16:15 CEST, opened 7 min ago (forming)`; `... 16:15 CEST, 2 d ago` |
| `DrillDownView.test.tsx` lines 20, 35 | title and golden | `Last bar 2026-10-03 16:00 CEST, 22 min ago`; title says Brussels time |
| `ScreenerBoard.test.tsx` lines 160, 178-179 | title and golden | `Last bar 2026-10-03 16:15 CEST, opened 7 min ago (forming)` |
| `SpaghettiChart.test.tsx` lines 62-67 | span | `Last 28 weeks, 2026-03-23 to 2026-10-04 (Brussels time)`; title says Brussels time |
| `BtcLegChart.test.tsx` line 71 | span | `Daily BTC, 2026-01-01 to 2026-10-08 (Brussels time), 3 bars` |
| `screener.spec.ts` test 7, the spaghetti chart test (about line 252) | `toContainText("UTC")` | `toContainText("Brussels time")`; one line for one line, no shift (S5b edits test 1 of the same file) |
| `test_refresh_router.py` lines 20-31, 73, 84 | `set(body) == STATUS_KEYS` | add `"server_time"` to `STATUS_KEYS` |
| stay green unedited | pinned shapes and scans | `chart-viewport.test.ts`, `screener-api.test.ts`, the `btc-leg-lines.test.ts` bands test (bounds stay day starts), the CSS parsers (`globals.css` untouched), `test_refresh_startup.py`, `test_no_verdict_symbols.py` |

**Tests (17 vitest, 3 pytest, 3 Playwright; plain functions; the worker names them by behaviour):**
- `brussels-time.test.ts` (8): (1) offset and abbreviation in winter (15 Jan 2026: 60, CET, `+01:00`) and summer (15 Jul: 120, CEST, `+02:00`); (2) spring change 29 Mar 2026 (00:59:59Z reads 01:59 CET, 01:00:00Z reads 03:00 CEST); (3) autumn change 25 Oct (00:59:59Z reads 02:59 CEST, 01:00:00Z reads 02:00 CET); (4) day boundary (2026-10-03T22:30:00Z is `04 Oct 00:30` and its `dayKey` differs from the UTC day; 22:00Z reads `00:00`, never `24:00`); (5) `midnightOf` for 28/29/30 Mar and 24/25/26 Oct (23:00Z, 23:00Z, 22:00Z of the day before; 22:00Z, 22:00Z, 23:00Z) with the 23 h and 25 h lengths; (6) identical output with `process.env.TZ` set to `UTC`, `America/Los_Angeles`, `Asia/Tokyo`, restored in a `finally` (the worker shows it red against a scratch `getHours` version, heading 6); (7) an invalid date gives `n/a`, never a throw; (8) `formatDateTimeZone` and `formatTimeZone` goldens.
- `chart-time-format.test.ts` (12): (1) 15m window 21:00Z-23:30Z on 3 Oct gives `["03 Oct","04 Oct","01:00"]` (the second tick is Brussels midnight, 22:00Z); (2) 4h frame, window 00:00Z-24:00Z of 3 Oct (6 h step) gives `["03 Oct","12:00","18:00","04 Oct"]` (ticks 04:00Z, 10:00Z, 16:00Z, 22:00Z, not UTC-aligned); (3) 1d frame, window 2026-10-23T22:00Z to 2026-10-27T00:00Z gives instants 10-23T22:00Z, 10-24T22:00Z, 10-25T23:00Z, 10-26T23:00Z (24, 25, 24 h apart) and labels `24 Oct`..`27 Oct`; (4) 1w ticks on Brussels Mondays (5 Oct 2026 is 2026-10-04T22:00Z); (5) year rule beyond 365 days (24-month window 2024-10-01T00:00Z to 2026-10-01T00:00Z, 1d: labels `["Jan 25","Jan 26"]`) and the month step (window 2026-01-01T00:00Z to 2026-10-01T00:00Z, 1w: ticks 03-31T22:00Z, 06-30T22:00Z, 09-30T22:00Z, labels `["01 Apr","01 Jul","01 Oct"]`); (6) intraday never uses it; (7) spring, 3 h step, window 28 Mar 22:00Z to 29 Mar 04:00Z: ticks 23:00Z, 01:00Z, 04:00Z, labels `["29 Mar","03:00","06:00"]`; (8) spring, 1 h step, window 29 Mar 00:00Z-03:00Z: `["29 Mar","03:00","04:00","05:00"]`, no `02:00`; (9) autumn, 1 h step, window 24 Oct 23:00Z to 25 Oct 03:00Z: `["25 Oct","02:00","03:00","04:00"]`, `02:00` once (the 01:00Z tick skipped), and a 15m frame, window 2026-10-25T00:30Z to 01:30Z: ticks 00:30Z and 00:45Z only, labels `["25 Oct","02:45"]`; (10) a 23:30Z instant belongs to the next Brussels day in winter and summer; (11) `brusselsAxis.format` returns the tick's own label and formats off-tick values in Brussels; (12) degenerate or invalid domains give at most one tick.
- `chart-freshness.test.ts` (+2): a winter caption (`... 13:00 CET`); a bar whose Brussels date differs from its UTC date (22:30Z gives `2026-10-04 00:30 CEST`). `ScreenerBoard.test.tsx` (+1): the `1d` chip title is `1d candle from 2026-10-03 02:00 CEST (forming)` and the N/A chip keeps its reason title. `spaghetti-lines.test.ts` (+3): day-level span; intraday span with one abbreviation; span across 25 Oct with both. `btc-leg-lines.test.ts` (+1): first bar 2026-03-28T23:30:00Z reads `2026-03-29`.
- `test_refresh_router.py` (+3, numbered 4-6): `server_time` is `Z` and equals the worker clock; with no worker it equals the patched `ccxt_adapter._now`, and is `None` with the other 10 keys intact when that patched clock raises; `RefreshStatus` in `refresh.ts` matches the `status()` keys and nullability (parse the interface as `test_layout.py` does).
- Playwright `brussels-time.spec.ts` (hybrid, 3): (1) the BTC box caption equals `Last bar <oracle>` for the API's `last_bar_ts` under the Tokyo zone; (2) the `/screener` main text has no whole word `UTC`, both span lines contain `(Brussels time)`, the `1d` chip tooltip matches `candle from \d{4}-\d\d-\d\d \d\d:\d\d (CET|CEST)`; (3) `GET /api/refresh/status` returns a `Z` `server_time` within 120 s of the host clock and the 10 old keys.

**Gates and probe:** "S11a exact gates" (G-S11a-1..13, P-S11-1).
**Lane:** capped lane yes: one read-only reviewer (Python and TS lockstep, stale `UTC` comments, relative imports in island-reachable files, no `Date.UTC` in display strings), tester at EVL. **Budget [estimate]:** 90 tool calls, 70 minutes, 3 CI polls, 3.0-3.8 USD, 1 full pytest run, e2e twice.

**Risks:** (1) Intl data may differ between Node and Chromium: the e2e oracle is arithmetic, so a difference fails visibly. (2) A daily candle now reads 01:00 or 02:00: correct but surprising; the probe says so. (3) 10 existing goldens change: the table is closed, any other failure stops the worker.

**Rollback:** revert the PR; the extra status key is harmless.

## S11b: poller, freshness strip, in-place chart updates (RT3, capped subagent lane: yes)

**Goal:** the page checks the server every 60 s while visible; boxes, drill-down, spaghetti and BTC charts update in place (zoom, scroll, selection kept; unchanged charts untouched); the strip shows the server's refresh times in Brussels time with an overdue marker; a failed check is visible and never wipes data. Base = the S11a merge SHA.

**Owned (exact):** new `web/lib/{live-poll,refresh-strip,same-data,use-simple-lines}.ts`, `web/lib/api/refresh.ts`, `web/components/screener/{LiveProvider,FreshnessStrip}.tsx`, `web/islands/live-props.svelte.js`; edited `web/lib/{chart-viewport,island-loader,chart-freshness}.ts`, `web/islands/{simple-lines.svelte,entry.js}`, `web/components/chart/{ChartFreshness,MiniChart}.tsx`, `web/components/screener/{ScreenerBoard,SpaghettiChart,BtcLegChart,DrillDownView,CoinPanel}.tsx`, `web/app/screener/page.tsx`, `web/app/globals.css`; the vitest files and `web/e2e/live-refresh.spec.ts` named under Tests; backlog stubs `process/general-plans/backlog/screener-{live-ondemand-states-contrast,passive-polls}_NOTE_<dd-mm-yy>.md`; report `screener-batch4-s11b_REPORT_<dd-mm-yy>.md`.
**Forbidden:** FORBIDDEN list, all of `api/`, S11a files (`web/lib/{brussels-time,chart-time-format,spaghetti-lines,btc-leg-lines}.ts`, `web/lib/types/*`; a missing export stops the worker), other existing tests.

**Rules (locked):**
- **P1 Poller** (`LivePoller`, pure, no React). `start()` runs one check at once, then the next 60 000 ms (`POLL_INTERVAL_MS`) after the previous check SETTLES (a `setTimeout` chain: no overlap). Each check has an `AbortController` aborted after 10 000 ms. The n-th consecutive failure waits `min(60 000 * 2^n, 300 000)` ms (120, 240, 300, 300 s); a success resets. Hidden tab (`document.visibilityState`, read in `start()` and on `visibilitychange`; the constructor touches no `document` or `window`): timer and in-flight check cancelled, nothing runs; visible: one check at once, then the cadence. An abort from `stop()` or a hidden tab is neither a failure nor a settled check (snapshots unchanged); only the 10 s timeout and a rejected or non-OK answer fail. `start()` is idempotent and restartable after `stop()` (StrictMode runs effects twice). Snapshots for `useSyncExternalStore`, stable between changes: data `{tick, dataVersion}`, status `{phase, failures, lastGood}` (last status plus its server instant), clock `{nowMs}`. `tick` rises after every settled check except the first (the baseline); `dataVersion` rises when `running`, `last_tick_started` or `last_tick_finished` differ from the previous success, and on every success while the worker is not running.
- **P2 Clock.** `serverNowMs = lastGood.serverMs + (mono() - monoAtSuccess)`, `mono` defaulting to `performance.now`; a 30 s ticker (visible only) refreshes the clock snapshot. A success with a null or unparsable `server_time` counts for `tick` and `dataVersion` but does not sync the clock (`lastGood.serverMs` unchanged, null if none; `useLiveClock()` null, so captions use the payload); the strip prints `Page checked n/a`, no age. Display code never calls `Date.now()` or `new Date()` without an argument (`S11-clock`).
- **P3 Provider and consumers.** `LiveProvider` makes one poller (`useRef`), shares it by a stable context value, takes injectable `fetchStatus`, `intervalMs`, `mono`; hooks `useLiveData`, `useLiveClock`, `useLiveStatus` (each `useSyncExternalStore` has a `getServerSnapshot`). With no provider `useLiveData` is `{tick:0, dataVersion:0}` and `useLiveClock` null: nothing auto-refetches. Board and open drill-down re-run their fetch effect on `tick`; spaghetti and BTC charts on `dataVersion`. On success `setX(prev => shareStructure(prev, next, VOLATILE))` and the error is cleared: `shareStructure` (`same-data.ts`) returns `prev` itself when equal ignoring `VOLATILE` (`server_time`, `fetched_at`, `clock_skew_seconds`) at any depth, else `next` with each equal subtree replaced by the previous object. On failure the data stays and the existing error element shows (`board-error`, `spaghetti-error`, `drilldown-error`, `btc-leg-error`); `DrillDownView` shows `drilldown-error` above the retained chart when `view` exists (it replaces the ternary at `DrillDownView.tsx:69-82`); `ScreenerBoard` renders it with `key={drillDownSymbol}`; a timeframe or symbol change keeps the old data until the new arrives, an older timeframe's answer is ignored. `CoinPanel` is `React.memo`; `fetchRefreshStatus(signal)` throws an error naming the status (the poller owns the abort).
- **P4 In place.** `useSimpleLines(ref, props, mountKey)` mounts the island once per `mountKey` (MiniChart `timeframe|height`, spaghetti its chart timeframe, BTC `btc`) and calls the handle's `update(props)` when the memoised props change; the latest props live in a ref. `mountSimpleLines` keeps returning a dispose FUNCTION with an optional `update` property (a handle without it is re-mounted). `live-props.svelte.js` holds a `$state.raw` object and gives `mount` a props object of getters over it; `entry.js` returns `Object.assign(dispose, { update })`. The island resets zoom only when the timeframe or the list of line keys changes (the reset `$effect` reads `range` inside `untrack`) and keeps a zoomed range through an update with `keepRange(range, extent)` (new, pure, in `chart-viewport.ts`: clamped into the new extent, span kept, null when no longer zoomed). Ladder if the seeded zoom test fails twice on one assertion: the approach above; then an exported `update(next)` in `simple-lines.svelte` reassigning the destructured props; then `needs_input`.
- **P5 Captions.** `ChartFreshness` ages against `useLiveClock()` when present (payload `server_time` otherwise) through `freshnessCaption(fields, nowMs?)`; `stale` stays the payload's.
- **P6 Strip** (`FreshnessStrip`, first in `page.tsx` inside `LiveProvider`, which also wraps `BtcLegChart` and `ScreenerBoard`). `<section aria-label="Data freshness" data-testid="freshness-strip">`, no heading, no `aria-live`; testids `strip-refreshed`, `-next`, `-checked`, `-overdue`, `-failed`, `-zone`, `-help`; a visually hidden `<div role="status" aria-live="polite" data-testid="strip-announcer">` that changes only on a state change; height reserved from the first render (`Checking the server...`). Copy: `Server refreshed 14:15 CEST (3 min ago)`, `Next refresh 14:30 CEST`, `Page checked 14:17 CEST`, `Times are Brussels time, CEST (+02:00).`, help `Page checked is the last time this page got an answer from the server, by the server's clock; it re-checks every minute while this tab is visible. Overdue means more than 5 min past the scheduled refresh time.` A time on another Brussels day than the server clock gets a `DD MMM` prefix. Other states: worker off `Automatic server refresh is off (<reason>). This page still re-checks every minute.` (reason `SCREENER_REFRESH_WORKER=0` reads "switched off by SCREENER_REFRESH_WORKER=0", `not-started` and `not-running` "not running", `start-failed` "failed to start", `stopped` and others as is); no tick yet `Server has not finished its first refresh. Next refresh <t>`; `last_tick_failed > 0` adds `<n> pairs did not refresh in that run`; `backoff_seconds > 0` adds `Refreshes are failing; retrying about <t>`; a failed check shows `Could not check the server. Last answer from the server: <t>.` and keeps the last items. No verdict or badge wording (`S11b-words`).
- **P7 Overdue.** `overdue` = the worker is running AND `serverNowMs > next_tick_at + 300 000` (strictly greater; `OVERDUE_GRACE_SECONDS = 300` covers a running tick). Marker `Refresh overdue: expected <t>`. Announcer: `Refresh is overdue`; `Could not check the server`; back from overdue `Refresh is no longer overdue`; back from failed `The server answered again`; else unchanged.
- **P8 Styling.** `globals.css`: tokens only; classes `.freshness-strip*` and `.visually-hidden`; `min-height` on the strip; the overdue marker is a border and weight, not coloured text; no text opacity; no name the CSS parsers read.

**Existing tests that break:** none expected; any other red test stops the worker (convention 6).

**Tests (63 vitest, 4 Playwright; plain functions):**
- `live-poll.test.ts` (12, fake timers, fake `mono`): (1) first check at once, next 60 s after the previous SETTLES; (2) no overlap: a never-resolving fetch blocks a second call until the 10 s abort; (3) hidden, also when started hidden: nothing runs for 10 min, and a hidden abort leaves every snapshot field unchanged; (4) visible: one check at once; (5) waits after consecutive failures 120, 240, 300, 300 s, a success returns to 60 s; (6) a failure keeps `lastGood`; a null `server_time` succeeds without syncing the clock; (7) `serverNowMs` = last server instant plus monotonic elapsed, unchanged by `vi.setSystemTime` to 2001; (8) re-sync on every success; (9) `dataVersion` only on a changed `last_tick_finished` or a `running` flip, every success when not running; (10) `tick` after each settled check except the first; (11) `stop()` mid-check leaves no timer, listener or failure, and `start()` works again; (12) `checkNow()` never leaves two timers.
- `refresh-strip.test.ts` (10): waiting (a null `server_time` prints `Page checked n/a`, no age); off with each reason; first refresh pending; ok lines golden (3 min ago); overdue false at `next_tick_at + 300 s`, true at +301 s; never overdue when off or first; day prefix and CET after 2026-10-25T01:00Z; backoff and failed-pair copy; a failed check keeps the last items; no verdict word and no `UTC` in any string.
- `same-data.test.ts` (5): equal returns `prev`; volatile keys ignored at any depth; a changed leaf gives a new root while unchanged siblings keep identity; array length and order changes; null and scalars. `refresh-api.test.ts` (3): URL and parse; a non-OK answer names the status; the signal is passed, an abort rejects.
- `use-simple-lines.test.tsx` (7, `vi.mock("@/lib/island-loader")` at file top): (1) mounts once with the latest props; (2) a props change calls `update` once, no re-mount; (3) a handle without `update` is re-mounted; (4) a `mountKey` change disposes and re-mounts; (5) unmount disposes; (6) a change before the async mount ends mounts with the latest props, no `update`; (7) dispose before resolve never mounts.
- `FreshnessStrip.test.tsx` (8): (1) ok golden with testids, zone line, help text; (2) CEST to CET across 2026-10-25T01:00Z; (3) no heading and no `aria-live` on the container, announcer `role="status"`; (4) five polls in one state leave the announcer unchanged, overdue sets it once, recovery sets `Refresh is no longer overdue`; (5) overdue at +301 s, not +300 s; (6) a failed check keeps the last items and sets failure line and announcer; (7) worker-off and first-refresh copy; (8) day prefix.
- `ScreenerBoardLive.test.tsx` (12, `LiveProvider` with injected `fetchStatus`, fake timers): (1) no provider: one board fetch, no timer; (2) a tick refetches the CURRENT timeframe (after a switch to 1h) and the focused timeframe button keeps focus; (3) an identical payload (only volatile keys differ): zero island `update` calls; (4) one changed coin causes one `update`, the others none; (5) a failed refetch keeps the panels and shows `board-error`, the next success clears it; (6) the open drill-down stays open and refetches with its own timeframe; a failed tick refetch keeps `mini-chart` beside `drilldown-error`; another coin's "Drill down" re-mounts the island (`mountSimpleLines` mock called twice); (7) a slow answer for the old timeframe is ignored; (8) spaghetti and BTC refetch on `dataVersion` only and keep data on failure; (9) hidden: no board request in 5 min; (10) resume: an immediate status check, then a board refetch; (11) a caption age follows the live clock; (12) inside `<StrictMode>` the first check triggers no second board fetch and no `Could not check the server`.
- `chart-viewport.test.ts` (+4): `keepRange` null stays null; a range inside the extent is unchanged; a slid extent clamps with the span kept; a range no longer zoomed gives null. `chart-freshness.test.ts` (+2): `nowMs` overrides the payload clock; a negative age reads `<1 min`.
- Playwright `live-refresh.spec.ts` (hybrid, 4; `page.clock.install()` before `goto`; status and board are the real answers with edits: the e2e worker is off, so the status becomes `running: true` with `last_tick_finished` 3 min before its `server_time`): (1) strip times equal the oracle for the status instants, `CEST` or `CET` by the arithmetic rule; (2) `window.__keep = 1` survives; a board answer with one more BTC bar plus `page.clock.runFor(61_000)` moves the BTC plot's `data-visible-to` to that bar, board requests rising by exactly 1; (3) after a ctrl-wheel zoom the update keeps `data-zoomed="true"`, `data-visible-from` and `window.scrollY`, an open drill-down stays open; (4) status and board aborted: after 61 s the strip says `Could not check the server`, panels stay; routes restored and `runFor(120_000)`: refreshed line back, announcer `The server answered again`. Without `page.clock` (U2), trigger a check by overriding `document.visibilityState` to `hidden`, then `visible`, and dispatching `visibilitychange` in `page.evaluate`; test 4 uses it for failure and recovery (no 120 s wait); only test 2 keeps a real 61 s wait (`test.setTimeout(150_000)`).

**Gates and probe:** "S11b exact gates" (G-S11b-1..11, P-S11-3 to P-S11-5).
**Lane:** capped lane yes: one read-only reviewer (island update path, stable `useSyncExternalStore` snapshots and server snapshot, a poller constructor free of `document` and `window`, clock rule, word and storage scans), tester at EVL. **Budget [estimate]:** 130 tool calls, 120 minutes, 4 CI polls, 4.2-5.7 USD, 2 full-suite runs, e2e three times.

**Risks:** (1) the island update path is the least certain part (U1); the ladder in P4 decides. (2) `page.clock` with the Next dev server (U2): fallback is the `visibilitychange` trigger in the e2e description, plus a real 61 s wait in test 2 only. (3) The exchange is busier while a page is open (P-S11-5). (4) A snapshot recreated on every call would loop `useSyncExternalStore`; the reviewer checks it. (5) Stay green unedited: the 28 `components/screener` tests, `ChartFreshness.test.tsx`, `screener-api.test.ts`, the CSS parsers, e2e tests 1-9 and the contrast routes (the strip is outside the grid, with no heading and no `coin-panel-` testid).

**Rollback:** revert the PR; S11a stays and the page returns to load-once behaviour.

## Touchpoints

Changed: the owned files of S11a and S11b. Read only: `api/data/freshness.py` (`iso_z`, `FORMING_TTL`), `api/data/ccxt_adapter.py` (`_now`, refresh hook), `api/routers/refresh.py` (returns `status()` unchanged), `api/analytics/screener_board.py`, `api/scripts/seed_e2e_cache.py` (bars end at the current time), `web/playwright.config.ts` (ports 8001 and 3100), `web/e2e/contrast.spec.ts`, `web/lib/types/screener.ts`.

## Public Contracts

- Added: `GET /api/refresh/status` key `server_time` (ISO UTC with trailing `Z`, or null; convention 3); TS `RefreshStatus`. Unchanged: the other 10 keys, `POST /api/refresh/now`, board, chart-view, spaghetti and BTC payloads, every timestamp already shipped, CORS. While visible the page issues one small status GET a minute and repeats the board GET it already makes every minute (plus the open drill-down's chart GET; spaghetti and BTC once per server refresh).
- Display contract: every time on `/screener` is Europe/Brussels with CET or CEST; the browser zone and locale never matter; candles still open at UTC boundaries.
- Security scan (STRIDE, quick): no auth, key or secret surface; the new field is a clock reading; read-only GETs with a 10 s abort and a capped backoff (no request storm after an outage); copy renders as React text; nothing is stored in the browser.

## Blast Radius

S11a 25 touches, S11b 35 (60 of the 100 limit). RT3: a public endpoint field, a display module used by every caption, the shared chart island (its only callers are the three screener components), a polling layer. Test-count effect: pytest 996 to 999, vitest 251 to 331 (34 to 42 files), e2e screener+contrast 17 unchanged (24 with the new specs), full suite 65 to 72 (6 to 8 files).

## Acceptance Criteria

The criterion table is in the Validate Contract skeleton; every id links to its gate and to its user decision: AC-S11a-1,2,3 = U3; AC-S11a-4 = U2 prerequisite; AC-S11b-1,2,3,4 = U1; AC-S11b-5,6 = U2 and the clock rule; AC-S11b-7 = accessibility and contrast; AC-S11a-5 and AC-S11b-8 = regression. Residuals AC-S11a-1r, AC-S11a-2r, AC-S11b-8r, AC-S11b-9r are Known-Gap with probes or a backlog stub and keep their gates CONDITIONAL.

## Verification Evidence

| Gate / Scenario | Strategy | Proves SPEC criterion |
|---|---|---|
| G-S11a-1..2 pytest status field and full run | Fully-Automated | U2 prerequisite, no regression (AC-S11a-4,5) |
| G-S11a-3..4 vitest labels, DST, goldens | Fully-Automated | U3 (AC-S11a-1,2,3) |
| G-S11a-11..12 e2e under another browser zone | Hybrid | U3 end to end (AC-S11a-1,3,4,5) |
| P-S11-1, P-S11-2 PC check of the labels and of the 25 Oct change | Agent-Probe | U3 on the real display (AC-S11a-1r, AC-S11a-2r) |
| G-S11b-1..2 vitest poller, strip, in-place, board | Fully-Automated | U1, U2 (AC-S11b-1..7) |
| G-S11b-9..10 e2e live, screener, contrast, full suite | Hybrid | U1, U2 end to end (AC-S11b-1..8) |
| P-S11-3..5 PC: live cycle, hidden tab, outage, request rate | Agent-Probe | U1 in a real browser (AC-S11b-9r) |

## Risk Predictions (condensed 5-persona pass)

Security: read-only GETs, no secret. Performance: one cheap status GET a minute plus the board GET the page already made; the exchange sees more pair refreshes while a tab is open (P-S11-5). Data integrity: one added key, no data change. User: a failed check is visible and keeps the last data; DST and a wrong-zone browser are tested. Maintainability: one zone module, a pure poller, a pure strip model.

## Implementation Checklist (atomic; one slice per worker)

**S11a:** 1 baseline (pytest, vitest, tsc, islands, e2e 17). 2 stubs for the 17 vitest, 3 pytest and 3 e2e tests and the NEW text in the 10 changed goldens; red runs (G-S11a-13). 3 `status()` and `types/refresh.ts`. 4 `brussels-time.ts`. 5 `chart-time-format.ts` and the island import. 6 caption, span and tooltip helpers and the comments. 7 real tests, goldens re-derived (convention 10). 8 `brussels-time.spec.ts` and the `screener.spec.ts` line. 9 gates G-S11a-1..13 once, after the commit. 10 report, PR, CI, tester.
**S11b** (after S11a merged): 1 baseline. 2 stubs for the 63 vitest and 4 e2e tests; red run (G-S11b-11). 3 `same-data`, `live-poll`, `refresh-strip`, `api/refresh` with tests. 4 `keepRange` and `chart-freshness`. 5 island: `live-props.svelte.js`, `simple-lines.svelte`, `entry.js`, `island-loader.ts`, `use-simple-lines`. 6 `LiveProvider`, `FreshnessStrip`, CSS, `page.tsx`. 7 `MiniChart`, `SpaghettiChart`, `BtcLegChart`, `DrillDownView`, `ScreenerBoard`, `CoinPanel`, `ChartFreshness`. 8 component tests. 9 `live-refresh.spec.ts`. 10 gates G-S11b-1..11 once, after the commit (an offline `pnpm exec next build`, if it runs, is a report line, not a gate). 11 backlog stubs, report, PR, CI, tester.

## Phase Completion Rules

`CODE DONE` = PR open with green gates in the report; `VERIFIED` only after independent confirmation (tester or CI on the head SHA, plus the tester's e2e run) AND the slice's PC probe. A slice may merge only when every gate including the e2e gates is green, CI is green on the head SHA and report heading 9 holds no open `needs_input` or `blocker`; otherwise it stops at `review`. S11a stays at `review` until P-S11-1, S11b until P-S11-3. P-S11-2 (25 Oct 2026) is date-bound: it holds no merge and closes AC-S11a-2r. A diff touching CLAUDE.md, AGENTS.md, README.md, `.claude/`, `.github/`, `deploy/` stops at `review`. After the S11b EVL the planner updates `current-state.md` line 50 ("chart axes use UTC labels"; line 48, the refresh worker, can mention `server_time`), notes in the batch-2 plan that the S2 UTC axis decision is superseded for display by U3, and registers S11a and S11b in MASTER-PLAN (planner steps; this plan does not edit MASTER-PLAN).

## Open and resolved questions

| # | Question | Options | Recommendation |
|---|---|---|---|
| Q1 RESOLVED 10-10-26 | The estimate for S11 is 7.2-9.5 USD (two slices, testers included) against the 4-6 USD first expected. | The user raised the programme ceiling to 75 USD (about 45.1 spent, 29.9 left): S5b's 5.5-8 still fits with 20.4 left at the top S11 figure. | Closed: build S11a then S11b and re-price S11b from the real S11a cost; no budget question remains |

Resolved by the user 10-10-26: U1 poll every 60 s quietly, U2 proof = strip plus per-chart last-bar line, U3 always Europe/Brussels with the offset shown, U4 S11 before S5b, Q1 ceiling 75 USD. Decided without asking (reversible): the board is fetched every cycle as chosen (U1), the spaghetti and BTC charts only when the server's refresh changed; overdue = more than 5 min past the scheduled time; the first check is the baseline; backoff capped at 300 s; a daily candle reads 01:00 or 02:00 with no extra note on the page; ticks follow Brussels midnights; the strip has no heading; the offset reads `CET`/`CEST` and `+01:00`/`+02:00`, never `UTC`; the poll interval is a constant; a refresh that changes nothing causes no state change and no island update, while caption ages and the strip move by design.

## Hand-over to S5b (the planner re-validates the S5b plan after the S11b merge)

Files changed here that `process/general-plans/active/screener-batch3_09-10-26/screener-batch3_PLAN_09-10-26.md` also cites:
- `ScreenerBoard.tsx` (S11b): reads `useLiveData`, shares structure, clears `error` on success; `CoinPanel` becomes `memo`, so S5b must pass stable props (an inline `actions={<.../>}` element defeats the memo: harmless but wasteful). `ScreenerBoard.test.tsx` (S11a): 10 tests (+1 chip title), caption golden is Brussels text; S5b's "9 renders" becomes 10 `render(<ScreenerBoard` calls.
- `CoinPanel.tsx` (S11a chip title, S11b memo); `DrillDownView.tsx` and its test (S11a golden; S11b tick refetch); `SpaghettiChart.tsx` (S11b: the mount effect becomes `useSimpleLines`; S5b's controlled `hidden`, sorted-key Set and `reloadToken` build on that; its "mounts once" test mocks `@/lib/island-loader` and the mocked `mountSimpleLines` should return `Object.assign(dispose, { update })`, a plain function also works); `SpaghettiChart.test.tsx` (S11a golden); `BtcLegChart.tsx` and its test (not cited by S5b, changed here).
- `web/e2e/screener.spec.ts` (S11a: test 7, one line, no shift; S5b edits test 1); `contrast.spec.ts` (not edited; it now also audits the strip above the board).
- `web/app/globals.css` (S11b adds `.freshness-strip*` and `.visually-hidden`; S5b's plan says it adds `.visually-hidden`: reuse it). `web/app/screener/page.tsx` (S11b; S5b forbids it, still right).
- S5b's FORBIDDEN names `web/islands/` and `web/lib/{chart-viewport,island-loader,spaghetti-lines}.ts` (batch-3 line ~130): still true for S5b; they changed here first.
- `web/components/screener/__tests__/ScreenerBoardLive.test.tsx` (S11b, 12 tests, each renders `ScreenerBoard` inside a `LiveProvider`): not in S5b's `S5b-scope` test list (batch-3 line ~328) nor in its existing-tests-that-break table (line ~150), yet S5b makes the board also call `fetchLayout` (default: a real fetch) and render panels only after board and layout settled. The re-validated S5b plan must add it to that table (each render gets `fetchLayout={fetchLayoutStub}`), to its Owned list and to `S5b-scope`; the counts in G-S5b-1/2 do not change; `live-refresh.spec.ts` and `brussels-time.spec.ts` are covered by G-S5b-10 only (G-S5b-9 names three specs). This plan does not edit the S5b plan.
- New arithmetic for S5b: pytest 999; vitest baseline 331 in 42 files, so G-S5b-2 becomes 396 in 49 files; `components/screener` existing tests 48 in 6 files (28 + 8 + 12), so G-S5b-1 becomes 113 in 13 files; G-S5b-9 stays 24 (its specs are unchanged), G-S5b-10 full suite becomes 79 in 9 files (72 + 7); `S5b-scope` stays valid.

## Later batches (dependencies only)

S5b (layout UI) after the S11b merge and the re-validation above; S9 needs S5b; S10 is separate. Backlog stubs written by S11b: `screener-passive-polls_NOTE` (a read flag so polling does not queue exchange refreshes; only if P-S11-5 shows too much traffic) and `screener-live-ondemand-states-contrast_NOTE` (contrast of the overdue and failed strip variants).

## Validate Contract

(skeleton by the planner; vc-validate-agent completes it in PVL and stamps it; the tables are the contract as planned; Known-Gap residuals carry a proving strategy, never Known-Gap)
supersedes: none (first draft)
Status: PENDING
Gate: PENDING
generated-by: plan-agent (skeleton)

### Test gates

gap-resolution: A proven now / B added by this plan's checklist / C deferred to a named later step / D backlog stub (residual, keep-active).

| criterion id | behavior | strategy | proving test | gap-resolution |
|---|---|---|---|---|
| AC-S11a-1 | every axis label, caption, tooltip and span on the screener is Brussels time with CET or CEST, whatever the browser zone and locale | Fully-Automated | G-S11a-3 `brussels-time.test.ts` 1-8, `chart-time-format.test.ts` 1-12, `chart-freshness.test.ts`, `spaghetti-lines.test.ts`, `btc-leg-lines.test.ts`, `ScreenerBoard.test.tsx` chip title; hybrid G-S11a-11 test 1 (Tokyo zone, arithmetic oracle) | B (run: C) |
| AC-S11a-2 | the 29 Mar and 25 Oct 2026 changes and Brussels day-boundary ticks are right (skipped hour, repeated hour, 23 h and 25 h days) | Fully-Automated | G-S11a-3 `brussels-time.test.ts` 2-5, `chart-time-format.test.ts` 1-3, 7-9 | B |
| AC-S11a-3 | no visible word `UTC` on `/screener`; payload timestamps and `ChartBar.timestamp` unchanged | Fully-Automated | G-S11a-3 component goldens, `S11a-utc`; hybrid G-S11a-11 test 2 | B (run: C) |
| AC-S11a-4 | `/api/refresh/status` carries `server_time` (Z), the other 10 keys unchanged, the TS mirror matches | Fully-Automated | G-S11a-1 `test_refresh_router.py` 1, 4-6; hybrid G-S11a-11 test 3 | B (run: C) |
| AC-S11a-5 | no regression: other tests, screener and contrast e2e | Hybrid | G-S11a-2, G-S11a-4..6, G-S11a-11, G-S11a-12 | B (run: C) |
| AC-S11a-1r | axis labels in a real browser on the user's display | Agent-Probe | P-S11-1 (residual: the island is not unit-tested; labels come from the tested function) | C |
| AC-S11a-2r | the 25 Oct 2026 change on the real machine | Agent-Probe | P-S11-2 | C |
| AC-S11b-1 | the page checks every 60 s while visible and updates board, drill-down, spaghetti and BTC without a reload; checks never overlap; a stale timeframe answer is ignored | Fully-Automated | G-S11b-1 `live-poll.test.ts` 1-2, 9-10, `ScreenerBoardLive.test.tsx` 2, 7, 8, 12; hybrid G-S11b-9 test 2 | B (run: C) |
| AC-S11b-2 | no chart is updated and no panel state changes when its data did not change (only caption ages and the strip move); zoom, pan and the open drill-down (chart kept when a refetch fails) survive an update; another coin's drill-down starts unzoomed | Fully-Automated | G-S11b-1 `same-data.test.ts`, `use-simple-lines.test.tsx`, `chart-viewport.test.ts` `keepRange`, `ScreenerBoardLive.test.tsx` 3, 4, 6; hybrid G-S11b-9 test 3 | B (run: C) |
| AC-S11b-3 | a hidden tab makes no request; becoming visible checks at once; an abort from `stop()` or a hidden tab is neither a failure nor a settled check | Fully-Automated | G-S11b-1 `live-poll.test.ts` 3-4, 11, `ScreenerBoardLive.test.tsx` 9-10, 12 | B |
| AC-S11b-4 | a failed check backs off (120, 240, 300 s), is visible, keeps the last good data and recovers | Fully-Automated | G-S11b-1 `live-poll.test.ts` 5-6, `ScreenerBoardLive.test.tsx` 5-6, `FreshnessStrip.test.tsx` 6; hybrid G-S11b-9 test 4 | B (run: C) |
| AC-S11b-5 | the strip shows refreshed, next and checked in Brussels time with zone, the overdue rule exact and stated on screen, no verdict wording | Fully-Automated | G-S11b-1 `refresh-strip.test.ts`, `FreshnessStrip.test.tsx` 1-2, 5, 7-8; `S11b-words`; hybrid G-S11b-9 test 1 | B (run: C) |
| AC-S11b-6 | ages and the checked time come from the server's clock plus monotonic elapsed time, not from the browser's wall clock (the gate scans the display files) | Fully-Automated | G-S11b-1 `live-poll.test.ts` 7-8, `ScreenerBoardLive.test.tsx` 11; `S11-clock` | B |
| AC-S11b-7 | live region only on a state change, no heading, the strip passes the contrast audit in its default state | Fully-Automated | G-S11b-1 `FreshnessStrip.test.tsx` 3-4; hybrid G-S11b-9 contrast route | B (run: C) |
| AC-S11b-8 | no regression: screener, contrast and the full e2e suite | Hybrid | G-S11b-2..4, G-S11b-9, G-S11b-10 | B (run: C) |
| AC-S11b-8r | contrast of the overdue and failed variants | Hybrid | none today (Known-Gap residual): backlog `screener-live-ondemand-states-contrast_NOTE` (written by S11b); the audit reads the default state only | D (CONDITIONAL) |
| AC-S11b-9r | the live 15-minute cycle, a hidden tab and an API outage in a real browser; exchange request rate while open | Agent-Probe | P-S11-3, P-S11-4, P-S11-5 | C |

### S11a exact gates (repo root; baselines 996 pytest, 251 vitest in 34 files)

| Gate | Command | Expected |
|---|---|---|
| G-S11a-1 | `UV_FROZEN=1 uv run --project api pytest api/tests/routers/test_refresh_router.py -q` | 6 passed (3 + 3) |
| G-S11a-2 | `UV_FROZEN=1 uv run --project api pytest api/ -q` | 999 passed (996 + 3), 2 skipped, 5 deselected, 0 xfailed |
| G-S11a-3 | `cd web && pnpm exec vitest run lib/__tests__/brussels-time.test.ts lib/__tests__/chart-time-format.test.ts lib/__tests__/chart-freshness.test.ts lib/__tests__/spaghetti-lines.test.ts lib/__tests__/btc-leg-lines.test.ts components/chart components/screener` | 73 passed in 10 files (8 + 12 + 7 + 8 + 7 + 3 + 28) |
| G-S11a-4 | `cd web && pnpm test` | 268 passed in 35 files (251 + 17; 34 + 1) |
| G-S11a-5 | `cd web && pnpm exec tsc --noEmit --incremental false` | exit 0 |
| G-S11a-6 | `cd web && pnpm build:islands` | exit 0 |
| G-S11a-7 | `git diff --check` | exit 0, no output |
| G-S11a-8 | `S11a-scope`, `FORBIDDEN`, `S-secret-scan` (command block), after the commit | print nothing |
| G-S11a-9 | `FIXTURES` | prints nothing |
| G-S11a-10 | `S11a-utc`, `S11a-words` | print nothing |
| G-S11a-11 | Gate convention 4 with `screener.spec.ts contrast.spec.ts brussels-time.spec.ts` | 20 passed (10 + 7 + 3); NOT-RUN is not allowed |
| G-S11a-12 | Gate convention 4, no spec argument (full suite), once, after G-S11a-11 | 68 passed in 7 files (65 in 6 files from `playwright test --list`, re-recorded at spawn, plus 3) |
| G-S11a-13 | red-first: heading 6 holds the runs on the untouched base with stubs | G-S11a-1: 6 tests, 4 failed (3 stubs and the `STATUS_KEYS` shape test), 2 passed; G-S11a-3: 73 tests in 10 files, 37 failed (27 stubs, 10 changed goldens), 36 passed; full `pnpm test`: 268 in 35 files, 37 failed |
| P-S11-1 | user PC after pull, `deploy/build-web.ps1`, restart both tasks: the checklist under "Probes" | Brussels labels everywhere, none says UTC, unchanged by the Windows zone |

### S11b exact gates (S11a merge SHA recorded as the base; counts relative to 999 pytest, 268 vitest in 35 files, e2e 68 in 7 files)

| Gate | Command | Expected |
|---|---|---|
| G-S11b-1 | `cd web && pnpm exec vitest run lib/__tests__/live-poll.test.ts lib/__tests__/refresh-strip.test.ts lib/__tests__/same-data.test.ts lib/__tests__/refresh-api.test.ts lib/__tests__/use-simple-lines.test.tsx lib/__tests__/chart-viewport.test.ts lib/__tests__/chart-freshness.test.ts components/chart components/screener` | 111 passed in 14 files (12 + 10 + 5 + 3 + 7 + 14 + 9 + 3 + 48) |
| G-S11b-2 | `cd web && pnpm test` | 331 passed in 42 files (268 + 63; 35 + 7) |
| G-S11b-3 | `cd web && pnpm exec tsc --noEmit --incremental false` | exit 0 |
| G-S11b-4 | `cd web && pnpm build:islands` | exit 0 |
| G-S11b-5 | `UV_FROZEN=1 uv run --project api pytest api/tests/analytics/test_no_verdict_symbols.py api/tests/routers/test_refresh_router.py -q` | 8 passed (2 + 6; no api change) |
| G-S11b-6 | `git diff --check` | exit 0, no output |
| G-S11b-7 | `S11b-scope`, `FORBIDDEN`, `S-secret-scan`, `FIXTURES`, after the commit | print nothing |
| G-S11b-8 | `S11b-utc`, `S11b-words`, `S11-nostore`, `S11-clock` | print nothing |
| G-S11b-9 | Gate convention 4 with `screener.spec.ts contrast.spec.ts brussels-time.spec.ts live-refresh.spec.ts` | 24 passed (10 + 7 + 3 + 4); NOT-RUN is not allowed |
| G-S11b-10 | Gate convention 4, no spec argument (full suite), once, after G-S11b-9 | 72 passed in 8 files |
| G-S11b-11 | red-first: heading 6 holds the G-S11b-1 red run | on the untouched base with stubs: 111 tests in 14 files, 63 failed, 48 passed; full `pnpm test`: 331 in 42 files, 63 failed, 268 passed |
| P-S11-3..5 | user PC after pull, `deploy/build-web.ps1`, restart both tasks: the checklist under "Probes" | live update with zoom kept; hidden tab resumes at once; outage visible and recovers; request rate sane |

### Scope and secret-hygiene commands (run from the repo root, after the commit; the labels above refer to these)

```
# FORBIDDEN: nothing may match
git diff --name-only origin/main...HEAD | grep -E '^(CLAUDE\.md|AGENTS\.md|README\.md|\.claude/|\.github/|deploy/|api/scripts/|api/tests/deploy/|api/data/(lse_adapter|equities_store|cache|ccxt_adapter|freshness)\.py|process/MASTER-PLAN\.md|process/context/current-state\.md|process/archive/)'

# FIXTURES: nothing may match
git diff --name-only --diff-filter=MDR origin/main...HEAD | grep -E '/fixtures/'

# S-secret-scan: nothing may match (added lines only)
git diff origin/main...HEAD | grep -nE "^\+.*(Bearer [A-Za-z0-9._-]{12,}|(API_KEY|SECRET|TOKEN|PASSWORD)[A-Z_]* *[:=] *[\"'][A-Za-z0-9+/_-]{12,})"

# S11a-scope: nothing may match
git diff --name-only origin/main...HEAD | grep -vE '^(api/data/refresh_worker\.py|api/tests/routers/test_refresh_router\.py|web/lib/(brussels-time|chart-time-format|chart-freshness|spaghetti-lines|btc-leg-lines|island-loader)\.ts|web/lib/types/refresh\.ts|web/components/screener/CoinPanel\.tsx|web/components/chart/ChartFreshness\.tsx|web/islands/simple-lines\.svelte|web/lib/__tests__/(brussels-time|chart-time-format|chart-freshness|spaghetti-lines|btc-leg-lines)\.test\.ts|web/components/chart/__tests__/ChartFreshness\.test\.tsx|web/components/screener/__tests__/(ScreenerBoard|DrillDownView|SpaghettiChart|BtcLegChart)\.test\.tsx|web/e2e/(screener|brussels-time)\.spec\.ts|process/general-plans/active/screener-batch4_10-10-26/screener-batch4-s11a_REPORT_[0-9-]+\.md)$'

# S11a-utc: nothing may match (MiniChart.tsx is S11b's and island-loader.ts keeps a true data comment; brussels-time.ts and chart-time-format.ts need Date.UTC)
grep -nw 'UTC' web/lib/chart-freshness.ts web/lib/spaghetti-lines.ts web/lib/btc-leg-lines.ts web/components/screener/CoinPanel.tsx web/components/chart/ChartFreshness.tsx web/islands/simple-lines.svelte

# S11a-words: nothing may match
grep -niwE 'bullish|bearish|bull|bear|buy|sell|overbought|oversold|confidence|(out|under)perform(ing)?|risk-(on|off)|favorable' web/lib/brussels-time.ts web/lib/chart-time-format.ts web/lib/chart-freshness.ts web/lib/spaghetti-lines.ts web/lib/btc-leg-lines.ts web/components/screener/CoinPanel.tsx

# S11b-scope: nothing may match
git diff --name-only origin/main...HEAD | grep -vE '^(web/lib/(live-poll|refresh-strip|same-data|use-simple-lines|chart-viewport|island-loader|chart-freshness)\.ts|web/lib/api/refresh\.ts|web/islands/(simple-lines\.svelte|entry\.js|live-props\.svelte\.js)|web/components/(chart/(ChartFreshness|MiniChart)|screener/(LiveProvider|FreshnessStrip|ScreenerBoard|SpaghettiChart|BtcLegChart|DrillDownView|CoinPanel))\.tsx|web/app/(screener/page\.tsx|globals\.css)|web/lib/__tests__/(live-poll|refresh-strip|same-data|refresh-api|chart-viewport|chart-freshness)\.test\.ts|web/lib/__tests__/use-simple-lines\.test\.tsx|web/components/screener/__tests__/(FreshnessStrip|ScreenerBoardLive)\.test\.tsx|web/e2e/live-refresh\.spec\.ts|process/general-plans/backlog/screener-(live-ondemand-states-contrast|passive-polls)_NOTE_[0-9-]+\.md|process/general-plans/active/screener-batch4_10-10-26/screener-batch4-s11b_REPORT_[0-9-]+\.md)$'

# S11b-utc: nothing may match
grep -nw 'UTC' web/lib/chart-freshness.ts web/lib/refresh-strip.ts web/components/screener/{CoinPanel,FreshnessStrip,LiveProvider,ScreenerBoard,DrillDownView,SpaghettiChart,BtcLegChart}.tsx web/components/chart/{ChartFreshness,MiniChart}.tsx web/islands/simple-lines.svelte

# S11b-words: nothing may match
grep -niwE 'bullish|bearish|bull|bear|buy|sell|overbought|oversold|confidence|(out|under)perform(ing)?|risk-(on|off)|favorable|healthy|unhealthy|degraded|broken|good|bad|alert|badge|verdict|score|rating' web/lib/{refresh-strip,live-poll}.ts web/components/screener/{FreshnessStrip,LiveProvider}.tsx

# S11-nostore: nothing may match
grep -nE 'localStorage|sessionStorage|indexedDB|document\.cookie' web/lib/{live-poll,refresh-strip,same-data,use-simple-lines}.ts web/lib/api/refresh.ts web/components/screener/{FreshnessStrip,LiveProvider}.tsx

# S11-clock: nothing may match
grep -nE 'Date\.now\(|new Date\(\)' web/lib/{live-poll,refresh-strip,chart-freshness}.ts web/components/screener/{FreshnessStrip,LiveProvider}.tsx web/components/chart/ChartFreshness.tsx
```

### Failing stubs

Each test in a slice's Tests list starts as a stub (`raise NotImplementedError("NOT IMPLEMENTED - TDD stub: <behaviour>")`; vitest and Playwright: `throw new Error(...)`) and follows convention 5. Tests added to existing files are stubbed inside them; changed goldens are written as the new text.

### Red-today evidence (origin/main 1e7d337; read-only checks run 10-10-26, nothing committed)

AC-S11a-1,3: `grep -w UTC` finds the word in `chart-freshness.ts`, `spaghetti-lines.ts`, `btc-leg-lines.ts`, `CoinPanel.tsx`, `ChartFreshness.tsx`, `MiniChart.tsx`, `simple-lines.svelte`, `island-loader.ts`; `CoinPanel.chipTitle` builds `candle from ${chip.open_ts}` from the raw payload string. AC-S11a-4: `STATUS_KEYS` lists 10 keys and the test asserts equality. AC-S11b-1: `grep -rn "refresh/status" web` is empty; `ScreenerBoard` has no timer. AC-S11b-2: `simple-lines.svelte` resets `range` whenever `series` changes. Scratch runs (Node 22.22.0, ICU 77.1, system zone UTC): offsets 60/120 at the 2026-03-29T01:00:00Z change and 120/60 at 2026-10-25T01:00:00Z; Brussels midnights and day lengths as in C3; the last Sundays of March and October 2026 are the 29th and the 25th; `en-US` short zone name `GMT+2`, `en-GB` `CEST`; `format(new Date("x"))` throws `RangeError`; `h23` and `hour12: false` both print `00:00` at midnight. Baselines 10-10-26 as in the header (pytest 187.7 s, vitest 13.9 s, build:islands 7.6 s, e2e 2.6 min); Playwright 1.63.0 has `page.clock`.

### Unverified facts: owner and deterministic fallback

| # | Fact | Status | Owner | Fallback |
|---|---|---|---|---|
| U1 | `mount` with a props object of getters over a `$state.raw` value updates the island in place | proven on a scratch Svelte 5.57.1 component (same node updated, zoom kept, reset on key or timeframe change); the real LayerChart island is not unit-tested | S11b e2e test 3 | the second approach in P4, then `needs_input` |
| U2 | `page.clock.install()` and `runFor` drive the 60 s poll under the Next dev server without breaking its own timers | not run | S11b e2e tests 2-4 | test 2 only: wait a real 61 s with `test.setTimeout(150_000)`; tests 3-4 trigger a check with the `document.visibilityState` override and `visibilitychange` (S11b e2e description) |
| U3 | changing `process.env.TZ` inside a vitest worker changes `Date` local getters (pool `forks`) | proven in a scratch vitest 2.1.9 run (restore `TZ` in a `finally`) | S11a `brussels-time.test.ts` 6 | assert the module source has none of `getHours`, `getDate`, `getDay`, `getMonth`, `getFullYear`, `toLocale` |
| U4 | Chromium's `Europe/Brussels` data agrees with Node's | not run | S11a e2e test 1 (arithmetic oracle) | a difference fails the test and is reported |
| U5 | `performance.now()` keeps advancing across sleep and a hidden tab | not measurable offline | P-S11-4 | the immediate check on resume re-syncs |
| U6 | request rate with a page open (hook-queued refreshes) | not measurable offline | P-S11-5 | `POLL_INTERVAL_MS`; backlog `screener-passive-polls_NOTE` |
| U7 | whole-suite e2e count | 65 in 6 files at `1e7d337` | S11a worker | re-record at spawn; a differing baseline stops the worker |

### Not verifiable offline

The user's real display and Windows zone; the live 15-minute cycle; DST in real life (25 Oct 2026); a real hidden tab and system sleep; the exchange request rate; GitHub CI; every new test.

### What this coverage does NOT prove

- The island is never mounted under jsdom: axis labels in the browser, the in-place update and zoom survival are proven only by the seeded e2e (hybrid) and the probes; the labels come from the unit-tested function.
- The e2e fakes the browser clock and edits the server answers; it proves the page reacts to a changed answer, not that the real worker produces one every 15 minutes (P-S11-3).
- Data refreshed by a page-triggered drain between ticks reaches the spaghetti and BTC charts only at the next tick; board and drill-down pick it up within a minute.
- The overdue and failed variants of the strip are not contrast-audited (AC-S11b-8r). Neither CI nor the gates run `next build`; the provider is a client component imported by a server page (an offline `pnpm exec next build`, if it runs, is a report line only).
- The Svelte update path was proven on a scratch component, not on the real LayerChart island.
- Ages freeze while the tab is hidden and are re-synced by the immediate check on resume; a sleep longer than the monotonic clock covers is a probe item (U5).

### Probes (user PC; the planner walks the user through these; copy-paste checklist)

P-S11-1 (after S11a: pull, run `deploy/build-web.ps1`, restart both tasks, open the screener, press Ctrl+F5):
1. Press `15m`; under a coin chart read `Last bar YYYY-MM-DD HH:MM CEST (or CET), opened N min ago (forming)`. The HH:MM is within the last 15 minutes of the Windows clock. Press `1d`: it reads 02:00 CEST (01:00 CET), which is midnight UTC and expected.
2. On the chart axis expect hours such as 14:00, 16:00 and day labels such as `10 Oct` that switch at Brussels midnight.
3. Hover a gain chip: `1d candle from ... CEST (forming)`.
4. Press Ctrl+F and search `UTC`: nothing on the page.
5. Set the Windows time zone to Pacific, reload: every time on the page stays the same. Set it back.

P-S11-2 (Sunday 25 Oct 2026, after 03:00 CEST turns into 02:00 CET; reload): captions read `CET`, times moved by one hour, no one-hour axis shows `02:00` twice.

P-S11-3 (after S11b, same pull and restart): zoom one coin chart with Ctrl and wheel, open a drill-down, then do not touch the page for one full cycle (about 15 minutes plus the refresh itself; never press F5). `Page checked` moves every minute; when the time in `Next refresh` passes, `Server refreshed` moves and the last-bar lines change. Zoom and the drill-down are still there.
P-S11-4: switch to another tab for 5 minutes and come back: `Page checked` shows the current time within a second or two. Optionally let the PC sleep 10 minutes and wake it.
P-S11-5: stop the API task for 3 minutes: the strip says `Could not check the server`, the boxes keep their data; start it: the strip recovers within 5 minutes, or at once when you switch away from the tab and back. With the page open for 10 minutes read the API log: pair refreshes should come every few minutes, not every minute; tell the planner if it looks like more.

### Open gaps

Q1 (budget) is RESOLVED 10-10-26 (ceiling 75 USD); no budget gap remains. AC-S11b-8r (backlog stub written by S11b) is a named residual. known-gap: AC-S11a-1r, AC-S11a-2r, AC-S11b-9r are probes P-S11-1 to P-S11-5 on the user PC.

## Test Infra Improvement Notes

(none identified yet) Candidates: a CI job for the seeded Playwright specs (S11 is the fourth UI slice that needs a local e2e run CI cannot confirm); a Svelte component test runner so island behaviour (axis labels, update in place) is not only an e2e matter (a scratch config ran in 1.4 s); a TZ matrix for the vitest run (`TZ=UTC`, `Asia/Tokyo`) against local-zone formatting.

## Resume and Execution Handoff

1. Selected plan file: `process/general-plans/active/screener-batch4_10-10-26/screener-batch4_PLAN_10-10-26.md`
2. Last completed step: PLAN drafted 10-10-26 against origin/main `1e7d337`; PVL cycle 1 returned CONDITIONAL and supplement cycle 1 folded F1-F7 and advisories a-j (results.tsv row 2); PVL cycle 2 is next.
3. Validate-contract status: pending (skeleton above, Status PENDING, Gate PENDING); no PASS stamp and no goal block.
4. Context loaded: CLAUDE.md, all-context.md, all-tests.md, the batch 1 to 3 plans and PVL reports, the S5b plan, and the real code and tests named in the owned lists.
5. Next step for a fresh agent: Q1 is resolved (ceiling 75 USD); run VALIDATE (PVL cycle 2) on this file until the PASS stamp, wait for the user's explicit "ENTER EXECUTE MODE", then the planner registers S11a and S11b in MASTER-PLAN, writes the S11a envelope (master-planner.md section 8, at most 8,000 bytes, a pointer list citing the sub-range table) and spawns S11a only; S11b's envelope follows the S11a merge SHA; after S11b the planner re-validates the S5b plan with "Hand-over to S5b".

## Envelope line ranges (re-derive with `grep -n '^## \|^### '` at spawn time; worker cap 36,000 B = CLAUDE.md 13,443 counted once + envelope (cap 8,000) + plan bytes)

Line numbers refer to this file as saved. This table is the last block, so editing it moves no earlier line; if any earlier line is edited, re-derive the numbers with the grep named in the heading and recount the bytes (each line plus its newline). Each set holds: the decision lines the slice needs, Gate conventions 1-11 (convention 2 is three lines: the shared rule, the S11a baselines, the S11b start; each slice skips the other's line), the slice Goal, Owned and Forbidden lines, its design or rules, its existing-tests and tests lines, its exact gates without the PC probe, the command-block lines it uses (the fence lines 276 and 322 included) and Failing stubs. A worker never needs: Name check, budget, Lane, Risks and Rollback lines, Touchpoints, the criteria rows (PVL and the tester use them), probes, Red-today, Hand-over, Resolved questions. S11a reads C1-C5; S11b reads none of them (its rules restate what it needs) and its envelope names `web/lib/brussels-time.ts` and `web/lib/types/refresh.ts` as extra code reads (code files do not count against the plan-byte cap).

| Slice | Plan ranges (lines) | Plan bytes | Envelope room (cap 36,000) | Slack (room - 2,100) |
|---|---|---|---|---|
| S11a | 41-45, 49-51, 53-61, 81, 83-84, 86-90, 92, 94-105, 107-112, 257-271, 293-295, 297-298, 300-301, 303-304, 306-307, 309-310, 326, 330 | 17,924 | 4,633 | 2,533 |
| S11b | 49-50, 52-61, 123, 125-126, 128-136, 138, 140-148, 276-288, 293-295, 297-298, 300-301, 312-313, 315-316, 318-319, 321-322, 324-326, 330 | 20,435 | 2,122 | 22 |

Computed as 36,000 - 13,443 (CLAUDE.md) - plan bytes. Slack is measured against 2,100 B, the estimate of a filled envelope (the template alone is 864 B; with the 11 report headings inline and the owned, forbidden and gate pointers, 1,900-2,300 B is realistic). S11b has only 22 B of slack: any later edit inside an S11b range must be byte-neutral (trim wording, or move prose outside the ranges), and an envelope that would not fit is trimmed, never the ranges. Naming operating-instructions.md (6,678 B) lifts the cap to 43,000 and adds about 320 B of room. The union of both sets is 34,940 B over 120 lines: not readable by one worker, which is why S11 is two slices.
