# S-T3a report: tier-1 fetch, robots, politeness, logs, response cache, fixture server

## 1 Task ID
T57 (slice S-T3a), branch claude/t57-dit-s-t3a-tier1-fetch

## 2 Outcome
Done. Tooling suite and guards green on head; full API suite green (see 6). Draft PR opened; not merged.

## 3 Summary
- fetch_tier1.fetch(url, pass_): needs a real FetchPass (isinstance), checks permits() on the URL and every redirect hop, builds the client only afterwards (counter clients_built() proves zero clients on refusal), robots per hop, never raises, maps to the closed status set.
- robots.py: RobotsChecker; robots fetch needs a pass and a listed host, shares the client (UA, politeness, logging), fails closed (timeout, unreachable, 5xx, unparsable). 404/410 = no robots file = allow.
- politeness.py: per-host min delay (reservation based, injectable clock and sleeper), global and per-host concurrency, honest UA without contact data.
- logging_setup.py: one line per request (host, path, status, duration_ms, tier); query, fragment, control characters dropped; IP literals redacted.
- response_cache.py: only OK responses cached; hit returns cache_hit with zero requests; refresh=True makes one request; corrupt entries read as a miss.
- Fixture server: loopback port 0, plain-HTTP forward proxy; tests fetch http://example.test/... and the client uses scrapling Fetcher.get(proxy=...) (verified in the tooling env, scrapling 0.4.15). Gate unchanged.
- Finding: scrapling logs full URLs including query strings; fetch_tier1 sets the "scrapling" logger to CRITICAL so only our sanitised line is emitted (test covers it).

## 4 Files changed
src/data_integration/{fetch_tier1,robots,politeness,logging_setup,response_cache}.py; tests/{fixture_server,plugin_fixture_server,test_fetch_tier1,test_robots,test_politeness,test_logging,test_response_cache}.py; this report. No api/ change, conftest untouched.

## 5 Commits
See PR branch (one code commit plus report commit).

## 6 Tests run (command, result, UTC, SHA)
- Baseline, untouched origin/main (worktree): UV_FROZEN=1 uv run --project api pytest api/ -q: 1169 passed, 1 skipped, 5 deselected, 2 warnings.
- Red-first: 5 new test modules, 5 collection errors (modules missing) before implementation.
- Tooling: 193 passed (same count before the final marker-audit arg tweak and after).
- tooling_guards on head: 26 passed (one earlier failure, marker audit, fixed by taking fixture_server in three tests).
- Full API on head (75a2bd2 plus report): UV_FROZEN=1 uv run --project api pytest api/ -q: 1169 passed, 1 skipped, 5 deselected (equals baseline; tooling tests live under tools/, not api/, so 0 new CI-visible tests).
- Date 2026-10-14 UTC.

## 7 Tests NOT run
No live-network, browser or antibot tests (none exist in this slice).

## 8 Deviations
- First baseline attempt was contaminated (new test files already present, and one run used the wrong environment); discarded and rerun cleanly on an origin/main worktree.
- Three tests take the unused fixture_server argument only to satisfy the marker audit.

## 9 Blockers
None.

## 10 Follow-up
S-T4 can reuse tests/plugin_fixture_server.py (fixture_server with .proxy_url, .requests, .paths(host), .count). Unlisted routes: /data/{ok,slow,500,429,challenge,redirect-same,redirect-other,redirect-unlisted,redirect-loop}; robots by host (robots-disallow.test, robots-500.test, robots-garbage.test, robots-hang.test).

## 11 Context cost
Extra files opened beyond the envelope: api/tests/tooling_guards/test_marker_audit.py and test_import_boundary.py (audit rules), approvals.py signatures, test_gate.py header.
