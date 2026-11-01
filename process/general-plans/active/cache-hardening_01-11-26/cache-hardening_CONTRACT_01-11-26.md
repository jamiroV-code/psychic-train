# cache-hardening validate-contract (01-11-26)

Branch `claude/cache-hardening`, base origin/main e1394b80. Direct-lane worker.

## Scope (verified open on e1394b80)
- KG3: `api/analytics/cointegration/pairs_response.py:134-137,174-176,182-184` write results, provenance and spread files with no fsync and a fixed `.tmp` name.
- KG4: `api/data/cache.py:349-351` (`write_liqtide_raw`) and `:529-531` (`write_exchange_market_snapshot`) use a fixed `.json.tmp` name, no fsync.
- KG5: `api/data/etf_flows_adapter.py:110` writes the cache parquet in place (`merged.to_parquet(path)`).

## Not built (verified)
- SQ1 watchlist fallback: no fallback exists (`api/data/watchlist.py:89-91` returns an empty list); the open item is an owner decision whether to ADD one.
- D7: S8 refresh worker merged (`api/data/refresh_worker.py:127-130`, `ccxt_adapter.py:547-549`); worker-off residual only.
- D18: note states "Needs a decision"; behaviour unchanged (keeps history, never shortens).

## Gates
1. Red tests committed failing first (one commit), then fixes.
2. One convention: every fix goes through cache.py's existing same-directory `mkstemp` + fsync + `os.replace` helpers; no new temp scheme.
3. Written bytes unchanged (same JSON separators and ensure_ascii per writer).
4. `UV_FROZEN=1 uv run --project api pytest` on changed test files green; then `api/tests/data`, `api/tests/analytics`, `api/tests/scripts/test_compute_pairs.py`, `api/tests/routers/test_pairs.py`, `api/tests/routers/test_regime_components.py` green except known Windows host failures.
5. No edits to .github/, dependency files, PR #211 files.
6. Draft PR; Linux CI green.
