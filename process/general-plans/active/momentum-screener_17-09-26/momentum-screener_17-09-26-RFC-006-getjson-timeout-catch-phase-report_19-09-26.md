# RFC-006 Phase Report — getJson Timeout + Catch Handling (scoped slice)

**Date**: 19-09-26
**Plan**: `process/general-plans/active/momentum-screener_17-09-26/getjson-timeout-catch_PLAN_19-09-26.md`
**Status**: ✅ VERIFIED — all 5 Acceptance Criteria confirmed by EVL 19-09-26. RFC-006 itself is only **partially** done; see Next.
**Phases run**: RESEARCH → INNOVATE → PLAN → VALIDATE (CONDITIONAL, accepted with concerns) → EXECUTE → EVL → UPDATE PROCESS (this report)
**SPEC**: skipped — inner-loop RFC governed by `momentum-screener_SPEC_17-09-26.md` (same precedent as RFC-005 and `weekly-ohlc-anchor_PLAN_19-09-26.md`)

---

## Outcome

`web/lib/api/screener.ts`'s shared `getJson<T>` fetch helper had no timeout and no timeout-specific
error shape. Two of its five caller components — `DrillDownView.tsx` and `NarrativeStrip.tsx` —
had no `.catch` at all on their fetch effects, so a rejected or hung request produced an unhandled
promise rejection / silent stall rather than any rendered error state. (The other three callers
already caught correctly and were out of scope.)

Fix applied: a module-scope `DEFAULT_TIMEOUT_MS = 10_000` constant; `getJson<T>`'s `fetch` call now
passes `{ signal: AbortSignal.timeout(DEFAULT_TIMEOUT_MS) }`, and a `TimeoutError`-named rejection is
reshaped into `Error("API request timed out after 10000ms: ...")` before rethrow (all other errors
rethrow unchanged). `DrillDownView` and `NarrativeStrip` each gained `error` state, a clear-before-
refetch + `.catch` on their existing effects, and their own component-appropriate render: inline-
alongside (`data-testid="drilldown-error"`) for `DrillDownView`, matching `ScreenerBoard.tsx`'s
convention; whole-section-replace (`data-testid="narrative-error"` inside the `narrative-strip`
section) for `NarrativeStrip`, matching `LegTimelineBanner.tsx`'s convention.

EVL results (run by the user on their own machine, since this session has no `device_bash` and its
own cloud sandbox has npm-registry egress blocked):

- `pnpm test -- DrillDownView.test.tsx` — passed (AC-2: error renders, header/Close/timeframe-toggle
  preserved, error clears on next successful fetch).
