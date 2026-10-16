---
name: plan:narrative-baskets-wave-programme
description: "COMPLEX wave programme for P5 narrative baskets after the owner decisions of 16-10-26: screener groups are the baskets, attention-momentum pipeline, My baskets tab, Discovery tab, retire verdict code, live probes. 12 worker slices."
date: 16-10-26
feature: narrative-baskets
metadata:
  node_type: memory
  type: plan
---

# Narrative Baskets: Wave programme (slices A-G)

**Complexity:** COMPLEX (12 slices, 6 waves). **SPEC:** `narrative-baskets_SPEC_02-10-26.md` + `narrative-baskets_SPEC-amendment_16-10-26.md` (A6 wins). **Status:** PLANNED; PVL 1 and 2 fixes applied 16-10-26 against `main` at 38bb43e; not yet gated. "Momentum" = mindshare (attention) momentum, never price. Python computes every number, the web renders it, unavailable data is an explicit state, never 0.

## Owner decisions (16-10-26, binding)

- **D-1 Baskets = screener groups.** Groups of section `crypto` (`api/data/layout.py`) ARE the baskets: one coin per group, names 1-40 chars unique ignoring case, at most 12 groups INCLUDING `main` (11 baskets; `MAX_GROUPS=12`), rename renames the basket (identity = group id). Group `main` is "Unassigned", never scored. No `baskets.json`. B-G read baskets only via `api/data/baskets_view.py`.
- **D-3 Percentiles** against a top-100 market-cap reference universe (stablecoin and wrapped lists excluded), also for basket coins outside it (placed, not added). A source not fetchable for the reference set is `unavailable` for ranking.
- **Momentum** = mindshare momentum. **X** key exists: private env, spend caps. **Reddit** optional. **Discovery** on the top 100 (AC-41).
- **D-2 Spend.** Ceiling 160 USD, about 106 used. Programme 36-50 (mid 43), projected 142-156. Ask point 7 USD, cap 15 per slice; the planner re-checks after waves 2 and 4 and stops for the owner above 150.
- **D-4 Defaults.** Windows 7/30/90, default 30. Weights 1/n over available sources (X lower, config). Under 90 daily points = `insufficient-history`. Kept: `/history`, `/mindshare`, `narrative_config.py`, `mapping.py`, `narrative_category_map.json`, archived parquet, `narratives.json`, `narrative_categories.json`.

## Common rules

- Worker branch `claude/<task-id>-<slug>`, one draft PR, never merged by the worker; every slice rolls back by reverting its PR. Red-first: failing tests committed first, red count recorded (report heading 6). Baselines measured on untouched origin/main, never hard-coded.
- **Read cap (CLAUDE.md WORKER set, 36,000 B for EVERYTHING the worker reads):** CLAUDE.md 13,443 + envelope <= 4,000 + plan ranges + code ranges, so plan ranges + code <= 18,500. Plan ranges = this Common rules block (about 2,100) + the slice's own section (<= 3,000) + any amendment paragraph named. Each slice lists code reads as caps; whole files are measured on main (38bb43e), ranges are budgets the worker stops at. Over budget = `needs_input`. The planner re-measures post-merge files (marked NEW) before dispatch and shrinks the list.
- Store tests redirect `watchlist.DEFAULT_WATCHLIST_PATH`, `SCREENER_LAYOUT_PATH` and new paths to `tmp_path`; never `monkeypatch.undo()` with `isolated_cache`; prove no real file changed (size, mtime, sha256). New test dirs get `__init__.py`.
- Providers are unreachable from the sandbox: adapters tested on fixtures only; no live call, no real X call. A signal without a probe record is `unavailable` and feeds no score (AC-34).
- Protected, unedited, green after every slice (AC-25): `api/tests/data/test_pytrends_adapter.py`, `api/tests/scripts/{test_snapshot_narrative,test_snapshot_workflow_schedules,test_backfill_pytrends_history}.py`, `api/tests/analytics/narrative/{test_narrative_config,test_mindshare}.py`, `api/tests/analytics/test_mapping.py`; `git diff --stat origin/main -- <paths>` empty.
- Forbidden for all: CLAUDE.md, AGENTS.md, `process/**` except the report, `.github/**`, any `.env` or key file, `api/data/pytrends_adapter.py` (wrap), `api/data/cache.py`, `api/scripts/snapshot_narrative.py`, `api/analytics/narrative/{narrative_config,exchange_attention,mapping,mindshare}.py`.
- No secret in files, fixtures, commits, prompts or logs; log `type(exc).__name__` only. A CLAUDE.md/AGENTS.md diff stops at `review`.

