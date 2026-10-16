---
name: plan:narrative-baskets-a-d
description: "COMPLEX plan for P5 narrative baskets, slices A-D only: baskets store and CRUD, basket performance endpoint, retire old verdict code, web editor and spaghetti view 1. E, F, G are the next plan."
date: 16-10-26
feature: narrative-baskets
metadata:
  node_type: memory
  type: plan
---

# Narrative Baskets: Plan (slices A-D)

**Complexity:** COMPLEX (4 slices, 3 waves). **SPEC:** `narrative-baskets_SPEC_02-10-26.md` (same folder). **Decision:** D-4. **Status:** PLANNED, not validated. Written 16-10-26 by a plan writer from `main` at 38bb43e; no code edited.

## Overview

Owner decision 16-10-26: build slices A-D now. A baskets store + CRUD + coin-must-be-on-screener + cascade on screener removal (AC-9, 27, 31, 32). B daily basket performance (AC-30, 31). C retire the old verdict code (AC-11, AC-25 protected). D web editor + view 1 chart with explicit gap states (AC-9, 24, 27, 28, 30, 31, 32 UI half).

**Next plan, NOT here:** E mindshare API (AC-29, 33, 34 exclusion), F mindshare view, G live probes on the owner PC (AC-34). Until E/F, the old keyword mindshare view stays on the page (assumption A8).

**Facts read on main (grounding).** Watchlist = JSON file, call-time path, env `SCREENER_WATCHLIST_PATH`, 30-coin cap (`api/data/watchlist.py`). `DELETE /api/watchlist/{symbol}` returns `{"coins": [...]}` and `tests/routers/test_watchlist.py::test_remove_coin` asserts exactly that. Spaghetti today: `screener_board.build_spaghetti` (% change from 0, per coin). Old narrative stack: `trigger.py` (triggered/confirmed/trust_weight, also writes legacy `coingecko/{category}`), `mapping.py`, `scoring.py`, `history.py` (imports `trigger` for `MIN_AVAILABLE_SOURCES`, `BASE_TRUST_WEIGHT`; emits composite `trust_weight`), `momentum.py` (direction/trend labels), routes `/categories`, `/history`, `/momentum`, `/mindshare`. Nightly archive `api/scripts/snapshot_narrative.py` imports only `narrative_config`, `exchange_attention`, adapters and `cache`; it never imports `trigger`/`mapping`.

## Assumptions the owner may override

- A1 Basket storage = JSON file `api/data/baskets.json` (gitignored like `watchlist.json`; env `SCREENER_BASKETS_PATH`), same pattern as the watchlist. Rejected: a database table.
- A2 Windows 7d / 30d / 90d, default 30d (OQ-17), daily points.
- A3 Cascade on screener coin removal confirmed (OQ-16); a basket left empty stays, with an explicit empty state.
- A4 No extra views beyond view 1 (OQ-11).
- A5 Basket names: free text, trimmed, 1-40 chars, unique ignoring case; ids are opaque (`b-` + 8 hex). No basket-count cap.
- A6 `DELETE /api/watchlist/{symbol}` gains an additive field `affected_baskets` (list of names; `[]` if none). One existing assertion in `test_watchlist.py` is updated.
- A7 `/api/narrative/momentum` is removed with `momentum.py` (its direction/trend labels are state labels under AC-11). `/history` keeps raw series; its composite loses `trust_weight`. Numeric rank fields stay API-side until plan E rewrites `/history`.
- A8 Old keyword `MindshareView` and `/mindshare` stay mounted and unchanged until E/F (D audits it for zero-fill only).
- A9 Archived history files (parquet under the cache, `narratives.json`, `narrative_categories.json`) are kept. The legacy `coingecko/{category}` series stops growing when `trigger.py` goes.
- A10 Basket coin symbols reuse `watchlist.normalize_symbol`; membership is checked against `read_watchlist()` at write time.

## Slice index (a worker reads CLAUDE.md, its envelope, Common rules and ITS slice heading only)

Common rules; S-A; S-B; S-C; S-D; Waves and cost; Risks; Validate contract.

## Common rules

