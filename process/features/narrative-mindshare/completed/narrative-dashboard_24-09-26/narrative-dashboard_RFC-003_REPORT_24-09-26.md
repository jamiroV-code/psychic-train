---
name: report:narrative-dashboard-rfc-003
description: "RFC-3 execute report — GET /api/narrative/history (read-only), composite/rank/change maths, E3 harness pack; all automated gates green, not committed, review decision pending"
date: 24-09-26
metadata:
  node_type: memory
  type: report
  feature: narrative-mindshare
  phase: RFC-3
phase: rfc-003
status: COMPLETE_WITH_GAPS
feature: narrative-mindshare
plan: process/features/narrative-mindshare/active/narrative-dashboard_24-09-26/narrative-dashboard_PLAN_24-09-26.md
---

# RFC-3 — `GET /api/narrative/history` + composite / rank / change maths

**BLUF:** RFC-3 is code-complete and every automated gate is green:
- Full api suite: **378 passed, 3 deselected** (was 336; 42 new).
- web vitest: **75 passed (12 files)**.
- RFC-1 contract test: **3/3**.
- `git diff` on `trigger.py` and `screener_board.py` is **empty**. `get_categories` has an unchanged body.

Nothing is committed. RFC-3 is **not finalize-ready** (E3): `harness/review-decision.json` is `PENDING`
until the user reviews sample output. The manual curl against a real cache is a user-PC step.

## Decisions applied (user-approved 2026-09-24)
- **D1 = (a):** the legacy CoinGecko series is shown with the label "CoinGecko trending (legacy-map count)" and a reason, and is **excluded** from the composite. A `coingecko-narrative/{category}` source is a composite slot. It is read if present and treated as unavailable otherwise; both cases are tested. RFC-3 never writes it. RFC-4 must write under exactly `cache.write_narrative_point("coingecko-narrative", category_id, ...)`.
- **D2 = (a):** `nightly-7d` and `backfill-269d` pytrends are separate series, each normalised on its own. The composite uses whichever exists on a date (pytrends counts once), and composite points from backfill are flagged `mixed_scale`. The change figure is `mixed_scale` if either end is.
- **D3 = (a):** Hyperliquid `volume_share` is a composite slot. `new_listing_count` is display-only and keeps its null + `no-baseline-yet` rows. None of this touches `compute_trigger` or `/categories`.

## What Was Done

| File | Change |
|---|---|
| `api/analytics/narrative/history.py` (new) | A pure read of the archive. It never calls an adapter or `compute_narrative_categories` and never writes. Keys: pytrends and reddit by `keywords[0]`; coingecko, coingecko-narrative and exchange by id. Composite slots: `pytrends, reddit, coingecko-narrative, exchange_volume_share`. A point exists only when ≥ `trigger.MIN_AVAILABLE_SOURCES` (2) slots are present; `coverage` = present/4. `trust_weight` is 0.6, or 0.4 without pytrends (trigger constants). Normalisation runs over the full stored history, then `start`/`end` filtering. `gap_before` is set when the step is more than `NARRATIVE_MAX_GAP_DAYS=2` days. Series status comes from age: ≤1 day ok, older stale, pytrends >7 days presumed-dead; exchange uses its stored row status. Comparison is a competition rank (1, 1, 3) at 6 dp, taken at `as_of` = latest composite date ≤ `end`. Change = 7 days, with the baseline in [as_of−9d, as_of−7d]. Missing entries get `rank=None` plus a reason. Unknown ids raise `UnknownCategoryError` before any path is built. `redistributable` is False for all sources (constants). |
| `api/models/narrative.py` | Additive only: `NarrativeHistoryResponse` and its children (`...Category`, `...Series`, `...Point`, `NarrativeCoin`, `NarrativeComposite(Point)`, `NarrativeComparison(Entry)`, `NarrativeChange(Entry)`). `NarrativeCategory` is untouched. |
| `api/routers/narrative.py` | Adds `get_history` and `_history_response`. Returns 422 for: start > end, an empty `categories` list, an unknown id, or a malformed date (FastAPI). Gzip is inherited. The body of `get_categories` is unchanged; only the imports above it grew. |
| `api/tests/analytics/test_history.py` (new, 25) | Real cache round-trip keyed by keyword. Composite golden values (1/3, 1/3, 2/3). Skipna. Coverage floor: one source → no point; one source ever → `unavailable`. Trust cap. Scale invariance (AC-10). Legacy CoinGecko excluded. coingecko-narrative absent and present. new_listing null. Separate pytrends variants and `mixed_scale`. Stable normalisation under filtering. Gap boundary at 2 and 3 days, and after filtering. Age statuses. Rank ties. Comparison with a missing category. No-data case. Change: exact baseline, 9-day fallback, too-old baseline, `mixed_scale`. Allow-list. UTC 23:59:59 vs 00:00:00. narrative_only coins. A check that trigger and screener do not import history. |
| `api/tests/routers/test_narrative_history.py` (new, 17) | TestClient against the real app with every fetcher patched to raise. Shape and grid. Legacy label. Variants. Coins. Category and date filters. Six 422 cases, including `../../secrets`. One source down leaves the others unaffected (AC-9). Empty cache → 200 with no 500. Zero cache writes. Gzip. `get_history` and `get_categories` are separate. |
| `harness/` (new) | `risk-gate.json`, `context-snippets.json`, `verification.json`, `review-decision.json` (PENDING) and `adversarial-validation.json`. Validator: the only failure is the intended `decision must be approved…` one. |

