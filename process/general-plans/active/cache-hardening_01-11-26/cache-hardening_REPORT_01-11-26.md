# cache-hardening report (01-11-26)

## 1 Task ID
cache-hardening (backlog notes: pipeline-cache-hardening-followups_NOTE_01-10-26, pipeline-etf-flows-atomic-write_NOTE_29-09-26, ohlcv-negative-cache-and-1d-gap-replace_NOTE_04-10-26). Branch `claude/cache-hardening`, worktree `C:/Users/jamir/.herdr/worktrees/my_site/wt-cache-hardening`, draft PR #213.

## 2 Outcome
done (the three open atomic-write items are fixed; the other items were checked and are already handled or need an owner decision, as the table shows)

## 3 Summary
Each note item was checked against origin/main e1394b80:

| Item | State on e1394b80 (evidence) | Action |
|---|---|---|
| KG3 pairs_response fsync | OPEN: `pairs_response.py:134-137` (fixed `.tmp`, no fsync), `:174-176` spread files, `:182-184` results | FIXED: all three go through `cache._atomic_to_parquet` / `cache._atomic_write_bytes`; local helper removed |
| KG4 fixed temp name in cache.py JSON writers | OPEN: `cache.py:349-351` (`write_liqtide_raw`), `:529-531` (`write_exchange_market_snapshot`) | FIXED: new `cache._atomic_write_bytes` (same pattern as `_atomic_to_parquet`); `_atomic_write_json` delegates to it; bytes unchanged |
| KG5 etf_flows merge non-atomic | OPEN: `etf_flows_adapter.py:110` `merged.to_parquet(path)` | FIXED: `cache._atomic_to_parquet(merged, path)` |
| SQ1 watchlist loader fallback | DOES NOT APPLY as worded: `watchlist.py:89-91` returns `{"coins": []}`; there is no fallback. The real open question (pipeline-completeness PLAN line 345) is whether to ADD one | Not built: owner decision. Adding it would show example coins as if they were the user's |
| D7 failed OHLCV fetch not negatively cached | MOSTLY ADDRESSED by S8: reads are cache-only while the worker runs (`refresh_worker.py:449-451`, `ccxt_adapter.py:547-549`); failed pairs are skipped until the next backoff-aware tick (`refresh_worker.py:127-130,292,339`). Residual: with `SCREENER_REFRESH_WORKER=0`, `ccxt_adapter.py:597-603` still retries on every request | Not built: the residual only exists with the worker off, and the TTL is a decision |
| D18 non-contiguous 1d tail keeps history | OPEN, unchanged: `ccxt_adapter.py:632-635` (`gap-kept`). The note says "Needs a decision" | Not built: owner decision (backfill or surface `note`). History is never shortened |

## 4 Files changed
- `api/data/cache.py`: new `_atomic_write_bytes`; `_atomic_write_json` delegates to it; both JSON archive writers use it.
- `api/data/etf_flows_adapter.py`: `merge_into_cache` writes atomically; docstring updated.
- `api/analytics/cointegration/pairs_response.py`: results, provenance and spread writes use cache.py helpers; local `_atomic_write_bytes` deleted.
- Tests: `api/tests/data/test_cache_atomic_writes.py` (8 new: bytes unchanged, foreign temp untouched, fsync before replace, replace failure leaves nothing, each run for both writers), `api/tests/data/test_etf_flows_adapter.py` (interrupted merge keeps the prior cache), `api/tests/scripts/test_compute_pairs.py` (5 fsyncs, foreign fixed-name temps untouched).
- Notes: the three backlog notes got status lines; this folder holds the CONTRACT and this REPORT.

## 5 Commits
`claude/cache-hardening`: d1c6e324 (red tests), 8c211c0f (fix), 56ad3d48 (backlog notes), plus the commit that adds this report.

## 6 Tests run
All runs were local on Windows, with `UV_FROZEN=1 uv run --project api pytest ... -q -p no:cacheprovider`, on 2026-11-01:
- Red, on e1394b80 code with the new tests: `test_cache_atomic_writes.py test_etf_flows_adapter.py tests/scripts/test_compute_pairs.py` gave 8 failed, 61 passed, 1 skipped. Exactly the new KG3/KG4/KG5 tests failed; the bytes-unchanged guards passed.
- Green, at 8c211c0f: the same files plus `test_liqtide_raw_archive.py` and `tests/analytics/test_exchange_attention.py` gave 95 passed, 1 skipped.
- Broad, at 8c211c0f: `api/tests/data api/tests/analytics tests/scripts/test_compute_pairs.py tests/scripts/test_seed_pairs_fixture.py tests/routers/test_pairs.py tests/routers/test_regime_components.py` gave 2213 passed, 2 failed, 2 skipped. Both failures are host-only:
  - `test_universe_classes::test_discovery_end_to_end_on_fixture` is the known no-network guard failure.
  - `test_equities_store::test_path_override_honoured_at_call_time` fails because it asserts a `/` path separator on Windows. My diff does not touch equities.
- Linux CI on PR #213: see the PR checks (the final result reports their state).

## 7 Tests NOT run
- The full `api/tests/routers` suite, because ~40 tests fail on this host on plain main. Linux CI is the judge.
- Web tests: no web files changed.
- KG1 (real power loss, directory fsync) and KG2 (Windows `os.replace` with an open reader) are not proven. No live PC probes were run.

## 8 Deviations
- KG5: I used the existing private `cache._atomic_to_parquet`, which `lse_adapter.py` and `attention/store.py` already call from other modules. I did not add the public helper the note suggests. Owner may request a public rename across all callers.
- KG3: each spread file is now fsynced inside the staging dir. The staging dir keeps its fixed name `spreads.tmp`, so two concurrent compute runs could still collide on it. Out of the note's scope; see Follow-up.

## 9 Blockers
None. Open owner decisions: SQ1 (add a watchlist fallback?), D18 (accept the 1d hole, backfill it, or surface `note`), D7 residual (negative cache when the worker is off: is it wanted, and with what TTL?).

## 10 Follow-up
- `api/data/watchlist.py:98-102` `_save_raw` writes the user's watchlist in place (non-atomic, and the data is not in git). Suggest routing it through the same helper pattern.
- Give the `pairs_response` staging dir a unique name (for example `mkdtemp`) if concurrent compute runs become possible: the worker's recompute and `compute_pairs.py` could overlap.
- `lse_adapter.py:238` has its own copy of the mkstemp/fsync sidecar logic and could use `cache._atomic_write_bytes`.

## 11 Context cost
I read three backlog notes, `cache.py` (helper and writer ranges), `etf_flows_adapter.py:1-118`, `pairs_response.py:1-203`, `watchlist.py`, `ccxt_adapter.py:509-643`, `refresh_worker.py:1-203`, three test files and master-planner.md headings. About 60k tokens. Tools: read, grep, bash, edit, write.
