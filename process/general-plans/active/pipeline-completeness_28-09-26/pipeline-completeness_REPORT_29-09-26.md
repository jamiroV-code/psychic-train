---
name: report:pipeline-completeness-execute
description: "EXECUTE report for P1 pipeline completeness — two nightly workflows, script exit codes, bootstrap script, runbook, guard-test reshape"
date: 29-09-26
status: COMPLETE_WITH_GAPS
feature: general
plan: process/general-plans/active/pipeline-completeness_28-09-26/pipeline-completeness_PLAN_28-09-26.md
metadata:
  node_type: memory
  type: report
  feature: general
  phase: EXECUTE
---

# EXECUTE — Pipeline Completeness (P1)

TL;DR: all 12 planned files written, every offline gate green, pytest **714 →
789 passed** (+75 tests, 0 failures, 5 deselected unchanged). AC-13 and AC-14
remain Known-Gap as planned. AC-12 (commit + draft PR) is **not claimed** —
this agent is forbidden from staging or committing; the orchestrator owns it.

## Measured counts (the plan's 717/5 expectation was wrong)

| | passed | deselected |
|---|---|---|
| Baseline, before any edit | **714** | 5 |
| After | **789** | 5 |

Delta = +75, exactly the added tests. Zero failures, zero regressions.
Pre-state recorded at baseline: `api/data/cache/{ohlcv,liquidity,pairs}` all
existed and were **empty**; `api/data/watchlist.json` did **not** exist.

## What Was Done

**Created (8):**
- `.github/workflows/pairs-refresh-snapshot.yml` — cron `17 19 * * *`; refresh
  then compute as two sequential steps of ONE job.
- `.github/workflows/liquidity-backfill-snapshot.yml` — cron `47 19 * * *`.
- `api/scripts/bootstrap_watchlist.py` — idempotent example→real copy (D5).
- `api/scripts/BOOTSTRAP.md` — runbook, all 10 required sections (D6).
- `api/tests/scripts/test_refresh_cache.py` (18 tests)
- `api/tests/scripts/test_backfill_primaries.py` (18 tests)
- `api/tests/scripts/test_bootstrap_watchlist.py` (8 tests)
- this report.

**Modified (5):**
- `api/scripts/refresh_cache.py` — `FetchSummary`, `run_refresh`, pure
  `exit_code`, `main(argv=None, *, sleep=time.sleep)`, `__main__` wrapper,
  D7 universe-coins-on-`1d`, `refresh_all()` kept as a thin wrapper.
- `api/scripts/backfill_primaries.py` — same pattern, `SeriesSummary`,
  `backfill_all()` kept.
- `api/scripts/compute_pairs.py` — `exit_code(summary)`, `main(argv, *, sleep)`,
  `__main__` wrapper. `compute_and_persist` untouched.
- `api/tests/scripts/test_compute_pairs.py` — autouse isolation fixture,
  canary, 7 new exit-code/integration tests. Existing tests unmodified.
- `api/tests/scripts/test_snapshot_workflow_schedules.py` — full reshape
  (dict of lists, `TOLERANT_STAGING`, `_staged_dirs`, 6 new tests, the
  `workflow_dispatch` assertion, docstring "five"). 38 tests, was 13.

The two workflows reproduce the existing safety shape exactly: `permissions:
contents: write` only, `concurrency` with `cancel-in-progress: false`,
`workflow_dispatch` alongside `schedule`, no `pull_request`, "nothing new to
commit" early exit, 3-attempt `git pull --rebase`/push retry. Staging uses the
tolerant form `git add -A -- <dir> 2>/dev/null || true`; no `-f` anywhere.
Commit is gated on an allow-list (both recorded codes in {0,2}); any other
code skips the commit and fails the job.

## Test Gate Outcomes (contract §Test-gate command list)

