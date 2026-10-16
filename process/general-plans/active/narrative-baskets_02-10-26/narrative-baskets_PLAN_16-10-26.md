---
name: plan:narrative-baskets-wave-programme
description: "COMPLEX wave programme for P5 narrative baskets after the owner decisions of 16-10-26: screener groups are the baskets, attention-momentum pipeline, My baskets tab, Discovery tab, retire verdict code, live probes. Slices A-G."
date: 16-10-26
feature: narrative-baskets
metadata:
  node_type: memory
  type: plan
---

# Narrative Baskets: Wave programme (slices A-G)

**Complexity:** COMPLEX (8 slices, 4 waves). **SPEC:** `narrative-baskets_SPEC_02-10-26.md` + `narrative-baskets_SPEC-amendment_16-10-26.md` (A6 wins). **Status:** PLANNED; PVL pass 1 fixes applied 16-10-26 against `main` at 38bb43e; not re-validated. "Momentum" = mindshare (attention) momentum, never price. Python computes every number, the web renders it, unavailable data is an explicit state, never 0.

## Owner decisions (16-10-26, binding)

- **D-1 Baskets = screener groups.** Groups of section `crypto` (`api/data/layout.py`) ARE the baskets: one coin per group, names 1-40 chars unique ignoring case, at most 12 groups INCLUDING `main` (11 baskets, accepted), rename renames the basket (identity = group id). Group `main` is "Unassigned", never scored. No `baskets.json`. B-G read baskets only via `api/data/baskets_view.py`.
- **D-3 Percentile universe.** Ranks are percentiles against a top-100 market-cap reference universe (stablecoin and wrapped lists excluded), also for basket coins outside the top 100 (placed in the distribution, not added). A source not fetchable for the reference set is `unavailable` for ranking.
- **Momentum** = mindshare momentum. **X** key exists: private env only, spend caps. **Reddit** optional. **Discovery** on the top 100 with the AC-41 rules.
- **D-2 Spend.** Ceiling 160 USD, about 106 used. Programme 32-48 (mid 40), projected 138-154. Ask point 7 USD, cap 15 per slice; the planner re-checks after waves 2 and 3 and stops for the owner above 150.
- **D-4 Defaults.** Windows 7/30/90, default 30. Weights 1/n over available sources (X lower, config). Under 90 daily points = `insufficient-history`. Kept: `/history`, `/mindshare`, `narrative_config.py`, `mapping.py`, archived parquet, `narratives.json`, `narrative_categories.json`.

## Common rules

- Worker branch `claude/<task-id>-<slug>`, PR to main. Red-first: failing tests committed first (report heading 6). Baselines measured on untouched origin/main.
- Store tests redirect `watchlist.DEFAULT_WATCHLIST_PATH`, `SCREENER_LAYOUT_PATH` and new paths to `tmp_path`; never `monkeypatch.undo()` with `isolated_cache`; prove no real file changed (size, mtime, sha256). New test dirs get `__init__.py` (suite imports `api.tests...`).
- Providers are unreachable from the sandbox: adapters tested on fixtures only. A signal without a probe record is `unavailable` and feeds no score (AC-34).
- Protected, unedited, green after every slice (AC-25: pytrends partial-hour fix, nightly archive): `api/tests/data/test_pytrends_adapter.py`, `api/tests/scripts/{test_snapshot_narrative,test_snapshot_workflow_schedules,test_backfill_pytrends_history}.py`, `api/tests/analytics/narrative/{test_narrative_config,test_mindshare}.py`, `api/tests/analytics/test_mapping.py`; `git diff --stat origin/main -- <paths>` empty.
- Forbidden for all: CLAUDE.md, AGENTS.md, `process/**` except the report, `.github/**`, any `.env` or key file, `api/data/pytrends_adapter.py` (wrap), `api/data/cache.py`, `api/scripts/snapshot_narrative.py`, `api/analytics/narrative/{narrative_config,exchange_attention,mapping,mindshare}.py`.
- No secret in files, fixtures, commits, prompts or logs; log `type(exc).__name__` only.
- Reads: entry set = CLAUDE.md 13,443 B + envelope <= 4,000 + Common rules + slice text (<= 8,000), about 26,000 B (cap 36,000). Source ranges (<= 35,000 B) are the files the envelope names; sizes measured on main, `~` = estimate. A CLAUDE.md/AGENTS.md diff stops at `review`. Spend per slice in heading 6.

