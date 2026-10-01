---
name: pipeline-completeness-pvl-iteration-001
description: "PVL supplement cycle 1 for the P1 pipeline-completeness plan: seven CONCERNs from the first-pass outer-pvl validate-contract folded into the plan."
date: 29-09-26
metadata:
  node_type: report
  type: pvl-iteration
  domain: plan
  iteration: 1
  read_when: "auditing the PVL loop for pipeline-completeness_28-09-26"
---

# PVL Iteration 001 — pipeline-completeness

**Plan:** `pipeline-completeness_PLAN_28-09-26.md`
**Cycle:** 1 of a 10-cycle cap · **Driver:** orchestrator · **Domain:** `plan`

## Entry state

First-pass outer-pvl verdict: **`Gate: CONDITIONAL`**, **0 FAIL**, **7 CONCERN**.
A first-pass CONDITIONAL is not terminal, and no human is present in this session to
accept the gaps, so EXECUTE was not legal. This cycle exists to satisfy the
`results.tsv` ≥1-fix-cycle route to EXECUTE rather than to bypass the gate.

## Gaps addressed (7 of 7)

| ID | Concern | Severity | Resolution folded into the plan |
|---|---|---|---|
| C1 | Crash detection matched only exit `1`, so `137` (OOM/timeout kill) left the job green **and still committed** | CONCERN (med) | Any code not in {0, 2} is a crash. Commit step requires both recorded codes in {0, 2}; final step fails on anything else. Residual (`uv run` itself exiting 2) recorded as Known-Gap. |
| C2 | `compute_pairs` returned 0 when every pair was `insufficient_overlap` | CONCERN (low-med) | Exit 2 iff `status_counts["ok"] == 0`; `insufficient_overlap`-only test case added. |
| C3 | Per-item exceptions collapsed to warn-only exit 2, overstating the "fails loudly" canary claim | CONCERN (med) | Per-item `status="error"`; exit 1 iff every item errored. Honesty item 2(a) reworded to match what the code does. |
| C4 | T22 isolation guard too weak — `grep -L` is file-level and blind to transitively-acquired fixtures; `watchlist.json` uncovered | CONCERN (med, **safety**) | Module-level autouse fixture in each of the 4 script test files, depending on `isolated_cache` and redirecting `DEFAULT_WATCHLIST_PATH`; `--setup-show` count must equal collected-test count; before/after snapshot covers `watchlist.json`. `conftest.py` untouched. |
| C5 | `parse_args(argv=None)` consumes pytest's own `sys.argv` → `SystemExit(2)`, breaking an existing untouched test | CONCERN (med) | `parse_args([] if argv is None else argv)`; `__main__` wrappers pass `sys.argv[1:]`. |
| C6 | No test asserted `workflow_dispatch` despite AC-1 requiring it | CONCERN (low) | Asserted in `test_triggers_permissions_and_concurrency` (binds all five workflows); tolerant-add test uses a minimal ignore rule under `bash -e`; guard docstring corrected to five workflows. |
| C7 | AC-12 mislabelled Fully-Automated but needs push access + authenticated `gh` | CONCERN (low) | Relabelled Hybrid; runbook gains the `/pairs` reads `stale` until `compute_pairs` note. |

## Measured evidence carried in from V2 (not assumptions)

- `git add <dir>` exits **128** when the path is absent and **1** when the path exists but is
  gitignored; `-A --` changes neither. `git add -A -- <dir> 2>/dev/null || true` exits 0 and
  stages nothing in both cases, including under `bash -e`. A `-f` control run stages the ignored
  file, so `-f` would defeat D1 and is banned.
- `test_compute_pairs.py` mentions `isolated_cache` twice, yet **8 of its 9 tests** receive it
  through `seeded` — the direct evidence that the original grep-based T22 check was insufficient.
- D7 confirmed safe for `/screener`: `screener_board.py:176`/`:224` iterate the watchlist;
  `leg_boundary.py:164` reads only BTC `1d`; the sole OHLCV-dir listing is the manual diagnostic
  `check_weekly_anchor.py:51`, not a served path.

## Exit state

`SUPPLEMENT_APPLIED` — 7 of 7 gaps addressed, scope unwidened, `validate-plan-artifact.mjs`
clean (0 failures / 0 warnings). `## Validate Contract` left intact for the V1 re-run.
AC-13 (cron actually fires) and AC-14 (live ccxt/FRED fetch) remain Known-Gap and are
expected to hold the re-run at CONDITIONAL — they are blocked by this container's egress
proxy, not by anything a further planning cycle can fix.

**Next:** re-spawn `vc-validate-agent` from V1 against the supplemented plan.
