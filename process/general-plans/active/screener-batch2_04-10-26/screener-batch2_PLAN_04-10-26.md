---
name: plan:screener-batch2
description: "Screener realignment batch 2: S4 verdict removal (staged, one worker, two ordered commits), S6 chart zoom/pan/sharpness plus spaghetti chart, S7 BTC leg chart with the D-14 estimate label plus the /api/regime/legs cache-only fix. Sequential S4 then S6 then S7; S5, S9, S10 are later"
date: 04-10-26
feature: general-plans
---

# Screener Batch 2: Verdict Removal, Chart Interaction, Spaghetti and BTC Leg Chart (S4, S6, S7)

Date: 04-10-26
Status: PLANNED, not yet validated (PLAN written 04-10-26 against origin/main 605424d; nothing executed). Needs VALIDATE, then the user's explicit ENTER EXECUTE MODE.
Complexity: COMPLEX (S4 first, then S6, then S7, strictly sequential; RT3 response models, shared chart island, regime router)

**TL;DR:** S4 deletes every verdict (confidence badge, momentum/trend/scalp, benchmark label, both strips) in one worker with two ordered commits: A = API and web contract plus web consumers, B = dead backend code, CSS and copy; 53 file touches, under the 100 limit, so no split. S6 gives every chart Ctrl/Cmd+wheel zoom, pinch, drag pan, double-click reset, crisp SVG axis text, and replaces the relative-performance chart by the spaghetti chart. S7 adds the BTC leg chart (confirmed legs over all cached BTC history) with the D-14 estimate label and fixes the inline BTC fetch in `/api/regime/legs`. Estimate 9-19 USD [estimate] against about 27.4 USD left. Six questions need the user (see "Open questions for the user"). A worker reads its slice section, "Decisions locked", "Gate conventions", its criteria rows, gates and scope commands (fine line ranges at the end).

Sources: SPEC `personal-tracker-realignment_SPEC_02-10-26.md` (D1-D11, F1-F5, AC-1..23, AC-26), INNOVATE `..._INNOVATE_03-10-26.md` (A-H, slice table), decisions.md D-14, batch-1 plan and its slice reports and PVL iterations 001-003, `process/context/{current-state,architecture}.md`, `process/context/tests/all-tests.md`, operating-instructions.md (RT tiers). Router: `process/context/all-context.md`. Real code read at origin/main 605424d (working tree equals it for api/ and web/).

Context Envelope: general-plans | PLAN | batch 2 | claude/pensive-albattani-ou0cgv | /home/user/psychic-train | tests | api/, web/ | this file | pytest then vitest | contract PENDING.

## Overview

Goal: a screener that shows numbers and charts only (no verdicts), whose every chart zooms, pans and reads sharply, with one spaghetti comparison chart and one BTC leg chart. Scope: S4, S6, S7 plus S8 open item (a). Non-goals: layout, groups, 30-cap, RSI display (S5, see Q2), equities page (S9), scheduled task (S10), any change to `deploy/**`, `api/scripts/**`, `lse_adapter.py`.

## Name check against INNOVATE / SPEC / batch-1 reports (real code read 04-10-26)

| INNOVATE / SPEC / report says | Actual code | Plan consequence |
|---|---|---|
| S4 "~20 source + ~12 test files" | measured: 42 tracked api/web files hold verdict tokens; S4 touches 53 files (27 source, 26 tests incl. one fixture) | one worker, two commits (C1) |
| drill-down keeps price chart and RSI; scalp view dropped | the drill-down fetches `/api/screener/{symbol}/scalp`, which returns the chart AND the scalp verdict | new `GET /api/screener/{symbol}/chart` replaces it (C2) |
| D1 drops `select_active_benchmark` | it also feeds `active_benchmark_reason` on `/api/regime/legs`; only consumer is `LegTimelineBanner` | field dropped (C4) |
| INNOVATE E "`/api/regime/legs` unchanged" | S4 changes it by that one field; S7 adds a new endpoint | stated in C4 |
| S4 stage 3 "delete analytics modules" | `compute_rsi` (momentum.py) is imported by `test_lse_adapter.py`; `compute_sma` is drawn data | kept in new `rsi.py`, `sma.py` (C3) |
| AC-2 old relative-performance chart is a screener deletion | it is the only multi-coin chart; no replacement exists before S6 | deleted by S6, not S4 (C5) |
| D6 spaghetti "same bars as the board" | board charts show 15m/1h/4h 120-200 bars, 1d all (500+), 1w all (~72) | spaghetti caps (C5, Q3) |
| D4 "all BTC daily history" | BTC 1d cache is 500 bars unless the user ran `backfill_pairs_universe` (`api/scripts/BOOTSTRAP.md` section 6); boundaries older than the first BTC bar cannot be confirmed | chart states its span (C7, Q6) |
| S8 open (a) "`/api/regime/*` fetches BTC 1d inline" | only `leg_boundary.py:164` (via `/legs`); `/components` makes no OHLCV call | S7 wraps `/legs` and `/btc-legs` (C8) |
| S2 report: rightmost tick label clips | `04 Oc` seen in the spike | S6 fixes with a bbox gate |

## Decisions locked for this batch

- **C1 S4: one worker, two ordered commits.** A = API and web contract, web consumers, 4 dead web components deleted, tests (31 touches); B = RSI/SMA relocation, dead backend modules deleted, regime field, CSS, copy, symbol gate (22 touches). Each commit passes all gates alone (A leaves `badge.py`, `momentum.py`, `trend.py`, `benchmark.py` present, unused and green). Measured 53 touches, below the 100 split threshold.
- **C2 Drill-down.** `GET /api/screener/{symbol}/chart?timeframe=` (default `4h`) returns `ChartView {symbol, timeframe, chart: ChartSeries}` and replaces `/scalp` (no alias; deploy web and API together). Builder `build_chart_view`; TS `fetchChartView`; prop `fetchChart` on `ScreenerBoard` and `DrillDownView`; the scalp reading is deleted and nothing replaces it (RSI: Q2).
- **C3 Indicators.** `rsi.py` keeps `compute_rsi`, `RSI_LENGTH`; `sma.py` keeps `compute_sma`, `SMA_LENGTH`; `momentum.py` and `trend.py` are deleted in B. `ChartSeries.sma` stays (plain SMA-60 line).
- **C4 Regime.** `/api/regime/legs` loses `active_benchmark_reason` in B (D1: the rule that wrote it is deleted, its only consumer is deleted). `test_regime_components.py::test_legs_shape_unchanged` compares with `model_fields` and stays green.
- **C5 Spaghetti (S6).** `GET /api/screener/spaghetti?timeframe=` returns `SpaghettiResponse {timeframe, window_cap_bars, server_time, series[], references[]}`. Window = the last `N` bars of the coin's own frame for that timeframe: `N` = 200 for 15m/1h/4h/1d, 28 for 1w (Q3 for 1d). A coin is available iff its frame has at least 60 bars (the board chart's own rule, `sma.SMA_LENGTH`); otherwise `available=false` with `reason` (`insufficient-history`, `bad-symbol`, `source-unavailable`), never a flat line. `pct = (close - first window close) / first window close x 100`, so every line starts at 0. BTC and HYPE are always in `references` (not in `series`), whether or not they are on the watchlist. Each entry: `symbol, available, reason, points[ChartBar with Z timestamps], window_start, window_end, bars, last_bar_ts, stale`. `GET /relative-performance`, its models, `build_relative_performance`, `RelativePerformanceChart`, `relative-performance-lines.ts` and their tests are deleted in S6. No ranking, no "outperforming" text anywhere.
- **C6 Chart interaction (S6), spike first.** Pure `web/lib/chart-viewport.ts` (range math) drives the island's `xDomain`; y re-fits to the visible points. Interactions on EVERY `simple-lines` chart (coin boxes, drill-down, spaghetti): Ctrl or Cmd + wheel zooms about the pointer; plain wheel is NOT handled (the page scrolls; the wheel listener is non-passive and calls `preventDefault` only with Ctrl/Cmd); two-pointer pinch zooms; drag pans only while zoomed (touch-action `pan-y` unzoomed, `none` zoomed); double-click or double-tap (300 ms) resets; a small reset button shows while zoomed; minimum span 5 bars; the range is clamped to the data extent; zoom resets when the series prop changes. Test hooks on the plot element: `data-zoomed="true|false"`, `data-visible-from`, `data-visible-to` (Z timestamps). LayerChart `transform` replaces the custom domain code ONLY if the spike passes all six criteria in S6 step 1; otherwise the custom path stands. Axis text is drawn in an `<Svg>` layer (crisp vector text); lines stay in `<Canvas>`; if the DPR check fails the fallback is all marks in `<Svg>` (precedent `spread-chart.svelte`; `pairs.spec.ts` asserts drawn paths).
- **C7 BTC leg chart (S7).** Leg = confirmed boundary date (`LegBoundary.date`) to the next confirmed boundary; the current leg runs to the last BTC bar; the stretch before the first confirmed boundary is NOT a leg; unconfirmed candidates never start a leg. Bars = every BTC `1d` bar in the cache; the payload states first bar, last bar and count. Estimate (D-14), heading exactly `Estimate (rule over the numbers shown)`, two independent labels, never merged: AGE = `age_days / median_days` of the earlier completed confirmed legs: `early` below 1/3, `mid` below 2/3, `late` otherwise; needs at least 3 earlier legs, else N/A with the count. COMPOSITE = 14-point change of the composite (`diff(periods=ROC_WINDOW_DAYS)` as `leg_boundary`): `rising` at or above +T, `falling` at or below -T, else `flat`, with `T` = 0.5 x the standard deviation of all historical 14-point changes (Q5); `T`, the std, `n` and the composite date are shown. Label sets are closed enums.
- **C8 Regime cache-only (S7).** `GET /api/regime/legs` and the new `GET /api/regime/btc-legs` run inside `refresh_worker.reads_cache_only_if_running()`. BTC `1d` empty or unavailable gives `available=false` with a reason, never zero legs.
- **C9 Payload conventions.** New payload timestamps are ISO UTC with seconds and a trailing `Z` (also on `ChartBar` points of the new endpoints); dates stay `YYYY-MM-DD`. Python models and TS interfaces are mirrored by hand and each has a contract test that parses the `export interface` text.
- **C10 Not changed.** Daily bars are never trimmed (only 15m/1h/4h keep 200); `lse_adapter.py`, `freshness.py` semantics, the web client 10 s timeout, `deploy/**`, `api/scripts/**` stay as merged.

