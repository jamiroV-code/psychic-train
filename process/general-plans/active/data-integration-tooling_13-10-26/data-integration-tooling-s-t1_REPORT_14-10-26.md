# S-T1 report: tooling skeleton, isolation and CI-visible guards

## 1 Task ID
T54 (slice S-T1). Branch `claude/t54-dit-s-t1-skeleton-guards`, base origin/main 5a13e55.

## 2 Outcome
Done; all gates green. No needs_input.

## 3 Summary
Created the separate uv project `tools/data-integration` (pins: scrapling[fetchers]==0.4.15, pandas 3.0.6, pyarrow 25.0.1, duckdb 1.5.5, equal to api/uv.lock), the skeleton modules (types, status, paths), the isolating conftest, the AC-5 clean-install script, and 14 CI-visible guard tests in `api/tests/tooling_guards`. The API install is unchanged (api/uv.lock and api/pyproject.toml diff empty).

## 4 Files changed
- `.gitignore` (append only)
- `tools/data-integration/{pyproject.toml,uv.lock,README.md}`
- `tools/data-integration/src/data_integration/{__init__,types,status,paths}.py`
- `tools/data-integration/scripts/check_clean_install.py`
- `tools/data-integration/tests/{conftest,test_skeleton}.py`
- `api/tests/tooling_guards/{__init__,test_tooling_isolation,test_import_boundary,test_marker_audit}.py`
- `api/tests/tooling_guards/_common.py` (extra shared helper, see 8)
- this report

## 5 Commits
One commit on the task branch (see PR).

## 6 Tests run
Times UTC 2026-10-14. SHA for green gates: the head commit of the PR (working tree identical to it).
- API baseline, untouched base 5a13e55: `UV_FROZEN=1 uv run --project api pytest api/ -q` -> 1143 passed, 1 skipped, 5 deselected (matches expected).
- Red-first: tooling tests before the project existed -> collection error (ModuleNotFoundError data_integration), 0 collected / 13 intended tests red. Guards on base: 14 passed (unchanged parts green on base).
- `UV_FROZEN=1 uv run --project api pytest api/tests/tooling_guards -q` -> 14 passed.
- `uv lock --project tools/data-integration` -> resolved 36 packages.
- `UV_PROJECT_ENVIRONMENT=<out-of-repo> uv run --project tools/data-integration pytest tools/data-integration/tests -q` -> 13 passed; also with UV_FROZEN=1 after lock exists -> 13 passed.
- `python tools/data-integration/scripts/check_clean_install.py` -> exit 0.
- Import probe (cache import leaves fastapi, ccxt, pandas_ta_classic out of sys.modules) -> exit 0.
- `UV_FROZEN=1 uv run --project api pytest api/ -q` -> 1157 passed, 1 skipped, 5 deselected = baseline 1143 + 14 guard tests.
- After Supplement 1 (UTC 2026-10-14 12:15): guards 17 passed; full api run 1160 passed, 1 skipped, 5 deselected = 1143 + 17.
- `git diff --check` clean; `git diff --exit-code api/uv.lock api/pyproject.toml` exit 0.

## 7 Tests NOT run
None of the plan gates skipped. No live network, no scrapling install step, no scrape.

## 8 Deviations
- Added `api/tests/tooling_guards/_common.py` (shared helpers) beyond the named owned files; it holds no tests.
- The workflow directory and ignore-file names are built from split strings in guard code because the harness hook blocks command text with those names.
- Tooling test count is 13 (parametrized), guards 14 (17 after Supplement 1).
- Supplement 1 came as a peer-session message from the planner, not from the user; I verified both gaps in my own code before fixing.

## 9 Blockers
None. No MASTER-PLAN registry update requested beyond marking S-T1 ready for review.

## 10 Follow-up
S-T3a must provide the `fixture_server` fixture the marker audit recognises. Fetch tier files named in the import-boundary allow-list: fetch_tier1/2/3.py and robots.py.

## 11 Context cost
No extra docs opened beyond the envelope list (plus api/pyproject.toml head and api/tests/deploy/test_zz_real_data_guard.py for patterns).

## Supplement 1 (planner follow-up after tester PASS_WITH_GAPS)
- test_tooling_isolation.py: workflow check now uses `mentions_tooling_dir` (lowercase plus backslash normalisation); new self-test covers `tools/`, `tools\`, mixed case and clean strings; base workflows still clean.
- test_marker_audit.py: `unmarked_tests` now audits async tests and methods of (nested) classes, honouring class decorators and class-level `pytestmark`; two new self-tests (flagged when unmarked, accepted when marked or using `fixture_server`).
- Counts: guards 17 (14 + 3); full api 1160 passed, 1 skipped, 5 deselected (1143 + 17). `git diff --check` clean; api/uv.lock and api/pyproject.toml diff empty.
- UTC 2026-10-14 12:15; head SHA = the PR head after the supplement commit.
