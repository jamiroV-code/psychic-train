ROLE: WORKER
You are a WORKER: direct lane. Do not orchestrate or spawn sessions/subagents; load only the files below.

Task: T63 (S-T3c) - provenance completeness and fetch hardening. Fix task from wave 3 tester findings. RT2.
Repo/base: origin/main.
Branch: claude/t63-dit-s-t3c-provenance-hardening
Acceptance: DIT-3, AC-10, AC-22 (F1); F2-F4.
Owned (this task only, minimal edits; existing tests changed only for new fields, never weakened): tools/data-integration/src/data_integration/{types,gate,fetch_tier1,robots,response_cache,provenance,pipeline,parse}.py, existing tests, new tools/data-integration/tests/test_provenance_completeness.py.
Read (only these; line ranges under src/data_integration/):
 1. CLAUDE.md (13,443 B)
 2. types.py, fetch_tier1.py, response_cache.py, provenance.py (whole: 579+5,778+1,411+1,944 B); gate.py 17-40 and 60-90 (2,205 B); robots.py 14-62 (1,758 B); pipeline.py 56-76 (1,151 B); parse.py 1-16 (382 B); approvals.py 51-74 (494 B); tests/_helpers.py (908 B)
Read total: 30,053 B + envelope (under 4,500 B) = under 34,600 B.
Scope (binding):
 F1 provenance.build_record also stores response_sha256 (sha256 hex of raw body bytes, computed in fetch_tier1, carried in FetchOutcome via new field body_sha256: str | None = None in types.py), scrapling_version (importlib.metadata.version('scrapling'); NOT import_module/__import__), parser_version (constant PARSER_VERSION='dit-parse-1' in parse.py), and approval facts. FetchPass keeps its private token and behaviour; gains approval_id (= record.id, e.g. source-20261014), approval_revision (int), approved, expires (= record.expiry), set by request_access from the record. Provenance copies source, allowed tier, approved, expires, approval_id, approval_revision; pipeline passes them through. Provenance stays a separate append-only file surviving cache.write_ohlcv. Tests: new fields present and typed; response_sha256 == sha256 of fixture body; approval facts equal fixture record; request_access FetchPass carries them; gate tests unchanged.
 F2 test: outgoing request has NO Referer header and only the fixed honest User-Agent. By hand (uncommitted): stealthy_headers=True must make it fail.
 F3 size caps: robots.txt body 512 KiB, page body configurable (default 5 MiB), read with a cap in fetch_tier1/robots; over cap gives the closed bad/too-large status (robots too large fails closed). Tests: oversized robots, oversized page.
 F4 response_cache key includes tier and URL; test same URL at tier 1 and tier 2 does not collide.
Tests: red-first (record red count). BASELINE RULE: run UV_FROZEN=1 uv run --project api pytest api/ -q on untouched origin/main: expect >=1184 passed, 1 skipped, 5 deselected, all green; tooling suite 253 passed; tooling_guards 41 passed; fewer or any failure stops at needs_input. After: baseline + your new CI-visible tests (state it).
Gates: UV_PROJECT_ENVIRONMENT=$HOME/.cache/dit-env uv run --project tools/data-integration pytest tools/data-integration/tests -q (new count; base 253); UV_FROZEN=1 uv run --project api pytest api/tests/tooling_guards -q (baseline 41); UV_FROZEN=1 uv run --project api pytest api/ -q; git diff --exit-code api/uv.lock api/pyproject.toml; git diff --check origin/main...HEAD. Avoid command text with .venv, node_modules, dist, build.
Done when: gates green; F1-F4 tests pass.
needs_input means STOP: do NOT merge, do NOT open a new PR. After your report, stop; do not wait on CI or check in.
You never merge. Open one PR (draft) against main and stop. Cost is reported by the planner, not the worker. Spend cap 15 USD; ask at 7 USD (stop, needs_input). No secrets, keys, IPs or user names. Synthetic fixtures only; loopback fixture server only; never run npx, REA or any real scrape.
Forbidden: approvals.py, approval_cli.py, rea/*, api/, guard files, api/data/cache.py, CLAUDE.md, AGENTS.md, .claude/, .mcp.json, .github/, deploy/, api/uv.lock, api/pyproject.toml, process/MASTER-PLAN.md, process/context/decisions.md.
Retry: 2 fix cycles per gate; repeat stops.
Report: process/general-plans/active/data-integration-tooling_13-10-26/data-integration-tooling-s-t3c_REPORT_14-10-26.md
Headings (11, in order): 1 Task ID, 2 Outcome, 3 Summary, 4 Files changed, 5 Commits, 6 Tests run (command, result, UTC, SHA), 7 Tests NOT run, 8 Deviations (list every file touched outside tests and why), 9 Blockers (MASTER-PLAN requests here), 10 Follow-up, 11 Context cost (extra docs opened).
Autonomy: edit Owned, run gates, push, draft PR.
