---
phase: rfc-006-e2e-proof
date: 2026-09-24
status: COMPLETE_WITH_GAPS
feature: narrative-mindshare
plan: process/features/narrative-mindshare/active/narrative-dashboard_24-09-26/narrative-dashboard_PLAN_24-09-26.md
---

# RFC-6 execute report — end-to-end proof + AC-3/AC-12 handoff

**BLUF:** `/narrative` is proven end to end. There are 14 new Playwright scenarios, and all 26 e2e tests passed on both runs (14 new + 6 regime + 6 screener). The e2e run found a **real product bug**: `/api/narrative/history` returned HTTP 500 as soon as an exchange listing series held two days. It is now fixed with a minimal change and has a regression test.

Gates:
- pytest: 392 passed, 3 deselected
- vitest: 110/110
- `tsc --noEmit`: exit 0
- screener and `trigger.py` diffs: empty

Nothing is committed. Still open: AC-3 and AC-12, plus two review decisions, all user-run on a real machine (checklist below).

## What Was Done

| File | Change |
|---|---|
| `api/scripts/seed_e2e_cache.py` | Adds `build_narrative_fixture(today)` (pure) and `seed_narrative()`. They write only through `cache.write_narrative_point` (pytrends nightly + `backfilled`, coingecko legacy, coingecko-narrative), `write_exchange_market_snapshot` and `write_exchange_point`. `main()` seeds the fixture after regime and adds `manifest["narrative"]`. **Key rule:** pytrends is keyed by `keywords[0]`, everything else by category id. Dates are UTC (ADR-6). No reddit rows and no `coingecko_trending.parquet`, both deliberate. |
| `api/tests/scripts/test_seed_narrative_fixture.py` (new, 4 tests) | 1. The fixture is pure and keyed correctly. 2. The seed writes what the manifest says, read back through the real readers. 3. `build_narrative_history` over the seed matches the hand-derived ranks, signs, mixed-scale count, gap date and reddit `no-archived-data`. 4. **Regression:** the `/api/narrative/history` endpoint returns 200 over the seed. |
| `web/e2e/narrative.spec.ts` (new, 14 tests) | All expectations are read from the manifest. The `/screener` AC-1 check runs last. Assertions use ranks and signs, never today's raw values. The file header documents that the 10-panel cap is unit-tested only. |
| `api/analytics/narrative/history.py` (**bug fix**, 4 lines) | See below. |

### Product bug found by the E2E

- **Symptom:** `GET /api/narrative/history` returned 500, and the page showed "Narrative history unavailable — Failed to fetch".
- **Cause:** `_exchange_frames` built its columns from Python lists holding `str`/`None`. Current pandas infers a NaN-backed `StringDtype` for those lists, so `None` became `NaN`. `NarrativeHistoryPoint.reason: str | None` then rejected the NaN.
  - This happens as soon as one exchange series has a day with a listing reason and a day without, e.g. `no-baseline-yet` on day 1 and `ok` on day 2.
  - That is exactly the state after the **second nightly run**, so the live dashboard would have broken on day 2.
- **Why earlier tests missed it:** RFC-3 tests used a single row or all-None reasons, and vitest uses injected fixtures.
- **Fix:** `_obj()` now returns `pd.Series(..., dtype=object)`, which keeps `None`.
- **Proof:** the new endpoint test fails without the fix (1 failed, 3 passed) and passes with it (4 passed). The e2e went from 12 narrative failures to 0.

## Scenario → AC map (all green, both runs)

