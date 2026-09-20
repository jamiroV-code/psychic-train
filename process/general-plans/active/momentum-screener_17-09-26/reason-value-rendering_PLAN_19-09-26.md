# `reason`-value Rendering — Plan

**Date**: 19-09-26
**Status**: ✅ VERIFIED — user confirmed all EVL runs (19-09-26)
**Complexity**: Simple
**Slug**: `reason-value-rendering`
**Parent program**: `momentum-screener_17-09-26` (inner-loop RFC-006, slice 2 of 2 remaining)
**Governing SPEC**: `process/general-plans/active/momentum-screener_17-09-26/momentum-screener_SPEC_17-09-26.md` (SPEC phase skipped for this inner-loop RFC, same precedent as RFC-005 and `getjson-timeout-catch_PLAN_19-09-26.md`)

---

## Overview

RFC-006 covers dead-data-rendering handling across the screener surface. The first slice
(`getjson-timeout-catch_PLAN_19-09-26.md`, ✅ VERIFIED) covered only `getJson` timeout/catch
handling. This plan covers the **second** of the two slices its own Overview explicitly deferred:
**`reason`-value rendering** — surfacing *why* a chart series is unavailable, not just that it is.

RFC-005 added an `UnavailableReason` literal (`"insufficient-history" | "bad-symbol" |
"source-unavailable"`) to the backend's `ChartSeries` and `RelativePerformanceSeries` models
(`api/models/screener.py`, confirmed present: lines 30, 97, 146) specifically because, before it
existed, `available: False` collapsed three unrelated causes — a misconfigured symbol, a dead data
source, and genuinely short history — into one signal. The frontend types
(`web/lib/types/screener.ts`) were never updated to mirror the new field, and all three render
sites that show an unavailable chart currently print the same hardcoded string regardless of cause:

- `CoinPanel.tsx` (`chart-unavailable`): always "Not enough history at this timeframe"
- `DrillDownView.tsx` (`drilldown-chart-unavailable`): always "Not enough history at this timeframe"
- `RelativePerformanceChart.tsx` (`rp-unavailable-note`): always "{symbol}: N/A for this window"

So the exact operator-facing problem RFC-005 fixed on the backend (a config bug reporting itself as
a history problem) is still reproduced on the frontend today — the backend now knows which of the
three it is, but no pixel on screen says so.

### Session Constraints (carried forward, do not soften)

This plan is authored from a Cowork cloud session with no `device_bash` — there is no shell on the
user's Windows machine reachable from here; file edits, when EXECUTE runs, go through the
remote-devices bridge one read/write at a time, not via shell commands run from this session.
Additionally, the `vc-*` named subagent types this repo's CLAUDE.md routes RIPER-5 phases to are
not spawnable in this session (available types here are `general-purpose`, `Explore`, `Plan`, …).
This session performed RESEARCH directly (reading the relevant source files listed under
Touchpoints, plus the RFC-005/RFC-006 phase reports) rather than via a `vc-research-agent` spawn,
given the small, single-track, low-ambiguity scope. This is a recorded protocol deviation from
CLAUDE.md §Orchestrator Role, not a concealed one — same pattern as `getjson-timeout-catch_PLAN_19-
09-26.md` and `weekly-ohlc-anchor_PLAN_19-09-26.md` in this same task folder.

Consequence: **EXECUTE and every test-running gate in this plan cannot be run from inside this
session.** They are written below as exact commands for the user, or a future session with
`device_bash`, to run. Static verification this session *can* perform (TypeScript syntax/shape
review by direct reading, no `tsc`/`pnpm` execution without `node_modules`) is noted separately
from actual test execution and never described as VERIFIED.

Out of scope for this plan (per RFC-006's own Overview and the first slice's Next section):
- Project-wide unification of the 3 existing dead-data-rendering conventions (inline-alongside for
  `CoinPanel`/`DrillDownView`, whole-section-replace for `NarrativeStrip`/`LegTimelineBanner`,
  per-item list note for `RelativePerformanceChart`) — this plan matches each touched component to
  its own existing convention, same discipline as the first slice.
