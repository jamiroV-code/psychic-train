# T36 / S4 worker report: staged verdict removal (screener-batch2, batch 2)

Branch `claude/t36-s4-verdict-removal`, from `main` 766e6a3. Lane: direct, RT3.

## 1. Status

`review`. Commits A and B are done, and every G-S4 gate passes at its own commit. The hybrid E2E (G-S4-10) also ran and passed. P-S4-1, the real-stack check on the user's PC, has not been run and stays open for the user (AC-S4-8).

## 2. Summary

- **Commit A** (`ad1d956`, 31 files) removes the verdict from the screener contract and page:
  - `CoinPanel` loses `momentum`, `trend`, `confidence`, the leg reading and the narrative reading.
  - `ScreenerBoardResponse` loses the benchmark field.
  - `/api/screener/{symbol}/scalp` is replaced by `/api/screener/{symbol}/chart`. It returns `ChartView {symbol, timeframe, chart}` with a default timeframe of `4h`.
  - The board build no longer reads leg-boundary or narrative state, so there are no inline pytrends, Reddit or CoinGecko calls on a cache miss.
  - On the web side, the TS mirror and the client change in lockstep (`fetchChartView`). `CoinPanel`, `ScreenerBoard` and `DrillDownView` drop the verdict UI, and the screener page renders only the board and the relative-performance chart.
  - The four verdict components are deleted with their tests. The narrative contract golden drops its screener blocks (Q1 = A).
- **Commit B** (`f4e814c`, 24 files) deletes the verdict backend:
  - RSI moves to `indicators/rsi.py` and SMA to `indicators/sma.py`.
  - `momentum.py`, `trend.py`, `confidence/` and `regime/benchmark.py` are deleted. The verdict types and literals leave `models/screener.py`.
  - `/api/regime/legs` drops its benchmark-reason field.
  - The CSS rules and the home blurb are cleaned.
  - A symbol gate (`test_no_verdict_symbols.py`) now keeps the removed names out of `api/` and `web/`.

## 3. Commits

| Commit | SHA | Files | Notes |
|---|---|---|---|
| A | `ad1d956` | 31 | Matches the plan's 31 touches. |
| B | `f4e814c` | 24 | The plan estimated 22. The extra file is `api/tests/routers/test_screener.py`: its B edit (import `SMA_LENGTH` from `sma`) is in the plan's break table but was not counted in B's touch list. The report goes in a separate docs commit so the gate SHAs above stay valid. |

## 4. Files changed

All files are inside Owned, and the S4-scope gate printed nothing at A and at B. No change touches CLAUDE.md, AGENTS.md, README.md, `.claude/`, `.github/`, `deploy/` or `api/scripts/`. Only one fixture changed: `api/tests/routers/fixtures/narrative_categories_contract.json` (Q1). FIXTURE-EQ shows that the only difference from origin/main is the removed blocks.

## 5. Tests

**Commit A**

- New: `test_screener_no_verdict_contract.py` (6 tests) and `web/lib/__tests__/screener-api.test.ts` (2 tests).
- Deleted: `test_screener_integration.py` (4 tests) and the four component suites (20 tests).
- Edited, as listed in the plan's break table:
  - `test_screener.py`: verdict asserts and leg/narrative patches dropped; `build_chart_view` asserts price, sma and freshness.
  - `test_screener_freshness_payload.py`
  - `test_screener_gain_contract.py`
  - `test_board_integration.py`: `test_chart_view_populated`.
  - `test_narrative_categories_contract.py`: third test deleted.
  - `ScreenerBoard.test.tsx`: test 1 asserts per-coin chips; test 2 asserts charts switch and that no verdict text appears.
  - `DrillDownView.test.tsx`: scalp-label test deleted, plus the line-110 assertion.
  - `RelativePerformanceChart.test.tsx`: comment only.
  - `screener.spec.ts`: test 6 waits for `/api/screener/BTC/chart`.
  - `narrative.spec.ts`: the strip test and the ordering note deleted.

**Commit B**

