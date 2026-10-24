# T77 (P5 S-F1) Discovery API: report

## 1 Task ID
T77, P5 S-F1. Branch `claude/t77-p5-s-f1-discovery-api`, base origin/main 087ca81.

## 2 Outcome
done. `GET /api/narrative/discovery?window=7|30|90` (default 30, other values 422) is live, store and config only.

## 3 Summary
Rules (each tested): top-100 universe from C's `load_universe` (stablecoins and wrapped already out); `exclude` list and `exclude_category_ids` (exchange-based-tokens) in `api/data/discovery.json`; 24h volume floor 20,000,000 USD (unknown volume = excluded, floor itself kept); per coin and source: mean of last 7 completed days vs mean of the `window` days before them; "gaining" iff at least 2 independent source groups rise (`source_groups` config: coingecko and exchange volume count as one); a coin needs at least 2 usable sources to be used; coin change = mean of its source changes (percent), winsorized at the category's 95th percentile (linear interpolation, upper tail); category score = mean, `median` beside, `coins_used`, `gaining_count`; a coin counts in each of its categories; no cross-category total; categories ranked by score, desc.

Categories: new `fetch_categories(ids, client, sleep)` in coingecko_attention.py (no key; markets endpoint with `category=`, 2 s pause, all-or-nothing, None on any failure). New `categories_store.py` (atomic, call-time path `attention/categories.json`, 14 kept). `refresh_attention.py --sources categories` (opt-in, not in DEFAULT_SOURCES): dry run writes nothing, failure keeps the old file.

Payload (for F2), `DiscoveryResponse`:
- `window` 7|30|90, `as_of` (yesterday UTC), `categories_as_of` (snapshot date, "" if none)
- `status` "ok"|"no-data"; `reason`: "" | "categories-missing" | "reference-missing" | "no-attention-data"
- `universe_size` (top-100 after list exclusions), `eligible_size` (after exclusions and volume floor)
- `categories[]`: `id`, `name`, `score` (mean, percent, null if no coins), `median`, `coins_used`, `gaining_count`, `coins[]`
- `coins[]` (sorted by change desc): `symbol`, `change` (winsorized %), `raw_change` (%), `gaining`, `sources_used`, `sources_gaining`
- Non-ok responses carry `categories: []`.

Known limits:
- CoinGecko's categories list endpoint has no membership, so membership is fetched per category from the config list (9 public tags plus the exchange-token tag); other tags are not shown.
- `window` sets the baseline length, not a fixed 7d-vs-30d (30 is the default and gives 7d vs the prior 30d); window 90 needs at least 45 baseline days and a source `ok` (90 days).
- Winsorizing clips the upper tail only (spec says 95th).
- Categories are only as fresh as the last manual `refresh_attention.py --sources categories` run; not scheduled.
- Coins never fetched for the store (outside wiki_articles) have no series, so are simply not used.

## 4 Files changed
Added: api/analytics/attention/discovery.py, api/models/discovery.py, api/routers/discovery.py, api/data/discovery.json, api/data/attention/categories_store.py, tests (analytics test_discovery, routers test_discovery, data/attention test_categories_store).
Edited (add-only except noted): api/main.py (import + one include_router), api/data/attention/coingecko_attention.py, api/scripts/refresh_attention.py (runner, import, print branch widened to `universe`/`categories`), tests test_coingecko_attention.py, test_refresh_attention.py (see 8).

## 5 Commits
a922120 red tests; 4ee1339 implementation; plus the report commit.

## 6 Tests run
- Baseline untouched origin/main: `UV_FROZEN=1 uv run --project api pytest api/ -q` = 1360 passed, 1 skipped, 5 deselected.
- Red: 10 failed + 3 collection errors (test_discovery x2, test_categories_store) at a922120.
- After: `pytest api/ -q` = 1402 passed, 1 skipped, 5 deselected (baseline 1360 + 42 new tests; skipped/deselected unchanged). Head SHA before the report commit: 4ee1339.
- Protected tests: `git diff --stat origin/main` on them empty. `git diff --check origin/main...HEAD` clean. Diff empty for web, CLAUDE.md, AGENTS.md, .claude, .github, cache.py.
- Real cache dir: tree sha256 before 63604a11d51a... (hash of all file hashes); after: 63604a11d51a... (equal: True). watchlist.json: path api/data/watchlist.json does not exist in this checkout, nothing to change.
- UTC date 2026-10-17. Spend: well under the 7 USD ask point (estimate 2 USD).

## 7 Tests NOT run
No vitest, no e2e (web untouched: `git diff origin/main -- web` empty). No live call; `refresh_attention.py` never run live.

## 8 Deviations
- Edited the existing pin test `test_default_sources_and_runners_are_pinned` (RUNNERS set gets "categories") in test_refresh_attention.py: unavoidable when adding a runner.
- Membership comes from per-category markets calls, not one categories-endpoint call (that endpoint has no members).
- Runner imports `discovery.load_config` lazily to read the category ids.

## 9 Blockers
None.

## 10 Follow-up
F2 consumes the payload above. Schedule the categories refresh (workflow) outside this slice. Consider a window-independent 7d vs 30d if the owner wants it literal.

## 11 Context cost
Read: CLAUDE.md, envelope, plan ranges (Common, S-F1, D-3/D-4), code ranges listed in the envelope plus conftest, basket.py/series.py head, test excerpts, about at cap; no other protocol docs opened.
