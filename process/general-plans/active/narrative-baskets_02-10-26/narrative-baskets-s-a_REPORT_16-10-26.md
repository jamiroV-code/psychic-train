# T68 (P5 S-A) report: baskets view over screener groups

## 1 Task ID
T68, P5 S-A. Branch claude/t68-p5-s-a-baskets, base origin/main ae9c095.

## 2 Outcome
Done (draft PR, not merged). ACs AC-35, AC-32, AC-27, AC-9 covered by pytest.

## 3 Summary
- `api/data/baskets_view.py`: pure `baskets`, `unassigned`, `basket_of` (group `main` = Unassigned).
- GET `/api/narrative/baskets` and POST `/api/narrative/baskets/{group_id}/coins` (move/unassign; membership 404 before any write; 422 for bad id, symbol, extra field; 404 unknown group).
- `DELETE /api/watchlist/{symbol}` now returns `affected_baskets` (new `RemoveCoinResponse`; GET/POST shapes unchanged). `add_coin` pins a NEW coin without `group_id` to `main` when a saved layout has `main` (best effort, logged).
- Known limits: `basket` in the move response is null when the target is `main` (plan said "names, null from Unassigned"; applied to both fields). `affected_baskets` has at most one name. If the layout read fails on delete it is `[]`. A layout without `main` leaves new coins in the last group (D-1 defect 2 stays; E warns). No revision check on a move (stale UI gets the next 409).

## 4 Files changed
api/data/baskets_view.py, api/models/baskets.py, api/routers/baskets.py, api/routers/watchlist.py, api/main.py (include_router + import), tests: api/tests/data/test_baskets_view.py, api/tests/routers/test_baskets.py, test_watchlist_cascade.py, one assertion in test_watchlist.py::test_remove_coin; this report.

## 5 Commits
10a72e2 red tests; 382a787 implementation; report commit follows on the same branch.

## 6 Tests run
- Baseline on untouched origin/main: `UV_FROZEN=1 uv run --project api pytest api/ -q` = 1204 passed, 1 skipped, 5 deselected.
- Red (commit 10a72e2): 23 failed, 10 passed (accidental 404/422 on missing route), plus 1 collection error (test_baskets_view.py, 4 tests uncollected). Red count 23 failed + 1 collection error.
- After (SHA 382a787, 2026-10-16T19:37Z): same command = 1236 passed, 1 skipped, 5 deselected (baseline 1204 + 32 new tests). Protected tests are inside this run, green; `git diff --stat origin/main --` on them empty.
- `git diff --check origin/main...HEAD` clean; forbidden paths diff empty.
- Real files: api/data/watchlist.json and layout.json absent before and after; api/data/cache tree (108 files) size/mtime/sha256 digest identical before and after.
- Spend: under 1 USD estimated (no provider calls).

## 7 Tests NOT run
vitest, Playwright e2e (web untouched; `git diff origin/main -- web` is empty). No CI waited on.

## 8 Deviations
None from Owned/Forbidden. First commit has no attribution trailer.

## 9 Blockers
None.

## 10 Follow-up
Slice E: warn that deleting a group moves its coins to the last group. Planner to confirm `basket: null` for unassign.

## 11 Context cost
About 33 KB of the 36,000 B cap read (CLAUDE.md, plan ranges, code ranges, test heads). Extra opened: test_watchlist.py lines 30-50, api/models/layout.py head (30 lines), watchlist.py SYMBOL_RE lines, conftest grep.