## Gate conventions (all slices; batch-1 conventions kept)

1. Every pytest gate runs with `UV_FROZEN=1`. RT3 snapshot rule: `git diff --name-only --diff-filter=MDR origin/main...HEAD | grep -E '/fixtures/'` prints nothing; S4 has ONE sanctioned exception (Q1) with its own equality command.
2. Baselines at origin/main 605424d (each worker re-records at spawn): pytest 963 passed, 2 skipped, 5 deselected, 0 xfailed; vitest 245 passed in 33 files; tsc exit 0; islands exit 0. Counts in slice gates are arithmetic from the previous slice's merged result; a worker records the observed delta and stops at `needs_input` if it differs.
3. New payload timestamps: C9. Every gate run is logged in report heading 6 with SHA and UTC time; testers re-run only gates whose paths changed.
4. The seeded E2E runs with `SCREENER_REFRESH_WORKER=0` and WITHOUT `--`: `cd web && SCREENER_REFRESH_WORKER=0 PLAYWRIGHT_CHROMIUM_PATH=/opt/pw-browsers/chromium-1194/chrome-linux/chrome pnpm test:e2e screener.spec.ts` (batch 1 found that `-- file` runs every spec). Hybrid: NOT-RUN with a stated reason is allowed, then the PC probe covers it.
5. Red-first: write the slice's new tests as stubs (`raise NotImplementedError(...)` / `throw new Error(...)`), run the first gate on the untouched base, record the red run in heading 6, then write the real tests. Behavioural reds are named per slice.
6. Hidden-break rule (batch-1 lesson): an existing test may be edited only as listed in the slice's "Existing tests that break" table; any other failing existing test stops the worker at `needs_input`. The tables come from grepping `monkeypatch.setattr(screener_board.<module>`, imports of every deleted or moved symbol, test ids and string literals in `web/e2e`.
7. Workers branch from `main`; this plan (with its validate-contract) must be on `main` before any envelope. Max 2 fix cycles per failing gate; the same failure twice stops the worker. A diff touching CLAUDE.md, AGENTS.md, README.md, `.claude/`, `.github/`, `deploy/` stops at `review`; no slice touches `deploy/**` or `api/scripts/**`.
8. No trailing whitespace: `git diff --check` exits 0 on every slice.
9. Live providers and real browsers on the PC are probes (P-*), never claimed by a worker. Known-Gap is a residual (backlog stub, gate stays CONDITIONAL), never a PASS.

## Sequencing and parallelism

Strictly sequential: S4 (commits A then B), then S6, then S7. Each branches from `main` after the previous merge; merges serialized with CI re-run (master-planner.md 5.6). S6 and S7 are NOT parallel (decision): they share five files and S7 reuses S6's viewport math.

| Shared file | S6 | S7 |
|---|---|---|
| `web/islands/simple-lines.svelte` | zoom, pan, SVG axes, DPR | bands and markers props |
| `web/lib/island-loader.ts` | new prop types | new prop types |
| `web/app/screener/page.tsx` | removes the old chart | adds the BTC leg chart |
| `web/app/globals.css` | spaghetti, reset button | leg chart, estimate panel |
| `web/e2e/screener.spec.ts` | tests 7-9 | new test |

S4 touches the same API files as S6 (`models/screener.py`, `screener_board.py`, `routers/screener.py`) and as S7 (`models/regime.py`, `routers/regime.py`, `leg_boundary.py`), so S4 is first. Max 3 workers is not used.

## Program budget

User decision 03-10-26: 45 USD ceiling, checked per slice before each spawn; 15 USD cap per slice for subagents. Spent so far 17.6025729 USD (batch-1 workers; two EVL tester runs unmetered), so 27.3974271 USD remain. Capped lane (3 subagents, 15 USD, one level) is allowed because all three slices are RT3 (response models, shared island, regime router). See the Costs table.

## Costs [estimate]

| Slice | Worker (opus) | Subagents (sonnet) | EVL tester | Total | Basis |
|---|---|---|---|---|---|
| S4 | 3-6 | 0.5-2 | 0.5-1 | 4-9 | 53 touches, 2 commits, 3 full-suite runs, 200 tool calls |
| S6 | 2-4 | 0.5-1 | 0.5-1 | 3-6 | spike, 28 touches, 2 full-suite runs, 160 tool calls |
| S7 | 1.5-3 | 0-0.5 | 0.5 | 2-4 | 18 touches, 2 full-suite runs, 120 tool calls |
| Batch 2 | | | | 9-19 | against 27.4 USD left |

After batch 2, 8.4-18.4 USD remain for S5 (3-6), S9 (1-3), S10 (3-8) = 7-17 USD: the ceiling can bind at the top of both ranges. Re-check after S4 and before each spawn; stop and ask above 15 USD for one slice or 45 USD in total.

## S4: Verdict removal, staged (RT3, capped subagent lane: yes)

**Goal:** no confidence badge, signal detail, momentum/trend state, scalp view, benchmark label, leg strip or narrative strip in the screener API or page; the drill-down keeps its chart and timeframe toggle.

**Owned, commit A:** `api/models/screener.py`, `api/analytics/screener_board.py`, `api/routers/screener.py`; `web/lib/types/screener.ts`, `web/lib/api/screener.ts`, `web/components/screener/{ScreenerBoard,CoinPanel,DrillDownView}.tsx`, `web/app/screener/page.tsx`; deleted `web/components/screener/{ConfidenceBadge,SignalDetailPanel,LegTimelineBanner,NarrativeStrip}.tsx` and their four `__tests__/*.test.tsx`; edited tests `web/components/screener/__tests__/{ScreenerBoard,DrillDownView,RelativePerformanceChart}.test.tsx`, `web/e2e/{screener,narrative}.spec.ts`, `api/tests/routers/{test_screener,test_screener_freshness_payload,test_screener_gain_contract,test_board_integration,test_narrative_categories_contract}.py`, `api/tests/routers/fixtures/narrative_categories_contract.json` (Q1); deleted `api/tests/routers/test_screener_integration.py`; new `api/tests/routers/test_screener_no_verdict_contract.py`, `web/lib/__tests__/screener-api.test.ts`.
**Owned, commit B:** `api/models/screener.py` (again); new `api/analytics/indicators/{rsi,sma}.py`; deleted `api/analytics/indicators/{momentum,trend}.py`, `api/analytics/confidence/{badge,__init__}.py`, `api/analytics/regime/benchmark.py`; edited `api/analytics/screener_board.py` (import swap), `api/routers/regime.py`, `api/models/regime.py`, `api/analytics/regime/leg_boundary.py` (docstrings), `api/data/refresh_worker.py` (comment), `web/app/globals.css`, `web/app/page.tsx` (home blurb); tests: new `api/tests/analytics/{test_rsi,test_no_verdict_symbols}.py`; deleted `test_momentum.py`, `test_confidence_badge.py`, `test_benchmark.py`; edited `test_sma.py`, `api/tests/routers/test_regime.py`, `api/tests/data/test_lse_adapter.py` (import line only); report `screener-batch2-s4_REPORT_<dd-mm-yy>.md`.
**Forbidden:** the FORBIDDEN list below, narrative-owned files (`api/analytics/narrative/**`, `api/models/narrative.py`, `web/components/narrative/**`), `api/data/{ccxt_adapter,cache,freshness,lse_adapter}.py`, S6/S7 files.

**Design, commit A:**
1. `models/screener.py`: `CoinPanel` loses `momentum`, `trend`, `confidence`, `leg_context`, `narrative_state`; `ScreenerBoardResponse` loses `active_benchmark`; delete `ScalpMomentumState`, `ScalpView`; add `ChartView`. `MomentumState`, `TrendState`, `BenchmarkSelection`, `RegimeState` and the verdict literals STAY until B (`badge.py` and `benchmark.py` still import them; deleting them breaks `import api.main`). `RelativePerformance*` stays (S6).
2. `screener_board.py`: `build_coin_panel(symbol, timeframe, now=None)` and `build_screener_board` stop calling momentum, trend, badge, narrative, `leg_boundary`, `select_active_benchmark` (an inline pytrends/Reddit/CoinGecko path on cache misses disappears); `build_scalp_view` becomes `build_chart_view`; delete `_coin_narrative_state` and dead imports; `trend_mod` stays only for `compute_sma`/`SMA_LENGTH` until B.
3. `routers/screener.py`: delete `/{symbol}/scalp`; add `GET /{symbol}/chart` inside `reads_cache_only_if_running()`.
4. `screener.ts` in lockstep: delete the verdict types, `ScalpView`, `LegBoundary`, `LegBoundaryResponse`, `LiquidityCompositeVariant`, `NarrativeCategory`, `SourceAvailability`; add `ChartView`; `api/screener.ts`: add `fetchChartView`, delete `fetchScalpView`, `fetchLegs`, `fetchNarrativeCategories`. Keep the `export interface` layout (contract tests parse it).
5. Web: `CoinPanel` drops the signal detail, `momentum-state`, `trend-direction` and the signals block; `ScreenerBoard` drops the `active-benchmark` span and uses `fetchChart`; `DrillDownView` drops the scalp reading (toggle default stays `4h`, comment fixed); `page.tsx` renders `ScreenerBoard` and `RelativePerformanceChart` only.

