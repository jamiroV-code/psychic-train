---
name: note:screener-ondemand-states-contrast
description: "Backlog: contrast audit of the layout UI's on-demand states (rename input, remove confirm, open drill-down), AC-S5b-8r Known-Gap"
date: 10-10-26
feature: general
---

# Screener layout UI: contrast of the on-demand states (backlog note)

- **Problem:** The contrast audit (`web/e2e/contrast.spec.ts`) reads /screener in its default state only. The group rename input, the coin Remove confirm step (Confirm/Cancel) and the open drill-down appear only after a click, so none is measured. S5b (T41) did not write this note or the audit; this note closes that gap in the record (AC-S5b-8r, a named residual of screener batch 3, gate CONDITIONAL on it).
- **Source path:** `process/general-plans/active/screener-batch3_09-10-26/screener-batch3_PLAN_09-10-26.md` (AC-S5b-8r row), `web/components/screener/{CoinGroup,CoinActions,DrillDownView}.tsx`, `web/app/globals.css`, `web/e2e/contrast.spec.ts`.
- **Fix option:** Drive each state in the contrast spec (click Rename on a group, click Remove on a coin, open a drill-down) and run the same text-contrast measure; aria-disabled controls keep their text colour with a dashed border (S5b report heading 3), so also measure one aria-disabled edge control.
- **Related:** the earlier twin note `screener-live-ondemand-states-contrast_NOTE_10-10-26.md` (freshness strip overdue and failed states); one slice can cover both.
- **Next small slice:** AC-8 group sort, `screener-group-sort_NOTE_09-10-26.md`. S5b advisories still worth carrying into it or the audit slice (PVL report `screener-batch3-s5b-pvl-iteration-006_REPORT_10-10-26.md`, plan "Validation record (PVL cycle 4, S5b)"): (a) group buttons (Rename, Move group, Delete group) have no accessible-name test; (d) the `S5b-words` scan hazard is `Date.UTC(` matching `UTC` as a word (not `AbortSignal`).
- **Estimate:** about 1 web e2e spec edit, about 0.5 USD [estimate]; re-check spend before spawning.
