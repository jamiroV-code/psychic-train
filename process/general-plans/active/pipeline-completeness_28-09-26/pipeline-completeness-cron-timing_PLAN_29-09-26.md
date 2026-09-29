---
name: plan:pipeline-completeness-cron-timing
description: "Move all five nightly workflows earlier for a 10h scheduler-delay budget, add a crossed-midnight runtime warning, and fix the false ~2h-late comments and guard test"
date: 29-09-26
feature: pipeline-completeness
---

# Pipeline Completeness — Cron Timing (T27) PLAN

Date: 29-09-26
Complexity: SIMPLE (config + one test file; no application source)
Status: ⏳ PLANNED
**Branch:** `claude/p1-pipeline` (draft PR; workflows only take effect after merge to `main`)

TL;DR: GitHub's scheduler delay grew from ~2h to 5h01m in three days, so every cron moves to 11:17–13:17 UTC (a 10h delay budget), each no-history workflow gets a first step that warns if the run crossed UTC midnight, and the guard test's buffer goes from 180 to 600 min.

## Overview

Context loaded: `process/context/all-context.md` (LiqTide publish window, 2026-09-27 cron-timing entry) and `process/context/tests/all-tests.md` (pytest runner). Post-phase testing: vc-tester runs G1–G6 after EXECUTE.

## Problem (measured, orchestrator ground truth)

| Workflow | Cron | 09-27 start (delay) | 09-28 start (delay) |
|---|---|---|---|
| chain-growth-snapshot | 17:47 | 20:26Z (2h39m) | 22:38Z (4h52m) |
| narrative-snapshot | 18:17 | 21:23Z (3h06m) | 23:18Z (5h01m) |
| liqtide-snapshot | 18:47 | 21:38Z (2h51m) | 23:31Z (4h45m) |