## S-A: baskets view over screener groups (RT2)

**Owned.** `api/data/baskets_view.py` (pure: groups minus id `main` to baskets, `unassigned`, `basket_of`), `api/models/baskets.py`, `api/routers/baskets.py`, `api/routers/watchlist.py`, `api/main.py` (one `include_router` line), tests `api/tests/data/test_baskets_view.py`, `api/tests/routers/{test_baskets,test_watchlist_cascade}.py`, one assertion in `test_watchlist.py::test_remove_coin`. **Forbidden:** `api/data/{layout,watchlist}.py`, `api/routers/layout.py`, `api/analytics/**`, `web/**`.

**Endpoints.** GET `/api/narrative/baskets` -> `{revision, baskets[{id,name,coins}], unassigned[]}`. POST `/api/narrative/baskets/{group_id}/coins` `{symbol}` moves a screener coin into a basket (`main` = unassign) -> `{symbol, basket, previous_basket}` (names, null from Unassigned). Create, rename, delete stay on `/api/layout/crypto` (revision 409). **Validation.** `group_id` matches `layout.GROUP_ID_RE` (422); `symbol` via `watchlist.normalize_symbol` (max 15, 422) and on the watchlist, else 404 "<SYM> is not on your screener. Add it to the screener first." (AC-27, file bytes unchanged); unknown group 404; extra body fields 422. `place_coin` checks neither membership nor revision, so the router checks membership; a stale UI gets the next 409.

**Defects on main (read).** (1) `layout._reconcile` appends coins no group holds to the LAST group, so a coin added without `group_id` would join a basket: the router `add_coin` calls `place_coin("crypto", sym, "main")` for a NEW coin without `group_id` when `read_layout("crypto").source == "file"` and `main` exists (best effort, logged). (2) Deleting a group moves its coins to the last group: E warns, no `layout.py` change. DELETE `/api/watchlist/{symbol}` reads the layout first and returns `affected_baskets` (names; `[]` for Unassigned or a logged layout failure) (AC-32).

**ACs.** AC-35 (amendment paragraph), AC-32, AC-27, AC-9 (via layout API, survives reload); `main` never a basket; layout without `main` returns every group; watchlist cap/404 tests green. **Tests (FA, red-first).** About 22 via router, re-read file; oversize symbol, bad id, unknown group, extra field.
**Depends on:** none. **Cost:** 3-4 USD. **Reads (caps, code 9,910):** `layout.py` consts, `_reconcile`, `read_layout`, `place_coin` 4,300 of 11,719; `routers/watchlist.py` 2,310; `main.py` router lines 900 of ~4,000; `test_layout.py` head and fixtures 1,500 of 7,387; `test_watchlist.py::test_remove_coin` and client fixture 900 of 1,826. Plan ranges 5,550 (Common 2,100, S-A 2,800, AC-35 650). Total with CLAUDE.md and 4,000 envelope: 32,903.

## S-B1: attention store, Wikipedia and CoinGecko sources (RT2, fixtures)

