# getJson Timeout + Catch Handling — Plan

**Date**: 19-09-26
**Status**: ✅ VERIFIED — user confirmed all EVL runs (19-09-26)
**Complexity**: Simple
**Slug**: `getjson-timeout-catch`
**Parent program**: `momentum-screener_17-09-26` (inner-loop RFC-006)
**Governing SPEC**: `process/general-plans/active/momentum-screener_17-09-26/momentum-screener_SPEC_17-09-26.md` (SPEC phase skipped for this inner-loop RFC, same precedent as RFC-005 and `weekly-ohlc-anchor_PLAN_19-09-26.md`)

---

## Overview

RFC-006 covers dead-data-rendering handling across the screener surface. This plan is deliberately narrowed to **only** the `getJson` timeout/catch handling slice: `web/lib/api/screener.ts`'s shared fetch helper has no timeout and no timeout-specific error shape, and 2 of its 5 caller components (`DrillDownView.tsx`, `NarrativeStrip.tsx`) have no `.catch` on their fetch effects at all — a rejected or hung promise currently produces an unhandled rejection / silent stall rather than a rendered error state.

Out of scope for this plan (separate future RFC-006 slices, not to be pulled in here):
- `reason`-value rendering (why a data point is unavailable)
- Project-wide unification of the 3 existing error-rendering conventions (this plan intentionally matches each touched component to its own existing convention — inline-alongside for `DrillDownView`, whole-section-replace for `NarrativeStrip` — rather than picking one)
- Adding `aria-live`/`role="alert"` to any error state (none of the existing error renders in this codebase use a live region; this plan does not introduce one)
- Making the timeout configurable (hardcoded 10s constant)
- Fixing the stale "three of four call sites" comment in `web/e2e/screener.spec.ts` (~line 157) — actual count is 2 of 5; flagged here, not corrected by this plan

See `process/context/all-context.md` for project-wide architecture/conventions and `process/context/tests/all-tests.md` for the current test inventory and known gaps this plan will touch.

### Session Constraints (carry forward, do not soften)

This plan was authored from a Cowork cloud session with no `device_bash` — there is no shell on the user's Windows machine reachable from here; file edits, when EXECUTE runs, go through the remote-devices bridge one read/write at a time, not via shell commands run from this session. Additionally, the `vc-*` named subagent types this repo's CLAUDE.md routes RIPER-5 phases to are not spawnable in this session (available types here are `general-purpose`, `Explore`, `Plan`, …); RESEARCH/INNOVATE/PLAN for this slug were run by `general-purpose` subagents briefed with each `vc-*` agent's role instead. This is a recorded protocol deviation from CLAUDE.md §Orchestrator Role, not a concealed one — same pattern as `weekly-ohlc-anchor_PLAN_19-09-26.md` in this same task folder.

Consequence: **EXECUTE and every test-running gate in this plan cannot be run from inside this session.** They are written below as exact commands for the user, or a future session with `device_bash`, to run.

---

## Phase Completion Rules

- PLAN is complete when this file is written and contains all required sections (this file).
- PLAN does not proceed to EXECUTE directly. The next phase is VALIDATE (`vc-validate-agent` role, or a `general-purpose` subagent briefed with that role under the same session-constraint deviation noted above), which converts the Acceptance Criteria and Touchpoints below into an executable V1–V7 gate contract.
- EXECUTE may not begin against an empty or missing Validate Contract (see that section below).
- This plan is SIMPLE: no phase-program gates, no PVL/EVL loop scaffolding beyond the standard VALIDATE→EXECUTE→UPDATE PROCESS sequence, single task folder, no sub-plans.

---

## Acceptance Criteria