**Design, commit B:** `models/screener.py` deletes the types and literals A kept; `rsi.py`, `sma.py` carry the kept functions (with the `pandas_ta_classic` import comment); `screener_board.py` imports `sma`; delete the four modules; `routers/regime.py` and `models/regime.py` drop `select_active_benchmark`, `active_benchmark_reason` and stale docstring lines; `leg_boundary.py`, `refresh_worker.py` docstrings stop naming deleted symbols (the worker text says "screener reads (board, chart view, other screener endpoints) are cache-only", so S6 leaves it); `globals.css` deletes `.screener-board__benchmark`, `.coin-panel__signals*`, `.confidence-badge*`, `.signal-detail-panel*`, the two `:not(.confidence-badge)` terms and rewrites the strips comment (`section > strong` stays); `app/page.tsx` blurb: "Price charts and gain chips across the watchlist."

**Existing tests that break (exact edits allowed):**

| Test | Why | Edit |
|---|---|---|
| `test_screener.py` 111-112, 173-174, 229-230 | `monkeypatch.setattr(screener_board.leg_boundary / .narrative_trigger)` raises AttributeError | delete the six lines, the `_NO_LEG_DATA` import, the docstring paragraphs; B: line 40 imports `SMA_LENGTH` from `sma` |
| `test_screener.py` 116-137, 150, 184-194 | assert `momentum`, `trend`, `build_scalp_view` | drop verdict asserts; `build_chart_view` asserts price, sma, freshness; chip tests at 197, 218 unchanged |
| `test_screener_freshness_payload.py` 18, 45-49, 97-102 | `BenchmarkSelection`, four monkeypatches, scalp chart | delete; assert `build_chart_view("BTC", "4h").chart` freshness |
| `test_screener_gain_contract.py` 93-94 | same monkeypatch break | delete them and the `no_leg` setup |
| `test_board_integration.py::test_scalp_view_populated` | route removed | `/chart`, renamed `test_chart_view_populated` |
| `test_screener_integration.py` (4) | whole file is verdict | delete |
| `test_narrative_categories_contract.py` line 3, 83, 104-110 | all 3 tests fail: `_run_scenario` calls `_coin_narrative_state`; golden JSON holds `screener_narrative_state` | Q1 A: reword docstring, drop the key in `_run_scenario`, delete the third test, remove both `screener_narrative_state` blocks from the golden |
| `test_regime.py` (B) 19, 26-31, 45, 59, 71 | `select_active_benchmark`, `active_benchmark_reason` | drop import and three asserts; keep the 3 tests |
| `test_sma.py` (B) | imports `compute_trend`; 2 trend tests | import from `sma`; delete the two trend tests; the insufficient test asserts `compute_sma(...) is None` |
| `test_momentum.py` (B) | deleted functions | delete; its 2 RSI tests move to `test_rsi.py` |
| `test_lse_adapter.py` (B) line 15 | imports `momentum.compute_rsi` | import from `indicators.rsi` |
| `ScreenerBoard.test.tsx` 22-26, 55, 64-92, 197-207 | verdict fields, momentum asserts, `fetchScalp` | drop fields; test 1 asserts per-coin chips; test 2 asserts charts switch and no verdict element; `fetchChart` |
| `DrillDownView.test.tsx` | `ScalpView`, `fetchScalp`, scalp reading (62-76, 110) | `ChartView`, `fetchChart`; delete the scalp-label test; drop the line-110 assertion |
| `web/e2e/screener.spec.ts` ~43, 72, test 6 | `active_benchmark`, `active-benchmark`, `/scalp` | drop; test 6 waits for `/api/screener/BTC/chart` and asserts dialog and close |
| `web/e2e/narrative.spec.ts` 349-357, header 17-19 | asserts `narrative-strip` on `/screener` | delete that test and the ordering note |
| `RelativePerformanceChart.test.tsx` 124 | comment names deleted components | reword the comment |
| 4 component tests | components deleted | delete |

**Tests (names):** `test_screener_no_verdict_contract.py` (6): `test_coin_panel_has_no_verdict_fields`, `test_board_response_has_no_active_benchmark_and_keeps_freshness_fields`, `test_scalp_route_is_gone_and_chart_route_serves_the_drill_down`, `test_chart_view_carries_freshness_fields_for_every_timeframe` (1w judged on its daily bar), `test_board_build_makes_no_leg_boundary_or_narrative_call` (both patched to raise), `test_typescript_mirror_has_no_verdict_names_and_declares_chart_view`. `test_rsi.py` (2, moved). `test_no_verdict_symbols.py` (2, B): `test_no_verdict_symbol_in_api_or_web_source` (the `S4-verdict` tokens plus `confidence over direction`; roots `api/`, `web/`; `.py .ts .tsx .svelte .css .js`; skips `.venv`, `node_modules`, `.next`, `public`, `__pycache__`, itself; allow-list `{api/analytics/narrative/mapping.py: narrative_state, api/scripts/seed_e2e_cache.py: NarrativeStrip}`), `test_allow_list_entries_still_match_something`. Vitest `screener-api.test.ts` (2): `fetchChartView builds /api/screener/<SYM>/chart?timeframe=`, `lib/api/screener.ts exports no scalp, legs or narrative fetcher` (reads the file text).

**Gates:** G-S4-1..12 below. Behavioural reds on the untouched base: `test_coin_panel_has_no_verdict_fields`, `test_scalp_route_is_gone_...`, `test_board_build_makes_no_leg_boundary_or_narrative_call`; B: `test_no_verdict_symbol_in_api_or_web_source`. **Lane:** capped, yes (one `vc-tester`, one read-only reviewer sweeping deleted symbols in css, e2e ids, comments). **Budget [estimate]:** 200 tool calls, 150 minutes, 6 CI polls, 4-9 USD, 3 full-suite runs (baseline, A, B).

**Risks:** (1) a missed monkeypatch or import surfaces only in the full suite; the table comes from a grep, G-S4-9 and the full suite catch the rest. (2) Web and API must deploy together (new drill-down route). (3) `narrative.spec.ts` is narrative-owned: edit only the listed lines; a conflict with the narrative-baskets plan stops at `review`. (4) RSI leaves the API (nothing displayed it); Q2 decides where it returns. (5) The board loses a network-capable narrative call: latency only improves.
**Rollback:** revert the PR (or commit B alone); the golden JSON edit reverts with it.

## S6: Chart interaction, crisp axes and the spaghetti chart (RT3, capped subagent lane: yes)

**Goal:** every chart (coin boxes, drill-down, spaghetti) zooms, pans and resets as in C6, axis text is crisp at DPR 2, and one spaghetti chart replaces the relative-performance chart. Starts after the S4 merge SHA exists.

**Owned (exact):** `api/models/screener.py`, `api/analytics/screener_board.py`, `api/routers/screener.py` (add spaghetti; delete relative-performance); `web/islands/simple-lines.svelte`, `web/lib/{chart-viewport,spaghetti-lines}.ts` (new), `web/lib/island-loader.ts`, `web/lib/{chart-palette,format-unavailable-reason}.ts` (comments only), `web/lib/chart-time-format.ts` (only if the tick or label fix needs it), `web/lib/types/screener.ts`, `web/lib/api/screener.ts`, `web/components/chart/MiniChart.tsx`, `web/components/screener/{SpaghettiChart,ScreenerBoard}.tsx`, `web/app/screener/page.tsx`, `web/app/globals.css`; deleted `RelativePerformanceChart.tsx`, `web/lib/relative-performance-lines.ts`, `web/components/screener/__tests__/RelativePerformanceChart.test.tsx`, `api/tests/routers/test_relative_performance.py`; tests new `api/tests/routers/test_spaghetti.py`, `web/lib/__tests__/{chart-viewport,spaghetti-lines}.test.ts`, `web/components/screener/__tests__/SpaghettiChart.test.tsx`; edited `ScreenerBoard.test.tsx`, `api/tests/routers/test_board_integration.py`, `web/e2e/screener.spec.ts` (tests 7-9), `web/e2e/contrast.spec.ts` (line 121 only), `web/lib/__tests__/chart-time-format.test.ts` (only if the formatter changes); backlog stub `process/general-plans/backlog/spaghetti-toggle-persistence_NOTE_<dd-mm-yy>.md` (AC-22 residual until S5, Q4); report `screener-batch2-s6_REPORT_<dd-mm-yy>.md`.
**Forbidden:** the FORBIDDEN list below, S7 files, `api/data/**`, `api/models/regime.py`, `api/routers/regime.py`, `refresh_worker.py`, other islands (`regime-panel`, `narrative-panel`, `onchain-*`, `spread-chart`, `panel-sync`).

