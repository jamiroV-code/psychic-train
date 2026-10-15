ROLE: WORKER
Direct lane: no spawning; load only files below.

Task: T59 (S-T4) - tiers 2/3 (DynamicFetcher/StealthyFetcher wrappers), robots before navigation. RT2.
Base origin/main. Branch: claude/t59-dit-s-t4-browser-antibot-tiers
Acceptance: AC-6 (tiers 2, 3), AC-16, AC-17 (owner scripts), tier-3 parts of AC-3, AC-13.
Owned (under tools/data-integration/): src/data_integration/{fetch_tier2,fetch_tier3}.py; tests/{test_tier2_browser,test_tier3_gating,test_tier23_robots}.py; tests/fixtures/js_page/*; scripts/{probe_tier1,probe_tier2}.py; README.md (append a probe section only); ONE extend-only edit of tests/fixture_server.py (ADD routes only: js page, block pages with challenge text, 403, captcha marker; never change existing behaviour).
Read (paths under tools/data-integration/):
 1. CLAUDE.md (13,443 B)
 2. plan PLAN_14-10-26.md lines 138-149 (2,405 B)
 3. src/data_integration/: fetch_tier1.py 33-138 (5,248); robots.py 19-86 (2,657); gate.py 25-45 (1,071); politeness.py 1-22 (862); types.py (614); status.py (620)
 4. tests/fixture_server.py 40-123 (3,029)
Read total 29,949 B; with envelope < 34,600 B.
Unread: ResponseCache(root, tier=1): .tier, put(url,status,body), get(url); tests/_helpers.py: NOW, fixed_clock(), make_record(source, tier); request_access(source, tier, store, clock).
STEP 0 (first): probe whether the cloud Chromium (PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers) can serve the tier-2 fixture test. NEVER run `playwright install`/`scrapling install`. Record VIABLE / NOT-VIABLE / INCONCLUSIVE in report heading 3. If not VIABLE, tests stay stub-navigator based; real-browser proof is the owner's AC-17 script; mark real-browser tests `browser`.
Binding, reuse fetch_tier1 shapes: FetchOutcome (body_sha256), FetchPass (approval_id/revision/approved/expires), size caps (limit: checked after the client returns the whole body), ResponseCache tier == pass tier (mismatch refused), politeness, structured logging, closed statuses. Tier 2: allowed_tier >= 2, permits(url), redirect check. Tier 3 passes options through only when allowed_tier == 3. Robots check BEFORE any navigation (AC-6): zero navigations (stub navigator counts) when disallowed, unreachable or unparsable. Block-style pages map to challenge_page. Tier 3 scope: gating, block-page mapping, option pass-through; NOT proven against any real protected site; never invoke real challenge solving; no bypass claim. The import-boundary guard allows network/browser imports only in fetch_tier2.py, fetch_tier3.py, robots.py. Markers browser/antibot are deselected by default; tests importing fetch_tier* need the fixture_server fixture or a marker.
Probes: temp approval record; paths._repo_root(); probe_tier1 loopback fetch/parse/store to a temp cache, prints PASS/FAIL; probe_tier2 same with the JS page, prints size hints and timing.
Red-first (record red count); plain test functions; ASCII. BASELINE RULE: on untouched origin/main run UV_FROZEN=1 uv run --project api pytest api/ -q: expect at least 1184 passed, 1 skipped, 5 deselected, green; tooling 266; tooling_guards 41; fewer or any failure: needs_input. After: baseline + new CI-visible tests (state it).
Gates: UV_PROJECT_ENVIRONMENT=$HOME/.cache/dit-env uv run --project tools/data-integration pytest tools/data-integration/tests -q; UV_FROZEN=1 uv run --project api pytest api/tests/tooling_guards -q; UV_FROZEN=1 uv run --project api pytest api/ -q; git diff --exit-code api/uv.lock api/pyproject.toml; git diff --check origin/main...HEAD. Avoid command text with .venv, node_modules, dist, build.
Done: default suite green; probe_tier1 PASS.
Must NOT: run playwright install, scrapling install, npx, REA or any real scrape; claim tier-3 effectiveness; edit other S-T modules or guards (-> needs_input); write outside tmp_path.
Forbidden: CLAUDE.md, AGENTS.md, .claude/, .mcp.json, .github/, deploy/, api/, process/MASTER-PLAN.md, process/context/*.
After your report stop; do not wait on CI. needs_input means STOP: no merge, no new PR. Never merge; open one draft PR against main and stop.  Cap 15 USD; ask at 7 (needs_input). No secrets, keys, IPs, user names. Synthetic fixtures; loopback only. 2 fix cycles per gate.
Report: process/general-plans/active/data-integration-tooling_13-10-26/data-integration-tooling-s-t4_REPORT_14-10-26.md
Headings (11): 1 Task ID, 2 Outcome, 3 Summary, 4 Files changed, 5 Commits, 6 Tests run (cmd, result, UTC, SHA), 7 Tests NOT run, 8 Deviations, 9 Blockers, 10 Follow-up, 11 Context cost.
