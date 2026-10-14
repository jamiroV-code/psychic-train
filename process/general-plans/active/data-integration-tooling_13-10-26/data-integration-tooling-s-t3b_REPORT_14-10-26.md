# S-T3b Report

## 1 Task ID
T58 (slice S-T3b), branch claude/t58-dit-s-t3b-parse-store

## 2 Outcome
done. All gates green; draft PR opened.

## 3 Summary
Added parse, validate, normalise, store_writer, provenance, adaptive and pipeline modules plus six test files and synthetic fixtures. Verified in the tooling env that `from scrapling.parser import Selector` is valid for scrapling 0.4.15 and loads no curl_cffi, playwright, patchright, scrapling.fetchers or scrapling.engines. Pipeline: pass check, fetch (any Fetcher), parse, validate, adaptive, normalise, write via cache.write_ohlcv, provenance. First run with no baseline returns `uncertain` and writes nothing unless `accept_baseline=True`; the baseline is saved only after a successful write. A moved table with a baseline gives `changed` (cache dir stays empty); unchanged re-run gives `cache_hit` with no new provenance record; non-empty key gives `refused` unless `replace=True`.

## 4 Files changed
- tools/data-integration/src/data_integration/{parse,validate,normalise,store_writer,provenance,adaptive,pipeline}.py (new)
- tools/data-integration/tests/{test_parse,test_validate,test_normalise_roundtrip,test_provenance,test_adaptive,test_pipeline}.py (new), tests/fixtures/*.html (6, new)
- api/tests/tooling_guards/test_import_boundary.py (extend; see 8)

## 5 Commits
7bd1ca8 feat(data-integration): S-T3b ... (report commit follows)

## 6 Tests run
- Red first: tooling pytest with new tests on missing modules: 6 collection errors (6 files), 0 collected.
- Baseline, untouched origin/main (clean worktree): `UV_FROZEN=1 uv run --project api pytest api/ -q` = 1169 passed, 1 skipped, 5 deselected. (An earlier run in the working tree showed 1 failure because my new parse.py landed mid-run; discarded.)
- Tooling suite: 191 passed (head 7bd1ca8).
- Guards: `pytest api/tests/tooling_guards -q` 38 passed.
- Full API on head: 1181 passed, 1 skipped, 5 deselected = baseline 1169 + 12 new guard tests.
- `git diff --exit-code api/uv.lock` clean; `git diff --check origin/main...HEAD` clean.

## 7 Tests NOT run
Browser/antibot markers, live network, real scrape (not in scope).

## 8 Deviations
The existing `test_only_fetch_tiers_import_network_modules` body changed by one line: it now calls the new file-aware `flagged_imports(path.name, source)` instead of the inline scan, because parse.py/adaptive.py must be exempt for `scrapling.parser`; it cannot stay byte-identical and pass. Its assertion and the other S-T1 tests are unchanged. curl_cffi and patchright were added to NETWORK_ROOTS. Allow-list uses a dot boundary (`scrapling.parser` or `scrapling.parser.*`). Pipeline signature is keyword-only `run(fetcher, pass_, *, url, selector, symbol, timeframe, ...)`.

## 9 Blockers
None. No MASTER-PLAN update requests.

## 10 Follow-up
Decision request: first-run baseline needs `accept_baseline=True` (owner-explicit); confirm this is the wanted UX for S-T4 CLI wiring.

## 11 Context cost
No extra docs beyond the envelope list; read gate.py lines 1-14 and 40-70 and approvals.py ApprovalStore (small) to build the test FetchPass.