**Design:**
1. **Spike first (before any Svelte edit; 30 minutes, record in report heading 9 with PNGs read at DPR 2, `deviceScaleFactor: 2`).** (a) LayerChart `transform` is adopted only if ALL hold: Ctrl/Cmd+wheel zooms and plain wheel does not; drag pans; double-click resets; the visible domain is readable so `utcAxis` ticks follow and y re-fits; two-pointer pinch works under touch emulation; it composes with an `<Svg>` axes layer plus a `<Canvas>` lines layer. Any failure: custom path. (b) layers: `<Svg>` axes plus `<Canvas>` marks in one `Chart` (axis `<text>` nodes inside the container, lines still painted). (c) DPR: canvas `width === round(clientWidth x 2)`; if not, set the backing store manually when `Canvas` exposes a ratio, else all marks in `<Svg>` and `screener.spec.ts` test 7's pixel counter counts drawn paths instead (the S6-owned edit).
2. `chart-viewport.ts` (pure, vitest): `zoomAt(range, fraction, factor, extent)`, `pan(range, dx, extent)`, `pinchFactor(startDist, nowDist)`, `isDoubleTap(prevTs, ts, dist)`, `shouldHandleWheel(event)` (Ctrl or Meta only), `touchActionFor(zoomed)`, clamp and 5-bar minimum.
3. `simple-lines.svelte`: viewport state, non-passive wheel listener via `addEventListener`, pointer events, reset button (`data-testid="chart-reset"`), `data-zoomed`/`data-visible-*`, `<Svg>` axes (right padding at least the half-width of the widest tick label so the last label never clips), `<Canvas>` lines, y re-fit to visible points, `utcAxis` for the visible span, optional new props are additive (`MiniChart` and the spaghetti pass `timeframe`).
4. API: `build_spaghetti(timeframe)` per C5, wrapped in `reads_cache_only_if_running()`; Z timestamps via `freshness.iso_z`; delete the relative-performance models, builder, route and constants.
5. Web: `SpaghettiChart` inside `ScreenerBoard` (follows the board timeframe; prop `fetchSpaghetti` injectable; the 8 existing `ScreenerBoard` tests pass a stub so no real fetch runs), legend of per-coin toggle buttons (`spaghetti-toggle-<SYM>`, `aria-pressed`; state in memory only, Q4), span text (`spaghetti-span`, for example `Last 28 weeks, 2026-03-23 to 2026-10-04 UTC`), per-coin unavailable note (`spaghetti-note-<SYM>`), BTC and HYPE drawn thicker in fixed palette slots (`SERIES.primary`, `SERIES.secondary`) and the other coins cycle `CATEGORICAL` minus those two; island-internal nearest-line highlight on pointer move; no ranking or comparative wording; `spaghetti-lines.ts` holds the pure builders and `formatPercentChange` moved from the deleted file.
6. `page.tsx` renders `ScreenerBoard` only (the board hosts the spaghetti); `contrast.spec.ts` line 121 `ready` becomes `[data-testid="spaghetti-legend"]`.

**Existing tests that break (exact edits allowed):**

| Test | Why | Edit |
|---|---|---|
| `test_relative_performance.py` (3) | route and builder deleted | delete the file |
| `test_board_integration.py::test_relative_performance_populated` | route deleted | `/api/screener/spaghetti`, name `test_spaghetti_populated`, same count |
| `RelativePerformanceChart.test.tsx` (9) | component deleted | delete; its legend, palette and axis-format cases are re-asserted in `spaghetti-lines.test.ts` and `SpaghettiChart.test.tsx` |
| `ScreenerBoard.test.tsx` (8 renders) | the board now mounts `SpaghettiChart` | pass `fetchSpaghetti={stub}` in every render; add the follow-the-timeframe test |
| `screener.spec.ts` test 7 (`rp-chart-container`, `rp-legend-*`) | ids removed | rewrite for `spaghetti-chart-container`, `spaghetti-legend`, reference lines; mini-chart pixel check kept (or path check on the all-SVG fallback) |
| `contrast.spec.ts` line 121 | waits for `rp-legend` | selector change only; SVG axis text now enters the contrast audit and must pass 4.5:1 |
| `chart-palette.test.ts` | parses the `--series-N` block of `globals.css` | none; do not edit that block |

**Tests (names):** `test_spaghetti.py` (8): `test_series_is_percent_change_from_each_coins_own_window_start`, `test_every_available_line_starts_at_zero`, `test_window_is_the_boards_last_bars_capped_per_timeframe` (200 and 28, span fields), `test_btc_and_hype_are_references_not_coin_lines`, `test_thin_and_failed_coins_are_explicit_no_data_never_flat_zero`, `test_payload_timestamps_are_utc_z`, `test_pydantic_fields_match_typescript_interfaces`, `test_spaghetti_read_is_cache_only_while_worker_runs`. `chart-viewport.test.ts` (10): zoom keeps the anchor date, clamps to the extent, 5-bar minimum, zoom-out stops at full range, pan moves and clamps, pan only when zoomed, pinch factor, double-click and double-tap reset, plain wheel ignored, Ctrl and Meta both zoom. `spaghetti-lines.test.ts` (5): one line per available coin, references thicker and distinct, hidden coins leave the lines but stay in the legend, unavailable coin has a note and no line, palette cycles past 8 without the reserved slots. `SpaghettiChart.test.tsx` (6): legend names, toggle, span text, unavailable note, error state (`spaghetti-error`), no comparative wording. Playwright (hybrid, `screener.spec.ts`): test 7 rewritten, test 8 `ctrl-wheel zooms, drag pans, double-click resets, plain wheel does not zoom` (reads `data-zoomed` and `data-visible-*` on a coin box and on the spaghetti), test 9 `axis text is SVG, every tick label stays inside the plot box, canvas backing store matches DPR 2` (`test.use({ deviceScaleFactor: 2 })`).

**Gates and probe:** "S6 exact gates" (G-S6-1..11, P-S6-1). Behavioural reds on the untouched base: `test_series_is_percent_change_...` (route absent), `chart-viewport` stubs; E2E tests 8-9 are red today (no handlers, canvas text).

**Lane:** capped lane yes: one `vc-tester`, one read-only reviewer (Python/TS lockstep, deleted-symbol sweep, touch-action logic). **Budget [estimate]:** 160 tool calls, 120 minutes, 5 CI polls, 3-6 USD, 2 full-suite runs.

**Risks:** (1) LayerChart facts (`transform`, layers, canvas ratio) are unverifiable offline (the scout hook blocks `node_modules`); the spike and fallbacks cover it. (2) Ctrl+wheel normally zooms the browser page; the listener is non-passive and scoped to the plot; Playwright proves the code path, phone pinch is P-S6-1. (3) SVG axis text enters the contrast audit; fix colours via existing tokens, not by exempting it. (4) 30 coin boxes each carry listeners; kept light (no timers). (5) AC-22 (toggle persistence) stays open until S5 (Q4).

**Rollback:** revert the PR; the relative-performance chart returns with it.

## S7: BTC leg chart, estimate label and regime cache-only fix (RT3, capped subagent lane: yes)

**Goal:** the screener top shows BTC daily history with confirmed legs shaded and boundary dates marked, the current-leg numbers, and the D-14 estimate; `/api/regime/legs` and the new endpoint read from the cache while the refresh worker runs. Starts after the S6 merge SHA exists.

**Owned (exact):** new `api/analytics/regime/btc_legs.py`; `api/analytics/regime/leg_boundary.py` (factor `_leg_inputs(as_of)`; `compute_current_leg_state` behaviour and its 13 tests unchanged), `api/routers/regime.py`, `api/models/regime.py` (new response models); `web/lib/types/btc-legs.ts` (new), `web/lib/api/regime.ts` (add `fetchBtcLegs`), `web/lib/btc-leg-lines.ts` (new, pure), `web/lib/island-loader.ts`, `web/islands/simple-lines.svelte` (additive `bands`, `markers`), `web/components/screener/{BtcLegChart,LegEstimate}.tsx` (new), `web/app/screener/page.tsx`, `web/app/globals.css`, `web/e2e/screener.spec.ts` (one new test); tests new `api/tests/analytics/test_btc_legs.py`, `api/tests/routers/test_btc_legs_router.py`, `web/lib/__tests__/btc-leg-lines.test.ts`, `web/components/screener/__tests__/BtcLegChart.test.tsx`; report `screener-batch2-s7_REPORT_<dd-mm-yy>.md`.
**Forbidden:** the FORBIDDEN list below, S6-owned logic (`chart-viewport.ts` is imported, not edited), `api/data/**`, `refresh_worker.py`, `liquidity_composite.py`, `api/analytics/narrative/**`.

**Design:**
1. `_leg_inputs(as_of)` returns variant, composite result, candidates, confirmations and the BTC `OhlcvResult`; it keeps `ccxt_adapter` and `liquidity_composite` referenced as module attributes so `test_leg_boundary.py` monkeypatches still apply.
2. `btc_legs.build_btc_leg_chart(as_of=None) -> BtcLegChartResponse` (C7, C8): `available, reason, server_time, composite_variant, first_bar_ts, last_bar_ts, bar_count, btc[ChartBar], boundaries[{date, z_score, confirmed_date}] (confirmed only), legs[{start, end|None, days, is_current}], current_leg{start_date, days_in_leg, composite_value, composite_as_of, change_14d, last_boundary_z, latest_candidate{date, z_score, confirmed}|None, composite_variant}|None, estimate|None`. `estimate = {heading, age{label, age_days, median_days, ratio, earlier_legs, earlier_lengths_days, rule, reason}, composite{label, change_14d, threshold, history_std, n_changes, composite_as_of, rule, reason}}`; `rule` strings are written in Python (single source).
3. `routers/regime.py`: `GET /api/regime/btc-legs`; both it and `/legs` run inside `reads_cache_only_if_running()`.
4. Web: `BtcLegChart` above the board (own fetch, injectable `fetchData`), the island with `bands` (confirmed legs, alternating two tints) and `markers` (boundary dates), `timeframe="1d"` for UTC ticks, S6 zoom/pan inherited; readouts for the current leg (`btc-current-leg-*` testids) and `LegEstimate` (`leg-estimate`, heading text exact, each input beside its label, N/A with its reason). Fallback chain for bands, decided in a short spike (record in heading 9): (1) LayerChart `Rect` marks; (2) the BTC line coloured per leg plus boundary `Rule`s; (3) markers and a legs table only (then AC-S7-3 stays at `review`).
5. No sentence anywhere states what BTC will do; the allow-listed words are exactly the six estimate labels and appear only as payload values and their rendering.

**Existing tests that break:** none expected. Must stay green unedited: `test_leg_boundary.py` (13), `test_regime_components.py::test_legs_shape_unchanged`, `test_onchain_activity_router.py::test_existing_routes_unchanged` (it only asserts the onchain route set), the S4 symbol gate. Any failure of these stops at `needs_input`.

