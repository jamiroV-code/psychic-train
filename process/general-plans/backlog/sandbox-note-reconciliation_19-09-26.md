# Backlog: Stale "SANDBOX NOTE — written but never executed" disclosures in `web/components/screener/__tests__/`

**Date raised**: 19-09-26
**Raised by**: `getjson-timeout-catch_PLAN_19-09-26.md` EXECUTE Results ("New observation flagged
for UPDATE PROCESS") and confirmed at EVL
**Status**: OPEN
**Origin plan**: `process/general-plans/active/momentum-screener_17-09-26/getjson-timeout-catch_PLAN_19-09-26.md`

## Why this exists

Every test file in `web/components/screener/__tests__/` carries a "SANDBOX NOTE" stating the tests
were written to spec but never executed — vitest could not be installed/run in the authoring
sandbox at the time each file was written. That disclosure is now stale for at least the files that
have since actually run:

- `vitest.config.ts` itself carries a comment referencing a real `pnpm test` run on 18-09-26 that
  surfaced and fixed a `ReferenceError: React is not defined` issue (recorded as Standing Lesson
  Deviation #12 in `process/context/tests/all-tests.md`).
- `getjson-timeout-catch_PLAN_19-09-26.md`'s own EVL is a second real `pnpm test` run, on 19-09-26,
  in which `DrillDownView.test.tsx` and `NarrativeStrip.test.tsx` — both still carrying the SANDBOX
  NOTE, including in their newly-added cases from this plan — actually executed and passed.

No file-by-file reconciliation has happened. The note is currently a single boilerplate paragraph
copy-pasted into every file regardless of that file's actual run history.

## Why it matters

A stale "never executed" note sitting next to tests that HAVE executed and passed erodes the note's
signal for the tests that genuinely haven't run yet. A reader (human or agent) triaging a failure,
or deciding how much to trust a green result, has no way to tell from the note itself which files it
still accurately describes. This is the same class of problem `all-tests.md`'s Standing Lesson
table exists to catalog: a disclosure or a passing suite that no longer means what it claims to mean
is worse than no disclosure at all, because it actively misleads rather than leaving a visible gap.

## What a fix would need

- Audit each test file under `web/components/screener/__tests__/` against `all-tests.md`'s own run
  log and the phase reports that recorded real `pnpm test` runs (at minimum: the 18-09-26 run noted
  in `vitest.config.ts`'s comment, and `getjson-timeout-catch_PLAN_19-09-26.md`'s 19-09-26 EVL run)
  to determine, per file, whether it has actually executed since being written.
- For files confirmed executed: either remove the SANDBOX NOTE entirely, or replace it with a
  one-line "last confirmed run: <date>, <result>" note instead of the generic disclaimer.
- For files not yet confirmed executed: keep the note, but make it specific to that file rather than
  implying a blanket sandbox-wide state that no longer holds project-wide.
- This is a documentation/comment change only — no test logic changes.

## Not blocking

`getjson-timeout-catch_PLAN_19-09-26.md` shipped and was verified without this reconciliation —
the plan's own EVL run is itself evidence the touched files work, independent of what their SANDBOX
NOTE says. Flagged as a hygiene item for a future pass, not a blocker on anything currently in
flight.