Delay is growing (~2h → 3h → 5h). Narrative committed 41 min before losing a day. At 5h01m the two new workflows (19:17, 19:47) would start ~00:18Z / ~00:48Z. The guard test pins scheduled time only, never observed delay, so it passed. (MASTER-PLAN T27 was not found on `origin/main`; the orchestrator's numbers are the source.)

## Decisions

### D1 — Delay budget: 600 min (10h)
- Observed max 5h01m and growing ~1h/day over the last three days. 8h = observed max + ~60%; 10h = ~2x observed max. Chose 10h because the trend is rising and moving earlier costs nothing for these sources.
- Latest safe cron = 24:00 − 10h = **before 14:00 UTC** (test: `start + 600 < 1440`, i.e. start ≤ 13:59).
- Rejected 8h (latest 16:00): only ~3h headroom over an already-growing delay. Rejected >12h: pushes crons toward 00–02 UTC, colliding with LiqTide's publish window.

### D2 — New schedule (all five, 30-min stagger, same relative order for no-history jobs)

| Workflow | Old | New | Latest start at 10h delay | Class |
|---|---|---|---|---|
| pairs-refresh-snapshot | 19:17 | **11:17** | 21:17 | catch-up |
| liquidity-backfill-snapshot | 19:47 | **11:47** | 21:47 | catch-up |
| chain-growth-snapshot | 17:47 | **12:17** | 22:17 | no-history (revised series) |
| narrative-snapshot | 18:17 | **12:47** | 22:47 | no-history |
| liqtide-snapshot | 18:47 | **13:17** | 23:17 | no-history |

- Stagger: min gap 30 min (≥ 20 required). No-history order preserved (chain → narrative → liqtide).
- Publish timing: LiqTide publishes ~00:25–01:12 UTC; a 13:17 cron fires ~12h after publish. Archive is keyed by `generated_utc[:10]`, so even a very late run captures the right day as long as it runs before the *next* publish (~01:12 next day) — liqtide has ~11h55m more tolerance than narrative. Narrative sources (pytrends "now 7-d", Reddit search, CoinGecko trending) are continuous — no publish gate. growthepie/L2BEAT are full revisable series; any time of day works.
- Rejected: keeping catch-up jobs late with a separate smaller buffer — adds a second test constant for no gain; uniform budget is simpler.
- Rejected: putting catch-up jobs after the no-history jobs — not needed; they don't push to tracked dirs today (inert commit) and order among catch-up jobs doesn't matter.

### D3 — Catch-up workflows (pairs, liquidity): why late/wrong-day is harmless
- `refresh_cache`, `backfill_primaries`, `compute_pairs` are idempotent full re-fetch/recompute; the next run repairs anything; commit steps are inert today (gitignored dirs, D1).
- OHLCV tail bar: at 11:17 UTC (and at the old 19:17) the latest daily bar is the **in-progress** current-UTC-day bar; the previous day's bar is complete. Moving earlier only makes that tail bar more partial; the next night's run overwrites it. Behavior class unchanged; no script change.

### D4 — Narrative transition day (and the other two)
- Points are dated by the UTC day the run executes; moving 18:17 → 12:47 stays within the same UTC day, so a point still represents "the day it ran". No meaning change.
- Duplicates are harmless: `snapshot_narrative.py` checks `has_row(...)` per (source, key, date) and skips — a second run on the same UTC day writes nothing. LiqTide archive is first-write/no-overwrite keyed by `generated_utc[:10]`; chain-growth merges series.
- Gap risk: GitHub reads the cron from `main` at trigger time. If merge lands **after 12:47 UTC but before the old 18:17 slot fires**, that day may get no scheduled narrative run. **User action at merge:** after merging, run `gh workflow run narrative-snapshot.yml` (and `liqtide-snapshot.yml`, `chain-growth-snapshot.yml`) once the same UTC day; the `has_row` skip makes this safe even if a scheduled run also fires. Safest is merging before 12:00 UTC.

### D5 — Runtime guard (kept: cheap, one step, testable)
First step (before checkout, so it measures start time) in each of the three no-history workflows:

```yaml
      - name: Warn when the run crossed UTC midnight
        run: |
          cron_hour=12   # must equal this workflow's cron hour
          now_hour=$((10#$(date -u +%H)))
          if [ "$now_hour" -lt "$cron_hour" ]; then
            echo "::warning::scheduled for ${cron_hour}:xx UTC but started at $(date -u +%H:%M) UTC - the run crossed UTC midnight; today's no-history point may be dated the wrong day"
          fi
```
(`cron_hour` = 12, 12, 13 for chain-growth, narrative, liqtide.) Never fails the job. Limitation stated honestly: a delay ≥ 24h − ... wraps and is not detected; it detects crossing midnight only, not "close to midnight". `workflow_dispatch` runs before the cron hour would also warn — acceptable noise, message says "scheduled".
- Rejected: failing the job — the data is already lost or mis-dated; failing blocks the commit of whatever was fetched. Rejected: a delay-threshold check — needs the scheduled timestamp, which Actions doesn't expose to the job.

### D6 — Guard-test changes (`api/tests/scripts/test_snapshot_workflow_schedules.py`)
- `SCHEDULER_DELAY_BUFFER_MIN = 600`; rename `test_cron_starts_at_least_3h_before_utc_midnight` → `test_cron_leaves_scheduler_delay_budget_before_utc_midnight` and fix its message.
- Rewrite module docstring: measured delays 2h39m–5h01m (09-27/09-28, `gh`/actions list, recorded 2026-09-29), growing; 10h budget; test pins schedule only, the runtime step catches real crossings.
- Add `NO_HISTORY = {"chain-growth-snapshot.yml", "narrative-snapshot.yml", "liqtide-snapshot.yml"}` and `test_no_history_workflows_warn_on_midnight_crossing` (parametrized): the step named "Warn when the run crossed UTC midnight" exists, is `steps[0]`, has no `if`, contains `::warning::`, no `exit 1`, and its `cron_hour=(\d+)` equals the hour parsed from `_crons(name)[0]`.
- Unchanged and still passing: stagger, triggers/permissions/concurrency, retry-push, strict `git add <dir>` for the three legacy workflows and tolerant form for the two new ones, no-force-add, module invocation, pairs ordering/unconditional compute, crash-skips-commit, warn-on-exit-2 (only matches `::warning::` steps in the two new workflows, which get no guard step), tolerant-staging subprocess tests.

### D7 — Comment fixes
Replace every "~2h late (observed up to ~2h20m)" / "lands well before UTC midnight" / "~3h+ of margin" claim in all five workflow headers with: "GitHub started these runs 2h39m–5h01m late on 2026-09-27/28 (measured from the Actions run list, 2026-09-29), and the delay was growing; scheduled HH:MM UTC to survive a 10h delay budget." Plus per-file source-specific text (LiqTide publish window; narrative wrong-day loss; catch-up harmlessness + partial tail bar). Update BOOTSTRAP.md §8 times (19:17/19:47 → 11:17/11:47).

## Acceptance Criteria

- AC-1 All five crons start ≤ 13:59 UTC (10h budget), ≥ 20 min apart — G1.
- AC-2 Three no-history workflows have a first-step midnight-crossing warning whose hour matches the cron — G1, G6.
- AC-3 No stale "~2h late" / "well before midnight" claims remain — G4.
- AC-4 All existing guard assertions still pass; full suite green; workflows parse — G1–G3.
- AC-5 Nothing outside Touchpoints changed — G5.
- AC-6 (post-merge, known-gap) runs land on the cron's UTC day — `gh run list`.

## Phase Completion Rules

- Green offline gates = `CODE DONE`, not `VERIFIED`; VERIFIED needs AC-6 after merge.
- Touching an out-of-scope file is stop-and-report.

## Touchpoints
- `.github/workflows/chain-growth-snapshot.yml`, `narrative-snapshot.yml`, `liqtide-snapshot.yml` — cron, header comment, new first step
- `.github/workflows/pairs-refresh-snapshot.yml`, `liquidity-backfill-snapshot.yml` — cron, header comment
- `api/tests/scripts/test_snapshot_workflow_schedules.py` — buffer, docstring, rename, new test
- `api/scripts/BOOTSTRAP.md` — §8 times only
- this task folder

## Public Contracts
None changed. Script dating/archiving logic untouched. Workflow cron times are the only externally visible change (when commits to `main` appear).

## Blast Radius
7 files, all config/docs/test. Risk class: CI/scheduling (deploy/runtime adjacent — manual-first evidence is the post-merge `gh run list` check). HARD OUT OF SCOPE: every `api/` source file (incl. `cache.py`, `pytrends_adapter.py`, `watchlist.py`, `ccxt_adapter.py`, `main.py`, `tests/conftest.py`), `web/`, `process/context/**`, `.gitignore`, deploy/CORS config, other plans.

## Implementation Checklist
1. Edit the five cron lines per D2.
2. Rewrite the five header comments per D7 (no "~2h", "2h20m", "well before", "~3h+" left).
3. Add the D5 step as the first step of the three no-history workflows with cron_hour 12/12/13.
4. Update the guard test per D6.
5. Update BOOTSTRAP.md §8 times.
6. Run gates G1–G6.

## Verification Evidence

| Gate / Scenario | Strategy | Proves SPEC criterion |
|---|---|---|
| G1 guard test file passes (38 existing + 3 new) | Fully-Automated | Schedule meets 10h budget, stagger, safety shape unchanged |
| G2 full api suite green | Fully-Automated | No regression |
| G3 YAML parse of all five workflows | Fully-Automated | Workflows valid |
| G4 stale-claim grep empty | Fully-Automated | False comments removed |
| G5 scope guard diff | Fully-Automated | Nothing outside touchpoints changed |
| G6 guard step shell logic (bash with fake hour) | Fully-Automated | Warning fires only when now_hour < cron_hour |
| Post-merge `gh run list` started-at vs cron for 3+ nights | Agent-Probe (known-gap here) | Runs actually land on the intended UTC day |

## Test Infra Improvement Notes
(none identified yet) — observed scheduler delay is structurally not testable offline; the runtime warning is the only in-repo signal.

## Resume and Execution Handoff
1. Selected plan: `process/general-plans/active/pipeline-completeness_28-09-26/pipeline-completeness-cron-timing_PLAN_29-09-26.md`
2. Last completed: PLAN + VALIDATE (fast mode)
3. Validate-contract: written (below), Gate: PASS
4. Context loaded: all five workflows, the guard test, BOOTSTRAP.md §8, `snapshot_narrative.py` (has_row dedupe), `snapshot_chain_growth.py` (utc_now dating), all-context.md (LiqTide publish window)
5. Next: ENTER EXECUTE MODE → vc-execute-agent (opus) applies checklist 1–5, then vc-tester runs G1–G6.

## Validate Contract

generated-by: outer-pvl
date: 2026-09-29
Date: 2026-09-29
Gate: PASS

**V1:** plan file exists; blast radius explicit; no Inner Loop Refresh Note.

**V2/V3 (inline single-agent simulation):**

| Layer 1 | Status | Note |
|---|---|---|
| Infra fit | PASS | Cron syntax unchanged shape `M H * * *`; `_start_minute` regex accepts it |
| Test coverage | PASS | Existing 38 tests pass on end state (checked: stagger ≥30, 13:17+600=1397<1440) |
| Breaking changes | PASS | No script/contract change |
| Security | PASS | Permissions/triggers unchanged; guard step has no secrets, no `${{ }}` interpolation of untrusted input |

| Layer 2 | Status | Note |
|---|---|---|
| Crons (D2) | PASS | All 5 ≤ 13:17; latest 13:17+600 < 1440 |
| Guard step (D5) | PASS | Placed at `steps[0]`; does not match existing tests' commit/fail/warn-on-exit-2 lookups (warn test only covers the two new workflows) |
| Test edits (D6) | PASS | `_steps()` requires single job `snapshot` — holds for all five |
| Comments (D7) | PASS | G4 grep defined against exact stale phrases |

Totals: 0 FAILs / 0 CONCERNs → **Net Gate: PASS**

**Test gates (offline, run by vc-tester from repo root):**
- G1 `uv run --project api pytest api/tests/scripts/test_snapshot_workflow_schedules.py -q` → 41+ passed, 0 failed
- G2 `uv run --project api pytest api/ -q` → 0 failed (baseline count recorded by tester before EXECUTE)
- G3 `uv run --project api python -c "import yaml,glob; [yaml.safe_load(open(f)) for f in glob.glob('.github/workflows/*.yml')]; print('ok')"` → `ok`
- G4 `grep -rnE "~2h|2h20m|well before UTC midnight|~3h\+|21:10" .github/workflows api/tests/scripts/test_snapshot_workflow_schedules.py api/scripts/BOOTSTRAP.md` → no output (exit 1)
- G5 `git diff --name-only HEAD` ⊆ {five workflows, the guard test, `api/scripts/BOOTSTRAP.md`, this task folder}
- G6 for each no-history workflow: extract the guard step's `run` and execute with a stubbed `date` (PATH shim returning hour cron_hour−1 → expect `::warning::`; returning cron_hour → expect no output), exit 0 both cases

**Execute-agent instructions:**
- E1 Use `10#` in the hour arithmetic (08/09 are invalid octal otherwise).
- E2 Keep strict `git add <dir>` lines in the three legacy workflows byte-identical.
- E3 Do not touch any `api/` source file; no git add/commit.

**Accepted known-gaps:**
- K1 Real scheduler delay and cron firing cannot be observed from this container; verify after merge with `gh run list --workflow <file> --json startedAt,createdAt` for 3+ nights: every no-history run must start on the cron's UTC day.
- K2 Merge-day gap (D4): user runs `gh workflow run` for the three no-history workflows after merge if merged after 12:47 UTC.
- K3 Guard step cannot detect delays that wrap a full day or runs close-but-not-past midnight.

## Autonomous Goal Block
SESSION GOAL: T27 cron timing — 10h delay budget, midnight-crossing warning
Next phase: EXECUTE: process/general-plans/active/pipeline-completeness_28-09-26/pipeline-completeness-cron-timing_PLAN_29-09-26.md
Hard stops: no api/ source edits; no push/merge; no git commit without request
Gates: G1–G6 above
