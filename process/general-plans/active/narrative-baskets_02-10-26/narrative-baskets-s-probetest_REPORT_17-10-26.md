# T91 report: probe-records test hardening

## 1 Task ID
T91 (P5), branch claude/t91-fix-probe-records-test, base origin/main 48286e8.

## 2 Outcome
Done with a deviation (see 8): the named failing test no longer exists on base, and the full suite on untouched-equivalent base had 0 failures. Tests were still hardened so no data-dependent assertion on the shipped probe_records.json remains.

## 3 Summary
- `test_shipped_probe_records_empty` is not present on origin/main 48286e8 (`git grep` finds it only in the T89 wire-rest report). The registry test there is already `test_shipped_probe_records_are_well_formed`, which does not assert emptiness. Red-first could not be shown.
- test_registry.py: added tmp-fixture gate tests (empty records -> not-probed for every source; an ok record -> only that source usable; missing file already covered; unreadable/non-dict JSON -> not-probed) and replaced the shipped-file test with a stable contract (valid JSON, dict, keys in registry.FETCHERS, each record a dict with an allowed state, no secret/token/key/IP-looking strings). It never asserts emptiness.
- test_trends.py::test_not_probed_and_no_probe_row asserted `"trends" not in` the shipped records: a latent break if the daily job ever records trends. Now uses a tmp probe file.
- Other probe_records / attention-store references audited (test_discovery, routers/test_attention, test_fixpack_p5, analytics conftest, test_record_probe, workflow guard): they use tmp paths or monkeypatch PROBE_RECORDS_PATH, or only parse workflow text. No change needed. No test reads the committed attention parquet files. AC-25 tests untouched.
- Known limits: the contract's secret regex is a heuristic; suite order was not randomized (no random-order plugin installed), two identical-order runs only.

## 4 Files changed
api/tests/data/attention/test_registry.py, api/tests/data/attention/test_trends.py, this report.

## 5 Commits
One commit on the task branch (see PR).

## 6 Tests run
- `UV_FROZEN=1 uv run --project api pytest api/tests/data/attention -q`: 105 passed (2026-10-17 UTC).
- Baseline full suite on base plus in-flight test edits (edits landed mid-run, so not a clean baseline): 1455 passed, 1 skipped, 5 deselected, 0 failed. The expected failure did not reproduce.
- After, run 1: 1458 passed, 1 skipped, 5 deselected, 0 failed (164 s). Run 2: 1458 passed, 1 skipped, 5 deselected, 0 failed (173 s), finished 2026-10-17T20:42:17Z, SHA 48286e8 plus working-tree edits.
- Cache parquet files restored with `git checkout -- api/data/cache` after each run.

## 7 Tests NOT run
Random-order run (no plugin); clean untouched-base full run (contaminated as noted).

## 8 Deviations
The failing test named in the envelope is absent from base; red-first not demonstrable. Scope kept to test files.

## 9 Blockers
None.

## 10 Follow-up
Consider a random-order plugin in CI to catch order-dependence.

## 11 Context cost
About 45 KB read; well under cap.
