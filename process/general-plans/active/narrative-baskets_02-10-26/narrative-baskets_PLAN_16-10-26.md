---
name: plan:narrative-baskets-wave-programme
description: "COMPLEX wave programme for P5 narrative baskets after the owner decisions of 16-10-26: baskets over screener groups, attention-momentum pipeline, My baskets tab, Discovery tab, retire verdict code, live probes. Slices A-G."
date: 16-10-26
feature: narrative-baskets
metadata:
  node_type: memory
  type: plan
---

# Narrative Baskets: Wave programme (slices A-G)

**Complexity:** COMPLEX (7 slices, 4 waves). **SPEC:** `narrative-baskets_SPEC_02-10-26.md` + `narrative-baskets_SPEC-amendment_16-10-26.md` (A6 wins). **Status:** PLANNED, not validated. Written 16-10-26 from `main` at 38bb43e; no code run or edited. Replaces the earlier A-D draft (price lines and multi-basket membership dropped).

## Overview

Order: baskets (screener side), attention pipeline, "My baskets" tab, then Discovery; live probes on the owner PC run alongside. "Momentum" = mindshare momentum, never price. Python computes every number, the web renders it, unavailable data is an explicit state, never 0.

## Decisions for the owner

**D-1 Baskets = screener groups (recommended) or a separate `baskets.json`.** Read on main: `api/data/layout.py` + `api/models/layout.py` store named groups per section (`crypto`) in `layout.json`. Rules: one coin in one group only, names 1-40 chars unique ignoring case, max 12 groups, atomic write, revision check, every read reconciles to the watchlist (removed coin vanishes: `drop_coin`), `place_coin` moves a coin. So groups ARE named one-membership lists. Recommendation: REUSE; every group except default `main` is a basket; `main` is shown "Unassigned", never scored.
- Gains: no new store, CRUD or cascade; editing stays where the owner arranges coins; slice A costs 3-4 USD.
- Loses/changes: renaming or deleting a group also changes the screener board; 12-basket cap; a coin is always in some group (Main = no basket); AC-32 notice needs the group name added to the removal response.
- Fallback: `api/data/baskets.json` (env `SCREENER_BASKETS_PATH`, watchlist pattern) with own CRUD and cascade, about +3 USD in A. B-G read baskets only via `api/data/baskets_view.py`, so the store is swappable.

**D-2 Spend.** Ceiling 160 USD, used about 106; programme 33-50 (mid 41), projected 139-156. Ask point 7 USD, cap 15 USD per slice.

**D-3 Percentile universe.** Ranking 5-30 screened coins among themselves is noisy. Recommend: rank within the Discovery universe (top 100 after AC-41 filters) for sources fetchable for all 100 (Wikipedia, exchange volume, CoinGecko); Google Trends and X are fetched for screened coins only, ranked within them and flagged "small universe". Alternative: screened coins only (cheaper, weaker).

**D-4 Defaults.** Windows 7/30/90, default 30. Weights 1/n over available sources (X lower, config). A source with under 90 days for a coin gives "insufficient history", not a partial ratio. `/history`, `/mindshare` stay as raw APIs; `narrative_config.py`, archived parquet, `narratives.json`, `narrative_categories.json` are kept.

## Common rules

- Worker branch `claude/<task-id>-<slug>`, PR to main. Red-first: failing tests committed first (report heading 6). Baselines measured on untouched origin/main (all-tests.md counts are stale).
- Store tests redirect `watchlist.DEFAULT_WATCHLIST_PATH`, `SCREENER_LAYOUT_PATH` and any new path to `tmp_path`; never `monkeypatch.undo()` with `isolated_cache`; prove no real file changed (size, mtime, sha256). Cache tests cross the real cache boundary under `isolated_cache`.
- Providers are unreachable from the sandbox: adapters tested on fixtures only, no claim about live behaviour. A signal without a probe record is `unavailable` and feeds no score (AC-34).
- Protected, unedited and green everywhere (AC-25): `api/tests/data/test_pytrends_adapter.py`, `api/tests/scripts/test_snapshot_narrative.py`, `api/tests/scripts/test_snapshot_workflow_schedules.py`, `api/tests/scripts/test_backfill_pytrends_history.py`; `git diff --stat origin/main -- <paths>` empty.
- Forbidden for all: CLAUDE.md, AGENTS.md, `process/**` except the report, `.github/**`, any `.env` or key file, `api/data/pytrends_adapter.py` (wrap, never edit), `api/scripts/snapshot_narrative.py`, `api/analytics/narrative/{narrative_config,exchange_attention}.py`.
- No secret in files, fixtures, commits, prompts or logs.
- Worker read set: CLAUDE.md 13,443 + envelope <= 4,000 + Common rules + its slice (<= 6,000 each) + source ranges <= 35,000 B (sizes below measured from the repo listing, `~` = range estimate). A CLAUDE.md or AGENTS.md diff stops at `review`. Spend per slice in heading 6.

