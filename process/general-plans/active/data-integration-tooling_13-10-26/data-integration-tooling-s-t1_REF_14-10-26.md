ROLE: WORKER
You are a WORKER: direct lane. Do not orchestrate, do not spawn sessions or subagent chains; load only the files listed below; this overrides any orchestrator wording in CLAUDE.md.

Task: T54 (slice S-T1) - tooling project skeleton, isolation and CI-visible guards. RT2.
Repo: psychic-train. Base: origin/main after PR #65 merge (git fetch; branch from origin/main; it contains the validated plan).
Branch: claude/t54-dit-s-t1-skeleton-guards
Acceptance: tools/data-integration is an importable uv project with the pins from DIT-1; the API install is unchanged; guards in api/tests/tooling_guards pass; AC-2, 4, 5, 15, 21 (gitignore half) per the plan section.
Owned: tools/data-integration/{pyproject.toml,uv.lock,README.md}, tools/data-integration/src/data_integration/{__init__,types,status,paths}.py, tools/data-integration/scripts/check_clean_install.py, tools/data-integration/tests/{conftest,test_skeleton}.py, api/tests/tooling_guards/{__init__,test_tooling_isolation,test_import_boundary,test_marker_audit}.py, .gitignore (append only). uv.lock is generated.
Read (only these):
 1. CLAUDE.md (13,443 B)
 2. process/general-plans/active/data-integration-tooling_13-10-26/data-integration-tooling_PLAN_14-10-26.md lines 40-75 (Common, 6,060 B) and lines 88-100 (S-T1, 4,012 B)
 3. api/data/cache.py lines 1-30 (1,106 B); .gitignore (1,746 B)
Read total: 13,443 + 6,060 + 4,012 + 1,106 + 1,746 = 26,367 B + this envelope (3,993 B) = 30,360 B, under the 36,000 B cap.
Tests: red-first (failing stubs, record red count); log API baseline on untouched base (expected 1143 passed, 1 skipped, 5 deselected; a different count stops at needs_input; afterwards passed = baseline + new guard tests). Gates: UV_FROZEN=1 uv run --project api pytest api/tests/tooling_guards -q (unchanged parts green on base); uv lock --project tools/data-integration; UV_PROJECT_ENVIRONMENT=$HOME/.cache/dit-env uv run --project tools/data-integration pytest tools/data-integration/tests -q (no UV_FROZEN before uv.lock exists); python tools/data-integration/scripts/check_clean_install.py; import probe from the plan (failure = needs_input); UV_FROZEN=1 uv run --project api pytest api/ -q; git diff --check origin/main...HEAD. Set UV_PROJECT_ENVIRONMENT outside the repo; the harness hook blocks command text containing .venv, node_modules, dist, build;.
Advisory E1 (binding): test_skeleton asserts the pandas/pyarrow/duckdb pins equal api/uv.lock (3.0.6, 25.0.1, 1.5.5); tree scans skip .venv. Workflows must contain no tools/data-integration; never scan for the word playwright.
Done when: gates green on head SHA; api pytest = baseline + guard tests; git diff --exit-code api/uv.lock.
After your report, stop; do not wait on CI or check in. needs_input means STOP: do NOT merge, do NOT open a new PR.
You never merge. Open one PR (draft) against main and stop. Cost is reported by the planner, not the worker. Spend cap 15 USD; ask at 7 USD (stop with needs_input). No secrets, keys, IPs or user names anywhere. Synthetic fixtures only; no live network; never run npx, REA or any real scrape.
Forbidden (planner-side or protected): CLAUDE.md, AGENTS.md, .claude/, .mcp.json, .github/, deploy/, api/uv.lock, api/pyproject.toml, existing adapter/cache code, process/MASTER-PLAN.md, process/context/decisions.md.
Retry budget: 2 fix cycles per gate; same failure twice stops. Stop at review if: scope expansion, irreversible action, unverifiable condition, any doubt. ASCII only.
Report: process/general-plans/active/data-integration-tooling_13-10-26/data-integration-tooling-s-t1_REPORT_14-10-26.md
Report headings (11, in order): 1 Task ID, 2 Outcome, 3 Summary, 4 Files changed, 5 Commits, 6 Tests run (command, result, UTC, SHA), 7 Tests NOT run, 8 Deviations, 9 Blockers (put any MASTER-PLAN registry-update request here), 10 Follow-up (put decision requests and proposed tasks here), 11 Context cost (note any extra docs opened).
Autonomy: edit Owned, run gates, push, draft PR. Never merge.
