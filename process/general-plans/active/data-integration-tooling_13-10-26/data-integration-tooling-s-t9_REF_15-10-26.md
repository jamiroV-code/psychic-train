ROLE: WORKER
Direct lane: no spawning; read only below.

Task: T65 (S-T9) - resource-host allowance. RT2. Base origin/main. Branch: claude/t65-dit-s-t9-resource-hosts
Acceptance: Amendment A3 (AC-28..AC-32), read from main (the owner merged the docs PR before dispatch). Owner decision 15-10-26 (planner quotes the owner message here when dispatching). Owned/forbidden: exactly as in A3. gate.py only __slots__, __init__ (+1 object.__setattr__ line), line 95 FetchPass return; types.py not touched. provenance.py: add the resource_hosts key after line 47 (do not read it).
Read (PLAN = this folder's PLAN_14-10-26.md; code under tools/data-integration/src/data_integration/), total with envelope 34,760 B (<= 35,000):
 1. CLAUDE.md 13,443 B
 2. PLAN l.58-75 (3,011); l.368-379 (4,320)
 3. fetch_tier2.py 45-100, 157-161 (2,452); gate.py 28-41, 93-96 (1,198)
 4. approvals.py 51-100 (1,831); approval_cli.py 44-end (3,544)
 5. all-data-sources.md l.420 + 438 (961)
Unread: provenance.py, cli.py, others.
Red-first (record red count): write test_route_guard, test_resource_hosts, test_tier2_resource_browser (module mark browser), api/tests/tooling_guards/test_resource_host_guard.py; they fail on base. Stdlib-only files stay stdlib-only.
Baselines: measure on untouched origin/main, no hard-coding. Expect API >= 1196 passed/1 skipped/5 deselected, tooling >= 544, guards >= 53; fewer or any failure: needs_input.
Gates: UV_PROJECT_ENVIRONMENT=$HOME/.cache/dit-env uv run --project tools/data-integration pytest tools/data-integration/tests -q; UV_FROZEN=1 uv run --project api pytest api/tests/tooling_guards -q; UV_FROZEN=1 uv run --project api pytest api/ -q; git diff --exit-code api/uv.lock api/pyproject.toml; git diff --check origin/main...HEAD; git diff origin/main...HEAD empty for forbidden files; docs delta +550 B. Avoid command text with venv, node_modules, dist, build, vendor, coverage. ASCII. After: baseline + new tests (state it).
Must NOT: run a real scrape; use network; run npx or REA; run scrapling install or playwright install; create a real approval record (fake store in tmp_path only); edit files outside Owned.
Forbidden: CLAUDE.md, AGENTS.md, .claude/, .mcp.json, .github/, deploy/, api/ (except the guard test), decisions.md, process/MASTER-PLAN.md, other process/context/*.
Cap 15 USD; ask at 7 (needs_input). One draft PR against main; never merge; after report stop, do not wait on CI. needs_input means STOP. No secrets, keys, IPs, user names. 2 fix cycles/gate.
Report: process/general-plans/active/data-integration-tooling_13-10-26/data-integration-tooling-s-t9_REPORT_15-10-26.md
Headings (11): 1 Task ID, 2 Outcome, 3 Summary (with a "Known limits" bullet), 4 Files changed, 5 Commits, 6 Tests run (cmd, result, UTC, SHA), 7 Tests NOT run, 8 Deviations, 9 Blockers, 10 Follow-up, 11 Context cost.
