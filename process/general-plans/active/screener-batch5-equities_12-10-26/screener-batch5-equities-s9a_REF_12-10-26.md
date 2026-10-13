ROLE: WORKER
You are a WORKER: direct lane. Do not orchestrate or spawn sessions; load only the files below. Capped lane: at most 3 sonnet subagents, one level, listed in the report. Spend cap 15 USD; ask the planner above 7 USD.
After your report, stop; do not wait on CI or check in. needs_input means STOP: do NOT merge, do NOT open a new PR.

Task: T45 (batch 5, slice S9A) - equities API: cache-only board, chart, spaghetti, list/add/remove with the 30 cap, status, US market calendar, minimal refresh.
Acceptance: G-S9A-1..5 pass; AC-S9A-1..7. If a count differs from the plan or you hit a blocker: set needs_input, STOP, do NOT merge. Live-shape independent: no real LSE call, no key in tests.
Owned/Forbidden/Design/Tests: the plan's S9A section and gate conventions 1-11. Editable existing test: only api/tests/data/test_equities_store.py as the plan's table says. ASCII only. Never log, echo or commit LSE_API_KEY; fixtures synthetic only.
Base: main 881a2fd or later (git fetch, branch from origin/main). Baselines: pytest 1016 passed/2 skipped/5 deselected (1018 collected), vitest 400/50, e2e 79/9 (web untouched). Expected end: pytest 1080/2/5.
Branch: claude/t45-s9a-equities-api (from main)
Read: process/general-plans/active/screener-batch5-equities_12-10-26/screener-batch5-equities_PLAN_12-10-26.md lines 11, 30-66, 81-98, 242-252, 261-262, 269 (re-derive with `grep -n '^## \|^### '`). The plan is on branch claude/pensive-albattani-ou0cgv: `git fetch origin claude/pensive-albattani-ou0cgv`, then read it with `git show origin/claude/pensive-albattani-ou0cgv:<path>`; do not commit anything from that branch.
Tests: red run first; each gate once after the last edit; scan commands only after the commit.
Report: process/general-plans/active/screener-batch5-equities_12-10-26/screener-batch5-equities-s9a_REPORT_12-10-26.md, headings: Task ID, Outcome, Summary, Files, Commits, Tests run (SHA, UTC), Tests NOT run, Deviations, Blockers, Follow-up, Context cost.
Stop at review if: scope expansion, doubt, or a diff touching CLAUDE.md, AGENTS.md, README.md, .claude/, .github/, deploy/, uv.lock, api/pyproject.toml or outside Owned.
Autonomy: edit Owned, gates, push, draft PR. Never merge.
