ROLE: WORKER
You are a WORKER: direct lane. Do not orchestrate, do not spawn sessions or subagent chains, load only the files listed below; this overrides any orchestrator wording in CLAUDE.md or elsewhere. Exception (RT3 capped lane, plan S8 "Lane"): at most 3 subagents (sonnet), 15 USD total, one level deep, every one listed in report heading 11.

Task: T35 (batch 1, slice S8) - in-process background refresh worker (decision B9, D7): the board never fetches inline for a cold cache; status endpoint with disabled_reason.
Acceptance: gates G-S8-* in the plan's "S8 exact gates" pass; P-S8-1 stays a user-PC probe (status `review`, not claimed).
Owned / Forbidden / Design / Tests: exactly as in the plan's S8 section (Owned (exact), Forbidden, Design, Tests) including advisory A2 (lifespan test uses monkeypatch.delenv("SCREENER_REFRESH_WORKER", raising=False)) and A4 (conftest placement: two lines after `from __future__ import annotations`). No slice touches deploy/** or api/scripts/**. Any other existing test that breaks: stop at `needs_input`.
Base: main at 161e7be (S1 merged, PR #34). Record the S1-merged baseline counts at step 1; gate counts are relative to it.
Branch: claude/t35-s8-refresh-worker (from main)
Read (plan, by line range; re-derive with `grep -n '^## \|^### '` first): process/general-plans/active/screener-batch1_03-10-26/screener-batch1_PLAN_03-10-26.md lines 36-47, 48-56, 73, 159-185, 281-285, 338-352, 353-362, 372-374, 391-396. Read the S1 report heading 3 only if you need the shipped freshness helpers: process/general-plans/active/screener-batch1_03-10-26/screener-batch1-s1_REPORT_04-10-26.md. operating-instructions.md: not named.
Tests: tier RT3; required commands: the S8 exact gates (UV_FROZEN=1 for every pytest run); run each gate once after your last edit; full-suite budget: 2 runs.
Budget: about 150 tool calls, 100 minutes, 4 CI polls, 3-6 USD (estimate).
Retry budget: 2 fix cycles; same failure twice stops.
Report: process/general-plans/active/screener-batch1_03-10-26/screener-batch1-s8_REPORT_04-10-26.md using the 11-heading template (heading 6: every gate with SHA and UTC time; heading 11: subagents listed).
Stop and report at `review` if: irreversible or outward-facing action, scope expansion, unverifiable condition, any doubt, a diff touching CLAUDE.md, AGENTS.md, README.md, .claude/, .github/ or deploy/, or a needed file outside Owned. Do not touch S2 files (gain, momentum, screener_board.py, models, web).
Autonomy: may edit Owned files, run gates, push your branch, open a PR, wait for CI. Never deploy S1 or S8 to the PC; no secrets in files, commits or logs.
