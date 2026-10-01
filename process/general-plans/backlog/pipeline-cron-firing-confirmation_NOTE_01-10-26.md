---
name: note:pipeline-cron-firing-confirmation
description: "Backlog: after merging P1, confirm the five scheduled workflows actually fire on their cron day (AC-13/AC-6) and that the scheduler delay stays inside the 10h budget"
date: 01-10-26
feature: general
---

# Confirm real cron firing after merge (backlog note)

**TL;DR:** Nothing about the five workflows' real firing was observable offline. After `claude/p1-pipeline` (PR #11) merges to `main`, check the first 2-3 nights.

**Priority:** High (cheap, and the delay varies by hours).

**Checks (per workflow: pairs-refresh, liquidity-backfill, chain-growth, narrative, liqtide):**
- `gh run list --workflow <file> --json event,createdAt,startedAt` - started-at vs the cron time (11:17 / 11:47 / 12:17 / 12:47 / 13:17 UTC). Every no-history run must start on the cron's UTC day.
- Observed delay vs the 10h budget. It was 2h39m-5h01m on 2026-09-27/28; on 2026-09-29/30 narrative and liqtide were about 4h late (narrative 4h02m/4h01m at 22:18:55Z/22:18:40Z, liqtide 3h52m/3h52m at 22:39:27Z/22:38:43Z, against the old 18:17/18:47 crons), so it varies by hours rather than growing steadily. Watch that the variance stays inside the budget.
- The schedule-only midnight-crossing warning step fires only on `schedule` events and never on `workflow_dispatch`.
- pairs-refresh and liquidity-backfill jobs run end to end; their commit step reports "nothing new to commit" (inert by design until P2 persistent disk).

**Source:** plans AC-13 (schedules) and AC-6 / K1 (cron timing) in `process/general-plans/active/pipeline-completeness_28-09-26/`.