- Worker branch `claude/<task-id>-<slug>`, PR to main. Retry rules, no-re-run rule: `operating-instructions.md` (named in the envelope only if needed).
- Red-first: each slice's tests are committed failing first (record in report heading 6), then the code.
- Python is the single source of numbers; the web renders them (SPEC constraint). Unavailable data is an explicit state, never 0, NaN or silently dropped.
- Tests touching stores follow all-tests.md lessons 3, 9, 10: redirect BOTH `watchlist.DEFAULT_WATCHLIST_PATH` and the baskets path to `tmp_path`, never `monkeypatch.undo()` with `isolated_cache`, and prove no real file changed (size, mtime, sha256 before and after).
- Baselines are MEASURED on untouched origin/main by the worker before editing (all-tests.md lists 873 passed at 753db23 but main has moved; do not trust it).
- Protected guards that MUST stay green and unedited in every slice (AC-25): `api/tests/data/test_pytrends_adapter.py` (partial-hour cases), `api/tests/scripts/test_snapshot_narrative.py`, `api/tests/scripts/test_snapshot_workflow_schedules.py`, `api/tests/scripts/test_backfill_pytrends_history.py`. Check with `git diff --stat origin/main -- <paths>` (empty) and a green run.
- Forbidden for all slices: CLAUDE.md, AGENTS.md, `process/**` except the report, `.github/**`, `api/data/pytrends_adapter.py`, `api/scripts/snapshot_narrative.py`, `api/analytics/narrative/{narrative_config,exchange_attention}.py`.
- Worker set cap 36,000 B: CLAUDE.md 13,443 + envelope <= 4,000 + this plan's slice and Common rules (<= 6,000 each). Source reads below are extra, on demand, <= 35,000 B per slice.
- Any CLAUDE.md or AGENTS.md diff stops at `review`. Spend is reported per slice in heading 6.

## S-A: baskets store, CRUD router, screener membership, cascade (RT3)

**Objective.** Persist user baskets; refuse non-screener coins; cascade a screener removal into all baskets, enforced by the API.

**Owned.** `api/data/baskets.py` (new), `api/models/baskets.py` (new), `api/routers/baskets.py` (new), `api/routers/watchlist.py` (edit), `api/main.py` (one `include_router` line), `api/tests/data/test_baskets_store.py`, `api/tests/routers/test_baskets.py`, `api/tests/routers/test_watchlist_cascade.py` (all new), `api/tests/routers/test_watchlist.py` (the one `test_remove_coin` assertion), `.gitignore` (one line, `api/data/baskets.json`). **Forbidden:** `api/data/watchlist.py` (use its public API), `api/analytics/**`, `api/routers/narrative.py`, `web/**`.

**Design.** File `{"version":1,"baskets":[{"id","name","coins":[...]}]}`; call-time path resolve; lock around read-modify-write; atomic write (temp + replace). Routes under `/api/narrative/baskets`: `GET`, `POST {name, coins}`, `PUT /{id} {name, coins}`, `DELETE /{id}`. Coin not on the screener: 422, detail `"<SYM> is not on your screener. Add it to the screener first."`, basket unchanged. Unknown id 404. Duplicate coins deduped, order kept. Cascade in `DELETE /api/watchlist/{symbol}`: confirm the coin is on the watchlist (else the existing 404), remove it from every basket (collect names), then remove it from the watchlist; return `affected_baskets`. Layout upkeep stays best effort as today.

**ACs.**
- AC-9 (pytest): create, rename, edit coins, delete; survives a reload of the store file; no file editing needed.
- AC-27: screener coin accepted; non-screener coin rejected with the message above and the file bytes unchanged; free-text names accepted; empty basket allowed.
- AC-31: one coin in two baskets; both keep it; no cross-basket total in any payload.
- AC-32: remove a coin held by two baskets: both updated, `affected_baskets` lists both, invariant (every basket coin is on the watchlist) holds; coin in no basket: `affected_baskets == []`, baskets file untouched; empty basket stays.
- Existing watchlist cap and 404 tests still green.

**Tests (red-first, FA).** About 30 tests across the three new files. Boundary test: write via the router, read the file back, reload. Isolation proof per Common rules.

**Dependencies.** None. **Cost.** 4-6 USD. **Read list (bytes measured from the repo listing):** `api/data/watchlist.py` 5,228; `api/routers/watchlist.py` 2,310; `api/main.py` 4,248; `api/tests/routers/test_watchlist_cap.py` 6,759; `api/tests/routers/test_watchlist.py` 1,826 = 20,371 (plus the `isolated_cache` fixture lines of `api/tests/conftest.py`, size not measured, range <= 2,000). **Risks.** Two files cannot be changed atomically: order above makes a failed second write retry-safe. **Rollback.** Revert the PR; `baskets.json` is local data and can be deleted.

