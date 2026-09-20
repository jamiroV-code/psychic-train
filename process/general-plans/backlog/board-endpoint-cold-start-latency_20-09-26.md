# Backlog: Screener board endpoint pays a ~23.7s cold-start cost on the first request

**Date raised**: 20-09-26
**Raised by**: `dead-data-notice-unification_PLAN_20-09-26.md` EVL — `pnpm test:e2e` (Playwright),
root-caused during the same plan's UPDATE PROCESS phase
**Status**: OPEN
**Origin plan**: `process/general-plans/active/momentum-screener_17-09-26/dead-data-notice-unification_PLAN_20-09-26.md`

## Why this exists

`pnpm test:e2e` (Playwright) failed 1 of 6 specs —
`"the board renders one panel per watchlist symbol, from a real request"`
(`web/e2e/screener.spec.ts`) — while the other 5 passed and all 40/40 vitest tests passed. Not a
regression from `dead-data-notice-unification`'s 8 touchpoints (all confined to
`web/components/screener/` presentational markup, no `api/` file among them). Root-caused by direct
read of the live backend source, during this same task's UPDATE PROCESS pass:

1. **`load_markets()` is uncached and lazy, with no pre-warm.** `_exchange()`
   (`api/data/ccxt_adapter.py:101-123`) builds the process-wide `ccxt.hyperliquid()` singleton and
   calls `ex.load_markets()` at line 117 the first time any request needs a live fetch. This costs
   roughly 12.5s. No FastAPI `startup`/`lifespan` handler exists anywhere in `api/` to run this at
   process boot instead of on the first real request (confirmed by a repo-wide grep for
   `startup`/`lifespan`/`load_markets` — no such hook exists anywhere in the codebase).
2. **OHLCV fetching is fully serial, no concurrency.** `build_coin_panel`
   (`api/analytics/screener_board.py:134-146`) fetches `1d` and `1w` (lines 134-135), then loops
   sequentially over the remaining `TIMEFRAMES` (`15m`/`1h`/`4h`) at lines 141-145 — one
   `ccxt_adapter.fetch_ohlcv` call at a time, awaited before the next starts. `build_screener_board`
   (lines 175-194) then calls `build_coin_panel` once per watchlist coin in a plain synchronous list
   comprehension (lines 190-193) — no `asyncio.gather`, no thread pool, no concurrency anywhere in
   this file or `ccxt_adapter.py`. With the current 4-coin watchlist (`api/data/watchlist.json`:
   BTC, HYPE, ETH, SOL) and 4 live-fetched timeframes per coin (`1d`, `15m`, `1h`, `4h` — `1w`
   derives from the already-cached `1d` bars fetched moments earlier in the same call via
   `_cache_is_fresh`, so it costs no extra network round trip), a cold board request makes **up to
   16 sequential live OHLCV calls**, each costing roughly 0.3-0.8s.
3. **The arithmetic matches the measured failure.** 12.5s (`load_markets`) + ~8s (serial OHLCV
   fetches, ~16 × ~0.5s) + ~3.3s (baseline compute) ≈ the measured 23.7s on the very first request
   after a fresh process start. Playwright's default `expect` timeout is 5s, so only the very first
   request against a freshly-started, seeded, cold-cache backend trips it — exactly what an isolated
   single-spec run, or the first spec in a full-suite run, is. A warm request (same process, the
   `_exchange()` singleton and cache already populated, `_cache_is_fresh()` at
   `ccxt_adapter.py:173-184` short-circuiting most per-timeframe work) took 3.3-3.6s, which is why 5
   of 6 specs in the same run pass.

## Why it matters

Not a correctness bug — every eventually-successful request returns correct data; this is pure
first-request latency. But it means:

- A cold-started backend (every real deployment restart, and every from-scratch e2e run) fails its
  first board request against any client with a timeout well under ~24s, Playwright's default 5s
  included.
- The e2e suite is now flaky-by-position: whichever spec happens to hit the backend first pays the
  full cold-start cost and can fail on timing alone, unrelated to what it is actually testing. A
  future spec reordering, a new spec added earlier in the file, or CI parallelization changes could
  make a *different* spec fail next, which would look like a new regression when it is really the
  same pre-existing defect landing on a different spec.

## Secondary, currently-dormant risk (not proven active in this run)

Neither `pytrends_adapter.fetch_trend` (`api/data/pytrends_adapter.py:85-112`) nor
`reddit_adapter.fetch_mentions` (`api/data/reddit_adapter.py:106-134`) checks cache freshness before
attempting a live call — unlike `ccxt_adapter._cache_is_fresh`, both adapters always attempt the live
call first and only fall back to the cached series on failure. In this sandbox this costs
effectively 0s (`pytrends` import fails instantly at `pytrends_adapter.py:54-57`; Reddit's
`_get_access_token` returns `None` immediately when `REDDIT_CLIENT_ID`/`REDDIT_CLIENT_SECRET` are
unset, `reddit_adapter.py:52-55`), but a fully configured deployment with real credentials and
reachable third-party APIs would add real per-request latency here too, on **every** board request
that touches narrative data, not just the first. Flagged as a secondary note, not confirmed as
contributing to the measured 23.7s in this environment — a fix here is lower priority than the
primary cold-start defect above unless/until credentials are configured for real.

## What a fix would need

For the primary cold-start defect (pick one or combine):

- Add a FastAPI `lifespan`/`startup` handler that calls `ccxt_adapter._exchange()` (or a dedicated
  `warm_exchange()` wrapper) once at process boot, moving the `load_markets()` cost off the first
  real request.
- Parallelize the per-timeframe fetches inside `build_coin_panel` (e.g. a bounded thread pool around
  the existing synchronous `ccxt` calls, since `ccxt`'s sync client is not natively async) and/or
  parallelize `build_screener_board`'s per-coin loop — either would cut the ~8s serial-fetch
  component significantly.
- Alternatively, and cheaper on the test side only: have the e2e suite's global setup issue one
  warm-up request to `/api/screener/board` before running specs, so no individual spec pays the
  cold-start cost. This would stabilize the suite but would not fix the underlying latency for real
  users on a fresh deployment.

For the secondary dormant risk: add a freshness/TTL check to `pytrends_adapter.fetch_trend` and
`reddit_adapter.fetch_mentions` before attempting a live call, mirroring
`ccxt_adapter._cache_is_fresh`'s pattern, so a fully configured deployment does not pay live-call
latency on every request when a fresh cached value already exists.

## Not blocking

`dead-data-notice-unification_PLAN_20-09-26.md` shipped and was verified without this fix — none of
its 8 touchpoints touch `api/`, and the failing e2e spec's root cause is independently confirmed to
be pre-existing backend behavior, not caused by this plan's frontend markup change. Flagged for a
future PLAN/EXECUTE cycle, not a blocker on anything currently in flight.
