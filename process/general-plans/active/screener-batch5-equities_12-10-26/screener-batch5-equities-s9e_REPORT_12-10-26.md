# S9E Worker Report: market-hours refresh tick and equities freshness strip

## 1. Task ID

T50, batch 5, slice S9E. Branch `claude/t50-s9e-equities-refresh` from origin/main `2223e95`.

## 2. Outcome

CODE DONE, gates PASS (G-S9E-1..6, seeded e2e run on the head code SHA `661fe50`). AC-S9E-1 stays CONDITIONAL on the two estimated constants (`REFRESH_DELAY_MINUTES` 30, `BAR_DUE_AFTER_MINUTES` 60), as the envelope directs. Status: review (awaits P-S9-2 on the PC). Not merged.

## 3. Summary

- `api/data/equities_refresh.py`: new `EquitiesRefreshWorker` (daemon thread; injectable clock, wake Event, fetch, tickers, per-ticker bar date). `schedule_first` sets a catch-up tick 20 s after start only when a ticker's newest bar is behind `last_due_session(now)` (no bar counts as behind); otherwise it sleeps to `equities_calendar.next_refresh_at(now)`. `run_tick` advances `next_tick_at` as the tick starts, runs `refresh_all` (reuses `PASS_LOCK`, per-ticker isolation), then retries every 30 min up to 3 times while a ticker is behind the session the tick is for (`tick_session`, not `last_due_session(now)`, per F3), else schedules the next close. An all-failed tick doubles the wait (from 1800 s, cap 3600 s); any success resets it. A woken pass (`request_now`) leaves the schedule alone. `next_tick_at` is stored, never recomputed per status call. Registry: `start_from_env` (off with `SCREENER_REFRESH_WORKER=0`, reason `SCREENER_REFRESH_WORKER=0`; off without `LSE_API_KEY`, reason `missing-key`), `stop_worker`, `current_worker`, `request_now`. `status()` keeps the S9A form when no worker runs (existing S9A tests unedited and green) and reports the live values plus `last_bar_date` when it runs. Logs carry a ticker and an exception class name only.
- `api/routers/equities.py`: `POST /refresh` calls `equities_refresh.request_now()` (wakes the running worker, else the S9A background pass). Add-triggered refresh unchanged.
- `api/main.py`: lifespan starts the equities worker after the crypto one and stops it after the crypto one (nested try/finally so one failure never skips the other).
- `web/lib/types/equities.ts`: `EquitiesStatus extends RefreshStatus` with `last_bar_date`.
- `web/lib/equities-strip.ts`: `equitiesStripModel(status, nowMs)` reuses `stripModel` (so `isOverdue` and the 300 s grace are the crypto rule) and `stripTime`; adds "Latest daily bar YYYY-MM-DD" (or "No daily bars cached yet"), "Next expected refresh Mon 12 Oct 22:30 CEST" (weekday + date + Brussels time from the server instant), plain off wording ("no market data key is set on the server" for `missing-key`), ticker wording for failed counts, and an equities help text (no 15-minute proof). No browser clock read.
- `web/components/screener/FreshnessStrip.tsx`: optional `model` prop (default `stripModel`), renders `strip-last-bar` when the model provides `lastBar`. Crypto output unchanged (S11 strip tests unedited, green).
- `web/components/equities/EquitiesScreener.tsx`: `<FreshnessStrip model={equitiesStripModel} />`.

## 4. Files

Edited (5): `api/data/equities_refresh.py`, `api/routers/equities.py`, `api/main.py`, `web/components/screener/FreshnessStrip.tsx`, `web/components/equities/EquitiesScreener.tsx`.
New (7): `web/lib/equities-strip.ts`, `web/lib/types/equities.ts`, `api/tests/data/test_equities_refresh_worker.py` (14), `api/tests/routers/test_equities_status_router.py` (3), `web/lib/__tests__/equities-strip.test.ts` (14), `web/components/screener/__tests__/FreshnessStripModel.test.tsx` (4), `web/e2e/equities-live.spec.ts` (2).
Plus this report. No existing test file edited. No forbidden file touched (`refresh_worker.py`, `refresh-strip.ts`, `types/refresh.ts`, `live-poll.ts`, `lse_adapter.py` unchanged; `refresh_worker.enabled_from_env` is imported read-only).

## 5. Commits

- `661fe50` feat(equities): market-hours refresh worker and equities freshness strip (T50 / S9E)
- (this report, next commit)

## 6. Tests run (SHA, UTC)

