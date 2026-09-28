---
name: report:pytrends-partial-hour-fix-closeout
description: "UPDATE PROCESS closeout for the pytrends isPartial-hour bug fix"
date: 28-09-26
metadata:
  node_type: memory
  type: report
  feature: narrative-mindshare
  phase: UPDATE-PROCESS
---

# Pytrends Partial-Hour Zeros Fix — UPDATE PROCESS Closeout

**Status: COMPLETE. Selected plan path:**
`process/features/narrative-mindshare/completed/pytrends-partial-hour-fix_28-09-26/pytrends-partial-hour-fix_PLAN_28-09-26.md`

## Root cause

`api/data/pytrends_adapter.py::_fetch_live` took `df.iloc[-1]` of Google Trends' hourly `"now 7-d"`
`interest_over_time()` frame with no `isPartial` filtering. The last row is frequently Google's
still-accumulating current hour, which is often 0 or heavily under-counted. Because Google Trends
keeps no history, each affected night's real value was permanently and unrecoverably lost.
Confirmed real damage: `memecoins` and `RWA` categories wrote 0.0 on every nightly snapshot since
09-24/09-26; only `ai` got real nonzero values.

## Fix

`_fetch_live` now drops `isPartial=True` rows before selecting the last point (4-line change,
`api/data/pytrends_adapter.py` lines 66-69), reusing the exact pattern already proven in
`api/scripts/backfill_pytrends_history.py::daily_points`. Returns `(None, None)` when no complete
row survives the filter, so `fetch_trend`'s existing `unavailable`/`presumed-dead` handling takes
over instead of writing a fabricated 0. Behavior is byte-identical to pre-fix when no `isPartial`
column is present at all. Signature and both call sites (`fetch_trend`,
`snapshot_narrative.py::snapshot_pytrends`) are unchanged by design.

New test file `api/tests/data/test_pytrends_adapter.py` (3 tests, synthetic `pandas.DataFrame`
fixtures via `sys.modules` injection of a fake `pytrends.request` module — `pytrends` is confirmed
not installed in the `api` env and not a declared dependency).

## Test evidence

- Baseline (`git log` `af1f558`, pre-fix on this branch): `uv run --project api pytest api/ -q` →
  **623 passed, 5 deselected**.
- Post-fix (`git log` `d186a08`): `uv run --project api pytest api/ -q` → **626 passed, 5
  deselected** — exactly +3 new tests, zero regressions.
- `uv run --project api pytest api/tests/data/test_pytrends_adapter.py -v` → 3/3 passed,
  independently confirmed as the EVL gate re-run (not just execute-agent's own claim).
- `git diff api/data/pytrends_adapter.py` independently re-confirmed AC-5 (no
  `cache.write_narrative_point`/`read_narrative_series`/migration touch — diff is confined to the
  4-line row-selection block) and AC-6 (signature `def _fetch_live(keyword: str) -> tuple[float |
  None, str | None]:` and both call sites unchanged).

## SPEC Achievement

All 6 acceptance criteria in `pytrends-partial-hour-fix_SPEC_28-09-26.md` — **met**:

| AC | Criterion | Status |
|---|---|---|
| AC-1 | never returns Google's incomplete-hour value | met — `test_fetch_live_drops_partial_hour_row` |
| AC-2 | all-partial → `(None, None)` → falls to unavailable/presumed-dead | met — `test_fetch_live_all_rows_partial_returns_none` |
| AC-3 | no `isPartial` column → unchanged behavior | met — `test_fetch_live_no_ispartial_column_unchanged` |
| AC-4 | no regression to existing consumers | met — full suite 626/5, zero regressions |
| AC-5 | no retroactive cache correction | met — diff review (Agent-Probe) |
| AC-6 | no interference with `narrative-v2` RFC-3 | met — diff review (Agent-Probe) |

No Known Gaps. `closeout_classification: CLEAN` (EVL HANDOFF SUMMARY, orchestrator).

## Scope independence from `narrative-v2`

`narrative-v2` (`process/features/narrative-mindshare/active/narrative-v2_25-09-26/`) is a
separate, currently-executing plan (RFC-1 in progress). This fix's touchpoints are confined to
`api/data/pytrends_adapter.py` (+ one new test file) — confirmed by direct read of
`narrative-v2_PLAN_25-09-26.md`'s RFC-3 design before this fix started (RFC-3 is NOT STARTED,
blocked behind RFC-2, and will add a new *additive* batched-fetch function later — it does not
touch `_fetch_live`'s internals). Zero file overlap; no merge-conflict risk identified.

## Cleanup performed this session

- Task folder archived: `active/pytrends-partial-hour-fix_28-09-26/` →
  `completed/pytrends-partial-hour-fix_28-09-26/`.
- Originating backlog note `process/general-plans/backlog/pytrends-partial-hour-zeros_NOTE_27-09-26.md`
  Finding 1 marked RESOLVED, pointing at this task folder. Finding 2 (09-25 gap) already closed by
  the cron-timing fix.
- `process/context/all-context.md` updated: new "Changes Since Last Update" entry (newest-first),
  Open Question struck through and marked resolved, References + Scan Metadata amended.
- `process/context/data-sources/all-data-sources.md`, `process/context/planning/all-planning.md`:
  reviewed, no change needed (neither describes the isPartial bug or fix specifics).
- `process/context/tests/all-tests.md`: reviewed, intentionally NOT updated. Its per-feature test
  count table tracks EVL milestones for other in-flight work (`narrative-v2`); this fix's own
  before/after count (623→626) is recorded in the plan's validate-contract and in this closeout
  note, and will be folded into `narrative-v2`'s own eventual UPDATE PROCESS count entry rather than
  creating a conflicting interim row here.

## Commit

Already committed on branch `claude/vigilant-hamilton-grr18c` (SPEC `15b1104`, PLAN `af1f558`,
validate-contract `a1a966f`, code fix `d186a08`), pushed to origin. This UPDATE PROCESS session's
archival/context changes are a separate process-only commit (plan/report/backlog/context files
only, no source files).

**Status:** DONE
