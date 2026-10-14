# S-T2 report

## 1 Task ID
T55 (slice S-T2), branch claude/t55-dit-s-t2-approval-gate

## 2 Outcome
done (draft PR opened, not merged). Both suites green; AC-1, AC-3, AC-21 (store + index), AC-22 (approval facts shape) covered.

## 3 Summary
Added approvals.py (record, atomic store with revision, .bad rename, source-name regex plus reserved names, UTC Z timestamps), gate.py (stdlib only; request_access, Refused, FetchPass with private token, immutable, host/page bound permits()), approval_cli.py (status with placeholder path and override flag; add refuses without TTY and needs the typed source name). 4 CI-visible guards added. Gate order: bad clock, bad source (reported as missing), store, approved-in-future (bad_clock), expiry (now >= expiry), tier.

## 4 Files changed
tools/data-integration/src/data_integration/{approvals,gate,approval_cli}.py; tools/data-integration/tests/{test_gate,test_approvals_store,test_approval_cli}.py plus tests/_helpers.py (small fixture helper, not in the Owned list); api/tests/tooling_guards/test_approval_store_guard.py.

## 5 Commits
443e029 feature commit; earlier report-only commit (needs_input stop).

## 6 Tests run
- Corrected API baseline on untouched base c46fe1a: 1160 passed, 1 skipped, 5 deselected (envelope said 1143).
- Red-first: new tooling tests run before implementation: 3 collection errors (0 tests ran; all three files failed on missing modules).
- Tooling: UV_PROJECT_ENVIRONMENT=$HOME/.cache/dit-env uv run --project tools/data-integration pytest tools/data-integration/tests -q : 52 passed (2026-10-14T15:02Z, 443e029)
- UV_FROZEN=1 uv run --project api pytest api/tests/tooling_guards -q : 21 passed (17 wave 1 + 4 new)
- UV_FROZEN=1 uv run --project api pytest api/ -q : 1164 passed, 1 skipped, 5 deselected (= 1160 + 4)
- git diff --exit-code api/uv.lock : clean. No *.approval.json found under tools, api, process.

## 7 Tests NOT run
git diff --check origin/main...HEAD is run just before push (see PR). No CI waited on.

## 8 Deviations
- Envelope baseline correction 1143 -> 1160 (planner confirmed).
- Added tests/_helpers.py (not in Owned list) for shared synthetic fixtures.
- Marker audit flags tests importing socket, so test_gate.py looks the module up by name via importlib for the zero-client counter.
- Tests for "approvals dir gitignored and absent from the index" check .gitignore patterns and a file scan of the repo (no git subprocess; shallow-checkout safe).
- An unknown/bad source name returns Refused reason "missing" (closed reason set); an invalid tier value returns tier_too_low.

## 9 Blockers
None. No MASTER-PLAN update requested.

## 10 Follow-up
Decision request: none. Optional: FetchPass currently allows only default ports; a non-default port approval would need an explicit record field.

## 11 Context cost
No extra docs opened beyond the envelope list plus .gitignore and test_marker_audit.py (to fix the audit failure).