## Backlog item — existing `/categories` keying bug (user chose a separate fix)
- `api/analytics/narrative/trigger.py:206` does `cache.read_narrative_series(source, category_id)` for pytrends, reddit and coingecko.
- `api/data/pytrends_adapter.py:100` writes `write_narrative_point("pytrends", keyword, ...)`, and `api/data/reddit_adapter.py:133` writes `write_narrative_point("reddit", subreddit_or_keyword, ...)`.
- Effect: `/categories` never reads the stored pytrends or reddit history, so its trigger runs on coingecko alone. Fixing it changes AC-1 output, so the RFC-1 contract snapshot must be deliberately re-baselined in that task. The orchestrator will queue it.

## What Was Skipped or Deferred
- The manual curl on a real cache is a user-PC step, because the narrative cache here is empty (egress block).
- `review-decision.json` is pending user APPROVE or REJECT (manual-first). RFC-3 is not finalize-ready until that is recorded.
- The plan's "User confirmed working / sample output for 2+ categories" item is pending.

## Test Gate Outcomes
| Gate | Result |
|---|---|
| `test_history.py` | 25 passed |
| `test_narrative_history.py` | 17 passed |
| `test_narrative_categories_contract.py` | 3 passed |
| `uv run --project api pytest api/ -q` | **378 passed, 3 deselected** |
| `pnpm --filter web test` | **75 passed, 12 files** |
| `git diff -- trigger.py screener_board.py` | empty |
| risk-pack validator | only `review-decision.decision` fails (PENDING by design) |

## Plan Deviations (within blast radius)
1. The response is category-first, not the flat §11 `series[]`, and it adds `variant`, `in_composite`, `mixed_scale`, `coverage`, `sources_present`, `redistributable_all` and `coins` (as proposed in Stage 0).
2. `trust_weight` is per composite point, not per source (ADR-4 text).
3. Ranking happens only at `as_of`, with no per-date rank history (ADR-5 text). Ranks are among the *requested* categories.
4. An extra composite slot, `coingecko-narrative`, and the exclusion of the legacy CoinGecko count, per D1.
5. `RankEntry.value` holds the composite level for comparison and the delta for change (internal only; the API fields are `value` and `delta`).

For UPDATE PROCESS to amend in the plan: §11 shape; §11/§12b key naming (keyword for pytrends and reddit, plus the new `coingecko-narrative/{id}` key for RFC-4); ADR-4 trust_weight; ADR-5 rank scope; ADR-6 redistributable (False); the data-sources group (pytrends, reddit and CoinGecko redistributable=False).

## Test Infra Gaps Found
None. `isolated_cache`, TestClient and fetchers patched to raise were sufficient. Note: the router test file takes about 30 s because each TestClient boots the app.

## Closeout Packet
- Plan: `process/features/narrative-mindshare/active/narrative-dashboard_24-09-26/narrative-dashboard_PLAN_24-09-26.md`
- Classification: **Keep in active/testing.** The review decision and the user-PC curl are pending.
- Verified: all automated gates above. Not verified: output against a real cache, and user review.
- Next: EVL confirmation run (vc-tester), then the user fills in `harness/review-decision.json`. After that, RFC-4 and RFC-5 can start in parallel.

## Forward Preview
- **Test Infra Found:** `no_network` fixture pattern (all fetchers raise); `build_narrative_history(today=...)` is injectable.
- **Blast Radius Changes:** RFC-4 must write `coingecko-narrative/{category_id}` (count via `map_coin_to_narrative_category`) and exchange rows via `exchange_attention.run_daily()`. RFC-5 reads `NarrativeHistoryResponse`, and must show `mixed_scale`, the legacy-map label and `redistributable` in its caveats.
- **Commands to Stay Green:** `uv run --project api pytest api/ -q`; `pnpm --filter web test`; the contract test.
- **Dependency Changes:** none.

Follow-up stubs created: none (the backlog bug is recorded above for the orchestrator to queue). CONTEXT_PARTIAL: none.

TL;DR: `/history` is built, read-only and green (378 api, 75 web, contract 3/3, trigger and screener diff empty). The review decision is pending the user, and the `/categories` keying bug is logged for a separate fix.
