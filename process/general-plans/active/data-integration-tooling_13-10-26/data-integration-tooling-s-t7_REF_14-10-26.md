ROLE: WORKER
Direct lane: no spawning; read only below.

Task: T62 (S-T7) - CLI `python -m data_integration`. RT2. Base origin/main (T59 merged). Branch: claude/t62-dit-s-t7-cli
Acceptance: Amendment A1 (US-4; AC-1, AC-3 via CLI). Owned (tools/data-integration/): src/data_integration/{__main__,cli,recipe}.py; tests/{test_cli,test_recipe}.py; recipes/example.recipe.json (synthetic, host example.test); api/tests/tooling_guards/test_cli_guard.py.
Read (PLAN = this folder's PLAN_14-10-26.md; code under tools/data-integration/src/data_integration/):
 1. CLAUDE.md 13,443 B
 2. PLAN l.40-75 (6,060); l.332-342 (4,465)
 3. approval_cli.py 65-93; rea/wrapper.py 33-46, 99-107, 160-176; pipeline.py 19-24, 30-44; gate.py 16-40, 67-72; politeness.py 11-14; fetch_tier1.py 81-83; robots.py 19-22; adaptive.py 31-37; parse.py 9-17; validate.py 24; approvals.py 35-36, 52-64, 103-105, 118; types.py 8-14; paths.py 37-38; provenance.py 42-46 (6,622 B)
 Total with envelope < 35,000 B. Unread: status.py (use status.ALL_STATUSES), response_cache.py; fetch_tier2/3.py missing or off-registry: needs_input.
Binding (PVL G1-G7):
 G1 exit codes: ok,cache_hit,dry-run,preview=0; usage/bad recipe/flags=2; gate refusal=3 (missing,expired,tier_too_low,store_missing,store_corrupt,bad_clock,url_not_approved); robots_blocked,timeout,connection_failed,http_error,challenge_page=4; invalid=5; changed,uncertain=6; refused=7 (3 sources: off-list URL/redirect, no pass, TargetNotEmpty; message from detail). After request_access check pass_.permits(url): refusal=exit 3 url_not_approved, also in --dry-run. rea: Refusal=2, ReaResult INVALID=5 (FileNotFoundError=Node/npx message, TimeoutExpired=timeout message, else "REA failed"), OK=0. Tests parametrize status.ALL_STATUSES (code+plain message), 6 Refused reasons+url_not_approved, each rea branch.
 G2 outcome line: id=pass_.approval_id, revision=pass_.approval_revision, expiry=pass_.expires; rate=ApprovalStore.read(source).rate_policy. `approvals status` prints no id; test only expiry equals the status line.
 G3 tests: --accept-baseline (no store; store+same selector; store+other selector: allowed only 1st and 3rd; with baseline=exit 2, no write); --replace empty provenance=exit 2 before any fetch (registry calls 0); with records=allowed.
 G4 measure baselines on untouched origin/main, no hard-coding. Expect >= API 1184 passed/1 skipped/5 deselected, tooling >= 266, guards >= 41; any failure or fewer: needs_input.
 G5 leave wave/spend lines alone; btc-hist recipe is T61 (planner).
 G7 schema_version == 1; min_delay finite 1.0..3600; max_concurrent ints 1..2; preview prints "baseline: present/none"; --refresh no-op in preview/dry-run.
Gates: UV_PROJECT_ENVIRONMENT=$HOME/.cache/dit-env uv run --project tools/data-integration pytest tools/data-integration/tests -q; UV_FROZEN=1 uv run --project api pytest api/tests/tooling_guards -q; UV_FROZEN=1 uv run --project api pytest api/ -q; git diff --exit-code api/uv.lock api/pyproject.toml; git diff --check origin/main...HEAD. Avoid command text with .venv, node_modules, dist, build. Red-first (record red count); ASCII. After: baseline + new tests (state it).
Must NOT: run npx, REA or any real scrape; use network; edit existing modules, workflows, fixture_server.py; add proxy option; import fetch_tier* in tests.
Forbidden: CLAUDE.md, AGENTS.md, .claude/, .mcp.json, .github/, deploy/, api/ (except guard test), process/MASTER-PLAN.md, process/context/*.
After report stop; do not wait on CI. needs_input means STOP: no merge, no new PR. Never merge; one draft PR against main. Cap 15 USD; ask at 7 (needs_input). No secrets, keys, IPs, user names. Loopback only. 2 fix cycles/gate.
Report: process/general-plans/active/data-integration-tooling_13-10-26/data-integration-tooling-s-t7_REPORT_14-10-26.md
Headings (11): 1 Task ID, 2 Outcome, 3 Summary, 4 Files changed, 5 Commits, 6 Tests run (cmd, result, UTC, SHA), 7 Tests NOT run, 8 Deviations, 9 Blockers, 10 Follow-up, 11 Context cost.
