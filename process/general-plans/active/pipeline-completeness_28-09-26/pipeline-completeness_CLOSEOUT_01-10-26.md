---
name: report:pipeline-completeness-closeout
description: "UPDATE PROCESS closeout for the P1 pipeline-completeness task folder (three plans): code done, not verified, keep in active"
date: 01-10-26
status: COMPLETE_WITH_GAPS
feature: general
plan: process/general-plans/active/pipeline-completeness_28-09-26/pipeline-completeness_PLAN_28-09-26.md
metadata:
  node_type: memory
  type: report
  feature: general
  phase: UPDATE-PROCESS
---

# P1 pipeline completeness - closeout packet

**Verdict:** all three plans are **WITH_GAPS / keep in active (code done, not verified)**. Nothing is archived and nothing is marked VERIFIED. Independent `vc-tester` EVL runs were green, but each plan's gate is CONDITIONAL on recorded gaps, and no human accepted any gap - they are carried under the autonomous-run policy.

## 1. Selected plans

| Plan | Commit | Status |
|---|---|---|
| `pipeline-completeness_PLAN_28-09-26.md` (schedules + cache story) | `4c975a3` | CODE DONE |
| `pipeline-completeness-atomic-writes_PLAN_29-09-26.md` | `ba82986` | CODE DONE |
| `pipeline-completeness-cron-timing_PLAN_29-09-26.md` | `9e04f71` | CODE DONE |

Branch `claude/p1-pipeline`, PR #11 (process commits for validate contracts/PVL cycles sit between these).

## 2. Classification

**WITH_GAPS / keep in active** for all three (maps to "Keep in active/testing"). Not archivable: each has criteria resting on a Known-Gap residual that no passing automated gate proves (AC-13/AC-14; AC-6; KG1-KG5).

## 3. What was finished

- Two new nightly workflows (`pairs-refresh-snapshot.yml`, `liquidity-backfill-snapshot.yml`); `.github/workflows/` now has five.
- `refresh_cache.py`, `backfill_primaries.py`, `compute_pairs.py` have real exit codes; `bootstrap_watchlist.py` and `api/scripts/BOOTSTRAP.md` added; guard test reshaped.
- Cache decision: nothing new committed (estimated ~1.5-3.3 GB/year otherwise).
- All 9 parquet writers in `api/data/cache.py` atomic (`_atomic_to_parquet`), `.gitignore` covers `*.tmp`.
- All five crons moved to 11:17 / 11:47 / 12:17 / 12:47 / 13:17 UTC; 10h delay budget; schedule-only midnight-crossing warning on the three no-history workflows.

## 4. Verified vs unverified

**Verified (independent vc-tester, offline):**
- Schedules + cache story: pytest 714 -> 789 passed / 5 deselected; guard test 13 -> 38.
- Atomic writes: 789 -> 817; 28 new tests, red-first (18 failed on old code); real cache and `watchlist.json` byte/mtime unchanged.
- Cron timing: 817 -> 820; guard file 38 -> 41 / 0 skipped; 72-case G6 guard script ok.
- Final full suite: **820 passed / 5 deselected**.

**Unverified:** real cron firing (AC-13, AC-6, K1); any live ccxt/Hyperliquid/FRED fetch (AC-14); real power-loss durability; Windows behaviour; GitHub's evaluation of the `if:` guard.

## 4b. Validate-contract compliance

Each plan has a `## Validate Contract`, gate **CONDITIONAL** (not PASS) on recorded gaps only; 0 FAILs at final pass. `results.tsv` rows 0-8 record the PVL cycles. Independent validation overturned the author's inline PASS in all three plans.

## 5. Gaps (open)

- **KG1** real power-loss durability; no directory fsync; fsync only spy-tested.
- **KG2** Windows `os.replace` with an open reader.
- **KG3** `pairs_response.py` tmp writes not fsynced.
- **KG4** two JSON writers in `cache.py` use a fixed temp name.
- **KG5** `etf_flows_adapter.merge_into_cache` writes non-atomically (request path, gitignored, no git copy). Needs a user scope decision.
- **AC-13 / AC-14** cron firing and live fetch unobserved.
- **K1** delay unobservable offline (was growing ~+2h/day); **K2** merge-day loss window; **K3** guard only detects post-midnight starts; **K4** pytrends sampling hour shifts from ~18:17 to ~12:47 (one-time discontinuity in the archived series).

