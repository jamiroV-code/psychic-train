ROLE: WORKER
You are a WORKER: direct lane. Do not orchestrate or spawn subagents; load only the files below.

Task: T60 (slice S-T5b) - docs section, router row, validators. RT0. Docs only; you must not touch code.
Repo/base: origin/main (git fetch).
Branch: claude/t60-dit-s-t5b-docs-router
Acceptance: AC-18.
Owned (the only edits): process/context/data-sources/all-data-sources.md (frontmatter keywords: add REA, scrapling, scrape, approval; ONE new section 'New dataset workflow', at most 3,500 B by wc -c) and process/context/all-context.md (ONE new row in the hand-written Task Routing Table; do NOT hand-edit the GENERATED:routing tables). Planner-granted exception to the usual process/context ban. Disjoint from T59 (tools/data-integration only).
Read (only these):
 1. CLAUDE.md (13,443 B)
 2. plan data-integration-tooling_PLAN_14-10-26.md lines 40-75 (Common, 6,060 B) and 163-173 (S-T5b, 1,735 B)
 3. all-data-sources.md lines 1-12 (628 B) and 45-66 (1,654 B); all-context.md lines 70-93 (2,116 B)
 4. Merged code (true names/options): rea/evidence_template.md (318 B); approval_cli.py lines 70-92 (955 B); approvals.py lines 52-64 (284 B); rea/wrapper.py lines 20-35 (458 B) and 99-125 (1,008 B); pipeline.py lines 30-45 (348 B); README.md lines 25-30 (149 B)
Read total 29,156 B + this envelope (under 5,200 B) = under 34,400 B (cap 36,000 B).
Section content: 4 steps (REA study with evidence note, approval record via approval_cli add, fetch via pipeline, review and store); evidence templates (VERIFIED/ASSUMED findings); approval fields; local-store backup guidance (approvals, scrape store, evidence live outside the repo; back them up separately); REA wrapper how-to (run_rea; live commands need confirm_source listed in findings; owner runs it, workers never); rule 'no scraped data in git-tracked directories without a recorded redistribution check'; Farside on-demand refresh is outside the tooling; known limits (tiers 2/3 not proven live, approval-file forgeability, REA web modes unverified, Windows/Py 3.12 unverified until owner probes AC-16/17); owner-run commands as real invocations. T59 adds scripts/probe_tier1.py and probe_tier2.py at the same time: name them if on origin/main, else mark them 'added by T59' and say so in heading 10. State only what the merged code does; quote real option names; no invented flags. The new row cites only existing backticked process/... paths and carries the REA/scrapling/approval wording.
Gates (RT0): node .claude/skills/vc-context-discovery/scripts/discover-context.mjs --check-routing; node .claude/skills/vc-generate-context/scripts/validate-all-context.mjs; node .claude/skills/vc-audit-context/scripts/validate-context-discovery.mjs; PLANNER-BUDGET: run `sed -n 171,183p process/development-protocols/master-planner.md | bash` (run it, do not read it) before and after; record headroom. The baseline already exits 1 because process/context/current-state.md is over its 8,000 B ceiling: record that as pre-existing, do NOT fix it. Router part of all-context.md must stay under 7,000 B (recompute it). git diff --check origin/main...HEAD. Avoid command text containing .venv, node_modules, dist, build. Red-first and API tests do not apply (no code); no API test run needed.
Done when: section <= 3,500 B; validators as before or better; only the two owned files changed.
Must NOT: touch code, tests, any other doc, MASTER-PLAN.md, current-state.md; run npx, REA, scrapling install or any real scrape; use the network.
After your report, stop; do not wait on CI or check in. needs_input means STOP: do NOT merge, do NOT open a new PR.
You never merge. Open one PR (draft) against main and stop. Cost is reported by the planner, not the worker. Spend cap 15 USD; ask at 7 USD (needs_input). No secrets, keys, IPs or user names. Synthetic examples only; no live network.
Forbidden: CLAUDE.md, AGENTS.md, .claude/, .mcp.json, .github/, deploy/, api/, tools/, process/MASTER-PLAN.md, process/context/decisions.md and every other process doc.
Retry: 2 fix cycles per gate; same failure twice stops. ASCII only.
Report: process/general-plans/active/data-integration-tooling_13-10-26/data-integration-tooling-s-t5b_REPORT_14-10-26.md
Report headings (11, in order): 1 Task ID, 2 Outcome, 3 Summary, 4 Files changed, 5 Commits, 6 Tests run (command, result, UTC, SHA), 7 Tests NOT run, 8 Deviations, 9 Blockers (MASTER-PLAN update requests), 10 Follow-up, 11 Context cost (extra docs opened).
Autonomy: edit Owned, run gates, push, draft PR.
