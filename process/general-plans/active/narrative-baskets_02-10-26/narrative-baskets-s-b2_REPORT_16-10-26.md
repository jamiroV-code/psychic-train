# T71 (P5 S-B2) report

## 1 Task ID
T71, branch claude/t71-p5-s-b2-volume-trends.

## 2 Outcome
done (draft PR, not merged). ACs AC-34, AC-24 covered on fixtures.

## 3 Summary
- `exchange_volume.py`: Binance daily quote volume (history, close x base volume of completed UTC days) and Hyperliquid forward-only (rolling 24h snapshot stored as previous UTC day). Never raises; reasons carry exception type only.
- `trends.py`: wraps `pytrends_adapter.fetch_trend`; one point per refresh, current-day row dropped; stays not-probed (no probe row added).
- Registry entries: exchange_volume, hyperliquid_volume, trends. Owner approved widening (option 1): `refresh_attention.py` got runners, default sources pinned to wikipedia,coingecko (new sources opt-in via --sources, so default runs make no ccxt/pytrends call); `test_registry.py` expected set updated; one test added to `test_refresh_attention.py`.
- Known limits: Binance quote volume is an approximation; Hyperliquid and Trends history builds forward one point per refresh (90 days to ok); no live call was ever made, so provider behaviour is unprobed (slice G); Trends keyword defaults to the lower-case symbol.

## 4 Files changed
api/data/attention/{exchange_volume,trends,registry}.py; api/scripts/refresh_attention.py; api/tests/data/attention/{test_exchange_volume,test_trends,test_registry}.py; api/tests/scripts/test_refresh_attention.py; this report.

## 5 Commits
cf73fd2 red tests; 3232a8d implementation.

## 6 Tests run
- Baseline origin/main: UV_FROZEN=1 uv run --project api pytest api/ -q: 1282 passed, 1 skipped, 5 deselected.
- Red (cf73fd2): 2 collection errors (17 new tests uncollected) + 2 failing (registry set, refresh default sources) = red count 4.
- After merging main (conflict in refresh_attention.py resolved): full suite 1300 passed, 1 skipped, 5 deselected.
- git diff --check origin/main: clean. web and protected pytrends test and adapter diff: empty. Date 2026-10-16 UTC, SHA 3232a8d. Spend: under 1 USD.

## 7 Tests NOT run
Full pytest after the final fix; sha256/mtime check of real cache and watchlist.json (not captured before; tests use isolated_cache and tmp_path); vitest/e2e (web untouched).

## 8 Deviations
Edited `refresh_attention.py`, `test_registry.py`, `test_refresh_attention.py` (B1 files) on the owner's explicit choice "1". Read cap exceeded slightly by reading refresh_attention.py and its test. No `exchange_attention.py` in api/data (only the forbidden analytics one, unread); ccxt_adapter has no daily-volume function, so ccxt is called directly.

## 9 Blockers
None.

## 10 Follow-up
Slice G: probe records and Trends comparability. Planner: confirm Binance/Hyperliquid terms before enabling by default.

## 11 Context cost
About 36-40 KB of reads; docs opened: none beyond the envelope set.