**Owned.** New `api/data/attention/{__init__,types,store,registry,wikipedia,coingecko_attention}.py`, `api/data/wiki_articles.json` (top 100 + screener coins; gap = `no-article`), `api/data/attention/probe_records.json` (`{}` until G), `api/scripts/refresh_attention.py`, tests and fixtures `api/tests/data/attention/`, `api/tests/scripts/test_refresh_attention.py`. **Forbidden:** edits to existing adapters (wrap `coingecko_adapter`), A files, `api/main.py`.

**Contract.** `SourceSeries(source, symbol, points[(date, value)], state, reason)`, state in `ok | unavailable | insufficient-history | no-article | capped | not-probed`. Wikipedia: daily pageviews, 90+ days. CoinGecko: top-100 list with market caps, categories, trending (if `coingecko_adapter` lacks the markets call, add a thin fetcher inside `coingecko_attention.py`, never edit the adapter). **Store.** `store.py`: `cache.CACHE_ROOT/attention/{source}/{symbol}.parquet`, path resolved at call time, atomic write, one row per UTC day, only COMPLETED UTC days (date before today) are stored (a partial day would freeze a wrong value), first observation wins. Request handlers (C, F1) read the store only. `refresh_attention.py` is the only fetcher: `--dry-run`, `--sources`, exit 0/2/1, per-source isolation, run on the owner PC (G), never from `.github`. `registry.py` maps source to fetcher; the reader returns `not-probed` without a row in `probe_records.json`.

**ACs.** AC-34, AC-24. **Tests (FA, red-first).** About 25 fixture tests (ok, empty, short history, HTTP error, rate limit, store round trip, completed-days-only, first-wins, tmp_path isolation, dry run writes nothing).
**Depends on:** none (wave 1 with A). **Cost:** 3-4 USD. **Reads (caps, code 9,104):** `coingecko_adapter.py` 3,804; `cache.py` CACHE_ROOT and atomic-write helper 1,800 of 28,762; `refresh_cache.py` arg and exit-code parts 2,000 of 5,818; `api/tests/conftest.py` `isolated_cache` 1,500. Plan ranges 4,800 (Common 2,100, S-B1 2,700). Total with 13,443 and 4,000: 31,347.

## S-B2: exchange volume and Trends sources (RT2, fixtures)

**Owned.** `api/data/attention/{exchange_volume,trends}.py`, their `registry.py` entries, tests `api/tests/data/attention/test_{exchange_volume,trends}.py`. **Forbidden:** other B1 files, existing adapters. Exchange volume: Binance daily quote volume (history), Hyperliquid (forward), wrapping `hyperliquid_narrative_adapter` and `ccxt_adapter`. Trends wraps `pytrends_adapter` (isPartial rows already dropped); comparability across 100 coins is decided in G, until then `not-probed`.
**ACs.** AC-34, AC-24. **Depends on:** B1 merged. **Cost:** 3-4 USD. **Reads (caps, code 11,700):** `hyperliquid_narrative_adapter.py` 4,724; `exchange_attention.py` public functions 2,000 of ~4,000; `pytrends_adapter.py` public functions 2,500 of 10,264; B1 `types/registry` (NEW) 2,500. Plan ranges 4,500. Total 33,600.

## S-B3: Reddit and X sources (RT2, fixtures)

**Owned.** `api/data/attention/{reddit,xsearch}.py`, their `registry.py` entries, tests `api/tests/data/attention/test_{reddit,xsearch}.py`. **Forbidden:** other B1 files, existing adapters. Reddit (AC-39) reuses the `REDDIT_CLIENT_ID/SECRET` check; no keys = `unavailable`.