## S-A: baskets view over screener groups (RT2)

**Owned.** `api/data/baskets_view.py` (pure: groups minus id `main` to baskets, `unassigned`, `basket_of`), `api/models/baskets.py`, `api/routers/baskets.py`, `api/routers/watchlist.py`, `api/main.py` (one `include_router` line), tests `api/tests/data/test_baskets_view.py`, `api/tests/routers/{test_baskets,test_watchlist_cascade}.py`, one assertion in `test_watchlist.py::test_remove_coin`. **Forbidden:** `api/data/{layout,watchlist}.py`, `api/routers/layout.py`, `api/analytics/**`, `web/**`.

**Endpoints.** GET `/api/narrative/baskets` -> `{revision, baskets[{id,name,coins}], unassigned[]}`. POST `/api/narrative/baskets/{group_id}/coins` `{symbol}` moves a screener coin into a basket (`main` = unassign) -> `{symbol, basket, previous_basket}` (names, null from Unassigned). Create, rename, delete stay on `/api/layout/crypto` (revision 409). **Validation.** `group_id` matches `layout.GROUP_ID_RE` (422); `symbol` via `watchlist.normalize_symbol` (max 15, 422) and on the watchlist, else 404 "<SYM> is not on your screener. Add it to the screener first." (AC-27, file bytes unchanged); unknown group 404; extra body fields 422. `place_coin` checks neither membership nor revision, so the router checks membership; a stale UI gets the next 409.

**Defects found on main.** (1) `layout._reconcile` appends coins no group holds to the LAST group, so a coin added without `group_id` would join a basket: `add_coin` calls `place_coin(..., "main")` for a new coin without `group_id` when `read_layout("crypto").source == "file"` and `main` exists. (2) Deleting a group moves its coins to the last group: E warns, no `layout.py` change. DELETE `/api/watchlist/{symbol}` reads the layout first and returns `affected_baskets` (names; `[]` for Unassigned or a logged layout failure) (AC-32).

**ACs.** AC-35, AC-32, AC-27, AC-9 (via layout API, survives reload); `main` never a basket; layout without `main` returns every group; watchlist cap/404 tests green. **Tests (FA, red-first).** About 22 via router, re-read file; oversize symbol, bad id, unknown group, extra field.
**Depends on:** none. **Cost:** 3-4 USD. **Reads (~22,000):** `layout.py` ranges ~6,500 of 11,719; `models/layout.py` ~1,900; `routers/watchlist.py` 2,310; `watchlist.py` ~1,000; `main.py` ~700; `test_layout.py` 7,387; `test_watchlist.py` 1,826. **Rollback.** Revert PR.

## S-B1: attention store and universe-wide sources (RT2, fixtures)

**Owned.** New `api/data/attention/{__init__,types,store,registry,wikipedia,exchange_volume,coingecko_attention}.py`, `api/data/wiki_articles.json` (top 100 + screener coins; gap = `no-article`), `api/data/attention/probe_records.json` (`{}` until G), `api/scripts/refresh_attention.py` + `api/tests/scripts/test_refresh_attention.py`, tests and fixtures `api/tests/data/attention/`. **Forbidden:** edits to existing adapters (wrap `coingecko_adapter`, `hyperliquid_narrative_adapter`, `ccxt_adapter`), A files.

