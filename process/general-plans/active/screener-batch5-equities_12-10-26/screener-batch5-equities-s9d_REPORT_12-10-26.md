# T48 / S9D worker report: equities end-to-end proof, spaghetti and drill-down

## 1. Task ID

T48, batch 5, slice S9D. Branch `claude/t48-s9d-equities-e2e` from `origin/main` 4ec0cd0 (S9C merged).

## 2. Outcome

PASS. G-S9D-1..5 pass on code SHA f88f520; every count equals the plan's arithmetic. Seeded e2e ran on f88f520 (90 passed in 10 files).

## 3. Summary

- `api/scripts/seed_e2e_equities.py`: refuses unless `SCREENER_CACHE_ROOT` is set, is not `cache.DEFAULT_CACHE_ROOT` and is what the cache module reads, and `SCREENER_EQUITIES_PATH` is set and is not `api/data/equities.json`. Writes synthetic daily bars for SYNA, SYNB, SYNC (420 NYSE sessions, 88 derived weekly bars) and SYNTHIN (20 sessions), ending on `equities_calendar.last_due_session(now)`, through `lse_adapter._write_cache` (redistributable=false footer, `fetched_at` sidecar); writes `equities.json`; adds an `equities` key to `web/e2e/.fixture-manifest.json` and keeps every other key. Prices are a deterministic wave; no network, no key.
- `web/playwright.config.ts`: chain `seed_e2e_cache.py && seed_e2e_equities.py && uvicorn`; `SCREENER_EQUITIES_PATH` in the e2e cache root; `LSE_API_KEY` set to the empty string.
- `web/e2e/contrast.spec.ts`: `/equities` added to the route table (+1).
- `web/e2e/equities.spec.ts`: the 10 plan cases; afterEach restores the seeded tickers in order and deletes the saved equities layout.
- Vitest: `EquitiesSpaghetti.test.tsx` (6) and `EquitiesDrillDown.test.tsx` (6), each rendering `EquitiesScreener` with its real clients over a fetch spy and an island stub that records chart props.
- No conditional component file was needed (no D test was red against merged C).

## 4. Files

New: `api/scripts/seed_e2e_equities.py`, `api/tests/scripts/test_seed_e2e_equities.py`, `web/e2e/equities.spec.ts`, `web/components/equities/__tests__/EquitiesSpaghetti.test.tsx`, `web/components/equities/__tests__/EquitiesDrillDown.test.tsx`. Edited: `web/playwright.config.ts` (+8), `web/e2e/contrast.spec.ts` (+1). Plus this report. 7 code files (5 new, 2 edited), as planned.

## 5. Commits

- f88f520 test(equities): end-to-end proof, spaghetti and drill-down (T48 / S9D)
- this report (docs commit on top)

## 6. Tests run (SHA, UTC)

| Gate | SHA | Time (Z) | Result |
|---|---|---|---|
| Red-first: G-S9D-1 on untouched base with stub file | 4ec0cd0 | 08:04 | collection error (module missing): 5 red |
| Red-first: G-S9D-2 on untouched base with stub files | 4ec0cd0 | 08:05 | 12 failed, 8 passed in 3 files |
| G-S9D-1 seeder + crypto seeder pytest | f88f520 | 08:10 | 10 passed |
| G-S9D-5 full pytest | f88f520 | 08:10-08:13 | 1105 passed, 2 skipped, 5 deselected |
| G-S9D-2 `vitest run components/equities` | f88f520 | 08:13 | 20 passed in 3 files |
| G-S9D-5 full vitest | f88f520 | 08:13 | 458 passed in 57 files |
| G-S9D-5 tsc --noEmit | f88f520 | 08:13 | clean |
| G-S9D-5 build:islands | f88f520 | 08:13 | built |
| G-S9D-3 e2e equities + contrast | f88f520 | 08:13-08:14 | 18 passed |
| G-S9D-4 full e2e | f88f520 | 08:14-08:17 | 90 passed; `--list` 90 tests in 10 files |
| REAL-DATA, `git diff --check`, FORBIDDEN, FIXTURES, S-secret, S9D-scope, S9-words, S9-utc, S9-nostore | f88f520 | 08:18 | all print nothing; diff --check exit 0 |

A pre-commit run of G-S9D-3 (18 passed) also happened during development.

## 7. Tests NOT run

None of the gates. Probe P-S9-1 is the user's and is not claimed.

## 8. Deviations

- The plan's weekly figure (88) is the observed derived count for a 420-session series ending 2026-10-09; the pytest asserts at least 60 weekly bars (the rule that matters) rather than exactly 88, since the count can be 87 or 88 depending on the run date.
- The seeder removes only `<guarded root>/equities` before writing (the crypto seeder already empties the root); it never touches the crypto seed.

## 9. Blockers

None.

## 10. Follow-up

- The seeded bars end on the newest due session at seed time; a run that crosses a session's due time (close + 60 min) would see the board call them stale. The e2e asserts no stale marker, so this cannot fail a run; noted only.

## 11. Context cost

Read: CLAUDE.md, the envelope, the plan ranges named in it. No other context doc opened. No subagents. Spend is measured by the planner.
