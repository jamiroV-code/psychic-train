# T51 equities catch-up fix - report

## Outcome
done (draft PR, not merged)

## Summary
The worker treated a ticker as current when its newest bar was dated the due session, even if that bar was a still-forming one fetched before the session's bar was due, so no catch-up ran after a missed close. `_behind` now also marks a ticker behind when its bar date equals the session but the cache's fetched_at is before `bar_due_at(session)` (close + 60 min), or the fetch time is missing/unreadable. The same check drives schedule_first (catch-up 20 s after start) and run_tick's 3 x 30 min retry. New optional `fetched_at` hook on EquitiesRefreshWorker: default reads the sidecar via `lse_adapter.cached_fetched_at`; when only `bar_date` is injected (existing tests) the fetch-time check is off, so existing tests are unchanged. Start-up after a missed tick already runs via schedule_first's 20 s catch-up; no extra change needed.

## Files
- api/data/equities_refresh.py (_behind rule, fetched_at hook)
- api/data/equities_calendar.py (public bar_due_at helper, additions only)
- api/data/lse_adapter.py (public cached_fetched_at accessor, additions only)
- api/tests/data/test_equities_catchup.py (7 new tests)

## Tests run with SHA/UTC
Base origin/main bd14de8, run 2026-10-13 UTC, UV_FROZEN=1 uv run --project api pytest:
- catchup + refresh_worker: 21 passed; calendar + refresh: 24 passed
- full api/: 1134 passed, 1 skipped, 5 deselected (baseline 1127 + 7 new)
- git diff --check clean; added lines ASCII-only; web untouched

## Deviations
None. Default fetched_at for bar_date-only injection disables the check (keeps existing fakes compatible).

## Blockers
None.
