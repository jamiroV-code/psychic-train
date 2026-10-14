# T63 (S-T3c) report

## 1 Task ID
T63 (S-T3c), branch claude/t63-dit-s-t3c-provenance-hardening, base origin/main (c2b9052).

## 2 Outcome
done. F1-F4 implemented; all gates green. PR is draft; not merged.

## 3 Summary
- F1: FetchOutcome.body_sha256 (set in fetch_tier1 for OK and in ResponseCache for cache hits); FetchPass gains approval_id, approval_revision, approved, expires set by request_access (token and immutability unchanged); parse.PARSER_VERSION='dit-parse-1'; provenance.build_record adds response_sha256, scrapling_version (importlib.metadata.version), parser_version, approved, expires, approval_id, approval_revision; pipeline passes outcome hash (computes sha256 of body if a custom fetcher left it None).
- F2: test asserts no Referer and only the fixed User-Agent on the wire (page and robots). Hand mutation stealthy_headers=True made it fail (Referer present); reverted, not committed.
- F3: robots body cap 512 KiB (ROBOTS_MAX_BYTES, "robots too large" fails closed -> robots_blocked); page cap max_body_bytes default 5 MiB -> http_error "body too large".
- F4: ResponseCache key = sha256(tier + URL), tier stored in metadata and checked on read; ResponseCache(root, tier=1).

## 4 Files changed
src/data_integration/{types,gate,parse,provenance,pipeline,response_cache,robots,fetch_tier1}.py; new tests/test_provenance_completeness.py (9 tests); this report.

## 5 Commits
One commit on the task branch (see PR).

## 6 Tests run (command, result, UTC, SHA)
Base SHA c2b9052, all run 2026-10-14 UTC:
- Baseline origin/main: api/ 1184 passed, 1 skipped, 5 deselected; tooling 253 passed; tooling_guards 41 passed.
- Red-first: new test file against untouched src: collection error (PARSER_VERSION import), 0 of 9 pass. After fix, an interim run showed 3 test-side fixture errors, fixed in the test file only.
- After: tooling 262 passed (253 + 9 new CI-visible); tooling_guards 41 passed; api/ 1184 passed, 1 skipped, 5 deselected (tooling tests are not in api/); lock/pyproject diff clean; git diff --check clean.

## 7 Tests NOT run
Browser/antibot/integration markers (deselected); no real scrape.

## 8 Deviations (files touched outside tests and why)
- Source files above, per Owned list only. No forbidden file touched.
- Too-large page status: status.py is not owned and has no too_large entry, so http_error with detail "body too large" is used (closed set unchanged).
- Cap is enforced after the client returns the body (Scrapling buffers the whole response); it bounds what is parsed, hashed and cached, not peak memory of the read.
- New test file defines its own loopback server fixture named fixture_server because the tooling_guards marker audit requires that fixture name; the shared fixture_server.py was not edited.
- ResponseCache default tier is 1; Tier-2 callers must pass tier=2.

## 9 Blockers
none. No MASTER-PLAN requests.

## 10 Follow-up
Streamed capped read if a tier ever needs hard memory bound; add too_large to status.py in a task that owns it.

## 11 Context cost (extra docs opened)
None beyond the listed set (also read tests/test_fetch_tier1.py, test_provenance.py, fixture_server.py, conftest.py heads, status.py, and the marker-audit guard for the failure).

## Follow-up 1
Note: PR #76 (head f89642d) was already merged by the owner at 16:31:32Z, before this follow-up arrived. Per the merged-PR rule the branch was restarted from origin/main (2dc383d) and the follow-up is a new PR, not #76.

Changes:
- F-B: fetch_tier1 refuses (status refused, "response cache tier does not match the pass tier") when cache.tier != pass_.tier, before any cache read or client build. Cache reads and writes therefore always use the pass tier.
- F-C: tests added for a legacy old-format cache key (miss, no error), robots body exactly at 512 KiB accepted and cap+1 failing closed, tier-1 pass with tier-2 cache refused with zero clients and zero requests, and a tier-2 pass (via request_access) never reading tier-1 entries.
- F-A (docs only): comments on DEFAULT_MAX_BODY_BYTES and ROBOTS_MAX_BYTES. Known limit for the docs slice: "The size caps are checked after the client has returned the whole body, so they protect parsing and caching but not the download itself; the client timeout bounds time."
- F-D untouched.

Tests (UTC 2026-10-14T16:42Z, base 2dc383d): red-first, the 2 tier tests failed on pre-change source (others pass because they pin existing behaviour). tooling 266 passed (262 + 4); tooling_guards 41; api/ 1184 passed, 1 skipped, 5 deselected; lock/pyproject diff clean. Head SHA: see PR.
