ROLE: WORKER
You are a WORKER: direct lane. Do not orchestrate or spawn sessions; load only the files below. Capped lane: at most 3 sonnet subagents, one level, listed in the report. Spend cap 15 USD; ask the planner above 5 USD.
After your report, stop; do not wait on CI or check in. needs_input means STOP: do NOT merge, do NOT open a new PR.

Task: T46 (batch 5, slice S9B) - layout section "equities" via a section registry in api/data/layout.py; crypto behaviour unchanged.
Acceptance: G-S9B-1..4 pass; AC-S9B-1..3. If a count differs from the plan or you hit a blocker: set needs_input, STOP, do NOT merge. Live-shape independent: no real LSE call, no key in tests.
Owned/Forbidden/Design/Tests: the plan's S9B section and gate conventions 1-11. Editable existing test: only api/tests/routers/test_layout.py (line 177 SECTIONS == ("crypto", "equities")) as the plan's table says. ASCII only. Fixtures synthetic only.
Base: main 6aee5e2 or later (S9A merged; git fetch, branch from origin/main). Baselines: pytest 1080 passed/2 skipped/5 deselected; web untouched. Expected end: pytest 1100/2/5.
Branch: claude/t46-s9b-equities-layout (from main)
Read: process/general-plans/active/screener-batch5-equities_12-10-26/screener-batch5-equities_PLAN_12-10-26.md lines 11, 30-66, 99-107, 242-250, 253-254, 261-262, 269 (re-derive with `grep -n '^## \|^### '`). The plan is on branch claude/pensive-albattani-ou0cgv: `git fetch origin claude/pensive-albattani-ou0cgv`, then read it with `git show origin/claude/pensive-albattani-ou0cgv:<path>`; do not commit anything from that branch.
Tests: red run first; each gate once after the last edit; scan commands only after the commit.
Report: process/general-plans/active/screener-batch5-equities_12-10-26/screener-batch5-equities-s9b_REPORT_12-10-26.md, headings: Task ID, Outcome, Summary, Files, Commits, Tests run (SHA, UTC), Tests NOT run, Deviations, Blockers, Follow-up, Context cost.
Stop at review if: scope expansion, doubt, or a diff touching CLAUDE.md, AGENTS.md, README.md, .claude/, .github/, deploy/, uv.lock, api/pyproject.toml, api/routers/, api/models/ or outside Owned.
Autonomy: edit Owned, gates, push, draft PR. Never merge.
