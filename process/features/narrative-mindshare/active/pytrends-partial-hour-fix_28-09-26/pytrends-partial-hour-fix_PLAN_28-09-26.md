---
name: plan:pytrends-partial-hour-fix
description: "Drop isPartial=True rows in pytrends_adapter._fetch_live before picking the last point, so the nightly narrative snapshot never archives Google's incomplete current hour as a real value"
date: 28-09-26
feature: narrative-mindshare
---

# Pytrends Partial-Hour Zeros — PLAN (SIMPLE)

**Date**: 28-09-26
**Status**: DRAFT — pending VALIDATE
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
  assumed. If `pytrends` genuinely is not installed in the `api` environment (module docstring notes
  it's not a hard dependency), the test must still pass by injecting a fake module into
  `sys.modules` before `_fetch_live` executes its local `import`.
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
2. Last completed phase or step: PLAN written, not yet validated.
3. Validate-contract status: pending — VALIDATE has not run yet (see placeholder section below).
4. Supporting context files loaded: `process/context/all-context.md`, `process/context/tests/all-tests.md`, `process/context/planning/all-planning.md`, the locked SPEC in this task folder, `api/data/pytrends_adapter.py`, `api/scripts/backfill_pytrends_history.py` (lines 85-119).
5. Next step for a fresh agent: run VALIDATE against this plan (mandatory gate before EXECUTE, per this repo's `VALIDATE Gate` orchestration rule). Do not route directly to EXECUTE.

## Validate Contract

(placeholder — vc-validate-agent writes this section before EXECUTE)
