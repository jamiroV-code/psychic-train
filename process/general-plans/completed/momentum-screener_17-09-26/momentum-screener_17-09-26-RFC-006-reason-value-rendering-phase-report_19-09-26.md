# RFC-006 Phase Report — `reason`-value Rendering (scoped slice 2/2)

**Date**: 19-09-26
**Plan**: `process/general-plans/active/momentum-screener_17-09-26/reason-value-rendering_PLAN_19-09-26.md`
**Status**: ✅ VERIFIED — user confirmed `pnpm test` full suite green (38/38) except the known,
pre-existing `e2e/screener.spec.ts` vitest-collection gap. RFC-006 is now done for both slices its
own Overview named as in-scope; one item remains separately queued (see Next).
**Phases run**: RESEARCH → INNOVATE (light — mechanical copy/shared-helper decision) → PLAN →
VALIDATE (CONDITIONAL, accepted with concerns) → EXECUTE → EVL → UPDATE PROCESS (this report)
**SPEC**: skipped — inner-loop RFC governed by `momentum-screener_SPEC_17-09-26.md` (same precedent
as RFC-005 and `getjson-timeout-catch_PLAN_19-09-26.md`)

---

## Outcome

RFC-005 added an `UnavailableReason` literal (`"insufficient-history" | "bad-symbol" |
"source-unavailable"`) to the backend's `ChartSeries` and `RelativePerformanceSeries` models
specifically so a misconfigured symbol, a dead data source, and genuinely short history would stop
collapsing into one "unavailable" signal. The frontend types were never updated to mirror the new
field, and all three render sites that show an unavailable chart (`CoinPanel.tsx`,
`DrillDownView.tsx`, `RelativePerformanceChart.tsx`) printed the same hardcoded string regardless of
cause — the exact problem RFC-005 fixed on the backend was still reproduced on screen.

Fix applied: `web/lib/types/screener.ts` now exports `UnavailableReason` and both interfaces carry
`reason: UnavailableReason | null`, matching the wire shape exactly. A new shared
`web/lib/format-unavailable-reason.ts` maps the three values (plus the `null` fallback, which
reproduces the pre-RFC-005 default copy byte-for-byte) to distinct human-facing text, used by all
three render sites so the mapping can't drift across them. Each now also carries a `data-reason`
attribute (`CoinPanel`'s `chart-unavailable`, `DrillDownView`'s `drilldown-chart-unavailable`, and a
new per-coin `data-testid="rp-unavailable-{symbol}"` inside `RelativePerformanceChart`'s existing
note) for direct assertion without string-matching rendered text.

EVL results (run by the user on their own machine, since this session again had no `device_bash` and
its own cloud sandbox again had npm-registry egress blocked):

- `pnpm test` (full suite) — **all passed**, except the known, pre-existing `e2e/screener.spec.ts`
  vitest-collection failure (same gap the prior slice found and left for the `vitest-config-e2e-
  exclude_19-09-26.md` backlog item — not a regression from this plan; nothing in this plan's
  Touchpoints includes `e2e/` or `vitest.config.ts`).

Net: all 6 Acceptance Criteria verified. The V6 gap accepted at VALIDATE (no in-session test
execution) is now closed by the user's real run, same pattern as the prior slice.

## Deviations

None. All 9 files matched the Implementation Checklist exactly — recorded in the plan's own EXECUTE
Results section, along with a live re-occurrence of the `device_commit_files`-silently-not-landing
failure mode (this time on the plan file's own EXECUTE-Results update, not a Touchpoint — caught by
the same re-stage-and-byte-diff discipline the prior slice established, resolved with `force: true`
on retry).

Nothing outside the plan's 9 Touchpoints was modified: no `api/` change (the field already existed
there), no touch to `NarrativeStrip.tsx`/`LegTimelineBanner.tsx` (their `unavailable` states are a
different, unrelated literal type), no `SignalDetailPanel.tsx` change, no `aria-live` addition, and
no unification of the three dead-data-rendering conventions (each touched component still matches
its own existing convention, same discipline as the first RFC-006 slice) — all explicitly out of
scope per the plan's own Overview.

## Context updated

- `process/context/tests/all-tests.md` — "Last updated" line moved to this cycle; the `web/` vitest
  row now reflects 38/38 (31 carried over from the prior slice + 7 new: a new
  `format-unavailable-reason.test.ts` with 4 cases, plus one new case each in `ScreenerBoard.test.tsx`,
  `RelativePerformanceChart.test.tsx` and `DrillDownView.test.tsx`); one new Debugging Quick
  Reference row added for the frontend's new reason-specific unavailable text and its `data-reason`
  attribute. No existing Standing Lesson row touched — this slice produced no new green-but-wrong
  incident.

## Backlog raised

None new. The two backlog items the prior slice raised
(`vitest-config-e2e-exclude_19-09-26.md`, `sandbox-note-reconciliation_19-09-26.md`) are unchanged
by this slice and remain open.

## Next

RFC-006 is now **done for both slices its own Overview named as in scope** — `getjson-timeout-catch`
(✅ VERIFIED, prior session) and this `reason-value-rendering` slice. One item remains, deliberately
never pulled into either slice:

- **Project-wide unification of the three dead-data-rendering conventions** (inline-alongside for
  `CoinPanel`/`DrillDownView`, whole-section-replace for `NarrativeStrip`/`LegTimelineBanner`,
  per-item list note for `RelativePerformanceChart`) — not started; both RFC-006 slices intentionally
  matched each touched component to its own existing convention instead of unifying. Still separately
  queued, not blocking anything.

Unchanged from the prior slice's own Next section, still open:

- RFC-001 stub closeout toward archival (`stub_rfc001-frontend-tests_18-09-26.md` the remaining
  item).

Per the standing precedent in this task folder, this plan
(`reason-value-rendering_PLAN_19-09-26.md`) stays in
`process/general-plans/active/momentum-screener_17-09-26/` and is **not** moved to `completed/`. The
task folder archives only when the entire `momentum-screener` program is done.
