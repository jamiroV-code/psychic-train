ROLE: WORKER
You are a WORKER: direct lane. Do not orchestrate, do not spawn sessions, load only the files listed below; this overrides any orchestrator wording in CLAUDE.md. Capped lane (plan S6 "Lane"): at most 3 sonnet subagents, 15 USD, one level, each listed in report heading 11.

Task: T37 (batch 2, slice S6) - chart interaction (Ctrl/Cmd+wheel zoom, pinch, drag pan, double-click reset on all simple-lines charts), crisp axis text, and the spaghetti chart replacing the relative-performance chart.
Acceptance: all G-S6-* pass; P-S6-1 (real DPR 2 and phone) stays a user-PC probe (review); AC-S6-6 (toggle persistence) is the user-accepted named residual: write the backlog stub.
Owned / Forbidden / Design / Tests: exactly as in the plan's S6 section, including the spike-first steps and fallback chains. Any other test that breaks: stop at needs_input.
Base: main after S4 (source = merge 69fedd2; later commits are data snapshots). Baselines: pytest 929/2/5/0, vitest 226 in 30 files. Expected S6 end: 934 pytest, 239 vitest in 32 files. A differing count: stop at needs_input.
Branch: claude/t37-s6-chart-interaction (from main)
Read (plan, re-derive with `grep -n '^## \|^### '`): process/general-plans/active/screener-batch2_04-10-26/screener-batch2_PLAN_04-10-26.md lines 39, 45-46, 49-50, 52, 54-61, 141-172, 280-281, 290-297, 321, 323-335, 355-357, 359-360, 365-366, 374-375, 377-378, 385, 387, 389. Nothing else.
Advisory: S6 comments, test names and docstrings must not name the deleted chain (relative-performance-lines.ts, "relative performance"): S6-dangling is case-insensitive.
Tests: RT3; record red runs first (UV_FROZEN=1 on every pytest); each gate once after the last edit. Spike results go in report heading 9.
Budget: 130 tool calls, 100 min, 4 CI polls, 3-6 USD. Retry: 2 fix cycles; same failure twice stops.
Report: process/general-plans/active/screener-batch2_04-10-26/screener-batch2-s6_REPORT_09-10-26.md (11 headings; 6 = gates with SHA and UTC).
Stop at review if: irreversible or outward action, scope expansion, doubt, a diff touching CLAUDE.md, AGENTS.md, README.md, .claude/, .github/, deploy/, or a file outside Owned.
Autonomy: edit Owned, run gates, push, open PR, wait for CI. Never deploy; no secrets.