**Tests (names):** `test_btc_legs.py` (12): `test_legs_run_from_confirmed_boundary_to_next_confirmed_boundary`, `test_stretch_before_first_confirmed_boundary_is_not_a_leg`, `test_unconfirmed_candidates_never_start_a_leg`, `test_current_leg_runs_to_last_btc_bar_with_days_golden`, `test_age_label_early_mid_late_at_exact_thirds_of_the_median`, `test_median_uses_only_completed_earlier_legs_and_needs_three`, `test_composite_change_is_the_14_point_roc_and_labels_rising_falling_flat_at_the_threshold`, `test_flat_threshold_is_half_the_std_of_historical_changes_and_is_reported`, `test_no_confirmed_boundary_means_no_current_leg_and_no_estimate`, `test_unavailable_composite_makes_composite_part_na_never_flat`, `test_unavailable_btc_history_is_unavailable_not_zero_legs`, `test_estimate_heading_is_exact_labels_are_closed_enums_and_every_input_is_in_the_payload`. `test_btc_legs_router.py` (5): `test_endpoint_shape_and_utc_z_timestamps`, `test_pydantic_fields_match_typescript_interfaces`, `test_btc_legs_read_is_cache_only_while_worker_runs`, `test_regime_legs_read_is_cache_only_while_worker_runs` (S8 open item a: a fake exchange records calls and must see none), `test_btc_legs_sources_contain_no_verdict_words` (scans the S7 python and web files for `bullish|bearish|bull|bear|buy|sell|confidence|signal|outperform|underperform|risk-on|risk-off|favorable`, case-insensitive whole words). Vitest: `btc-leg-lines.test.ts` (6): bands from legs, markers from boundaries, current leg open to the last bar, estimate text lists every input, N/A rendering carries the reason, no wording beyond the closed labels; `BtcLegChart.test.tsx` (6): heading text exact, inputs visible, N/A states, unavailable state with reason, current-leg readouts, fetch error. Playwright (hybrid, one test): chart container present; API `bar_count` equals the seeded BTC 1d count from the manifest; estimate heading exact or an explicit N/A reason; legs strictly increasing.

**Gates and probe:** "S7 exact gates" (G-S7-1..9, P-S7-1). Behavioural reds on the untouched base: `test_regime_legs_read_is_cache_only_while_worker_runs` (today the exchange is called), route absent tests.

**Lane:** capped lane yes (one read-only reviewer: estimate rule against D-14 wording, verdict-word scan; tester at EVL). **Budget [estimate]:** 120 tool calls, 90 minutes, 4 CI polls, 2-4 USD, 2 full-suite runs.

**Risks:** (1) the cache may hold only 500 BTC daily bars; boundaries before the first bar cannot be confirmed, so the chart says "BTC history from <date>, N bars" (Q6). (2) The composite series may end days before the last BTC bar; its date is shown. (3) Band drawing is unverifiable offline: the three-step fallback. (4) The estimate must stay a rule over shown numbers; the closed enums and the word scan guard it.

**Rollback:** revert the PR; `/legs` returns to inline fetching (S8 item (a) reopens).

## Later batches (not in this plan; dependencies only)

S5 layout, groups, 30-cap, and the RSI display if Q2 = S5 (needs S4); S9 equities page (S3, S5); S10 optional scheduled task, `deploy/**`, RT4, brief only (S8, R12).

## Touchpoints

Changed: the owned files of S4, S6, S7 listed in their sections (`api/{models,analytics,routers}`, `api/data/refresh_worker.py` comment only, web `lib`, `islands`, `components/screener`, `app`, e2e, tests). Read only: `api/data/{ccxt_adapter,freshness,cache}.py`, `api/analytics/regime/liquidity_composite.py`, `api/scripts/seed_e2e_cache.py` (seeded stack: 500 daily bars, 120 sub-daily, liquidity series), `web/lib/chart-time-format.ts`.

## Public Contracts

- Removed: `momentum`, `trend`, `confidence`, `leg_context`, `narrative_state` on `CoinPanel`; `active_benchmark` on the board; `GET /api/screener/{symbol}/scalp`; `active_benchmark_reason` on `/api/regime/legs`; `GET /api/screener/relative-performance` (S6).
- Added: `GET /api/screener/{symbol}/chart` (`ChartView`), `GET /api/screener/spaghetti` (`SpaghettiResponse`), `GET /api/regime/btc-legs` (`BtcLegChartResponse`); TS mirrors in `screener.ts` and `btc-legs.ts` with contract tests. All additive models default-free of verdicts; timestamps per C9.
- Security scan (STRIDE, quick): no auth, key or secret surface; read-only GETs on a Tailscale-only API; the estimate label is data-derived text with a closed enum, no user input reaches it.

## Blast Radius

About 53 files for S4, 28 for S6 (30 if the tick fix needs `chart-time-format`), 18 for S7 (RT3: response models, the shared chart island, regime router; one fixture edit). Other `fetch_ohlcv` consumers (pairs, refresh worker, scripts) are untouched. Test-count effect: pytest 963 to 929 to 934 to 951, vitest 245 to 229 to 242 to 254.

## Acceptance Criteria

Criterion table (id, behaviour, strategy, proven by, gap-resolution) is in the Validate Contract skeleton; every id is linked to its gate and to its SPEC criterion. SPEC links: AC-S4-* = AC-1, AC-2, AC-18, AC-16, D1, F5; AC-S6-* = F2, F3, AC-21, AC-22, AC-23, D6; AC-S7-* = AC-12, D4, F5, D-14, S8 item (a).

## Verification Evidence

| Gate / Scenario | Strategy | Proves SPEC criterion |
|---|---|---|
| G-S4-1, G-S4-2, G-S4-9 contract tests, symbol gate | Fully-Automated | AC-1, AC-2, AC-18 (AC-S4-1..5) |
| G-S4-3..6 full pytest, vitest, tsc, islands | Fully-Automated | no regression, AC-16 (AC-S4-6, AC-S4-7) |
| G-S4-10 E2E screener and narrative specs | Hybrid (NOT-RUN with reason allowed) | AC-1 on the page (AC-S4-3) |
| P-S4-1 PC check of the page, drill-down and routes | Agent-Probe | AC-1, F5 on the real stack |
| G-S6-1, G-S6-3 spaghetti and viewport tests | Fully-Automated | AC-21, AC-23, F2 (AC-S6-1..5) |
| G-S6-10 E2E zoom, pan, SVG axis text, DPR 2, contrast | Hybrid | F2, F3, AC-21 (AC-S6-2..4) |
| P-S6-1 PC at DPR 2 and phone pinch | Agent-Probe | F3 sharpness and F2 touch (AC-S6-3r, AC-S6-2r) |
| G-S7-1, G-S7-3 legs, estimate, router, web tests | Fully-Automated | AC-12, D4, D-14, S8 (a) (AC-S7-1..6) |
| G-S7-8 E2E leg chart | Hybrid | AC-12 on seeded data (AC-S7-3) |
| P-S7-1 PC deep history and cache-only read | Agent-Probe | D4 history depth, S8 (a) live (AC-S7-4r) |

## Risk Predictions (condensed 5-persona pass)

Security: no new secret or auth surface. Performance: the board loses a network-capable call; spaghetti reads cache-only while the worker runs; 30 coin-box listeners. Data integrity: N/A with reasons (spaghetti, estimate), `stale` per series, honest history span. User: chips and layout change as intended; web and API deploy together; Ctrl+wheel only. Maintainability: the symbol gate with a self-checking allow-list stops verdict code returning under another name.

## Implementation Checklist (atomic; one slice per worker)

**S4:** 1 baseline. 2 stubs for the 8 new tests (6 contract, 2 vitest), red run G-S4-1 on the untouched base. 3 commit A python: models, board, router. 4 commit A python tests per the table, delete `test_screener_integration.py`, fixture and narrative contract edit (Q1). 5 commit A web: types, api, `ScreenerBoard`, `CoinPanel`, `DrillDownView`, `page.tsx`; delete 4 components and 4 tests; edit 2 component tests, `screener.spec.ts`, `narrative.spec.ts`; new `screener-api.test.ts`. 6 gates A (G-S4-1,3..8,10..12), commit A. 7 stubs for `test_rsi` and `test_no_verdict_symbols`, red run of the symbol gate. 8 commit B python: `rsi.py`, `sma.py`, board import, delete four modules, regime router and model, docstrings, tests per the table. 9 commit B web: `globals.css`, `app/page.tsx`. 10 gates B (all), commit B. 11 report, PR, CI, tester.
**S6** (after S4 merged): 1 baseline. 2 stubs, red run G-S6-1. 3 spike (C6 a-c) with PNGs, decision recorded. 4 `chart-viewport.ts` and tests. 5 `simple-lines.svelte`, loader types, `MiniChart`. 6 spaghetti API, models, route, delete relative-performance. 7 `spaghetti-lines.ts`, `SpaghettiChart`, `ScreenerBoard`, `page.tsx`, CSS, deletions. 8 E2E tests 7-9, `contrast.spec.ts` line. 9 gates, backlog stub, report, PR, tester.
**S7** (after S6 merged): 1 baseline. 2 stubs, red run G-S7-1. 3 `_leg_inputs`, `btc_legs.py`, models, router (both wraps). 4 types, api, `btc-leg-lines.ts`. 5 band spike (decision recorded), island props. 6 `BtcLegChart`, `LegEstimate`, `page.tsx`, CSS. 7 E2E test. 8 gates, report, PR, tester.

## Phase Completion Rules

`CODE DONE` = PR open with green gates in the report; `VERIFIED` only after independent confirmation (tester or CI on the head SHA) AND its PC probe. S4 may merge after the offline gates and stay at `review` until P-S4-1; S6 until P-S6-1; S7 until P-S7-1. A diff touching CLAUDE.md, AGENTS.md, README.md, `.claude/`, `.github/`, `deploy/` stops at `review`. Known-Gap (AC-22 persistence, S6) has a backlog stub and keeps its gate CONDITIONAL.

