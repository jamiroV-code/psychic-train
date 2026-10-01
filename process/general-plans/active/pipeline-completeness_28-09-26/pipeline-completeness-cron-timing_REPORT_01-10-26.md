---
phase: pipeline-completeness-cron-timing-execute
date: 2026-10-01
status: COMPLETE_WITH_GAPS
feature: pipeline-completeness
plan: process/general-plans/active/pipeline-completeness_28-09-26/pipeline-completeness-cron-timing_PLAN_29-09-26.md
---

# Cron Timing (T27) — EXECUTE Report

TL;DR: All five crons moved to 11:17–13:17 UTC, false delay comments rewritten, the schedule-only midnight-crossing warning is `steps[0]` of the three no-history workflows, and the guard test has a 600-min budget plus a new parametrized test. All offline gates G1–G6 green; 817 → 820. Status is CODE DONE, not VERIFIED (AC-6 needs post-merge `gh run list`).

## What Was Done
- Crons: pairs `17 11`, liquidity `47 11`, chain-growth `17 12`, narrative `47 12`, liqtide `17 13` (all `* * *`).
- Header comments in all five workflows: measured 2h39m–5h01m delay (2026-09-27/28, recorded 2026-09-29, growing ~+2h/day), 10h budget; catch-up workflows explain why late or wrong-day runs are harmless (idempotent re-fetch, partial tail bar); pairs/liquidity stagger sentences rewritten for the new order (E4); old clock times removed.
- D5 guard step added as `steps[0]` (before checkout) to chain-growth (12), narrative (12), liqtide (13): `if: github.event_name == 'schedule'`, `10#` parsing, `::warning::` only, no `exit 1`.
- Guard test: `SCHEDULER_DELAY_BUFFER_MIN = 600`, docstring rewritten, test renamed to `test_cron_leaves_scheduler_delay_budget_before_utc_midnight`, `NO_HISTORY` set + `test_no_history_workflows_warn_on_midnight_crossing[x3]`. No existing assertion edited.
- BOOTSTRAP.md §8: 19:17→11:17, 19:47→11:47 only.

## What Was Skipped or Deferred
- `process/context/**` stale times (all-context.md, all-data-sources.md:139) — UPDATE PROCESS work, forbidden here.
- No git add/commit (per instructions).

## Test Gate Outcomes
| Gate | Result |
|---|---|
| Baseline (before edits) | guard file 38 passed; full suite 817 passed / 5 deselected |
| G1 | 41 passed, 0 skipped |
| G2 | 820 passed / 5 deselected (baseline + 3) |
| G3 | `ok` |
| G4a | no output (rc 1); on scratch copy of OLD text: matches in all 5 workflows + test (10 lines) |
| G4b | no output (rc 1) + `after liqtide-snapshot` rc 1; OLD text: 16 lines + pairs:23 |
| G5 | only the 5 workflows, guard test, BOOTSTRAP.md (+ this report); BOOTSTRAP numstat `2 2` |
| G6 | `G6 ok` (72 cases), rc 0 — script extracted verbatim from the plan, run from scratch dir |
| Safety shape | `git diff` shows no change to any `git add`, permissions, concurrency or retry-push line |

## Plan Deviations
None.

## Test Infra Gaps Found
- K1 real scheduler delay/cron firing unobservable offline; K3 guard only detects post-midnight starts; K2 merge-day action for the user; K4 pytrends sampling-hour shift. All per plan.

## Closeout Packet
- Plan: path above. Finished: checklist 1–5. Verified: G1–G6 offline. Unverified: AC-6 (real runs land on cron day), Actions' evaluation of the `if:`.
- Remaining: spawned vc-tester EVL; UPDATE PROCESS fixes context docs; user K2 action at merge (dispatch any workflow merged after its new cron time, same UTC day; liqtide before ~00:25 UTC).
- Classification: Keep in active/testing (CODE DONE until post-merge AC-6).

## Forward Preview
### Test Infra Found
G6 script lives in the plan's Validate Contract; extract the ```python block and run from repo root.
### Blast Radius Changes
None beyond plan touchpoints.
### Commands to Stay Green
`uv run --project api pytest api/tests/scripts/test_snapshot_workflow_schedules.py -q -rs` (41); `uv run --project api pytest api/ -q` (820/5).
### Dependency Changes
None.
