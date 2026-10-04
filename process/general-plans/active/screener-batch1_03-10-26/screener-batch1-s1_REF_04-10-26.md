ROLE: WORKER
You are a WORKER: direct lane. Do not orchestrate, do not spawn sessions or subagent chains, load only the files listed below; this overrides any orchestrator wording in CLAUDE.md or elsewhere. Exception (RT3 capped lane, plan S1 "Lane"): at most 3 subagents (sonnet), 15 USD total, one level deep, every one listed in report heading 11: one vc-tester confirming gates, one read-only reviewer diffing api/models/screener.py against web/lib/types/screener.ts.

Task: T32 (batch 1, slice S1) - freshness core: forming candle expires, gap bug fixed, sub-daily history bounded, every chart payload carries age/stale fields, existing red proof turns green.
Acceptance: gates G-S1-1..G-S1-11 in the plan pass (G-S1-11 = red-first record); P-S1-1 stays a user-PC probe (status `review`, not claimed).
Owned files / Forbidden / Frozen / Design / Tests: exactly as in the plan's S1 section (Owned (exact), Forbidden, Frozen, Design, Tests). Any other existing test that breaks: stop at `needs_input`.
Branch: claude/t32-s1-freshness-core (from main)
Read (plan, by line range; re-derive with `grep -n '^## \|^### '` first): process/general-plans/active/screener-batch1_03-10-26/screener-batch1_PLAN_03-10-26.md lines 36-45, 48-56, 65-96, 259-269, 290-307, 353-364, 391-396. Do not read other plan parts. operating-instructions.md: not named.
Tests: tier RT3; required commands: G-S1-1..G-S1-11 as in "S1 exact gates" (UV_FROZEN=1 for every pytest run); first run G-S1-1 once on the untouched base and record it (red-first); run each gate once after your last edit; full-suite budget: 2 runs.
Budget: 120 tool calls, 90 minutes, 4 CI polls, 2-5 USD (estimate).
Retry budget: 2 fix cycles; same failure twice stops.
Report: process/general-plans/active/screener-batch1_03-10-26/screener-batch1-s1_REPORT_04-10-26.md using the 11-heading template (heading 6: every gate with SHA and UTC time; heading 9: the two test-assertion edits, seed/refresh script notes; heading 11: subagents listed).
Also write s1-probe/probe_freshness.py (read-only, plan S1 "Gates and probe") and the backlog stub named in Owned.
Stop and report at `review` if: irreversible or outward-facing action, scope expansion, unverifiable condition, any doubt, a diff touching CLAUDE.md, AGENTS.md, README.md, .claude/, .github/ or deploy/, or a needed file outside Owned.
Autonomy: may edit Owned files, run gates, push your branch, open a PR, wait for CI. Never merge unless the standing worker rule in master-planner.md section 5 says so; never deploy; no secrets in files, commits or logs. Do not deploy S1 to the PC (S8 must merge first).
