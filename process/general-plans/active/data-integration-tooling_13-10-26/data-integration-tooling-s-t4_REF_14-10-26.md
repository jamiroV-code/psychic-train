ROLE: WORKER
You are a WORKER: direct lane. Do not orchestrate or spawn subagents; load only the files below.

Task: T59 (slice S-T4) - tiers 2 and 3 (DynamicFetcher/StealthyFetcher wrappers), robots before navigation. RT2.
Repo/base: origin/main (git fetch).
Branch: claude/t59-dit-s-t4-browser-antibot-tiers
Acceptance: AC-6 (tiers 2, 3), AC-16, AC-17 (owner probe scripts), tier-3 parts of AC-3, AC-13.
Owned: tools/data-integration/src/data_integration/{fetch_tier2,fetch_tier3}.py, tools/data-integration/tests/{test_tier2_browser,test_tier3_gating,test_tier23_robots}.py, tools/data-integration/tests/fixtures/js_page/*, tools/data-integration/scripts/{probe_tier1,probe_tier2}.py, tools/data-integration/README.md (append a probe section only), and ONE extend-only edit of tools/data-integration/tests/fixture_server.py (new routes for js_page and block-style pages: challenge text, 403, captcha marker; existing routes unchanged).
Read (only these):
 1. CLAUDE.md (13,443 B)
 2. plan data-integration-tooling_PLAN_14-10-26.md lines 40-75 (Common, 6,060 B) and 138-149 (S-T4, 2,405 B)
 3. tools/data-integration/src/data_integration/types.py (579 B); gate.py lines 15-62 (1,728 B); robots.py lines 17-22 and 64-100 (917 B); fetch_tier1.py lines 81-100 (1,175 B)
 4. tools/data-integration/tests/fixture_server.py lines 40-123 (3,029 B); tests/_helpers.py (908 B; conftest.py is autouse, not read)
Read total 30,244 B + this envelope (under 5,200 B) = under 35,500 B, cap 36,000 B.
Statuses: only the closed set in status.py.
STEP 0 (first): probe whether the cloud Chromium (PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers) can serve the tier-2 fixture test. NEVER run `playwright install` or `scrapling install`. Record VIABLE / NOT-VIABLE / INCONCLUSIVE in report heading 3. If not VIABLE, tier-2 tests stay stub-navigator based and the real-browser proof is the owner's AC-17 script; mark real-browser tests `browser`.
Binding: tier 2 needs FetchPass with allowed_tier >= 2, permits(url) and a redirect check; tier 3 passes options through only when allowed_tier == 3. The robots check runs BEFORE any navigation on tiers 2 and 3 (AC-6): zero navigations when disallowed, unreachable or unparsable (stub navigator counts calls). Block-style fixture pages map to challenge_page. Tier 3 honest scope: approval gating, block-style mapping, option pass-through; NOT proven against any real protected site; no real challenge-solving in tests; no bypass claim. Tests reuse fixture_server (E4) with a stub navigator so they run in the default suite; the marker audit needs the fixture_server fixture or a browser/antibot marker on tests importing fetch_tier*. The import-boundary guard allow-list already names fetch_tier2.py, fetch_tier3.py and robots.py as the only files allowed network/browser imports. Probe scripts make their own temp approval record, call paths._repo_root(); probe_tier1: loopback fetch/parse/store into a temp cache, prints PASS/FAIL; probe_tier2: same with a JS page, prints download-size hints and timing.
Tests: red-first (record red count). BASELINE RULE: no hard-coded API total. Start with UV_FROZEN=1 uv run --project api pytest api/ -q on untouched origin/main; record exact counts (at least the last known true total, 1169 passed, 1 skipped, 5 deselected, all green; may be higher after supplements; fewer or any failure stops at needs_input). After: passed = baseline + new CI-visible tests. Gates: UV_PROJECT_ENVIRONMENT=$HOME/.cache/dit-env uv run --project tools/data-integration pytest tools/data-integration/tests -q; UV_FROZEN=1 uv run --project api pytest api/tests/tooling_guards -q; UV_FROZEN=1 uv run --project api pytest api/ -q; git diff --exit-code api/uv.lock; git diff --check origin/main...HEAD. Avoid command text containing .venv, node_modules, dist, build.
Done when: default suite green on head SHA; browser/antibot tests green or unverified; probe_tier1 PASS.
Must NOT: run playwright install, scrapling install, npx, REA or any real scrape; claim tier-3 effectiveness; edit S-T3 modules or guards (need a change -> needs_input); write outside tmp_path.
After your report, stop; do not wait on CI or check in. needs_input means STOP: do NOT merge, do NOT open a new PR.
You never merge. Open one PR (draft) against main and stop. Cost is reported by the planner, not the worker. Spend cap 15 USD; ask at 7 USD (needs_input). No secrets, keys, IPs or user names. Synthetic fixtures only; no live network (loopback only).
Forbidden: CLAUDE.md, AGENTS.md, .claude/, .mcp.json, .github/, deploy/, api/uv.lock, api/pyproject.toml, api/data/cache.py, guard files, process/MASTER-PLAN.md, process/context/*, other slices' files (except the edit above).
Retry: 2 fix cycles per gate; same failure twice stops. ASCII only.
Report: process/general-plans/active/data-integration-tooling_13-10-26/data-integration-tooling-s-t4_REPORT_14-10-26.md
Report headings (11, in order): 1 Task ID, 2 Outcome, 3 Summary, 4 Files changed, 5 Commits, 6 Tests run (command, result, UTC, SHA), 7 Tests NOT run, 8 Deviations, 9 Blockers (MASTER-PLAN update requests), 10 Follow-up, 11 Context cost (extra docs opened).
Autonomy: edit Owned, run gates, push, draft PR.