**Contract.** `SourceSeries(source, symbol, points[(date, value)], state, reason)`, state in `ok | unavailable | insufficient-history | no-article | capped | not-probed`. Wikipedia: daily pageviews, 90+ days. Exchange volume: Binance daily quote volume (history), Hyperliquid (forward). CoinGecko: top-100 list with market caps, categories, trending. **Store (first draft persisted nothing).** `store.py`: `cache.CACHE_ROOT/attention/{source}/{symbol}.parquet`, path resolved at call time, atomic write, one row per UTC day, first observation wins. Request handlers (C, F) read the store only. `refresh_attention.py` is the only fetcher: `--dry-run`, `--sources`, exit 0/2/1, per-source isolation, run on the owner PC (G), never from `.github`. `registry.py` maps source to fetcher; the reader returns `not-probed` without a row in `probe_records.json`.

**ACs.** AC-34, AC-24. **Tests (FA, red-first).** About 30 fixture tests (ok, empty, short history, HTTP error, rate limit, store round trip, first-wins, tmp_path isolation, dry run writes nothing).
**Depends on:** none (wave 1 with A). **Cost:** 4-6 USD. **Reads (~26,000):** `coingecko_adapter.py` 3,804; `hyperliquid_narrative_adapter.py` 4,724; `exchange_attention.py` ~4,000; `cache.py` ~5,000 of 28,762; `refresh_cache.py` 5,818; its adapter test 3,265. **Risk.** Wrong article mapping (reviewable JSON). **Rollback.** Revert PR.

## S-B2: Trends, Reddit and X sources (RT2, fixtures)

**Owned.** `api/data/attention/{trends,reddit,xsearch}.py`, their `registry.py` entries, tests/fixtures `api/tests/data/attention/test_{trends,reddit,xsearch}.py`. **Forbidden:** other B1 files, existing adapters.

Trends wraps `pytrends_adapter` (isPartial rows already dropped); comparability across 100 coins is decided in G, until then `not-probed`. Reddit (AC-39) reuses the `REDDIT_CLIENT_ID/SECRET` check; no keys = `unavailable`.

**X (AC-38).** Token read at call time with `os.environ.get("X_BEARER_TOKEN")` (as `reddit_adapter._get_access_token`); absent = `unavailable`; never in a module attribute, dataclass, cache file, log, exception text or `repr`; sent only in the Authorization header. Env config with safe defaults: `X_LIVE` off (dry-run unless `X_LIVE=1`), `X_MAX_READS_PER_RUN`, `X_MAX_READS_PER_DAY`, `X_MAX_USD_PER_DAY`, `X_USD_PER_READ`; day counter under the cache dir (outside git). At a cap: stop, state `capped`. Dry run: zero network calls, prints planned reads and USD. X search covers 7 days, so daily counts are appended to the store and X stays `insufficient-history` (no score) until 90 own rows exist (about 90 days; shown in the UI). Weight below other sources; flagged for bot and cashtag spam. Tests: each cap stops the run; dry run with a network stub that fails if called; `caplog`/`repr`/exception text free of a canary token; tracked-file scan finds no bearer-token pattern.

**Depends on:** B1 merged. **Cost:** 4-6 USD. **Reads (~19,000):** B1 `types/store/registry` ~5,000; `pytrends_adapter.py` ~6,000; `reddit_adapter.py` 5,437; `test_pytrends_adapter.py` ~3,000 (protected). **Rollback.** Revert PR.

## S-C: coin and basket scoring, API (RT2)

**Owned.** `api/analytics/attention/{__init__,ratio,rank,score,basket,series,universe}.py`, `api/models/attention.py`, `api/routers/attention.py` (GET `/api/narrative/baskets/attention?window=7|30|90`, enum else 422), `api/main.py` (one line), `api/data/attention_weights.json`, `api/data/attention_universe.json` (stablecoin/wrapped lists), tests `api/tests/analytics/attention/`, `api/tests/routers/test_attention.py`. **Forbidden:** A, B files, `web/**`.