1. **AC-1 (timeout fires cleanly):** Against a non-responding backend, a call through `getJson<T>` (any of the 5 `fetchX` functions in `web/lib/api/screener.ts`) throws a catchable `Error` after `DEFAULT_TIMEOUT_MS` (10,000ms) — specifically `Error(\`API request timed out after 10000ms: ${path}\`)` — rather than hanging indefinitely or leaving the returned promise unresolved.
2. **AC-2 (DrillDownView error + Close preserved):** On a rejected or timed-out fetch driven by `DrillDownView.tsx`'s effect, the component renders a `data-testid="drilldown-error"` element containing the error message, while the header (symbol name + Close button) and the timeframe-toggle group remain rendered and functional (Close still closes the drill-down).
3. **AC-3 (NarrativeStrip error):** On a rejected or timed-out fetch driven by `NarrativeStrip.tsx`'s effect, the component renders the whole-section-replace error state: `<section data-testid="narrative-strip" aria-label="Narrative categories"><span data-testid="narrative-error">{error}</span></section>`.
4. **AC-4 (no regression to already-catching callers):** The 3 existing `getJson` callers that already have working `.catch` handling are unaffected in behavior (same success-path output, same existing error-path output) by the `screener.ts` change — only the timeout wrapping and error-message shape for timeout specifically are new; non-timeout errors rethrow unchanged, so existing catch blocks receive the same error type/shape they do today for non-timeout failures.
5. **AC-5 (no existing test regresses):** All currently-passing tests in `web/components/screener/__tests__/` and `web/e2e/screener.spec.ts` continue to pass after this change (execution pending — see Session Constraints; this is a criterion to verify in EVL, not a claim of current verification).

---

## Touchpoints

| File | Change |
|---|---|
| `web/lib/api/screener.ts` | Add `DEFAULT_TIMEOUT_MS = 10_000` constant; wrap the `fetch` call inside `getJson<T>` with `{ signal: AbortSignal.timeout(DEFAULT_TIMEOUT_MS) }`; catch the resulting `TimeoutError` and rethrow as `new Error(\`API request timed out after ${DEFAULT_TIMEOUT_MS}ms: ${path}\`)`; all other errors rethrow unchanged. No signature change to any of the 5 exported `fetchX` functions. |
| `web/components/screener/DrillDownView.tsx` | Add `error` state; add `.catch((err: Error) => { if (!cancelled) setError(err.message); })` to the `fetchScalpView`-driven effect; clear `error` to `null` at the top of the effect before each new call; render `data-testid="drilldown-error"` gated on `error`, replacing only the data-dependent body (`MiniChart`/`chart-unavailable` block + `scalp-rsi-reading` div) — header and timeframe-toggle group stay unconditional (inline-alongside pattern, matches `ScreenerBoard.tsx`). |
| `web/components/screener/NarrativeStrip.tsx` | Add `error` state; same `.catch` + clear-before-refetch pattern on the `fetchNarrativeCategories`-driven effect; add an error-check branch before the existing `!categories` loading branch, returning the whole-section-replace error markup (matches `LegTimelineBanner.tsx`). |
| `web/components/screener/__tests__/DrillDownView.test.tsx` | Add new test case(s) covering AC-2 (rejected/timed-out fetch → `drilldown-error` renders, Close button still present and functional). Written as part of this plan's Implementation Checklist, not left as a gap. |
| `web/components/screener/__tests__/NarrativeStrip.test.tsx` | Add new test case(s) covering AC-3 (rejected/timed-out fetch → `narrative-error` renders inside the `narrative-strip` section). Written as part of this plan's Implementation Checklist, not left as a gap. |

No Update Trigger is intended for `process/context/tests/all-tests.md` as part of this plan — the new test cases add coverage within the existing test files' scope rather than changing the recorded test-runner setup or known-gap inventory structure. (If EXECUTE or EVL determines the gap-tracking entry for these two files needs updating, that is a call for UPDATE PROCESS, not a commitment made here.)

`process/context/all-context.md` — no change; referenced above and in Resume/Handoff for continuity only.

---

## Public Contracts

None. No exported function signatures change (`getJson<T>` and all 5 `fetchX` functions keep their existing signatures). No component props change on `DrillDownView` or `NarrativeStrip`. The `data-testid="drilldown-error"` and `data-testid="narrative-error"` attributes are net-new additions, not modifications to any existing contract, and are additive/non-breaking for any existing test selector.

