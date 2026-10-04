# T35 / S8 in-process background refresh worker: worker report (04-10-26)

## 1 Task ID

T35 (screener batch 1, slice S8: in-process background refresh worker, decisions B9 and D7). Branch `claude/t35-s8-refresh-worker`, from `main` 161e7be (S1 merged, PR #34).

## 2 Outcome

Done; status `review`. G-S8-1 to G-S8-9 pass on a1354aa. P-S8-1 is a user-PC probe and is not claimed. Nothing was merged or deployed.

## 3 Summary

- `api/data/refresh_worker.py` (new): `RefreshWorker`, a daemon thread loop.
  - First tick after 20 s, then every `SCREENER_REFRESH_INTERVAL_SECONDS` (default 900).
  - A tick plans sorted(watchlist + BTC + HYPE) x (15m, 1h, 4h, 1d), plus anything queued.
  - It fetches only pairs that fail `freshness.cache_is_fresh`. A missing file never counts as fresh.
  - `1w` is derived through `fetch_ohlcv(sym, "1w")` right after the coin's `1d` and is never fetched directly.
  - Pool of 4 threads, with one non-blocking lock per (symbol, timeframe). A busy pair is skipped.
- Wake handling: the loop waits on a `threading.Event` with the delay as timeout.
  - `request_refresh` (deduplicated, non-blocking) wakes a drain of the queued pairs.
  - `request_now` wakes one full tick. At most one tick is pending.
- Failure handling:
  - Each pair runs inside `try/except`, and so does each loop iteration. Logs carry only exception type names.
  - Backoff: a tick with no `ok`/`stale` pair and at least one `unavailable` doubles the delay, capped at 3600 s. Any success resets it.
  - Each tick first calls `ccxt_adapter.retry_markets_if_latched()` (N1).
  - A pair that failed since the last tick is skipped by woken drains, so page loads cannot get around the backoff (review item 1).
- Clock, wait Event, fetch, exchange, symbol source, freshness rule and latch retry are all injectable.
- Process registry: `start_from_env` / `stop_worker` / `install_worker` / `status()`.
  - `SCREENER_REFRESH_WORKER` is tri-state: `0` off, `1` forces on, unset on.
  - `disabled_reason` is `SCREENER_REFRESH_WORKER=0`, `stopped`, `start-failed` or `not-started`.
  - `reads_cache_only_if_running()` is the router wrapper.
- `api/data/ccxt_adapter.py`: added `cached_reads_only()` (a `ContextVar`), `set_refresh_hook()` and `retry_markets_if_latched()`.
  - Inside the context, `fetch_ohlcv` serves the cache with zero exchange work. It calls the hook for any pair that is not fresh and sets `note="refresh-queued"`. A missing cache gives an empty frame with status `unavailable`.
  - In the same mode, the `1w` branch derives from the cached daily without writing.
  - With the flag off, the S1 code path is unchanged.
- `api/routers/refresh.py` (new):
  - `GET /api/refresh/status` returns the 9 planned fields plus `disabled_reason`. Timestamps use the `Z` form.
  - `POST /api/refresh/now` returns 202 `{accepted, already_pending}`, or 503 `worker-not-running` when the worker is off.
- `api/routers/screener.py`: board, relative-performance and scalp are wrapped in `reads_cache_only_if_running()`.
- `api/main.py`: a `lifespan` starts and stops the worker, plus `include_router(refresh.router)`.
- `api/tests/conftest.py`: the two A4 lines, placed after `from __future__ import annotations`.

## 4 Files changed

- `api/data/refresh_worker.py` (new)
- `api/routers/refresh.py` (new)
- `api/data/ccxt_adapter.py`
- `api/routers/screener.py`
- `api/main.py`
- `api/tests/conftest.py` (+2 lines exactly)
- `api/tests/data/test_refresh_worker.py` (new, 14 tests)
- `api/tests/routers/test_refresh_router.py` (new, 3 tests)
- `api/tests/deploy/test_refresh_startup.py` (new, 3 tests; A2 `monkeypatch.delenv("SCREENER_REFRESH_WORKER", raising=False)` in `test_lifespan_starts_and_stops_worker`)
- this report

All files are in Owned. None is under deploy/, api/scripts/, web/, .claude/, .github/, and none is an S2 file.

## 5 Commits

- a7bf45e: worker, adapter flag, routers, lifespan, 20 tests
- a1354aa: review fixes (drain throttle after failures, non-blocking pool shutdown, stop previous worker on install, start failure degrades instead of crashing the app, no `1w` write on cache-only reads, clock guard in the loop)
- (this report commit)

## 6 Tests run

S1-merged baseline, recorded at step 1 on 161e7be at 2026-10-04T01:54:59Z:
- pytest `api/`: 931 passed, 2 skipped, 5 deselected, 0 xfailed
- vitest: 223 passed in 30 files
- tsc: exit 0
- islands: exit 0

Red run (TDD stubs on 161e7be, 2026-10-04T02:00:12Z): G-S8-1 gave 20 failed.

Final runs, each once after the last code edit, on SHA a1354aa:

| Gate | UTC | Result |
|---|---|---|
| G-S8-1 | 2026-10-04T02:08:59Z | 20 passed, 0 failed, 0 skipped |
| G-S8-8 | 2026-10-04T02:09:05Z | 61 passed, 1 skipped, 1 deselected, 0 failed |
| G-S8-6 `git diff --check` | 2026-10-04T02:09:13Z | exit 0, no output |
| G-S8-7 S8-scope + FORBIDDEN | 2026-10-04T02:09:14Z | both print nothing |
| G-S8-9 FIXTURES | 2026-10-04T02:09:14Z | prints nothing |
| G-S8-2 | 2026-10-04T02:09:18Z | 951 passed (931 + 20), 2 skipped, 5 deselected, 0 xfailed, 0 failed |
| G-S8-3 | 2026-10-04T02:12:13Z | 223 passed in 30 files (unchanged) |
| G-S8-4 | 2026-10-04T02:12:24Z | exit 0 |
| G-S8-5 | 2026-10-04T02:12:28Z | exit 0 |

- Every pytest run used `UV_FROZEN=1`.
- Full-suite budget: 2 of 2 runs used (the baseline and G-S8-2).
- `ruff check` on all touched Python files: clean.

## 7 Tests NOT run

- P-S8-1 (user PC: overnight ticks, 30-coin rate limits, restart, warm board under 10 s). Agent-Probe, not claimed.
- CI: the result is recorded on the PR.

## 8 Deviations

- G-S8-3/4/5 commands were run from `web/` (`pnpm test`, `pnpm exec tsc ...`, `pnpm build:islands`). `pnpm --filter web ...` from the repo root fails here: the root has no `package.json` and `web/node_modules` was not installed. I ran `pnpm install --frozen-lockfile` in `web/` first, which changed no tracked file.
- The plan's xfailed count (1) is gone on the S1-merged base: the baseline shows 0 xfailed and 2 skipped. Counts are relative to that baseline, as the envelope says.
- The status payload adds `disabled_reason` next to the 9 listed fields, as Design point 4 and B9 require. `POST /now` returns the body `{accepted, already_pending}`.
- Pending-run semantics: `/now` asks for one full tick, and a load-triggered request asks for a drain of the queue only.

## 9 Blockers

None.

## 10 Follow-up

Reviewer items I left unfixed (none blocking):
- (a) `/api/regime/*` still calls `fetch_ohlcv("BTC","1d")` inline while the worker runs. It is outside S8's board/scalp/relative-performance scope.
- (b) A scalp request for a symbol that is not in the watchlist queues it, which costs one fetch attempt per tick at most. `_pair_locks` grows by one small entry per distinct symbol.
- (c) After an offline start, latch recovery waits for the next tick, which can be up to 3600 s under backoff. The plan specifies one retry per tick.

For the planner:
- A3: document the `SCREENER_REFRESH_WORKER=0` prefix for the seeded E2E in all-tests.md at UPDATE PROCESS.

## 11 Context cost

- Files read: CLAUDE.md, the envelope, the plan by the named line ranges plus the Cycle-3 advisory block (423-433), and the S1 report headings only (for the template). operating-instructions.md was not opened.
- Subagents: 1 of the 3 allowed. One `vc-code-reviewer` (sonnet), read-only, one level deep, covering thread-safety and lifespan. It found 0 blocking defects and 8 nits; I fixed 5 in a1354aa. The cost is within the cap and I estimate it at under 1 USD.
- Tool calls: about 40.
