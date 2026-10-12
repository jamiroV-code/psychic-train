# S9A worker report (T45)

## 1. Task ID

T45, batch 5, slice S9A: equities API (cache-only board, chart, spaghetti, list/add/remove with the 30 cap, status, US market calendar, minimal refresh). Branch `claude/t45-s9a-equities-api` from main `881a2fd`.

## 2. Outcome

PASS. G-S9A-1..5 green; counts match the plan arithmetic exactly (pytest 1080 passed / 2 skipped / 5 deselected).

## 3. Summary

- `equities_store`: `MAX_TICKERS = 30`, exact `CAP_MESSAGE`, `TickerLimitError`; a new ticker at 30 or more is refused, an existing one re-adds, an over-cap file is kept; add and remove hold one module lock (35 concurrent adds store exactly 30).
- `lse_adapter`: two functions were added and no existing line changed (the diff has no `-` lines). `read_cached_equity` is cache-only: it never touches the network or the key, and returns the result plus the sidecar `fetched_at`. `refresh_equity` is `fetch_equity_ohlcv` without the 6 h fresh-cache branch, writes both 1d and 1w, and never raises.
- `equities_calendar` (pure): hand-rolled US Eastern daylight rule (2nd Sunday March to 1st Sunday November). Functions: `session_close_utc`, `last_due_session`, `bar_is_stale`, `bar_is_partial` (1d and 1w), `next_refresh_at`. All calendar cases listed in the plan are tested.
- `equities_board`: board, chart view and spaghetti reuse the crypto models with no model change. Chips exist for 1d and 1w only; the 1w chip opens at the week's first session (the Labor Day week gives a number). `stale` and `is_partial` come from the calendar. Failure reasons map onto the closed `UnavailableReason`. Skew fields are null/False. Spaghetti windows are 200 and 28 bars with `references=[]`, in store order.
- `equities_refresh`: `refresh_ticker`, `refresh_all` (sequential, isolated per ticker, `PASS_LOCK` for S9E to reuse), `request_refresh_now` (background thread plus a pending flag, so a request during a pass gets exactly one more pass), `status` (S9A form), and `wait_until_idle`.
- `routers/equities` under `/api/equities`: list/add (422 invalid, 409 cap, a new ticker triggers one background refresh, best-effort layout upkeep)/delete (404); board, spaghetti and chart take `timeframe` 1d or 1w only, anything else 422; `GET /status`; `POST /refresh` (202). No `ccxt_adapter` import. `api/main.py` gains one import and one `include_router`.

## 4. Files

14 files: 10 new, 4 edited.

New: `api/data/equities_calendar.py`, `api/data/equities_refresh.py`, `api/analytics/equities_board.py`, `api/routers/equities.py`, `api/tests/equities_fixtures.py`, `api/tests/data/test_equities_calendar.py` (16), `api/tests/data/test_lse_cached_read.py` (6), `api/tests/data/test_equities_refresh.py` (8), `api/tests/analytics/test_equities_board.py` (14), `api/tests/routers/test_equities_router.py` (18).

Edited: `api/main.py`, `api/data/equities_store.py`, `api/data/lse_adapter.py` (additions only), `api/tests/data/test_equities_store.py` (`test_more_than_thirty_accepted` replaced by `test_thirty_first_refused`, plus 2 tests: +2 net).

Plus this report.

## 5. Commits

- `7c782d7` feat(equities): S9A equities API, cache-only board, US market calendar, minimal refresh
- the report commit, which follows it

## 6. Tests run (SHA, UTC)

- G-S9A-0 red: base `881a2fd` plus stubs in a scratch worktree (2026-10-12T06:55:34Z), run on the five new files plus the store file. Result: 65 failed (62 stubs + 3 changed store tests that assert a refusal), 12 passed.
- G-S9A-2 first run (pre-commit): 1 failure in my own test data. 120 daily bars give fewer than 60 weekly bars, so the 1w partial assertion saw an unavailable chart. I raised the seed to 400 bars; the rerun passed 32 (fix cycle 1 of 2).
- G-S9A-1 `7c782d7` 2026-10-12T06:56:27Z: 45 passed.
- G-S9A-2 `7c782d7` 2026-10-12T06:56:28Z: 32 passed.
- G-S9A-4 `7c782d7` 2026-10-12T06:56:33Z: `test_main_cors.py` and `test_lse_adapter.py` gave 25 passed, 1 skipped. The skip already exists on main: `test_lse_adapter.py:185` waits for the probe fixture (P-S3-1, the user's). Both files are unedited.
- G-S9A-3 `7c782d7` 2026-10-12T06:56:37Z: full run gave 1080 passed, 2 skipped, 5 deselected. This matches the plan (1016 + 64).
- G-S9A-5 `7c782d7` 2026-10-12T06:59Z, after the commit: REAL-DATA (find after `touch /tmp/s9-stamp`), `S-secret`, `FORBIDDEN`, `FIXTURES`, `S9A-scope` and `S9-words` each printed nothing; `git diff --check origin/main...HEAD` exited 0.

## 7. Tests NOT run

- vitest, tsc, build:islands and e2e: web is untouched in S9A, so they are not required.
- The live LSE probe P-S9-1 is the user's and is not claimed here.

## 8. Deviations

- `read_cached_equity` reports reason `fresh-cache` for any served cache that is not stale. The closed `Reason` literal has no cache-read value, and changing it would edit an existing line. The real fetch time is returned alongside as `fetched_at`.
- `lse_adapter` gained one added import line (`from api.data.freshness import as_utc`, placed beside the new functions) so the added lines avoid the uppercase tz literal. It is an addition; no existing line changed.
- `equities_refresh.status()` reports `last_tick_ok` and `last_tick_failed` as null ("ticks null"), where the crypto status uses integers.
- `equities_refresh.wait_until_idle()` was added so tests can wait for the background pass before teardown. Otherwise a pass could outlive the test and read the real store path or a real key.
- The router also maps `InvalidTickerError` on DELETE to 404 (a path that cannot be stored).

## 9. Blockers

None.

## 10. Follow-up

- S9B adds the `equities` layout section. Until then, `place_coin` and `drop_coin` for equities raise, and the router logs the failure and carries on (tested).
- S9E reuses `equities_refresh.PASS_LOCK` and fills the tick fields of `status()`.
- Residual AC-S9-r2: early closes and special closures are not modelled.

## 11. Context cost

Read: CLAUDE.md, the envelope, and the plan ranges named in the envelope. Code read on demand: the existing equities store, lse_adapter, screener board, models, watchlist store and router, the refresh worker status, freshness, gain and the layout functions. No other process docs were opened. Subagents: none.
