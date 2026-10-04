# OHLCV: negative cache for failed fetches, and the 1d gap rule (backlog stub)

Source: T32 / S1 (screener batch 1, freshness core), decisions D7 and D18. Not scheduled.

## 1. Failed fetches are not negatively cached (D7)

Since S1, a cache is fresh only when it was fetched inside the current bar and within `FORMING_TTL`. A fetch that FAILS (network error, rate limit, bad symbol) leaves the cache and its `fetched_at` sidecar untouched, so the next request retries the exchange at once. While the exchange is down, every board request therefore pays one failing call per (coin, timeframe): up to 30 coins x 4 fetched timeframes, each up to the ccxt timeout. `load_markets` failure is already latched per process (gap G4); per-fetch failures are not.

Options to weigh later: remember the failure time per (symbol, timeframe) in memory and skip the exchange for a short back-off (for example `FORMING_TTL`); or let the S8 background worker own all refreshes so request paths never wait on a failing exchange. S8 may make this moot; re-check after S8 merges.

## 2. A non-contiguous 1d tail keeps deep history (D18)

On the `since=None` path a 15m/1h/4h tail that does not touch the cache REPLACES the cached series (`note="gap-replaced"`). For `1d` the cached deep history (500+ bars, needed by the 60-period SMA, weekly derivation and pairs) is KEPT and the tail appended (`note="gap-kept"`), so the series can contain a hole of missing days. Indicators computed over the close sequence then span the hole silently.

Options: backfill the hole with explicit-`since` requests (up to 5000 candles each) when `gap-kept` is reported; or surface `note` in the payload so the UI can flag it. Needs a decision on whether a hole is acceptable for the regime/pairs consumers of daily bars.
