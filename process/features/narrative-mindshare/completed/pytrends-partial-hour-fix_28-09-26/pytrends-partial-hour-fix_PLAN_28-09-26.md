---
name: plan:pytrends-partial-hour-fix
description: "Drop isPartial=True rows in pytrends_adapter._fetch_live before picking the last point, so the nightly narrative snapshot never archives Google's incomplete current hour as a real value"
date: 28-09-26
feature: narrative-mindshare
---

# Pytrends Partial-Hour Zeros — PLAN (SIMPLE)

**Date**: 28-09-26
**Status**: COMPLETE — EXECUTE + EVL confirmed clean (626/5 deselected, +3 new tests, 0
regressions), archived via UPDATE PROCESS 28-09-26
**Complexity**: SIMPLE

Locked SPEC: `pytrends-partial-hour-fix_28-09-26/pytrends-partial-hour-fix_SPEC_28-09-26.md`
(same task folder). This plan implements that SPEC's 6 acceptance criteria exactly; it does not
restate or re-derive them — see the SPEC for the full narrative/flow diagram.

## Overview

`api/data/pytrends_adapter.py::_fetch_live` currently takes `df.iloc[-1]` of Google Trends' hourly
`"now 7-d"` frame with no filtering for `isPartial`. Google's current, still-accumulating hour is
frequently 0 or heavily under-counted, and because Google Trends keeps no history, a bad nightly
read is permanently lost. The fix: drop `isPartial=True` rows before selecting the most recent
point, reusing the exact pattern already proven in `backfill_pytrends_history.py::daily_points`
(`work = work[~partial]`). If no complete row remains, return `(None, None)` so the existing
`unavailable` / `presumed-dead` fallback in `fetch_trend` takes over — never write a fabricated 0.

## Goals

- Stop `_fetch_live` from ever returning Google's incomplete current-hour value.
- Preserve `_fetch_live`'s exact signature and every call site (`fetch_trend`,
  `snapshot_narrative.py::snapshot_pytrends`) — required by SPEC AC-6 for `narrative-v2` RFC-3
  non-interference.
- Add first-ever direct unit coverage of `_fetch_live`'s row-selection logic (currently zero).
- Leave all already-archived cache data untouched (SPEC AC-5).

## Scope

In scope: `api/data/pytrends_adapter.py::_fetch_live` internals only, plus one new test file.

Out of scope (verbatim from SPEC): `narrative-v2` RFC-1–RFC-7; the already-closed 09-25 cron-timing
gap; retroactively correcting archived zero points; switching to a daily-aggregate value instead of
an hourly point; `trigger.py`'s separately-tracked keying bug; any change to
`backfill_pytrends_history.py`; any `/narrative` UI/API/router change.

## Touchpoints

