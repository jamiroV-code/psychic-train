---
name: report:pair-screener-rfc-005-stage0
description: "RFC-005 Stage 0 — E2E fixture design, universe redirection, pairs.spec test list, gate commands, Playwright baseline on this PC"
date: 28-09-26
metadata:
  node_type: memory
  type: report
  feature: cointegration-screener
  phase: RFC-005-stage0
---

# RFC-005 Stage 0 — E2E + isolation proof: design and baseline

**Bottom line:** the design below is feasible. All designed row states except "Johansen refused" can be produced through the real compute path. However, the Playwright baseline on this PC is **22/26, not 26/26**. Four `screener.spec.ts` tests time out when the whole suite runs. The same spec passes 6/6 when run alone. Four decisions below need your approval before Stage 1.

Plan: `pair-screener_PLAN_25-09-26.md` §RFC-005. Worktree: `my_project-main` @ `9cc5a7d`. No code was written and nothing was committed.

## 1. Playwright baseline (run on this worktree, 28-09-26)

| Run | Result | Time |
|---|---|---|
| `cd web && pnpm test:e2e` (full, 26 tests) | **22 passed / 4 failed** | 6.8 min |
| `pnpm test:e2e e2e/screener.spec.ts` (alone) | **6/6 passed** | 1.4 min |

- **Failing tests** (all in `screener.spec.ts`: board renders, timeframe switch, thin symbol, drill-down): each fails `expect(getByTestId('coin-panel-…')).toBeVisible()` at the default **5 s** timeout.
- **Cause (probed):** I ran uvicorn directly on the seeded cache. `GET /api/screener/board?timeframe=1d` returned 200 in 2.2 s on the first call and 5.4 s on the second. That sits right on the 5 s limit. This matches the known "board cold-start latency" gap in `all-tests.md`. It is not a pairs regression: none of the screener files changed (see §6).
- The earlier "26/26" came from the cloud container. This is the first full run on your PC.
- Browsers were already installed (`chromium-1243`), so nothing was installed. Ports 8001 and 3100 were free.

## 2. Universe and cache redirection for E2E

- **Cache: already redirected.** `cache.py` reads `SCREENER_CACHE_ROOT` at import. The helpers `pairs_results_path`, `pairs_provenance_path` and `pairs_spread_path` are all built from `CACHE_ROOT`. So once `playwright.config.ts` sets that variable, results, provenance and spreads all live in `%TEMP%/screener-e2e-cache/pairs/`.
- **Universe: NOT redirected yet.** `pairs_universe.default_universe_path()` always returns the real `api/data/pairs_universe.json`. No env override exists, even though the plan names `PAIRS_UNIVERSE_PATH`.
- **Proposed (Stage 1):**
  1. `default_universe_path()` honours `PAIRS_UNIVERSE_PATH`, read at call time. This follows the "never bind at import" note already in that module.
  2. `playwright.config.ts` `apiEnv` gains `PAIRS_UNIVERSE_PATH = <E2E_CACHE_ROOT>/pairs_universe.json`.
  3. The seeder refuses to run if the variable is unset or resolves to the real file, the same guard pattern as `_guard()`.
  4. `api/data/pairs_universe.json` itself is never edited.

## 3. Fixture design

**Approach: seed OHLCV, then call `pairs_response.compute_and_persist()`, which is the production path (plan-preferred).**
- **Why this approach:** building results rows by hand would duplicate the `_row`, BH and provenance logic, and it risks the "fixture writer versus reader contract" failure described in Standing Lesson 7.
- **Freshness:** calling the real compute path also guarantees `computation_status == "fresh"`, because the provenance it writes matches the seeded cache.
- **OHLCV writes:** `cache.write_ohlcv(sym, "1d", df)`, the same function the adapter uses.
- **Timeframe:** only `1d` is seeded.

**Universe (6 fake tickers, 15 pairs).** None of these overlap with the screener seed (BTC/ETH/THIN/HYPE), so the screener fixture is unchanged.

