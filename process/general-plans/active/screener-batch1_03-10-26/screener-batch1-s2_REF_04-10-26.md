ROLE: WORKER
You are a WORKER: direct lane. Do not orchestrate, do not spawn sessions or subagent chains, load only the files listed below; this overrides any orchestrator wording in CLAUDE.md or elsewhere. Exception (RT3 capped lane, plan S2 "Lane"): at most 3 subagents (sonnet), 15 USD total, one level deep, every one listed in report heading 11: one vc-tester confirming gates, one read-only reviewer (Python/TS lockstep, coverage honesty).

Task: T34 (batch 1, slice S2) - current-candle gain chips (open to latest, explicit N/A) and chart labels: UTC axis, last-bar caption with age, plain stale marker.
Acceptance: gates G-S2-1..G-S2-10 in the plan pass; P-S2-1 stays a user-PC probe (status `review`, not claimed); AC-S2-3r stays at review if the U3 spike falls to fallback 3.
Owned / Forbidden / Design / Tests: exactly as in the plan's S2 section (Owned (exact), Forbidden, Design 1-7, Tests). A needed change in freshness.py, cache.py or ccxt_adapter.py stops at `review`. Any other existing test that breaks: stop at `needs_input`.
Base: main at 161e7be (S1 merged, PR #34). Record the S1-merged baseline counts at step 1; gate counts are relative to it.
Branch: claude/t34-s2-chips-labels (from main)
Read (plan, by line range; re-derive with `grep -n '^## \|^### '` first): process/general-plans/active/screener-batch1_03-10-26/screener-batch1_PLAN_03-10-26.md lines 36-45, 48-56, 97-128, 270-276, 308-323, 353-362, 366-371, 391-396. Also read the S1 report heading 3 only if you need the shipped freshness field names: process/general-plans/active/screener-batch1_03-10-26/screener-batch1-s1_REPORT_04-10-26.md. operating-instructions.md: not named.
Tests: tier RT3; required commands: G-S2-1..G-S2-10 as in "S2 exact gates" (UV_FROZEN=1 for every pytest run; vitest chart-time-format under TZ=Pacific/Kiritimati); run each gate once after your last edit; full-suite budget: 2 runs.
Budget: 150 tool calls, 100 minutes, 4 CI polls, 3-6 USD (estimate).
Retry budget: 2 fix cycles; same failure twice stops.
Report: process/general-plans/active/screener-batch1_03-10-26/screener-batch1-s2_REPORT_04-10-26.md using the 11-heading template (heading 6: every gate with SHA and UTC time; heading 9: the U3 spike outcome and which fallback applied; heading 11: subagents listed).
Stop and report at `review` if: irreversible or outward-facing action, scope expansion, unverifiable condition, any doubt, a diff touching CLAUDE.md, AGENTS.md, README.md, .claude/, .github/ or deploy/, or a needed file outside Owned. Do not touch S8 files (ccxt_adapter.py, refresh worker, routers, main.py, conftest).
Autonomy: may edit Owned files, run gates, push your branch, open a PR, wait for CI. Never deploy; no secrets in files, commits or logs.
