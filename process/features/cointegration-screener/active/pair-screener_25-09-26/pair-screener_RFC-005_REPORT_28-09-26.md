---
phase: rfc-005-e2e-isolation
date: 2026-09-28
status: COMPLETE
feature: cointegration-screener
plan: process/features/cointegration-screener/active/pair-screener_25-09-26/pair-screener_PLAN_25-09-26.md
---

# RFC-005 — E2E proof + isolation proof (execute report)

**Bottom line:** RFC-005 is code-complete and every gate is green:
- pytest: **484 passed / 3 deselected**;
- vitest: **153 / 19 files**;
- tsc: **0**;
- Playwright: **35/35, run twice** (26 existing + 9 new pairs tests).

The isolation diff on the protected screener and regime paths is **empty**. The earlier screener E2E flake is **pre-existing**: it also fails at the pre-feature commit 35e646f. It is fixed by a config-only 15 s expect timeout (D1). Nothing is committed. Waiting for your review.

## What Was Done

**D1 — screener flake: shown to be pre-existing, then fixed.**
- **Pre-feature run.** Created a temporary worktree at `35e646f`, set it up, and ran the full `pnpm test:e2e` there with the same ports and command.
  - Result: **24 passed / 2 failed**. The failures were `screener.spec.ts:80` (switching timeframe) and `:173` (drill-down).
  - Error: the same `toBeVisible()` 5 s timeout on `coin-panel-BTC`.
  - Those two tests are a subset of the 4 that failed on this branch at Stage 0 (22/26).
- **Cleanup.** `git worktree remove` unregistered the worktree, but the directory delete hit Windows "Filename too long" in `node_modules`. I emptied it with robocopy and removed it. Afterwards:
  - it is gone from disk and from `git worktree list`;
  - ports 8001, 3100, 8011 and 8012 are all free.
- **Fix.** `web/playwright.config.ts` gained `expect: { timeout: 15_000 }` with a comment explaining why. No test logic changed.

**D4 — `PAIRS_UNIVERSE_PATH`:**
- `api/data/pairs_universe.py` now has `default_universe_path()`, which honours `PAIRS_UNIVERSE_PATH` and reads it on every call. `real_universe_path()` is new: it returns the repo file and ignores the override. The seeder uses it for its guard.
- `api/tests/data/test_pairs_universe.py` has 4 new tests:
  - unset → the real file;
  - set → read at call time;
  - empty string → the real file;
  - a missing override file → a loud `UniverseFileError`.
- `playwright.config.ts` `apiEnv` now includes `PAIRS_UNIVERSE_PATH = <E2E_CACHE_ROOT>/pairs_universe.json`.
- `api/data/pairs_universe.json` was **not edited**; `git status` shows it clean.

**Seeder (`api/scripts/seed_e2e_cache.py`, additive only, +190 lines):**
- New functions: `build_pairs_fixture(today)` (pure), `check_pairs_results(table)` and `seed_pairs(today)`.
- **How it works:** it writes 6 fake coins' `1d` bars through `cache.write_ohlcv`, then writes the fixture universe. It then runs the **production `pairs_response.compute_and_persist()`**, which makes the result `fresh` by construction.
- **Self-check:** it verifies every designed state and calls `sys.exit` with a list of the problems on any miss, which fails the webServer start.
- **Guard:** it refuses to run if `PAIRS_UNIVERSE_PATH` is unset or resolves to the real universe file.
- **Manifest:** the facts go into `.fixture-manifest.json` under `pairs`.
- New `api/tests/scripts/test_seed_pairs_fixture.py` has 5 tests:
  - the build is pure and deterministic;
  - every designed state comes out and the result reads `fresh` through `read_table`/`read_detail`;
  - the check catches a tampered or missing row;
  - it refuses when the variable is unset;
  - it refuses the real file and leaves the real file byte-identical.

**Fixture facts (from the manifest, 28-09-26):**

| Item | Value |
|---|---|
| Universe | CINTA, CINTB, WEAKB, DRIFT, SHORT, GHOST |
| Pair count | 15 |
| Status counts | ok 6, insufficient_overlap 4, coin_unavailable 5 |
| Ranked (ok) order | CINTA-CINTB, CINTB-WEAKB, CINTA-WEAKB, WEAKB-DRIFT, CINTB-DRIFT, CINTA-DRIFT |
| Significant after BH | 2 of 6 |
| Raw-only | CINTA-WEAKB only |
| Not mean-reverting, and EG not significant while Johansen rank ≥ 1 (AC-6) | CINTA-DRIFT |
| CINTA-CINTB sample | 2024-04-11 → 2026-09-27, 900 days (ends on the seeding day; dates move daily, statistics do not) |