---

## Blast Radius

**Touched:**
- `web/lib/api/screener.ts`
- `web/components/screener/DrillDownView.tsx`
- `web/components/screener/NarrativeStrip.tsx`
- `web/components/screener/__tests__/DrillDownView.test.tsx`
- `web/components/screener/__tests__/NarrativeStrip.test.tsx`

**Explicitly NOT touched:**
- Nothing under `api/` (backend) — this is a frontend fetch-wrapper change only
- The other 3 already-catching `getJson` callers (unaffected per AC-4; not edited)
- `reason`-value rendering anywhere in the screener surface
- Any shared/common error component (none is introduced or refactored; each touched component keeps its own existing error-rendering convention)
- `web/e2e/screener.spec.ts` (the stale comment there is flagged in Overview, not edited)
- `process/context/all-context.md` (no content change, referenced only)

---

## Validate Contract

Status: CONDITIONAL
Date: 19-09-26
date: 2026-09-19
generated-by: outer-pvl

Parallel strategy: sequential
Rationale: Score 1/7 — only S7 fires (blast-radius ≥5 files: exactly 5 touchpoints). No other fan-out signal present (single feature area, no schema/auth/API/billing surface, no multi-plan dependency, no cross-cutting refactor). Single-agent sequential VALIDATE pass is correct; no dimension fan-out warranted.

Test gates (C3 5-column table):

| criterion id | behavior | strategy | proving test | gap-resolution |
|---|---|---|---|---|
| AC-1 | getJson throws formatted timeout Error after ~10s against a non-responding backend, rather than hanging | Agent-Probe | Manual check (Verification Evidence): black-holed endpoint, observe ~10s elapsed + exact `API request timed out after 10000ms: ...` message | C |
| AC-2 | DrillDownView renders drilldown-error on reject; header/Close/timeframe-toggle stay rendered; Close still works | Fully-Automated | New case in DrillDownView.test.tsx (Checklist item 4); `pnpm test -- DrillDownView.test.tsx` | B |
| AC-3 | NarrativeStrip renders whole-section-replace narrative-error markup on reject | Fully-Automated | New case in NarrativeStrip.test.tsx (Checklist item 5); `pnpm test -- NarrativeStrip.test.tsx` | B |
| AC-4 | 3 existing already-catching getJson callers unaffected (same success/error-path output) | Hybrid | Existing tests for those callers + full `pnpm test` regression run; no new targeted assertion added by this plan | C |
| AC-5 | No regression to any currently-passing test in __tests__/ or screener.spec.ts | Fully-Automated | `pnpm test` (full suite) + `pnpm test:e2e` | B |

gap-resolution legend: A — proven now | B — fixed in this plan | C — deferred to a named later phase/plan | D — backlog test-building stub

Failing stub (AC-2):
`test("should render drilldown-error and keep Close functional when fetch rejects", () => { throw new Error("NOT IMPLEMENTED — TDD stub: rejected/timed-out fetch in DrillDownView renders data-testid=drilldown-error with message; header/Close/timeframe-toggle remain rendered; Close still closes") })`

Failing stub (AC-3):
`test("should render narrative-error inside narrative-strip section when fetch rejects", () => { throw new Error("NOT IMPLEMENTED — TDD stub: rejected/timed-out fetch in NarrativeStrip renders whole-section-replace narrative-error markup") })`

