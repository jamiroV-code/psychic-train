# Dead-Data Notice Unification — Plan

**Date**: 20-09-26
**Status**: DRAFT — awaiting "ENTER VALIDATE MODE"
**Complexity**: Simple
**Slug**: `dead-data-notice-unification`
**Parent program**: `momentum-screener_17-09-26` (inner-loop item; RFC-006's own Overview separately
queued this as "unification of the 3 existing dead-data-rendering conventions", distinct from and
after the two already-closed RFC-006 slices)
**Governing SPEC**: `process/general-plans/active/momentum-screener_17-09-26/momentum-screener_SPEC_17-09-26.md`
(SPEC phase skipped for this inner-loop item, same precedent as RFC-005 and both RFC-006 slices)

---

## Overview

RFC-006's two slices closed the *content* gap in dead-data rendering:
`momentum-screener_17-09-26-RFC-006-getjson-timeout-catch-phase-report_19-09-26.md` made every
fetch call site catch and surface its own error instead of hanging or white-screening, and
`momentum-screener_17-09-26-RFC-006-reason-value-rendering-phase-report_19-09-26.md` (plan:
`reason-value-rendering_PLAN_19-09-26.md`, ✅ VERIFIED 19-09-26) made the `chart-unavailable` /
`drilldown-chart-unavailable` / `rp-unavailable-{symbol}` sites distinguish *why* a series is
missing via a new shared `formatUnavailableReason()` helper. Both slices explicitly deferred a
third, structural gap in their own Overview/Out-of-scope sections: the same "dead data" family of
UI states (a chart that can't render, a fetch that failed) is currently expressed through **two
independent, hand-duplicated markup shapes** — a `reason`-driven `<div>` at 3 sites
(`CoinPanel`, `DrillDownView`'s chart branch, `RelativePerformanceChart`'s per-coin note) and a
`message`-driven `<div>`/`<span>` at 4 sites (`DrillDownView`'s error branch, `NarrativeStrip`,
`LegTimelineBanner`, `RelativePerformanceChart`'s `rp-error`) — with no shared component behind
either shape. This plan (RESEARCH + INNOVATE already run in prior sessions of this program)
implements the INNOVATE-locked decision: a single `DeadDataNotice` component with a discriminated
union on `"message" in props`, wired into all 7 existing render sites with **zero testid renames
and zero placement changes** — a pure implementation-detail swap, not a behavior or contract
change. Two pre-existing test-coverage gaps (`LegTimelineBanner`'s error branch,
`RelativePerformanceChart`'s `rp-error`) are closed in the same pass since both files are being
touched anyway.

### Session Constraints (carried forward, do not soften)

This plan is authored from a Cowork cloud session with no `device_bash` — there is no shell on the
user's Windows machine reachable from here; file edits, when EXECUTE runs, go through the
remote-devices bridge one read/write at a time, not via shell commands run from this session. The
`vc-*` named subagent types this repo's CLAUDE.md routes RIPER-5 phases to are not spawnable in
this session. This session performed PLAN directly against RESEARCH/INNOVATE findings supplied by
the orchestrator, re-verifying every touchpoint's live current line numbers and content by staging
and reading each file fresh (not trusting the RESEARCH-supplied line numbers as final) — same
discipline as `reason-value-rendering_PLAN_19-09-26.md`. **Every line number cited below was
confirmed against a live read taken during this PLAN session, not carried over unverified.**

Consequence: **EXECUTE and every test-running gate in this plan cannot be run from inside this
session.** They are written below as exact commands for the user, or a future session with
`device_bash`, to run.

Out of scope for this plan (per RFC-006's own Overview and both prior slices' Out-of-scope
sections, carried forward unchanged):
- `SignalDetailPanel.tsx` — no `ChartSeries.reason`/error-message involvement; untouched.
- `ScreenerBoard.tsx`'s `board-error` — a different, page-level fetch-error site not part of the
  per-component "dead data" family this plan unifies; untouched.
- Any backend change — this is a pure frontend markup-consolidation slice.
- `aria-live`/`role="alert"` additions — no existing error/unavailable render in this codebase uses
  a live region; this plan does not introduce one.
- Any change to `format-unavailable-reason.ts` or `web/lib/types/screener.ts` — both stay as pure
  upstream dependencies, imported only.
- Renaming, moving, or restructuring any existing `data-testid` value, or changing where in the DOM
  tree a notice renders relative to its siblings — the INNOVATE decision is an implementation swap,
  not a UX change.

See `process/context/all-context.md` for project-wide architecture/conventions and
`process/context/tests/all-tests.md` for the current test inventory and known gaps.

---

## Phase Completion Rules

- PLAN is complete when this file is written and contains all required sections (this file).
- PLAN does not proceed to EXECUTE directly. VALIDATE converts the Acceptance Criteria and
  Touchpoints below into an executable gate checklist.
- EXECUTE may not begin without explicit "ENTER EXECUTE MODE" from the user (hard gate, no
  exception under this plan's own Session Constraints).
- This plan is SIMPLE: one feature area (`web/components/screener/`), ~9-file blast radius, no
  schema/auth/API change, no phase-program gates — single task folder, no sub-plans.

---

## INNOVATE Decision (locked — restated verbatim for execute-readiness, not re-derived)

One new component, `web/components/screener/DeadDataNotice.tsx`:

```tsx
import { formatUnavailableReason } from "@/lib/format-unavailable-reason";
import type { UnavailableReason } from "@/lib/types/screener";

// discriminated union on "message" in props
type ReasonVariant  = { testId: string; reason: UnavailableReason | null; context: "timeframe" | "window"; className?: string };
type MessageVariant = { testId: string; message: string; className?: string };
export type DeadDataNoticeProps = ReasonVariant | MessageVariant;

export function DeadDataNotice(props: DeadDataNoticeProps) {
  if ("message" in props) {
    return <div data-testid={props.testId} className={props.className}>{props.message}</div>;
  }
  return (
    <div data-testid={props.testId} data-reason={props.reason ?? undefined} className={props.className}>
      {formatUnavailableReason(props.reason, props.context)}
    </div>
  );
}
```

No `"use client"` directive — same as `CoinPanel.tsx` and `SignalDetailPanel.tsx`, this is a pure
presentational function component with no hooks/state, safe to import from both client and
(hypothetically) server components.

Per-site wiring table (testid and placement UNCHANGED — locked, restated from INNOVATE):

| Component | File | Instance | testId (unchanged) | Variant |
|---|---|---|---|---|
| CoinPanel | `CoinPanel.tsx:45-55` | chart unavailable | `chart-unavailable` | reason, `context="timeframe"` |
| DrillDownView | `DrillDownView.tsx:74-80` | chart unavailable | `drilldown-chart-unavailable` | reason, `context="timeframe"` |
| DrillDownView | `DrillDownView.tsx:70-72` | fetch error | `drilldown-error` | message |
| NarrativeStrip | `NarrativeStrip.tsx:40-46` | fetch error | `narrative-error` | message |
| LegTimelineBanner | `LegTimelineBanner.tsx:38-44` | fetch error | `leg-timeline-error` | message |
| RelativePerformanceChart | `RelativePerformanceChart.tsx:137-145` | per-coin unavailable | `rp-unavailable-{symbol}` | reason, `context="window"` |
| RelativePerformanceChart | `RelativePerformanceChart.tsx:133` | fetch error | `rp-error` | message |

**`leg-timeline-error` testid discrepancy check (per orchestrator's explicit ask): NONE FOUND.**
The live file was staged and read fresh during this PLAN session
(`LegTimelineBanner.tsx` line 41): `<span data-testid="leg-timeline-error">{error}</span>` — the
testid RESEARCH/INNOVATE assumed is exactly the real one. No correction needed.

**Tag-name/`querySelector` assertion check (per orchestrator's explicit ask): NONE FOUND.** All of
`NarrativeStrip.test.tsx`, `LegTimelineBanner.test.tsx`, `RelativePerformanceChart.test.tsx`,
`ScreenerBoard.test.tsx`, `DrillDownView.test.tsx`, and `web/e2e/screener.spec.ts` were staged and
read in full during this PLAN session. Every assertion that reaches these elements does so via
`getByTestId`/`queryByTestId`/`querySelector('[data-testid="..."]')` (attribute selector, not tag
selector) and then reads `.textContent` / `.dataset.*` / `.getAttribute(...)` — never `.tagName`,
never a bare-tag CSS selector (`querySelector('span...')` or `('div...')`). **No touchpoint is
added for this** — the `<span>`→`<div>` change on `narrative-error`, `leg-timeline-error`, and
`rp-unavailable-{symbol}` (see Touchpoint 6 note) is confirmed safe against every test file in this
blast radius, verified by direct read rather than assumed.

---

## Acceptance Criteria

1. **AC-1 (reason variant renders correctly):** `DeadDataNotice` given `{ reason, context }`
   renders `formatUnavailableReason(reason, context)` as its text content and carries
   `data-reason={reason ?? undefined}`. **Proven by:** `ScreenerBoard.test.tsx`'s existing
   `"distinguishes a bad-symbol chart-unavailable reason..."` case (CoinPanel path),
   `DrillDownView.test.tsx`'s existing `"distinguishes a source-unavailable chart reason..."` case,
   and `RelativePerformanceChart.test.tsx`'s existing `"distinguishes a source-unavailable reason
   from an insufficient-history reason, per coin"` case — all three pass unmodified after the swap.
   **Strategy:** Fully-Automated.
2. **AC-2 (message variant renders correctly):** `DeadDataNotice` given `{ message }` renders
   `message` as its text content and carries no `data-reason` attribute. **Proven by:**
   `NarrativeStrip.test.tsx`'s existing `"replaces the whole section with narrative-error..."` case,
   `DrillDownView.test.tsx`'s existing `"renders drilldown-error..."` case, and the two **new**
   cases added by this plan (`LegTimelineBanner.test.tsx`, `RelativePerformanceChart.test.tsx`) —
   see New Test Cases below. **Strategy:** Fully-Automated.
3. **AC-3 (no testid renamed):** A diff of the 5 edited component files shows every existing
   `data-testid` string value byte-identical to its pre-change value; no new `data-testid` string
   introduced except the ones already named in the wiring table. **Proven by:** EXECUTE's own
   pre-write/post-write string-literal diff (see Implementation Checklist step 9) plus every
   existing test in the blast radius passing unmodified (a renamed testid fails its own
   `getByTestId` call immediately). **Strategy:** Fully-Automated + Hybrid (full `pnpm test`).
4. **AC-4 (siblings untouched):** In `CoinPanel.tsx`, the header (`coin-panel__symbol`,
   `open-drilldown-{symbol}`), `SignalDetailPanel`, `momentum-state`/`trend-direction` spans, and
   `gain-readout-row` render unchanged. In `DrillDownView.tsx`, the header (`symbol`,
   `drilldown-close`) and `drilldown-timeframe-toggle` render unchanged regardless of branch. In
   `RelativePerformanceChart.tsx`, `rp-timeframe-toggle` and `rp-chart-container` render
   unconditionally regardless of `error`/`unavailableCoins` state. **Proven by:**
   `ScreenerBoard.test.tsx`'s AC-5/AC-16/AC-20/AC-7 cases, `DrillDownView.test.tsx`'s AC-18 cases
   and the existing AC-2 error case's own sibling-survives assertions, and the **new**
   `RelativePerformanceChart.test.tsx` case's explicit `rp-chart-container`/`rp-timeframe-toggle`
   presence assertions (see New Test Cases). **Strategy:** Fully-Automated.
5. **AC-5 (NarrativeStrip/LegTimelineBanner confirmed/candidate sections stay absent on error):**
   Neither component's error branch reintroduces `narrative-confirmed`/`narrative-unconfirmed` or
   `leg-confirmed-boundaries`/`leg-candidate-boundaries` — mechanically impossible without
   fabricating data, per INNOVATE rationale, and this plan does not attempt it. **Proven by:**
   `NarrativeStrip.test.tsx`'s existing explicit `not.toBeInTheDocument()` assertions on those two
   testids, and the **new** `LegTimelineBanner.test.tsx` case's equivalent assertions (see New Test
   Cases). **Strategy:** Fully-Automated.
6. **AC-6 (LegTimelineBanner error-branch gap closed):** The new
   `LegTimelineBanner.test.tsx` case passes: `leg-timeline-error` renders the thrown message,
   `leg-timeline-banner`'s `aria-label="Leg timeline"` wrapper stays mounted, loading/body testids
   are absent. **Strategy:** Fully-Automated.
7. **AC-7 (RelativePerformanceChart `rp-error` gap closed):** The new
   `RelativePerformanceChart.test.tsx` case passes: `rp-error` renders the thrown message,
   `rp-unavailable-note` does not render (no `data` to derive it from), `rp-chart-container` and
   `rp-timeframe-toggle` stay mounted. **Strategy:** Fully-Automated.
8. **AC-8 (`SignalDetailPanel`/`ScreenerBoard` untouched):** Neither file appears in the write set;
   a diff shows zero changes. **Proven by:** EXECUTE's own file-list accounting (only the 8 files
   in Touchpoints below are written). **Strategy:** Fully-Automated (mechanical check).
9. **AC-9 (no tag-name assertion broken):** The pre-existing grep/read confirmation above (no
   tag-name/`querySelector`-by-tag assertion anywhere in the blast radius's test files or the
   Playwright spec) still holds after EXECUTE — re-run the same check as a final EXECUTE step
   before EVL, since a file could in principle have drifted between PLAN and EXECUTE sessions.
   **Strategy:** Fully-Automated (grep).
10. **AC-10 (no new TypeScript error):** Every call site's prop usage matches
    `DeadDataNoticeProps`'s discriminated union exactly (either both `reason`+`context`, or only
    `message` — never a mix, never neither). A static, no-`node_modules` `tsc --noResolve --noEmit`
    pass over the 6 touched `.tsx` files (same method as `reason-value-rendering_PLAN_19-09-26.md`'s
    EXECUTE Results) produces zero `TS2322`/`TS2339`/`TS2741`/`TS2353`-class diagnostics; a real
    `pnpm build`/`tsc` run on the user's machine closes this for real. **Strategy:** Hybrid.

---

## Touchpoints

All line numbers below were confirmed by staging and reading each live file during this PLAN
session (see Session Constraints) — not carried over from RESEARCH unverified.

1. **`web/components/screener/DeadDataNotice.tsx` (NEW)** — the shared component, exact code given
   in the INNOVATE Decision section above.
2. **`web/components/screener/CoinPanel.tsx`**
   - Line 3: remove `import { formatUnavailableReason } from "@/lib/format-unavailable-reason";`
     (no longer called directly from this file).
   - Add `import { DeadDataNotice } from "@/components/screener/DeadDataNotice";` alongside the
     existing imports (after line 2, before line 4's `TIMEFRAMES` import — exact position not
     load-bearing, just group with the other same-directory component imports).
   - Lines 45-55 (the `panel.chart.available ? <MiniChart .../> : (<div ...>...</div>)` block):
     replace the `<div data-testid="chart-unavailable" ...>...</div>` (lines 48-54) with:
     ```tsx
     <DeadDataNotice
       testId="chart-unavailable"
       reason={panel.chart.reason}
       context="timeframe"
       className="coin-panel__unavailable"
     />
     ```
     The surrounding `panel.chart.available ? <MiniChart .../> : (...)` ternary structure (line 45,
     47, 55) is untouched.
3. **`web/components/screener/DrillDownView.tsx`**
   - Line 6: remove `import { formatUnavailableReason } from "@/lib/format-unavailable-reason";`.
   - Add `import { DeadDataNotice } from "@/components/screener/DeadDataNotice";` alongside the
     existing imports.
   - Lines 70-72 (`{error ? (<div data-testid="drilldown-error">{error}</div>) : (`): replace line
     71 with:
     ```tsx
     <DeadDataNotice testId="drilldown-error" message={error} />
     ```
     `error` is narrowed to `string` (non-null) by the enclosing `error ? (...)` truthy branch —
     no `?? ""` fallback needed or wanted (would silently hide a compile-time narrowing check if
     ever misapplied). Lines 70 and 72 (the ternary itself) are untouched.
   - Lines 74-80 (inside the `<>...</>` fragment, the `view?.chart.available ? <MiniChart .../> :
     (<div data-testid="drilldown-chart-unavailable" ...>...</div>)` block): replace the `<div
     data-testid="drilldown-chart-unavailable" ...>...</div>` (lines 77-79) with:
     ```tsx
     <DeadDataNotice
       testId="drilldown-chart-unavailable"
       reason={view?.chart.reason ?? null}
       context="timeframe"
     />
     ```
     Lines 74-76 and 80-89 (the ternary wrapper, the always-rendered `scalp-rsi-reading` div at
     line 84) are untouched.
4. **`web/components/screener/NarrativeStrip.tsx`**
   - Add `import { DeadDataNotice } from "@/components/screener/DeadDataNotice";` alongside the
     existing imports (this file currently has no `formatUnavailableReason` import to remove).
   - Lines 40-46 (`if (error) { return (<section ...><span data-testid="narrative-error">{error}
     </span></section>); }`): replace line 43 with:
     ```tsx
     <DeadDataNotice testId="narrative-error" message={error} />
     ```
     `error` is narrowed to `string` by the enclosing `if (error) {` guard. Lines 42 and 44-45
     (the `<section>` wrapper with its `aria-label`) are untouched — the section wrapper element
     itself does not change tag; only the inner element (line 43) changes from `<span>` to
     `<div>` as a result of using `DeadDataNotice` (accepted, see Verification Evidence below).
5. **`web/components/screener/LegTimelineBanner.tsx`**
   - Add `import { DeadDataNotice } from "@/components/screener/DeadDataNotice";` alongside the
     existing imports.
   - Lines 38-44 (`if (error) { return (<section ...><span data-testid="leg-timeline-error">
     {error}</span></section>); }`): replace line 41 with:
     ```tsx
     <DeadDataNotice testId="leg-timeline-error" message={error} />
     ```
     `error` is narrowed to `string` by the enclosing `if (error) {` guard. Lines 40 and 42-43 (the
     `<section>` wrapper) are untouched — same `<span>`→`<div>` inner-element tag change as
     NarrativeStrip, accepted for the same reason.
   - Testid trace (added during VALIDATE, closing a documentation gap the VALIDATE pass found):
     `leg-composite-variant`, asserted absent in the new error-branch test case (Touchpoint 7,
     `LegTimelineBanner.test.tsx`), is the `<div data-testid="leg-composite-variant">` element at
     `LegTimelineBanner.tsx:62`, inside the success-render branch (lines 60-100) — the "Composite:
     full (LiqTide) / reduced (FRED + DefiLlama)" indicator. It is never rendered by the
     `if (error) {...}` branch (lines 38-44) this plan touches, so the new test's absence-assertion
     is correct. Confirmed by a live re-read of `LegTimelineBanner.tsx` during this VALIDATE pass.
6. **`web/components/screener/RelativePerformanceChart.tsx`**
   - Line 6: remove `import { formatUnavailableReason } from "@/lib/format-unavailable-reason";`.
   - Add `import { DeadDataNotice } from "@/components/screener/DeadDataNotice";` alongside the
     existing imports.
   - Line 133 (`{error && <div data-testid="rp-error">{error}</div>}`): replace with:
     ```tsx
     {error && <DeadDataNotice testId="rp-error" message={error} />}
     ```
     `error` is narrowed to `string` within the `&&` right-hand operand (TypeScript control-flow
     narrowing on a bare identifier check) — no tag change here, `rp-error` was already a `<div>`.
   - Lines 137-145 (the `unavailableCoins.length > 0 && (<div data-testid="rp-unavailable-note"
     ...>{unavailableCoins.map((s) => (<span key={s.symbol} data-testid={...} data-reason={...}>
     {s.symbol}: {formatUnavailableReason(...)}</span>))}</div>)` block): replace the inner
     `.map()` callback body (lines 140-142) with:
     ```tsx
     <span key={s.symbol}>
       {s.symbol}:{" "}
       <DeadDataNotice testId={`rp-unavailable-${s.symbol}`} reason={s.reason} context="window" />
     </span>
     ```
     **Design note (why this exact shape, not a 1:1 span replacement):** the existing markup put
     the `{symbol}: ` prefix and the reason text inside the *same* `<span data-testid=
     "rp-unavailable-{symbol}">` element. `DeadDataNoticeProps` has no slot for an extra prefix
     alongside `reason`/`context`, so the prefix must live outside the `DeadDataNotice`-rendered
     element rather than inside it. This is safe against both existing assertions in
     `RelativePerformanceChart.test.tsx`: the first case reads `rp-unavailable-note`'s (the outer
     wrapper's) aggregate `.textContent`, which still contains `"NEWCOIN: Not enough history for
     this window"` regardless of which descendant element the "NEWCOIN: " text node sits in; the
     second case reads each per-coin testid element's own `.textContent`/`.getAttribute(
     "data-reason")` and never asserts the `{symbol}: ` prefix is *inside* that specific element —
     only that the reason-text and `data-reason` are present and differ between coins. Both keep
     passing unmodified. The `rp-unavailable-note` outer wrapper div (line 138) and the `.map()`
     call itself (line 139, 143) are untouched. `data-testid`/`data-reason` move from the outer
     `<span>` onto the `DeadDataNotice`-rendered `<div>` — the wrapping `<span key={s.symbol}>` that
     remains carries neither.
7. **`web/components/screener/__tests__/LegTimelineBanner.test.tsx`** — add one new `it()` case
   (exact text in New Test Cases below), mirroring `NarrativeStrip.test.tsx`'s
   `"replaces the whole section with narrative-error when the fetch rejects (AC-3)"` pattern
   exactly (same `vi.fn()`-mock-rejects → `waitFor` → assert error testid + message text → assert
   section wrapper survives with its `aria-label` → assert loading/body testids absent).
8. **`web/components/screener/__tests__/RelativePerformanceChart.test.tsx`** — add one new `it()`
   case (exact text in New Test Cases below), same rejects-then-assert pattern, adapted to this
   component's own always-present-toolbar-and-chart-container convention (RelativePerformanceChart
   never fully replaces its body on error — see Touchpoint 6's `rp-error` wiring — so the new case
   also asserts `rp-chart-container`/`rp-timeframe-toggle` stay mounted, which is this component's
   own version of AC-4's "siblings untouched").

No other file is in scope. No `api/` change. `web/lib/format-unavailable-reason.ts` and
`web/lib/types/screener.ts` are read but not written.

---

## Public Contracts

- **New:** `export type DeadDataNoticeProps` (discriminated union, `ReasonVariant | MessageVariant`)
  and `export function DeadDataNotice(props: DeadDataNoticeProps)` from
  `web/components/screener/DeadDataNotice.tsx` — an internal component contract within
  `web/components/screener/`, not a wire/API contract. No consumer outside this directory is
  expected; if one appears later it must respect the discriminated union exactly (no partial-props
  call).
- **Unchanged:** every existing `data-testid`/`data-reason` attribute contract at all 7 render
  sites (see wiring table). `ChartSeries.reason`, `RelativePerformanceSeries.reason`,
  `UnavailableReason`, and `formatUnavailableReason(reason, context)`'s signature are all read-only
  dependencies of this plan, untouched.

---

## Blast Radius

`web/components/screener/` only:
- 1 new file (`DeadDataNotice.tsx`)
- 5 edited component files (`CoinPanel.tsx`, `DrillDownView.tsx`, `NarrativeStrip.tsx`,
  `LegTimelineBanner.tsx`, `RelativePerformanceChart.tsx`)
- 2 edited test files (`__tests__/LegTimelineBanner.test.tsx`,
  `__tests__/RelativePerformanceChart.test.tsx`)

No `web/lib/` change. No `api/` change. No `web/e2e/` change (confirmed by direct read: the
Playwright spec asserts none of the 7 testids this plan touches — see the tag-name-assertion check
above — so it needs no update; re-confirmed as a Verification Evidence step below rather than
assumed permanently true).

---

## Implementation Checklist

1. Create `web/components/screener/DeadDataNotice.tsx` with the exact code in the INNOVATE Decision
   section above (imports: `formatUnavailableReason` from `@/lib/format-unavailable-reason`,
   `UnavailableReason` from `@/lib/types/screener`).
2. Edit `CoinPanel.tsx`: drop the `formatUnavailableReason` import (line 3), add the
   `DeadDataNotice` import, replace lines 48-54 per Touchpoint 2.
3. Edit `DrillDownView.tsx`: drop the `formatUnavailableReason` import (line 6), add the
   `DeadDataNotice` import, replace line 71 per Touchpoint 3, replace lines 77-79 per Touchpoint 3.
4. Edit `NarrativeStrip.tsx`: add the `DeadDataNotice` import, replace line 43 per Touchpoint 4.
5. Edit `LegTimelineBanner.tsx`: add the `DeadDataNotice` import, replace line 41 per Touchpoint 5.
6. Edit `RelativePerformanceChart.tsx`: drop the `formatUnavailableReason` import (line 6), add the
   `DeadDataNotice` import, replace line 133 per Touchpoint 6, replace lines 140-142 per
   Touchpoint 6.
7. Add the new `it()` case to `LegTimelineBanner.test.tsx` (exact text below).
8. Add the new `it()` case to `RelativePerformanceChart.test.tsx` (exact text below).
9. Before committing any file via `device_commit_files`, diff each edited file's full list of
   `data-testid="..."` string literals (old vs. new) and confirm the set is identical except for
   no additions/removals/renames — this is AC-3's mechanical check, do it per file, not once at the
   end.
10. Re-run the tag-name/`querySelector`-by-tag grep (AC-9) across
    `NarrativeStrip.test.tsx`, `LegTimelineBanner.test.tsx`, `RelativePerformanceChart.test.tsx`,
    `ScreenerBoard.test.tsx`, `DrillDownView.test.tsx`, `web/e2e/screener.spec.ts` immediately
    before EVL — confirm still zero matches (this plan found zero at PLAN time; a clean re-check at
    EXECUTE/EVL time is the actual gate, not the PLAN-time finding by itself).
11. `device_commit_files` each of the 8 touched files (1 new + 7 edited), then re-stage and
    byte-diff each one against the local pre-commit copy before considering it landed — per this
    task folder's own operational lesson (`reason-value-rendering_PLAN_19-09-26.md` EXECUTE
    Results: a `device_commit_files` call reported `written: [...]` while silently not landing on
    first attempt). Do not trust the write call's own success response alone.
12. Run the Verification Evidence commands below (on the user's machine, or a future
    `device_bash`-capable session).

---

## New Test Cases (exact `it()` text and body)

### `web/components/screener/__tests__/LegTimelineBanner.test.tsx`

Add inside the existing `describe("LegTimelineBanner", ...)` block, after the last existing case:

```tsx
// dead-data-notice-unification: closes the pre-existing zero-coverage gap on
// this component's error branch — mirrors NarrativeStrip.test.tsx's
// equivalent case exactly (same vi.fn()-mock-rejects-then-assert pattern).
it("replaces the whole section with leg-timeline-error when the fetch rejects, keeping the confirmed/candidate body absent", async () => {
  const fetchData = vi.fn(async (): Promise<LegBoundaryResponse> => {
    throw new Error("API request timed out after 10000ms: /api/screener/legs");
  });
  render(<LegTimelineBanner fetchData={fetchData} />);

  await waitFor(() => expect(screen.getByTestId("leg-timeline-error")).toBeInTheDocument());
  expect(screen.getByTestId("leg-timeline-error").textContent).toContain(
    "API request timed out after 10000ms"
  );

  // Whole-section-replace: the banner section itself stays, its body does not.
  const section = screen.getByTestId("leg-timeline-banner");
  expect(section).toBeInTheDocument();
  expect(section.getAttribute("aria-label")).toBe("Leg timeline");
  expect(screen.queryByTestId("leg-timeline-loading")).not.toBeInTheDocument();
  expect(screen.queryByTestId("leg-confirmed-boundaries")).not.toBeInTheDocument();
  expect(screen.queryByTestId("leg-candidate-boundaries")).not.toBeInTheDocument();
  expect(screen.queryByTestId("leg-composite-variant")).not.toBeInTheDocument();
});
```

No new imports needed — `LegBoundaryResponse` is already imported at the top of this file.

### `web/components/screener/__tests__/RelativePerformanceChart.test.tsx`

Add inside the existing `describe("RelativePerformanceChart", ...)` block, after the last existing
case:

```tsx
// dead-data-notice-unification: closes the pre-existing zero-coverage gap on
// rp-error — same pattern as the LegTimelineBanner/NarrativeStrip error cases,
// adapted to this component's own convention: the toolbar and chart container
// stay mounted on error (nothing here is a whole-section replace).
it("renders rp-error when the fetch rejects, while the toolbar and chart container stay mounted", async () => {
  const fetchData = vi.fn(async (): Promise<RelativePerformanceResponse> => {
    throw new Error("API request timed out after 10000ms: /api/screener/relative-performance");
  });
  render(<RelativePerformanceChart fetchData={fetchData} />);

  await waitFor(() => expect(screen.getByTestId("rp-error")).toBeInTheDocument());
  expect(screen.getByTestId("rp-error").textContent).toContain(
    "API request timed out after 10000ms"
  );

  // No data to derive an unavailable-coins note from; nothing else fabricated.
  expect(screen.queryByTestId("rp-unavailable-note")).not.toBeInTheDocument();

  // Siblings survive — this component never whole-section-replaces on error.
  expect(screen.getByTestId("rp-timeframe-toggle")).toBeInTheDocument();
  expect(screen.getByTestId("rp-chart-container")).toBeInTheDocument();
});
```

No new imports needed — `RelativePerformanceResponse` is already imported at the top of this file.

---

## Verification Evidence

| Gate / Scenario | Strategy | Proves SPEC criterion |
|---|---|---|
| `pnpm test -- CoinPanel` — n/a, no dedicated file; covered via `ScreenerBoard.test.tsx` | Fully-Automated | AC-1, AC-3, AC-4 |
| `pnpm test -- ScreenerBoard.test.tsx` (existing `chart-unavailable`/`bad-symbol` cases) | Fully-Automated | AC-1, AC-3, AC-4 |
| `pnpm test -- DrillDownView.test.tsx` (existing chart/error cases) | Fully-Automated | AC-1, AC-2, AC-3, AC-4 |
| `pnpm test -- NarrativeStrip.test.tsx` (existing error case) | Fully-Automated | AC-2, AC-3, AC-5 |
| `pnpm test -- LegTimelineBanner.test.tsx` (new case, Touchpoint 7) | Fully-Automated | AC-2, AC-3, AC-5, AC-6 |
| `pnpm test -- RelativePerformanceChart.test.tsx` (existing + new case, Touchpoint 8) | Fully-Automated | AC-1, AC-2, AC-3, AC-4, AC-7 |
| Full `pnpm test` (whole vitest suite, checks for any unforeseen regression) | Fully-Automated | AC-3, AC-8 |
| `pnpm test:e2e` (Playwright, unaffected surface — confirms no regression at the boundary) | Hybrid | AC-3, AC-4 |
| Grep re-check: no `.tagName`/tag-selector assertion on the 7 touched testids across the blast-radius test files + e2e spec | Fully-Automated | AC-9 |
| File-list accounting: only the 8 Touchpoints files were written | Fully-Automated | AC-8 |
| `tsc --noResolve --noEmit` static pass (no `node_modules`, same method as the prior slice) over the 6 touched `.tsx` files, zero shape-error diagnostics | Hybrid | AC-10 |

Exact commands for the user, or a future `device_bash`-capable session, to run:

```
cd web
pnpm exec tsc --noEmit         # AC-10: real type-check with node_modules — web/package.json has no
                                # dedicated "typecheck" script, so this is the correct available
                                # invocation (added during VALIDATE; was missing from this block)
pnpm test -- ScreenerBoard.test.tsx
pnpm test -- DrillDownView.test.tsx
pnpm test -- NarrativeStrip.test.tsx
pnpm test -- LegTimelineBanner.test.tsx
pnpm test -- RelativePerformanceChart.test.tsx
pnpm test                      # full vitest suite — checks AC-3/AC-8 (no regression anywhere)
pnpm test:e2e                  # Playwright — confirms the unaffected e2e surface stays green
```

Every new/modified test case in this plan is written-but-unexecuted in the same sense as this task
folder's own precedent (`getjson-timeout-catch_PLAN_19-09-26.md`,
`reason-value-rendering_PLAN_19-09-26.md`) — not to be described as VERIFIED, PASSING, or confirmed
until an actual `pnpm test` run has been observed. What this session (PLAN) verified without
execution: direct reads of every touched file's live current content and every test file in the
blast radius, confirming line numbers, testid strings, and the absence of tag-name assertions
(recorded above under the INNOVATE Decision section) — explicitly distinguished from a real
type-check or test run, which EXECUTE/EVL must still perform.

No manual/exploratory browser check is needed for this slice — this is a pure implementation-detail
swap with no new timing-dependent behavior; the `pnpm test`/`pnpm test:e2e` commands above are
sufficient to close every AC.

---

## Test Infra Improvement Notes

- No new test infrastructure is introduced by this plan (no new mocking pattern, no new test
  utility). The two gap-closing cases reuse the exact `vi.fn()`-mock-rejects pattern already
  established in `NarrativeStrip.test.tsx` and `DrillDownView.test.tsx`.
- Backlog candidate (not part of this plan, noted for future consideration): a dedicated
  `DeadDataNotice.test.tsx` directly unit-testing the component in isolation (both variants,
  independent of any of the 7 call sites) would give this shared component its own coverage rather
  than relying entirely on its consumers' tests. Not added here because the INNOVATE decision this
  plan implements does not call for one, and every behavior it would cover is already exercised
  end-to-end through the 7 call sites' own existing + new tests (AC-1/AC-2 above). Flagged as a
  possible follow-up, not a gap this plan leaves silently unaddressed.
- The known, pre-existing `vitest.config.ts` / `web/e2e/screener.spec.ts` collection gap (tracked in
  `process/general-plans/backlog/vitest-config-e2e-exclude_19-09-26.md`) is unrelated to this plan's
  blast radius and is not affected by it either way.

---

## Resume and Execution Handoff

- **Last completed step:** PLAN (20-09-26) — this file written, all touchpoints re-verified against
  live source during this session (not carried over from RESEARCH unverified). Both explicit
  discrepancy checks the orchestrator asked for (`leg-timeline-error` testid name,
  tag-name/`querySelector` assertions in the affected test files + e2e spec) came back clean — no
  correction needed, no extra touchpoint required.
- **Next step:** VALIDATE — convert the 10 Acceptance Criteria and 8 Touchpoints above into an
  executable gate checklist; this plan's own Verification Evidence table already gives VALIDATE a
  starting proof-linkage per AC. EXECUTE does not begin without explicit "ENTER EXECUTE MODE" after
  VALIDATE.
- **Continuity pointer:** this task folder continues from RFC-005/RFC-006's report/plan lineage in
  `momentum-screener_17-09-26`; see `reason-value-rendering_PLAN_19-09-26.md` in this same folder
  for the precedent this plan follows on format, the no-`device_bash`/no-`vc-*`-subagent
  session-constraint pattern, and the `device_commit_files` byte-diff-verification lesson (repeated
  in Implementation Checklist step 11 here).
- **Context references:** `process/context/all-context.md` and `process/context/tests/all-tests.md`
  — the latter's inventory should be updated once this plan's 2 new/2 modified test cases are
  confirmed passing, same update pattern as both prior RFC-006 slices.
- **What this closes in RFC-006:** RFC-006's own Overview named three items — the two content
  slices (both ✅ VERIFIED) and this convention-unification item. Once this plan's EVL closes, the
  dead-data-rendering thread of RFC-006 is fully done, not just its two content slices.


---

## Validate Contract

**Gate: CONDITIONAL** — accepted-with-concerns, consistent with this task folder's own established
precedent. Both prior RFC-006 slices in this same folder —
`getjson-timeout-catch_PLAN_19-09-26.md` and `reason-value-rendering_PLAN_19-09-26.md` — reached
CONDITIONAL for the same structural reason: this session (like the PLAN/INNOVATE/RESEARCH sessions
before it) has no `device_bash` and no reliable npm-registry egress from its own cloud sandbox, so
no gate command below can actually be *run* in-session. That is a known, already-accepted
environment gap, not a new finding. Two genuinely new, non-blocking findings were surfaced during
this VALIDATE pass and are recorded below.

| Gate | Check | Result |
|---|---|---|
| V1 (scope) | Touchpoints match the Overview's stated scope; `SignalDetailPanel.tsx` and `ScreenerBoard.tsx` stay untouched; no `api/` change; no `aria-live` addition | PASS |
| V2 (vacuous-green ban) | Every AC maps to a concrete `it(...)` case (existing or new), not to Agent-Probe/Known-Gap alone | PASS, with one accepted CONCERN — `DeadDataNotice` itself has no dedicated unit test; it is proven only indirectly through its 7 consumers' tests. The plan's own "Test Infra Improvement Notes" section already names this as a backlog candidate rather than a gap this plan owns, so it is carried forward as-is, not newly discovered here |
| V3 (contract coverage) | Each of the 10 ACs maps to at least one Implementation Checklist item and one Touchpoint | PASS — AC-1→Touchpoints 2,3,6; AC-2→Touchpoints 3,4,5,6; AC-3→checklist item 9 + all 5 edited files; AC-4→Touchpoints 2,3,6 (implicit — same implicit-mapping style this task folder's own precedent uses for its AC-4 equivalent); AC-5→Touchpoints 4,5; AC-6→Touchpoint 7; AC-7→Touchpoint 8; AC-8→checklist item 11 (implicit — no explicit checklist line says "confirm these 2 files stay out of the write set," minor); AC-9→checklist item 10; AC-10→Verification Evidence table row, see the V6 CONCERN below |
| V4 (blast radius) | No Touchpoint outside `web/components/screener/`; the Blast Radius section's stated file count (1 new + 5 edited + 2 test = 8) matches the Touchpoints list exactly, with no `web/lib/` or `api/` file among them | PASS — blast radius as stated is accurate |
| V5 (reversibility) | Every change is a pure markup/import swap (an existing `<div>`/`<span>` literal replaced with an equivalent `<DeadDataNotice .../>` call rendering the same testid/text); no data write, no schema/API change, nothing destructive | PASS |
| V6 (test executability) | Can this session run the tests it specifies? | **FAIL, accepted** — no `device_bash`, no npm-registry egress from this cloud sandbox; same accepted structural gap as both prior RFC-006 slices. Commands are handed to the user in the plan's own Verification Evidence section. **Finding from this VALIDATE pass, now RESOLVED:** the "Exact commands" copy-paste block was missing the `tsc`/`pnpm build` line AC-10 needs — fixed by adding `pnpm exec tsc --noEmit` to that block (checked `web/package.json`'s own `scripts`: no dedicated `typecheck` script exists, so this is the correct real invocation, not a generic guess) |
| V7 (naming/convention compliance) | New file `DeadDataNotice.tsx` is PascalCase, matching every existing file in `web/components/screener/` (`CoinPanel.tsx`, `DrillDownView.tsx`, `NarrativeStrip.tsx`, `LegTimelineBanner.tsx`, `RelativePerformanceChart.tsx`); every `data-testid` string is preserved byte-identical per the plan's own AC-3 | PASS |

**Additional finding, now RESOLVED during this VALIDATE pass:** the new `LegTimelineBanner.test.tsx`
case (Touchpoint 7 / New Test Cases) asserts
`expect(screen.queryByTestId("leg-composite-variant")).not.toBeInTheDocument()` — a testid that was
not otherwise traced anywhere else in the plan at the time this contract was first written. Live
re-read of `LegTimelineBanner.tsx` during this VALIDATE pass confirmed it is real: a
`<div data-testid="leg-composite-variant">` at line 62, inside the success-render branch (lines
60-100), never rendered by the `if (error) {...}` branch (lines 38-44) this plan touches — so the
assertion is correct. The trace is now recorded in Touchpoint 5 alongside every other testid this
plan touches or asserts.

Test gates (carried forward from the plan's own Verification Evidence table — VALIDATE found no
incorrect strategy assignment in it):

| criterion id | behavior | strategy | proving test | gap-resolution |
|---|---|---|---|---|
| AC-1, AC-3, AC-4 | reason variant + siblings survive (CoinPanel/DrillDownView/RelativePerformanceChart paths) | Fully-Automated | `pnpm test -- ScreenerBoard.test.tsx` / `DrillDownView.test.tsx` / `RelativePerformanceChart.test.tsx` (existing cases) | A |
| AC-2, AC-3, AC-5 | message variant, NarrativeStrip error branch | Fully-Automated | `pnpm test -- NarrativeStrip.test.tsx` (existing case) | A |
| AC-2, AC-3, AC-5, AC-6 | LegTimelineBanner error-branch gap closed | Fully-Automated | `pnpm test -- LegTimelineBanner.test.tsx` (new case, Touchpoint 7) | B |
| AC-1, AC-2, AC-3, AC-4, AC-7 | RelativePerformanceChart `rp-error` gap closed | Fully-Automated | `pnpm test -- RelativePerformanceChart.test.tsx` (new case, Touchpoint 8) | B |
| AC-3, AC-8 | no unforeseen regression anywhere; only the 8 Touchpoints files written | Fully-Automated | full `pnpm test` | A |
| AC-3, AC-4 | unaffected e2e surface stays green | Hybrid | `pnpm test:e2e` | A |
| AC-9 | no tag-name/`querySelector`-by-tag assertion reintroduced | Fully-Automated | grep re-check across the blast-radius test files + `web/e2e/screener.spec.ts` | A |
| AC-10 | no new TS shape error at any of the 6 touched call sites | Hybrid | `pnpm exec tsc --noEmit` (added to the "Exact commands" block during this VALIDATE pass) | A — command now present and correct; proven when EXECUTE/EVL runs it |

gap-resolution legend: A — proven now (gate passes when run) · B — new coverage added by this plan's
own checklist · C — needs a small addition to the plan before the gate is fully executable · D —
backlog stub (not used here).

Dimension findings:
- Infra fit: PASS — no new dependency, no new runtime surface; `DeadDataNotice.tsx` is a plain
  presentational function component matching this directory's existing convention.
- Test coverage: CONCERN — every AC is covered by a concrete test; the one remaining item is (a)
  `DeadDataNotice` has no dedicated unit test of its own (pre-existing, accepted disposition per the
  plan's own Test Infra Improvement Notes). Item (b), AC-10's proving command missing from the plan's
  "Exact commands" block, was found and RESOLVED during this VALIDATE pass (see V6 above).
- Breaking changes: PASS — zero testid renames, zero placement changes, zero API/schema change; the
  `<span>`→`<div>` inner-element tag changes on `narrative-error`/`leg-timeline-error`/
  `rp-unavailable-{symbol}` were checked by the plan against every assertion in the blast radius's
  test files and confirmed attribute-selector-only (no tag-name assertion exists anywhere in scope).
- Security surface: PASS — pure frontend markup change; no new input handling, no new network call,
  no auth/data surface touched.

Open gaps:
- V6 (test executability): known-gap, accepted — same structural session limitation as both prior
  RFC-006 slices; real verification happens on the user's machine at EXECUTE/EVL, same pattern.
- ~~AC-10 exact-command omission~~ — **RESOLVED during this VALIDATE pass:** `pnpm exec tsc --noEmit`
  added to the Verification Evidence "Exact commands" block (checked `web/package.json`'s scripts;
  no dedicated `typecheck` script exists, so this is the real available invocation).
- ~~`leg-composite-variant` testid documentation gap~~ — **RESOLVED during this VALIDATE pass:**
  confirmed real via live re-read of `LegTimelineBanner.tsx` (line 62) and traced in Touchpoint 5.

What this coverage does NOT prove:
- None of the `pnpm test` / `pnpm test:e2e` / grep / `tsc` commands above have actually been run, in
  this or any prior session, against this plan's changes — they prove the change is *specified* to
  be testable, not that it currently passes. Real pass/fail status is established only when
  EXECUTE/EVL runs them on the user's machine, exactly as both prior RFC-006 slices closed theirs.
- These commands do not prove `DeadDataNotice` behaves correctly for prop combinations no current
  call site exercises (e.g., a `reason` variant with `context="window"` and `reason: null`, if no
  existing call site currently passes exactly that pairing) — only the combinations actually wired
  at one of the 7 call sites are covered by this plan's test gates.
- No command here covers visual/CSS regression (e.g., how `coin-panel__unavailable` renders on
  screen) — none of AC-1 through AC-10 claims to prove that, and this VALIDATE pass does not either.

Gate: CONDITIONAL (concerns noted above; no unresolved FAIL beyond the already-established,
previously-accepted V6 structural gap)
Accepted by: session (VALIDATE agent) — matching this task folder's own established
CONDITIONAL-accepted-with-concerns precedent (`getjson-timeout-catch_PLAN_19-09-26.md`,
`reason-value-rendering_PLAN_19-09-26.md`). Accepted concerns, by name:
1. V6 test-executability structural gap — pre-existing, not new to this plan; still open, real
   verification happens at EXECUTE/EVL on the user's machine.
2. AC-10 exact-command omission — found and RESOLVED during this VALIDATE pass (fix applied above).
3. `leg-composite-variant` testid documentation gap — found and RESOLVED during this VALIDATE pass
   (traced and confirmed above).
4. `DeadDataNotice`'s own lack of a dedicated unit test — pre-existing disposition, already accepted
   in the plan's own Test Infra Improvement Notes as a backlog candidate, not a gap this plan owns.
