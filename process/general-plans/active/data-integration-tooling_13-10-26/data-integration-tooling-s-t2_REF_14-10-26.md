ROLE: WORKER
You are a WORKER: direct lane. Do not orchestrate or spawn sessions/subagents; load only the files listed below; this overrides orchestrator wording in CLAUDE.md.

Task: T55 (slice S-T2) - approval gate, local approval store, store guards. RT2.
Repo: psychic-train. Base: origin/main (git fetch; contains wave 1).
Branch: claude/t55-dit-s-t2-approval-gate
Acceptance: AC-1, 3, 21, 22 per the plan section.
Owned: tools/data-integration/src/data_integration/{approvals,gate,approval_cli}.py, tools/data-integration/tests/{test_gate,test_approvals_store,test_approval_cli}.py, api/tests/tooling_guards/test_approval_store_guard.py.
Read (only these):
 1. CLAUDE.md (13,443 B)
 2. process/general-plans/active/data-integration-tooling_13-10-26/data-integration-tooling_PLAN_14-10-26.md lines 40-75 (Common, 6,060 B) and 101-113 (S-T2, 2,808 B)
 3. tools/data-integration/src/data_integration/{types,status,paths}.py (2,182 B); api/data/layout.py lines 106-142 (1,125 B); api/tests/tooling_guards/_common.py (1,058 B) and test_import_boundary.py lines 9-26 (758 B); tools/data-integration/tests/conftest.py (1,444 B)
Read total: 13,443 + 6,060 + 2,808 + 2,182 + 1,125 + 1,058 + 758 + 1,444 = 28,878 B + this envelope (3,938 B) = 32,816 B, under the 36,000 B cap.
Binding: gate is standard-library only. FetchPass has a private constructor token and is host- and page-bound; consumers use isinstance on the real class. Refused.reason: missing|expired|tier_too_low|store_missing|store_corrupt|bad_clock. Source names match ^[a-z0-9][a-z0-9_-]{0,63}$ before any path is built; a bad name gives Refused, never an exception. Expiry is now >= expiry, UTC ISO-8601 with Z. Advisory E2: permits() tests cover userinfo host, non-http scheme, port. approval_cli `status` is Python, shows the placeholder path; `add` refuses without a TTY and needs the source name typed. Store: paths.approvals_dir() (DIT_APPROVALS_DIR override, LOCALAPPDATA default); tests use tmp_path.
Tests: red-first (record red count); log the API baseline on the untouched base (expected 1143 passed, 1 skipped, 5 deselected; a different count stops at needs_input). Gates: UV_PROJECT_ENVIRONMENT=$HOME/.cache/dit-env uv run --project tools/data-integration pytest tools/data-integration/tests -q; UV_FROZEN=1 uv run --project api pytest api/tests/tooling_guards -q; UV_FROZEN=1 uv run --project api pytest api/ -q; git diff --exit-code api/uv.lock; git diff --check origin/main...HEAD. Avoid command text with .venv, node_modules, dist, build (hook blocks it); keep guard string-splitting readable.
Done when: both suites green on head SHA; no *.approval.json outside tmp_path.
After your report, stop; do not wait on CI or check in. needs_input means STOP: do NOT merge, do NOT open a new PR.
You never merge. Open one PR (draft) against main and stop. Cost is reported by the planner, not the worker. Spend cap 15 USD; ask at 7 USD (stop with needs_input). No secrets, keys, IPs or user names anywhere. Synthetic fixtures only; no live network; never run npx, REA or any real scrape. Must NOT: write to a real LOCALAPPDATA/home path, ship sample approvals, touch fetch code.
Forbidden: CLAUDE.md, AGENTS.md, .claude/, .mcp.json, .github/, deploy/, api/uv.lock, api/pyproject.toml, existing adapter/cache code, process/MASTER-PLAN.md, process/context/decisions.md, S-T1 guard files.
Retry budget: 2 fix cycles per gate; same failure twice stops. ASCII only.
Report: process/general-plans/active/data-integration-tooling_13-10-26/data-integration-tooling-s-t2_REPORT_14-10-26.md
Report headings (11, in order): 1 Task ID, 2 Outcome, 3 Summary, 4 Files changed, 5 Commits, 6 Tests run (command, result, UTC, SHA), 7 Tests NOT run, 8 Deviations, 9 Blockers (put any MASTER-PLAN registry-update request here), 10 Follow-up (put decision requests and proposed tasks here), 11 Context cost (note any extra docs opened).
Autonomy: edit Owned, run gates, push, draft PR.
