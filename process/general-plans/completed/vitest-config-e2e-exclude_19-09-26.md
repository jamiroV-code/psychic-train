# Backlog: `vitest.config.ts` does not exclude `e2e/` from vitest's collection

**Date raised**: 19-09-26
**Raised by**: `getjson-timeout-catch_PLAN_19-09-26.md` EVL — `pnpm test` (full suite)
**Status**: RESOLVED 24-09-26 — `web/vitest.config.ts` now sets `test.exclude: [...configDefaults.exclude, "e2e/**"]` (regime-dashboard RFC-006, `process/features/cycle-regime/active/regime-dashboard_24-09-26/`). `pnpm --filter web test`: 12 files / 75 tests passed, 0 failed files, 5 consecutive runs.
**Origin plan**: `process/general-plans/active/momentum-screener_17-09-26/getjson-timeout-catch_PLAN_19-09-26.md`

## Why this exists

The `getjson-timeout-catch` plan's EVL ran the full `pnpm test` (vitest) suite: 31/31 individual
tests passed, but the run reported one test *file* as failed — `e2e/screener.spec.ts`. That file is
a Playwright spec, written with `@playwright/test`'s `test(name, async ({ page }) => ...)` fixture
style. vitest has no `page` fixture, so it fails at the first `page.goto(...)` call, before any
assertion in the file runs. `pnpm test:e2e` (the real Playwright runner) passes the same file
correctly.

`vitest.config.ts` currently has no `exclude` entry for the `e2e/` directory, so vitest tries to
collect and execute every `.spec.ts`/`.test.ts` file under `web/`, including ones written for a
different test runner entirely.

## Why it matters

Low-stakes but real noise: anyone running `pnpm test` and glancing at file-level pass/fail (rather
than the per-test count) sees a red file and has to re-derive, each time, that it's not a
regression — exactly the kind of ambiguity `all-tests.md`'s Standing Lesson table exists to prevent.
It also means a genuinely broken `e2e/screener.spec.ts` and a vitest-can't-run-this-file
non-failure look identical in vitest's file-level output, which could hide a real Playwright-spec
authoring mistake behind the expected "of course it fails under vitest" noise.

Not blocking: Playwright already covers that file's actual surface correctly (`pnpm test:e2e`
passed 6/6 per `playwright-e2e_19-09-26-phase-report.md`), so no test coverage gap exists — this is
purely a collection/config mismatch.

## What a fix would need

- Add `e2e/` (or the specific glob covering `e2e/**/*.spec.ts`) to `vitest.config.ts`'s `test.exclude`
  array, alongside vitest's own defaults (`node_modules`, `dist`, etc.).
- Re-run `pnpm test` once to confirm the file no longer appears in vitest's collection and the
  31-test count is unaffected.
- No source change, no test-content change — purely a config-file edit.

## Not blocking

`getjson-timeout-catch_PLAN_19-09-26.md` shipped and was verified without this fix — the plan's own
Touchpoints never included `vitest.config.ts`, and `pnpm test:e2e` already proves the affected file
works correctly under its intended runner. Flagged for a future one-line PLAN/EXECUTE, not a
blocker on anything currently in flight.