**Method (AC-36).** Per coin and source: ratio = mean(last 7 daily)/mean(last 90 daily); rank = percentile against the reference universe's ratios (D-3), ties averaged. Coin score = weighted mean of available ranks (renormalised), `sources_used n of N`. Basket score = equal mean of member scores; breadth = share of members whose score at d exceeds d-7; "covers N of M". Series: score per day from data to that day, rebased to 100 at window start; gap where no coin has data; it applies TODAY's membership to the window (moving a coin rewrites the past) and the payload carries `membership_as_of`. Payload per basket: `id, name, score, change, breadth, coverage, series[], coins[{symbol, score, sources[{source, raw, ratio, rank, state}]}], status, reason, universe_size`. No cross-basket total; table key is `change`. Handlers read the store only (test: network stub raises).

**ACs.** AC-36, AC-37 (API half), AC-24, AC-35. Hand-computed tests: 2 baskets x 3 coins x 3 sources; missing source ("2 of 3"); dominant coin (breadth 1/3); coin outside the top 100 (universe size unchanged); all missing (`no-data`, no zero); empty basket. **Depends on:** A, B1 merged. **Cost:** 4-6 USD. **Reads (~17,000):** `baskets_view.py` ~2,500; B1 `types/store` ~4,000; `freshness.py` 3,845; `routers/screener.py` 2,091; a router test ~4,000. **Rollback.** Revert PR.

## S-D: retire the old verdict code (RT3)

**Known importers (read on main; `git grep` re-confirms first).** `trigger.py`: `routers/narrative.py`; `history.py` (constants `MIN_AVAILABLE_SOURCES`, `BASE_TRUST_WEIGHT`, `REDUCED_SOURCE_TRUST_CAP`); tests `test_history.py` (also reads `trigger.py` text), `routers/test_narrative.py`, `routers/test_screener_no_verdict_contract.py` (patches `assemble_narrative_categories`), `test_narrative_trigger.py`, `test_trigger_tripwire.py`, `test_narrative_categories_contract.py`, `test_seed_narrative_fixture.py`, `seed_e2e_cache.py` (`load_seed_categories`; unread). `momentum.py`: `routers/narrative.py`, `test_momentum.py`, `test_narrative_momentum.py`. `narrative_config.py` imports `mapping.LEGACY_COIN_CATEGORY_MAP` (used by `snapshot_narrative`, the backfill script, `test_narrative_config.py`), so **`mapping.py`, `narrative_category_map.json`, `migrate_narrative_config.py` STAY**, as does `scoring.py` (history, mindshare). `screener_board.py` does not import trigger.

**Owned.** Delete `api/analytics/narrative/{trigger,momentum}.py`, tests `api/tests/analytics/test_narrative_trigger.py`, `api/tests/analytics/narrative/{test_trigger_tripwire,test_momentum}.py`, `api/tests/routers/{test_narrative_categories_contract,test_narrative_momentum}.py`. Edit `api/routers/narrative.py` (keep `/history`, `/mindshare`), `api/models/narrative.py`, `history.py` (own the constants, drop composite `trust_weight`), `scoring.py` (docstring), tests `test_no_verdict_symbols.py`, `narrative/test_narrative_v2_boundaries.py`, `test_history.py`, `routers/{test_narrative,test_narrative_history,test_screener_no_verdict_contract}.py`, `api/scripts/seed_e2e_cache.py` + `test_seed_narrative_fixture.py` (narrative seeding only; read `narrative_categories.json` through a small local helper). New `api/tests/analytics/test_no_narrative_verdict_fields.py`. **Forbidden:** common list, A-C files, `web/**`.

**ACs.** AC-11: guard test red first: `/api/narrative/categories` and `/momentum` 404; no `triggered`, `confirmed`, `trust_weight` in `/history` or `/mindshare` JSON; source scan of `api/analytics/narrative/`, `routers/narrative.py`, `models/narrative.py` finds none (not all of `api/`: regime code legitimately says `confirmed`). AC-25: protected tests unedited, green. Deleted tests listed with reasons. Stop rule: an importer outside this list and the owned files = `needs_input`. **Depends on:** A, C merged; merge after E, no deploy between. **Cost:** 5-8 USD (riskiest). **Reads (~33,000):** `routers/narrative.py` 5,000 of 8,074; `history.py` ~3,000; `trigger.py` constants ~1,500; `models/narrative.py` ~3,000; `test_history.py` ~3,000; `test_screener_no_verdict_contract.py` ~2,500; `test_no_verdict_symbols.py` 2,953; `test_narrative_v2_boundaries.py` 4,975; `test_seed_narrative_fixture.py` 4,611; `seed_e2e_cache.py` ~3,500 of 43,301. Larger importer list: split D1 (api source) / D2 (tests, seeder). **Rollback.** Revert PR.