Dimension findings:
- Infra fit: PASS — `AbortSignal.timeout()` is a standard Web API, stable in Node ≥18, all evergreen browsers, and compatible with Next.js's fetch on client and server. No polyfill needed.
- Test coverage: CONCERN — AC-1 has only Agent-Probe verification; vacuous-green ban blocks a terminal PASS. A mechanical alternative (mocked-fetch unit test asserting `AbortSignal.timeout` wiring + `TimeoutError`-name reshaping) exists in principle but is not in this plan's Touchpoints (no `screener.ts` test file). AC-4 also has no new dedicated test, relying on the existing suite only.
- Breaking changes: PASS — confirmed none; no exported signature changes, only additive `data-testid` attributes.
- Security surface: PASS — client-side error handling only, no new data exposure, no auth/trust-boundary crossing.
- `web/lib/api/screener.ts` feasibility: PASS — mechanically straightforward fetch-wrapper addition inside existing try/catch; no signature or behavior conflicts.
- `web/components/screener/DrillDownView.tsx` feasibility: PASS — standard useState/useEffect conditional-render pattern, matches this repo's `ScreenerBoard.tsx` precedent.
- `web/components/screener/NarrativeStrip.tsx` feasibility: PASS — same pattern, matches `LegTimelineBanner.tsx` precedent.

Open gaps:
1. AC-1: no automated (Fully-Automated/Hybrid) proof of timeout wiring/error-shape in this plan's scope — only a manual probe. Optional remedy: add a mocked-fetch unit test for `screener.ts` (not currently a Touchpoint) in a future PLAN follow-up.
2. AC-4: no new dedicated test asserting non-timeout errors rethrow unchanged through the new try/catch — coverage is incidental via the existing suite, not proactive.
3. Pre-existing risk (not introduced by this plan): every test file in `web/components/screener/__tests__/` carries a SANDBOX NOTE — written but never executed. First real `pnpm test` run may surface latent pre-existing failures that EVL must distinguish from new regressions.

What this coverage does NOT prove:
- AC-1 gate: no CI-catchable regression protection (one-time manual check); no boundary-precision proof under clock drift; no partial-response-hang coverage; no concurrent-timeout coverage.
- AC-2/AC-3 gates: mocked rejection is instantaneous, not a genuine 10s wait; no coverage of rapid re-fetch/race conditions during symbol switching; no visual/CSS assertion.
- AC-4 gate: only proves the 3 untouched callers' existing paths still pass; does not newly assert non-`TimeoutError`-named rejections specifically rethrow byte-for-byte unchanged.
- AC-5 gate: first-ever real execution of previously-unexecuted tests — cannot yet distinguish pre-existing failures from this plan's regressions until run.

Gate: CONDITIONAL
Accepted by: user (19-09-26, "Accept with concerns" — AC-1 Agent-Probe-only gap and AC-4 no-new-dedicated-test gap both explicitly accepted; proceed to EXECUTE)

---

## Autonomous Goal Block

