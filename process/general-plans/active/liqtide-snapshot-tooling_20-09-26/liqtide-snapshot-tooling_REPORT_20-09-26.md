---
phase: liqtide-snapshot-tooling
date: 2026-09-20
status: COMPLETE_WITH_GAPS
feature: general-plans
plan: process/general-plans/active/liqtide-snapshot-tooling_20-09-26/liqtide-snapshot-tooling_PLAN_20-09-26.md
---

# LiqTide Snapshot Tooling — Execute Report

## Headline

All 4 checklist items implemented; all 6 test gates run and passed. **But the deliverable
question — do the full and reduced composites agree? — is unanswerable today**, and the
comparison script proved exactly that: `api/data/cache/liqtide/` is EMPTY (zero archived
days), so the full composite has no input at all. The `DISAGREE` verdict printed is
"one side has no data", not evidence of actual disagreement. See §Deliverable Finding.

## What Was Done

1. **`api/data/liqtide_adapter.py`** (additive) — `LiqTidePayload.raw: dict | None = None`
   added as the LAST field; `_parse_payload` sets `raw=raw`; `_row_to_payload` leaves it
   `None` with an explaining comment; `fetch_latest(client=None, dry_run=False)` skips the
   `cache.write_liqtide_payload` call when `dry_run=True` and still returns the full payload.
2. **`api/scripts/snapshot_liqtide.py`** (new) — `WEIGHTS` verbatim from the plan,
   `check_arithmetic` (recompute + clamp + weight-sum + `data_quality`), `check_coverage`
   (per-column non-null counts + calendar gap detection), `main()` with `--coverage` /
   `--verify-only` and exit codes 0/1/2. Never calls `write_liqtide_payload` directly.
3. **`.gitignore`** — `api/data/cache/` replaced with `api/data/cache/*` +
   `!api/data/cache/liqtide/` (negation after the broader ignore), with a comment.
4. **`api/scripts/compare_composite_variants.py`** (new) — follows
   `backtest_leg_boundaries.py` conventions (bootstrap, `REPORT_DIR` pointed at THIS task
   folder, atomic temp+`replace()` write, argparse). `AGREEMENT_TOLERANCE_DAYS =
   leg_boundary.CONFIRMATION_WINDOW_DAYS` with the verbatim reuse rationale comment.
   Greedy nearest-first bijective matching, AGREE/PARTIAL/DISAGREE verdict, JSON report.
5. **E2 (done)** — `api/tests/scripts/test_snapshot_liqtide.py`, 11 synthetic-fixture tests,
   no network. Covers the `check_coverage` non-empty/gap/null paths the empty local archive
   cannot reach via the CLI.

## Execute-Agent Instructions

- **E1 — SATISFIED (confirmed, not assumed).** `api/data/cache.py:34` declares
  `OHLCV_COLUMNS = ["timestamp", "open", "high", "low", "close", "volume", "source"]`, and
  `leg_boundary.confirm_boundaries` sorts `btc_price_df` on `"timestamp"` directly
  (`leg_boundary.py:111`). Column name is `"timestamp"`; the filter line uses it.
- **E2 — DONE** (optional, completed; see item 5 above).

## Test Gate Outcomes

| Gate | Result |
|---|---|
| `uv run pytest tests/ -x -q` (after item 1) | PASS — 168 passed, 1 deselected |
| `uv run pytest tests/ -x -q` (final, incl. new tests) | PASS — 179 passed, 1 deselected |
| Grep of `LiqTidePayload(` / `fetch_latest(` call sites | PASS — 3 constructor sites, ALL inside `liqtide_adapter.py`, ALL kwargs. ZERO external `fetch_latest(` callers. Additions are genuinely additive. |
| `snapshot_liqtide.py --verify-only` | PASS — exit 0, no WARN, and `api/data/cache/liqtide/` verified still empty afterward (no write) |
| `snapshot_liqtide.py --coverage` | PASS — exit 0, correctly reports EMPTY archive |
| `.gitignore` probe | PASS — liqtide throwaway shows `?? api/data/cache/liqtide/__throwaway.txt`; ohlcv throwaway matched by `.gitignore:18:api/data/cache/*`. Throwaways removed. |
| `compare_composite_variants.py` | PASS (ran to completion, verdict + JSON report written) |

## Deliverable Finding (the actual answer)

```
Window: 2024-01-11 -> 2026-09-20 (tolerance 10 days, BTC bars 501)
  full    available=False points=0 candidates=0 confirmed=[]
  reduced available=True  points=671 candidates=0 confirmed=[]
  VERDICT: DISAGREE
```

Two independent reasons the question cannot be answered right now:

1. **The full composite has zero input.** `cache/liqtide/` holds no archived payloads, so
   `build_full_composite` returns `available=False`. The `DISAGREE` verdict is the
   "one side has no confirmed boundaries" branch firing on missing data.
2. **The reduced composite found 0 candidate boundaries** over the entire 2024-01→2026-09
   window (671 points, available). Even a fully-populated full composite would have had
   nothing to match against on the reduced side.

**Consequence for the 2020-21 re-run and every pre-2024 backtest: still unvalidated.** This
script did not show the composites disagree; it showed the cross-check is currently
impossible. And it may stay impossible for a long time — LiqTide has no historical
endpoint, so the overlap window can only be populated forward from the first day the
snapshot script actually runs. A meaningful comparison needs years of archive, not days.

## What Was Skipped or Deferred

- `.github/workflows/` scheduling — explicitly out of scope per the plan and orchestrator.
- **No archiving run was made.** Only `--verify-only` (dry-run) was executed, so today's
  payload (2026-09-20, `tide_score=-0.0701`, value 46 "SLACK WATER", regime "TURBULENCE")
  is NOT archived. Running the plain `snapshot_liqtide.py` would capture it. Left to the
  user since it writes a now-git-trackable file.

## Plan Deviations

None. All 4 items implemented per spec.

## Test Infra Gaps Found

- `compare_composite_variants.py` has no unit test for `_match`/`_verdict` (pure functions).
  The CLI gate exercised them only on the degenerate empty-input path, so the bijective
  matching logic has never run against real boundaries. Candidate follow-up.

## Closeout Packet

- Selected plan: `process/general-plans/active/liqtide-snapshot-tooling_20-09-26/liqtide-snapshot-tooling_PLAN_20-09-26.md`
- Finished: all 4 checklist items + E1 + E2.
- Verified: full pytest suite, grep additivity, dry-run no-write, coverage mode, gitignore
  negation, end-to-end comparison run.
- Unverified: whether the composites actually agree (blocked on an empty archive, not on code).
- Remaining: start running the snapshot daily; decide on scheduling; consider whether the
  comparison question is answerable on any useful timescale given LiqTide's no-history limit.
- **Classification: Keep in active/testing** — code complete, but the plan's stated purpose
  (answering the agreement question) is not achieved and depends on archive accumulation.

## Forward Preview

- **Test Infra Found:** `pytest` with `integration` marker deselected by default;
  `api/scripts/` is an importable package, so script helpers are directly unit-testable
  (`api/tests/scripts/` added this phase).
- **Blast Radius Changes:** `api/data/liqtide_adapter.py` (additive), `.gitignore`,
  2 new scripts, 1 new test package.
- **Commands to Stay Green:** `cd api && uv run pytest tests/ -x -q`
- **Dependency Changes:** none.

## New Artifacts (uncommitted, for review)

- `process/general-plans/active/liqtide-snapshot-tooling_20-09-26/composite-variant-agreement-20260920-180830.json`
