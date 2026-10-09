ROLE: WORKER
You are a WORKER: direct lane. Do not orchestrate, do not spawn sessions, load only the files listed below; this overrides any orchestrator wording in CLAUDE.md. Capped lane (plan S4 "Lane"): at most 3 sonnet subagents, 15 USD, one level, listed in report heading 11.

Task: T36 (batch 2, slice S4) - staged verdict removal: commit A, then commit B.
Acceptance: A's gates pass after A; all G-S4-* pass after B; P-S4-1 stays a user-PC probe (review).
Owned / Forbidden / Design / Tests: exactly as in the plan's S4 section. Any other test that breaks: stop at needs_input.
Base: main 766e6a3 (source = 605424d). Baselines pytest 963/2/5/0, vitest 245/33 files; expected A 964 + 226/30, B 929. A differing count: stop at needs_input.
Branch: claude/t36-s4-verdict-removal (from main)
Read (plan, re-derive with `grep -n '^## \|^### '`): process/general-plans/active/screener-batch2_04-10-26/screener-batch2_PLAN_04-10-26.md lines 39, 41-44, 52, 54-61, 93-136, 280-289, 305, 307-318, 355-357, 359-360, 362-363, 365-366, 368-369, 371-372, 385, 387, 389. Nothing else.
Tests: RT3; G-S4-1 red run first on the untouched base (UV_FROZEN=1 on every pytest), record it; each gate once after the last edit of its commit.
Budget: 150 tool calls, 100 min, 4 CI polls, 4-9 USD. Retry: 2 fix cycles; same failure twice stops.
Report: process/general-plans/active/screener-batch2_04-10-26/screener-batch2-s4_REPORT_08-10-26.md (11 headings; 6 = gates with SHA and UTC).
Stop at review if: irreversible or outward action, scope expansion, doubt, a diff touching CLAUDE.md, AGENTS.md, README.md, .claude/, .github/, deploy/, or a file outside Owned.
Autonomy: edit Owned, run gates, push, open PR, wait for CI. Never deploy; no secrets.
