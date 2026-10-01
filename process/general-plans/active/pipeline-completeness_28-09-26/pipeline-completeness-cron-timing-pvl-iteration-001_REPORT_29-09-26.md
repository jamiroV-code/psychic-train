---
name: pipeline-completeness-cron-timing-pvl-iteration-001
description: "PVL supplement cycle 1 for the cron-timing plan (MASTER-PLAN T27): eight concerns found by an independent validate pass that overturned the plan author's inline PASS."
date: 29-09-26
metadata:
  node_type: report
  type: pvl-iteration
  domain: plan
  iteration: 1
  read_when: "auditing the PVL loop for the cron-timing plan"
---

# PVL Iteration 001 — cron-timing plan

**Plan:** `pipeline-completeness-cron-timing_PLAN_29-09-26.md`. Rows in the shared `results.tsv` are labelled `[cron-timing]`.

## Entry state
Inline fast-mode validate said `Gate: PASS`, 0 concerns. An independent `vc-validate-agent` then found **0 FAIL / 8 CONCERN** (first-pass CONDITIONAL, not terminal). This is the third plan in this task folder where the author's inline PASS did not survive an independent pass.

## Findings
| # | Finding | Evidence |
|---|---|---|
| 1 | The runtime guard step has no `if:`, so a manual `workflow_dispatch` run at 09:00 UTC emits a false "crossed midnight" warning — including the manual runs the plan's own merge advice tells the user to trigger | reproduced with a stubbed clock; fix `if: github.event_name == 'schedule'` + assertion change, 41 passed with it, fails without |
| 2 | Gate G4 (stale-phrase grep) is partly dead: `well before UTC midnight` matches 0 times because the phrase wraps across two comment lines; it also misses `3h before` and old clock times | replaced by G4a/G4b, proven on a scratch end state |
| 3 | Header sentences become false after the reorder ("30 minutes after liqtide (18:47)" in pairs, "after pairs (19:17)" in liquidity) | new sentences specified |
| 4 | Data-semantics prose wrong or incomplete: K2 must be per-workflow (LiqTide's day is permanently lost if the workflow is merged after 13:17 with no manual run before ~00:25 UTC; narrative loses the day's point; chain-growth harmless); pytrends' hourly last-point sampling hour shifts (new K4); "liqtide has ~11h55m more tolerance" is wrong (narrative 11h13m, liqtide ~11h08m); "growing ~1h/day" understated (last day ≈ +2h, so a 10h budget could be consumed in days) | measured |
| 5 | G5 `git diff --name-only HEAD` cannot see untracked files | use `git status --porcelain` + BOOTSTRAP numstat |
| 6 | G1 would not notice skipped tests (missing PyYAML skips the structural tests silently); G6 had no exact procedure | assert 0 skipped; 72-case script embedded |
| 7 | `process/context/all-context.md` and `data-sources/all-data-sources.md:139` state the old times and the "~2h" delay | recorded for UPDATE PROCESS, not edited here |
| 8 | Plan Resume line still literally reads "Gate: PASS", which falsely satisfies the mechanical PASS-grep that gates EXECUTE | fix |

## Verified by the validator (not assumptions)
38 existing tests pass unchanged; end state is 41 passed (38 + 3). Cron arithmetic holds (13:17 → 797 + 600 = 1397 < 1440; 13:59 passes, 14:00 fails; minimum stagger 30 min). Four mutations (guard removed, wrong cron_hour, a 14:17 cron, a 10-minute stagger) are each caught by the intended test only. `10#` handles hours 08/09 (a bare `$((08))` errors). Empty or failing `date` output cannot fail the job.

## Exit state
Supplement requested; EXECUTE is not legal until a re-validation from V1 clears the gate.
