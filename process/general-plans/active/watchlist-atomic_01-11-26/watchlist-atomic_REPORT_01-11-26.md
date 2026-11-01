# watchlist-atomic — REPORT (01-11-26)

## 1. Goal
Make `api/data/watchlist.py::_save_raw` crash-safe so a failure mid-write cannot truncate the owner's gitignored watchlist.json.

## 2. Scope delivered
`_save_raw` now writes a unique temp in the same dir, fsyncs, chmod 0644, `os.replace`; temp unlinked on any exception. Output format unchanged (indent=2 + trailing newline, text mode, same key order).

## 3. Helper decision
`cache._atomic_write_json` writes compact JSON (`separators=(",", ":")`, no newline) — format differs, so per envelope a small local helper following the same pattern was written; cache.py untouched (PR #213 owns it).

## 4. Files changed
- api/data/watchlist.py
- api/tests/data/test_watchlist_atomic_save.py (new)
- this task folder (contract + report)

## 5. Red-first evidence (before)
Commit "test(watchlist): red …" on plain main code: `2 failed, 2 passed` —
json.dump failure left file as `b'{"coins": ['` (truncated); os.replace patch "DID NOT RAISE" (in-place write never used it).

## 6. After evidence
Same 4 tests pass. Broad run (api/tests/data, routers test_watchlist/screener/layout/baskets, api/tests/deploy): `1 failed, 1620 passed, 4 skipped`.
The 1 failure, test_equities_store::test_path_override_honoured_at_call_time, is a Windows path-separator assertion (`endswith('api/data/equities.json')` against a backslash path) unrelated to this change; Linux CI is the judge.

## 7. Behaviours preserved
Parent dir created; missing file loads as {'coins': []} (tested); no example-file fallback added; cap / 409 / lock untouched.

## 8. Not changed / follow-ups (after #213 merges)
- api/analytics/pairs_response spreads.tmp write path
- lse_adapter non-atomic writes
- Optionally unify on one cache helper taking a formatting arg.

## 9. Unproven
Real power-loss durability (directory fsync not done, matching the cache.py pattern; on Windows not possible via os API). Simulated failures only.

## 10. Verification commands
`UV_FROZEN=1 uv run --project api pytest api/tests/data/test_watchlist_atomic_save.py api/tests/data/test_watchlist_store.py api/tests/routers/test_watchlist.py`

## 11. Status
Draft PR open; worktree C:/Users/jamir/.herdr/worktrees/my_site/wt-watchlist-atomic retained.
