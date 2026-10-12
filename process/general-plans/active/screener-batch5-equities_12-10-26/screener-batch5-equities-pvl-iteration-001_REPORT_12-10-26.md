---
domain: plan
iteration: 1
date: 2026-10-12
plan: screener-batch5-equities_PLAN_12-10-26.md
mode: VALIDATE first pass (PVL cycle 1)
gaps_found: 12
fail_count: 0
concern_count: 12
applied: 0
loop_status: validated_conditional
---

# PVL iteration 001 - screener-batch5-equities (first pass; results.tsv row 1)

Code under test: main `881a2fd` (branch `claude/pensive-albattani-ou0cgv`; `api/` and `web/` identical to main). Plan as read: 271 lines, 45,560 B, `validate-plan-artifact.mjs` 0 failures 0 warnings. One sequential validator ran Layer 1 and Layer 2 inline (read-only; scratch scripts in the session scratchpad; no repo file touched).

## Verdict: CONDITIONAL (0 FAIL, 12 CONCERN)

| Layer 1 dimension | Status | Why |
|---|---|---|
| Infra fit | CONCERN | cites match the code, but `fetch_equity_ohlcv` returns the cache for 6 h (F1) and the weekly rules reuse a crypto-only branch (F2) |
| Test coverage | CONCERN | counts correct; scan commands named in the gates did not exist (F6); lifespan wiring untested (F9) |
| Breaking changes | CONCERN | `screener-api.test.ts` reads `screener.ts` source (F7); otherwise additive |
| Security surface | PASS | key from env only, closed reasons; tests could reach a real key and the network (folded under F6/F8) |

## What was verified against the real code (all matched unless a finding says otherwise)

- Baselines re-run: pytest collect 1018 of 1023 (5 deselected), vitest 400 in 50 files (run), `playwright test --list` 79 in 9 files.
- Cites: `main.py:91-98`, `lse_adapter.py:320-363`, `layout.py:35-38,168,251,305`, `test_equities_store.py:50`, `test_layout.py:177`, `test_layout_store.py:168-176`, `test_refresh_router.py:162-166`, `ScreenerBoard.tsx:36-49,386`, `CoinPanel.tsx:104`, `DrillDownView.tsx:68`, `AddCoinForm.tsx:104`, `lib/api/layout.ts:8`, `lib/api/screener.ts:10`, `LiveProvider` `fetchStatus`, `contrast.spec.ts` 7 routes, existing counts (LinkedZoom 3, Live 12, live-poll 12, refresh-strip 10, FreshnessStrip 8, BoardLayout 15, layout store 15 / layout router 10 / cap 11 / watchlist 5 / board integration 5; e2e 10+7+4+3).
- No other test asserts SECTIONS, 45 tickers, a router list or nav links (`grep`): only `test_layout.py:177`, `test_equities_store.py:50`, and `test_onchain_activity_router.py` (route set, unaffected by new routes).
- Calendar: zoneinfo agrees with the hand-rolled EDT rule (2nd Sunday March to 1st Sunday November, close 16:00 local) for every day 2020-2035 (0 mismatches); 2026: Labor Day 09-07, Thanksgiving 11-26, Good Friday 04-03 are non-sessions in `nyse_holidays`; closes 20:00Z Fri 10-09/10-30, 21:00Z Mon 11-02, 21:00Z Fri 03-06, 20:00Z Mon 03-09; `next_refresh_at` cases right; Black Friday and Christmas Eve 2026 are the early-close residual (13:00 ET).
- Arithmetic per slice recounted: +64 / +20 / +46 / +5,+12,+11 / +17,+18,+2 = +106 pytest, +76 vitest, +13 e2e; ends 1122 / 476 in 59 files / 92 in 11 files; 59 file touches; budget totals.
- Worker bytes: CLAUDE.md 13,443 B; every stated range total reproduced (13,377 / 9,970 / 12,373 / 10,903 / 13,291).

## Findings (all CONCERN; each has a fix in iteration 002)