## S-A: baskets view over screener groups (RT2)

**Owned.** `api/data/baskets_view.py`, `api/routers/baskets.py` (GET `/api/narrative/baskets`), `api/routers/watchlist.py` (DELETE adds `affected_baskets`, `[]` if none), `api/main.py` (one `include_router` line), new tests `api/tests/data/test_baskets_view.py`, `api/tests/routers/{test_baskets,test_watchlist_cascade}.py`, one assertion in `api/tests/routers/test_watchlist.py::test_remove_coin`. **Forbidden:** `api/data/{layout,watchlist}.py` (use public functions; need a change = `needs_input`), `api/analytics/**`, `web/**`.

**ACs.** AC-35 (move via `place_coin`/layout save; response names the old basket); AC-32 (remove a coin held by a basket: basket updated, `affected_baskets` names it; coin only in `main`: `[]`); AC-27 (non-screener coin refused: "<SYM> is not on your screener. Add it to the screener first.", file bytes unchanged); AC-9 (create, rename, edit, delete via layout API, survives reload); `main` never returned as a basket; watchlist cap/404 tests green. **Tests (FA, red-first).** About 20; write via router, re-read file.
**Depends on:** none. **Cost:** 3-4 USD (fallback 6-8). **Reads (~25,300):** `layout.py` 11,719; `models/layout.py` ~1,800; `routers/watchlist.py` 2,310; `watchlist.py` ~2,500; `main.py` ~1,000; `tests/routers/test_layout.py` <= 6,000 (size unmeasured). **Risk.** Group edits move the board (accepted, D-1). **Rollback.** Revert PR; no data migrated.

## S-B: attention source adapters (RT2, fixtures)

**Owned.** New `api/data/attention/{__init__,types,wikipedia,xsearch,trends,exchange_volume,coingecko_attention,reddit}.py`, `api/data/wiki_articles.json` (coin-to-article map for the top 100 + screener coins; gap = `no-article`), `api/data/attention/probe_records.json` (`{}` until G), tests `api/tests/data/attention/`, fixtures `api/tests/fixtures/attention/`. **Forbidden:** edits to the existing adapters (wrap `pytrends_adapter`, `coingecko_adapter`, `reddit_adapter`, `hyperliquid_narrative_adapter`, `ccxt_adapter`), A files.

**Contract.** Each adapter returns `SourceSeries(source, symbol, points[(date, value)], state, reason)`, state in `ok | unavailable | insufficient-history | no-article | capped | not-probed`. Wikipedia: pageviews per article, daily, 90+ days. Trends: existing wrapper, per-coin term (per-request 0-100 scale, anchor-chained as today; comparability decided in G). Exchange volume: Hyperliquid and Binance (quote volume). CoinGecko: market data, categories, trending presence. Reddit: `unavailable` without keys. The reader returns `not-probed` for any source with no row in `probe_records.json`.

**X (AC-38).** Token only from env `X_BEARER_TOKEN`; never logged, never in an exception message or `repr`. Config `X_MAX_READS_PER_RUN`, `X_MAX_READS_PER_DAY`, USD per read; the day counter lives under the cache dir (outside git). At a cap: stop, state `capped`. Dry-run/estimate: zero network calls, reports planned reads and USD. Screened coins only; weight below other sources; flagged for bot and cashtag spam. Tests: both caps; dry run with a network stub that fails if called; log capture without the token; repo scan for a token value.