| Gate | SHA | UTC | Result |
|---|---|---|---|
| Red run (stubs, untouched base): G-S9E-1 | 2223e95 + stubs | 2026-10-12T10:28:42Z | 17 failed, 16 passed (the 17 new stubs red, calendar 16 green) |
| Red run: new vitest files | 2223e95 + stubs | 2026-10-12T10:28:52Z | 18 failed in 2 files |
| G-S9E-1 worker, status router, calendar | working tree on 2223e95 (= 661fe50 content) | 2026-10-12T10:32:49Z | 33 passed |
| G-S9E-2 crypto worker, router, startup, CORS (unedited) | same | 2026-10-12T10:32:49Z | 33 passed |
| G-S9E-3 vitest strip, model, S11 strip, refresh-strip, live-poll | same | 2026-10-12T10:32:49Z | 48 passed in 5 files |
| G-S9E-4 full pytest | same | 2026-10-12T10:33:03Z | 1127 passed, 1 skipped, 5 deselected |
| G-S9E-4 full vitest | same | 2026-10-12T10:33Z | 476 passed in 59 files |
| G-S9E-4 tsc, build:islands | same | 2026-10-12T10:35Z | exit 0, exit 0 |
| G-S9E-5 e2e equities-live + live-refresh + equities | 661fe50 | 2026-10-12T10:36:15Z | 16 passed (2 + 4 + 10) |
| G-S9E-5 e2e full (`--list` 92 in 11) | 661fe50 | 2026-10-12T10:37:27Z | 92 passed |
| G-S9E-6 REAL-DATA, S-secret, diff --check, FORBIDDEN, FIXTURES, S9E-scope, S9-words, S9-utc, S9-nostore, S9-clock | 661fe50 | 2026-10-12T10:41Z | all print nothing; diff --check exit 0 |

Counts against the envelope arithmetic: pytest 1127/1/5 (+17), vitest 476 in 59 (+18), e2e 92 in 11 (+2): all match. Baseline pytest was not re-run separately on the base; 1127 - 17 = 1110 passed / 1 skipped / 5 deselected agrees with the envelope's recount (the plan's 1105/2/5 predates the S9F adapter fix). The plan's G-S9E-4 text (1122/2/5) is superseded by the envelope's 1127/1/5.

## 7. Tests NOT run

None of the gates. Probes P-S9-2 and P-S9-3 are the user's and are not claimed. No live LSE call was made (all fetches injected).

## 8. Deviations

- Probe record P-S9-1 (filled from the envelope's user record, 2026-10-12; plan file not edited): base URL `https://api.londonstrategicedge.com/vault/candles`; auth header `x-api-key` (not Bearer); response a bare JSON list; bar date from `ts` "YYYY-MM-DD 00:00:00.000000" (date at 00:00, no tz); today's bar present during the session as a forming bar; final-bar time after the close NOT measured, so `REFRESH_DELAY_MINUTES` 30 and `BAR_DUE_AFTER_MINUTES` 60 stay estimates (AC-S9E-1 CONDITIONAL on them); `1w` not probed, no impact. The adapter already matches (S9F).
- Backoff interpretation: the doubling starts from the 30 min retry wait, so an all-failed tick waits 3600 s (the cap) before its next retry; retries still stop after 3, then the next close. Tested.
- Status precedence when no worker runs: an explicit off reason from the lifespan (`SCREENER_REFRESH_WORKER=0`, `start-failed`) wins; otherwise no key reads `missing-key`, else `not-started` (keeps the S9A status tests unedited). `stop_worker` resets the reason to `not-started`.
- A woken pass during a scheduled wait refreshes all tickers but does not move `next_tick_at` (the plan says `request_now` wakes it; schedule stability is what keeps the overdue rule honest).
- e2e test 1 reads the API's `disabled_reason` and accepts either `SCREENER_REFRESH_WORKER=0` or `missing-key` wording (the run showed the env reason), so it does not depend on how Playwright merges the server env.

## 9. Blockers

None. No needs_input.

## 10. Follow-up

- When the user measures when the final daily bar appears after the close, adjust `REFRESH_DELAY_MINUTES` / `BAR_DUE_AFTER_MINUTES` in `api/data/equities_calendar.py` (tests name both).
- A5 holds: the worker starts only when `LSE_API_KEY` is set at API start.
- Early closes (A7) remain a residual.

## 11. Context cost

Read: CLAUDE.md, the envelope, plan lines 11, 30-80, 133-142, 242-269, plus targeted greps of the plan's Acceptance Criteria rows (AC-S9E) and Validate Contract advisories A1-A11. Source read: the Owned files, `refresh_worker.py`, `refresh-strip.ts`, `types/refresh.ts`, `live-poll.ts` head, `brussels-time.ts`, `lib/api/equities.ts`, `lib/api/refresh.ts`, existing equities/refresh tests and e2e specs for patterns, `playwright.config.ts` env. No subagents spawned. operating-instructions.md not opened. Spend is measured by the planner.
