ROLE: WORKER
You are a WORKER: direct lane. Do not orchestrate, do not spawn sessions or subagent chains; load only the files listed below; this overrides any orchestrator wording in CLAUDE.md.

Task: T53 (slice S-T0) - apply the approved decisions to the data-integration SPEC wording. Docs only, RT0.
Repo: psychic-train. Base: origin/main after PR #65 merge (git fetch; branch from origin/main; it contains the validated plan).
Branch: claude/t53-dit-s-t0-spec-amendments
Acceptance: the SPEC matches the plan list "ACs whose wording changes"; AC numbering kept; change-log line dated 14-10-26 added; OQ-12, OQ-13 closed; L3 rewritten wrapper-only; INNOVATE questions 1-8 marked answered; every remaining SPEC line mentioning "rea-agents setup" contains "rejected" or "superseded".
Owned: process/general-plans/active/data-integration-tooling_13-10-26/data-integration-tooling_SPEC_13-10-26.md ONLY. Edit nothing else.
Read (only these):
 1. CLAUDE.md (13,443 B)
 2. process/general-plans/active/data-integration-tooling_13-10-26/data-integration-tooling_PLAN_14-10-26.md lines 40-75 (Common rules, 6,060 B) and lines 76-87 (S-T0, 1,151 B)
 3. SPEC lines 29, 91-116, 147-148, 150-173 (5,917 B)
Read total: 13,443 + 6,060 + 1,151 + 5,917 = 26,571 B + this envelope (2,987 B) = 29,558 B, under the 36,000 B cap.
Tests: RT0. Gates: (a) git diff --stat origin/main...HEAD lists exactly the SPEC file; (b) grep -n "rea-agents setup" <SPEC>: every hit line has "rejected" or "superseded"; (c) git diff --check origin/main...HEAD exits 0; (d) SPEC is ASCII. Advisories E1-E8 do not apply to this slice.
Done when: gates pass, PR (draft) open, report written.
After your report, stop; do not wait on CI or check in. needs_input means STOP: do NOT merge, do NOT open a new PR.
You never merge. Open one PR (draft) against main and stop. Cost is reported by the planner, not the worker. Spend cap 15 USD; ask at 7 USD (stop with needs_input). No secrets, keys, IPs or user names anywhere. Synthetic fixtures only; no live network; never run npx, REA or any real scrape.
Forbidden (planner-side or protected): CLAUDE.md, AGENTS.md, .claude/, .mcp.json, .github/, deploy/, api/uv.lock, api/pyproject.toml, existing adapter/cache code, process/MASTER-PLAN.md, process/context/decisions.md.
Retry budget: 2 fix cycles per gate; same failure twice stops. Stop at review if: scope expansion, irreversible action, unverifiable condition, any doubt. ASCII only.
Report: process/general-plans/active/data-integration-tooling_13-10-26/data-integration-tooling-s-t0_REPORT_14-10-26.md
Report headings (11, in order): 1 Task ID, 2 Outcome, 3 Summary, 4 Files changed, 5 Commits, 6 Tests run (command, result, UTC, SHA), 7 Tests NOT run, 8 Deviations, 9 Blockers (put any MASTER-PLAN registry-update request here), 10 Follow-up (put decision requests and proposed tasks here), 11 Context cost (note any extra docs opened).
Autonomy: edit the SPEC, run gates, push the branch, open a draft PR. Nothing else.