## UI standard (E and F; AC-42)

Worker reads first: `web/app/globals.css` tokens, `web/components/screener/{SpaghettiChart,CoinGroup,DeadDataNotice}.tsx`. Per tab: short header with the 7d/30d/90d selector; chart first; ranked table of five columns (name, score, signed change, breadth, "covers N of M"); coins behind a basket expand (coin score, "n of N sources", raw value per source). One plain label per number; no badges; one legend (the filter); gaps one muted "no data" mark; empty (no baskets: one line and a link to the screener), loading, error and partial states with `data-testid`s; old verdict clutter and keyword views removed. **Measurable.** vitest: one legend, no badge class, five columns, every state renders. Grep: no colour or font-size literal in new `.tsx`/css. Playwright at 375, 768, 1280 px: no horizontal scroll (`scrollWidth <= clientWidth`); `web/e2e/contrast.spec.ts` unedited, green. **Gate:** before/after screenshots (three widths, each state) in the PR, checked by planner or owner; green tests alone do not accept it.

## S-E: My baskets tab (RT3 + Playwright)

**Owned.** `web/components/narrative/**` (new `NarrativeTabs.tsx`, `BasketAttentionChart.tsx`, `BasketTable.tsx`, `BasketCoins.tsx`; edit `NarrativeDashboard.tsx`; delete old views `CategoryHistoryPanel`, `ComparisonView`, `ChangeInAttentionView`, `MomentumView`, `RedistributionBadge`, `MindshareView`, `DataQualityCaveat` if unused) with `__tests__/**`; `web/lib/{api,types}/attention.ts`, `web/lib/attention-lines.ts`, trimmed `web/lib/{api,types}/narrative.ts`, `web/lib/narrative-view-model.ts`, `web/lib/narrative-panel-lines.ts`, `web/lib/__tests__/` narrative and attention files, `web/e2e/narrative.spec.ts`, `web/components/screener/CoinActions.tsx` + `web/lib/api/watchlist.ts` (removal notice naming the basket; grep which file holds the DELETE call). Discovery tab = one-line placeholder until F. Group deletion warns that coins move to the last group. **Forbidden:** `api/**`; e2e creates baskets through the real API (Playwright `request`).

**ACs.** AC-37 (lines, gaps, "membership as of today" line); AC-36 UI; AC-35/32 UI; AC-24 (no `0` for missing); AC-42; grep gate: no `trust_weight`, `triggered`, `confirmed` in `web/components/narrative`, `web/lib/*narrative*`, `web/lib/*/attention*`. **Tests.** Red-first: `pnpm --filter web test`, `tsc --noEmit`, `pnpm build:islands`, `pnpm test:e2e` (`PLAYWRIGHT_CHROMIUM_PATH`, `SCREENER_REFRESH_WORKER=0`). **Depends on:** A, C merged. **Cost:** 6-9 USD. **Reads (~34,000):** `NarrativeDashboard.tsx` 7,846; `SpaghettiChart.tsx` 6,075; `spaghetti-lines.ts` ~3,000; `use-simple-lines.ts` 2,198; `CoinGroup.tsx` ~4,000 of 8,685; `CoinActions.tsx` 4,431; `DeadDataNotice.tsx` 841; tokens ~3,000; `lib/api/narrative.ts` 2,175; `lib/types/narrative.ts` 4,731; `narrative.spec.ts` ~6,000 of 16,199. **Risk.** CI does not run e2e. **Rollback.** Revert PR.

