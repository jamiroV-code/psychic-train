# OHLCV: negative cache for failed fetches, and the 1d gap rule (backlog stub)

Source: T32 / S1 (screener batch 1, freshness core), decisions D7 and D18. D7 remains backlog; D18 is in execution review.

**Re-check 01-11-26 (not built):** D7 — S8 merged: while the worker runs (default on) page reads are cache-only (`refresh_worker.py:449-451`, `ccxt_adapter.py:547-549`) and failed pairs are skipped until the next backoff-aware tick (`refresh_worker.py:127-130,292,339`). Residual only with `SCREENER_REFRESH_WORKER=0`, where `ccxt_adapter.py:597-603` still retries per request. D18 — unchanged (`ccxt_adapter.py:632-635`, `gap-kept`); still needs the owner decision below.

**D18 execution 02-11-26 — verified, owner review pending:** Owner chose “keep the gap and flag it”. Timestamp-derived daily summaries and visible board/drill-down disclosure are implemented on `claude/daily-data-gap`, draft PR #223. Isolated real-storage/API smoke and the resumed guarded API/Next/Edge Playwright gate passed cache/reload persistence, timeframe independence, real repair/removal, unchanged parquet/indicators and zero actual provider attempts. Readable 375/768/1280 plus repaired screenshots are retained in the task evidence folder. Earlier resource/fixture/guard failures are documented, not hidden. See `../active/daily-data-gap_02-11-26/daily-data-gap_REPORT_02-11-26.md`. D7, backfill and regime/pairs policy are unchanged.

## 1. Failed fetches are not negatively cached (D7)

Since S1, a cache is fresh only when it was fetched inside the current bar and within `FORMING_TTL`. A fetch that FAILS (network error, rate limit, bad symbol) leaves the cache and its `fetched_at` sidecar untouched, so the next request retries the exchange at once. While the exchange is down, every board request therefore pays one failing call per (coin, timeframe): up to 30 coins x 4 fetched timeframes, each up to the ccxt timeout. `load_markets` failure is already latched per process (gap G4); per-fetch failures are not.

Options to weigh later: remember the failure time per (symbol, timeframe) in memory and skip the exchange for a short back-off (for example `FORMING_TTL`); or let the S8 background worker own all refreshes so request paths never wait on a failing exchange. S8 may make this moot; re-check after S8 merges.

## 2. A non-contiguous 1d tail keeps deep history (D18)

On the `since=None` path a 15m/1h/4h tail that does not touch the cache REPLACES the cached series (`note="gap-replaced"`). For `1d` the cached deep history (500+ bars, needed by the 60-period SMA, weekly derivation and pairs) is KEPT and the tail appended (`note="gap-kept"`), so the series can contain a hole of missing days. Indicators computed over the close sequence then span the hole silently.

The approved D18 slice discloses internal missing UTC-day intervals from the complete daily timestamp series, not the transient fetch note. It does not backfill or change indicator calculations. Broader regime/pairs treatment remains out of scope.