- `pnpm test -- NarrativeStrip.test.tsx` — passed (AC-3: whole-section replacement renders correctly).
- `pnpm test` (full suite) — **31/31 individual tests passed.** One test *file*,
  `e2e/screener.spec.ts`, was reported failed in this run, but this is a pre-existing vitest-config
  gap, not a regression from this plan: that file uses Playwright's `test(name, async ({ page }) =>
  ...)` fixture style, which vitest cannot execute — it fails at `page.goto(...)` on the very first
  line, before any of this plan's code runs. `vitest.config.ts` simply does not exclude `e2e/` from
  vitest's own collection. Nothing in this plan's Touchpoints includes `e2e/screener.spec.ts` or
  `vitest.config.ts`.
- `pnpm test:e2e` (Playwright) — passed, confirming AC-4/AC-5 at the real e2e layer.
- AC-1 manual probe (non-responding backend) — passed, confirmed directly by the user: the call
  rejected at ~10s with the exact `API request timed out after 10000ms: ...` message.

Net: all 5 ACs verified. The two structural coverage gaps accepted at VALIDATE (AC-1 had only an
Agent-Probe gate, not an automated `screener.ts` wiring test; AC-4 had no new dedicated assertion,
relying on the existing suite) remain accurate as *coverage* observations, not correctness failures
— both ACs' actual runtime behavior is now confirmed working by the runs above, not merely inferred.

## Deviations

Four deviations were recorded during EXECUTE, all within blast radius (same touched files, same
semantic operation as planned) and documented at the time rather than discovered later or left
silent:

1. The plan's prose named the effects by their exported function names (`fetchScalpView`,
   `fetchNarrativeCategories`); the actual injectable prop names are `fetchScalp` (`DrillDownView`)
   and `fetchData` (`NarrativeStrip`) — same effects, a naming mismatch only.
2. `DrillDownView`'s two JSX siblings gated behind `!error` required a `<>...</>` fragment wrapper to
   share one condition — mechanically unavoidable, no change to the success-path DOM.
3. The `!res.ok` throw now sits inside the new try block rather than strictly around only the
   `fetch` call, so a timeout during `res.json()`'s body-read is also caught and reshaped. This is a
   superset of the plan's literal instruction, not a narrower or different behavior — AC-4 still
   holds because non-`TimeoutError` errors rethrow byte-for-byte unchanged.
4. A second `DrillDownView.test.tsx` case (clear-on-next-successful-fetch) was added beyond the
   Validate Contract's single AC-2 stub, because Implementation Checklist item 2 requires that
   behavior and nothing in the stub asserted it.

No file outside the plan's 5 Touchpoints was modified: no `api/` change, no `reason`-value
rendering, no `aria-live` addition, no error-convention unification, no configurable timeout, and
`web/e2e/screener.spec.ts`'s stale "three of four call sites" comment was left untouched as flagged
at PLAN time (out of scope by design).

## Context updated

- `process/context/tests/all-tests.md` — updated in this same UPDATE PROCESS pass: "Last updated"
  line moved to this cycle; a new Debugging Quick Reference row for the vitest-picks-up-`e2e/`
  symptom; two new Known Gaps bullets (the `vitest.config.ts` exclude gap, and the stale SANDBOX
  NOTE reconciliation gap); and a one-line addition to the `web/` vitest status-table row noting the
  +3 test cases this plan added and the file-level vitest/e2e collection caveat. No existing Standing
  Lesson row was touched or renumbered.

## Backlog raised

- `process/general-plans/backlog/vitest-config-e2e-exclude_19-09-26.md` — the one-line
  `vitest.config.ts` fix to exclude `e2e/` from vitest's own test collection. Low priority,
  mechanical, not blocking (Playwright already covers that surface correctly).
- `process/general-plans/backlog/sandbox-note-reconciliation_19-09-26.md` — the broader "SANDBOX
  NOTE — written but never executed" disclosure, present at the top of every file in
  `web/components/screener/__tests__/`, is now confirmed stale for at least the files that have run
  (18-09-26 and 19-09-26 real `pnpm test` runs both post-date when the notes were written). Needs a
  per-file reconciliation pass rather than one boilerplate disclaimer copy-pasted everywhere.

## Next

RFC-006 is **only partially done**. This plan deliberately covered only the `getJson`
timeout/catch slice. Two slices named in RFC-005's own "Next" section remain unstarted and
unscoped **on purpose** — the user explicitly narrowed this session to the getJson slice only, not
because they were forgotten:

- **`reason`-value rendering** (why a data point is unavailable, e.g. `bad-symbol` vs
  `source-unavailable`) — not started.
- **Project-wide unification of the three dead-data-rendering conventions** — not started; this
  plan intentionally matched each touched component to its own existing convention instead.

Two other items named in RFC-005's Next section are **not** carried forward as open here:

- **Playwright E2E** — already closed by a separate session. `playwright-e2e_PLAN_19-09-26.md` /
  `playwright-e2e_19-09-26-phase-report.md` report ✅ VERIFIED (6/6 passed), and
  `process/context/tests/all-tests.md`'s own "Known Gaps" section already shows "No E2E/browser
  suite" struck through as "Closed 19-09-26" with that phase report as the citation. No action
  needed from this plan.
- **RFC-001 stub closeout toward archival** — still queued, unchanged. `playwright-e2e_19-09-26-
  phase-report.md`'s own Next section lists this as still open (`stub_rfc001-frontend-tests_18-09-
  26.md` the remaining item); nothing found in this pass closes it, so it is stated here as still
  open rather than assumed closed.

Per the standing precedent in this task folder (`ccxt-symbol-resolution_PLAN_19-09-26.md`,
`weekly-ohlc-anchor_PLAN_19-09-26.md`, `playwright-e2e_PLAN_19-09-26.md`), this plan
(`getjson-timeout-catch_PLAN_19-09-26.md`) stays in
`process/general-plans/active/momentum-screener_17-09-26/` and is **not** moved to `completed/`.
The task folder archives only when the entire `momentum-screener` program is done.