- New: `test_rsi.py` (2 tests; the golden test moved, plus `test_compute_rsi_returns_none_below_length`) and `test_no_verdict_symbols.py` (2 tests).
- Deleted: `test_momentum.py`, `test_confidence_badge.py` and `test_benchmark.py`.
- Edited:
  - `test_sma.py`: imports from `sma`; the two trend tests are deleted; the insufficient-history test asserts `None`.
  - `test_regime.py`: still 3 tests; one is renamed `test_confirmed_boundary_is_passed_through_to_the_response`.
  - `test_lse_adapter.py`: import line only.
  - `test_screener.py`: import line only.

No existing test broke outside the plan's table.

## 6. Gates (SHA and UTC)

Baseline at `766e6a3`, before any edit: pytest 963 passed, 2 skipped, 5 deselected. vitest 245 passed in 33 files. Both match the envelope.

**Red-first runs**

| Run | SHA / tree | UTC | Result |
|---|---|---|---|
| G-S4-1, stubs (`NotImplementedError`) | `766e6a3`, untouched | 06:19:50Z | 6 failed |
| G-S4-1, real tests on the base code (A changes stashed) | `766e6a3` | 06:23:19Z | 6 failed. Includes the three named behavioural reds: `test_coin_panel_has_no_verdict_fields`, `test_scalp_route_is_gone_...` (`/chart` returned 404) and `test_board_build_makes_no_leg_boundary_or_narrative_call`. |
| G-S4-2, stubs on the A tree | `ad1d956` | 06:29:33Z | Red: collection error, because `indicators/rsi.py` does not exist at A. |
| `test_no_verdict_symbol_in_api_or_web_source` before the CSS edit | B tree, uncommitted | about 06:31Z | Failed: 13 hits for `confidence-badge` and `signal-detail-panel` in `globals.css`. This is the named B behavioural red. |