- `NarrativeStrip.tsx` / `LegTimelineBanner.tsx` — their "unavailable" states
  (`narrative_state: "unavailable"`, `leg_context: "unavailable"`) are a different, already-typed
  literal unrelated to `UnavailableReason`; not touched here.
- `SignalDetailPanel.tsx` — already renders `legContext`/`narrativeState` directly from their own
  typed props (RFC-004, Risk Prediction #4); no `ChartSeries.reason` involvement.
- Any backend change — `api/models/screener.py` already carries the field; this is a pure frontend
  contract-mirroring + rendering slice.
- `aria-live`/`role="alert"` additions (no existing error/unavailable render in this codebase uses
  a live region; this plan does not introduce one).

See `process/context/all-context.md` for project-wide architecture/conventions and
`process/context/tests/all-tests.md` for the current test inventory and known gaps.

---

## Phase Completion Rules

- PLAN is complete when this file is written and contains all required sections (this file).
- PLAN does not proceed to EXECUTE directly. VALIDATE (contract appended below) converts the
  Acceptance Criteria and Touchpoints into an executable gate checklist.
- EXECUTE may not begin without explicit "ENTER EXECUTE MODE" from the user (hard gate, no
  exception under this plan's own Session Constraints).
- This plan is SIMPLE: no phase-program gates, no PVL/EVL loop scaffolding beyond the standard
  VALIDATE → EXECUTE → UPDATE PROCESS sequence, single task folder, no sub-plans.

---

## Acceptance Criteria

1. **AC-1 (types mirror the backend contract):** `web/lib/types/screener.ts` exports an
   `UnavailableReason` type with exactly the three values `"insufficient-history" | "bad-symbol" |
   "source-unavailable"` (matching `api/models/screener.py`'s `Literal` verbatim), and both
   `ChartSeries` and `RelativePerformanceSeries` gain `reason: UnavailableReason | null` — matching
   the wire shape (pydantic emits the field as `null`, not omitted, when unset).
2. **AC-2 (CoinPanel distinguishes reasons):** When `panel.chart.available` is `false`, the
   `chart-unavailable` element's rendered text differs across at least the three `reason` values
   (not the same string for all three), carries a `data-reason` attribute equal to
   `panel.chart.reason`, and falls back to the existing "Not enough history at this timeframe" copy
   when `reason` is `null` (no regression for fixtures that don't set it).
3. **AC-3 (DrillDownView distinguishes reasons):** Same behavior as AC-2 for
   `drilldown-chart-unavailable`, driven by `view?.chart.reason`.
4. **AC-4 (RelativePerformanceChart distinguishes reasons per coin):** Each unavailable coin's note
   inside `rp-unavailable-note` renders reason-specific copy (not the fixed "N/A for this window"
   string regardless of cause), each carries its own `data-testid="rp-unavailable-{symbol}"` and
   `data-reason={reason}`, and the existing "for this window" framing is preserved specifically for
   the `insufficient-history` case (the one existing test's fixture doesn't set `reason`, so it
   exercises the fallback path — see Deviations note on updating that fixture).
5. **AC-5 (no duplicated copy across 3 sites):** The reason → human-copy mapping lives in exactly
   one shared, unit-tested function, not inlined three times — same rationale as this project's
   "one source of numerical truth" principle applied to display copy: three independent copies of
   the same mapping is how the mapping quietly drifts.
6. **AC-6 (no regression):** `ScreenerBoard.test.tsx`'s existing AC-19 case (`chart-unavailable`
   with no `reason` on the fixture) and `RelativePerformanceChart.test.tsx`'s existing
   `rp-unavailable-note` case still pass after their fixtures are updated to the new field shape.

---

## Touchpoints

1. `web/lib/types/screener.ts` — add `UnavailableReason` type; add `reason: UnavailableReason |
   null` to `ChartSeries` and `RelativePerformanceSeries`.
2. `web/lib/format-unavailable-reason.ts` (**NEW**) — single shared `formatUnavailableReason(reason:
   UnavailableReason | null, context: "timeframe" | "window")` function (AC-5).
3. `web/components/screener/CoinPanel.tsx` — render reason-aware text + `data-reason` in
   `chart-unavailable`.
4. `web/components/screener/DrillDownView.tsx` — render reason-aware text + `data-reason` in
   `drilldown-chart-unavailable`.
5. `web/components/screener/RelativePerformanceChart.tsx` — render reason-aware text +
   per-coin `data-testid`/`data-reason` inside `rp-unavailable-note`.
6. `web/lib/__tests__/format-unavailable-reason.test.ts` (**NEW**) — unit tests for the shared
   formatter (all 3 reason values × both contexts, plus the `null` fallback).
7. `web/components/screener/__tests__/ScreenerBoard.test.tsx` — update the AC-19 fixture to the new
   field shape (`reason: null` on the existing case, keep it green); add one new case with
   `reason: "bad-symbol"` asserting the distinct copy + `data-reason`.
8. `web/components/screener/__tests__/RelativePerformanceChart.test.tsx` — update `makeResponse`'s
   fixture to the new field shape; add a case covering a `"source-unavailable"` reason distinct
   from the existing `"insufficient-history"`-shaped (reason-less) case.
9. `web/components/screener/__tests__/DrillDownView.test.tsx` — add one new case: chart unavailable
   with a `reason` set, asserting `drilldown-chart-unavailable`'s text + `data-reason`.

No other file is in scope. No `api/` change (the field already exists there).

---

## Implementation Checklist

1. **`web/lib/types/screener.ts`**: add
   `export type UnavailableReason = "insufficient-history" | "bad-symbol" | "source-unavailable";`
   near the other literal unions at the top of the file. Add `reason: UnavailableReason | null;` as
   the last field on both the `ChartSeries` and `RelativePerformanceSeries` interfaces.
2. **`web/lib/format-unavailable-reason.ts`** (new file): export
   `formatUnavailableReason(reason: UnavailableReason | null, context: "timeframe" | "window"):
   string`. Mapping: `"bad-symbol"` → `"Symbol configuration issue"`; `"source-unavailable"` →
   `"Data source unavailable"`; `"insufficient-history"` or `null` → `` `Not enough history ${context
   === "timeframe" ? "at this timeframe" : "for this window"}` `` (this exact fallback preserves
   today's copy byte-for-byte for the pre-RFC-005 default case).
3. **`CoinPanel.tsx`**: replace the hardcoded `chart-unavailable` div's children and add
   `data-reason={panel.chart.reason ?? undefined}`; text becomes
   `formatUnavailableReason(panel.chart.reason, "timeframe")`.
4. **`DrillDownView.tsx`**: same transformation on `drilldown-chart-unavailable`, driven by
   `view?.chart.reason ?? null`.
5. **`RelativePerformanceChart.tsx`**: inside the `unavailableCoins.map(...)`, replace the
   `<span key={s.symbol}>{s.symbol}: N/A for this window</span>` with
   `<span key={s.symbol} data-testid={\`rp-unavailable-${s.symbol}\`} data-reason={s.reason ??
   undefined}>{s.symbol}: {formatUnavailableReason(s.reason, "window")}</span>`.
6. **`format-unavailable-reason.test.ts`** (new file): assert all 3 named reasons in both contexts,
   plus `null` in both contexts, produce the expected strings (7 assertions: 3×2 + 1 null case where
   context doesn't change which branch fires structurally, so 2 null assertions — 8 total). Add the
   same SANDBOX-NOTE-style disclosure this repo's other new test files carry (see Session
   Constraints).
7. **`ScreenerBoard.test.tsx`**: `makeCoin`'s default `chart` fixture and the AC-19 case's override
   both need `reason: null` added (TypeScript will otherwise fail to compile once `reason` is
   required on the interface — this is a **required** mechanical fixture update, not optional). Add
   one new `it(...)` case: `chart: { price: [], sma: [], available: false, reason: "bad-symbol" }`,
   assert `chart-unavailable`'s text contains "Symbol configuration issue" and its `data-reason`
   attribute equals `"bad-symbol"`.
8. **`RelativePerformanceChart.test.tsx`**: `makeResponse`'s 3 series entries each need a `reason`
   field added (`null` for the two `available: true` entries; `"insufficient-history"` for
   `"NEWCOIN"`, preserving the existing assertion's exact text). Add one new case with a second
   unavailable coin carrying `reason: "source-unavailable"`, asserting its note text contains "Data
   source unavailable" and differs from the first unavailable coin's note text.
9. **`DrillDownView.test.tsx`**: add one new case: `fetchScalp` resolves with `chart: { price: [],
   sma: [], available: false, reason: "source-unavailable" }`; assert
   `drilldown-chart-unavailable`'s text contains "Data source unavailable" and its `data-reason`
   equals `"source-unavailable"`. Mark written-but-unexecuted per this file's existing SANDBOX NOTE
   convention (same as the two cases the prior slice added).

---

## Verification Evidence (Test Procedure)

Cannot be executed in this session (no `device_bash`; this session's own cloud sandbox has npm
registry egress blocked — same constraint recorded in the prior slice's EVL). Exact commands for
the user, or a future session with `device_bash`, to run:

```
cd web
pnpm test -- format-unavailable-reason.test.ts
pnpm test -- ScreenerBoard.test.tsx
pnpm test -- RelativePerformanceChart.test.tsx
pnpm test -- DrillDownView.test.tsx
pnpm test                      # full vitest suite — checks AC-6 (no regression)
```

Every new/modified test case in this plan is written-but-unexecuted in the same sense as this
file's own precedent (`getjson-timeout-catch_PLAN_19-09-26.md`) — not to be described as VERIFIED,
PASSING, or confirmed until an actual `pnpm test` run has been observed. What this session *can*
verify without execution: a direct read of the edited files for TypeScript shape correctness (every
call site's `reason` access matches the new interface fields) — recorded in EXECUTE Results as a
static check, explicitly distinguished from a real type-check or test run.

No manual/exploratory browser check is needed for this slice — unlike AC-1 in the prior slice
(timeout timing), reason-value rendering has no timing-dependent behavior; the `pnpm test` commands
above are sufficient to close every AC.

---

## EXECUTE Results (19-09-26)

**Status: DONE_WITH_CONCERNS.** All 9 Touchpoints applied exactly as specified in the Implementation
Checklist, written to the device via `device_commit_files`, and each independently re-staged from
the device and byte-diffed clean against the pre-commit edited copy (per this repo's own
operational lesson about `device_commit_files` silently not landing — checked explicitly, all 9
clean).

**What changed, per file:**
1. `web/lib/types/screener.ts` — added `export type UnavailableReason = "insufficient-history" |
   "bad-symbol" | "source-unavailable";` and `reason: UnavailableReason | null;` on both
   `ChartSeries` and `RelativePerformanceSeries`.
2. `web/lib/format-unavailable-reason.ts` (new) — `formatUnavailableReason(reason, context)` per
   Implementation Checklist item 2, exact mapping as specified.
3. `CoinPanel.tsx` — `chart-unavailable` div now renders `formatUnavailableReason(panel.chart.reason,
   "timeframe")` and carries `data-reason`.
4. `DrillDownView.tsx` — same transformation on `drilldown-chart-unavailable`, driven by
   `view?.chart.reason ?? null`.
5. `RelativePerformanceChart.tsx` — each unavailable coin's `<span>` now carries its own
   `data-testid={\`rp-unavailable-${symbol}\`}`, `data-reason`, and reason-specific text via the
   shared formatter (`"window"` context).
6. `format-unavailable-reason.test.ts` (new) — 4 cases per Implementation Checklist item 6 (named
   reasons in both contexts, `insufficient-history`/`window` framing, `null` fallback, uniqueness
   check across the 3 named reasons).
7. `ScreenerBoard.test.tsx` — `makeCoin`'s default chart fixture and the AC-19 override both gained
   `reason: null`; the drill-down-mock's chart fixture also gained `reason: null` (required for
   compilation once the field is non-optional — this was flagged as required in the Implementation
   Checklist, not a surprise). One new case added: `bad-symbol` → "Symbol configuration issue" +
   `data-reason`.
8. `RelativePerformanceChart.test.tsx` — `makeResponse`'s 3 fixture entries gained `reason` (`null`
   ×2, `"insufficient-history"` for `NEWCOIN` — the existing assertion's expected text changed from
   "N/A for this window" to "Not enough history for this window" to match the new copy, since the
   old hardcoded string is gone by design). One new case added: a second unavailable coin
   (`DEADFEED`, `"source-unavailable"`) asserted to render different text and a different
   `data-reason` than `NEWCOIN`.
9. `DrillDownView.test.tsx` — `makeScalpView`'s chart fixture gained `reason: null`. One new case
   added: `"source-unavailable"` → "Data source unavailable" + `data-reason` on
   `drilldown-chart-unavailable`.

**Deviations:** none. All 9 files matched the Implementation Checklist exactly; no touchpoint
outside the planned 9 files was modified.

**Verification attempt:** tests could not be run (no `device_bash`; `npm`/`pnpm install` in this
session's own cloud sandbox hits `403 Forbidden` on `registry.npmjs.org` — confirmed again this
session via `npx typescript`, same egress block recorded in the prior slice). What WAS verified: a
pre-existing global `tsc` binary in this cloud sandbox (not this project's own pinned toolchain, no
`node_modules`) ran `tsc --noResolve --noEmit` against all 9 edited/new files. Every diagnostic
produced was module-resolution noise expected without `node_modules` or this project's path aliases
(`Cannot find module '@/...'`, `Cannot find module 'react'/'vitest'/'lightweight-charts'`, implicit-
`any` JSX/parameter warnings from the missing React type declarations) — **zero** diagnostics of a
kind that would indicate an actual defect in this change (no `TS2322` assignment mismatch, no
`TS2339` missing property, no `TS2741`/`TS2353` object-literal shape errors). A targeted grep across
all of `web/` for every `available: (true|false)` literal confirmed no `ChartSeries`- or
`RelativePerformanceSeries`-shaped fixture anywhere in the tree was missed — all now carry `reason`.

**AC-1 through AC-6 remain unverified by execution** — this was already the accepted Session
Constraint at VALIDATE time (V6 FAIL, accepted), not a new gap. The commands below must be run on
the user's own machine to close EVL.

**Operational note:** the first `device_commit_files` call for *this plan file's own* EXECUTE-
Results update silently did not land (re-stage + byte-diff caught it: the device still held the
pre-EXECUTE PLAN/DRAFT content after a `written: [...]`, `rejected: []` success response). A second
`device_commit_files` call with `force: true` on the same path landed correctly, confirmed clean.
This is the exact failure mode this task folder's own precedent (`getjson-timeout-catch_PLAN_19-09-
26.md`) named as the reason every EXECUTE write in this repo must be re-staged and byte-diffed, not
trusted from the write call's own response alone — recorded here as a second live occurrence, not a
hypothetical.

## EVL Results (19-09-26, run by the user)

- `pnpm test` (full suite) — **all passed**, except the known, pre-existing `e2e/screener.spec.ts`
  vitest-collection failure (`vitest.config.ts` doesn't exclude `e2e/` from vitest's own collection —
  same gap the prior slice found; tracked in `process/general-plans/backlog/vitest-config-e2e-
  exclude_19-09-26.md`, not a regression from this plan — nothing in this plan's Touchpoints includes
  `e2e/` or `vitest.config.ts`).

**Net result: all 6 Acceptance Criteria (AC-1 through AC-6) are now verified.** The V6 gap accepted
at VALIDATE (no in-session test execution possible) is closed by this real run, same pattern as the
prior RFC-006 slice.

---

## Resume and Execution Handoff

- **Last completed step:** EVL (19-09-26) — user confirmed the full `pnpm test` suite passed except
  the known, pre-existing `e2e/screener.spec.ts` vitest-collection gap. Plan is **✅ VERIFIED**.
- **Next step:** UPDATE PROCESS — archive this plan's findings (phase report written:
  `momentum-screener_17-09-26-RFC-006-reason-value-rendering-phase-report_19-09-26.md`), update
  `process/context/tests/all-tests.md`'s inventory (done), and close this task-folder thread of
  RFC-006 — both slices its own Overview named as in-scope (`getjson-timeout-catch` and
  `reason-value-rendering`) are now done; the dead-data-rendering-convention-unification item stays
  separately queued, per both slices' own Out-of-scope sections.
- **Continuity pointer:** this task folder continues from RFC-005/RFC-006's report/plan lineage in
  `momentum-screener_17-09-26`; see `getjson-timeout-catch_PLAN_19-09-26.md` in this same folder for
  the precedent on the no-`device_bash` / no-`vc-*`-subagent session-constraint pattern this plan
  also carries.
- **Context references:** `process/context/all-context.md` and `process/context/tests/all-tests.md`
  — the latter's inventory now reflects this plan's 7 new/9 modified test cases.

---

## VALIDATE Contract (V1–V7)

**Gate: CONDITIONAL** — accepted-with-concerns, consistent with this task folder's own precedent
(the prior slice's VALIDATE gate was also CONDITIONAL-accepted for the same structural reason: real
test execution is not possible from this session).

| Gate | Check | Result |
|---|---|---|
| V1 (scope) | Touchpoints match Overview's stated scope; no `api/`, no `NarrativeStrip`/`LegTimelineBanner`/`SignalDetailPanel` | PASS |
| V2 (vacuous-green ban) | Every AC has a concrete assertion path, not just an Agent-Probe | PASS — AC-1 through AC-6 all map to a specific `it(...)` case or a direct interface read; no AC relies solely on manual inspection |
| V3 (contract coverage) | Each Acceptance Criterion maps to at least one Implementation Checklist item and one Touchpoint | PASS — AC-1→item 1; AC-2→items 3,7; AC-3→items 4,9; AC-4→items 5,8; AC-5→items 2,6; AC-6→items 7,8 |
| V4 (blast radius) | No Touchpoint outside the 9 files listed | PASS |
| V5 (reversibility) | Every change is additive (new optional-shaped field made required only in already-hand-maintained fixtures) or a pure-function extraction; nothing destructive | PASS |
| V6 (test executability) | Can this session run the tests it just specified? | **FAIL, accepted** — no `device_bash`, npm registry blocked in this cloud sandbox. Same accepted gap as the prior slice; commands handed to the user instead (Verification Evidence section) |
| V7 (naming/convention compliance) | kebab-case new file (`format-unavailable-reason.ts`), `data-testid`/`data-reason` pattern matches existing `data-state` precedent (`momentum-state`, `trend-direction`) | PASS |

**Concerns accepted by proceeding to EXECUTE (once explicitly approved):**
1. V6 — no in-session test execution; EVL closes only after the user runs the commands above on
   their own machine, exactly as the prior slice closed.
2. The `format-unavailable-reason.test.ts` file is new (no existing file to append to) — its own
   SANDBOX NOTE will be written fresh rather than copied from a sibling, first time this repo adds
   that disclosure to a `web/lib/__tests__/` file rather than a `web/components/**/__tests__/` file.

---

## /goal Block

```
SESSION GOAL: reason-value rendering — RFC-006 slice 2/2 (momentum-screener screener surface)
Charter + umbrella plan: N/A — single SIMPLE plan, inner-loop RFC of momentum-screener_17-09-26
Autonomy: standard — no standing /goal active; EXECUTE requires this session's explicit approval per turn
Hard stop conditions / safety constraints:
- No file outside the 9 Touchpoints listed above
- No backend (api/) change
- No unification of the 3 dead-data-rendering conventions (separately queued)
- EXECUTE does not begin without explicit "ENTER EXECUTE MODE"
Next phase: EXECUTE (awaiting approval) — process/general-plans/active/momentum-screener_17-09-26/reason-value-rendering_PLAN_19-09-26.md
Validate contract: inline in plan (## VALIDATE Contract section above)
Execute start: no fully-auto commands (device_bash unavailable) | e2e spec: N/A | probe scenario: N/A | high-risk pack: no
```