SESSION GOAL: getJson timeout/catch handling for RFC-006's scoped slice (screener.ts timeout wrapper + DrillDownView/NarrativeStrip catch handling)
Charter + umbrella plan: process/general-plans/active/momentum-screener_17-09-26/momentum-screener_PLAN_17-09-26.md (umbrella has no ## Stable Program Goal section, so this plan carries its own goal block per BRANCH A)
Autonomy: this is an interactive (non-/goal) session — EXECUTE proceeds against this single plan with a phase-end check-in; pause on any hard-stop condition below rather than proceeding silently.
Hard stop conditions / safety constraints:
- Do not widen scope into reason-value rendering, aria-live additions, configurable timeout, or cross-component error-pattern unification without returning to PLAN first (all explicitly out-of-scope per Overview).
- Do not report AC-1, AC-4, or AC-5 as VERIFIED without an actual observed `pnpm test` / `pnpm test:e2e` run — this session cannot run them itself, and pre-existing SANDBOX NOTEs mean even old tests are currently unconfirmed.
- Do not treat AC-1 as fully proven at EXECUTE/UPDATE PROCESS time — it carries a CONDITIONAL gap (Agent-Probe-only, no automated `screener.ts` test in this plan's Touchpoints); if a later session adds a `screener.ts` unit test, this contract's AC-1 row must be updated before relying on it as proven.
Next phase: EXECUTE: process/general-plans/active/momentum-screener_17-09-26/getjson-timeout-catch_PLAN_19-09-26.md
Validate contract: (inline, above)
Execute start: Implementation Checklist item 1 (web/lib/api/screener.ts) | first test: DrillDownView.test.tsx new case | AC-1 manual probe pending until after Implementation Checklist completes | high-risk pack: no

---

## Implementation Checklist

1. **`web/lib/api/screener.ts`** — Add `const DEFAULT_TIMEOUT_MS = 10_000;` near the top of the file (module scope). In `getJson<T>`, pass `{ signal: AbortSignal.timeout(DEFAULT_TIMEOUT_MS) }` as part of the existing `fetch` call's init options. Wrap the fetch/await in a `try/catch`: if the caught error's `name` is `"TimeoutError"`, rethrow `new Error(\`API request timed out after ${DEFAULT_TIMEOUT_MS}ms: ${path}\`)`; otherwise rethrow the original error unchanged. Verify none of the 5 exported `fetchX` function signatures changed.
2. **`web/components/screener/DrillDownView.tsx`** — Add `const [error, setError] = useState<string | null>(null);` (or equivalent existing state convention in this file). At the top of the `fetchScalpView`-driven effect, reset `setError(null)` before issuing the new call. Add `.catch((err: Error) => { if (!cancelled) setError(err.message); })` to that fetch chain. In the render, gate the data-dependent body (the `MiniChart`/`chart-unavailable` block and the `scalp-rsi-reading` div) behind `!error`, and add an error branch rendering `<div data-testid="drilldown-error">{error}</div>` in its place — header (symbol + Close button) and the timeframe-toggle group stay outside this conditional, always rendered.
3. **`web/components/screener/NarrativeStrip.tsx`** — Add the same `error` state + clear-before-refetch + `.catch` pattern to the `fetchNarrativeCategories`-driven effect. Add an error-check branch before the existing `!categories` loading-branch return, returning `<section data-testid="narrative-strip" aria-label="Narrative categories"><span data-testid="narrative-error">{error}</span></section>` when `error` is set.
4. **`web/components/screener/__tests__/DrillDownView.test.tsx`** — Add test case(s): mock the fetch/API call to reject (and/or simulate a timeout), assert `drilldown-error` renders with the expected message text, and assert the Close button is still present and still calls its close handler when clicked. Mark as written-but-unexecuted (see Session Constraints / Test Procedure below) — do not mark VERIFIED.
5. **`web/components/screener/__tests__/NarrativeStrip.test.tsx`** — Add test case(s): mock the fetch/API call to reject (and/or simulate a timeout), assert the whole `narrative-strip` section renders with `narrative-error` containing the expected message text. Mark as written-but-unexecuted — do not mark VERIFIED.

---

## EXECUTE Results (19-09-26)

**Status: DONE_WITH_CONCERNS.** All 5 Implementation Checklist items applied exactly as specified, written to the device, and each independently re-staged from the device and byte-diffed clean against the edited copy post-commit (per this repo's own operational lesson about `device_commit_files` silently not landing — checked explicitly, all 5 clean).

**What changed, per file:**
1. `web/lib/api/screener.ts` — `DEFAULT_TIMEOUT_MS = 10_000` constant added; `getJson<T>`'s `fetch` call now passes `{ signal: AbortSignal.timeout(DEFAULT_TIMEOUT_MS) }`, wrapped in try/catch that reshapes a `TimeoutError`-named error into `Error("API request timed out after 10000ms: ...")` and rethrows anything else unchanged. All 5 exported `fetchX` signatures unchanged (confirmed by reading the file post-edit).
2. `DrillDownView.tsx` — `error` state added; effect clears it before each call and now has `.catch((err: Error) => { if (!cancelled) setError(err.message); })` on the existing `cancelled`-flag pattern; render gates the `MiniChart`/chart-unavailable/`scalp-rsi-reading` block behind `!error`, showing `data-testid="drilldown-error"` instead; header + Close button + timeframe-toggle group stay unconditional.
3. `NarrativeStrip.tsx` — same `error` state/clear/`.catch` pattern; error branch added before the `!categories` loading branch, returning the whole-section `narrative-strip`/`narrative-error` replacement, matching `LegTimelineBanner.tsx`'s shape.
4. `DrillDownView.test.tsx` — 2 new cases added (AC-2: error renders + Close still works; a second case covering clear-on-next-successful-fetch, beyond the single validate-contract stub, because Checklist item 2 requires that behavior and nothing asserted it). New SANDBOX NOTE disclosure added matching the file's existing convention.
5. `NarrativeStrip.test.tsx` — 1 new case (AC-3: whole-section error replacement). Same SANDBOX NOTE disclosure.

**Deviations (all within blast radius — same files, same semantic operation, documented not improvised):**
1. The plan's prose ("the `fetchScalpView`-driven effect") maps to the actual injectable prop names `fetchScalp` (`DrillDownView`) and `fetchData` (`NarrativeStrip`) — same effects, plan used the exported function name rather than the prop name.
2. `DrillDownView`'s two gated JSX siblings required a `<>...</>` fragment wrapper to share one `!error` condition — mechanically unavoidable, no success-path DOM change.
3. The `!res.ok` throw now sits inside the new try block rather than outside it, so a timeout during `res.json()` body-read is also caught and reshaped — this is a superset of the plan's literal instruction ("wrap the fetch/await"), not a narrower or different behavior; AC-4 still holds because non-`TimeoutError` errors rethrow byte-for-byte unchanged.
4. Second `DrillDownView` test case added beyond the validate-contract's single stub (see item 4 above) — same file, closes a real checklist requirement the stub didn't cover.

**Verification attempt:** tests could not be run. `pnpm install` in this session's own cloud sandbox hit `ERR_PNPM_FETCH_403` on every package (`registry.npmjs.org` is egress-blocked here, confirmed via direct `curl` probes returning 403 on `react`, `vitest`, and `lightweight-charts` — an organization policy block, not a transient or missing-file issue). What WAS verified: `tsc --noResolve` parse/type-check of all 5 edited files is clean — zero syntax errors, zero real type errors (the only diagnostic is a pre-existing, unmodified `process.env` reference needing `@types/node`, unrelated to this change) — and `AbortSignal.timeout()` typechecks correctly against this project's actual `tsconfig.json` (`target: ES2017`, `lib: [dom, dom.iterable, esnext]`).

**AC-1 through AC-5 remain unverified by execution** — this was already the accepted Session Constraint at VALIDATE time, not a new gap. The commands below must be run on the user's own machine (which already has `node_modules` installed) to close EVL.

**New observation flagged for UPDATE PROCESS, not acted on here** (outside EXECUTE's remit — `process/context/` edits are reserved for UPDATE PROCESS): `web/vitest.config.ts` carries a comment referencing a real `pnpm test` run on 18-09-26 that fixed a `ReferenceError: React is not defined` issue. This conflicts with the "never executed" SANDBOX NOTEs still present at the top of every file in `web/components/screener/__tests__/`. The test-file SANDBOX NOTEs may be stale and `process/context/tests/all-tests.md`'s inventory may need reconciling against what has actually run. Not touched this pass.

Nothing outside the 5-file Touchpoints was modified: no `api/`, no `reason`-value rendering, no aria-live, no error-convention unification, no configurable timeout, `web/e2e/screener.spec.ts`'s stale "three of four" comment left untouched as flagged at PLAN time.

---

## Verification Evidence (Test Procedure)

Not yet executed in any session (see Session Constraints and EXECUTE Results above — no `device_bash`, and this session's own cloud sandbox has npm registry access blocked by egress policy). These are the exact commands the user must run on their own machine to close EVL for this plan:

```
cd web
pnpm test -- DrillDownView.test.tsx
pnpm test -- NarrativeStrip.test.tsx
pnpm test                      # full vitest unit/component suite — checks AC-5 (no regression)
pnpm test:e2e                  # Playwright suite, including web/e2e/screener.spec.ts — checks AC-4/AC-5 at the e2e layer
```

Every test file in `web/components/screener/__tests__/` currently carries a "SANDBOX NOTE" stating vitest could not be installed/run in the authoring sandbox — existing tests were written to spec but never executed. The two new test cases this plan adds (Implementation Checklist steps 4–5) are **written-but-unexecuted in the same way** and must carry the same disclosure in their own SANDBOX NOTE — they are not to be described as VERIFIED, PASSING, or otherwise confirmed until an actual `pnpm test` run (per the commands above) has been observed.

Manual/exploratory check for AC-1 (timeout behavior), since it requires a genuinely non-responding backend rather than a mock: point the dev server's API base at an endpoint that never responds (e.g. a deliberately black-holed port or a proxy configured to drop the connection) and confirm the `fetchX` call rejects at ~10s with the `API request timed out after 10000ms: ...` message rather than hanging past that. Record the actual elapsed time observed.

---

## EVL Results (19-09-26, run by the user)

- `pnpm test -- DrillDownView.test.tsx` — **passed** (AC-2 confirmed: error renders, header/Close/timeframe-toggle preserved, clears on next successful fetch).
- `pnpm test -- NarrativeStrip.test.tsx` — **passed** (AC-3 confirmed: whole-section replacement renders correctly).
- `pnpm test` (full suite) — **31/31 tests passed.** One test *file* (`e2e/screener.spec.ts`) reported as failed in this run, but this is a pre-existing vitest-config issue, not a regression: that file uses `@playwright/test`'s `test(name, async ({ page }) => ...)` fixture style, which vitest cannot execute (`page` is not a vitest fixture) — it fails at `page.goto(...)` on the first line, before any of this plan's code is exercised. `vitest.config.ts` does not currently exclude `e2e/` from vitest's own collection. This plan did not introduce the issue (nothing in this plan's Touchpoints includes `e2e/screener.spec.ts` or `vitest.config.ts`) — flagged for UPDATE PROCESS as a one-line config fix (add `e2e/` to vitest's `exclude`), not a blocker here.
- `pnpm test:e2e` (Playwright) — **passed**, confirming AC-4/AC-5 at the e2e layer with the real Playwright runner.
- AC-1 manual check (non-responding backend) — **passed**, confirmed by the user.

**Net result: all 5 Acceptance Criteria (AC-1 through AC-5) are now verified.** The two structural gaps named at VALIDATE (AC-1 had no automated wiring test in this plan's scope; AC-4 had no new dedicated assertion) remain accurate as *coverage* observations — they were accepted gaps, not correctness failures, and both ACs' actual behavior is now confirmed working by the runs above.

---

## Resume and Execution Handoff

- **Last completed step:** EVL (19-09-26) — all Verification Evidence commands run by the user. All green except one pre-existing, unrelated vitest/Playwright config collision (`e2e/screener.spec.ts` under vitest) — see `## EVL Results` above. Plan is **✅ VERIFIED**.
- **Next step:** UPDATE PROCESS — archive this plan, note the `vitest.config.ts` exclude fix and the stale SANDBOX-NOTE/test-count reconciliation (both flagged during EXECUTE) as follow-ups, update `process/context/tests/all-tests.md`'s inventory if warranted, and close this task-folder thread of RFC-006 (the `reason`-value rendering and dead-data-unification slices remain separately queued, per RFC-005's original Next section).
- **Continuity pointer:** this task folder continues from RFC-005's report/plan in the same `momentum-screener_17-09-26` program lineage; see the SPEC referenced in Overview and `weekly-ohlc-anchor_PLAN_19-09-26.md` in this same plans folder for the precedent on the no-`device_bash` / no-`vc-*`-subagent session-constraint pattern this plan also carries.
- **Context references:** `process/context/all-context.md` (project architecture/conventions router) and `process/context/tests/all-tests.md` (test inventory and known gaps) — both should be consulted again at VALIDATE and EXECUTE time in case either has changed since this plan was written.

---

**Next instruction: "ENTER UPDATE PROCESS MODE" for this plan (`getjson-timeout-catch_PLAN_19-09-26.md`).**
