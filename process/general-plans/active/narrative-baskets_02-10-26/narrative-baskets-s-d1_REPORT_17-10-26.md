# T79 (P5 S-D1) report

## 1 Task ID
T79, P5 S-D1, branch claude/t79-p5-s-d1-decouple.

## 2 Outcome
done. Draft PR open against main, not merged.

## 3 Summary
- history.py owns MIN_AVAILABLE_SOURCES (2), BASE_TRUST_WEIGHT (0.6), REDUCED_SOURCE_TRUST_CAP (0.4); no trigger import.
- seed_e2e_cache.py build_narrative_fixture reads narrative_categories.json via a local helper.
- scoring.py docstring only; test_history.py and test_seed_narrative_fixture.py stop reading trigger.
- Test that scanned trigger.py text rewritten to the new fact (screener_board does not import history).
- New tests: no trigger/momentum import in history.py and the seed script, local constants, /history composite point field set pinned (incl. trust_weight).
- Known limits:
  - Composite trust_weight is KEPT, not dropped: routers/narrative.py:97 reads it and NarrativeCompositePoint requires it (both forbidden). Planner decision (option 2) via cross-session message; /history JSON unchanged.
  - Only routers/narrative.py and files D2 deletes still import trigger/momentum.

## 4 Files changed
api/analytics/narrative/history.py, api/analytics/narrative/scoring.py, api/scripts/seed_e2e_cache.py, api/tests/analytics/test_history.py, api/tests/scripts/test_seed_narrative_fixture.py, this report.

## 5 Commits
- fb7a810 red tests
- fe40a6f decouple (green)
- report commit on top

## 6 Tests run
- Baseline, untouched origin/main (clean worktree): UV_FROZEN=1 uv run --project api pytest api/ -q -> 1402 passed, 1 skipped, 5 deselected.
- After D1 (SHA fe40a6f, 2026-10-17T08:44:36Z): same cmd -> 1406 passed, 1 skipped, 5 deselected (baseline + 4 new tests).
- Red count at fb7a810: 4 failed (3 in test_history.py, 1 in test_seed_narrative_fixture.py).
- Protected AC-25 tests: git diff --stat origin/main empty, green in the full run.
- git diff --check origin/main...HEAD: clean. Forbidden-file diff: empty.
- Real cache api/data/cache (216 lines of size/mtime/sha256): identical before and after.
- Spend: not metered in session; well under the 7 USD ask line.

## 7 Tests NOT run
vitest and e2e (web untouched); git diff origin/main -- web is empty.

## 8 Deviations
- A first baseline attempt (-x) ran on a tree with the new tests already edited in; discarded, baseline re-measured in a clean worktree.
- Envelope said drop composite trust_weight; planner overrode to keep it (see 3).

## 9 Blockers
None now. Earlier needs_input on the trust_weight consumer was resolved by the planner.

## 10 Follow-up
- trust_weight in the composite is now a history-owned value that duplicates trigger semantics; owner/planner decides later whether to remove it (needs router + models + web check).
- coingecko_adapter.py docstring still mentions trigger.py (out of scope, comment only).

## 11 Context cost
CLAUDE.md, envelope, plan lines 23-32/74-79, and the capped code ranges; within the 36,000 B cap.