**ACs.** AC-34, AC-24 (states, never 0), AC-38, AC-39. **Tests (FA, red-first).** About 45 fixture tests per source (ok, empty, short history, HTTP error, rate limit). **Depends on:** none (wave 1 with A). **Cost:** 6-9 USD; if over 12, split X into B2. **Reads (~30,000):** `pytrends_adapter.py` ~6,000 of 10,264; `coingecko_adapter.py` 3,804; `reddit_adapter.py` 5,437; `hyperliquid_narrative_adapter.py` 4,724; `exchange_attention.py` ~4,000 of 7,596; `cache.py` ~6,000 of 28,762. **Risks.** Wrong article mapping (reviewable JSON, explicit state); X cost drift (caps are code); provider terms (G). **Rollback.** Revert PR.

## S-C: coin and basket scoring, API (RT2)

**Owned.** `api/analytics/attention/{ratio,rank,score,basket,series}.py`, `api/models/attention.py`, `api/routers/attention.py` (GET `/api/narrative/baskets/attention?window=7|30|90`), `api/main.py` (one line), `api/config/attention_weights.json`, tests `api/tests/analytics/attention/`, `api/tests/routers/test_attention.py`. **Forbidden:** A, B files, `web/**`.

**Method (AC-36).** Per coin and source: ratio = mean(last 7 daily)/mean(last 90 daily); rank = percentile within the universe (D-3), ties averaged. Coin score = weighted mean of available ranks (weights renormalised), `sources_used n of N`. Basket score = equal mean of member scores; breadth = share of members whose score at d exceeds d-7; coverage "covers N of M". Series: score per day using data to that day, rebased to 100 at window start; gap where no coin has data. Payload per basket: `score, change, breadth, coverage, series[], coins[{symbol, score, sources[{source, raw, ratio, rank, state}]}], status, reason, universe_size`. No cross-basket total; the table order key is `change`.

**ACs.** AC-36, AC-37 (API half), AC-24, AC-35. Hand-computed tests: 2 baskets x 3 coins x 3 sources; a missing source (score from 2, "2 of 3"); a dominant coin (score high, breadth 1/3); all missing (`no-data`, empty series, no zero). **Depends on:** A, B merged. **Cost:** 5-7 USD. **Reads (~17,500):** `baskets_view.py` ~2,500; B `types.py` ~2,000; `freshness.py` 3,845; `screener_board.py` ~3,000; `routers/screener.py` 2,091; one router test ~4,000. **Risks.** Small-universe percentiles (flagged in payload); missing 90-day history (state). **Rollback.** Revert PR.

## S-D: retire the old verdict code (RT3)

**Owned.** Delete `api/analytics/narrative/{trigger,mapping,momentum}.py`, `api/data/narrative_category_map.json`, tests `api/tests/analytics/{test_narrative_trigger,test_mapping}.py`, `api/tests/analytics/narrative/{test_trigger_tripwire,test_momentum}.py`, `api/tests/routers/{test_narrative_categories_contract,test_narrative_momentum}.py`. Edit `api/routers/narrative.py`, `api/models/narrative.py`, `api/analytics/narrative/{history,scoring}.py` (history owns its two constants, drops composite `trust_weight`), `api/tests/analytics/test_no_verdict_symbols.py`, `api/tests/analytics/narrative/test_narrative_v2_boundaries.py`, `api/tests/routers/{test_narrative,test_narrative_history}.py`, `api/tests/analytics/test_history.py`, `api/scripts/seed_e2e_cache.py` + `api/tests/scripts/test_seed_narrative_fixture.py` (narrative seeding only). New `api/tests/analytics/test_no_narrative_verdict_fields.py`. **Forbidden:** common list, A-C files, `web/**`.

**Method.** First, list every importer of `trigger`, `mapping`, `scoring`, `narrative_config` with `git grep` (report heading 4). If `snapshot_narrative.py` or a protected guard needs a symbol, keep it and stop `needs_input`. Delete, repair imports, run all.

**ACs.** AC-11 (guard test committed red first: no `triggered/confirmed/trust_weight` in `/history` or `/mindshare` shapes; `/categories` and `/momentum` return 404; source scan of `api/` finds none outside archived history); AC-25 (guards unedited and green; a test imports `snapshot_narrative` and `run_snapshot` resolves). Deleted tests listed with reasons. **Depends on:** A, C merged; merge after E. **Cost:** 6-10 USD (riskiest). **Reads (~34,000):** `routers/narrative.py` 5,000 of 8,074; `history.py` ~3,000 of 18,931; `scoring.py` 2,579; `trigger.py` ~1,500; `mapping.py` ~1,000; `momentum.py` ~1,500; `test_narrative_categories_contract.py` 4,583; `test_no_verdict_symbols.py` 2,953; `test_trigger_tripwire.py` ~2,000; `narrative_config.py` ~2,000; `test_narrative_v2_boundaries.py` ~2,500; `test_seed_narrative_fixture.py` ~2,000; `seed_e2e_cache.py` ~3,500 of 43,301. Larger importer list: split D1 (api source) / D2 (tests, seeder). **Risks.** Hidden importer on the nightly path (stop rule); page breaks if D lands before E (merge E first, no deploy between). **Rollback.** Revert PR; archived history files never touched.

