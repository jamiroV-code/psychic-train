# T29 report

## 1 Task ID
T29 - backtest script report dir `active` -> `completed`

## 2 Outcome
done (CI gate 8 and merge are recorded in the final reply, since CI runs after this file is committed)

## 3 Summary
- Changed one path segment on line 68 of `api/scripts/backtest_leg_boundaries.py` (`"active"` -> `"completed"`).
- Pre-edit grep found exactly one other hit, the comment at `api/scripts/compare_composite_variants.py:156`; no import, call, test or workflow references.
- Full api pytest: 870 passed, 1 skipped, 5 deselected, 1 xfailed. The script is not imported by tests, so the count is unaffected.

## 4 Files changed
- `api/scripts/backtest_leg_boundaries.py` (line 68, 1 insertion, 1 deletion)
- `process/general-plans/active/t29-backtest-report-dir_03-10-26/t29-backtest-report-dir_REPORT_03-10-26.md` (this report)

## 5 Commits
Branch `claude/t29-backtest-report-dir` (from main `1c6353f`):
- 834cf3d fix(api): point backtest_leg_boundaries REPORT_DIR at completed/
- report commit (SHA in final reply; the Master Planner records the merge SHA)

## 6 Tests run
- 2026-10-03T18:38:51Z @1c6353f: preflight file tests: all 4 files present
- 2026-10-03T18:38:51Z @1c6353f: `sed -n 68p api/scripts/backtest_leg_boundaries.py`: old line with `"active"`
- 2026-10-03T18:38:51Z @1c6353f: `git grep -n 'backtest_leg_boundaries' -- api web deploy .github ':!api/scripts/backtest_leg_boundaries.py'`: one hit, `api/scripts/compare_composite_variants.py:156` (comment)
- 2026-10-03T18:38:57Z @1c6353f+edit: `uv run --project api python -c "import ast; ast.parse(open('api/scripts/backtest_leg_boundaries.py').read())"`: exit 0
- 2026-10-03T18:38:57Z @1c6353f+edit: `git grep -n 'momentum-screener_17-09-26' -- api`: only `api/scripts/backtest_leg_boundaries.py:68:REPORT_DIR = Path(__file__).resolve().parents[2] / "process" / "general-plans" / "completed" / "momentum-screener_17-09-26"`
- 2026-10-03T18:38:57Z @1c6353f+edit: `git diff -U0`: one `-` line, one `+` line (line 68)
- 2026-10-03T18:43:11Z @834cf3d: `uv run --project api pytest api/ -q`: 870 passed, 1 skipped, 5 deselected, 1 xfailed, 2 warnings in 240.72s
- @834cf3d: `git status --porcelain`: empty; `git diff --name-only origin/main..HEAD`: `api/scripts/backtest_leg_boundaries.py` only
- @834cf3d: `git diff --check origin/main..HEAD`: no output

## 7 Tests NOT run
Web gates (vitest, tsc, island build): not required at RT2; CI runs them. No baseline pytest run on main: the script is not imported by tests, so the count is unchanged by construction.

## 8 Deviations
None. The pre-edit gate was run after checking out the branch from origin/main (the session started on a detached HEAD at the same commit, 1c6353f).

## 9 Blockers
No blockers; 0 fix cycles used. Registry-update request: mark T29 accepted, then archived with the merge SHA.

## 10 Follow-up
None. `compare_composite_variants.py` and the 18 history files naming the old path are out of scope by decision.

## 11 Context cost
Files loaded: CLAUDE.md, the T29 SPEC, the RT2 and retry rows of operating-instructions.md; about 15k tokens. Role: the first line of the envelope, `ROLE: WORKER`.
Merge tool: mcp__github__merge_pull_request. PR-create tool: mcp__github__create_pull_request.
Session tools: mcp__claude-code-remote__create_session: present (not called); mcp__claude-code-remote__archive_session: present (not called); mcp__claude-code-remote__send_message: present (not called); mcp__claude-code-remote__unarchive_session: present (not called); mcp__claude-code-remote__interrupt_session: present (not called); mcp__claude-code-remote__set_session_title: present (not called); mcp__claude-code-remote__set_session_tags: present (not called); mcp__claude-code-remote__list_sessions, get_session, list_events, get_event: present (not called, each under the mcp__claude-code-remote__ prefix); mcp__ccd_session__spawn_task: present (not called); mcp__ccd_session__dismiss_task: present (not called).