**X (AC-38).** Token read at call time with `os.environ.get("X_BEARER_TOKEN")` (as `reddit_adapter._get_access_token`); absent = `unavailable`; never in a module attribute, dataclass, cache file, log, exception text or `repr`; sent only in the Authorization header. Env config, safe defaults: `X_LIVE` off (dry-run unless `X_LIVE=1`), `X_MAX_READS_PER_RUN`, `X_MAX_READS_PER_DAY`, `X_MAX_USD_PER_DAY`, `X_USD_PER_READ`; day counter under the cache dir (outside git). At a cap: stop, state `capped`. Dry run: zero network calls, prints planned reads and USD. X search covers 7 days, so daily counts are appended to the store and X stays `insufficient-history` (no score) until 90 own rows exist (about 90 days; shown in the UI). Weight below other sources; flagged for bot and cashtag spam. Tests: each cap stops the run; dry run with a network stub that fails if called; `caplog`/`repr`/exception text free of a canary token; tracked-file scan finds no bearer-token pattern.

**Depends on:** B1 merged. **Cost:** 3-4 USD. **Reads (caps, code 9,000):** `reddit_adapter.py` 5,437; B1 `types/store/registry` (NEW) 3,500. Plan ranges 5,000 (Common 2,100, S-B3 2,900). Total 31,400.

## S-C: coin and basket scoring, API (RT2)

**Owned.** `api/analytics/attention/{__init__,ratio,rank,score,basket,series,universe}.py`, `api/models/attention.py`, `api/routers/attention.py` (GET `/api/narrative/baskets/attention?window=7|30|90`, enum else 422), `api/main.py` (one line), `api/data/attention_weights.json`, `api/data/attention_universe.json` (stablecoin/wrapped lists), tests `api/tests/analytics/attention/`, `api/tests/routers/test_attention.py`. **Forbidden:** A, B files, `web/**`.

**Method (AC-36).** Per coin and source: ratio = mean(last 7 daily)/mean(last 90 daily); rank = percentile against the reference universe's ratios (D-3), ties averaged. Coin score = weighted mean of available ranks (renormalised), `sources_used n of N`. Basket score = equal mean of member scores; breadth = share of members whose score at d exceeds d-7; "covers N of M". Series: score per day from data to that day, rebased to 100 at window start; gap where no coin has data; applies TODAY's membership (payload carries `membership_as_of`). Payload per basket: `id, name, score, change, breadth, coverage, series[], coins[{symbol, score, sources[{source, raw, ratio, rank, state}]}], status, reason, universe_size`. No cross-basket total. Handlers read the store only (test: network stub raises).

**ACs.** AC-36, AC-37 (API half), AC-24, AC-35. Hand-computed tests: 2 baskets x 3 coins x 3 sources; missing source ("2 of 3"); dominant coin (breadth 1/3); coin outside the top 100 (universe size unchanged); all missing (`no-data`, no zero); empty basket. **Depends on:** A, B1 merged. **Cost:** 4-6 USD. **Reads (caps, code 11,700):** `baskets_view.py` (NEW) 2,500; B1 `types/store/coingecko_attention` (NEW) 5,000; `routers/screener.py` 2,091; `test_narrative_mindshare.py` 2,152. Plan ranges 5,200. Total 34,300.

## S-D1: decouple the old verdict code (RT2)

**Known importers (read on main; `git grep` re-confirms first).** `trigger.py`: `routers/narrative.py`; `history.py` (constants `MIN_AVAILABLE_SOURCES`, `BASE_TRUST_WEIGHT`, `REDUCED_SOURCE_TRUST_CAP`); tests `test_history.py` (also reads `trigger.py` text), `routers/test_narrative.py`, `routers/test_screener_no_verdict_contract.py` (patches `assemble_narrative_categories`), `test_narrative_trigger.py`, `test_trigger_tripwire.py`, `test_narrative_categories_contract.py`, `test_seed_narrative_fixture.py`, `seed_e2e_cache.py` (`load_seed_categories`; unread). `momentum.py`: `routers/narrative.py`, `test_momentum.py`, `test_narrative_momentum.py`. `narrative_config.py` imports `mapping.LEGACY_COIN_CATEGORY_MAP` (used by `snapshot_narrative`, the backfill script, `test_narrative_config.py`), so **`mapping.py`, `narrative_category_map.json`, `migrate_narrative_config.py` STAY**, as does `scoring.py`.