## S-B: basket performance endpoint (RT2)

**Objective.** `GET /api/narrative/baskets/performance?window=7|30|90` (default 30): one entry per basket.

**Owned.** `api/analytics/baskets_performance.py`, `api/models/baskets_performance.py`, `api/routers/baskets_performance.py`, `api/main.py` (one line, after A merged), `api/tests/analytics/test_baskets_performance.py`, `api/tests/routers/test_baskets_performance.py` (all new). **Forbidden:** all S-A files, `api/analytics/screener_board.py` (read-only reuse of its reason mapping and freshness helpers; no edit), `web/**`.

**Method (locked by SPEC AC-30).** Daily completed bars from the cache (`fetch_ohlcv(symbol, "1d")` under `reads_cache_only_if_running()`, as the screener router does); the partial current-day bar is excluded. End date E = latest completed daily bar among the basket's coins; start S = E minus (window - 1) days. A coin is covered iff it has a positive close on S; each day's value = mean over covered coins with a close that day of `close / close_S * 100`, equal weight, no market-cap weighting. Each point carries `n` (coins used that day). Entry: `id, name, coins_total (M), coins_covered (N), missing [{symbol, reason: "no-ohlcv"|"insufficient-history"|"source-unavailable"}], points [{date, value, n}], status "ok"|"no-data", reason`. The UI string "covers N of M" is rendered from N and M. Zero covered: `status "no-data"`, `points []`, never zeros. Empty basket: `no-data` with reason `empty-basket`.

**ACs.**
- AC-30 (hand-computed, window 3 days): closes X 100,110,121; Y 50,50,100; Z 200,180,160. Full coverage: 100, 100, 133.6667 (day 3 is (121+200+80)/3). Z with a start gap (short history): covers 2 of 3, missing `[Z]`, day 3 = (121+200)/2 = 160.5. Z no OHLCV: same values, reason `no-ohlcv`. Zero coverage: `no-data`.
- AC-31: a coin in two baskets appears in both computations; no summed or ranked cross-basket field.
- AC-28 API half: one entry per basket, daily points, first value exactly 100.
- AC-24 API half: missing coin named, adapter status mapped to a reason, no NaN or null in `value`.

**Tests (red-first, FA).** Pure function tests on frames; router test through the real cache boundary (write OHLCV with `cache.write_ohlcv` under `isolated_cache`, read via the endpoint; all-tests.md lesson 5); window validation 422. **Dependencies.** S-A merged. **Cost.** 4-6 USD. **Read list:** `screener_board.py` ranges (`_reason_for`, `_spaghetti_line`, `build_spaghetti`) ~5,500 of the file; `api/data/baskets.py` (from A) ~4,000; `api/routers/screener.py` 2,091; `api/data/freshness.py` 3,845; `api/tests/routers/test_spaghetti.py` 9,814 = ~25,250. **Risks.** Daylight and UTC day boundaries (use UTC dates, ADR-6); forward-fill is deliberately not done (a missing day lowers `n`, shown). **Rollback.** Revert the PR.

## S-C: retire the old verdict code (RT3)

**Objective.** AC-11: `triggered`, `confirmed`, `trust_weight`, state labels and the `/categories` contract are gone from api source and tests; AC-25 untouched.

**Owned.** Delete: `api/analytics/narrative/{trigger,mapping,momentum}.py`, `api/data/narrative_category_map.json`, tests `api/tests/analytics/{test_narrative_trigger,test_mapping}.py`, `api/tests/analytics/narrative/{test_trigger_tripwire,test_momentum}.py`, `api/tests/routers/{test_narrative_categories_contract,test_narrative_momentum}.py`. Edit: `api/routers/narrative.py`, `api/models/narrative.py`, `api/analytics/narrative/history.py` (own the two constants it took from `trigger`, drop composite `trust_weight`), `api/analytics/narrative/scoring.py` (audit: keep only pure normalisation used by `history`/`mindshare`, drop anything else; delete `test_scoring.py` cases of removed code only), `api/tests/analytics/test_no_verdict_symbols.py` (drop the `mapping.py` allow-list entry), `api/tests/analytics/narrative/test_narrative_v2_boundaries.py`, `api/tests/routers/{test_narrative,test_narrative_history}.py`, `api/tests/analytics/test_history.py`, `api/scripts/seed_e2e_cache.py` and `api/tests/scripts/test_seed_narrative_fixture.py` (old narrative seeding; also its `NarrativeStrip` allow-listed token). New: `api/tests/analytics/test_no_narrative_verdict_fields.py`. **Forbidden:** common list, all S-A/S-B files, `web/**`.

