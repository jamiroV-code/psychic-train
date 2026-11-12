---
phase: rfc-006-stage0-e2e-proof
date: 2026-09-24
status: COMPLETE
feature: narrative-mindshare
plan: process/features/narrative-mindshare/active/narrative-dashboard_24-09-26/narrative-dashboard_PLAN_24-09-26.md
---

# RFC-6 Stage 0 — End-to-end proof + AC-3/AC-12 handoff: findings

**BLUF:** RFC-6 is doable with no new isolation mechanism. `seed_e2e_cache.py` gets a `seed_narrative()` that writes through the real `cache.write_narrative_point` / `write_exchange_market_snapshot` / `write_exchange_point` functions into the SAME temp cache the regime and screener specs use. Then `web/e2e/narrative.spec.ts` checks 13 scenarios against a real `/api/narrative/history` request. Expected values go in the manifest and are hand-derived in the seeder, not produced by calling `history.py`.

There are two hard limits:
- `/history` only ever returns the 4 seed categories (`narrative_categories.json`, fixed path, no env override). The 10-panel cap and the overflow list therefore stay **unit-tested only**.
- `/categories` (called by `/screener`'s NarrativeStrip) can **write** to the narrative cache. The AC-1 screener check must run last, and its assertions must be structural only.

No source or test file was edited in this stage.

## Context Envelope

| Field | Value |
|---|---|
| feature | narrative-mindshare |
| phase | EXECUTE (RFC-6 Stage 0 only) |
| session-goal | Narrative dashboard RFC-6: seeded E2E proof + AC-3/AC-12 user handoff |
| branch | `claude/kind-tesla-tat3vo` (clean tree; HEAD `e64c169` RFC-5) |
| worktree | main |
| context-group | tests, data-sources |
| blast-radius-packages | `api/scripts/seed_e2e_cache.py`, `web/e2e/narrative.spec.ts` (new) |
| active-plan | narrative-dashboard_PLAN_24-09-26.md |
| test-runner | pytest \| vitest \| playwright |
| validate-contract | inline in plan, Gate: PASS |

## 1. Seeding proposal (`seed_e2e_cache.py`)

The seeder follows the regime pattern exactly:
- a pure `build_narrative_fixture(today) -> {rows, facts}`;
- `seed_narrative(today=None)` writes the rows and returns `facts`;
- `main()` calls it after `seed_regime()` and adds `manifest["narrative"] = facts`.

The caller has already passed `_guard()`. `today` is **the UTC date** (`pd.Timestamp.now(tz="UTC").date()`), which is the same clock `history.build_narrative_history` uses. This is the ADR-6 tz boundary. Seeding ends on UTC today, so `FRESH_MAX_AGE_DAYS=1` keeps every series `ok` even if the run crosses UTC midnight.

**Key rule (Standing Lesson #7, writer/reader match):**
- pytrends and reddit are keyed by the seed's `keywords[0]` (`"AI crypto"`, `"RWA crypto"`, `"layer 2 crypto"`, `"memecoin"`).
- coingecko, coingecko-narrative and exchange are keyed by category id.

The seeder reads the keywords from `trigger.load_seed_categories()` rather than retyping them.

| Store | Writer used | Seed (window = last 30 UTC days) |
|---|---|---|
| pytrends nightly | `write_narrative_point("pytrends", kw, d, v, "fresh")` | ai, l2s, memecoins: last 20 days. **ai has a gap:** days −12..−9 are missing, so the step is more than 2 days and gives `gap_before`. |
| pytrends backfilled | `write_narrative_point(..., source_status="backfilled")` | ai only: 60 days before the nightly start (dates that don't overlap). This gives the dashed "backfill" line, and the composite `mixed_scale` markers on backfill-only dates. |
| reddit | none | **Nothing written** for every category. `/history` gives `unavailable / no-archived-data`, which is the RFC-4 C1 reality. |
| coingecko (legacy) | `write_narrative_point("coingecko", cid, ...)` | ai: a few days, so the "legacy-map count … excluded" text renders. |
| coingecko-narrative | `write_narrative_point("coingecko-narrative", cid, ...)` | ai, l2s, memecoins: last 20 days, aligned with pytrends so the composite has ≥2 slots. |
| exchange markets | `write_exchange_market_snapshot(d, names)` | Two snapshots, day −1 and day 0. Day 0 adds 2 names mapped to `ai` (e.g. `TAO`, `WLD`), so there is a real new-listing diff. |
| exchange series | `write_exchange_point(cid, row)` | **Day −1 for every category:** `listing_status="unavailable"`, `listing_reason="no-baseline-yet"` (the day-1 no-baseline case), with a real `volume_share`. **Day 0:** `listing_status="ok"`, `baseline_date=day −1`, ai `new_listing_count=2`, and `volume_share` for each category. rwa gets `volume_status="unavailable"`, `volume_reason="no-hyperliquid-market"`. |

Why this crosses the real boundary:
- every parquet and JSON file is produced by the production writer;
- the API reads it back through `read_narrative_series` / `read_exchange_series` / DuckDB;
- the browser fetches it over real CORS.

The rows are not written by calling `exchange_attention.run_daily()`, because that would need a fake ccxt exchange inside the seeder. The rows use the same `as_row` field set instead. **Technical decision (mine):** write rows directly through `write_exchange_point`. `run_daily` is already covered by RFC-2 pytest.

**Designed-in expectations** (hand-derived and written to the manifest; the spec reads them and never retypes them):

- **Comparison.** Values are monotonic by design:
  - ai rises to its series max on the last day, so its composite is 1.0 and it ranks 1.
  - memecoins falls to its minimum, so it ranks last among ranked categories.
  - l2s is flat. A constant series normalises to 0.5.
  - **rwa has only exchange volume, which is unavailable, so it has <2 slots on every date.** That gives `rank=null`, rendered as "—" with the reason `no-composite-on-as-of`/`no-composite-data`.
  - The seeder states the expected order `[ai, l2s, memecoins, rwa(null)]`.
- **Change.** ai and memecoins have composites 7–9 days back, so they get real deltas with fixed signs (ai > 0, memecoins < 0). **l2s composite only starts 3 days ago**, so there is no baseline in the window, giving delta null "—" with the reason `no-baseline-in-window`. The null-delta case is covered by a category that *does* rank in comparison, which is the stronger case.
- The manifest also records: the gap date for ai pytrends, the ai backfill date range, the day −1/day 0 dates, the ai new-listing count of 2, and the narrative-only coin symbol.
  - For the narrative-only coin: pick the first `ai` coin in `narrative_category_map.json` that is not in the legacy `COIN_CATEGORY_MAP`, computed in the seeder via `mapping.map_coin_to_narrative_category`.

A small pytest guards the seeder: `build_narrative_fixture` is pure, and the keyword keys equal `keywords[0]`. This is optional; I recommend it (mirrors Standing Lesson #7).

## 2. `narrative.spec.ts` scenarios → ACs

| # | Scenario (testids from RFC-5) | AC |
|---|---|---|
| 1 | `/narrative` loads: `narrative-dashboard` visible, `narrative-caveat-page` plus the history/comparison/change caveats visible, and no `narrative-error`. | AC-2, AC-11 |
| 2 | One `narrative-panel-{id}` per seed id (4). `narrative-chart-{id}` `data-points` > 0 for ai/l2s/memecoins. rwa shows its empty/insufficient-coverage state, not a zero line. | AC-2, AC-9 |
| 3 | Gap break: the API's `/history` response (via `request`) has `gap_before=true` on the manifest's gap date for ai pytrends, and the panel's segmented data reflects it. Use a `data-gap-count`-style attribute only if RFC-5 exposes one; otherwise assert on the API and on `data-points`. | AC-2 |
| 4 | Nightly and backfill are separate lines: `narrative-legend-ai-pytrends-nightly-7d` and `…-backfill-269d` are both present. | AC-4 |
| 5 | Mixed-scale marker: `narrative-mixed-scale-ai` has `data-count` > 0. `narrative-comparison-mixed-*` appears only where the manifest says it should. | AC-10 |
| 6 | Legacy-map label: `narrative-legacy-count-ai` text contains "legacy-map count" and "excluded". | AC-10 |
| 7 | Narrative-only label: `narrative-coin-ai-{SYM}` has `data-narrative-only="true"` for the manifest symbol. | AC-8 |
| 8 | Personal-use badge: `narrative-redistribution-badge` plus a per-panel `narrative-redistribution-{id}` are visible (all flags false). | constraint (licensing) |
| 9 | Comparison: row order and `data-rank` match the manifest. The rwa row shows "—" plus reason text, never "0", and sorts last. | AC-5 |
| 10 | Change: the ai/memecoins delta signs match the manifest. `change-delta-l2s` is exactly "—" plus `no-baseline-in-window` copy. | AC-6 |
| 11 | Hyperliquid: `narrative-new-listings-ai` shows 2. The volume-share legend is present. A no-baseline-yet notice appears only on the day −1 series state if it is visible. rwa's `no-hyperliquid-market` notice renders. | AC-7 |
| 12 | Reddit: `narrative-notice-ai-reddit` shows "Unavailable — no archived data…". The other sources still render (AC-9). | AC-9 |
| 13 | Home link: `home-link-narrative` on `/` navigates to `/narrative`. | — |
| 14 (**last**) | `/screener` NarrativeStrip still renders: `narrative-strip` visible and not stuck on `narrative-loading`. Structural only. Byte-identity stays with the existing pytest contract snapshot (3/3). | AC-1 |

**10-panel cap and overflow: unit-tested only.** The seed categories are fixed at 4, `/history` rejects unknown ids (422), and the categories file path has no env override. Reaching more than 10 would need a production change, which is out of scope. The vitest `NarrativeDashboard.test.tsx` and `narrative-view-model.test.ts` already cover it. The spec will assert `narrative-overflow-toggle` has count 0 as a negative check.

## 3. Interference with the regime/screener seeded cache

- **Paths are disjoint.** Narrative writes only under `CACHE_ROOT/narrative/**`. Regime writes liquidity/etf/liqtide, and the screener writes ohlcv. They share one `SCREENER_CACHE_ROOT`, which is wiped and rebuilt by `main()` on every run. No new env vars and no `playwright.config.ts` change are needed.
- **Real risk: `/categories` writes to the cache.** Visiting `/screener` makes NarrativeStrip call `/categories`, which runs `trigger.assemble_narrative_categories`. That call:
  - tries live pytrends. On success it writes `pytrends/{keyword}` for today, with keep-last, which would overwrite a seeded value;
  - writes legacy `coingecko/{id}` whenever trending is not `unavailable`.

  In this container egress is blocked, so nothing is written. On the user's PC it can be.

  **Mitigations (technical, mine):**
  - (a) Do **not** seed `coingecko_trending.parquet`, so no stale-snapshot fallback triggers a legacy write here.
  - (b) Workers are 1 and files run alphabetically, so `narrative` runs before `regime` and `screener`. Within the narrative spec, the AC-1 screener check goes **last**.
  - (c) Narrative assertions never depend on today's raw pytrends value. They depend on ranks and signs that are built with margin.
  - (d) Nothing in regime or screener reads `narrative/`, so no reverse interference is possible.
- `/categories` with blocked egress is slow (pytrends retries). That is already true for the screener spec today. Use generous timeouts only on the AC-1 check.
- The webServer health URL stays `/screener`. There is no change to ports or CORS.

## 4. AC-3 / AC-12 user-PC handoff checklist

The workflow only runs **from `main` after merge**: `schedule` triggers fire on the default branch only. `workflow_dispatch` also needs the file on the default branch before it shows in the Actions tab.

1. **Merge to main and push.** In GitHub, check Settings → Actions → General: Actions are enabled and the workflow permission is "Read and write".
2. **First run (AC-3):**
   - Go to Actions → "narrative-snapshot" → Run workflow (main), or run `gh workflow run narrative-snapshot.yml --ref main`, then `gh run watch`.
   - Expect exit 0, or exit 2 with a warning, and a commit touching only `api/data/cache/narrative/`.
   - Check again the next morning, after 23:00 UTC: there is a second bot commit, and there is one row per (source, category) for that date.
3. **Local snapshot sanity:**
   - `uv run --project api --with pytrends python -m api.scripts.snapshot_narrative --dry-run`
   - then the same command without `--dry-run`, run twice (the second run should skip all), then `--verify-only`.
4. **Hyperliquid integration test:** `uv run --project api pytest api/tests/data/test_hyperliquid_narrative_adapter.py -m integration -q`.
5. **pytrends backfill (AC-4)** (pytrends is not in `pyproject`, so `--with` is required):
   - `uv run --project api --with pytrends python api/scripts/backfill_pytrends_history.py --dry-run`, then check the output;
   - then run it again without `--dry-run`.
6. **Hyperliquid terms:** read Hyperliquid's terms of use and API docs for redistribution of market data.
   - If they allow it, flip `HYPERLIQUID_REDISTRIBUTABLE = True` in `api/data/hyperliquid_narrative_adapter.py` (a one-line change; D4). Then re-run `uv run --project api pytest api/ -q`.
   - Otherwise leave it `False`.
7. **Real-cache walkthrough (AC-12):**
   - API: `uv run --project api uvicorn api.main:app --host 127.0.0.1 --port 8000`
   - Web: `pnpm --filter web dev`
   - Open `http://localhost:3000/narrative` and confirm:
     - the caveat on every view;
     - a history chart per category;
     - backfill as a dashed line with markers;
     - comparison and change tables with "—" where there is no data;
     - Reddit unavailable;
     - Hyperliquid volume share, plus "no baseline yet" on its first day;
     - the personal-use badge.
   - Then open `/screener` and confirm the narrative strip looks as before.
8. **Risk-pack decisions:** set `"decision"` to `approved` / `approved-with-concerns` / `rejected`, with notes, in:
   - `harness/review-decision.json` (RFC-3 `/history` public API);
   - `harness/rfc-004/review-decision.json` (RFC-4 workflow: writes to main, `contents: write`, no secrets).

   Both are `PENDING` today with `mustStopBeforeFinalize: true`.
9. **Optional Reddit:** add the repo secrets **and** a two-line `env:` mapping in `narrative-snapshot.yml`. Per RFC-4, the secrets alone do nothing.

## 5. RFC-6 exit gate list

```
uv run --project api pytest api/ -q                                  # expect 388+ passed, integration deselected
pnpm --filter web test                                               # expect 110+ passed (16 files)
pnpm --filter web exec tsc --noEmit                                  # exit 0; restore web/tsconfig.tsbuildinfo after
cd web && PLAYWRIGHT_CHROMIUM_PATH=/opt/pw-browsers/chromium-1194/chrome-linux/chrome pnpm test:e2e
                                                                     # expect 12 existing + ~14 narrative, 0 failed
git diff -- web/components/screener api/analytics/narrative/trigger.py   # empty (AC-1)
```
Run the e2e twice, as the regime RFC-006 did, to catch order and flake issues.

## 6. Plan-text conflicts

1. **Reddit copy.** The RFC-6 Post-Phase Testing says Reddit shows `credentials-not-configured`. Under RFC-4 C1 no row is written, so `/history` gives `no-archived-data`. **The spec will assert `no-archived-data`.** UPDATE PROCESS should fix the plan text and §19.
2. **§19 Ops Runbook.** "Reddit rows read credentials-not-configured" and "add secrets" are both stale (RFC-4 report). The backfill command also lacks `--with pytrends`.
3. **Report naming.** The plan's Resume section says `narrative-dashboard_24-09-26-RFC-N-phase-report.md`; the actual convention is `narrative-dashboard_RFC-00N_REPORT_24-09-26.md`. I'm following the actual convention.
4. **Status Strip and Resume section are stale.** They show every RFC as PLANNED and "VALIDATE not yet run". This is for UPDATE PROCESS.
5. **"ranks match a hand-computed expectation."** This is interpreted as seeder-declared expected order in the manifest, derived from designed-in monotonic series, not by calling `history.py`. This keeps the check non-circular.
6. **The 10-panel cap** cannot be reached end to end (4 fixed seeds). It is unit-tested only; this narrows the RFC-6 wording and is not a gap in the product.

## Decisions needed from the user

1. **Approve this Stage 0 design** (seed shape, 14 scenarios, cap unit-tested only), so RFC-6 implementation can start.
2. **Optional seeder pytest** (`api/tests/scripts/test_seed_narrative_fixture.py`, pure-function check): include it (recommended) or skip it?

All other choices are technical and already decided above: direct `write_exchange_point` rows, no trending snapshot seed, AC-1 check last, and asserting `no-archived-data`.

## Forward Preview

- **Test Infra Found:** the regime `build_*_fixture` + manifest pattern; the RFC-5 testids; vitest fixtures in `web/components/narrative/__tests__/fixtures.ts`, which can serve as a shape reference only.
- **Blast Radius Changes:** `api/scripts/seed_e2e_cache.py` (additive); new `web/e2e/narrative.spec.ts`; optional new seeder pytest.
- **Commands to Stay Green:** see §5.
- **Dependency Changes:** none.

TL;DR: Seed the narrative cache through the real writers into the shared temp cache, run 14 Playwright scenarios with expectations from the manifest, keep the 10-panel cap unit-tested only, and run the `/screener` AC-1 check last. The user then completes the merge, dispatches the workflow, runs the backfill, checks the Hyperliquid terms, does the walkthrough, and signs the two risk packs.