## UI standard (E and F; AC-42)

Follow the existing conventions; the worker reads them first: `web/app/globals.css` (47 custom properties; use the tokens), the screener page `web/app/screener/` and `web/components/screener/{ScreenerBoard,CoinGroup,SpaghettiChart,DeadDataNotice,FreshnessStrip}.tsx` (island chart via `use-simple-lines`, legend toggles, gap notice). Per tab: short header with the 7d/30d/90d selector; chart first; compact ranked basket table (name, score, signed change, breadth, "covers N of M"); coins behind a basket expand (coin score, "n of N sources", raw value per source). One plain one-line label per number; no decorative badges; the chart legend doubles as the filter and is not repeated; gaps as one muted "no data" mark; restrained palette, type and spacing from tokens; empty (no baskets: one line and a link to the screener), loading and error states defined; checked at phone, tablet, desktop. Remove old trigger/confirmed/verdict clutter and the old keyword views from the page. **Acceptance gate:** before/after screenshots (three widths and each state) go in the PR; the planner or owner checks them before the slice is accepted. Green tests alone do not accept it.

## S-E: My baskets tab (RT3 + Playwright)

**Owned.** `web/components/narrative/**` (new `NarrativeTabs.tsx`, `BasketAttentionChart.tsx`, `BasketTable.tsx`, `BasketCoins.tsx`; edit `NarrativeDashboard.tsx`; delete the old views: `CategoryHistoryPanel`, `ComparisonView`, `ChangeInAttentionView`, `MomentumView`, `RedistributionBadge`, old `MindshareView`, `DataQualityCaveat` if unused) with `__tests__/**`; `web/lib/{api,types}/attention.ts`, `web/lib/attention-lines.ts`, trimmed `web/lib/{api,types}/narrative.ts`, `web/lib/narrative-view-model.ts`, `web/lib/narrative-panel-lines.ts`, `web/lib/__tests__/` narrative and attention files, `web/e2e/narrative.spec.ts`, `web/components/screener/CoinActions.tsx` + `web/lib/api/screener.ts` (removal notice only). Discovery tab = one-line placeholder until F. Basket editing stays in the screener groups UI. **Forbidden:** `api/**`; e2e creates baskets through the real API (Playwright `request`) on seeded coins.

**ACs.** AC-37 (lines, no comparative wording, gaps); AC-36 UI (raw beside headline, "n of N sources", breadth); AC-35/32 UI (move; notice naming the basket; none for Unassigned); AC-24 (every state; no `0` for missing); AC-42 (screenshots); web grep gate: no `trust_weight`, `triggered`, `confirmed` in `web/`. **Tests.** Red-first vitest and Playwright: `pnpm --filter web test`, `tsc --noEmit`, `pnpm build:islands`, `pnpm test:e2e` (`PLAYWRIGHT_CHROMIUM_PATH`, `SCREENER_REFRESH_WORKER=0`). **Depends on:** A, C merged. **Cost:** 7-10 USD. **Reads (~33,000):** `NarrativeDashboard.tsx` 7,846; `SpaghettiChart.tsx` 6,075; `spaghetti-lines.ts` ~3,000; `use-simple-lines.ts` 2,198; `CoinGroup.tsx` ~4,000; `CoinActions.tsx` ~2,500; `DeadDataNotice.tsx` 841; `globals.css` tokens ~3,000; unmeasured `lib/api/narrative.ts`, `lib/types/narrative.ts`, `e2e/narrative.spec.ts` capped 8,000. **Risks.** Chart island build; CI does not run e2e; remove-control location unverified. **Rollback.** Revert PR.

## S-F: Discovery API and tab (RT2 + RT3)

