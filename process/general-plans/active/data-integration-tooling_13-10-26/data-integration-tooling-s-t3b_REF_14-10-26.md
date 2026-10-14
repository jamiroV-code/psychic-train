ROLE: WORKER
You are a WORKER: direct lane. Do not orchestrate or spawn sessions/subagents; load only the files below; this overrides orchestrator wording in CLAUDE.md.

Task: T58 (slice S-T3b) - parse, validate, normalise, cache write, provenance, adaptive, pipeline. RT2.
Repo/base: origin/main (git fetch).
Branch: claude/t58-dit-s-t3b-parse-store
Acceptance: AC-8-11, 12 (pipeline), 22.
Owned: tools/data-integration/src/data_integration/{parse,validate,normalise,store_writer,provenance,adaptive,pipeline}.py, tools/data-integration/tests/{test_parse,test_validate,test_normalise_roundtrip,test_provenance,test_adaptive,test_pipeline}.py, tools/data-integration/tests/fixtures/ (disjoint from S-T3a).
Read (only these):
 1. CLAUDE.md (13,443 B)
 2. the plan data-integration-tooling_PLAN_14-10-26.md lines 40-75 (Common, 6,060 B) and 126-137 (S-T3b, 2,468 B)
 3. tools/data-integration/src/data_integration/{types,status,paths}.py (2,182 B), gate.py lines 15-40 (918 B); tests/{_helpers,conftest}.py (2,352 B)
 4. api/data/cache.py lines 20-21 (119 B), 36 (82 B, OHLCV_COLUMNS, E3), 118-131 (546 B), 158-187 (1,243 B)
Read total: 29,413 B + this envelope (under 4,000 B) = under 33,500 B (cap 36,000 B).
Binding: pipeline takes any Fetcher (types.py); tests use a fake Fetcher and a FetchPass via request_access + _helpers.make_record, not S-T3a code. Write only via cache.write_ohlcv (replaces the series; refuse a non-empty key unless replace=True); columns exactly OHLCV_COLUMNS. Guard trap: parse.py is not on the import-boundary allow-list, so nothing of yours may import scrapling or a network module by AST-visible import; load Scrapling's Selector via importlib.import_module in a function (tests too); if guards still fail, needs_input (do not edit guards). Adaptive store path from paths.py (outside repo and site-packages); lost store gives uncertain.
Tests: red-first (record red count). BASELINE RULE: no hard-coded API total. Start with UV_FROZEN=1 uv run --project api pytest api/ -q on untouched origin/main; record exact counts (at least 1169 passed, 1 skipped, 5 deselected, all green; fewer or any failure stops at needs_input). After: passed = recorded baseline + your new CI-visible tests. Gates: UV_PROJECT_ENVIRONMENT=$HOME/.cache/dit-env uv run --project tools/data-integration pytest tools/data-integration/tests -q; UV_FROZEN=1 uv run --project api pytest api/tests/tooling_guards -q; UV_FROZEN=1 uv run --project api pytest api/ -q; git diff --exit-code api/uv.lock; git diff --check origin/main...HEAD. Avoid command text containing .venv, node_modules, dist, build.
Done when: suite green on head SHA; changed fixture gives changed and an empty cache dir.
Must NOT: edit api/data/cache.py; import fetch_tier*; write outside tmp_path; use the network.
After your report, stop; do not wait on CI or check in. needs_input means STOP: do NOT merge, do NOT open a new PR.
You never merge. Open one PR (draft) against main and stop. Cost is reported by the planner, not the worker. Spend cap 15 USD; ask at 7 USD (stop with needs_input). No secrets, keys, IPs or user names. Synthetic fixtures only; no live network (loopback fixture server only); never run npx, REA or any real scrape.
Forbidden: CLAUDE.md, AGENTS.md, .claude/, .mcp.json, .github/, deploy/, api/uv.lock, api/pyproject.toml, existing adapter/cache code (cache.py), process/MASTER-PLAN.md, process/context/decisions.md, S-T1/S-T2/S-T5a-owned files.
Retry budget: 2 fix cycles per gate; same failure twice stops. ASCII only.
Report: process/general-plans/active/data-integration-tooling_13-10-26/data-integration-tooling-s-t3b_REPORT_14-10-26.md
Report headings (11, in order): 1 Task ID, 2 Outcome, 3 Summary, 4 Files changed, 5 Commits, 6 Tests run (command, result, UTC, SHA), 7 Tests NOT run, 8 Deviations, 9 Blockers (MASTER-PLAN update requests go here), 10 Follow-up (decision requests, proposed tasks), 11 Context cost (extra docs opened).
Autonomy: edit Owned, run gates, push, draft PR.
