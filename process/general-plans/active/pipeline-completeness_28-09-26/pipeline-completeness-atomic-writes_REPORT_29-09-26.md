---
phase: pipeline-completeness-atomic-writes-execute
date: 2026-09-29
status: COMPLETE_WITH_GAPS
feature: none (general-plans, P1 lane)
plan: process/general-plans/active/pipeline-completeness_28-09-26/pipeline-completeness-atomic-writes_PLAN_29-09-26.md
---

# Atomic parquet writes — EXECUTE report

TL;DR: All 9 parquet writers in `api/data/cache.py` now go through `_atomic_to_parquet` (same-dir mkstemp temp → write → flush + fsync → chmod → `os.replace`; temp removed on any exception). There are 28 new offline tests, confirmed red before the change and green after. Full suite: 789 → 817 passed, 5 deselected. The real cache and watchlist were not modified. KG1–KG5 stay open; P2 AC12 is not fully met until KG5 (`etf_flows_adapter`) is fixed.

## What Was Done

- `api/data/cache.py`: added `import tempfile`; added `_atomic_to_parquet(df, path)` right after `_as_utc`, written exactly to D1 (EAFP mode lookup, `BaseException` cleanup, docstring free of the gated literals); swapped the 9 sites 1:1 (`write_ohlcv`, `write_liqtide_payload`, `write_liqtide_backfill`, `write_liquidity_series`, `write_confirmed_boundaries`, `write_narrative_point`, `write_trending_snapshot`, `write_exchange_point`, `merge_onchain_series`). All guards and mkdirs are untouched.
- `api/tests/data/test_cache_atomic_writes.py` (new, 28 tests): helper round-trip / interrupted / replace-failure / first-write / fsync-before-replace spy (A3) / mode handling / `test_no_bypass` / `test_isolation_canary`; parametrised interrupted-write tests for 8 writers plus the separate N7 liqtide-payload test; 9 round-trip tests (including liqtide no-overwrite and onchain no-write-when-unchanged with mtime/bytes check); AC(e) narrative and exchange interrupted-then-resumed tests.
- `.gitignore`: one comment and `api/data/cache/**/*.tmp`, placed after `!api/data/cache/onchain/` (line 30).

**File mode (D1):** a new file is written as 0o644. When a file already exists, its permission bits are copied, so a 0o600 file stays 0o600. This is a normalisation, not strict preservation: a plain path write would have produced `0666 & ~umask`. On Windows `chmod` only toggles the read-only bit.

**Scope (KG5):** only the writers in `cache.py` were made atomic. `etf_flows_adapter.merge_into_cache` still writes parquet non-atomically and was not touched, so P2 AC12 is NOT fully met.

## Test Gate Outcomes

| # | Gate | Result |
|---|---|---|
| 1 | Baseline `pytest api/ -q` | 789 passed, 5 deselected (matches expected) |
| 2 | Before snapshots (size+mtime, sha256) | 57 files; `watchlist.json` absent in the real repo |
| 3 | Red run on unmodified `cache.py` | 18 failed / 10 passed. All 9 writers red on real corruption (junk bytes, or DuckDB "too small to be a Parquet file"); liqtide red on `assert not True`; `test_no_bypass` `assert 9 == 1`; the 10 passes are round-trip and canary tests, as expected. Re-confirmed after the test fix below in a scratch copy with the HEAD `cache.py` |
| 4 | `grep -c '\.to_parquet('` / `grep -c '_atomic_to_parquet('` | 1 / 10 (checked after the docstring was written) |
| 5 | New test file | 28 passed |
| 6 | `SETUP    F isolated_cache` count vs collected | 28 == 28 |
| 7 | Full suite | 817 passed, 5 deselected, 0 failed (789 + 28) |
| 8 | After-snapshot diffs (txt + sha) | both empty |
| 9 | Throwaway-repo gitignore proof | 3 parquets staged, 0 temps; `check-ignore -v` → `.gitignore:30:api/data/cache/**/*.tmp` for the temps in `liqtide/` and `onchain/` |
| 10 | Scope guard | `git status` shows only `.gitignore`, `api/data/cache.py`, the new test file, and this report; `conftest.py` and `etf_flows_adapter.py` are unmodified |

## Plan Deviations

- None in the product code.
- Test-internal fix during EXECUTE: the first draft reset its interruption patches with `monkeypatch.undo()`. That also undid the `isolated_cache` redirect of `CACHE_ROOT`, so the read-back after the reset pointed at the real cache path. Those reads were read-only, and the only tests that would have written afterwards had already failed on an assertion. A mid-run snapshot diff proved the real cache was unchanged. The fix scopes the interruption patches in `pytest.MonkeyPatch.context()` blocks, and the gate 8 diff confirms the final run is clean. Lesson for future tests: never call `monkeypatch.undo()` in a test that depends on `isolated_cache`.
- Optional A3 fsync spy test added (the plan allowed it).

## What Was Skipped or Deferred

- KG1 (real power loss / SIGKILL), KG2 (Windows open reader), KG3 (`pairs_response` has no fsync), KG4 (JSON writers use a fixed temp name), KG5 (`etf_flows_adapter`): all recorded, not fixed.
- Plan step 9, the KG5 backlog stub, belongs to UPDATE PROCESS.

## Test Infra Gaps Found

- None new. Candidate from the plan still stands: a reusable interrupt-writer fixture if T21 unifies the writers.

## Closeout Packet

- Selected plan: `process/general-plans/active/pipeline-completeness_28-09-26/pipeline-completeness-atomic-writes_PLAN_29-09-26.md`
- Status: CODE DONE. VERIFIED still needs an independent vc-tester EVL run of gates 1–10.
- Classification: Keep in active/testing (pending EVL).
- Next: vc-tester EVL, then UPDATE PROCESS (KG5 backlog stub).

## Forward Preview

### Test Infra Found
- The interruption patches must be scoped with `pytest.MonkeyPatch.context()`; `monkeypatch.undo()` also clears `isolated_cache`.
### Blast Radius Changes
- None beyond the plan's 3 files.
### Commands to Stay Green
- `uv run --project api pytest api/tests/data/test_cache_atomic_writes.py -q`; `uv run --project api pytest api/ -q` (817 / 5).
### Dependency Changes
- None (stdlib `tempfile` only).
