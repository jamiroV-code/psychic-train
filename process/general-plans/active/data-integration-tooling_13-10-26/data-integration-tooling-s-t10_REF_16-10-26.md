ROLE: WORKER
Direct lane: no spawning; read only below.

Task: T66 (S-T10) - page outline on selector miss. RT2. Base origin/main. Branch: claude/t66-dit-s-t10-outline
Acceptance: Amendment A4 (AC-33..AC-36) = the file process/general-plans/active/data-integration-tooling_13-10-26/data-integration-tooling-amendment-a4_PLAN_16-10-26.md, read from main (the owner merged the docs PR before dispatch). Owner decision 16-10-26 (planner quotes the owner message here when dispatching). Owned/forbidden: exactly as in A4. Outline = counts, host names, link paths, id/class tokens; never page text.
Read (PLAN = this folder's PLAN_14-10-26.md; code under tools/data-integration/src/data_integration/), total with envelope about 31,000 B (<= 35,000):
 1. CLAUDE.md 13,443 B
 2. PLAN l.58-75 (3,011); the whole A4 file (about 5,500)
 3. parse.py whole; pipeline.py 20-24, 46-65; cli.py 54-62, 117-121, 142-161, 211-221
 4. all-data-sources.md: the preview line(s) of "New dataset workflow"
Unread: types.py, status.py, validate.py, adaptive.py, fetch_tier*.py, others.
First: grep the tests for "matched nothing" and "PipelineResult("; an existing test that would break = needs_input. SelectorMatchedNothing does not exist yet: create it. Measure the docs section byte count on origin/main first (delta <= +200 B over that baseline). Wrap the outline call at both sites in try/except Exception.
Red-first (record red count): write test_page_outline, test_cli_outline (fixture HTML in tests/fixtures_outline/, fake registry, no network), api/tests/tooling_guards/test_outline_guard.py; they fail on base.
Baselines: measure on untouched origin/main, no hard-coding. Expect API >= 1199 passed/1 skipped/5 deselected, tooling >= 601, guards >= 56; fewer or any failure: needs_input.
Gates: UV_PROJECT_ENVIRONMENT=$HOME/.cache/dit-env uv run --project tools/data-integration pytest tools/data-integration/tests -q; UV_FROZEN=1 uv run --project api pytest api/tests/tooling_guards -q; UV_FROZEN=1 uv run --project api pytest api/ -q; git diff --exit-code api/uv.lock api/pyproject.toml; git diff --check origin/main...HEAD; git diff origin/main...HEAD empty for forbidden files. Avoid command text with venv, node_modules, dist, build, vendor, coverage. ASCII. After: baseline + new tests (state it).
Must NOT: run a real scrape; use network; run npx or REA; run scrapling install or playwright install; create a real approval record; edit files outside Owned; show page text in the outline.
Forbidden: CLAUDE.md, AGENTS.md, .claude/, .mcp.json, .github/, deploy/, api/ (except the guard test), decisions.md, process/MASTER-PLAN.md, other process/context/*.
Cap 15 USD; ask at 7 (needs_input). One draft PR against main; never merge; after report stop, do not wait on CI. needs_input means STOP. No secrets, keys, IPs, user names. 2 fix cycles/gate.
Report: process/general-plans/active/data-integration-tooling_13-10-26/data-integration-tooling-s-t10_REPORT_16-10-26.md
Headings (11): 1 Task ID, 2 Outcome, 3 Summary (with a "Known limits" bullet), 4 Files changed, 5 Commits, 6 Tests run (cmd, result, UTC, SHA), 7 Tests NOT run, 8 Deviations, 9 Blockers, 10 Follow-up, 11 Context cost.