1. Page loads with a caveat on every view (AC-2, AC-11).
2. One panel per seed category. `data-points` is correct (ai = 80). The unavailable rwa composite shows a notice. No overflow (AC-2, AC-9).
3. `gap_before` is set on exactly the manifest gap date (AC-2).
4. Nightly and backfill are separate lines, and the backfill points are `backfilled` (AC-4).
5. Mixed-scale `data-count` = 10, and today's rankings are not mixed (AC-10).
6. The legacy-map count is labelled "excluded from the composite" (AC-10).
7. The narrative-only coin is labelled (AC-8).
8. The personal-use badge shows on the page and on every panel (licensing).
9. Comparison order is `ai 1, l2s 2, memecoins 3, rwa —` with "Unranked" (AC-5).
10. Change signs are ai +, memecoins −. l2s and rwa show "—", and l2s has "No change" copy (AC-6).
11. Hyperliquid: the volume legend shows, "2 (as of today)" new listings, `no-baseline-yet` on day −1, and `no-hyperliquid-market` for rwa (AC-7).
12. Reddit shows `unavailable / no-archived-data` while the other sources render (AC-9).
13. The home link goes to `/narrative`.
14. **Last:** `/screener` NarrativeStrip renders and finishes loading (AC-1, structural only).

**The 10-panel cap and overflow are unit-tested only.** There are only 4 seed categories and `/history` returns 422 for unknown ids. Vitest covers the cap (`NarrativeDashboard.test.tsx`, `narrative-view-model.test.ts`). The E2E asserts that no overflow toggle appears.

## Test Gate Outcomes

| Gate | Result |
|---|---|
| `uv run --project api pytest api/ -q` | **392 passed, 3 deselected** (was 388; +4 new) |
| `pnpm --filter web test` | **16 files, 110 passed** |
| `pnpm --filter web exec tsc --noEmit` | exit 0; `web/tsconfig.tsbuildinfo` restored via `git checkout` |
| e2e run 1 (`PLAYWRIGHT_CHROMIUM_PATH=… pnpm test:e2e`) | **26 passed** (14 narrative, 6 regime, 6 screener), 55.2s |
| e2e run 2 | **26 passed**, 55.6s |
| `git diff -- web/components/screener api/analytics/narrative/trigger.py` | empty |
| Real `api/data/cache/` | untouched: no `narrative/` dir created; seeding only goes to the temp `SCREENER_CACHE_ROOT` |

## Plan Deviations

- **D1: a product code change in `history.py`.** This is a real bug exposed by the spec, fixed minimally as allowed by the brief. It stays inside the RFC-3 blast radius and does not change the `/history` contract (it now actually honours `reason: str | None`).
- The Reddit assertion uses `no-archived-data`, not `credentials-not-configured`, per the approved Stage 0 decision.
- The "no-hyperliquid-market" and "no-baseline-yet" reasons are asserted on the API's per-point `reason`. The UI panel notice shows the series-level status ("no archived data" for an all-null volume series, and the latest listing count). That is existing RFC-5 behaviour, recorded here but not changed.

## What Was Skipped or Deferred / Test Infra Gaps Found

- AC-3 (the nightly cron actually running) and AC-12 (the real-cache walkthrough): these are user-run.
- Both risk-pack review decisions are PENDING.
- **Infra note:** a `str`/`None` list turning into a NaN-backed `StringDtype` could also affect other list-built frames. I found no other instance on the `/history` path (`_narrative_frame` uses object arrays). This is worth a mention in UPDATE PROCESS as a Standing Lesson candidate.

## User-PC Handoff Checklist (AC-3 / AC-12)

The nightly workflow only runs **from `main` after merge**. Scheduled triggers fire on the default branch only, and `workflow_dispatch` only appears once the file is on `main`.

1. **Merge and push to `main`.** In GitHub, check Settings → Actions → General: Actions are enabled and "Workflow permissions" is **Read and write**.
2. **First dispatch (AC-3):**
   - Run `gh workflow run narrative-snapshot.yml --ref main`, then `gh run watch`. The Actions tab also works: "narrative-snapshot" → Run workflow.
   - Expect exit 0 (or exit 2 with a warning) and a bot commit touching only `api/data/cache/narrative/`.
   - The next day, after 23:00 UTC, confirm a second bot commit.
   - Then `git pull` and run `uv run --project api python -m api.scripts.snapshot_narrative --verify-only`: one new row per (source, category).
