## 1 Task ID
T222 — BTC Momentum API calculation/model/response/TypeScript contract slice

## 2 Outcome
The deterministic API implementation, focused tests, independent code review, and final GitHub Linux CI all passed. The first PR CI run exposed two typed web fixtures missing required `signals`; both were fixed and run #41690626570 passed both jobs. The local Windows full API suite remains red outside T222 test nodes, with the cache/watchlist guard mismatch unresolved. PR #241 remains draft/open; no merge, T223, or integrated chart verification yet.

## 3 Summary
- Added the deterministic daily BTC target-transition calculator using completed UTC daily closes, script defaults (21 bars/month; 63/126/252 horizons), crypto auto horizon (30 bars/month), the corrected vote-to-target formula, SMA filter, cap, active-date gating, gap/duplicate/invalid-data resets, forming-bar cutoff, and first out-of-range exit behavior.
- Added a private pure target helper with exact 0–3 vote target tests above/below SMA; signal events remain minimal and expose no target/allocation.
- Added the constrained Pydantic event, default-safe `signals` response field, BTC-only endpoint assembly, and matching TypeScript contract.
- Added focused golden and contract coverage for warm-up, transition timing/price, SMA equality, gaps/duplicates, date boundaries, model validation, route behavior, cache-only access, and composite-unavailable operation.
- Updated two existing `BtcLegChartResponse` web fixtures with `signals: []` after CI tsc surfaced the missing required field; no chart behavior changed.
- Final GitHub Actions run #41690626570 on `e4fd25b5` passed the full API job and web job (Vitest, tsc, island build).
- Independent reviewer `T222ApiIndependentReview` returned APPROVE for the API code; this is not a full-suite or feature approval.
- T223 chart markers, visual probing, integrated browser tests, and user chart confirmation remain pending.

## 4 Files changed
- `api/analytics/regime/btc_legs.py`
- `api/models/regime.py`
- `api/tests/analytics/test_btc_legs.py`
- `api/tests/routers/test_btc_legs_router.py`
- `web/lib/types/btc-legs.ts`
- `web/components/screener/__tests__/BtcLegChart.test.tsx`
- `web/lib/__tests__/btc-leg-lines.test.ts`
- `process/features/charting-indicators/active/btc-momentum-signals_02-11-26/T222_API_REPORT_03-11-26.md`
- `process/features/charting-indicators/active/btc-momentum-signals_02-11-26/harness/{risk-gate,context-snippets,verification,review-decision,adversarial-validation}.json`

## 5 Commits

Code commits: `a32921c8` (API) and `e4fd25b5` (web fixture correction) on `claude/t222-btc-momentum-api`.
Draft PR #241: https://github.com/jamiroV-code/psychic-train/pull/241 (open, draft).
GitHub Actions run #41690626570 on `e4fd25b5`: API and web jobs passed. No merge or deployment.

## 6 Tests run
- Focused T222 API tests: `api/.venv/Scripts/python.exe -m pytest api/tests/analytics/test_btc_legs.py api/tests/routers/test_btc_legs_router.py -q` — **28 passed, 2 deprecation warnings**.
- Final full API suite: `api/.venv/Scripts/python.exe -m pytest api/ -q` — **44 failed, 3675 passed, 4 skipped, 5 deselected, 9 warnings, 1 error** in 945.39s. `api/.pytest_cache/v/cache/lastfailed` lists failures in attention/discovery/equities/deploy/router tests and no T222 test node. The deploy real-data guard `test_real_data_paths_untouched` observed a mismatch between its package-start and end snapshots. No separate full-run before-snapshot or complete changed-path diff was preserved; no restore/delete was attempted.
- Post-correction `uv run --project api pytest api/ -q` attempt failed before pytest started with `uv trampoline failed to canonicalize script path`; the full suite was run via the project's Python interpreter instead.
- Initial GitHub CI run #41689448300: API job passed; web Vitest passed, but tsc failed because two existing typed fixtures omitted `signals`; island build was skipped. The fixtures were corrected in `e4fd25b5`.
- Local TypeScript check `pnpm --filter web exec tsc --noEmit --incremental false` — passed after the fixture correction.
- Local web suite `pnpm --filter web test` — **67 files / 639 tests passed**; existing Vite CJS deprecation and React `act(...)` warnings.
- Corrected GitHub CI run #41690626570 — API and web jobs passed; web job covered Vitest, tsc, and island build.
- Heartbeat guard quick fix: `api/.venv/Scripts/python.exe -m pytest api/tests/deploy/test_real_data_snapshot.py -q` — **1 passed in 0.77s**. Temporary-file regression proves the exact collector heartbeat is excluded while other cache files and watchlist changes remain detected.

## 7 Tests NOT run
- Seeded Playwright, manual chart visual probe, and user chart confirmation: pending T223/integrated gates.
- No second Windows full API run: Linux CI passed; do not rerun the Windows full suite until the cache/watchlist guard mismatch is understood.

## 8 Deviations
- The full-suite test runner used the existing `api/.venv/Scripts/python.exe -m pytest` interpreter because the prescribed `uv run` command could not start pytest on this Windows host.
- The deploy package's real-data guard reported a cache/watchlist snapshot mismatch. No separate full-run baseline or complete changed-path diff was preserved; no files were restored or deleted.
- Initial PR CI exposed missing required `signals` in two typed web test fixtures; added `signals: []` to both; no production behavior changed.

## 9 Blockers
- The local Windows full API suite remains red (44 failed, 3675 passed, 4 skipped, 5 deselected, 1 error); `lastfailed` lists no T222 test node. GitHub Linux API CI passed on PR #241.
- Read-only 60-second observation of 1,353 real cache/watchlist files found only `attention/_pc_state/collector_heartbeat.json` changing. It identifies standalone collector PID 23604, confirmed alive by Windows; the writer updates every 30 seconds. This reproduces an external-writer false positive in the old guard. The historical run did not preserve a changed-path diff, so its exact mismatch remains retrospectively unproven. The guard now excludes only that exact heartbeat path; all other cache files and watchlist remain protected. No real data was restored, deleted, or edited.
- PR #241 remains draft/open. No merge or T223 start until the owner accepts the local guard disposition and merges T222.

## 10 Follow-up
- The scoped heartbeat guard regression passed; the full Windows suite has not been rerun. Assess the remaining Windows failures separately rather than attributing them to the heartbeat.
- After the owner merges T222, proceed with T223, then run integrated RT4 gates and visual verification.

## 11 Context cost
Reviewed the approved plan/SPEC, API implementation, models, tests, TypeScript contract, failure list, and risk artifacts. No chart/UI code was changed in T222.