| # | Finding | Evidence | Fix |
|---|---|---|---|
| F1 | A tick, a manual refresh or a retry within 6 h of the last fetch returns the cache and fetches nothing, so a ticker added at 17:00Z is not updated at the 20:30Z tick, and "Refresh now" cannot fetch the final bar | `lse_adapter.py:336-339` (`_is_fresh` branch) | second adapter function `refresh_equity` (no existing line changes); `refresh_ticker` uses it; AC-S9A-7 |
| F2 | `compute_gain_chip` returns N/A (`insufficient-history`) for 1w when the week's Monday bar is missing; reproduced for the Labor Day week. Weekly `stale`/`is_partial` on the Monday label would read stale all week | `gain.py:_newest_weekly_bucket`; scratch run | chips built in `equities_board`; weekly rules on the daily leg |
| F3 | S9E retry compared against `last_due_session(now)`, which is still the previous session at close + 30 min, so a missing bar never retried; `next_tick_at` recomputed per call would slide and a missed tick could never read overdue | design text vs BAR_DUE 60 / DELAY 30 | retry vs the tick's own session; stored `next_tick_at` |
| F4 | No mapping from adapter failures onto the closed `UnavailableReason` (models are forbidden to change); board and spaghetti timeframes not validated | `models/screener.py` Literal | mapping and `Literal["1d","1w"]` on all three reads |
| F5 | A refresh request during a running pass could be dropped (new ticker never filled); thread and worker share no lock; `add_ticker` has no lock (crypto has `_LOCK`) | `watchlist.py` `_LOCK` | pending flag, shared module lock, store lock + thread test |
| F6 | The gates cite scope/forbidden/words/UTC/nostore/clock commands that do not exist (only an S9A scope that would flag the worker's own report file); scans read `main...` before the commit; tests could reach a real `LSE_API_KEY` and the network (no socket guard outside `api/tests/deploy`) | plan conv 7-10 | section "Scope and scan commands" (13 commands, dry-run), conv 7-10 reworded, `delenv` rule |
| F7 | S9C: `screener-api.test.ts` reads `screener.ts` for `export function fetchChartView`; equities fetchers created per render re-fire the board effect (`fetchBoard` in deps); gain-chip tooltip would show `02:00 CEST`; 1w caption "Latest daily bar" shows a Monday; context needs `"use client"`; G-S9C-2 ("minus the new files") was not a runnable command | `screener-api.test.ts:10`, `ScreenerBoard.tsx:114`, `CoinPanel.tsx:29-35` | S9C design and G-S9C-2 (`--exclude`, proven to select 50 files / 400 tests) |
| F8 | S9D: the equities seed must run after `seed_e2e_cache.py` (it removes the cache root, line 810); the e2e API would use a real key if the shell has one; 300 sessions give only 63 weekly bars (limit 60) | `seed_e2e_cache.py:810`; scratch run | order, empty `LSE_API_KEY`, 420 sessions (88 weekly) |
| F9 | S9E edits `main.py` lifespan but no test runs the lifespan with the equities worker | G-S9E-2 guards crypto only | router test 3 runs through `TestClient(app)` (count-neutral) |
| F10 | "3 changed store tests failed" on the base: two of them (re-add at cap, remove then add) pass on the base | `equities_store.py` has no cap | each changed test asserts a refusal |
| F11 | Budget mids 91.2 / 96.9 are 91.4 / 97.2 (mid 27.75); S5b cost 9.99 against an 8.0 high (+25%); the same overrun on A-D reaches 103.2 | MASTER-PLAN T41 | text fixed; spend gate before D |
| F12 | Worker ranges: S9A 13,377 B would be about 17.0 KB with F1-F6, over the 14,557 B cap; AC rows and lines 12-14 are not worker material | byte script | common = line 11 and 30-66; criteria rows left out (batch 4 precedent); FORBIDDEN reduced to the stop-at-review set |

## Not verifiable offline

The real LSE feed (probes P-S9-1, P-S9-2), a real display and phone, `next build`, CI Playwright, and every new test.

## Cost and strategy

Sequential, one validator, score 3 of 7 (S2, S6, S7). EXECUTE: sequential, one opus worker per slice.
