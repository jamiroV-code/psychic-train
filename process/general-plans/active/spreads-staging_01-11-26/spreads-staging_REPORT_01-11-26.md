# spreads-staging report (01-11-26)

## 1 Task ID
spreads-staging (KG3 follow-up from `process/general-plans/backlog/pipeline-cache-hardening-followups_NOTE_01-10-26.md` and `process/general-plans/active/cache-hardening_01-11-26/cache-hardening_REPORT_01-11-26.md` §10). Branch `claude/pairs-spreads-staging` from origin/main c69d1b2f. Worktree `C:/Users/jamir/.herdr/worktrees/my_site/wt-spreads-staging` (left in place). Draft PR #221.

## 2 Outcome
done. Linux CI is green on PR #221 (see §6).

## 3 Summary
`compute_and_persist` staged spreads in a fixed `pairs/spreads.tmp` dir. On c69d1b2f a second run's `rmtree(staging)` deleted the first run's staged files, and a mid-staging failure left `spreads.tmp` behind. Now:
- Each run stages in its own dir `pairs/spreads.tmp.<uuid4 hex>` (same parent). It is created with `Path.mkdir()` instead of `tempfile.mkdtemp`, because `mkdtemp` creates mode 0o700 on POSIX and the renamed `spreads/` dir would keep that mode. Permissions stay as before.
- Swap (`_swap_into_place`): the current `spreads/` is renamed aside to a unique `spreads.tmp.old.<hex>`, the staging dir is renamed to `spreads/`, and the aside dir is removed. If an overlapping run's dir lands in between, the rename fails and is retried (5 attempts). The last run to swap wins with its complete set. This is still two renames, not atomic. A directory cannot be replaced in one rename on Windows, nor on POSIX when the target is non-empty. Readers can briefly see no `spreads/` dir, the same gap as the old `rmtree` + `os.replace`. One difference: the old dir is no longer partly deleted before the rename. It is moved aside whole.
- Any failure during staging or the swap removes this run's staging dir (`try/finally`) and re-raises. The previous `spreads/` stays intact when the failure happens during staging.
- At the start of a run, `spreads.tmp*` dirs whose mtime is more than 1 hour old are removed. This covers the legacy fixed `spreads.tmp`, crashed `spreads.tmp.<hex>` dirs, and leftover `.old.` dirs. A live run's staging dir has a fresh mtime and is never touched.
- Unchanged: output files and formats, the provenance-first-invalidation order, and the `cache.py` helpers.

## 4 Files changed
- `api/analytics/cointegration/pairs_response.py`: `_STAGING_PREFIX`, `_STALE_STAGING_AGE_S`, `_SWAP_ATTEMPTS`, `_sweep_stale_staging`, `_swap_into_place`; spreads block in `compute_and_persist` rewritten.
- `api/tests/scripts/test_compute_pairs.py`: 3 new tests (overlapping runs, failure mid-staging, stale sweep vs live dir); the existing no-leftover test also asserts no `spreads.tmp*`.
- `process/general-plans/backlog/pipeline-cache-hardening-followups_NOTE_01-10-26.md`: status line.
- This report.

## 5 Commits
`claude/pairs-spreads-staging`: 9a24e8e4 (red tests), daba7617 (fix + note status), the report commit, plus the commit that records the CI result here.

## 6 Tests run
All runs were local on Windows, with `uv run --project api pytest ... -q -p no:cacheprovider`, on 2026-11-01:
- Red, at 9a24e8e4 (old code): `test_compute_pairs.py` gave 3 failed. The overlap test failed with `PermissionError(13)` plus `BrokenBarrierError`. The failure test found `spreads.tmp` left behind. The stale test found `spreads.tmp.crashed` still present. A first version of the overlap test passed on the old code, because both runs wrote identical bytes into the shared dir. It was strengthened before commit: run B's spreads are shifted, and each run checks that its staged bytes are unchanged.
- Green, at the fix: `test_compute_pairs.py` gave 22 passed. The 3 new tests were run 8 more times in a row and passed every time.
- Broad: `tests/scripts/test_compute_pairs.py tests/scripts/test_seed_pairs_fixture.py tests/routers/test_pairs.py tests/data/test_cache_pairs_helpers.py api/tests/analytics api/tests/data` gave 2260 passed, 2 failed, 3 skipped. Both failures are known host-only failures: `test_universe_classes::test_discovery_end_to_end_on_fixture` (no-network guard) and `test_equities_store::test_path_override_honoured_at_call_time` (`/` separator on Windows).
- Linux CI on draft PR #221 (run 41326700557, at the report commit): `api — pytest` passed (4m47s) and `web — vitest, tsc, island build` passed (37s).

## 7 Tests NOT run
- The full `api/tests/routers` suite, because ~40 tests fail on this host on plain main. Linux CI is the judge.
- Web tests: no web files changed.
- Real cross-process overlap (two `compute_pairs.py` processes): not run. The test uses two threads in one process, with forced interleaving. The swap-retry path's exact interleaving is OS-scheduled, so the test does not prove every ordering.
- Windows rename-aside while a reader holds a spread file open: not proven. It raises after 5 attempts, and `spreads/` is left as it was.

## 8 Deviations
- I used `Path.mkdir()` with a uuid4 name instead of `tempfile.mkdtemp`, to keep the dir mode (see §3).
- Stale `.old.` aside dirs also use the `spreads.tmp` prefix, so the same sweep cleans them after a crash.

## 9 Blockers
None.

## 10 Follow-up
- A real cross-process lock would remove the swap race entirely, if overlapping runs ever become common. Not needed for correctness now: the last swap wins with a complete set.
- `results.parquet` and `provenance.json` from overlapping runs are each written atomically, but the run that wins them may differ from the run that wins `spreads/`. With the same cache inputs the contents match. This was not in scope.

## 11 Context cost
I read `pairs_response.py:1-223`, `test_compute_pairs.py`, the cache-hardening report, the backlog note, and grep results for `spreads.tmp` and `compute_and_persist`. About 35k tokens. Tools: read, grep, glob, bash, edit, write.
