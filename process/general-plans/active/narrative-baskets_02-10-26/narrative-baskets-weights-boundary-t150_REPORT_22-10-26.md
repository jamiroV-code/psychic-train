---
name: report:narrative-baskets-weights-boundary-t150
description: "T150 worker report: the red frozen-snapshot guard after T130 was a test bug, not a scoring bug. Evidence per frozen day, test fix, new explicit `weights` field in snapshot records, and the A/B decision for 21 Oct (recommendation: neither)."
date: 22-10-26
feature: narrative-baskets
metadata:
  node_type: memory
  type: report
---

# T150 weights boundary: REPORT

## 1 Task ID

T150 (follow-up to T130, PR #156). Branch `claude/t150-weights-boundary-fix` from origin/main 9d38000.

## 2 Outcome

done. Status for the owner is a decision request (heading 9), not a blocker: the code needs no decision, because the recommended answer is "change nothing" in frozen data.

## 3 Summary

- **No scoring bug.** Every frozen day was scored with the weights its label says. Day 2026-10-21 (written by T130 code, run 034c93c) is labelled v1 and its rows fit ONLY v1 (table below).
- **Where the "v2 values" came from.** Since T130 a record stores the WHOLE run config. Its top-level `source_weights` is the current version (v2), with v1 sitting in `config.weights_history`. T134, and my own T130 guard test, read that top-level field as "the weights used". The guard test was wrong; the boundary `until: 2026-10-21` is right.
- **Code path, proven.** The refresh run on D calls `take_snapshot(D)`, then `build_discovery(window, today=D)`; that sets end = D-1, and `_coin` calls `weights_for_day(cfg, end)` (`discovery.py`). The label comes from the same `weights_for_day(cfg, day)` in `_record`. Same function, same day, so the label and the values cannot diverge. The new boundary tests (day before, boundary, day after) check this end to end, rows included.
- **Fix 1 (tests).** `frozen_mismatches` reads the weights a record was scored with: its `weights` field, else its own config's version for its day. It also checks every row's covered weight equals the sum of those weights over the row's sources. Six synthetic cases cover the merge-before-refresh race in general: old code freezing a day after `until` is caught, and a T130 record for a v1 day is not falsely flagged.
- **Fix 2 (code, additive).** New records also store `weights`, the version actually used, so nobody has to derive it from `config` again. Frozen files are untouched.

| Frozen day | label (`weights_version`) | stored `config.source_weights` | rows fit v1 | rows fit v2 | `weights_for_day(day)` |
|---|---|---|---|---|---|
| 2026-10-17..20 (12 files) | absent, so 1 | v1 | yes | no | v1 |
| 2026-10-21 (w7, w30, w90) | 1 | v2 (full config; v1 in its history) | yes | no | v1 |
| 2026-10-22 | not frozen yet (the 2026-10-23 refresh freezes it, with v2) | | | | v2 |

Examples from 2026-10-21_w30: covered weights are 35 (wikipedia 25 + exchange slot 10) and 10 (exchange slot only), which are v1 sums. Under v2 these would be 25 and 15.

## 4 Files changed

- `api/analytics/attention/signal_snapshots.py`: `weights` field in new records, docstring.
- `api/tests/analytics/attention/test_weights_v2.py`: `frozen_mismatches` helper, 6 race cases, 3 boundary snapshot tests, guard rewritten; ruff import-order fix (pre-existing I001 from T130).
- `process/.../narrative-baskets-weights-v2-t130_PLAN_21-10-26.md`: D10 corrected (how the guard reads weights). The v1-through-10-21 / v2-from-10-22 lines are correct and unchanged.
- This report.

## 5 Commits

See the PR on `claude/t150-weights-boundary-fix` (one code commit plus this report).

## 6 Tests run

- **Before**, origin/main 9d38000: `UV_FROZEN=1 uv run --project api pytest api -q` gave 1 failed (`test_committed_frozen_snapshots_match_their_days_weights`), 1861 passed, 1 skipped, 5 deselected.
- **Red first:** with the old check logic, the new case "T130 record for a v1 day" failed (false flag). The 3 boundary tests failed with `KeyError: 'weights'` before the code change.
- **After:** same command gave 1871 passed, 1 skipped, 5 deselected, 0 failed (2026-10-22 ~18:20 UTC). +9 tests.
- **Lint:** `uv run ruff check` on both touched .py files: all checks passed.
- **Pins:** `sha256sum -c` over all 15 frozen files, before and after: 15 OK. The 21 Oct hashes: `683c90e6c72f20aca1acf495548b2037634c98946600ff08d05667244325cf19` (w30), `c36d34389045f68dccadc2146c56048a487eb4e1597ce8260bacefb33d64383d` (w7), `8d84bcedc77f28398dc81e06522f26e2742bee4b4cc7d130fb845505705a2928` (w90). No test or plan pins them yet. The G7 pins of the 17 Oct files are unchanged.
- **Hygiene:** `git diff --check` clean; nothing under `.github/` or `web/`.

## 7 Tests NOT run

Web checks were not run (web untouched).

## 8 Deviations

- **First message:** it asked to fix "ONLY the config/boundary". Moving `until` would have been wrong: day 2026-10-21 really is v1, so `until: 2026-10-20` would make the chart rescore that day with v2 and disagree with its frozen record. The fix is in the test, plus an additive record field.
- **Second message (correction):** its premise, "label 1 but v2 values", is disproven by the rows (table in heading 3). I shipped the code hardening it asked for, but no change to how a day is scored was needed.

## 9 Blockers

**Owner decision on the 21 Oct file (A/B). Recommendation: neither.**

- **A)** Relabel 2026-10-21_w{7,30,90} to `weights_version` 2 and set v1 `until` to 2026-10-20. This rewrites three frozen files (their sha256 change; the D10 guard would then FAIL on them, because their rows fit v1 only). Worse, it marks a day scored with v1 as v2: a false point in the backtest chart. Reject.
- **B)** Keep the file and add a documented exception ("21 Oct frozen with v2 values under label 1"). The exception would record something that did not happen. Not needed.
- **Recommended (neither A nor B):** keep all frozen files and the config as they are. Point-in-time stays honest: the chart scores 21 Oct with v1, and the frozen record is v1. This PR only fixes the guard and adds the explicit `weights` field.