| # | Gate | Result |
|---|---|---|
| 1 | Baseline full suite | **714 passed / 5 deselected** |
| 2 | Per-section pytest | green at each section |
| 3 | `pytest api/tests/scripts -q`, then full suite | **789 passed / 5 deselected** |
| 4 | YAML parse of both new workflows | `YAML OK`, exit 0. `actionlint` not on PATH (not a failure) |
| 5 | Runbook greps | dirs 8 (≥4), estimated 10 (≥5), inert 2 (≥1), commands 24 (≥5), stale 2 (≥1) — all pass |
| 6 | `validate-plan-artifact.mjs`; `git diff --check` | 0 failures / 0 warnings; clean |
| 7 | Scope | exactly the 12 Touchpoint files changed; forbidden-surface diff **empty** |
| 8 | AC-12 commit + draft PR | **NOT RUN** — see Deviations |
| 9a | `autouse=True` present in all 4 test files | 2 each (≥1) |
| 9b | `--setup-show` SETUP count vs collected | **59 == 59 → EQUAL-PASS** |
| 9c | Before/after content snapshot | **REAL-CACHE-UNCHANGED** |
| 9d | `test_isolated_cache_redirects_cache_root` canary | present in all 4 files |
| 9e | `git status --porcelain` on `pairs_universe.json` / `watchlist.example.json` | empty → pass |

Additional safety observation: after all test runs,
`api/data/watchlist.json` still does not exist — no rogue `main([])` created
the developer's real watchlist.

## AC Status

| AC | Status |
|---|---|
| 1, 2, 3, 4, 5, 6, 9, 10, 11 | ✅ CODE DONE — fully-automated gates green |
| 7 | ✅ CODE DONE (Hybrid doc check passed; live runbook run is Known-Gap) |
| 8, 15 | ✅ present and reasoned in the plan's "D1 numbers" + BOOTSTRAP.md §6/§7 |
| 12 | ⛔ NOT CLAIMED — orchestrator owns the commit/PR |
| 13, 14 | 🔶 Known-Gap, unchanged — no cron firing, no live fetch observable here |

Plan status vocabulary: this reaches **CODE DONE**, not VERIFIED.

## Plan Deviations

1. **Baseline was 714, not the expected 717.** Not a deviation in behavior —
   the plan explicitly said the figure was unconfirmed and to record the
   measured value. Recorded.
2. **AC-12 not executed.** The plan's Checklist step 20 asks EXECUTE to commit,
   push and open a draft PR. This agent's binding session constraint forbids
   `git add`/`commit`/any staging or history command. Handed to the
   orchestrator; no attempt made. This is a process-ownership deviation, not a
   scope deviation.
3. **Three small additions inside the blast radius** (within-blast-radius,
   documented, continued): `WORKFLOW_MODULES` map and
   `test_warn_step_fires_only_on_exit_two` in the guard test (tightens AC-3
   without weakening anything); `REQUEST_SPACING_SECONDS` also added to
   `backfill_primaries.py` for symmetry with `refresh_cache.py` (value `0.0`,
   no behavior change). All inside files already listed in Touchpoints.

E1–E8 were all honored: E1 (`exit` matched as a statement, commit-step
`exit 0`/`exit 1` left alone), E2 (empty-cache integration test written as
NEW), E3 (both edge cases named tests), E4 (`ok = status=="ok" and not
insufficient_history`, pinned by a test), E5 (temp repo `git init`, `cwd`
pinned, `rev-parse --show-toplevel` asserted first), E6 (gate 9e added),
E7 (`bootstrap_watchlist` uses the same argv idiom), E8 (no script run against
the real tree).

## Test Infra Gaps Found

None new. The pre-existing note stands: the workflow guard test only checks
YAML text and structure — GitHub's expression semantics and whether the cron
actually fires are unproven locally. `actionlint` is not installed.

## Closeout Packet

- **Selected plan:** `process/general-plans/active/pipeline-completeness_28-09-26/pipeline-completeness_PLAN_28-09-26.md`
- **Finished:** all 20 checklist steps except step 20 (commit/PR).
- **Verified:** every offline gate in the contract's command list.
- **Unverified:** AC-12 (not attempted here), AC-13, AC-14 (structural).
- **Remaining:** orchestrator commit + draft PR; UPDATE PROCESS writes the two
  backlog stubs and the `all-context.md` pointer.
- **Classification:** **Keep in active/testing** — code-complete and green, but
  AC-12/AC-13/AC-14 keep it short of archival.

## Forward Preview

- **Test Infra Found:** `isolated_cache` remains opt-in globally; this plan
  made it autouse module-locally in four files. MASTER-PLAN T22's global audit
  is still open.
- **Blast Radius Changes:** none beyond the plan. Two new files under
  `.github/workflows/` — P2 must expect contention there.
- **Commands to Stay Green:** `uv run --project api pytest api/ -q` (expect
  789/5); `uv run --project api pytest api/tests/scripts -q`.
- **Dependency Changes:** none. No new packages.
