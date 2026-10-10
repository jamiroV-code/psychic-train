# S11a worker report: Brussels time on /screener (10-10-26)

## 1 Task ID

T42, batch 4, slice S11a. Branch `claude/t42-s11a-brussels-time`, from `origin/main` at `848b206`.

## 2 Outcome

needs_input, on one point only: the full pytest count is 1016, not the 999 in the envelope. The base moved after `1e7d337`: PR #45 added `api/tests/deploy/test_deploy_r12_guards_shape.py`, which has 17 tests. I re-recorded the baseline at spawn (convention 2) as 1013, and this slice adds +3 as the plan says, so the result is 1016. Every other gate count matches the plan exactly. The planner should confirm that the re-recorded baseline is acceptable before merging. P-S11-1 (real PC labels) is the user's probe and is not claimed here.

## 3 Summary

- `web/lib/brussels-time.ts` is the only file that names `Europe/Brussels`. It uses one module-level `Intl.DateTimeFormat("en-US", { timeZone, hourCycle: "h23" })` read through `formatToParts`. The offset is the wall clock minus the instant. CET and CEST come from the offset (60 / 120), and any other offset prints as `+HH:MM`. An invalid date prints `n/a`. All the exports listed in C2 exist with the fixed names.
- `chart-time-format.ts` exports `brusselsTicks`, `formatBrusselsTicks` and `brusselsAxis`, replacing the `utc*` names. `FIXED_STEPS`, `MONTH_STEPS` and `YEAR_SPAN_MS` are kept.
  - Sub-day ticks sit on the 15-minute grid at Brussels wall times that are a multiple of the step. In the repeated hour of 25 Oct, only the first pass gets ticks.
  - Day, week and month ticks sit on `midnightOf` (Brussels midnight).
  - 7- and 14-day steps are anchored to Mondays counted from 1970-01-05. The 2-day step uses Brussels days with an even number since 1970-01-01.
  - Imports are relative only, so the island build works.
- Captions, the 1d chip tooltip (`CoinPanel.chipTitle`), the spaghetti span and the BTC leg span follow the C4 text forms. An intraday span prints one abbreviation, or one on each end when the span crosses a clock change.
- `refresh_worker.status()` gains `server_time`, edited only inside `status()`. It reads the worker clock, or `ccxt_adapter._now` when no worker is registered, and is `None` if the clock raises. `web/lib/types/refresh.ts` declares `RefreshStatus` with 11 keys.
- `simple-lines.svelte`: only the import was renamed and one comment changed. `island-loader.ts`: one comment changed.

## 4 Files changed

All files are inside Owned; the S11a-scope check prints nothing.

- **API:** `api/data/refresh_worker.py`, `api/tests/routers/test_refresh_router.py`
- **Web, new:** `web/lib/brussels-time.ts`, `web/lib/types/refresh.ts`, `web/lib/__tests__/brussels-time.test.ts`, `web/e2e/brussels-time.spec.ts`
- **Web, edited:** `web/lib/{chart-time-format,chart-freshness,spaghetti-lines,btc-leg-lines,island-loader}.ts`, `web/components/screener/CoinPanel.tsx`, `web/components/chart/ChartFreshness.tsx`, `web/islands/simple-lines.svelte`
- **Tests:** `web/lib/__tests__/chart-time-format.test.ts` (rewritten, 12 tests); `web/lib/__tests__/{chart-freshness,spaghetti-lines,btc-leg-lines}.test.ts`; `web/components/chart/__tests__/ChartFreshness.test.tsx`; `web/components/screener/__tests__/{ScreenerBoard,DrillDownView,SpaghettiChart,BtcLegChart}.test.tsx`; `web/e2e/screener.spec.ts` (line 252 only)
- **Report:** this file

## 5 Commits

- `f2610f9` T42 S11a: Brussels time on /screener, status server_time
- the report commit that follows it

## 6 Tests run (gate, SHA, UTC)

**Baselines at spawn** (`848b206`, 11:37Z):
- pytest: 1013 passed, 2 skipped, 5 deselected. The +17 comes from the deploy test explained in heading 2; that file alone gives 17 passed.
- vitest: 251 in 34 files.
- e2e list: 65 in 6 files (10 + 7 + 17 + 16 + 9 + 6).

