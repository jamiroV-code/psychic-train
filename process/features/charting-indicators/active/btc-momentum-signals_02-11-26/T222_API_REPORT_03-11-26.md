## 1 Task ID
T222 — BTC Momentum API calculation/model/response/TypeScript contract slice

## 2 Outcome
The API implementation and focused tests pass, and an independent reviewer approved the code. The final full API suite failed outside the T222 test nodes. T222 is not finally validated or clean for merge; T223 and integrated browser verification remain pending.

## 3 Summary
- Added the deterministic daily BTC target-transition calculator using completed UTC daily closes, script defaults (21 bars/month; 63/126/252 horizons), crypto auto horizon (30 bars/month), the corrected vote-to-target formula, SMA filter, cap, active-date gating, gap/duplicate/invalid-data resets, forming-bar cutoff, and first out-of-range exit behavior.
- Added a private pure target helper with exact 0–3 vote target tests above/below SMA; signal events remain minimal and expose no target/allocation.
- Added the constrained Pydantic event, default-safe `signals` response field, BTC-only endpoint assembly, and matching TypeScript contract.
- Added focused golden and contract coverage for warm-up, transition timing/price, SMA equality, gaps/duplicates, date boundaries, model validation, route behavior, cache-only access, and composite-unavailable operation.
- Independent reviewer `T222ApiIndependentReview` returned APPROVE for the API code; this is not a full-suite or feature approval.
- T223 chart markers, visual probing, integrated browser tests, and user chart confirmation remain pending.

## 4 Files changed
- `api/analytics/regime/btc_legs.py`
- `api/models/regime.py`
- `api/tests/analytics/test_btc_legs.py`
- `api/tests/routers/test_btc_legs_router.py`
- `web/lib/types/btc-legs.ts`
- `process/features/charting-indicators/active/btc-momentum-signals_02-11-26/T222_API_REPORT_03-11-26.md`
- `process/features/charting-indicators/active/btc-momentum-signals_02-11-26/harness/{risk-gate,context-snippets,verification,review-decision,adversarial-validation}.json`

## 5 Commits
No commit created. No push, PR, merge, or deployment performed.

## 6 Tests run
- Focused T222 API tests: `api/.venv/Scripts/python.exe -m pytest api/tests/analytics/test_btc_legs.py api/tests/routers/test_btc_legs_router.py -q` — **28 passed, 2 deprecation warnings**.
- Final full API suite: `api/.venv/Scripts/python.exe -m pytest api/ -q` — **44 failed, 3675 passed, 4 skipped, 5 deselected, 9 warnings, 1 error** in 945.39s. `api/.pytest_cache/v/cache/lastfailed` lists failures in attention/discovery/equities/deploy/router tests and no T222 test node. The deploy real-data guard `test_real_data_paths_untouched` observed a mismatch between its package-start and end snapshots. No separate full-run before-snapshot or complete changed-path diff was preserved; no restore/delete was attempted.
- Post-correction `uv run --project api pytest api/ -q` attempt failed before pytest started with `uv trampoline failed to canonicalize script path`; the full suite was run via the project's Python interpreter instead.

## 7 Tests NOT run
- Web unit tests, TypeScript check, island build, seeded Playwright, and visual probe: T223/integrated gates remain pending.
- No second full API run; the final full suite is red, and the real-data guard mismatch must be understood before any repeat.

## 8 Deviations
- The full-suite test runner used the existing `api/.venv/Scripts/python.exe -m pytest` interpreter because the prescribed `uv run` command could not start pytest on this Windows host.
- The deploy package's real-data guard reported a cache/watchlist snapshot mismatch. No separate full-run baseline or complete changed-path diff was preserved; no files were restored or deleted.

## 9 Blockers
- The required full API suite did not pass. The failed-node list contains no T222 test node, and the focused T222 suite passed, but failures elsewhere and one error remain unresolved.
- `test_real_data_paths_untouched` observed a difference in the real-cache/watchlist snapshot; preserve those files until the cause and exact changed paths are established.
- No merge and no T223 start while the API gate is red.

## 10 Follow-up
- Complete the read-only root-cause triage of the unrelated failed nodes and the real-data guard mismatch. Do not restore or rerun the full suite until cache isolation is understood.
- After a clean API validation and owner merge, proceed with T223, then run integrated RT4 gates and visual verification.

## 11 Context cost
Reviewed the approved plan/SPEC, API implementation, models, tests, TypeScript contract, failure list, and risk artifacts. No chart/UI code was changed in T222.