3. **Local snapshot sanity:**
   - `uv run --project api --with pytrends python -m api.scripts.snapshot_narrative --dry-run`
   - then the same command without `--dry-run`, run twice (the second run skips everything);
   - then `--verify-only`.
4. **Hyperliquid integration test:** `uv run --project api pytest api/tests/data/test_hyperliquid_narrative_adapter.py -m integration -q`.
5. **pytrends backfill (AC-4)** (pytrends is not a project dependency, so `--with` is required):
   - `uv run --project api --with pytrends python api/scripts/backfill_pytrends_history.py --dry-run` and review the output;
   - then run it again without `--dry-run`.
6. **Hyperliquid terms check:** read Hyperliquid's Terms of Use and API docs on redistributing market data.
   - Only if they allow it, set `HYPERLIQUID_REDISTRIBUTABLE = True` in `api/data/hyperliquid_narrative_adapter.py` (decision D4), then run `uv run --project api pytest api/ -q`.
   - Otherwise leave it `False`, so the personal-use badge stays.
7. **Real-cache walkthrough (AC-12):**
   - API: `uv run --project api uvicorn api.main:app --host 127.0.0.1 --port 8000`
   - Web: `pnpm --filter web dev`
   - Open `http://localhost:3000/narrative` and confirm:
     - the caveat on all views;
     - a growing chart per category;
     - dashed backfill lines with orange mixed-scale dots;
     - comparison and change tables with "—" plus a reason where data is missing;
     - Reddit "no archived data" (unless secrets plus the workflow `env:` edit are added);
     - Hyperliquid volume share and new-listings text;
     - the personal-use badges.
   - Then open `http://localhost:3000/screener` and confirm the narrative strip looks unchanged.
8. **Review decisions (manual-first risk packs):** in each file, set `"decision"` to `approved`, `approved-with-concerns` or `rejected`, with a rationale and timestamp:
   - `process/features/narrative-mindshare/active/narrative-dashboard_24-09-26/harness/review-decision.json` (RFC-3, `/history` public API);
   - `…/harness/rfc-004/review-decision.json` (RFC-4 workflow: `contents: write`, pushes to `main`, no secrets).

   Both are PENDING with `mustStopBeforeFinalize: true`.
9. **Optional Reddit history:** add repo secrets `REDDIT_CLIENT_ID`/`REDDIT_CLIENT_SECRET` **and** a two-line `env:` mapping in `narrative-snapshot.yml`. Per RFC-4, the secrets alone do nothing.

## Closeout Packet

- Plan: `process/features/narrative-mindshare/active/narrative-dashboard_24-09-26/narrative-dashboard_PLAN_24-09-26.md` (not edited).
- Verified: every automated gate above, including two e2e runs.
- Not verified: live providers, the GitHub Actions run, the real-cache walkthrough, and both review decisions.
- Classification: **Keep in active/testing** until the user completes steps 2–8.
- For UPDATE PROCESS:
  - fix the plan's Reddit copy and §19 runbook (add `--with pytrends`, fix the secrets note);
  - fix the report naming note and the Status Strip;
  - record D1 (the `history.py` fix) and the pandas StringDtype lesson.
- Follow-up stubs: none. CONTEXT_PARTIAL: none.

## Forward Preview

- **Test Infra Found:** `manifest["narrative"]` facts; `seed_narrative()` is reusable under `isolated_cache`.
- **Blast Radius Changes:** `api/scripts/seed_e2e_cache.py`, `api/analytics/narrative/history.py` (fix), new `web/e2e/narrative.spec.ts`, new `api/tests/scripts/test_seed_narrative_fixture.py`.
- **Commands to Stay Green:** the four gates above; the e2e needs `PLAYWRIGHT_CHROMIUM_PATH` in this container.
- **Dependency Changes:** none.

TL;DR: The E2E is green twice (26/26), and all the other gates are green. The E2E caught and fixed a day-2 HTTP 500 in `/history`. The rest is the user-PC checklist: merge, dispatch, backfill, terms check, walkthrough, and the two review decisions.