Backlog notes written (`process/general-plans/backlog/`): `pipeline-cron-firing-confirmation_NOTE_01-10-26.md`, `pipeline-live-fetch-canary_NOTE_01-10-26.md`, `pipeline-etf-flows-atomic-write_NOTE_29-09-26.md`, `pipeline-cache-hardening-followups_NOTE_01-10-26.md`.

## What the schedule does NOT deliver

- **The commit steps of the two new workflows are inert on GitHub Actions** until P2 supplies a persistent disk (ephemeral runner, cache dirs gitignored). Today they are a nightly integration canary only.
- A GitHub-hosted `compute_pairs` only sees <=500 daily bars per coin (`DEFAULT_LIMIT`) versus the ~2,230-bar deep-fetched local cache. A CI pairs result is a canary, not a quality result.
- New cron times take effect only after merge to `main`.

## MERGE-TIME USER ACTIONS

1. **K2 - merge-day loss window.** If a no-history workflow is merged after its new cron time (chain-growth 12:17, narrative 12:47, liqtide 13:17 UTC), it has no scheduled run that UTC day. Run it manually the same UTC day: `gh workflow run <file>`.
   - liqtide: must be before ~00:25 UTC, or that day's file is permanently lost (it only publishes "latest").
   - narrative: loses that day's point.
   - chain-growth: harmless.
   - Merging before ~12:00 UTC avoids all of it.
2. **After merge**, verify the first 2-3 nights with `gh run list --workflow <file> --json event,createdAt,startedAt` (see the cron-firing backlog note).

## 6. SPEC achievement

Only the schedules plan has a SPEC (`pipeline-completeness_SPEC_28-09-26.md`). Per the plan's AC table (and the EXECUTE report): AC-1..7, 9-11 met by passing automated gates (AC-7's live runbook run is Known-Gap); AC-8, 15 documented; **AC-12 (commit + PR) was not claimed by EXECUTE - the orchestrator owns it (PR #11 exists)**; **AC-13, AC-14 unmet** (Known-Gap only) -> backlog notes above. Atomic-writes and cron-timing score against their own plan ACs: all automated criteria met; AC-6 (cron timing, real firing) unmet pending `gh run list`.

## 7. Commit checkpoint

Execution commits already made by the orchestrator (above). Process commit belongs after this UPDATE PROCESS: context docs, backlog notes, this closeout.

## 8. Regression status

Full suite 820 passed / 5 deselected, same 5 deselected as baseline; real cache and `watchlist.json` unchanged (size + mtime + sha256). Forbidden-surface diff empty at each plan.

## P2 handoff

Atomic writes landed, so P2's auto-resume prerequisite is met **for `cache.py` writers, EXCEPT KG5** (`etf_flows_adapter`). P2 AC12 is not fully met until KG5 is fixed. P2 should expect contention on `.github/workflows/` (two new files). The inert commit steps become real only with persistent disk.

## MASTER-PLAN reconciliation (not edited here)

- **T5:** the planned `pairs-recompute.yml` name is superseded by `pairs-refresh-snapshot.yml`.
- **T27:** addressed by the cron-timing change (pending merge and AC-6 confirmation).
- **T16:** root README should link `api/scripts/BOOTSTRAP.md`.
- Also: T21 (`cache.py` refactor) now owns KG3/KG4; T22 (global isolation audit) is still open - `isolated_cache` remains opt-in globally, made autouse module-locally in four test files.

## Drift score

MEDIUM (3 signals: >=10 files touched across the three plans, new task-folder/backlog notes, 3+ memory-worthy lessons). Recommend UPDATE PROCESS -- significant changes detected. (UPDATE PROCESS is this session.)

## Single best next state

Merge PR #11 early UTC (before ~12:00), do the K2 manual dispatch if late, verify first 2-3 nights, then re-run EVL/closeout to promote the plans; separately decide KG5 scope.