**Owned (D1).** `history.py` (own the constants, drop composite `trust_weight`), `scoring.py` (docstring), `api/scripts/seed_e2e_cache.py` + `test_seed_narrative_fixture.py` (narrative seeding only; read `narrative_categories.json` through a small local helper), `test_history.py`. After D1 only `routers/narrative.py` and files D2 deletes import `trigger`/`momentum`; suite green. **Forbidden:** common list, `routers/narrative.py`, A-C files, `web/**`. Stop rule: an importer outside this list and the owned files = `needs_input`.
**Depends on:** E2 merged. **Cost:** 3-4 USD. **Reads (caps, code 11,500):** `history.py` 3,000; `trigger.py` constants 1,500; `seed_e2e_cache.py` seeding parts 3,000 of 43,301; `test_seed_narrative_fixture.py` 2,000 of 4,611; `test_history.py` 2,000 of ~7,000. Plan ranges 5,200 (Common, D1 incl. importers). Total 34,100.

## S-D2: delete the old verdict code (RT3)

**Owned.** Delete `api/analytics/narrative/{trigger,momentum}.py`, tests `api/tests/analytics/test_narrative_trigger.py`, `api/tests/analytics/narrative/{test_trigger_tripwire,test_momentum}.py`, `api/tests/routers/{test_narrative_categories_contract,test_narrative_momentum}.py`. Edit `api/routers/narrative.py` (keep `/history`, `/mindshare`), `api/models/narrative.py`, tests `test_no_verdict_symbols.py`, `narrative/test_narrative_v2_boundaries.py`, `routers/{test_narrative,test_narrative_history,test_screener_no_verdict_contract}.py`. New `api/tests/analytics/test_no_narrative_verdict_fields.py`. **Forbidden:** common list, D1 files, `web/**`.

**ACs.** AC-11: guard test red first: `/api/narrative/categories` and `/momentum` 404; no `triggered`, `confirmed`, `trust_weight` in `/history` or `/mindshare` JSON; source scan of `api/analytics/narrative/`, `routers/narrative.py`, `models/narrative.py` finds none (not all of `api/`: regime code legitimately says `confirmed`). AC-25: protected tests unedited, green. Deleted tests listed with reasons. **Depends on:** D1, E2 merged; no deploy between E2 and D2. **Cost:** 3-4 USD (riskiest). **Reads (caps, code 11,800):** `routers/narrative.py` handlers 3,500 of 8,074; `models/narrative.py` 1,500 of 6,490; `test_screener_no_verdict_contract.py` 2,000 of 7,920; `test_no_verdict_symbols.py` 1,500 of 2,953; `test_narrative_v2_boundaries.py` 1,800 of 4,975; `routers/test_narrative.py` 1,500 of 4,188. Plan ranges 4,700. Total 33,900.

## UI standard (E1, E2, F2; AC-42)

Per tab: short header with the 7d/30d/90d selector; chart first; ranked table of five columns (name, score, signed change, breadth, "covers N of M"); coins behind a basket expand (coin score, "n of N sources", raw value per source). One plain label per number; no badges; one legend (the filter); gaps one muted "no data" mark; empty (no baskets: one line and a link to the screener), loading, error and partial states with `data-testid`s; old verdict clutter and keyword views removed. **Measurable.** vitest: one legend, no badge class, five columns, every state renders. Grep: no colour or font-size literal in new `.tsx`/css. Playwright at 375, 768, 1280 px: `scrollWidth <= clientWidth`; `web/e2e/contrast.spec.ts` unedited, green. **Gate:** before/after screenshots (three widths, each state) in the PR, checked by planner or owner; green tests alone do not accept it.

## S-E1: attention data layer, chart and table (RT3)

