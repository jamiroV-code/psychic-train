# screener-batch3 S5a worker report (09-10-26)

## 1 Task ID

T40 (batch 3, slice S5a): layout file API, 30-coin cap, symbol validation, RSI numbers, TS mirrors. Branch `claude/t40-s5a-layout-api` from `main` 7ead516 (only process files differ from the plan's 270f9ac).

## 2 Outcome

review. All gates G-S5a-1..12 pass on code SHA a3ffd98. P-S5a-1 stays a user probe (not run, not claimed). No needs_input, no blocker.

## 3 Summary

- `api/data/layout.py` (new): `layout.json` next to the watchlist (or `SCREENER_LAYOUT_PATH`), resolved at call time; atomic write (temp `.layout.json.*.tmp`, fsync, `os.replace`) under one RLock; reconcile on every read and write (coins off the watchlist dropped, unplaced coins to the last group, `main`/`Main` made when no group exists, hidden lines keep BTC, HYPE and members); unreadable, wrong-shape or `version != 1` reads as `recovered` and is moved to `layout.json.bad` (`os.replace`) by the next save, `place_coin` or reset; `place_coin`, `drop_coin`, `reset_layout` (drops only the section, the file only when none remains).
- `api/models/layout.py`, `api/routers/layout.py` (new): `GET/POST/DELETE /api/layout/{section}`; 404 unknown section, 409 `layout changed elsewhere`, 422 for rule breaks and for lists over 64 or symbols over 15 chars.
- `api/data/watchlist.py`: `MAX_COINS`, `CAP_MESSAGE`, `SYMBOL_RE`, `WatchlistFullError`, `InvalidSymbolError`, `normalize_symbol`; `add_coin`/`remove_coin` locked read-modify-write; `_save_raw` untouched.
- `api/routers/watchlist.py`: 409 cap, 422 symbol, optional `group_id`; layout upkeep in try/except with a logged warning; response models unchanged.
- `api/models/screener.py`, `api/analytics/screener_board.py`: `RsiReason`, `RsiReading`, `RsiPoint`, `CoinPanel.rsi`, `ChartSeries.rsi` (filled only by `build_chart_view`); non-finite values become `None`/skipped. `compute_rsi` was confirmed to equal the classic SMA-seeded Wilder loop exactly (70.1148... on a sine series) and returns NaN on a flat series (-> `flat-price`).
- `api/main.py`: router include and the CORS comment; `_cors_options` unchanged.
- TS mirrors `web/lib/types/{screener,layout}.ts`; vitest fixture edits exactly as the plan's table.

## 4 Files changed

`.gitignore` (3 lines), `api/analytics/screener_board.py`, `api/data/layout.py` (new), `api/data/watchlist.py`, `api/main.py`, `api/models/layout.py` (new), `api/models/screener.py`, `api/routers/layout.py` (new), `api/routers/watchlist.py`, `api/tests/data/test_layout_store.py` (new, 15), `api/tests/routers/test_layout.py` (new, 10), `api/tests/routers/test_watchlist_cap.py` (new, 11), `api/tests/routers/test_screener_rsi.py` (new, 9), `api/tests/routers/test_screener_no_verdict_contract.py` (add `"rsi"`), `web/components/screener/__tests__/ScreenerBoard.test.tsx` (`rsi` in `makeCoin`, `rsi: []` in `NO_FRESHNESS` and the two inline literals), `web/components/screener/__tests__/DrillDownView.test.tsx` (`rsi: []` in `NO_FRESHNESS`), `web/lib/types/layout.ts` (new), `web/lib/types/screener.ts`, this report. 19 files, matching the plan's touch count.

## 5 Commits

- a3ffd98 T40 S5a: layout file API, 30-coin cap, symbol validation, RSI numbers, TS mirrors
- (this report) process: T40 S5a worker report

## 6 Tests run (gate, SHA, UTC)

| Gate | SHA | UTC | Result |
|---|---|---|---|
| G-S5a-1 red run (45 stubs on untouched base) | 7ead516 + stubs | 2026-10-09T12:00:39Z | 45 failed |
| G-S5a-1 | a3ffd98 (pre-commit tree) | 2026-10-09T12:05Z | 45 passed |
| G-S5a-2 (inside REAL-DATA) | a3ffd98 | 2026-10-09T12:08:01Z | 996 passed, 2 skipped, 5 deselected, 0 xfailed |
| G-S5a-3 `pnpm test` | a3ffd98 | 2026-10-09T12:08:32Z | 251 passed in 34 files |
| G-S5a-4 tsc | a3ffd98 | 2026-10-09T12:08:32Z | exit 0 |
| G-S5a-5 build:islands | a3ffd98 | 2026-10-09T12:08:32Z | exit 0 |
| G-S5a-6 `git diff --check` | a3ffd98 | 2026-10-09T12:08:32Z | exit 0, no output |
| G-S5a-7 S5a-scope, FORBIDDEN, S-secret-scan | a3ffd98 | 2026-10-09T12:08:32Z | print nothing |
| G-S5a-8 FIXTURES | a3ffd98 | 2026-10-09T12:08:32Z | prints nothing |
| G-S5a-9 S5-ignore | a3ffd98 | 2026-10-09T12:08:32Z | three paths; ls-files nothing |
| G-S5a-10 REAL-DATA + test_main_cors | a3ffd98 | 2026-10-09T12:08:32Z | before/after identical (both empty: no real files on this machine); 10 passed |
| G-S5a-11 S5a-words, CAP-MESSAGE | a3ffd98 | 2026-10-09T12:05:41Z | nothing; 1 |
| G-S5a-12 seeded e2e screener + contrast | a3ffd98 | 2026-10-09T12:09:33Z | 17 passed |

G-S5a-1 was also covered inside G-S5a-2 after the commit. The report commit changes no code.

## 7 Tests NOT run

P-S5a-1 (user PC probe with curl against the real API): user probe, not claimed.

## 8 Deviations

- `test_layout_routes_use_only_get_post_delete` reads `app.openapi()["paths"]`: the installed FastAPI nests included routers (`_IncludedRouter`), so `app.routes` does not list `/api/layout` paths.
- `place_coin` with an unknown `group_id` writes nothing (returns False); the coin is placed by reconcile on the next read. The plan states only the reconcile outcome.
- Capped-lane reviewer subagent not spawned (allowed, not required); self-review of Python/TS lockstep, atomic write, reconcile and CORS done instead. EVL tester is the planner's step.

## 9 Blockers

None.

## 10 Follow-up

- `place_coin` and `reset_layout` move an unreadable file to `.bad` before deciding whether they write; harmless (the read would show `recovered` anyway) but noted.
- Watchlist write stays non-atomic (`_save_raw` untouched per plan; Test Infra notes).

## 11 Context cost

Read: CLAUDE.md (session-loaded), the envelope, the plan ranges named in the envelope. On demand: none of the root context docs. Source files read for the edit: the owned files plus `api/analytics/indicators/rsi.py`, `api/data/freshness.py` (iso_z, as_utc), `api/data/equities_store.py` (`_write` pattern), `api/data/ccxt_adapter.py` (OhlcvResult), `api/tests/conftest.py`, `test_watchlist.py`, `test_screener_gain_contract.py`, scan lines of `test_exchange_attention.py`, `test_history.py`, `test_no_verdict_symbols.py`. Subagents: 0. Tool calls about 30. `pnpm install --frozen-lockfile` was needed once in `web/` (deps absent in the container).