| File | Change |
|---|---|
| `api/data/pytrends_adapter.py` | Modify `_fetch_live` (lines ~50-74): drop `isPartial=True` rows before `df.iloc[-1]`; return `(None, None)` if nothing remains. No other function in this file changes. |
| `api/tests/data/test_pytrends_adapter.py` | New file. 3 required unit tests (see Acceptance Criteria mapping below) using synthetic `pandas.DataFrame` fixtures — no live network, no `pytrends` package import needed (tests exercise `_fetch_live`'s post-`interest_over_time()` logic by monkeypatching `TrendReq`, matching the pattern used for `pytrends`-adjacent tests elsewhere in this repo — see Implementation Checklist step 2 for the exact monkeypatch shape). |

No other files are touched. `api/tests/scripts/test_snapshot_narrative.py` is explicitly NOT
modified (SPEC Constraint) — it already mocks `_fetch_live`'s return value directly.

## Public Contracts

- `_fetch_live(keyword: str) -> tuple[float | None, str | None]` — signature unchanged.
- `fetch_trend(keyword: str) -> TrendResult` — unchanged, calls `_fetch_live` exactly as before.
- `TrendResult` dataclass — unchanged.
- No change to `cache.write_narrative_point`, `cache.read_narrative_series`, or any on-disk cache
  schema/format.
- This is a private internal-behavior fix. No new public surface is introduced.

## Blast Radius

- 1 modified source file (`api/data/pytrends_adapter.py`), 1 new test file. No schema, auth, API,
  or billing surface. No new dependency. Single phase (not a phase program) — INNOVATE-recommended
  strategy: sequential, signal score 0/7.
- Risk class: none of the High-Risk Classes (auth/billing/schema-migration/public-API/deploy/secrets)
  apply. This is a pure internal data-quality fix inside one already-isolated adapter module.

## Non-Interference / Constraints (carried forward from SPEC — do not deviate)

- Must NOT change `_fetch_live`'s signature or its call sites.
- Must NOT require live network access to test; use synthetic DataFrame fixtures only.
- Must NOT modify `api/tests/scripts/test_snapshot_narrative.py`.
- Must NOT touch `cache.write_narrative_point()`, `cache.read_narrative_series()`/
  `read_narrative_history`, or any file under `api/data/cache/narrative/`.
- Must NOT conflict with `narrative-v2` RFC-3 (not started, blocked behind RFC-2) — RFC-3 will add a
  new additive batched-fetch function to this same file later; this fix only touches `_fetch_live`'s
  internal row-selection, so no future merge conflict of concern.

## Implementation Checklist

1. **Read current `_fetch_live` in full** (`api/data/pytrends_adapter.py:50-74`) — confirm no drift
   from the version read during RESEARCH/SPEC (lines 50-74, `df.iloc[-1]` at line 66).

2. **Modify `_fetch_live`** in `api/data/pytrends_adapter.py`, inside the existing `try:` block right
   after the `df is None or df.empty or keyword not in df.columns` early-return check (currently line
   64-65) and before `last = df.iloc[-1]` (currently line 66):
   ```
   if "isPartial" in df.columns:
       df = df[~df["isPartial"].astype(bool)]
       if df.empty:
           return None, None
   last = df.iloc[-1]
   value = float(last[keyword])
   as_of = df.index[-1].strftime("%Y-%m-%d")
   return value, as_of
   ```
   - Pattern matches `backfill_pytrends_history.py::daily_points` lines 107-110 (`if "isPartial" in
     work.columns: ... work = work[~partial]`) — same column-presence guard, same boolean-mask drop.
   - The `if "isPartial" in df.columns` guard is what satisfies SPEC AC-3 (no-column case: unchanged
     behavior — falls straight through to `last = df.iloc[-1]` exactly as today).
   - The nested `if df.empty: return None, None` guard (post-filter) is what satisfies SPEC AC-2
     (all-partial case).
   - Do not touch the `MAX_RETRIES` loop, the `except Exception` handling, or anything outside this
     one `try` block's row-selection lines.
   - No change to imports, module docstring, dataclass, or any other function in the file.

3. **Create `api/tests/data/` directory if it does not already exist**, then create
   `api/tests/data/test_pytrends_adapter.py` with these 3 tests. Follow this repo's existing pytest
   conventions (see `api/tests/scripts/test_snapshot_narrative.py` for style/monkeypatch idioms).
   Use `unittest.mock.patch` (or `monkeypatch`) to replace `pytrends.request.TrendReq` inside
   `_fetch_live`'s local import so no real network call or `pytrends` package install is required —
   patch at the import site (`from pytrends.request import TrendReq` executes inside the function
   body, so patch `sys.modules["pytrends.request"]` or patch the module attribute before calling, per
   this repo's existing pattern for mocking function-local imports — confirm the exact mechanism
   against `test_snapshot_narrative.py`'s own `_fetch_live` mocking, which patches
   `pytrends_adapter._fetch_live` directly at the `fetch_trend` call boundary; for this new file,
   since the test targets `_fetch_live` itself, patch `pytrends.request.TrendReq` via
   `monkeypatch.setitem(sys.modules, "pytrends.request", fake_module)` or equivalent — pick the
   simplest correct mechanism that does not require the real `pytrends` package to be installed).

   **VALIDATE-confirmed (28-09-26): `pytrends` is genuinely NOT installed in the `api` env**
   (`uv run python -c "import pytrends"` → `ModuleNotFoundError`) and is NOT listed in
   `api/pyproject.toml` (confirmed by direct grep — matches the module docstring's own claim that
   it's deliberately not a hard dependency). This means patching an attribute on the real
   `pytrends.request` module is not possible — it does not exist to patch. The
   `monkeypatch.setitem(sys.modules, "pytrends.request", fake_module)` injection path is therefore
   not a fallback, it is the only viable mechanism, and execute-agent should use it directly rather
   than trying the "patch the module attribute" branch first.

   - `test_fetch_live_drops_partial_hour_row`: build a synthetic `pd.DataFrame` with a
     `DatetimeIndex`, an `isPartial` column, and the target keyword column. Last row
     `isPartial=True` with value `0`; second-to-last row `isPartial=False` with a real nonzero value
     (e.g. `42.0`). Mock `TrendReq.interest_over_time()` to return this frame. Assert `_fetch_live`
     returns `(42.0, <second-to-last row's date>)`, NOT `(0.0, <last row's date>)`.
   - `test_fetch_live_all_rows_partial_returns_none`: same shape, but every row has `isPartial=True`.
     Assert `_fetch_live` returns `(None, None)`.
   - `test_fetch_live_no_ispartial_column_unchanged`: same shape but with NO `isPartial` column at
     all. Assert `_fetch_live` returns the value/date from the actual last row (`df.iloc[-1]`) —
     i.e. today's exact pre-fix behavior, unchanged.

4. **Run the new test file in isolation** to confirm all 3 pass:
   `uv run --project api pytest api/tests/data/test_pytrends_adapter.py -v`

5. **Run the full regression suite** to confirm SPEC AC-4 (no regression to
   `test_snapshot_narrative.py`, `trigger.py`, or `/narrative` consumers):
   `uv run --project api pytest api/ -q` (deselects `integration`-marked tests per this repo's
   default `addopts`, per `process/context/tests/all-tests.md`).

6. **Diff review for AC-5 and AC-6** (Agent-Probe strategy, no automated test exists for these):
   run `git diff api/data/pytrends_adapter.py` and confirm:
   - (AC-5) no line touches `cache.write_narrative_point`, `cache.read_narrative_series`, or any
     cache read/write/migration code — the diff is confined to `_fetch_live`'s row-selection block.
   - (AC-6) `_fetch_live`'s signature (`def _fetch_live(keyword: str) -> tuple[float | None, str |
     None]:`) is unchanged, and no call site (`fetch_trend`, `snapshot_narrative.py`) was touched.

## Acceptance Criteria (mapped 1:1 to SPEC)

| SPEC AC | Plan step that satisfies it | Verification |
|---|---|---|
| AC-1: never returns incomplete-hour value | Step 2 (isPartial drop before `iloc[-1]`) | `test_fetch_live_drops_partial_hour_row` |
| AC-2: all-partial → `(None, None)` → falls to `unavailable`/`presumed-dead` | Step 2 (post-filter empty guard) | `test_fetch_live_all_rows_partial_returns_none` |
| AC-3: no `isPartial` column → unchanged behavior | Step 2 (`if "isPartial" in df.columns` guard) | `test_fetch_live_no_ispartial_column_unchanged` |
| AC-4: no regression to existing consumers | Step 5 | `pytest api/ -q` full green, `test_snapshot_narrative.py` unmodified and passing |
| AC-5: no retroactive cache correction | Step 6 (diff review) | Manual diff inspection — Agent-Probe |
| AC-6: no interference with RFC-3 | Step 6 (diff review) | Manual diff inspection — Agent-Probe |

## Verification Evidence

| Gate / Scenario | Strategy | Proves SPEC criterion |
|---|---|---|
| `test_fetch_live_drops_partial_hour_row` (`api/tests/data/test_pytrends_adapter.py`) | Fully-Automated | AC-1 |
| `test_fetch_live_all_rows_partial_returns_none` (same file) | Fully-Automated | AC-2 |
| `test_fetch_live_no_ispartial_column_unchanged` (same file) | Fully-Automated | AC-3 |
| `uv run --project api pytest api/ -q` (full suite, incl. unmodified `test_snapshot_narrative.py`) | Fully-Automated | AC-4 |
| `git diff api/data/pytrends_adapter.py` reviewed for cache-write/migration touches | Agent-Probe | AC-5 |
| `git diff api/data/pytrends_adapter.py` reviewed for signature/call-site stability | Agent-Probe | AC-6 |

## Test Infra Improvement Notes

(none identified yet)

## Dependencies / Risks

- No new dependencies. No infra setup required (synthetic fixtures only, per SPEC Constraint).
- Risk: the exact mechanism for mocking `pytrends.request.TrendReq` inside a function-local import
  without installing the real `pytrends` package needs to be confirmed against this repo's existing
  conventions at implementation time (Step 3) — flagged explicitly in the checklist rather than
  assumed. **Resolved during VALIDATE (28-09-26):** `pytrends` is confirmed not installed and not a
  declared dependency, so `sys.modules` injection is the required mechanism, not merely a fallback —
  see Step 3's VALIDATE-confirmed note above.
- Risk: none to production behavior — this narrows a failure path (fewer bad writes), it cannot
  newly break a currently-passing case, since `isPartial=False` rows and no-`isPartial`-column cases
  are both explicitly preserved.

## Phase Completion Rules

- PLAN is complete when this file is written with all required sections (Touchpoints, Public
  Contracts, Blast Radius, Verification Evidence, Test Infra Improvement Notes, Resume and
  Execution Handoff) and the validator passes.
- VALIDATE is complete when `## Validate Contract` below is replaced with a written V1-V7 contract
  and Gate is PASS or an accepted CONDITIONAL.
- EXECUTE is complete when all 6 checklist steps are done, all 3 new tests pass, the full
  `pytest api/ -q` regression run is green, and the Step 6 diff review confirms AC-5/AC-6.
- This is a SIMPLE single-phase plan — no phase program, no umbrella plan, no multi-phase status
  table.

## Resume and Execution Handoff

1. Selected plan file path: `process/features/narrative-mindshare/active/pytrends-partial-hour-fix_28-09-26/pytrends-partial-hour-fix_PLAN_28-09-26.md`
2. Last completed phase or step: VALIDATE complete, Gate: PASS — ready for EXECUTE.
3. Validate-contract status: written 28-09-26 (see `## Validate Contract` below), `generated-by: outer-pvl`.
4. Supporting context files loaded: `process/context/all-context.md`, `process/context/tests/all-tests.md`, `process/context/planning/all-planning.md`, the locked SPEC in this task folder, `api/data/pytrends_adapter.py`, `api/scripts/backfill_pytrends_history.py` (lines 85-119), `api/tests/scripts/test_snapshot_narrative.py`, `api/analytics/narrative/trigger.py`.
5. Next step for a fresh agent: `ENTER EXECUTE MODE` for this plan. No PVL supplement cycle needed (first-pass PASS, 0 FAILs, 0 CONCERNs).

## Validate Contract

Status: PASS
Date: 28-09-26
date: 2026-09-28
generated-by: outer-pvl

Parallel strategy: sequential
Rationale: signal score 0/7 (single-file source change + one new test file, no schema/auth/API/billing surface, no phase program) — matches INNOVATE's own recommendation; VALIDATE fan-out itself ran as one pass (Simple Mode) rather than a multi-agent spawn, appropriate for this plan's size.

Test gates (C3 5-column table):

| criterion id | behavior | strategy | proving test | gap-resolution |
|---|---|---|---|---|
| AC-1 | `_fetch_live` drops the current, still-accumulating (`isPartial=True`) hour before picking the latest point | Fully-Automated | `uv run --project api pytest api/tests/data/test_pytrends_adapter.py::test_fetch_live_drops_partial_hour_row -v` | B |
| AC-2 | When every available row is partial, `_fetch_live` returns `(None, None)` so `fetch_trend` falls into existing `unavailable`/`presumed-dead` handling instead of writing a fabricated 0 | Fully-Automated | `uv run --project api pytest api/tests/data/test_pytrends_adapter.py::test_fetch_live_all_rows_partial_returns_none -v` | B |
| AC-3 | When the frame has no `isPartial` column, behavior is byte-identical to pre-fix (`df.iloc[-1]` used directly) | Fully-Automated | `uv run --project api pytest api/tests/data/test_pytrends_adapter.py::test_fetch_live_no_ispartial_column_unchanged -v` | B |
| AC-4 | No regression to `test_snapshot_narrative.py`, `trigger.py`, or any other pytrends/narrative consumer | Fully-Automated | `uv run --project api pytest api/ -q` (baseline confirmed green 28-09-26: 623 passed, 5 deselected, exit 0) | A |
| AC-5 | No retroactive correction of already-archived cache points — diff touches only `_fetch_live`'s row-selection block, no `cache.write_narrative_point`/`read_narrative_series`/migration code | Agent-Probe | `git diff api/data/pytrends_adapter.py` reviewed for cache read/write/migration touches | B |
| AC-6 | `_fetch_live` signature and all call sites (`fetch_trend`, `snapshot_narrative.py`) unchanged — no interference with not-yet-started `narrative-v2` RFC-3 | Agent-Probe | `git diff api/data/pytrends_adapter.py` reviewed for signature/call-site stability | B |

gap-resolution legend:
- A — proven now (gate passes in this cycle)
- B — fixed in this plan (gate added by this plan's checklist)
- C — deferred to a named later phase/plan
- D — backlog test-building stub (named residual; keep-active; continue)

Legacy line form (retained so existing validate-contract consumers still parse):
- `_fetch_live` row-selection: Fully-automated: `uv run --project api pytest api/tests/data/test_pytrends_adapter.py -v` (3 new tests) | Fully-automated: `uv run --project api pytest api/ -q` (full regression, baseline 623 passed/5 deselected confirmed green pre-EXECUTE) | Agent-probe: `git diff api/data/pytrends_adapter.py` reviewed for AC-5 (no cache-write touch) and AC-6 (signature/call-site stability)

Failing stub (AC-1):
```
test("should drop the isPartial=True current-hour row before picking the latest point, returning the prior complete row's value instead", () => {
  throw new Error("NOT IMPLEMENTED — TDD stub: test_fetch_live_drops_partial_hour_row")
})
```

Failing stub (AC-2):
```
test("should return (None, None) when every row in the fetched frame is isPartial=True", () => {
  throw new Error("NOT IMPLEMENTED — TDD stub: test_fetch_live_all_rows_partial_returns_none")
})
```

Failing stub (AC-3):
```
test("should behave exactly as pre-fix (use df.iloc[-1] directly) when the frame has no isPartial column at all", () => {
  throw new Error("NOT IMPLEMENTED — TDD stub: test_fetch_live_no_ispartial_column_unchanged")
})
```

(Note: stubs are written in the generic `test(...)` skeleton form per `vc-test-coverage-plan`
convention; execute-agent implements them as real `pytest` functions per the plan's own Step 3
test descriptions, which are the authoritative Python-shaped spec for each test body.)

Dimension findings:
- Infra fit: PASS — no container/infra/runtime surface touched; pure single-module Python fix. File paths confirmed to exist and match plan's line-number claims exactly (`_fetch_live` lines 50-74, early-return at 64-65, `df.iloc[-1]` at line 66 — zero drift from plan text, confirmed by direct read 28-09-26). `api/tests/data/` directory already exists with an `__init__.py` and 8 sibling test files, so plan's "create if it does not already exist" step is a no-op.
- Test coverage: PASS — all 3 new unit-test commands and the full-suite regression command verified runnable with this repo's exact `uv run --project api pytest ...` convention (confirmed via a live subset run: `api/tests/data` = 162 passed, 4 deselected; full `api/ -q` = 623 passed, 5 deselected, exit 0, confirmed 28-09-26 as pre-EXECUTE baseline). No high-risk class applies, so Agent-Probe-only coverage for AC-5/AC-6 is acceptable under the Test Tier Waterfall (no forced-hybrid minimum).
- Breaking changes: PASS — `_fetch_live` signature and both call sites (`fetch_trend`, `snapshot_narrative.py::snapshot_pytrends`) confirmed unchanged by plan design; `test_snapshot_narrative.py` confirmed (via direct read) to monkeypatch `pytrends_adapter._fetch_live` at the module-attribute level, never exercising the real row-selection logic, so it needs no edit and will not regress. No schema, cache-format, or public-API surface touched.
- Security surface: PASS — no auth, billing, secrets, or trust-boundary logic touched. No new external input trust boundary introduced (same pytrends response shape parsed as before, only filtered more defensively before use).
- Mocking-mechanism risk (plan's Dependencies/Risks section): RESOLVED, not a CONCERN — confirmed 28-09-26 that `pytrends` is genuinely not installed in the `api` env (`ModuleNotFoundError`) and is not declared in `api/pyproject.toml`, so `monkeypatch.setitem(sys.modules, "pytrends.request", fake_module)` is the required (not merely fallback) mechanism for the new test file. Plan text updated above with this confirmation so execute-agent does not need to discover it independently.
- Cache/AC-5 scope: PASS — plan's touchpoints list only `api/data/pytrends_adapter.py` and the new test file; no reference anywhere in the plan to `cache.py` write paths or `api/data/cache/narrative/`, consistent with AC-5's forward-only-fix requirement.
- AC mapping 1:1 to SPEC: PASS — plan's Acceptance Criteria table and Verification Evidence table checked directly against the SPEC's 6 acceptance criteria (read in full); every AC's wording, test name, and strategy matches the SPEC exactly, no drift or omission found.

Open gaps: none

What this coverage does NOT prove:
- The 3 new unit tests prove `_fetch_live`'s row-selection logic in isolation against synthetic DataFrames — they do NOT prove Google Trends' real API actually returns `isPartial` in the shape assumed (this container's egress proxy blocks Google Trends, so no live-network confirmation is possible here; the existing 269-day backfill script's proven use of the identical pattern is the closest available real-world evidence).
- The full-suite regression run (`pytest api/ -q`) proves no *existing* test breaks — it does NOT prove the nightly `snapshot_narrative.py` cron job itself behaves correctly end-to-end on the user's real schedule (that would require observing an actual nightly run post-deploy, which is out of scope for this fix's verification and consistent with how prior narrative-mindshare fixes in this repo have been closed).
- The AC-5/AC-6 Agent-Probe diff reviews prove the *committed diff's file scope* is correct — they do NOT prove no other developer/agent modifies `_fetch_live`'s call sites in a future unrelated change; this is an inherent limit of a point-in-time diff review, not a gap specific to this plan.
- No test confirms whether previously-zero'd categories (`memecoins`, `RWA`) will in fact receive nonzero values once this fix ships — that depends on real Google Trends data at fetch time, which cannot be predicted or tested in advance; the fix's correctness is that it stops writing *known-fake* zeros, not that it guarantees nonzero output.

Gate: PASS (no FAILs, no CONCERNs — plan checked directly against SPEC, source files read to confirm zero drift, test commands verified runnable, mocking-mechanism risk resolved)

## Autonomous Goal Block

```
SESSION GOAL: Fix pytrends_adapter._fetch_live to drop Google Trends' incomplete isPartial=True
current-hour row before selecting the latest point, so the nightly narrative snapshot stops
archiving permanently-lost fake zeros for memecoins/RWA categories.
Charter + umbrella plan: N/A — single SIMPLE plan, no phase program, no umbrella.
Autonomy: Standard RIPER-5 autonomy rules apply (process/development-protocols/orchestration.md
§Autonomy Mode). This plan carries Gate: PASS with 0 FAILs/0 CONCERNs — EXECUTE may proceed on
explicit "ENTER EXECUTE MODE" without a PVL supplement cycle.
Hard stop conditions / safety constraints:
- Do NOT change _fetch_live's function signature or either call site (fetch_trend,
  snapshot_narrative.py::snapshot_pytrends) — required for narrative-v2 RFC-3 non-interference.
- Do NOT modify api/tests/scripts/test_snapshot_narrative.py.
- Do NOT touch cache.write_narrative_point, cache.read_narrative_series/read_narrative_history,
  or any file under api/data/cache/narrative/ — this is a forward-only fix, no retroactive
  correction of already-archived zero points.
- Do NOT require live network access for the new tests — synthetic DataFrame fixtures only
  (pytrends is confirmed not installed in the api env).
Next phase: EXECUTE: process/features/narrative-mindshare/active/pytrends-partial-hour-fix_28-09-26/pytrends-partial-hour-fix_PLAN_28-09-26.md
Validate contract: inline in plan (see ## Validate Contract section above)
Execute start: fully-automated commands — `uv run --project api pytest api/tests/data/test_pytrends_adapter.py -v` then `uv run --project api pytest api/ -q` | no e2e spec (backend-only fix) | agent-probe: `git diff api/data/pytrends_adapter.py` reviewed for AC-5/AC-6 | high-risk pack: no (no high-risk class present)
```