**Owned.** `api/analytics/attention/{discovery,universe}.py`, `api/models/discovery.py`, `api/routers/discovery.py` (GET `/api/narrative/discovery?window=7|30|90`), `api/config/discovery.json` (volume floor, exclusion lists), `api/main.py` (one line), tests `api/tests/analytics/attention/test_discovery.py`, `api/tests/routers/test_discovery.py`; web `web/components/narrative/Discovery*.tsx` (+ tests), `web/lib/{api,types}/discovery.ts`, tab wiring in `NarrativeTabs.tsx`, e2e cases. **Forbidden:** B, C files (read only).

**Method (AC-41).** Universe: top 100 by market cap (CoinGecko) minus stablecoins, wrapped/staked duplicates, exchange tokens (config lists + category tags), minus 24h volume under the floor. Per coin 7d vs 30d per source; "gaining" iff at least 2 independent available sources rise; contribution winsorized at the 95th percentile; category score = mean with median beside it and `coins_used`. A coin in several CoinGecko categories counts in each; no cross-category total. Ranked by category momentum; raw values and gaps as in C.

**ACs.** AC-40, AC-41 (each rule tested), AC-24, AC-42. **Depends on:** C, E merged. **Cost:** 5-8 USD. **Reads (~27,000):** `coingecko_adapter.py` 3,804; B `coingecko_attention.py` + `types.py` ~5,000; C `ratio.py`/`rank.py` ~4,000; `NarrativeTabs.tsx` ~3,000; `BasketTable.tsx` ~3,000; tokens ~3,000; a router test ~4,000. **Risks.** Noisy public category tags (shown with `coins_used`); CoinGecko rate limits (G). **Rollback.** Revert PR.

## S-G: live probes on the owner PC

No agent can run these. Per signal, the owner records in `api/data/attention/probe_records.json` and the task folder (AC-34): reachable; history depth (need 90 days); per-coin or per-keyword; refetchable; comparable across coins; personal-use terms. X also: dry-run estimate vs one capped real run, bot/cashtag spam sample, real USD per 100 reads; the key is set only in the owner's private environment outside git. Order: Wikipedia, exchange volume, CoinGecko, Google Trends (per-coin comparability), Reddit (if keys), X last. Agent part (wave 3): `api/scripts/record_probe.py` + `api/tests/scripts/test_record_probe.py` only, 1-2 USD. Until a record exists the source shows "unavailable"; tabs work on the rest.

## Waves and cost (max 2 concurrent workers)

| Wave | Slices | Concurrent | Why |
|---|---|---|---|
| 1 | A, B | 2 | disjoint globs; `api/main.py` only in A |
| 2 | C | 1 | needs A and B |
| 3 | E, D + G script | 2 | web vs api, disjoint; merge E before D, no deploy between |
| 4 | F | 1 | needs C and E |
| any | G probes | owner PC | gate which sources feed scores |

USD (reading-based, not measured): A 3-4, B 6-9, C 5-7, D 6-10, E 7-10, F 5-8, G script 1-2 = 33-50 (mid ~41). 106 + 33-50 = 139-156 vs 160: tight at the top end. The planner re-checks spend after waves 2 and 3 and stops for the owner above 150.

## Risks

R1 unprobed sources: tabs ship thin until G. R2 small-universe percentiles (D-3). R3 old stack more entangled than read (D stop rule). R4 estimates from reading. R5 X cost drift (caps, dry run). R6 groups coupled to the board (D-1). R7 UI judged by eye (screenshot gate). R8 Windows paths/deploy verifiable only on the PC.

## Validate contract

_Placeholder. `vc-validate-agent` writes this section (V1-V7) before EXECUTE; do not start EXECUTE with it empty. Run `validate-plan-artifact.mjs` on this file (RT0). Open validator questions: D-1 and D-3 answers; importer list for D; sizes of `lib/api/narrative.ts`, `lib/types/narrative.ts`, `e2e/narrative.spec.ts`, `tests/routers/test_layout.py`._

## Planner checklist (after merge)

Register slices in MASTER-PLAN; fix docs naming removed symbols (`all-context.md`, `all-tests.md`, `all-data-sources.md`); decision entry for D-1/D-3; update SPEC split note; note the legacy `coingecko/{category}` series freeze when `trigger.py` goes.

## Not verified

No code run or searched (Bash unavailable); importer lists come from reading. `~` sizes are estimates, others exact. `globals.css` and the screener page were only listed, not opened; E/F workers read them first.