**Method.** First step (report heading 4): list every importer of `trigger`, `mapping`, `scoring`, `narrative_config` with `git grep` (this plan could not run a code search; the list above is from reading files). If `snapshot_narrative.py` or any protected guard needs a symbol, keep it and stop with `needs_input` instead of editing the guard. Then delete, then repair imports, then run everything.

**ACs.**
- AC-11 (new guard test): response-shape tests on `/history` and `/mindshare` contain none of `triggered`, `confirmed`, `trust_weight`; `/categories` and `/momentum` return 404; a source scan of `api/` finds none of the three tokens, nor `trigger.py`, outside archived history (allow-list empty). Docs and `web/` are covered by S-D and the UPDATE PROCESS checklist.
- AC-25: the four protected guards unedited and green; `snapshot_narrative.py` unedited; a test imports it and checks `run_snapshot` still resolves with `trigger` gone.
- No other test changes behaviour: the diff of deleted tests is listed in the report with the reason per file.

**Tests (red-first).** The new guard test is committed first (red), turns green after deletion. **Dependencies.** S-A merged (the plan order); runs in parallel with S-B (disjoint). **Cost.** 8-12 USD (largest and riskiest). **Read list (ranges, ~34,100 B):** `routers/narrative.py` ranges 5,000 of 8,074; `history.py` trigger/trust references ~3,000 of 18,931; `scoring.py` 2,579; `trigger.py` header and constants ~1,500 of 11,807; `mapping.py` ~1,000 of 6,314; `momentum.py` header ~1,500 of 8,828; `test_narrative_categories_contract.py` 4,583; `test_no_verdict_symbols.py` 2,953; `test_trigger_tripwire.py` ~2,000 of 4,246; `narrative_config.py` ~2,000 of 7,893; `test_narrative_v2_boundaries.py` ~2,500 of 4,975; `test_seed_narrative_fixture.py` ~2,000 of 4,611; `seed_e2e_cache.py` narrative ranges ~3,500 of 43,301. **If the worker exceeds the read cap or the importer list is larger than listed:** split into C1 (api source) and C2 (tests and seeder) by a new envelope, same ownership split. **Risks.** R-C1 hidden importer breaks the nightly path; R-C2 seeder (43 KB) coupling; R-C3 the live page degrades between C and D (momentum error notice, possible render crash on missing `trust_weight`). Mitigation for R-C3: deploy to the PC is manual (`deploy/build-web.ps1`); do not deploy between C and D. **Rollback.** Revert the PR; the deleted data file and code return from git; no archived history file is touched.

## S-D: web editor and view 1 (RT3 + Playwright)

**Objective.** `/narrative` becomes: basket editor, then view 1 (basket spaghetti), then the old mindshare view unchanged (A8). Old history/comparison/change/momentum panels are removed.

**Owned.** `web/components/narrative/**` (new `BasketEditor.tsx`, `BasketSpaghettiChart.tsx`; delete `CategoryHistoryPanel`, `ComparisonView`, `ChangeInAttentionView`, `MomentumView`, `RedistributionBadge`, and `DataQualityCaveat` if unused; edit `NarrativeDashboard.tsx`) with `__tests__/**`, `web/lib/api/baskets.ts`, `web/lib/types/baskets.ts`, `web/lib/baskets-lines.ts` (new), `web/lib/api/narrative.ts`, `web/lib/types/narrative.ts`, `web/lib/narrative-view-model.ts`, `web/lib/narrative-panel-lines.ts` (trim or delete), `web/lib/__tests__/` narrative and baskets files, `web/e2e/narrative.spec.ts`, the screener remove-coin control (`web/components/screener/CoinActions.tsx`, confirm by reading) and `web/lib/api/screener.ts` with their tests. **Forbidden:** `api/**`, Python seeders (e2e creates baskets through the real API with Playwright `request`, on the existing seeded screener coins).

**Design.** Reuse `SpaghettiChart` structure (island via `use-simple-lines`, legend toggles, `DeadDataNotice`) and `AddCoinForm` patterns. Lines are plotted from the API values rebased to 100; no client maths. Window switch 7/30/90, default 30. Per basket: "covers N of M coins" and missing coins with reason; `no-data` and empty states are text, never a flat line. No wording that ranks or labels ("outperforming", "rising", "hottest"). Editor: name field, coin picker listing only current screener coins, server 422 message shown verbatim. After a screener removal the control shows "Also removed from: <names>" from `affected_baskets`.