## Open questions for the user

| # | Question | Options | Recommendation |
|---|---|---|---|
| Q1 | The golden file `api/tests/routers/fixtures/narrative_categories_contract.json` records `screener_narrative_state`, a verdict being deleted; the RT3 rule forbids editing fixtures. | A edit the golden: remove only those two blocks (equality command proves nothing else changed). B keep a test-local copy of the derivation so the golden is untouched (keeps dead verdict logic in tests). C keep `screener_board._coin_narrative_state` (defeats AC-2). | A |
| Q2 | RSI per coin box and in the drill-down (SPEC AC-3) is in no batch-2 slice; S4 removes the only RSI fields (nothing displayed them). | A S5 adds it with the layout work. B add an `rsi` field to S4's contract commit (about 8 more touches, +0.5-1 USD). C its own small slice. | A (S4 keeps `compute_rsi` in `rsi.py`) |
| Q3 | Spaghetti span for 1d: D6 says about 200 days, the board's 1d chart shows all 500+ cached bars. | A last 200 daily bars (readable, the 28-week rule for 1w is the same idea). B all cached daily bars. | A |
| Q4 | AC-22 wants toggle persistence; D2 says the server layout file, which S5 builds. | A in-memory toggles now, persist in S5 (backlog stub keeps AC-22 CONDITIONAL). B browser localStorage as an interim (throwaway, not shared across devices). C a separate tiny server endpoint (duplicates S5). | A |
| Q5 | The D-14 estimate needs numbers you have not fixed: the "flat" threshold and the minimum earlier legs. | A flat when the 14-point change is within 0.5 x the standard deviation of the composite's own history (shown on screen), at least 3 earlier legs. B a fixed threshold you name, for example 0.25 composite units. C 2 earlier legs minimum. | A |
| Q6 | "All BTC history" is only what the cache holds (500 daily bars unless the deep backfill ran); older boundaries cannot be confirmed. | A the chart states its span; you run the existing `backfill_pairs_universe` once on the PC before P-S7-1 (no code). B a later slice makes the worker keep a deep BTC history (new scope, 1-2 USD). | A |

Decided without asking (reversible): `/scalp` removed with no alias; `active_benchmark_reason` dropped from `/legs` (C4); S6 and S7 sequential; no S4 split.

## Validate Contract

(skeleton - vc-validate-agent fills Status, Gate and the verdict before EXECUTE; the tables below are the proposed content to check against real code)

Status: PENDING
Gate: (not stamped)
generated-by: plan-agent skeleton

### Test gates

gap-resolution: A proven now / B added by this plan's checklist / C deferred to a named later step / D backlog stub (residual, keep-active).

| criterion id | behavior | strategy | proving test | gap-resolution |
|---|---|---|---|---|
| AC-S4-1 | no verdict fields; `/scalp` gone; `/chart` serves the drill-down | Fully-Automated | G-S4-1 `test_coin_panel_has_no_verdict_fields`, `test_board_response_has_no_active_benchmark_and_keeps_freshness_fields`, `test_scalp_route_is_gone_and_chart_route_serves_the_drill_down` | B |
| AC-S4-2 | chart view keeps freshness fields; board makes no leg or narrative call | Fully-Automated | G-S4-1 `test_chart_view_carries_freshness_fields_for_every_timeframe`, `test_board_build_makes_no_leg_boundary_or_narrative_call` | B |
| AC-S4-3 | page has no strips, benchmark label, momentum, trend or confidence element | Fully-Automated | G-S4-4 `ScreenerBoard.test.tsx`; hybrid G-S4-10 | B (run: C) |
| AC-S4-4 | TS mirror has no verdict names and matches the models | Fully-Automated | G-S4-1 `test_typescript_mirror_has_no_verdict_names_and_declares_chart_view`, G-S4-4 `screener-api.test.ts`, G-S4-5 tsc | B |
| AC-S4-5 | verdict code deleted, no dead imports, allow-list self-checks | Fully-Automated | G-S4-2 `test_no_verdict_symbol_in_api_or_web_source`, `test_allow_list_entries_still_match_something`, G-S4-9 | B |
| AC-S4-6 | RSI and SMA values unchanged after the move | Fully-Automated | G-S4-2 `test_rsi.py`, `test_sma.py`, `test_lse_adapter.py::test_rsi_on_equity_bars_via_compute_rsi` | A |
| AC-S4-7 | other pages unchanged (`/regime/legs` data, pairs, onchain green) | Fully-Automated | G-S4-3 full pytest, `test_regime.py`, G-S4-11 | B |
| AC-S4-8 | real stack shows a verdict-free page and a working drill-down | Agent-Probe | P-S4-1 | C |
| AC-S6-1 | spaghetti: per-coin percent from own window start, 0 anchor, caps, references, N/A never flat | Fully-Automated | G-S6-1 `test_spaghetti.py` | B |
| AC-S6-2 | Ctrl/Cmd+wheel zoom, drag pan, double-click reset on all charts; plain wheel not handled | Fully-Automated | G-S6-3 `chart-viewport.test.ts`; hybrid G-S6-10 tests 8 | B |
| AC-S6-2r | two-finger pinch and one-finger pan on a phone | Agent-Probe | P-S6-1 | C |
| AC-S6-3 | axis text is SVG, no label clipped, canvas matches DPR 2 | Hybrid | G-S6-10 test 9 | B (run: C) |
| AC-S6-3r | text looks sharp on a real DPR 2 display | Agent-Probe | P-S6-1 | C |
| AC-S6-4 | spaghetti UI: legend, toggles, span text, no comparative wording, follows the board timeframe | Fully-Automated | G-S6-3 `SpaghettiChart.test.tsx`, `spaghetti-lines.test.ts`, `ScreenerBoard.test.tsx` | B |
| AC-S6-5 | SVG axis text passes the contrast audit | Hybrid | G-S6-10 `contrast.spec.ts` screener route | B (run: C) |
| AC-S6-6 | toggle choice survives a reload (AC-22) | Hybrid | S5 e2e toggle-reload test (not in S6); residual backlog `spaghetti-toggle-persistence_NOTE` | D (CONDITIONAL until S5) |
| AC-S7-1 | legs from confirmed boundary to next; current leg open; pre-first stretch not a leg | Fully-Automated | G-S7-1 legs tests | B |
| AC-S7-2 | estimate: heading exact, AGE and COMPOSITE labels from closed enums, inputs and thresholds in the payload, N/A with reasons | Fully-Automated | G-S7-1 estimate tests, `test_btc_legs_sources_contain_no_verdict_words` | B |
| AC-S7-3 | chart shows bands, boundary markers, readouts and the estimate panel on seeded data | Hybrid | G-S7-3 `BtcLegChart.test.tsx`, G-S7-8 E2E | B (run: C) |
| AC-S7-4 | `/regime/legs` and `/regime/btc-legs` are cache-only while the worker runs | Fully-Automated | G-S7-1 both cache-only tests | B |
| AC-S7-4r | real worker plus real cache: both endpoints answer at once; deep history span stated | Agent-Probe | P-S7-1 | C |
| AC-S7-5 | BTC history unavailable is `available=false`, never zero legs; Z timestamps; TS mirror | Fully-Automated | G-S7-1 `test_unavailable_btc_history_...`, router shape and contract tests | B |

### S4 exact gates (repo root; A = after commit A, B = after commit B; counts are arithmetic from the 963/245 baseline)

| Gate | Command | Expected |
|---|---|---|
| G-S4-1 (A) | `UV_FROZEN=1 uv run --project api pytest api/tests/routers/test_screener_no_verdict_contract.py -q` | 6 passed |
| G-S4-2 (B) | `UV_FROZEN=1 uv run --project api pytest api/tests/analytics/test_rsi.py api/tests/analytics/test_sma.py api/tests/analytics/test_no_verdict_symbols.py api/tests/data/test_lse_adapter.py -q` | 22 passed (2+3+2+15), 1 skipped (`test_probe_fixture_parses`) |
| G-S4-3 | `UV_FROZEN=1 uv run --project api pytest api/ -q` | A: 964 passed (963 - 4 - 1 + 6); B: 929 passed (964 - 19 - 6 - 12 + 2 - 2 + 2); both 2 skipped, 5 deselected, 0 xfailed |
| G-S4-4 | `pnpm --filter web test` (from `web/`: `pnpm test`) | 229 passed in 30 files (245 - 17 - 1 + 2; 33 - 4 + 1); B unchanged |
| G-S4-5..7 | `pnpm --filter web exec tsc --noEmit --incremental false`; `cd web && pnpm build:islands`; `git diff --check` | each exit 0, `diff --check` no output |
| G-S4-8 | `S4-scope`, `FORBIDDEN` (command block) | print nothing |
| G-S4-9 | `S4-verdict` (B) | prints nothing |
| G-S4-10 | hybrid, Gate convention 4: `... pnpm test:e2e screener.spec.ts narrative.spec.ts` | all passed; NOT-RUN with a reason allowed |
| G-S4-11 | `UV_FROZEN=1 uv run --project api pytest api/tests/deploy api/tests/routers/test_regime.py api/tests/routers/test_regime_components.py api/tests/routers/test_narrative_categories_contract.py api/tests/data/test_refresh_worker.py -q` | 0 failed (deploy, regime, narrative contract, worker board-read test unaffected) |
| G-S4-12 | `FIXTURES` and `FIXTURE-EQ` in the command block | `FIXTURES` prints exactly `api/tests/routers/fixtures/narrative_categories_contract.json`; `FIXTURE-EQ` prints nothing |
| P-S4-1 | user PC after pull, `deploy/build-web.ps1`, restart both tasks: open `/screener` (no benchmark label, no momentum/trend/confidence text, no leg or narrative strip) and a drill-down (chart and toggle work); `curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/api/screener/BTC/scalp`; `curl -s "http://127.0.0.1:8000/api/screener/board?timeframe=1h"` | page verdict-free; 404; no `active_benchmark` key |