| Ticker | Construction (log price, 900 daily bars ending today) |
|---|---|
| `CINTA` | random walk (`base`) |
| `CINTB` | `0.5 + 0.8·base + AR(0.80)` noise, which makes it strongly cointegrated with CINTA |
| `WEAKB` | `0.2 + base + AR(≈0.975)` noise, weakly cointegrated. This is the raw-only target |
| `DRIFT` | `base + explosive x`, where `x_t = 1.006·x_{t-1} + ε`. This is the not-mean-reverting target |
| `SHORT` | random walk, only **200** bars (below `MIN_OVERLAP_DAYS` = 365) |
| `GHOST` | in the universe, **no cache file** |

**Expected row states, and how I know.** I checked each state with a scratchpad probe calling the real `stats.compute_pair_stats` and `bh_adjust`. The probe code is not in the repo.

| Target | Pair(s) | Probe evidence |
|---|---|---|
| `coin_unavailable` (AC-12) | GHOST × all 5 others | status `coin_unavailable`, reason `GHOST: no usable cached daily closes` |
| `insufficient_overlap` | SHORT × CINTA/CINTB/WEAKB/DRIFT | status `insufficient_overlap`, reason "only 200 days …, need 365" |
| Significant after BH | CINTA–CINTB, CINTB–WEAKB | raw p ≈ 1e-8 / 5e-5 range, BH < 0.05, half-life computed (3.9 d) |
| Raw-only tag | CINTA–WEAKB (tuned) | AR φ 0.975 gives raw p 0.025–0.048 on several seeds. BH ≈ 2× raw at rank 3 of 6, so it lands ≥ 0.05. The seed gets pinned in Stage 1 |
| `not_mean_reverting` | CINTA–DRIFT | rate 1.006: 3 of 3 seeds gave `not_mean_reverting` (AR(1) β = +0.0016 to +0.0073) |
| EG / Johansen disagree (AC-6) | CINTA–DRIFT, CINTB–DRIFT | EG p ≈ 0.8–0.99 (not significant) but Johansen trace ≈ 139 > 15.49 (rank ≥ 1). Occurred naturally |
| Johansen **refused** | — | **Not reachable naturally.** The refusal needs complex eigenvalues with an imaginary part above 1e-9, and 0 of 153 real pairs showed it (RFC-002). See Decision D3 |

**Guarantees built into the seeder (Stage 1):**
- After `compute_and_persist()`, the seeder reads the results back and **asserts every designed state**. If any state is off, it exits non-zero, which fails the Playwright webServer start. A wrong fixture can never produce a green run.
- The seeder writes the actual facts into `web/e2e/.fixture-manifest.json` under a `pairs` key: pair count, the status per pair, the ok-row order by BH p, the raw-only pair, the not-mean-reverting pair, the disagree pair, and the sample-window start/end for the chart-range check. The spec reads expectations from there and never retypes numbers (the narrative-spec convention).
- A new `api/tests/scripts/` test covers the seeder's pairs section and the `PAIRS_UNIVERSE_PATH` override.
- Pattern: `build_pairs_fixture(today)` + `seed_pairs(today)` in `seed_e2e_cache.py`, the same as regime and narrative. There is no second seeder.

**Stale scenario:** only one results file exists per run, so fresh and stale cannot both be seeded. See Decision D2.

## 4. `web/e2e/pairs.spec.ts` — test list

1. `/pairs` loads from a real `/api/pairs` request. No status banner is shown (fresh). The significance banner reads "N of 6 pairs are significant after correcting for 6 tests". There is no error or empty state, and zero console errors.
2. The table shows all 15 rows (manifest `pair_count`).
3. Default order: ok rows sorted by BH p ascending, matching the manifest order. Non-ok rows are grouped at the bottom.
4. The raw-only tag appears on exactly the manifest's raw-only pair and on no other row.
5. The `insufficient_overlap` rows show their reason and no stats (—). The `coin_unavailable` rows show the GHOST reason.
6. The detail page for CINTA/CINTB (reached by clicking the row link) shows:
   - the spread chart;
   - chart range text equal to the sample-window text and to the manifest dates (AC-7);
   - both EG directions;
   - the Johansen block;
   - the computed half-life and z-score;
   - the disclosure.