**Red run on stubs (G-S11a-13).** Run on the base `848b206` plus the stubs and the new goldens, before any source edit, 11:41Z:
- G-S11a-1: 6 tests. 4 failed (3 stubs and the `STATUS_KEYS` shape test), 2 passed.
- G-S11a-3: 73 tests in 10 files. 37 failed (27 stubs and 10 changed goldens), 36 passed.
- Full `pnpm test`: 268 tests in 35 files, 37 failed.
- Test 6 in `brussels-time.test.ts`: I ran a scratch `getHours` formatter (not committed) under the zones UTC, America/Los_Angeles and Asia/Tokyo. It printed the wrong wall time in all three (for example `2026-10-03 22:30`, `15:30` and `2026-10-04 07:30` where the answer is `2026-10-04 00:30`), so the zone-independence test does catch a browser-zone leak.

**Green run** (code SHA `f2610f9`; the code was unchanged between the first runs and that commit):

| Gate | Result | UTC |
|---|---|---|
| G-S11a-1 | 6 passed | 11:46Z |
| G-S11a-2 | 1016 passed, 2 skipped, 5 deselected, 0 xfailed (baseline 1013 + 3; see heading 2) | 11:48Z |
| G-S11a-3 | 73 passed in 10 files | 11:46Z |
| G-S11a-4 | 268 passed in 35 files | 11:48Z |
| G-S11a-5 | tsc exit 0 | 11:48Z |
| G-S11a-6 | build:islands exit 0 | 11:48Z |
| G-S11a-7 | `git diff --check` exit 0 | 11:48Z |
| G-S11a-8 | S11a-scope, FORBIDDEN and S-secret-scan print nothing (run after the commit) | 11:49Z |
| G-S11a-9 | FIXTURES prints nothing | 11:49Z |
| G-S11a-10 | S11a-utc and S11a-words print nothing | 11:49Z |
| G-S11a-11 | seeded e2e `screener.spec.ts contrast.spec.ts brussels-time.spec.ts`: 20 passed | 11:49-11:50Z |
| G-S11a-12 | seeded e2e, full suite: 68 passed (`--list`: 68 in 7 files) | 11:50-11:52Z |

**Goldens re-derived by arithmetic (convention 10).** The EU rule gives 2026 summer time from 29 Mar 01:00Z to 25 Oct 01:00Z. I checked every golden against that rule, and none came from program output. For example: `14:15Z` on 3 Oct is 16:15 CEST; 2020-01-01 00:00Z is 01:00 CET; `midnightOf` gives 28/29/30 Mar as 23:00Z, 23:00Z, 22:00Z of the day before, and 24/25/26 Oct as 22:00Z, 22:00Z, 23:00Z; 5 Oct 2026 is a Monday (2026-10-04T22:00Z).

**Gate-trap checks** (convention 11): the new and changed lines contain no `role="group"`, no browser storage, no headings, and none of the banned UI words. `brussels-time.ts` and `chart-time-format.ts` have no `@/` imports. The verdict-token scan is part of the passing full pytest run.

## 7 Tests NOT run

- The P-S11-* probes (a real display and real PC labels). They belong to the user.
- CI. It does not run Playwright, so the seeded e2e above is the only Playwright evidence.

## 8 Deviations

- The pytest baseline was 1013, not 996, because the base moved (see heading 2). The arithmetic (+3) holds.
- `chart-time-format.ts` now imports `./types/screener` relatively instead of `@/lib/types/screener` (a type-only import). This follows convention 11 for files the island imports.
- `brussels-time.test.ts` was written with the file tool, not a shell heredoc, because the repo privacy hook misread `process.env.TZ` as a `.env` path. There is no effect on content.

## 9 Blockers

None. The only open item is the pytest-count acknowledgement in heading 2.

## 10 Follow-up

- S11b: the poller and freshness strip can consume `RefreshStatus.server_time`.
- `MiniChart.tsx` still has a comment saying "UTC" for the axis. That file belongs to S11b, as the plan says.
- `components/regime/DrillDown.tsx` shows a "Last fetched (UTC)" label. It is on a different page and outside S11a scope.

## 11 Context cost

- **Files opened:** CLAUDE.md (in context), the envelope, and the plan line ranges the envelope names. No other protocol or context docs.
- **Subagents:** none spawned (0 of 3).
- **Tool calls:** about 45.
