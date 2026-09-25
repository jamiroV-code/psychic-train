---
name: report:pair-screener-rfc-001
description: "RFC-001 phase report — pair universe file + loader + deep-fetch backfill script, real Hyperliquid deep fetch, tests"
date: 25-09-26
metadata:
  node_type: memory
  type: report
  feature: cointegration-screener
  phase: RFC-001
phase: rfc-001
status: COMPLETE
feature: cointegration-screener
plan: process/features/cointegration-screener/active/pair-screener_25-09-26/pair-screener_PLAN_25-09-26.md
---

# RFC-001 — Universe file + loader + deep-fetch script

**Bottom line:** RFC-001 is code-complete. All 18 coins are now deeply cached: 660 to 2229 daily
bars each, going back to between 2020-08-19 and 2024-12-05. No coin hit the 5000-bar cap. BTC, ETH,
HYPE and SOL grew with zero old bars lost or changed. The full api suite shows 420 passed (392 + 28
new) and 3 deselected. Stage 0 findings are in `pair-screener_RFC-001-stage0_REPORT_25-09-26.md`.

## What Was Done

| File | Change |
|---|---|
| `api/pyproject.toml`, `api/uv.lock` | `statsmodels>=0.14` (installed 0.15.0); no `arch` (Stage 0) |
| `api/data/pairs_universe.json` (new) | `{"coins": [...]}`, the 18 approved tickers |
| `api/data/pairs_universe.py` (new) | `load_universe(path=None)`: path resolved at call time, uppercases and strips, warns and drops duplicates, warns on known stablecoins, raises `UniverseFileError` on a missing or malformed file. `enumerate_pairs()` returns C(n,2) pairs. Does not import `watchlist` |
| `api/scripts/backfill_pairs_universe.py` (new) | `DEEP_FETCH_SINCE_MS` = 2020-01-01 UTC (named constant), `DEEP_FETCH_LIMIT = 5000`, explicit `since` on every call. A `RecordingExchange` proxy sees the raw page length, so a page of exactly 5000 bars triggers the next page (`since` = last bar + 1 day). Stops on a short or empty page, on `now`, or at `MAX_PAGES = 20`. Prints a per-coin table. No CLI args; mirrors `backfill_primaries.py` |
| `api/tests/data/test_pairs_universe.py` (new, 19 tests) | Real file = the 18; C(18,2) = 153 with no dupes or self-pairs (AC-1); malformed/missing file; warnings; isolation (AC-9): a fresh-interpreter import leaves `api.data.watchlist` out of `sys.modules`, plus an AST check |
| `api/tests/scripts/test_backfill_pairs_universe.py` (new, 9 tests, all `isolated_cache`) | Shallow 501-bar cache deepened to the mocked deep start (row count AND first date); every call uses `since` and never `None`; mocked cap pages forward with exact advanced `since` values; single call when not capped; `MAX_PAGES` stop; `bad_symbol` reported without a fetch; `watchlist.json` hash unchanged (AC-11 partial); constant = 2020-01-01 UTC |

`ccxt_adapter.py` was not edited, and neither were any screener, watchlist, regime or narrative
files. No commits were made.

## Real deep-fetch run (Hyperliquid, this machine, 25-09-26)

Backup taken first. The four existing `1d.parquet` files were copied to
`C:\Users\Z00565YF\AppData\Local\Temp\claude\C--Users-Z00565YF-Downloads-my-project\75b7eff2-0c93-44e6-a0de-05d94771440f\scratchpad\ohlcv-backup\{BTC,ETH,HYPE,SOL}\1d.parquet`.

Script output (every coin took 1 page; 0 pages hit the cap):

| Coin | Status | Bars | First | Last |
|---|---|---|---|---|
| BTC | ok | 2229 | 2020-08-19 | 2026-09-25 |
| ETH | ok | 2229 | 2020-08-19 | 2026-09-25 |
| SOL | ok | 2203 | 2020-09-14 | 2026-09-25 |
| HYPE | ok | 660 | 2024-12-05 | 2026-09-25 |
| XRP | ok | 2196 | 2020-09-21 | 2026-09-25 |
| DOGE | ok | 2229 | 2020-08-19 | 2026-09-25 |
| ADA | ok | 2069 | 2021-01-26 | 2026-09-25 |
| AVAX | ok | 2194 | 2020-09-23 | 2026-09-25 |
| LINK | ok | 2226 | 2020-08-22 | 2026-09-25 |
| LTC | ok | 2229 | 2020-08-19 | 2026-09-25 |
| BCH | ok | 2183 | 2020-10-04 | 2026-09-25 |
| DOT | ok | 2109 | 2020-12-17 | 2026-09-25 |
| SUI | ok | 1242 | 2023-05-03 | 2026-09-25 |
| NEAR | ok | 2051 | 2021-02-13 | 2026-09-25 |
| APT | ok | 1438 | 2022-10-19 | 2026-09-25 |
| ARB | ok | 1283 | 2023-03-23 | 2026-09-25 |
| OP | ok | 1578 | 2022-06-01 | 2026-09-25 |
| ATOM | ok | 2229 | 2020-08-19 | 2026-09-25 |

**Exactly-5000 flag:** none. The largest count is 2229.

