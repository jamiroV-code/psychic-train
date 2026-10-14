ROLE: WORKER
You are a WORKER: direct lane. Do not orchestrate or spawn sessions/subagents; load only the files listed below; this overrides orchestrator wording in CLAUDE.md.

Task: T56 (slice S-T5a) - REA allow-listed wrapper, evidence template, tests. RT2.
Repo: psychic-train. Base: origin/main (git fetch; contains wave 1).
Branch: claude/t56-dit-s-t5a-rea-wrapper
Acceptance: AC-19 and AC-23 (amended) per the plan section.
Owned: tools/data-integration/src/data_integration/rea/{__init__,wrapper,allowlist,evidence_template.md}, tools/data-integration/tests/{test_rea_wrapper,test_rea_evidence}.py, api/tests/tooling_guards/test_rea_guards.py.
Read (only these):
 1. CLAUDE.md (13,443 B)
 2. process/general-plans/active/data-integration-tooling_13-10-26/data-integration-tooling_PLAN_14-10-26.md lines 40-75 (Common, 6,060 B) and 150-162 (S-T5a, 3,559 B)
 3. tools/data-integration/src/data_integration/{status,paths}.py (1,603 B); api/tests/tooling_guards/_common.py (1,058 B) and test_import_boundary.py lines 9-26 (758 B); tools/data-integration/tests/conftest.py (1,444 B)
Read total: 13,443 + 6,060 + 3,559 + 1,603 + 1,058 + 758 + 1,444 = 27,925 B + this envelope (3,920 B) = 31,845 B, under the 36,000 B cap.
Binding: exact frozenset allow-list (case-sensitive, first token); per-command flag allow-list; argument regex ^[A-Za-z0-9._/:@=-]{1,200}$ plus forbidden " % ^ & | < >; subprocess.run(..., shell=False); on Windows resolve npx.cmd explicitly; npm_config_ignore_scripts=true. Evidence outside the repo via paths.evidence_dir() (DIT_EVIDENCE_DIR, tmp_path in tests); redact subject.local_path and normalized_result.input_path. Evidence template ends with the fixed footer sentence from the plan. Advisory E5: test a Windows drive-letter path (backslash fails the regex; convert to forward slashes).
Tests: ALL use a fake runner; the one real npx call is the developer's, later, NOT your gate. Red-first (record red count); log the API baseline on the untouched base (expected 1143 passed, 1 skipped, 5 deselected; a different count stops at needs_input). Gates: UV_PROJECT_ENVIRONMENT=$HOME/.cache/dit-env uv run --project tools/data-integration pytest tools/data-integration/tests -q; UV_FROZEN=1 uv run --project api pytest api/tests/tooling_guards -q; UV_FROZEN=1 uv run --project api pytest api/ -q; git diff origin/main...HEAD -- .claude CLAUDE.md AGENTS.md .mcp.json is empty; git diff --exit-code api/uv.lock; git diff --check origin/main...HEAD. Avoid command text with .venv, node_modules, dist, build (hook blocks); keep guard string-splitting readable.
Done when: all gates green on head SHA.
After your report, stop; do not wait on CI or check in. needs_input means STOP: do NOT merge, do NOT open a new PR.
You never merge. Open one PR (draft) against main and stop. Cost is reported by the planner, not the worker. Spend cap 15 USD; ask at 7 USD (stop with needs_input). No secrets, keys, IPs or user names anywhere. Synthetic fixtures only; no live network; never run npx, REA or any real scrape. Must NOT: run rea-agents setup, create .mcp.json, edit agent configs, write evidence into the repo.
Forbidden: CLAUDE.md, AGENTS.md, .claude/, .mcp.json, .github/, deploy/, api/uv.lock, api/pyproject.toml, existing adapter/cache code, process/MASTER-PLAN.md, process/context/decisions.md, S-T1 guard files.
Retry budget: 2 fix cycles per gate; same failure twice stops. ASCII only.
Report: process/general-plans/active/data-integration-tooling_13-10-26/data-integration-tooling-s-t5a_REPORT_14-10-26.md
Report headings (11, in order): 1 Task ID, 2 Outcome, 3 Summary, 4 Files changed, 5 Commits, 6 Tests run (command, result, UTC, SHA), 7 Tests NOT run, 8 Deviations, 9 Blockers (put any MASTER-PLAN registry-update request here), 10 Follow-up (put decision requests and proposed tasks here), 11 Context cost (note any extra docs opened).
Autonomy: edit Owned, run gates, push, draft PR.
