---
name: report:narrative-baskets-trends-t149-t100b-r4
description: "T149 round 4: fixes from the third review T159 on PR #162. The store-failure line is now deterministic last (stdout), store-failed counts as a code reason, and the value guards reject >100 and bool."
date: 24-10-26
feature: narrative-baskets
metadata:
  node_type: memory
  type: report
---

# T149 round 4 (T159 review fixes on PR #162): REPORT

## 1 Task ID

T149 round 4. Fixes from review T159 (verdict MERGE AFTER SMALL FIXES; 1 Medium, 3 Lows) on PR #162, branch `claude/t149-t100b-trends-fetch`.

## 2 Outcome

done.

## 3 Summary

- **Medium, fixed. The store-failure line was printed out of order.**
  - The bug: since round 3, the final `<source>: error store-failed: Class xN` line went to stderr, while the summary line went to stdout. In CI (`2>&1 | tee`, no `PYTHONUNBUFFERED`), stdout is block-buffered, so the stderr line came out first. The verifier reads the last `<source>:` line, so a store failure read GREEN, for every source.
  - The fix: the error line now goes to stdout, after the summary, with `flush=True`, so it is always last.
  - A new subprocess test runs the real CLI path with stdout and stderr in one pipe and `PYTHONUNBUFFERED` removed from the environment. For both Wikipedia and Trends, it checks that the last `<source>:` line is the error line, that `classify` reads it as `failed`, and (for Trends) that the workflow's `verify()` reports `summary trends: failed`. Exit code 1.
  - Before the fix this test failed exactly as the reviewer described: the last line was the `1/2 ok` summary.
- **`store-failed` is now a code reason.** `attention_extra._CODE_REASON` now also matches `store-failed: Class`. A run where every store write fails is therefore red, even if the error line were missing, rather than a yellow warning. This is a one-pattern edit to `api/scripts/attention_extra.py` (not under `.github/`), with a test. It is outside the PLAN's file list, as the planner allowed.
- **Low, value guards.**
  - `store._replaceable` now rejects values above 100 and bool values. It checks the raw values before the float conversion, so `True` is no longer taken as 1.0.
  - `complete_days` rejects bool values (`bad-value`).
  - The redundant `isfinite` check is removed: NaN is caught first, and inf fails the 0..100 range.
- **Test data fix.** The M1 characterization test's synthetic re-pull used values up to 138. The new >100 guard correctly rejected it, so the test now scales by 1.25 and stays inside Google's 0..100 scale. Its assertions are unchanged.
- **Real mutation counts** (the PR body said 18): 34 distinct mutations across the four rounds, all killed in the end.

  | Round | Mutations | Notes |
  |---|---|---|
  | 1 | 8 | One survived at first; the test was strengthened, then it was killed |
  | 2 | 8 | The 8 round-1 mutations were also re-run on the new code, with stale-pyc protection |
  | qualified-term change | 2 | |
  | 3 | 10 | |
  | 4 | 6 | |

## 4 Files changed

- `api/scripts/refresh_attention.py`: error line to stdout, flushed.
- `api/scripts/attention_extra.py`: `store-failed` added to `_CODE_REASON`. Outside the PLAN's file list; the planner allowed it.
- `api/data/attention/store.py`: guard on raw values, range 0..100, no bool.
- `api/data/attention/trends.py`: bool rejected, dead check removed.
- Tests:
  - `test_refresh_attention_trends.py`: +3 (subprocess x2, reason kind).
  - `test_store.py`: +2 cases.
  - `test_trends.py`: +1.
  - `test_trends_pull.py`: test data scaled into 0..100.
- This report.
- Nothing under `.github/`.

## 5 Commits

On `claude/t149-t100b-trends-fetch`: `4b370d4` (merge of origin/main), then one fix commit plus this report (see the PR).

## 6 Tests run

All runs used `UV_FROZEN=1 PYTHONDONTWRITEBYTECODE=1`, on 24-10-26 UTC.
- Red first: 6 failed before the code (both subprocess cases, the reason-kind test, store 100.5 and True, and the bool frame).
- G1: 144 passed.
- Full API: **2021 passed, 0 failed**, 1 skipped, 5 deselected. Before this round: 2015. +6 tests.
- G7: 3x OK. `git diff --check` is clean.
- Mutations: 6, all killed (table in heading 3).

## 7 Tests NOT run

No live Google call. Web checks were not run (web untouched). The real workflow was not dispatched (T100c territory). The subprocess test reproduces its pipe and buffering.

## 8 Deviations

The `attention_extra.py` edit, as above.

## 9 Blockers

None. Owner decisions unchanged: M1 goes to T100b-PIT; M2b is NO for now.

## 10 Follow-up

T100b-PIT; T100c.

## 11 Context cost

Loaded: the T159 message, the edited code sections, `attention_extra.py` (pattern only), and the workflow step lines. About 20k tokens for this round. USD not metered; my estimate is that all rounds together are under the 10 USD ask level.
