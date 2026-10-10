---
name: note:screener-live-ondemand-states-contrast
description: "Backlog: contrast audit of the freshness strip's overdue and failed variants (AC-S11b-8r Known-Gap)"
date: 10-10-26
feature: general
---

# Screener freshness strip: contrast of the on-demand states (backlog note)

- **Problem:** The contrast audit (`web/e2e/contrast.spec.ts`) reads /screener in its default state only. The freshness strip's overdue marker (`.freshness-strip__overdue`, a `--sev-prov` border and bold text) and failed line (`.freshness-strip__failed`, a `--sev-bad` left rule and semibold text) appear only when the server is late or a check fails, so neither is measured.
- **Source path:** `process/general-plans/active/screener-batch4_10-10-26/screener-batch4_PLAN_10-10-26.md` (AC-S11b-8r, Open gaps), `web/components/screener/FreshnessStrip.tsx`, `web/app/globals.css`.
- **Fix option:** Drive both states in the contrast spec with routed status answers (an overdue `next_tick_at`, then an aborted status request plus a hidden/visible toggle to force a check) and run the same text-contrast measure on the strip. Text stays shell ink (`--ink-1`); only the borders carry the state colours, which are graphics (3:1).
