# T69 (P5 S-B1) Report

## 1 Task ID
T69, P5 S-B1. Branch claude/t69-p5-s-b1-attention-store, base origin/main (ae9c095).

## 2 Outcome
done. Draft PR opened against main; not merged.

## 3 Summary
- Added attention store (completed UTC days only, one row per day, first observation wins, path resolved at call time under cache.CACHE_ROOT/attention, atomic write via the existing cache helper).
- Added Wikipedia pageviews source and a CoinGecko source (thin fetchers inside coingecko_attention.py: top-100 markets minus stablecoin/wrapped lists, per-coin daily volume). coingecko_adapter is wrapped (fetch_trending_symbols), not edited.
- registry.py maps source to fetcher; read_series returns not-probed without a row in probe_records.json ({}).
- refresh_attention.py: --dry-run, --sources, --symbols; exit 0 (a source ok), 2 (none ok), 1 (every source errored); per-source isolation; logs exception type names only.
- Known limits:
  - CoinGecko stores 24h volume (market_chart, daily) as its proxy; categories and trending are not stored (trending is a snapshot; wrapper only).
  - wiki_articles.json has 47 symbols (about 20 mapped null = no-article), not the full top 100 plus screener coins; needs a follow-up fill.
  - The CoinGecko stablecoin/wrapped exclusion lists are a short hand-written set.
  - Provider response shapes are fixture-based only; no live check (probe is slice G).

## 4 Files changed
Owned files only: api/data/attention/{__init__,types,store,registry,wikipedia,coingecko_attention}.py, probe_records.json, api/data/wiki_articles.json, api/scripts/refresh_attention.py, api/tests/data/attention/ (__init__, conftest, fixtures/markets_top.json, 4 test files), api/tests/scripts/test_refresh_attention.py, plus this report.

## 5 Commits
1. 1a0f392 tests (red)
2. implementation commit (green)
3. report commit

## 6 Tests run
- Red: `UV_FROZEN=1 uv run --project api pytest api/tests/data/attention api/tests/scripts/test_refresh_attention.py -q` on commit 1a0f392: 5 collection errors, 0 tests run (46 test functions defined). Red count 5 errors / 46 tests.
- Baseline on untouched origin/main (separate worktree): `UV_FROZEN=1 uv run --project api pytest api/ -q` = 1204 passed, 1 skipped, 5 deselected.
- After (HEAD 9b2811c, 2026-10-16T19:33Z): same command = 1250 passed, 1 skipped, 5 deselected. Equals baseline + 46 new tests.
- Protected tests are inside the full run, green; `git diff --stat origin/main` on them is empty.
- `git diff --check origin/main...HEAD` clean. `git diff origin/main` empty for CLAUDE.md, AGENTS.md, .claude, .github, api/main.py, api/data/cache.py, coingecko_adapter.py, api/analytics, api/routers, web.
- Real cache: api/data/cache has 108 files, listing fingerprint (size, mtime, path) 8db64397b494b05b after the run; git status clean. No separate before snapshot was taken, so the before/after check rests on git status clean plus test isolation (a test asserts the real cache tree is unchanged). api/data/watchlist.json does not exist in this checkout (nothing to hash).
- Spend: not measured by the harness; well under the 7 USD ask line.

## 7 Tests NOT run
Web vitest and e2e not run; `git diff origin/main -- web` is empty. No live provider call and no run of refresh_attention.py live.

## 8 Deviations
- A first baseline run started on the working tree while the branch was being cut; discarded and re-measured in a clean worktree of origin/main.
- No before-snapshot of the real cache (see heading 6).
- Test conftest alias fixture attention_cache is used only under api/tests/data/attention; the script test uses isolated_cache directly.

## 9 Blockers
None.

## 10 Follow-up
Complete wiki_articles.json for top 100 plus screener coins; verify provider shapes in slice G; decide whether CoinGecko trending/categories need storage.

## 11 Context cost
Read: CLAUDE.md (13,443 B), plan ranges (about 4,000 B), coingecko_adapter.py (3,804 B), and small ranges of cache.py, refresh_cache.py and conftest.py. Within the 36,000 B cap. No other docs opened.

## 12 Addendum (2026-10-16, tester finding F5): real-cache snapshot
Taken on origin/main after PRs #98 to #101 and #103, by a separate session, as the before/after proof heading 6 lacked. It is a fresh check, not a reconstruction of the original run.
- `api/data/cache`: 108 files, all tracked in git. For each file, path, size, mtime and sha256 were listed and sorted before and after the run.
- Run: `UV_FROZEN=1 uv run --project api pytest api/tests/data/attention api/tests/scripts/test_refresh_attention.py -q` = 64 passed.
- Result: before and after listings are byte-identical (digest of the listing starts 14f76fbfd93eaf5c); `git status` clean; `api/data/watchlist.json` and `layout.json` do not exist, so nothing to hash.
