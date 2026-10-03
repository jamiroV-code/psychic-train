---
name: spec:t19-archive-stale-plans
description: "Worker brief T19 (proposed, not approved): move finished plan folders from process/general-plans/active/ to completed/ with evidence per folder (docs-only RT0)"
date: 03-10-26
feature: general
---

# T19 - archive stale plans from `process/general-plans/active/` (worker brief)

**TL;DR:** Of nine folders in `active/`, one is a clear archive candidate (momentum-screener), the rest must stay for a recorded reason. Status `proposed`: no worker may start until the user approves and VALIDATE passes. Moves are reversible (`git mv`).

Registry row: T19 in `process/MASTER-PLAN.md` (planner-only file). Envelope after VALIDATE and approval (`t19-archive-stale-plans_REF_03-10-26.md`).

## Candidate review (planner, read-only, `5676ceb`, 03-10-26)

| Folder | Evidence | Verdict |
|---|---|---|
| `momentum-screener_17-09-26` | Umbrella plan: RFC-001/002/003 VERIFIED, RFC-004 DONE_WITH_CONCERNS (updated 24-09-26); sub-plans ccxt-symbol-resolution, getjson-timeout-catch, playwright-e2e, reason-value-rendering, weekly-ohlc-anchor all `VERIFIED`; screener shipped (P4 realignment builds on it). Open: `dead-data-notice-unification_PLAN_20-09-26.md` is `DRAFT` (never validated), `momentum-screener_PLAN` RFC-004 concerns, three `stub_*` files | Candidate: archive after the worker confirms each open item is either backlogged or obsolete; DRAFT plan gets a backlog NOTE rather than being lost |
| `master-planner-recovery_02-10-26` | Gates 5-6 remain; R4/R8 `review` | MUST STAY (user rule) |
| `snapshot-cron-timing_27-09-26` | `CODE DONE`, `VERIFIED pending next scheduled runs`; T27 `review`, run start times unchecked | Keep until T27 evidence exists |
| `pipeline-completeness_28-09-26` | P1 `review`; real cron firing unverified; etf_flows write non-atomic | Keep |
| `deployability_28-09-26` | P2 `review`; runtime verifiable only on the user's PC | Keep |
| `ui-shell_28-09-26` | T14 `review`, no human visual acceptance, no PLAN file | Keep |
| `liqtide-snapshot-tooling_20-09-26` | `COMPLETE_WITH_GAPS`; composite agreement unanswered (empty archive) | Keep (known gap is not an archive basis) |
| `narrative-baskets_02-10-26`, `personal-tracker-realignment_02-10-26` | SPEC only, P4/P5 `proposed` | Keep (live programs) |

Also in `active/`: `_GUIDE.md` (stays).

## Scope

1. Re-check every row of the table against the files and `git log` at start; if the evidence changed, update the verdict in the report, not silently.
2. For `momentum-screener_17-09-26`: backlog NOTE (`process/general-plans/backlog/<slug>_NOTE_<dd-mm-yy>.md`) for each open item that still matters; then `git mv process/general-plans/active/momentum-screener_17-09-26 process/general-plans/completed/momentum-screener_17-09-26` (whole folder, name unchanged).
3. Path references elsewhere (MASTER-PLAN, recovery plan, realignment SPEC, backlog notes, legacy `reports/`) are NOT edited by the worker; list them in the report for the planner.

## Acceptance

Source folder gone, destination present with identical file count (state both counts), `node .claude/skills/vc-audit-plans/scripts/validate-plan-inventory.mjs` shows 0 failures and no new warnings versus its pre-change output, `git diff --check` clean.

## Ownership

- Owned: `process/general-plans/active/momentum-screener_17-09-26/**` (move source), `process/general-plans/completed/momentum-screener_17-09-26/**` (destination), new files under `process/general-plans/backlog/` named in scope 2, this task folder.
- Forbidden: `process/MASTER-PLAN.md`, `process/archive/**`, `process/context/**`, the other `active/` folders, `CLAUDE.md`, `AGENTS.md`, `README.md`, `.claude/**`, `api/**`, `web/**`, `deploy/**`.
- Overlap: none with T18, PERF, R12.

## Tests

Tier RT0: `validate-plan-inventory.mjs`, `validate-context-discovery.mjs`, `git diff --check`. No pytest, vitest or Playwright. Full-suite budget 0.

## Stop and report at `review` if

Any listed folder's evidence contradicts the verdict, an open item is unclear (ask, do not guess), or a deletion (not a move) seems needed.