7. The detail page for CINTA/DRIFT shows the `not_mean_reverting` box with no half-life number, and Johansen and EG disagreeing, both visible (AC-6).
8. `/pairs/CINTA/NOPE` shows the 404 message from the API `detail` text.
9. `/pairs/CINTA/CINTA` shows the 422 self-pair message.
10. *(if D2 = yes)* stale banner shown with the reason text verbatim.
11. *(if D2/D3 = yes)* the other banner wording ("No pair is significant … Closest: …") and a Johansen-refused reason.

## 5. Gate commands (from `all-tests.md` + the plan's validate contract)

```
uv run --project api pytest api/ -q                  # expect 475 passed / 3 deselected + new seeder tests
pnpm --filter web test                               # expect 153 passed / 19 files
pnpm --filter web exec tsc --noEmit                  # then: git checkout web/tsconfig.tsbuildinfo
cd web && pnpm test:e2e                              # 26 existing + ~9-11 pairs, run twice
git diff --stat 35e646f -- api/routers/screener.py api/data/watchlist.py web/app/screener/ api/analytics/regime/   # must be empty
```

## 6. Preliminary isolation check (read-only, today)

- The `git diff --stat 35e646f` on the four hard-excluded paths, plus `screener.spec.ts`, `screener_board.py` and `ccxt_adapter.py`, returned **empty**.
- The non-pairs files that did change are the expected ones:
  - `cache.py`: one line extends the bootstrap subdir list with `"pairs"`, and the `pairs_*` helpers are additive;
  - `main.py`: one import-line change plus the router include;
  - `pyproject.toml` and `uv.lock`: statsmodels;
  - `web/app/page.tsx`: the link;
  - `tsconfig.tsbuildinfo`: a build artifact.
- Stage 1 will additionally touch `pairs_universe.py`, `seed_e2e_cache.py` and `playwright.config.ts`, all outside the excluded set.

## 7. Decisions needing your approval

- **D1 — The screener timeout flake (blocks "all green, run twice").** `screener.spec.ts` is on the RFC-005 "zero edits" list, so the fix cannot go in the spec. Options:
  - **(a) Recommended:** in `playwright.config.ts`, add a one-line global `expect: { timeout: 15_000 }`. Assertion logic is unchanged, and it affects waits only.
  - **(b)** Pre-warm the board, for example by pointing the API webServer `url` readiness check at `/api/screener/board?timeframe=1d`.
  - **(c)** Change nothing and record the flake as a known gap, proving the screener with a separate solo run.
- **D2 — Stale banner.** Use Playwright `page.route` to serve the real seeded response with `computation_status: "stale"` and a reason. This checks UI wiring only, and the report would label it that way, not as a boundary proof.
  - **Recommended: yes, as one labelled test.** The real stale detection is already covered by pytest (RFC-003).
  - Alternative: skip, since vitest already covers the banner.
- **D3 — Johansen-refused row and the "no pair significant" banner wording.** Neither can occur in the real seeded run.
  - **Recommended: skip in E2E** and rely on the existing vitest and pytest coverage.
  - Alternative: route-mock them like D2.
- **D4 — Adding `PAIRS_UNIVERSE_PATH`** to `pairs_universe.py` (a small additive edit plus a test) and to `playwright.config.ts`. The plan names this mechanism, but the variable does not exist yet. **Recommended: approve.**

## Not run in Stage 0

- The full pytest and vitest suites were not run in Stage 0. Their baselines (475/3, 153/19) are taken from the RFC-004 records and get re-run in Stage 3.
- The real-cache walkthrough (Stage 4) will run on this PC, which is your own machine. Whether Hyperliquid is reachable gets recorded then.

TL;DR: fixture design is proven feasible through the real compute path (all states except Johansen-refused). Universe redirection needs a new `PAIRS_UNIVERSE_PATH`. The baseline is 22/26 because of a 5 s timeout flake in `screener.spec.ts` (it passes 6/6 alone). Approve D1–D4 to start Stage 1.