### S6 exact gates (S4 merge SHA recorded as the base; counts relative to the S4-merged baseline of 929 pytest, 229 vitest in 30 files)

| Gate | Command | Expected |
|---|---|---|
| G-S6-1 | `UV_FROZEN=1 uv run --project api pytest api/tests/routers/test_spaghetti.py -q` | 8 passed |
| G-S6-2 | `UV_FROZEN=1 uv run --project api pytest api/ -q` | 934 passed (929 + 8 - 3), 2 skipped, 5 deselected, 0 xfailed |
| G-S6-3 | `pnpm --filter web test` | 242 passed in 32 files (229 + 10 + 5 + 6 + 1 - 9; 30 + 3 - 1) |
| G-S6-4 | `pnpm --filter web exec tsc --noEmit --incremental false` | exit 0 |
| G-S6-5 | `cd web && pnpm build:islands` | exit 0 |
| G-S6-6 | `git diff --check` | exit 0, no output |
| G-S6-7 | `S6-scope` and `FORBIDDEN` | print nothing |
| G-S6-8 | `FIXTURES` | prints nothing |
| G-S6-9 | `S6-dangling` | prints nothing |
| G-S6-10 | hybrid: Gate convention 4 with `screener.spec.ts contrast.spec.ts` | all passed (screener tests 1-9, contrast 7 routes); NOT-RUN with a reason allowed |
| G-S6-11 | red-first and spike record: report heading 6 holds the G-S6-1 red run; heading 9 holds the spike decision (a-c) with PNG names | present (tester reads the report) |
| P-S6-1 | user PC at DPR 2 and a phone: axis digits crisp on a coin box, drill-down and spaghetti; Ctrl+wheel zoom, drag pan, double-click reset; plain wheel scrolls the page; two-finger pinch zooms, one finger scrolls the page until zoomed | all as stated |

### S7 exact gates (S6 merge SHA recorded as the base; counts relative to 934 pytest, 242 vitest in 32 files)

| Gate | Command | Expected |
|---|---|---|
| G-S7-1 | `UV_FROZEN=1 uv run --project api pytest api/tests/analytics/test_btc_legs.py api/tests/routers/test_btc_legs_router.py -q` | 17 passed (12 + 5) |
| G-S7-2 | `UV_FROZEN=1 uv run --project api pytest api/ -q` | 951 passed (934 + 17), 2 skipped, 5 deselected, 0 xfailed; `test_leg_boundary.py` 13 unchanged |
| G-S7-3 | `pnpm --filter web test` | 254 passed in 34 files (242 + 12; 32 + 2) |
| G-S7-4 | `pnpm --filter web exec tsc --noEmit --incremental false` | exit 0 |
| G-S7-5 | `cd web && pnpm build:islands` | exit 0 |
| G-S7-6 | `git diff --check` | exit 0, no output |
| G-S7-7 | `S7-scope` and `FORBIDDEN` | print nothing |
| G-S7-8 | hybrid: Gate convention 4 with `screener.spec.ts` | all passed; NOT-RUN with a reason allowed |
| G-S7-9 | `FIXTURES`, and `S7-verdict-words` (also the S4 gate test inside G-S7-2) | print nothing |
| P-S7-1 | user PC after the deep BTC backfill: `/screener` shows BTC legs across the cached history with its stated span; the estimate inputs equal a hand calculation for the current leg; with the worker running, `curl http://127.0.0.1:8000/api/regime/legs` and `.../btc-legs` answer at once | as stated |

### Scope and secret-hygiene commands (run from the repo root; the labels above refer to these)

```
# FORBIDDEN (every slice): nothing may match
git diff --name-only origin/main...HEAD | grep -E '^(CLAUDE\.md|AGENTS\.md|README\.md|\.claude/|\.github/|deploy/|api/scripts/|process/MASTER-PLAN\.md|process/context/current-state\.md|process/archive/)'

# FIXTURES: S6, S7 nothing; S4 exactly the one sanctioned path (Q1 = A)
git diff --name-only --diff-filter=MDR origin/main...HEAD | grep -E '/fixtures/'

# FIXTURE-EQ (S4): the golden differs from origin/main only by the removed screener_narrative_state blocks
git show origin/main:api/tests/routers/fixtures/narrative_categories_contract.json | python3 -c "import json,sys; d=json.load(sys.stdin); [v.pop('screener_narrative_state') for v in d.values()]; sys.stdout.write(json.dumps(d, indent=2, sort_keys=True)+'\n')" | diff - api/tests/routers/fixtures/narrative_categories_contract.json

# S4-scope
git diff --name-only origin/main...HEAD | grep -vE '^(api/models/(screener|regime)\.py|api/analytics/screener_board\.py|api/routers/(screener|regime)\.py|api/analytics/indicators/(rsi|sma|momentum|trend)\.py|api/analytics/confidence/(badge|__init__)\.py|api/analytics/regime/(benchmark|leg_boundary)\.py|api/data/refresh_worker\.py|web/lib/types/screener\.ts|web/lib/api/screener\.ts|web/lib/__tests__/screener-api\.test\.ts|web/components/screener/(ScreenerBoard|CoinPanel|DrillDownView|ConfidenceBadge|SignalDetailPanel|LegTimelineBanner|NarrativeStrip)\.tsx|web/components/screener/__tests__/(ScreenerBoard|DrillDownView|ConfidenceBadge|SignalDetailPanel|LegTimelineBanner|NarrativeStrip|RelativePerformanceChart)\.test\.tsx|web/app/(page\.tsx|globals\.css|screener/page\.tsx)|web/e2e/(screener|narrative)\.spec\.ts|api/tests/routers/(test_screener|test_screener_freshness_payload|test_screener_gain_contract|test_board_integration|test_screener_integration|test_screener_no_verdict_contract|test_regime|test_narrative_categories_contract)\.py|api/tests/routers/fixtures/narrative_categories_contract\.json|api/tests/analytics/(test_rsi|test_momentum|test_sma|test_confidence_badge|test_benchmark|test_no_verdict_symbols)\.py|api/tests/data/test_lse_adapter\.py|process/general-plans/active/screener-batch2_04-10-26/screener-batch2-s4_REPORT_[0-9-]+\.md)$'

# S4-verdict (B): nothing may match outside the two allow-listed comment files
grep -rnE 'ConfidenceBadge|SignalDetailPanel|NarrativeStrip|LegTimelineBanner|compute_badge|derive_leg_context|derive_narrative_state|select_active_benchmark|BenchmarkSelection|active_benchmark|MomentumState|TrendState|ConfidenceState|ScalpView|compute_scalp_momentum|compute_dual_timeframe_momentum|classify_momentum|compute_trend|momentum-state|trend-direction|confidence-badge|signal-detail-panel|scalp-rsi-reading|/scalp|fetchScalp|leg_context|narrative_state' api web --include='*.py' --include='*.ts' --include='*.tsx' --include='*.svelte' --include='*.css' --include='*.js' --exclude-dir=.venv --exclude-dir=node_modules --exclude-dir=.next --exclude-dir=public --exclude-dir=__pycache__ --exclude=test_no_verdict_symbols.py | grep -vE '^(api/analytics/narrative/mapping\.py|api/scripts/seed_e2e_cache\.py):'

# S6-scope
git diff --name-only origin/main...HEAD | grep -vE '^(api/models/screener\.py|api/analytics/screener_board\.py|api/routers/screener\.py|web/islands/simple-lines\.svelte|web/lib/(chart-viewport|spaghetti-lines|island-loader|chart-palette|format-unavailable-reason|chart-time-format|relative-performance-lines)\.ts|web/lib/types/screener\.ts|web/lib/api/screener\.ts|web/lib/__tests__/(chart-viewport|spaghetti-lines|chart-time-format)\.test\.ts|web/components/chart/MiniChart\.tsx|web/components/screener/(SpaghettiChart|RelativePerformanceChart|ScreenerBoard)\.tsx|web/components/screener/__tests__/(SpaghettiChart|RelativePerformanceChart|ScreenerBoard)\.test\.tsx|web/app/(screener/page\.tsx|globals\.css)|web/e2e/(screener|contrast)\.spec\.ts|api/tests/routers/(test_spaghetti|test_relative_performance|test_board_integration)\.py|process/general-plans/active/screener-batch2_04-10-26/screener-batch2-s6_REPORT_[0-9-]+\.md|process/general-plans/backlog/spaghetti-toggle-persistence_NOTE_[0-9-]+\.md)$'

# S6-dangling: the relative-performance chain is gone everywhere
grep -rniE 'relative.performance|RelativePerformance' api web --include='*.py' --include='*.ts' --include='*.tsx' --include='*.css' --include='*.svelte' --exclude-dir=.venv --exclude-dir=node_modules --exclude-dir=.next --exclude-dir=public --exclude-dir=__pycache__

# S7-scope
git diff --name-only origin/main...HEAD | grep -vE '^(api/analytics/regime/(btc_legs|leg_boundary)\.py|api/routers/regime\.py|api/models/regime\.py|web/lib/types/btc-legs\.ts|web/lib/api/regime\.ts|web/lib/btc-leg-lines\.ts|web/lib/island-loader\.ts|web/islands/simple-lines\.svelte|web/components/screener/(BtcLegChart|LegEstimate)\.tsx|web/components/screener/__tests__/BtcLegChart\.test\.tsx|web/lib/__tests__/btc-leg-lines\.test\.ts|web/app/(screener/page\.tsx|globals\.css)|web/e2e/screener\.spec\.ts|api/tests/analytics/test_btc_legs\.py|api/tests/routers/test_btc_legs_router\.py|process/general-plans/active/screener-batch2_04-10-26/screener-batch2-s7_REPORT_[0-9-]+\.md)$'

# S7-verdict-words: nothing may match in the S7 files
grep -niwE 'bullish|bearish|bull|bear|buy|sell|confidence|signal|outperform|outperforming|underperform|underperforming|risk-on|risk-off|favorable' api/analytics/regime/btc_legs.py web/lib/btc-leg-lines.ts web/components/screener/BtcLegChart.tsx web/components/screener/LegEstimate.tsx
```

