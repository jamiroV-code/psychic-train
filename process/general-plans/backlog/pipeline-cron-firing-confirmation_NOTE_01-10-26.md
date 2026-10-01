---
name: note:pipeline-cron-firing-confirmation
description: "Backlog: after merging P1, confirm the five scheduled workflows actually fire on their cron day (AC-13/AC-6) and that the scheduler delay stays inside the 10h budget"
date: 01-10-26
feature: general
---

# Confirm real cron firing after merge (backlog note)

**TL;DR:** Nothing about the five workflows' real firing was observable offline. After `claude/p1-pipeline` (PR #11) merges to `main`, check the first 2-3 nights.

**Priority:** High (cheap, and the delay was growing).

**Checks (per workflow: pairs-refresh, liquidity-backfill, chain-growth, narrative, liqtide):**
- `gh run list --workflow <file> --json event,createdAt,startedAt` - started-at vs the cron time (11:17 / 11:47 / 12:17 / 12:47 / 13:17 UTC). Every no-history run must start on the cron's UTC day.
- Observed delay vs the 10h budget. It was 2h39m-5h01m on 2026-09-27/28 and growing about +2h/day, so the budget could be consumed within days.
- The schedule-only midnight-crossing warning step fires only on `schedule` events and never on `workflow_dispatch`.
- pairs-refresh and liquidity-backfill jobs run end to end; their commit step reports "nothing new to commit" (inert by design until P2 persistent disk).

**Source:** plans AC-13 (schedules) and AC-6 / K1 (cron timing) in `process/general-plans/active/pipeline-completeness_28-09-26/`.
