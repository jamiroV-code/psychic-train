# T72 (P5 S-C2) report: top-100 reference universe

## 1 Task ID
T72, branch `claude/t72-p5-s-c2-universe`, base origin/main.

## 2 Outcome
done. Ranking now uses a top-100 market-cap reference from a stored snapshot (AC-36 reference part). A missing reference is explicit: `no-data`, reason `reference-missing`, never a 0 (AC-24).

## 3 Summary
- `fetch_top100_markets` (unfiltered rows `{id, symbol, market_cap, volume_24h}`, None on failure); `fetch_top100` untouched.
- `universe_store.py`: atomic `cache.CACHE_ROOT/attention/universe.json`, same date replaced, last 14 kept, path resolved at call time.
- `refresh_attention.py`: source `universe` in DEFAULT_SOURCES; dry run makes no call and writes nothing; a failed fetch keeps the old file and counts as a source error.
- `load_universe()` returns `(symbols, reason)`: non-empty `reference` in the config overrides, else the latest snapshot; first 100 by market cap, then minus stablecoins, wrapped and `exchange_tokens`. Absent/corrupt = `([], "reference-missing")`. `load_reference()` still returns a list.
- **Owner to confirm:** the new `exchange_tokens` list (BNB LEO OKB CRO GT KCS BGB MX) is a planner PROPOSAL, kept as editable config in `attention_universe.json`. It drops BNB from the reference.
- Known limits:
  - The markets endpoint has no category tags, so none are stored.
  - The cut to 100 happens before exclusions, so the reference holds fewer than 100 symbols.
  - The universe source is in DEFAULT_SOURCES, so the first live run must be done by the owner/planner; none was run here.
  - `_atomic_write_json` is a private helper of cache.py, reused (cache.py not edited).

## 4 Files changed
`api/data/attention/{coingecko_attention.py, universe_store.py (new)}`, `api/scripts/refresh_attention.py`, `api/analytics/attention/{universe,basket}.py`, `api/data/attention_universe.json`, tests: `test_universe_store.py` (new), `test_universe.py` (new), additions in `test_coingecko_attention.py`, `test_basket_scoring.py`, `test_refresh_attention.py`.

## 5 Commits
Red tests first (failing), then implementation (see PR).

## 6 Tests run
- Baseline origin/main: `UV_FROZEN=1 uv run --project api pytest api/ -q` = 1324 passed, 1 skipped, 5 deselected.
- After: same command = 1342 passed, 1 skipped, 5 deselected (baseline + 18 new). Protected tests unedited (diff empty); `git diff --check` clean; cache tree hash unchanged.
- Red count: 8 failed + 2 collection errors (the two new modules, 10 tests) = 18 red tests at the red commit.
- Date 2026-10-16 UTC; SHA: see PR head. Spend: well under 7 USD.

## 7 Tests NOT run
No live network, no live `refresh_attention.py`. Playwright/web not relevant.

## 8 Deviations
- Existing `test_default_sources_exclude_opt_in_volume_and_trends` asserted DEFAULT_SOURCES == (wikipedia, coingecko); updated to include `universe` (owned file, required by the spec).
- Read cap: the actual file sizes exceeded the planned ones (refresh_attention.py 5,350, coingecko_attention.py 3,615, plan ranges 3,893); I read ranges only, total stayed near the cap, not measured exactly.
- `watchlist.json` is not tracked in the repo at a path I could find; the cache tree was hashed before/after instead (unchanged).

## 9 Blockers
None.

## 10 Follow-up
Owner confirms `exchange_tokens`; first live `universe` refresh on the owner PC.

## 11 Context cost
About 36 KB of reads (cap 36,000), no extra docs opened.