**DuckDB coverage query** (the plan's verification query, all 18 in one pass): the row counts and
first/last dates are identical to the table above. For every coin, row count = distinct timestamps,
so there are no duplicate bars.

**Grew, not replaced (BTC/ETH/HYPE/SOL):**

| Coin | Before (bars, range) | After (bars, range) | Old bars missing | Old bars with changed OHLCV |
|---|---|---|---|---|
| BTC | 501, 2025-05-08..2026-09-20 | 2229, 2020-08-19..2026-09-25 | 0 | 0 |
| ETH | 501, 2025-05-08..2026-09-20 | 2229, 2020-08-19..2026-09-25 | 0 | 0 |
| HYPE | 501, 2025-05-08..2026-09-20 | 660, 2024-12-05..2026-09-25 | 0 | 0 |
| SOL | 501, 2025-05-08..2026-09-20 | 2203, 2020-09-14..2026-09-25 | 0 | 0 |

All 501 old bars are present with byte-equal OHLCV, including the previously newest bar
(2026-09-20). The last dates moved forward 5 days. The merge only added bars.

## Feasibility-VERDICT known-gaps (recorded, not dropped)

1. **Live cap behaviour:** not observed, because no real response reached 5000. Only the mocked test
   proves the pagination logic. **New observation:** BTC, ETH, DOGE, LTC and ATOM all start on
   exactly **2020-08-19**, and LINK starts 3 days later. The same first date across unrelated coins
   suggests Hyperliquid has a server-side history floor, not five coincident listings. A floor at
   the OLD end cannot be fixed by paging forward, and nothing would detect it (the page is below
   5000). It does not affect AC-8 (365-day minimum overlap), because every pair has at least 660
   overlapping days. It is worth knowing when reading "first date" as a listing date.
2. **Real listing dates:** first dates are recorded above. For the 2020-08-19 group they are likely
   the floor, not the listing.
3. **Rate-limit/backoff under 18 sequential calls:** not stressed. 18 calls completed with no
   rate-limit failures (every status `ok`). The adapter's own `_fetch_with_backoff` is unchanged.

## Test Gate Outcomes

| Gate | Result |
|---|---|
| New tests only | 28 passed |
| `uv run --project api pytest api/tests/data/ api/tests/scripts/ -q` | 164 passed, 2 deselected, 2 warnings (warnings not from new files) |
| Real deep fetch (hybrid) | 18/18 `ok`, table above |
| DuckDB coverage query | matches, no duplicate timestamps |
| Grew-not-replaced check | 0 missing, 0 changed, for all 4 |
| `uv run --project api pytest api/ -q` | **420 passed, 3 deselected** (392 baseline + 28 new) |

## Plan Deviations

1. **RFC-001 Stages item 3 text (UPDATE PROCESS to fix):** the plan says
   `fetch_ohlcv(symbol, "1d", limit=DEEP_LOOKBACK_LIMIT)` with no `since`. The implementation
   follows the Stage 0 / feasibility-VERDICT method instead: `since=DEEP_FETCH_SINCE_MS`
   (2020-01-01 UTC) on every call, `limit=5000`, and next-page on a capped response. This was
   user-approved (decision 4). The plan body was not edited.
2. **Cap detection via a recording proxy (within blast radius):** `fetch_ohlcv` returns the merged
   cache, not the raw page, so the script wraps the exchange in `RecordingExchange` and passes it as
   `exchange=` to see the raw length. The adapter's own public `exchange=` parameter is used, and
   the adapter is not modified. Side effect: the script calls `ccxt_adapter._exchange()` (a
   module-private accessor) to get the shared instance to wrap.
3. **Verification Checklist "Error handling confirmed (a `bad_symbol` universe candidate excluded)"**
   was left unticked. No real coin failed resolution, so there was no real exclusion to record. The
   `bad_symbol` path is covered by the mocked `test_unknown_coin_is_reported_not_fetched` and
   `test_backfill_all_never_touches_watchlist_json`. "User confirmed working" is also unticked; that
   is your call.

## Test Infra Gaps Found

- None blocking. The live cap and old-end history-floor behaviour are known-gaps (above).
- The cache directory is git-ignored, so the deep cache exists only on this machine. A fresh clone
  needs to run the script once (Ops Runbook).

## Closeout Packet

- Plan: `process/features/cointegration-screener/active/pair-screener_25-09-26/pair-screener_PLAN_25-09-26.md`
- Finished: RFC-001 Stages 0-3, tests, real run, all implementation checkboxes.
- Verified: 28 new tests, scoped and full suites, real deep fetch, coverage query, grew-not-replaced.
- Unverified: user review of the universe and coverage table; the live cap/floor behaviour.
- Classification: **Keep in active/testing.** The RFC is code-complete and awaiting user confirmation. RFC-002 has not started.
- Next valid state: EVL confirmation run (vc-tester), then user confirms RFC-001, then RFC-002 Stage 0.

## Forward Preview

### Test Infra Found
`isolated_cache` plus an injected fake exchange (`exchange=`) runs `fetch_ohlcv` with no network.
The `FakeExchange` in `test_backfill_pairs_universe.py` honours since/limit/cap and is reusable for
RFC-002/005 fixtures.

### Blast Radius Changes
New: `api/data/pairs_universe.{json,py}`, `api/scripts/backfill_pairs_universe.py`, two test files.
Modified: `api/pyproject.toml`, `api/uv.lock`. Local cache (git-ignored): 14 new
`api/data/cache/ohlcv/{coin}/1d.parquet` files, and 4 deepened.

### Commands to Stay Green
- `uv run --project api pytest api/tests/data/ api/tests/scripts/ -q` (164 passed / 2 deselected)
- `uv run --project api pytest api/ -q` (420 passed / 3 deselected, ~4.5 min)
- Re-deepen: `uv run --project api python api/scripts/backfill_pairs_universe.py`

### Dependency Changes
statsmodels 0.15.0 (+ scipy 1.18.1, patsy, formulaic, interface-meta, narwhals, wrapt).
RFC-002 note: in 0.15, `coint()` returns a `CointResult` (indexable, length 3), and `coint_johansen`
can emit `ComplexWarning`.

Follow-up plan stubs created: none. CONTEXT_PARTIAL: none.