## S-F: Discovery API and tab (RT2 + RT3)

**Owned.** `api/analytics/attention/discovery.py`, `api/models/discovery.py`, `api/routers/discovery.py` (GET `/api/narrative/discovery?window=7|30|90`, enum), `api/data/discovery.json` (volume floor, exclusion lists), `api/main.py` (one line), tests `api/tests/analytics/attention/test_discovery.py`, `api/tests/routers/test_discovery.py`; web `web/components/narrative/Discovery*.tsx` (+ tests), `web/lib/{api,types}/discovery.ts`, tab wiring in `NarrativeTabs.tsx`, e2e cases. **Forbidden:** B, C files (read only).

**Method (AC-41).** C's top-100 list minus exchange tokens (config + category tags) minus 24h volume under the floor (about 20M USD). Per coin 7d vs 30d per source from the store; "gaining" iff at least 2 independent sources rise; contribution winsorized at the 95th percentile; category score = mean, median beside it, `coins_used`. A coin counts in each of its CoinGecko categories; no cross-category total. Ranked by category momentum.

**ACs.** AC-40, AC-41 (each rule tested), AC-24, AC-42. **Depends on:** C, E merged. **Cost:** 5-7 USD. **Reads (~27,000):** `coingecko_adapter.py` 3,804; B1 `coingecko_attention`/`store` ~5,000; C `universe/rank` ~4,000; `NarrativeTabs.tsx` ~3,000; `BasketTable.tsx` ~3,000; tokens ~3,000; a router test ~4,000. **Rollback.** Revert PR.

## S-G: live probes on the owner PC

No agent can run these. Per signal the owner records in `api/data/attention/probe_records.json` and the task folder (AC-34): reachable; history depth (90 days); per-coin; refetchable for 100 coins; comparable across coins; personal-use terms. X also: dry-run estimate vs one capped real run, spam sample, real USD per 100 reads; key only in the owner's private environment outside git. After probes pass the owner schedules `refresh_attention.py`. Order: Wikipedia, exchange volume, CoinGecko, Google Trends, Reddit (if keys), X last. Agent part (wave 3): `api/scripts/record_probe.py` + `api/tests/scripts/test_record_probe.py`, 1-2 USD. No record = "unavailable".

## Waves and cost (max 2 concurrent workers)

| Wave | Slices | Why |
|---|---|---|
| 1 | A, B1 | disjoint; `api/main.py` only in A |
| 2 | C, B2 | C needs A, B1; B2 needs B1; disjoint |
| 3 | E, then D; G script | E needs A, C; D merges after E |
| 4 | F | needs C, E |
| any | G probes | owner PC; gate which sources feed scores |

USD (reading-based; recent slices ran 1-4 USD, so an upper bound): A 3-4, B1 4-6, B2 4-6, C 4-6, D 5-8, E 6-9, F 5-7, G script 1-2 = 32-48 (mid 40). 106 + 32-48 = 138-154 vs 160.

## Risks

R1 unprobed sources: tabs thin until G. R2 reference ranks need `refresh_attention.py` run on the PC. R3 old stack more entangled than read (D stop rule). R4 estimates from reading. R5 X cost drift (caps, default off). R6 groups coupled to the board. R7 UI judged by eye (screenshot gate). R8 Windows paths verifiable only on the PC. R9 X feeds no score for about 90 days.

## Validate contract

_Placeholder. `vc-validate-agent` writes this section (V1-V7) before EXECUTE; do not start EXECUTE with it empty. Run `validate-plan-artifact.mjs` (RT0). Not opened yet: `seed_e2e_cache.py`, `globals.css`, `.github` workflows, `web/lib/__tests__/screener-api.test.ts`._

## Planner checklist (after merge)

Register slices in MASTER-PLAN; fix docs naming removed symbols (`all-context.md`, `all-tests.md`, `all-data-sources.md`); decision entry D-1/D-3; update SPEC split note; note the legacy `coingecko/{category}` series freeze when `trigger.py` goes.