**Commit A gates** (`ad1d956`, each run once after A's last edit)

| Gate | UTC | Result |
|---|---|---|
| G-S4-1 | 06:26:41Z | 6 passed |
| G-S4-3 | 06:31:26Z to 06:35:52Z | 964 passed, 2 skipped, 5 deselected, 0 xfailed. Run on a detached checkout of `ad1d956`; see the note below. |
| G-S4-4 | 06:26Z | 226 passed in 30 files |
| G-S4-5 (tsc) | 06:27Z | exit 0 |
| G-S4-6 (islands) | 06:27Z | exit 0 |
| G-S4-7 (`diff --check`) | 06:27Z | exit 0, no output |
| G-S4-8 (S4-scope, FORBIDDEN, S-secret-scan) | 06:27Z | all printed nothing |
| G-S4-11 | 06:28Z | 95 passed, 1 skipped, 0 failed |
| G-S4-12 | 06:28:23Z | FIXTURES printed exactly the one sanctioned path; FIXTURE-EQ printed nothing |

Note on G-S4-3 at A: a first full run started at 06:26:40Z on the working tree. B edits began while it was still running, so that run (964 passed) was discarded and G-S4-3 was re-run on a clean detached checkout.

**Commit B gates** (`f4e814c`, each run once after B's last edit)

| Gate | UTC | Result |
|---|---|---|
| G-S4-1 | 06:36:01Z | 6 passed |
| G-S4-2 | 06:37:37Z | 22 passed, 1 skipped (2+3+2+15, plus `test_probe_fixture_parses` skipped) |
| G-S4-3 | 06:37:40Z to 06:42:05Z | 929 passed, 2 skipped, 5 deselected, 0 xfailed |
| G-S4-4 | 06:36Z | 226 passed in 30 files (unchanged from A) |
| G-S4-5 (tsc) | 06:36Z | exit 0 |
| G-S4-6 (islands) | 06:36Z | exit 0 |
| G-S4-7 (`diff --check`) | 06:36Z | exit 0, no output |
| G-S4-8 (S4-scope, FORBIDDEN, S-secret-scan) | 06:36Z | all printed nothing |
| G-S4-9 (S4-verdict) | 06:37Z | printed nothing |
| G-S4-10 (hybrid E2E: `screener.spec.ts` and `narrative.spec.ts`, Gate convention 4) | 06:42Z to 06:44:05Z | 24 passed |
| G-S4-11 | 06:37Z | 95 passed, 1 skipped, 0 failed |
| G-S4-12 | 06:37:37Z | same as at A |

**Count deltas match the plan's arithmetic**

| Suite | Plan formula | Expected | Observed |
|---|---|---|---|
| pytest at A | 963 - 4 - 1 + 6 | 964 | 964 |
| pytest at B | 964 - 19 - 6 - 12 + 2 - 2 + 2 | 929 | 929 |
| vitest | 245 - 20 - 1 + 2 | 226 in 30 files | 226 in 30 files |

## 7. Deviations

1. **No route-table check in `test_scalp_route_is_gone_and_chart_route_serves_the_drill_down`.** I first wrote it to inspect `app.routes`. The routers are mounted in a way that list does not flatten, so it showed only `/api/health` and the docs routes. The test now proves the change over HTTP instead: `/scalp` returns 404, and `/chart` returns 200 with exactly `{symbol, timeframe, chart}`, defaulting to `4h` and honouring `timeframe=1h`. This cost one fix cycle on that test.
2. **Fetch order in `build_coin_panel`.** It still fetches 1d and 1w first, then the other timeframes, as before. The now-unused daily/weekly momentum and trend computation is gone.
3. **`refresh_worker.py` line 4.** It reads "board and chart reads are cache-only", as the plan dictates. Relative-performance reads are still cache-only in code; the plan drops them from the comment on purpose (S6 scan).
4. **Vitest stubs.** The vitest file `screener-api.test.ts` was written directly, without a `throw` stub run. Gate convention 5 ties the recorded red run to the slice's first gate (G-S4-1, pytest), and that red run is recorded above.

## 8. Risks and open items

- **Deploy together.** Web and API must ship together: `/scalp` has no alias (C2). An old web build against the new API would 404 on the drill-down.
- **Breaking change to `/api/regime/legs`.** It no longer returns its benchmark-reason field (C4). No consumer is left in the repo; the deleted leg strip was the only one.
- **Allow-listed names.** `api/analytics/narrative/mapping.py` and `api/scripts/seed_e2e_cache.py` still carry one removed name each, and both are allow-listed. `test_allow_list_entries_still_match_something` fails if either entry goes stale.
- **Out-of-scope docs.** Process docs (completed plans, the UI audit, data-sources context) still describe the verdict. They are outside Owned and were not touched.

## 9. Probe handoff (P-S4-1, the user's PC)

Run the stack against the real cache, open `/screener` and check four things:

1. The page shows no leg or narrative strip, no benchmark label, and no momentum, trend or confidence element.
2. Each coin panel shows only its chart, its freshness caption and the 5 gain chips.
3. "Drill down" opens the dialog. It issues `GET /api/screener/<SYM>/chart?timeframe=4h`, the timeframe toggle refetches, and Close dismisses the dialog.
4. The home page blurb reads "Price charts and gain chips across the watchlist."

## 10. Budget

- About 70 tool calls and about 30 minutes of wall time.
- 3 full pytest runs counted as gates (baseline, A clean, B). One extra full run was discarded (see heading 6).
- No subagents spawned.
- CI polls are not counted here. The PR's CI result goes to the planner in the PR thread.

## 11. Docs opened and lane

- **Opened:** CLAUDE.md (session load); the task envelope; plan lines 39, 41-44, 52, 54-61, 93-136, 280-289, 305, 307-318, 355-372, 385-389 (re-derived with `grep -n '^## \|^### '`, unchanged).
- **Not opened:** operating-instructions.md and master-planner.md. Because master-planner.md was not opened, these heading names are inferred from the envelope ("11 headings; 6 = gates with SHA and UTC") rather than copied from its section 9 template.
- **Lane:** capped, with 0 subagents used (cap 3 sonnet, 15 USD).
