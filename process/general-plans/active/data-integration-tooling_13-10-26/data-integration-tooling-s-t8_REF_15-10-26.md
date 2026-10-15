ROLE: WORKER
Direct lane: no spawning; read only below.

Task: T64 (S-T8) - cloud-run support. RT2. Base origin/main. Branch: claude/t64-dit-s-t8-cloud-run
Acceptance: Amendment A2 (AC-24..AC-27). Owner decision 15-10-26 (planner quotes the owner message here when dispatching). Owned: tools/data-integration/src/data_integration/{approval_cli,approvals,paths}.py; tools/data-integration/tests/{test_approval_cli_cloud,test_paths_private}.py; api/tests/tooling_guards/test_cloud_guard.py; ONLY lines 415, 420, 427, 439 of process/context/data-sources/all-data-sources.md.
Read (PLAN = this folder's PLAN_14-10-26.md; code under tools/data-integration/src/data_integration/):
 1. CLAUDE.md 13,443 B
 2. PLAN l.58-75 (3,011); l.350-360 (4,082)
 3. approval_cli.py 44-end (2,167); approvals.py 51-72, 81-100 (1,597); paths.py all (983)
 4. all-data-sources.md l.413-443 (2,192)
 Total with envelope 31,475 B (<= 35,000). Unread: gate.py, cli.py, others.
Red-first (record red count): AC-27 docs asserts fail on base: "Workers never run live commands" absent; "--owner-statement", "connection_failed", "scrapling install" present; "stay on the owner's PC" absent (l.413-443); also TTY matrix, statement checks (AND DIT_APPROVALS_DIR set), PathInRepo for approvals_dir/scrape_dir (evidence_dir unchanged), approval_cli add and _status catch PathInRepo (exit 2), non-string owner_statement raises ValueError/StoreCorrupt. Stdlib-only files stay stdlib-only (GUARDED, test_approval_store_guard.py). Guard test scans only api/ (skip tooling_guards), deploy/, .github/workflows like test_cli_guard._scan_files; needles built by concatenation.
Baselines: measure on untouched origin/main, no hard-coding. Expect API >= 1192 passed/1 skipped/5 deselected, tooling >= 523, guards >= 49; fewer or any failure: needs_input.
Gates: UV_PROJECT_ENVIRONMENT=$HOME/.cache/dit-env uv run --project tools/data-integration pytest tools/data-integration/tests -q; UV_FROZEN=1 uv run --project api pytest api/tests/tooling_guards -q; UV_FROZEN=1 uv run --project api pytest api/ -q; git diff --exit-code api/uv.lock api/pyproject.toml; git diff --check origin/main...HEAD; git diff origin/main...HEAD empty for forbidden files. Avoid command text with venv, node_modules, dist, build, vendor, coverage. ASCII. After: baseline + new tests (state it).
Must NOT: run a real scrape; use network; run npx or REA; run scrapling install or playwright install; create a real approval record (fake store in tmp_path only); edit existing modules, workflows, tests, gate.py, cli.py, recipe.py, pipeline.py, fetch_tier*.py, provenance.py, rea/wrapper.py, evidence guard.
Forbidden: CLAUDE.md, AGENTS.md, .claude/, .mcp.json, .github/, deploy/, api/ (except guard test), decisions.md, process/MASTER-PLAN.md, other process/context/*.
Cap 15 USD; ask at 7 (needs_input). One draft PR against main; never merge; after report stop, do not wait on CI. needs_input means STOP. No secrets, keys, IPs, user names. 2 fix cycles/gate.
Report: process/general-plans/active/data-integration-tooling_13-10-26/data-integration-tooling-s-t8_REPORT_15-10-26.md
Headings (11): 1 Task ID, 2 Outcome, 3 Summary (with a "Known limits" bullet), 4 Files changed, 5 Commits, 6 Tests run (cmd, result, UTC, SHA), 7 Tests NOT run, 8 Deviations, 9 Blockers, 10 Follow-up, 11 Context cost.