**The real rule for merging a weights change** (and why "merge before 12:00 UTC 23 Oct" was the wrong framing):

- The refresh on day D freezes day D-1, using whatever config is on main when the run checks out. It is scheduled at 07:23 UTC; the commit lands later (around 13:30 in recent runs), so the commit time is not the deadline.
- Code with the history table scores every day by `weights_for_day`, so after the merge any day is correct whenever it is frozen.
- The only risk is OLD code (no history table) freezing a day AFTER the new `until`. That record would hold old weights for a day the table gives to the new version.
- Rule: set `until` to at least the newest day frozen on main when you merge, and merge before the refresh run that would freeze `until + 1` STARTS (07:23 UTC on `until + 2`). If that is missed, set `until` to the newest day the old code froze.
- The guard test enforces this on every PR that merges main, and now reads the right field.
- For T130: merged 21 Oct ~22:00 UTC, before the run that froze 21 Oct; `until` = 21 Oct. Both conditions held. The red CI came only from the guard's bug.

**Registry update request:** T150 in review (draft PR).

## 10 Follow-up

- Optional: pin the three 21 Oct hashes in the next plan's G7 block.
- Unchanged from T130: web marks for v1/v2 points, and the "of 100 weight" text.

## 11 Context cost

Loaded: the planner messages, `signal_snapshots.py` (edited parts), `test_weights_v2.py`, the frozen files (computed checks only), the workflow cron line. About 25k tokens this task. Spend is under the 10 USD ask point (not measured exactly). Tools: Bash, file tools, GitHub MCP, remote send_message.