**ACs.**
- AC-9 (Playwright CRUD flow), AC-27 (UI refusal of a non-screener attempt, message rendered), AC-31 (two baskets sharing a coin, both lines render).
- AC-28: vitest chart render (line count, no comparative wording, empty and insufficient states); Playwright lines render after create, edit, delete. Readability by eye: HY, owner looks once.
- AC-30 UI: "covers N of M" text and missing-coin list on a seeded basket with one missing coin.
- AC-24 UI: each explicit state rendered; no `0` shown for missing.
- AC-32 UI: Playwright removes a shared coin, sees the notice naming both baskets; a coin in no basket shows no notice.
- AC-11 web half: a grep gate over `web/` finds no `trust_weight`, `triggered`, `confirmed`.

**Tests.** Red-first vitest and Playwright; `pnpm --filter web test`, `tsc --noEmit`, `cd web && pnpm build:islands`, `cd web && pnpm test:e2e` (cloud container: `PLAYWRIGHT_CHROMIUM_PATH`, `SCREENER_REFRESH_WORKER=0`). **Dependencies.** S-B and S-C merged. **Cost.** 10-14 USD. **Read list (~32,500 B):** `NarrativeDashboard.tsx` 7,846; `SpaghettiChart.tsx` 6,075; `spaghetti-lines.ts` ~3,000 of 5,392; `use-simple-lines.ts` 2,198; `AddCoinForm.tsx` ~2,000 of 4,011; `CoinActions.tsx` ~2,500 of 4,431; `DeadDataNotice.tsx` 841; unmeasured `lib/api/narrative.ts`, `lib/types/narrative.ts`, `e2e/narrative.spec.ts`, capped at 8,000 B by range (measure on first read). **Risks.** R-D1 e2e (CI does not run it) is red from C until D; R-D2 screener remove control location unverified; R-D3 chart island build. **Rollback.** Revert the PR; the API stays valid.

## Waves and cost

| Wave | Slices | Concurrent | Why |
|---|---|---|---|
| 1 | A | 1 | B and C both need the store and the screener rule |
| 2 | B and C | 2 (disjoint globs, only `api/main.py` is B alone) | B adds new files; C deletes and edits old ones |
| 3 | D | 1 | needs B's endpoint and C's contract |

Spend now about 106 of 130 USD (headroom 24). Estimates: A 4-6, B 4-6, C 8-12, D 10-14 = 26-38 USD (mid 32). Waves 1-2 (A, B, C) cost 16-24 and fit the headroom only at the low end. **Owner decision needed before wave 3:** raise the ceiling by about 10-14 USD for D, or drop D to the next plan. The planner re-checks spend after wave 2 and stops there if it exceeds 124 USD.

## Risks (plan level)

R1 old stack more entangled than read (hidden importers): C's first step is an importer list; stop on `needs_input`. R2 C and D leave main with a degraded page between merges: no deploy in between (R-C3). R3 estimates are from reading, not from measuring runs. R4 cascade across two files is not atomic (S-A). R5 Windows path or deploy behaviour is verifiable only on the PC.

## Validate contract

_Placeholder. `vc-validate-agent` writes this section (V1-V7) before EXECUTE; do not start EXECUTE with it empty. Run `validate-plan-artifact.mjs` on this file (RT0). Open validator questions: importer list for C; location of the screener remove control for D; size of `lib/api/narrative.ts`, `lib/types/narrative.ts`, `e2e/narrative.spec.ts`._

## Planner checklist (after merge, not worker work)

Register P5a-P5d in MASTER-PLAN (D-4 follow-up); fix docs naming removed symbols (`all-context.md`, `all-tests.md` counts, `all-data-sources.md`; SPEC AC-11 says docs too); add decision entry for A6/A7 if the owner confirms; update the SPEC split note for E/F/G; note the legacy `coingecko/{category}` series freeze (A9).

## Not verified by this plan writer

Ran no code and no search; the full "Common rules" of the data-integration plan could not be read (tool output limit), so conventions follow its Amendment A5, `operating-instructions.md` and `all-tests.md`. File sizes marked with `~` are range estimates; others are exact from the repo listing. Counts in `all-tests.md` are stale and must be re-measured by each worker.