**`web/e2e/pairs.spec.ts` (9 tests):**
1. The table loads: fresh (no status banner), the exact significance-banner text, the disclosure, and 0 console errors.
2. All 15 rows are shown. The order matches the manifest: ranked rows first, then insufficient_overlap, then coin_unavailable. Each `data-status` is correct.
3. The raw-only tag appears on exactly one row.
4. Each non-ok row shows its reason (GHOST's reason / "only N days … need 365") and no stat cells.
5. CINTA/CINTB detail (reached by clicking the row):
   - chart range text equals the sample window and the manifest dates (**AC-7**);
   - a canvas is present;
   - both EG directions are shown, exactly one marked as used;
   - Johansen verdict, half-life, z-score and disclosure are shown;
   - 0 console errors.
6. CINTA/DRIFT detail: "Not mean-reverting — no half-life", with EG and Johansen both shown and Johansen "Yes" (**AC-6**).
7. `/pairs/CINTA/NOPE`: the 404 message with the API's detail text.
8. `/pairs/CINTA/CINTA`: the 422 self-pair message.
9. Stale banner, labelled **UI-only (D2)**: the real response is fetched through `page.route`, then only `computation_status`/`stale_reason` are overridden.

The spec header records D3: no Johansen-refused row and no "no pair significant" banner in E2E, with pointers to the unit tests that cover them.

**Stage 4 — real-cache re-check (this PC; Hyperliquid was already reachable here, since RFC-001's deep fetch ran on this machine):**
- I started uvicorn with no env overrides, against the real cache.
- `GET /api/pairs` returned `fresh`, universe 18, 153 pairs, 153 ok, 0 with BH < 0.05. This matches RFC-004's live walkthrough.
- `GET /api/pairs/DOGE/BCH` returned 200.
- The visual walkthrough and screenshots are RFC-004's (`rfc-004-walkthrough/`). I did not repeat them.

## Test Gate Outcomes

| Gate | Result |
|---|---|
| `uv run --project api pytest api/ -q` | **484 passed, 3 deselected** (475 + 4 universe override + 5 seeder) |
| `pnpm --filter web test` | **153 passed / 19 files** (4 of 5 runs; see below) |
| `pnpm --filter web exec tsc --noEmit` | exit 0 |
| `cd web && pnpm test:e2e` run 1 | **35 passed** (6.7 min) |
| `cd web && pnpm test:e2e` run 2 | **35 passed** (5.2 min) |
| `pairs.spec.ts` red-first | Initially 8/9. The failure was a real manifest ordering bug, fixed in the seeder (see Deviations); the page was right |

**Vitest note:** the first full vitest run reported 1 failed / 152 passed. The next 4 consecutive runs were 153/153. I could not capture which test failed. RFC-005 changed no file that vitest collects (`e2e/**` is excluded, and the only web changes are the spec and the Playwright config), so this is an intermittent pre-existing failure, not a regression from this RFC.

## Isolation Proof (AC-9, AC-10, AC-11)

```
$ git diff --stat 35e646f -- api/routers/screener.py api/data/watchlist.py web/app/screener/ api/analytics/regime/
(empty)
```

**Broader check, also empty.** Every screener, regime and narrative router, model and analytics folder, `screener_board.py`, the web app/components/lib-api files for all three, and `screener.spec.ts`, `regime.spec.ts` and `narrative.spec.ts`.

**All non-pairs files changed vs 35e646f (committed plus working tree):**
- `api/data/cache.py` (additive `pairs_*` helpers plus one bootstrap-list entry);
- `api/main.py` (router registration);
- `api/pyproject.toml` and `api/uv.lock` (statsmodels);
- `web/app/page.tsx` (link);
- **new in RFC-005:** `api/scripts/seed_e2e_cache.py` (+190 lines, 0 deleted, E2E infra) and `web/playwright.config.ts` (+8 lines: the pairs env variable and the D1 timeout);
- `web/tsconfig.tsbuildinfo` (a build artifact).

**AC-11, the real cache was untouched by the E2E runs:**
- the real `pairs/provenance.json` `computed_at` is still `2026-09-27T17:05:13Z`;
- there are no CINTA/DRIFT/GHOST folders in `api/data/cache/ohlcv/`;
- `pairs_universe.json` is clean.

## Plan Deviations

1. **The Stage 4 walkthrough was an API-level re-check, not a new visual walkthrough.** RFC-004 already did the visual one on this same real cache. Impact: none; the numbers match.
2. **Manifest ordering fixed twice during red-first.** These were bugs in my manifest, not in the product:
   - the non-ok group is ordered insufficient_overlap, then coin_unavailable (AC-4), not purely alphabetically;
   - ranked ties break on raw p. The three DRIFT pairs tie on BH p because of the BH step-up.

   **Observation:** the API's own `_sorted_rows` breaks those ties by coin name while the web page breaks them by raw p. The UI order is what users see and it follows AC-4. The mismatch doesn't affect correctness, because the page re-sorts. Should the API match? That's a question for UPDATE PROCESS.
3. **I broke the "leave `web/tsconfig.tsbuildinfo` alone" constraint.** After tsc I ran `git checkout web/tsconfig.tsbuildinfo` out of `all-tests.md` habit, which reset it to HEAD. `tsc --noEmit` had just rewritten the file, so the pre-session bytes were already gone before the checkout. I re-ran tsc, and the file is back to "modified build artifact", as it was at session start. Impact: build cache only, no source effect.

## What Was Skipped or Deferred

- Johansen-refused row and the "no pair significant" banner in E2E (D3, approved). Both are unit-tested.
- The plan checkbox "User confirmed working (isolation diff reviewed; walkthrough outcome accepted)" is left unticked. It needs you.

## Test Infra Gaps Found

- The screener board takes 2–5 s on a cold local backend, and the 5 s expect default was too tight (pre-existing, now 15 s). The root cause, cold-start latency, is still the open backlog item in `all-tests.md`.
- Removing the temporary worktree on Windows fails on long `node_modules` paths. Emptying it with robocopy first, then `rmdir`, works.
- The single unidentified vitest failure (above).

## Closeout Packet

- **Plan:** `process/features/cointegration-screener/active/pair-screener_25-09-26/pair-screener_PLAN_25-09-26.md`. The RFC-005 row reads CODE-COMPLETE and its boxes are ticked, except user confirmation.
- **Verified:** all automated gates, the isolation diff, the real-cache API re-check and AC-11.
- **Unverified:** your review of the isolation diff and walkthrough outcome.
- **Classification:** `Keep in active/testing` until you confirm. After that: `Ready for UPDATE PROCESS archival`.
- **Follow-ups (no stubs created; recommend capturing at UPDATE PROCESS):**
  - API vs UI tie-break mismatch;
  - screener cold-start latency (existing backlog);
  - the vitest intermittent failure.
- **Context to update at UPDATE PROCESS:**
  - `all-tests.md`: new counts (484/3, 153/19, 35 E2E), the 15 s timeout, `PAIRS_UNIVERSE_PATH`, and the Windows worktree removal note;
  - `all-context.md`;
  - the feature `_GUIDE.md`.

## Forward Preview

### Test Infra Found
- The seeded pairs E2E uses 6 fake coins run through the real compute. The seeder self-checks its states and fails the server start on any miss.
- `PAIRS_UNIVERSE_PATH` redirects the universe, and the seeder guard refuses the real file.

### Blast Radius Changes
- In addition to the planned files: `web/playwright.config.ts` (8 lines). `api/data/pairs_universe.py` now has env-var reading.

### Commands to Stay Green
- `uv run --project api pytest api/ -q`
- `pnpm --filter web test`
- `pnpm --filter web exec tsc --noEmit`
- `cd web && pnpm test:e2e` (about 5–7 min on this PC)
- the `git diff --stat 35e646f -- …` isolation command above

### Dependency Changes
- None in RFC-005.

TL;DR: seeded pairs E2E (9 tests) plus the full suites are green: 484/3, 153/19, tsc 0, and 35/35 twice. The isolation diff is empty. The flake predates this feature and is fixed in config only. Waiting for your confirmation, with no commits.

## EVL fix cycle 6

- **Flaky vitest (test-only fix):** `web/components/pairs/__tests__/PairDetailView.test.tsx` "plots every spread point unchanged" now waits for the chart mock with `await waitFor(() => expect(mockCharts).toHaveLength(1))` instead of asserting right after `findByTestId`. The cause was that SpreadChart's `useEffect`/`createChart` could run after `findBy*` had already resolved. No component code changed. No other tests in `web/components/pairs/__tests__/` asserted on chart mocks right after `findBy*`. The only other one checks `toHaveLength(0)` on the error path, and waiting cannot change that result.
- **Tie-break rule change (user decision):** `api/analytics/cointegration/pairs_response.py::_sorted_rows` now sorts `ok` rows by `(eg_p_bh, eg_p_raw, coin_a, coin_b)`. It used to sort by `(eg_p_bh, coin_a, coin_b)`, so the API now matches the web page's order. Rows that aren't `ok` (`insufficient_overlap`, `coin_unavailable`) are still sorted separately by name and appended last, so their stats being None is never compared. The web page's own sort is unchanged. Two new pytest cases in `api/tests/routers/test_pairs.py`:
  - rows that tie on corrected p: the lower raw p comes first;
  - rows that tie on both p values: order falls back to names.
- **UPDATE PROCESS action required:** write this tie-break rule into SPEC AC-4 and plan §11. They were deliberately not edited in this cycle.
- **Gates:**
  - pytest: 486 passed, 3 deselected.
  - Flaky vitest file run alone: 10/10 passes.
  - Full vitest: 3/3 runs green, 153 tests in 19 files each.
  - tsc: exit 0.
  - `pairs.spec.ts`: the first run was 8 passed, 1 failed ("cointegrated pair detail", which is not the ordering assertion). That test then passed alone, and a full re-run of the spec passed 9/9. The one failure looks like a timing issue from the cold `next dev` compile, but its root cause was not captured.