**Owned.** `web/components/narrative/{BasketAttentionChart,BasketTable}.tsx` with `__tests__/**`, `web/lib/{api,types}/attention.ts`, `web/lib/attention-lines.ts`, `web/lib/__tests__/attention*`. Standalone components, tested with injected data; no dashboard edit. **Forbidden:** `api/**`, `NarrativeDashboard.tsx`, other web files.
**ACs.** AC-37 (lines, gaps, "membership as of today" line), AC-36 UI, AC-24 (no `0` for missing), AC-42 chart and table. **Tests.** Red-first: `pnpm --filter web test`, `tsc --noEmit`, `pnpm build:islands`. **Depends on:** A, C merged. **Cost:** 3-5 USD. **Reads (caps, code 10,700):** `SpaghettiChart.tsx` 3,500 of 6,075; `use-simple-lines.ts` 2,198; `globals.css` tokens 2,000; `lib/api/narrative.ts` 2,175; `DeadDataNotice.tsx` 841. Plan ranges 5,900 (Common, UI standard 1,600, E1). Total 34,000.

## S-E2: My baskets tab wiring (RT3 + Playwright)

**Owned.** `web/components/narrative/{NarrativeTabs,BasketCoins}.tsx`, `NarrativeDashboard.tsx`, deletions of old views (`CategoryHistoryPanel`, `ComparisonView`, `ChangeInAttentionView`, `MomentumView`, `RedistributionBadge`, `MindshareView`, `DataQualityCaveat` if unused) and their tests, trimmed `web/lib/{api,types}/narrative.ts`, `web/lib/narrative-view-model.ts`, `web/lib/narrative-panel-lines.ts` and their tests, `web/e2e/narrative.spec.ts`, `web/components/screener/CoinActions.tsx` + `web/lib/api/watchlist.ts` (removal notice naming the basket; grep which file holds the DELETE call). Discovery tab = one-line placeholder until F2. Group deletion warns that coins move to the last group. **Forbidden:** `api/**`; e2e creates baskets through the real API (Playwright `request`).
**ACs.** AC-35/32 UI; AC-42; grep gate: no `trust_weight`, `triggered`, `confirmed` in `web/components/narrative`, `web/lib/*narrative*`, `web/lib/*/attention*`. **Tests.** Red-first; `pnpm --filter web test`, `tsc --noEmit`, `pnpm build:islands`, `pnpm test:e2e` (`PLAYWRIGHT_CHROMIUM_PATH`, `SCREENER_REFRESH_WORKER=0`). **Depends on:** E1 merged. **Cost:** 4-5 USD. **Reads (caps, code 12,500):** `NarrativeDashboard.tsx` 4,500 of 7,846; `CoinActions.tsx` 2,500 of 4,431; `CoinGroup.tsx` 2,500 of 8,685; `narrative.spec.ts` 3,000 of 16,199. Plan ranges 5,900. Total 35,343 with an envelope <= 3,500. **Risk.** CI does not run e2e.

## S-F1: Discovery API (RT2)

**Owned.** `api/analytics/attention/discovery.py`, `api/models/discovery.py`, `api/routers/discovery.py` (GET `/api/narrative/discovery?window=7|30|90`, enum), `api/data/discovery.json` (volume floor, exclusion lists), `api/main.py` (one line), tests `api/tests/analytics/attention/test_discovery.py`, `api/tests/routers/test_discovery.py`. **Forbidden:** B, C files (read only), `web/**`.

**Method (AC-41).** C's top-100 list minus exchange tokens (config + category tags) minus 24h volume under the floor (about 20M USD). Per coin 7d vs 30d per source from the store; "gaining" iff at least 2 independent sources rise; contribution winsorized at the 95th percentile; category score = mean, median beside it, `coins_used`. A coin counts in each of its CoinGecko categories; no cross-category total. Ranked by category momentum.
**ACs.** AC-40 (API half), AC-41 (each rule tested), AC-24. **Depends on:** C, B2 merged. **Cost:** 3-4 USD. **Reads (caps, code 11,500):** `coingecko_adapter.py` 3,804; B1 `coingecko_attention`/`store` (NEW) 3,000; C `universe/rank` (NEW) 2,500; `test_narrative_mindshare.py` 2,152. Plan ranges 5,000. Total 33,900.

