# S-T8 cloud-run support - worker report

## 1 Task ID
T64 (S-T8), Amendment A2 (AC-24..AC-27). Branch claude/t64-dit-s-t8-cloud-run, base origin/main d8e4641.

## 2 Outcome
Done. All gates green. (First dispatch stopped at needs_input because A2 was not yet on main; resumed after PR #82 merged.)

## 3 Summary
- `approvals add --owner-statement TEXT`: TTY matrix per A2; statement path never calls input_fn; refused (exit 2, no file) unless 20-500 printable ASCII chars naming the source and every host, no TTY, and DIT_APPROVALS_DIR set. Stored verbatim in new optional `owner_statement` (default empty; old records load; non-string is StoreCorrupt).
- `approvals_dir()` and `scrape_dir()` raise `PathInRepo` (symlinks resolved, side-effect-free checkout root, fixed message); `evidence_dir` unchanged. `approval_cli` add and status exit 2 on it.
- Docs lines 415, 420, 427, 439 rewritten; block is 2,950 B.
- Known limits: a statement cannot prove a human wrote it; the owner's chat message quoted in the envelope is the only control; no real record or scrape was made; the CLI-quoting of the owner message and time is the planner's job.

## 4 Files changed
approval_cli.py, approvals.py, paths.py; tests test_approval_cli_cloud.py (14), test_paths_private.py (5), api/tests/tooling_guards/test_cloud_guard.py (4); all-data-sources.md lines 415, 420, 427, 439.

## 5 Commits
One commit on the task branch (see PR).

## 6 Tests run
Red-first on base code with new tests: tooling 18 failed / 3 passed of 21 new; guards 1 failed / 3 passed of 4 new.
Baselines on untouched origin/main d8e4641 (worktree): tooling 523 passed/1 deselected; guards 49; API 1192 passed/1 skipped/5 deselected.
After (UTC 2026-10-15, on branch head):
- tooling pytest tools/data-integration/tests: 544 passed, 1 deselected (baseline 523 + 21 new)
- guards pytest api/tests/tooling_guards: 53 passed (49 + 4 new)
- API pytest api/: 1196 passed, 1 skipped, 5 deselected (1192 + 4 new guards)
- git diff --exit-code api/uv.lock api/pyproject.toml: clean

## 7 Tests NOT run
Real scrape, network, npx/REA, scrapling install, playwright install (forbidden).

## 8 Deviations
None. Guard test uses git ls-files and git check-ignore via subprocess (test-only).

## 9 Blockers
None.

## 10 Follow-up
Planner-side doc edits (decisions.md, plan Safety rules, S-T6 step 4, SPEC L5) are not done by this worker.

## 11 Context cost
Extra docs opened: none beyond the envelope set (plus test_cli_guard, _common, _helpers, conftest, test_approval_cli heads for style).
