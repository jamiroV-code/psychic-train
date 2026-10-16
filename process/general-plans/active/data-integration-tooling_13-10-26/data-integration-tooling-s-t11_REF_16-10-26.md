ROLE: WORKER
Direct lane: no spawning; read only below.

Task: T67 (S-T11) - table header outline on missing columns. RT2. Base origin/main. Branch: claude/t67-dit-s-t11-table-headers
Acceptance: Amendment A5 (AC-37..AC-39) = process/general-plans/active/data-integration-tooling_13-10-26/data-integration-tooling-amendment-a5_PLAN_16-10-26.md, read from main (owner merged the docs PR first). Owner decision 16-10-26 (planner quotes it here when dispatching). Owned/forbidden: exactly as in A5. Outline = tables matched, header names, row/column counts; never data rows or page text.
Read (code under tools/data-integration/src/data_integration/), total <= 35,000 B (measure each with wc -c first; expected about 30,000):
 1. CLAUDE.md 13,443 B
 2. the whole A5 file
 3. parse.py whole; pipeline.py 46-65; cli.py 54-62, 142-161
 4. all-data-sources.md: preview line(s) of "New dataset workflow"
Unread: A4 file, types.py, status.py, validate.py, adaptive.py, fetch_tier*.py, others.
First: grep tests for "missing columns" and "PipelineResult("; an existing test that would break = needs_input. Missing columns is a returned string from validate_table, not an exception: create none. Measure the docs section bytes on origin/main first (delta <= +120 B). Wrap the outline call at both sites in try/except Exception.
Red-first (record red count): write test_table_outline, test_cli_table_outline (HTML in tests/fixtures_table_outline/, fake registry, no network), api/tests/tooling_guards/test_table_outline_guard.py (new); they fail on base.
Baselines: MEASURE on untouched origin/main; expect API >= 1202 passed/1 skipped/5 deselected, tooling >= 635, guards >= 59; fewer or any failure: needs_input.
Gates: UV_PROJECT_ENVIRONMENT=$HOME/.cache/dit-env uv run --project tools/data-integration pytest tools/data-integration/tests -q; UV_FROZEN=1 uv run --project api pytest api/tests/tooling_guards -q; UV_FROZEN=1 uv run --project api pytest api/ -q; git diff --exit-code api/uv.lock api/pyproject.toml; git diff --check origin/main...HEAD; git diff origin/main...HEAD empty for forbidden files. Avoid command text with venv, node_modules, dist, build, vendor, coverage. ASCII. State: baseline + new tests.
Must NOT: run a real scrape; use network; run npx or REA; run scrapling install or playwright install; create a real approval record; edit outside Owned; show data rows or page text.
Forbidden: CLAUDE.md, AGENTS.md, .claude/, .mcp.json, .github/, deploy/, api/ (except the guard test), decisions.md, process/MASTER-PLAN.md, other process/context/*.
Cap 15 USD; ask at 7 (needs_input). One draft PR against main; never merge; after report stop, do not wait on CI. needs_input means STOP. No secrets, keys, IPs, user names. 2 fix cycles/gate.
Report: process/general-plans/active/data-integration-tooling_13-10-26/data-integration-tooling-s-t11_REPORT_16-10-26.md
Headings (11): 1 Task ID, 2 Outcome, 3 Summary (with a "Known limits" bullet), 4 Files changed, 5 Commits, 6 Tests run (cmd, result, UTC, SHA), 7 Tests NOT run, 8 Deviations, 9 Blockers, 10 Follow-up, 11 Context cost.