## S-F2: Discovery tab (RT3)

**Owned.** `web/components/narrative/Discovery*.tsx` (+ tests), `web/lib/{api,types}/discovery.ts`, tab wiring in `NarrativeTabs.tsx`, Discovery cases in `web/e2e/narrative.spec.ts`. **Forbidden:** `api/**`. **ACs.** AC-40, AC-42. **Tests.** As E2. **Depends on:** F1, E2 merged. **Cost:** 3-4 USD. **Reads (caps, code 11,000):** `NarrativeTabs.tsx` (NEW) 2,500; `BasketTable.tsx` (NEW) 2,500; `globals.css` tokens 2,000; `narrative.spec.ts` 2,500; `lib/api/attention.ts` (NEW) 1,500. Plan ranges 5,400 (Common, UI standard 1,600, F2). Total 33,800.

## S-G: live probes on the owner PC

No agent can run these. Per signal the owner records in `api/data/attention/probe_records.json` and the task folder (AC-34): reachable; history depth (90 days); per-coin; refetchable for 100 coins; comparable across coins; personal-use terms. X also: dry-run estimate vs one capped real run, spam sample, real USD per 100 reads; key only in the owner's private environment. Then the owner schedules `refresh_attention.py`. Order: Wikipedia, exchange volume, CoinGecko, Trends, Reddit (if keys), X last. Agent part (wave 6): `api/scripts/record_probe.py` + `api/tests/scripts/test_record_probe.py`, 1-2 USD. No record = "unavailable".

## Waves and cost (max 2 concurrent workers)

| Wave | Slices | Why |
|---|---|---|
| 1 | A, B1 | disjoint; `api/main.py` only in A |
| 2 | C, B2 | C needs A, B1; B2 needs B1; disjoint (C: `main.py`, `analytics/`; B2: `data/attention/`) |
| 3 | E1, B3 | E1 needs A, C (web only); B3 needs B1 (api only) |
| 4 | E2, F1 | E2 web; F1 api and `main.py` |
| 5 | D1, F2 | D1 api; F2 web |
| 6 | D2, G script | api, disjoint files |
| any | G probes | owner PC; gate which sources feed scores |

USD (reading-based; recent slices ran 1-4 USD): A 3-4, B1 3-4, B2 3-4, B3 3-4, C 4-6, D1 3-4, D2 3-4, E1 3-5, E2 4-5, F1 3-4, F2 3-4, G script 1-2 = 36-50 (mid 43). 106 + 36-50 = 142-156 vs 160.

## Risks

R1 unprobed sources: tabs thin until G. R2 ranks need `refresh_attention.py` run on the PC. R3 old stack more entangled than read (D1 stop rule). R4 read ranges are caps from reading. R5 X cost drift (caps, default off). R6 groups coupled to the board. R7 UI judged by eye (screenshot gate). R8 Windows paths only on the PC. R9 X feeds no score for about 90 days. R10 NEW file sizes known only at dispatch.

## Validate contract

_Placeholder. `vc-validate-agent` writes this section (V1-V7) before EXECUTE; do not start EXECUTE with it empty. Run `validate-plan-artifact.mjs` (RT0). Not opened yet: `seed_e2e_cache.py`, `globals.css`, `.github` workflows, `conftest.py`, `refresh_cache.py`._

## Planner checklist (after merge)

Register slices in MASTER-PLAN; fix docs naming removed symbols (`all-context.md`, `all-tests.md`, `all-data-sources.md`); decision entry D-1/D-3; update SPEC split note; note the legacy `coingecko/{category}` series freeze when `trigger.py` goes.