### Failing stubs

Each test named in a slice's Tests list starts as `def test_x(): raise NotImplementedError("NOT IMPLEMENTED - TDD stub: <behaviour>")` (vitest and Playwright: `throw new Error(...)`); the worker runs the slice's first gate on the untouched base, records the red run in heading 6, then writes the real tests. Tests that only move (`test_rsi.py` cases) are not stubbed.

### Red-today evidence (origin/main 605424d; read-only checks, nothing committed)

AC-S4-1/2: `CoinPanel` has `momentum`, `trend`, `confidence`, `leg_context`, `narrative_state`; the board has `active_benchmark`; `/{symbol}/scalp` exists; the board calls `leg_boundary` and `narrative_trigger`. AC-S4-5: 42 tracked api/web files hold verdict tokens (list in the S4 evidence below). AC-S6-1: no `/spaghetti`; `simple-lines.svelte` has no wheel, pointer or viewport code and draws axis text in `<Canvas>`. AC-S7-4: `/api/regime/legs` calls `fetch_ohlcv("BTC","1d")` outside any cache-only context (`leg_boundary.py:164`). AC-S7-1: no `btc_legs.py`, no `/btc-legs`. Scratch build (04-10-26, nothing committed): a copy of `api/` at 605424d with commit-A semantics (board without leg, narrative, badge, benchmark, momentum or trend calls; verdict fields and `ScalpView` removed; `/chart` added) failed exactly the S4 table rows on the python side (4 integration tests; 4 `test_screener.py` fixtures plus 2 tests with their own patches; 3 freshness-payload tests; `test_percent_change_by_timeframe_equals_chip_pct`; `test_scalp_view_populated`; the 3 narrative-contract tests), apart from tests that read `web/`, `deploy/` or `.gitignore`, absent in the copy. The scratch also showed that deleting `BenchmarkSelection` or `MomentumState` in commit A breaks `import api.main` (`benchmark.py` and `badge.py` still import them), hence the model split between A and B. Not run: P-S4-1, P-S6-1, P-S7-1, AC-S6-2r/3r, AC-S7-4r (browser, phone, PC cache).

### S4 split evidence (decision C1)

Tracked `api/` and `web/` files containing a verdict token (the S4-verdict token list plus `.confidence`, `confidence:`, `momentum.state`, `trend.direction`, excluding `.venv`, `node_modules`, fixtures): 42, of which 40 are S4 files and 2 are the allow-listed comment-only files (`mapping.py`, `seed_e2e_cache.py`). Planned touches: commit A 31 (13 source, 18 tests), commit B 22 (14 source, 8 tests), total 53 of the 100 split threshold (27 source, 26 tests); deletions are 17 of the 53. Reproduce: `git ls-files api web | grep -vE '\.venv|node_modules|/fixtures/' | xargs grep -lE '<token list>' | wc -l`.

### Unverified facts: owner and deterministic fallback

| # | Fact | Status | Owner | Fallback |
|---|---|---|---|---|
| U1 | LayerChart `transform`, `<Svg>` plus `<Canvas>` in one Chart, canvas pixel ratio | unverifiable offline (scout hook blocks `node_modules`) | S6 spike with PNGs | custom viewport, all-SVG |
| U2 | `Rect` bands in the island | unverifiable offline | S7 band spike | coloured segments, then markers only |
| U3 | wheel listener with `preventDefault` under Svelte 5 | precedent `regime-panel.svelte` uses `onwheel` with `preventDefault` and `regime.spec.ts` drives wheel events | S6 step 3 uses `addEventListener(..., {passive: false})` | none needed |
| U4 | BTC `1d` depth on the PC | unknown (500 bars unless deep backfill ran) | P-S7-1 | span stated on the chart (Q6) |
| U5 | Ctrl+wheel and pinch on real browsers and phones | Playwright proves the code path only | P-S6-1 | probe, never claimed |

### Not verifiable offline

Live Hyperliquid; LayerChart rendering; DPR 2 on a real display; phone touch; the PC cache depth; GitHub CI; every new test; the refresh worker against the real exchange.

### What this coverage does NOT prove

- Pure and fake-exchange gates prove viewport math, payload shape, the estimate rule and cache-only reads, NOT how the charts feel on a phone or look on a DPR 2 screen (P-S6-1) nor real BTC history depth (P-S7-1).
- The symbol gate proves no listed token remains, NOT that no new verdict wording appears elsewhere (the S7 word scan covers S7 files only).
- E2E runs on seeded bars (500 daily, 120 sub-daily); it proves wiring, not live data.

### Open gaps

AC-S6-6 (toggle persistence) waits for S5: backlog `spaghetti-toggle-persistence_NOTE_<dd-mm-yy>.md`. RSI display: Q2. Open: Q1-Q6. known-gap: island render fidelity on real displays: probes P-S6-1, P-S7-1.

Mechanics: PVL iterations write `results.tsv` and `screener-batch2-pvl-iteration-NNN_REPORT_<dd-mm-yy>.md` in this folder.

## Resolved questions (user, before this plan)

1. Product is personal data tracking: no verdicts, badges, flags or confidence scores. 2. Verdict removal is staged (contract first, deletion second). 3. Interactions on ALL charts; spike LayerChart first, custom fallback. 4. Spaghetti 1w shows about 28 weeks and spans the board's bars. 5. Axis text must be crisp. 6. BTC leg chart over all BTC history plus the D-14 estimate; both strips come off the page. 7. Never trim daily bars. 8. S8 open item (a) is fixed inside S7; (b) and (c) are accepted limits. 9. Budget: 45 USD ceiling, about 27 USD left.

## Worker envelopes

Written by the planner AFTER the user's explicit ENTER EXECUTE MODE: one per slice, at most 8,000 bytes, a pointer list citing the fine sub-range table below, saved as `screener-batch2-s{4,6,7}_REF_<dd-mm-yy>.md` in this task folder (master-planner.md section 8 template; branches `claude/<task-id>-<slug>`). S6's envelope is issued only after the S4 merge SHA, S7's only after the S6 merge SHA.

## Test Infra Improvement Notes

(none identified yet) Candidates: a Playwright project with `deviceScaleFactor: 2` for crispness checks; a shared fake-exchange module (also noted in batch 1); jsdom never mounts the Svelte islands.

## Resume and Execution Handoff

1. Selected plan file: `process/general-plans/active/screener-batch2_04-10-26/screener-batch2_PLAN_04-10-26.md`
2. Last completed step: PLAN written 04-10-26 (not validated). Batch 1 is merged (PRs #33-#36); its probes are still pending on the PC.
3. Validate-contract status: skeleton present (criteria table, exact gates, scope commands); vc-validate-agent writes Status, Gate and the verdict.
4. Context loaded: SPEC, INNOVATE, decisions.md D-14, current-state.md, architecture.md, all-tests.md, operating-instructions.md, batch-1 plan and reports (S1, S2, S3, S8) and PVL iterations 001-003, real code at 605424d (screener, regime, island, e2e, test files).
5. Next step for a fresh agent: answer or accept the recommendations for Q1-Q6, run VALIDATE (check every "Existing tests that break" row against real code, the three scope regexes with a dry run, and the baselines), then wait for the user's explicit "ENTER EXECUTE MODE"; the planner then writes three envelopes and spawns S4. Next instruction (RIPER-5): say **ENTER VALIDATE MODE**.

## Envelope line ranges (re-derive with `grep -n '^## \|^### '` at spawn time; worker cap 36,000 B = CLAUDE.md 13,443 counted once + envelope (cap 8,000) + plan bytes)

Same mechanism as batch 1 (fine sub-ranges, no protocol change). Line numbers refer to this file as saved with this table; the table is the last block, so editing it moves no earlier line (re-derive with the grep above if any earlier line is edited). Each set = the decision lines the slice needs, Gate conventions 1-8, the slice section without its Risks and Rollback lines, its criteria rows, its exact gates without the PC probe, the command-block lines it uses, and Failing stubs. A worker never needs: Name check, Costs, Open questions, Risks, Rollback, PC probes, Red-today evidence.

| Slice | Plan ranges (lines) | Plan bytes | Envelope room (cap 36,000) |
|---|---|---|---|
| S4 | 39, 41-44, 52, 54-61, 93-134, 278-287, 303, 305-316, 353-355, 357-358, 360-361, 363-364, 366-367, 380, 382, 384 | 19,570 | 2,987 |
| S6 | 39, 45-46, 49-50, 52, 54-61, 139-170, 278-279, 288-295, 319, 321-333, 353-355, 357-358, 369-370, 372-373, 380, 382, 384 | 17,271 | 5,286 |
| S7 | 39, 44, 47-50, 52, 54-61, 176-196, 278-279, 296-301, 336, 338-348, 353-355, 357-358, 375-376, 378-380, 382, 384 | 14,122 | 8,435 |

Computed as 36,000 - 13,443 (CLAUDE.md) - plan bytes. A filled envelope is about 1.8-2.6 KB (template alone 864 B): S4's room is the tight one; if an S4 envelope would not fit, trim the envelope text, never the ranges. Naming operating-instructions.md (6,678 B) moves the cap to 43,000 and leaves the room within 400 B of the figures above. S7's room exceeds the 8,000 B envelope cap, so 8,000 B is the binding limit there.
