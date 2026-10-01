---
name: plan:pipeline-completeness-cron-timing
description: "Move all five nightly workflows earlier for a 10h scheduler-delay budget, add a crossed-midnight runtime warning, and fix the false ~2h-late comments and guard test"
date: 29-09-26
feature: pipeline-completeness
---

# Pipeline Completeness — Cron Timing (T27) PLAN

Date: 29-09-26
Complexity: SIMPLE (config + one test file; no application source)
Status: ⏳ PLANNED — VALIDATE re-run 2026-10-01 after PVL supplement cycle 1: all 8 concerns RESOLVED, 0 FAIL, verdict CONDITIONAL on recorded structural gaps K1-K4 only (no human accepted them; autonomous-run policy). Ready for EXECUTE (opus vc-execute-agent), then spawned vc-tester EVL.
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
- Observed max 5h01m and growing fast: the last day's increments were about +2h (chain-growth +2h13m, narrative +1h55m, liqtide +1h54m). At that rate a 10h budget could be consumed within days, so K1 requires checking the first 2-3 nights after merge, not just "3+". 8h = observed max + ~60%; 10h = ~2x observed max. Chose 10h because the trend is rising and moving earlier costs nothing for these sources.
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
- Publish timing: LiqTide publishes ~00:25–01:12 UTC; a 13:17 cron fires ~12h after publish. Archive is keyed by `generated_utc[:10]`, so even a very late run captures the right day as long as it runs before the *next* publish (~00:25-01:12 next day). Remaining tolerance at the new crons: narrative 24:00 − 12:47 = 11h13m; liqtide ~24:25 − 13:17 = ~11h08m (roughly equal; liqtide is not more tolerant). Narrative sources (pytrends "now 7-d", Reddit search, CoinGecko trending) are continuous — no publish gate. growthepie/L2BEAT are full revisable series; any time of day works.
- Rejected: keeping catch-up jobs late with a separate smaller buffer — adds a second test constant for no gain; uniform budget is simpler.
- Rejected: putting catch-up jobs after the no-history jobs — not needed; they don't push to tracked dirs today (inert commit) and order among catch-up jobs doesn't matter.

### D3 — Catch-up workflows (pairs, liquidity): why late/wrong-day is harmless
- `refresh_cache`, `backfill_primaries`, `compute_pairs` are idempotent full re-fetch/recompute; the next run repairs anything; commit steps are inert today (gitignored dirs, D1).
- OHLCV tail bar: at 11:17 UTC (and at the old 19:17) the latest daily bar is the **in-progress** current-UTC-day bar; the previous day's bar is complete. Moving earlier only makes that tail bar more partial; the next night's run overwrites it. Behavior class unchanged; no script change.

### D4 — Narrative transition day (and the other two)
- Points are dated by the UTC day the run executes; moving 18:17 → 12:47 stays within the same UTC day, so a point still represents "the day it ran". Day-dating is unchanged, but see K4: pytrends' hourly last-point sampling hour shifts with the cron, so "no meaning change" holds for the date only, not for the pytrends reading's diurnal phase (Reddit, CoinGecko, exchange are rolling windows and unaffected).
- Duplicates are harmless: `snapshot_narrative.py` checks `has_row(...)` per (source, key, date) and skips — a second run on the same UTC day writes nothing. LiqTide archive is first-write/no-overwrite keyed by `generated_utc[:10]`; chain-growth merges series.
- Gap risk (K2, per workflow): GitHub reads the cron from `main` at trigger time. A workflow merged after its OWN new cron time and before its old slot has no scheduled run that UTC day.
  - narrative: that day's point is lost.
  - liqtide: that day's file is PERMANENTLY lost if the workflow is merged after 13:17 and no manual run happens before the ~00:25 UTC publish (the next publish overwrites it; Standing Rule 8).
  - chain-growth: harmless (full revisable series).
  - The OLD crons may already be crossing midnight, so merge as early as possible. **User action at merge:** if merged after 12:17 / 12:47 / 13:17 respectively, run `gh workflow run chain-growth-snapshot.yml`, `narrative-snapshot.yml`, `liqtide-snapshot.yml` once the same UTC day; the `has_row` skip makes a duplicate safe.

### D5 — Runtime guard (kept: cheap, one step, testable)
First step (before checkout, so it measures start time) in each of the three no-history workflows, schedule-only:

```yaml
      - name: Warn when the run crossed UTC midnight
        if: github.event_name == 'schedule'
        run: |
          cron_hour=12   # must equal this workflow's cron hour
          now_hour=$((10#$(date -u +%H)))
          if [ "$now_hour" -lt "$cron_hour" ]; then
            echo "::warning::scheduled for ${cron_hour}:xx UTC but started at $(date -u +%H:%M) UTC - the run crossed UTC midnight; today's no-history point may be dated the wrong day"
          fi
```
(`cron_hour` = 12, 12, 13 for chain-growth, narrative, liqtide.) Never fails the job.
- Why `if: github.event_name == 'schedule'`: a manual `workflow_dispatch` before the cron hour would otherwise emit a false midnight-crossing warning, including the manual runs K2 tells the user to trigger at merge time (a liqtide dispatch at 12:47-12:59 would warn). Proven on a scratch copy: guard tests pass with the schedule-only assertion and fail without the `if`.
- Limitation stated honestly (K3): the guard detects only "started after UTC midnight" (hour wrapped to a value below the cron hour). A start close to but before midnight is not flagged, and a delay of 24h or more wraps back past the cron hour and is not detected.
- Rejected: failing the job — the data is already lost or mis-dated; failing blocks the commit of whatever was fetched. Rejected: a delay-threshold check — needs the scheduled timestamp, which Actions doesn't expose to the job.

### D6 — Guard-test changes (`api/tests/scripts/test_snapshot_workflow_schedules.py`)
- `SCHEDULER_DELAY_BUFFER_MIN = 600`; rename `test_cron_starts_at_least_3h_before_utc_midnight` → `test_cron_leaves_scheduler_delay_budget_before_utc_midnight` and fix its message.
- Rewrite module docstring: measured delays 2h39m–5h01m (09-27/09-28, `gh`/actions list, recorded 2026-09-29), growing; 10h budget; test pins schedule only, the runtime step catches real crossings.
- Add `NO_HISTORY = {"chain-growth-snapshot.yml", "narrative-snapshot.yml", "liqtide-snapshot.yml"}` and `test_no_history_workflows_warn_on_midnight_crossing` (parametrized): the step named "Warn when the run crossed UTC midnight" exists, is `steps[0]`, has `if == "github.event_name == 'schedule'"` (not "no `if`"), contains `::warning::`, no `exit 1`, and its `cron_hour=(\d+)` equals the hour parsed from `_crons(name)[0]`.
- Unchanged and still passing: stagger, triggers/permissions/concurrency, retry-push, strict `git add <dir>` for the three legacy workflows and tolerant form for the two new ones, no-force-add, module invocation, pairs ordering/unconditional compute, crash-skips-commit, warn-on-exit-2 (only matches `::warning::` steps in the two new workflows, which get no guard step), tolerant-staging subprocess tests.

### D7 — Comment fixes
Replace every "~2h late (observed up to ~2h20m)" / "lands well before UTC midnight" / "~3h+ of margin" claim in all five workflow headers with: "GitHub started these runs 2h39m–5h01m late on 2026-09-27/28 (measured from the Actions run list, 2026-09-29), and the delay was growing; scheduled HH:MM UTC to survive a 10h delay budget." Plus per-file source-specific text (LiqTide publish window; narrative wrong-day loss; catch-up harmlessness + partial tail bar). Update BOOTSTRAP.md §8 times (19:17/19:47 → 11:17/11:47).
- Stagger sentences (E4): after the reorder pairs is first, so the pairs header ("30 minutes after liqtide (18:47)") and liquidity header ("after pairs (19:17)") become false. New pairs sentence: runs first of the five, 30 minutes before liquidity-backfill and 60 minutes before chain-growth. New liquidity sentence: runs 30 minutes after pairs and 30 minutes before chain-growth. The chain-growth, narrative and liqtide neighbour sentences (chain → narrative → liqtide order, 30-minute gaps) stay true; drop every old clock time (17:47/18:17/18:47/19:17/19:47) from all comments.

## Acceptance Criteria

- AC-1 All five crons start ≤ 13:59 UTC (10h budget), ≥ 20 min apart — G1.
- AC-2 Three no-history workflows have a first-step midnight-crossing warning that is schedule-only (`if == "github.event_name == 'schedule'"`) and whose hour matches the cron — G1, G6.
- AC-3 No stale "~2h late" / "well before midnight" / old clock-time / "after liqtide-snapshot" claims remain — G4a, G4b.
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
2. Rewrite the five header comments per D7, including the new pairs/liquidity stagger sentences (no "~2h", "2h20m", "well before", "~3h+", old clock times, or "after liqtide-snapshot" left).
3. Add the D5 step (with `if: github.event_name == 'schedule'` and `10#`) as the first step of the three no-history workflows with cron_hour 12/12/13.
4. Update the guard test per D6.
5. Update BOOTSTRAP.md §8 times.
6. Run gates G1–G6 (spawned vc-tester; record the G2 baseline pass count BEFORE EXECUTE).

## Verification Evidence

| Gate / Scenario | Strategy | Proves SPEC criterion |
|---|---|---|
| G1 guard test file passes: 41 passed (38 existing + 3 new), **0 skipped** (use `-rs`; a skip means PyYAML is missing and structural tests silently did not run) — AC-1, AC-2 | Fully-Automated | Schedule meets 10h budget, stagger, schedule-only guard shape |
| G2 full api suite green (baseline count recorded before EXECUTE; must be baseline + 3) — AC-4 | Fully-Automated | No regression |
| G3 YAML parse of all five workflows — AC-4 | Fully-Automated | Workflows valid |
| G4a stale-text grep (`~2h`, `2h20m`, `~3h+`, `21:10`, `3h before`, `least 3h`, `least_3h`, `lands well`, `well before UTC midnight`) over workflows, guard test, BOOTSTRAP.md -> no output — AC-3 | Fully-Automated | False comments removed (`lands well` catches the phrase wrapped across two lines; `least_3h` catches an un-renamed `test_cron_starts_at_least_3h_...`, which no other alternative matches and G1's count cannot see) |
| G4b stale clock-time/cron grep (17:47, 18:17, 18:47, 19:17, 19:47 and old cron strings) -> no output, plus `grep -n "after liqtide-snapshot"` on the pairs workflow -> no output — AC-3 | Fully-Automated | Old times and stale order statements removed |
| G5 scope guard: `git status --porcelain` (sees untracked files, unlike `git diff --name-only HEAD`) lists only the five workflows, the guard test, BOOTSTRAP.md, or this task folder; plus `git diff --numstat HEAD -- api/scripts/BOOTSTRAP.md` <= `2 2` — AC-5 | Fully-Automated | Nothing outside touchpoints changed |
| G6 guard step shell logic: the 72-case script in the Validate Contract (3 workflows x 24 hours, PATH-shim `date`, asserts `if` is schedule-only, rc 0, empty stderr, warning iff hour < cron_hour) — AC-2 | Fully-Automated | Warning fires only when now_hour < cron_hour, only on schedule runs |
| Post-merge `gh run list` started-at vs cron for the first 2-3 nights (K1) | Agent-Probe (known-gap here) | Runs actually land on the intended UTC day |

## Known Gaps (recorded, none accepted by a human)
- K1 Real scheduler delay is unobservable offline. Delay grew by about +2h in the last day (chain +2h13m, narrative +1h55m, liqtide +1h54m), so check `gh run list --workflow <file> --json event,createdAt,startedAt` the first 2-3 nights after merge; every no-history run must start on the cron's UTC day.
- K2 Merge-day loss window per workflow — see D4 (liqtide's file is permanently lost; narrative loses the day's point; chain-growth harmless). Merge early; dispatch manually if after the new cron time.
- K3 Guard detects only "started after UTC midnight" (see D5).
- K4 pytrends hourly last-point sampling hour shifts from ~18:17 to ~12:47, a one-time diurnal-phase discontinuity in the archived series (see D4).

## Test Infra Improvement Notes
(none identified yet) — observed scheduler delay is structurally not testable offline; the runtime warning is the only in-repo signal.

## Resume and Execution Handoff
1. Selected plan: `process/general-plans/active/pipeline-completeness_28-09-26/pipeline-completeness-cron-timing_PLAN_29-09-26.md`
2. Last completed: PLAN, VALIDATE first pass (independent), PVL supplement cycle 1 (2026-10-01, 8 gaps applied), and the VALIDATE re-run (2026-10-01: all 8 RESOLVED, empirically re-proven on a scratch end state).
3. Validate-contract: written 2026-10-01, status CONDITIONAL after 1 PVL fix cycle. It rests on recorded structural gaps K1-K4 only; NO HUMAN accepted them (autonomous-run policy). K2 is an ACTION for the user at merge time.
4. Context loaded: all five workflows, the guard test, BOOTSTRAP.md §8, `snapshot_narrative.py` (has_row dedupe), `snapshot_chain_growth.py` (utc_now dating), all-context.md (LiqTide publish window)
5. Next: ENTER EXECUTE MODE → vc-execute-agent (opus) applies checklist 1–5, then a spawned vc-tester runs G1–G6 (G2 baseline recorded in the contract: 817 passed / 5 deselected, so the post-EXECUTE count must be 820).
6. UPDATE PROCESS handoff (NOT for EXECUTE to edit): `process/context/all-context.md` (about lines 14, 199–213, 356, 706–708) and `process/context/data-sources/all-data-sources.md:139` still state the old 17:47/18:17/18:47 cron times and the "~2h" delay; correct them at UPDATE PROCESS.

## Validate Contract

Status: CONDITIONAL
Date: 01-10-26
date: 2026-10-01
generated-by: outer-pvl
supersedes: 2026-09-29 (outer-pvl) — first-pass independent contract (0 FAIL / 8 CONCERN); this re-run, after PVL supplement cycle 1, has current evidence

Parallel strategy: sequential
Rationale: one validator ran the four dimensions and the section checks itself, backed by scratch-copy experiments (no Layer 1/2 subagents spawned). EXECUTE score 2/7 (S6 CI/scheduling-adjacent, S7 7 files in blast radius); three workflows share one identical step and one test file, so consistency beats speed. Recommended for EXECUTE: 1 vc-execute-agent (opus), then 1 vc-tester (sonnet, EVL). Alternatives: parallel subagents (2) — saves minutes, adds a shared-constant coordination risk; workflow / agent team — over-scoped.

Verdict: **Gate: CONDITIONAL — 0 FAIL / 0 new CONCERN after 1 PVL fix cycle.** All eight supplement items from cycle 1 are RESOLVED (table below). What remains is structural and recorded (K1-K4, stale context docs); none can be closed offline. **NO HUMAN accepted these gaps** — they are carried under the autonomous-run policy, and K2 is an ACTION for the user at merge time. `PHASE_COMPLETE: VALIDATE` is legal: CONDITIONAL with 1 recorded fix cycle (`results.tsv` has the `[cron-timing]` baseline row 6 and cycle-1 row 7; `wc -l` = 9 ≥ 3).

**Cycle-1 supplement verification (each checked against the plan text):**

| # | Concern | Status | Where / wording |
|---|---|---|---|
| 1 | Guard false-warns on `workflow_dispatch` | RESOLVED | D5 YAML carries `if: github.event_name == 'schedule'` + rationale; D6 test asserts that exact value; checklist 3; E1; AC-2 |
| 2 | G4 partly dead | RESOLVED | G4a/G4b in Verification Evidence and the gate list. One further hole found and patched here: `least 3h` cannot match the un-renamed test name `test_cron_starts_at_least_3h_...` (underscores) and G1's count cannot see a missed rename, so `least_3h` was added to G4a (plan row and gate list) |
| 3 | Pairs/liquidity header sentences false after reorder | RESOLVED | D7 stagger paragraph + checklist 2 + E4 give the new sentences; G4b `after liqtide-snapshot` grep |
| 4 | K2 per-workflow, K4 pytrends, D2 tolerances, D1 growth rate | RESOLVED | D4 (per-workflow K2 incl. LiqTide permanent loss), K4, D2 (narrative 11h13m, liqtide ~11h08m, arithmetic re-checked), D1 (+2h/day; chain +2h13m, narrative +1h55m, liqtide +1h54m, re-computed from the Problem table) |
| 5 | G5 blind to untracked files | RESOLVED | G5 = `git status --porcelain` + BOOTSTRAP numstat; proven satisfiable (see Evidence) |
| 6 | G1 skips, G6 unspecified | RESOLVED | G1 `-rs`, 0 skipped; G6 script embedded and executed (see Evidence) |
| 7 | Context docs stale | RESOLVED (handoff) | Resume item 6 routes `all-context.md` and `all-data-sources.md:139` to UPDATE PROCESS; line 356 added to the list by this pass |
| 8 | Stale literal PASS verdict | RESOLVED | the mechanical PASS-verdict grep on the plan returns 0 before and after this write (this contract writes only the CONDITIONAL verdict) |

**Evidence (scratch copy in the session scratchpad; the repo was never modified, `git status --porcelain` empty before and after, including after the full suite):**
- Baseline on the current tree: guard test file 38 passed, 0 skipped; full api suite **817 passed, 5 deselected** (G2 baseline; post-EXECUTE count must be 820).
- End state built on scratch (crons 11:17/11:47/12:17/12:47/13:17, buffer 600, schedule-only guard step as `steps[0]`, renamed test, new parametrized test, BOOTSTRAP times): **41 passed, 0 skipped**. G3 `ok` on 5 workflows (current and end state).
- Mutations, each failing exactly the intended assertion: drop the `if:` (guard test fails at the `if` assertion); wrong `cron_hour` (13→12); cron 14:17 (budget test + cron_hour test); guard not `steps[0]`.
- G4a/G4b checked both directions: on the CURRENT tree they match (~10 and ~18 lines, plus `after liqtide-snapshot` at pairs:23, plus `least_3h` at test:119); on the end state all three return no output (rc 1). Inert alternatives, harmless: `21:10` and `least 3h` cannot match in the scoped files (the gate as a whole still fails correctly).
- G5: the BOOTSTRAP §8 edit is exactly 2 lines (diff 2 removed / 2 added → numstat `2 2`), so the check is satisfiable and fails on any wider edit. The tree stays clean after the full G2 run (no stray untracked files).
- G6: the embedded script extracted from this plan and run from the scratch repo root: `G6 ok` (72 cases) on the end state. It fails on: `if:` removed, `-lt` mutated to `-le` (spurious warning at the cron hour), `10#` removed (`08`/`09` crash), and on the current tree (no guard step). The stubbed clock exercises the shell only; the `if:` is a workflow-level condition, covered by a separate assertion in G1 and G6.
- Scope: touchpoints exactly the five workflows, the guard test, BOOTSTRAP.md §8, this task folder; Blast Radius and Public Contracts keep every `api/` source file, `web/`, `process/context/**`, deploy/CORS, `pytrends_adapter.py` (+ test), `watchlist.py`, `ccxt_adapter.py`, `conftest.py`, `.gitignore` out of scope; no script's archiving or dating behaviour changes.
- No gate that cannot pass or cannot fail remains on the intended end state.

Test gates (C3 table):

| criterion id | behavior | strategy | proving test | gap-resolution |
|---|---|---|---|---|
| AC-1 | all five crons start <= 13:59 UTC and >= 20 min apart | Fully-Automated | G1: `test_cron_leaves_scheduler_delay_budget_before_utc_midnight[x5]`, `test_crons_are_staggered` | B |
| AC-2 | the 3 no-history workflows have a first-step, schedule-only midnight-crossing warning whose hour == the cron hour | Fully-Automated | G1: `test_no_history_workflows_warn_on_midnight_crossing[x3]` (asserts `steps[0]`, `if == "github.event_name == 'schedule'"`, `::warning::`, no `exit 1`, hour == cron hour) | B |
| AC-2 | the guard shell warns iff hour < cron_hour, exits 0, no stderr | Fully-Automated | G6 (script below) | B |
| AC-3 | no stale timing claims remain | Fully-Automated | G4a + G4b | B |
| AC-4 | existing 38 assertions, full suite, workflow parse unchanged | Fully-Automated | G1, G2, G3 | A |
| AC-5 | nothing outside touchpoints changed | Fully-Automated | G5 | A |
| AC-6 | real scheduled runs start on the cron's UTC day | Agent-Probe | post-merge `gh run list --workflow <file> --json event,createdAt,startedAt` (K1) | C |

Failing stub:
def test_no_history_workflows_warn_on_midnight_crossing(name): raise AssertionError("NOT IMPLEMENTED — TDD stub: guard is steps[0], schedule-only, hour == cron hour")
Failing stub:
def test_cron_leaves_scheduler_delay_budget_before_utc_midnight(name): raise AssertionError("NOT IMPLEMENTED — TDD stub: start + 600 < 1440 for every cron")

Legacy line form:
- schedule + guard shape: [Fully-automated: G1] | shell logic: [Fully-automated: G6] | stale text: [Fully-automated: G4a/G4b] | scope: [Fully-automated: G5] | real cron firing: [agent-probe: post-merge gh run list] | [known-gap: real scheduler delay, documented K1]

**Final offline gate list (run from repo root by a spawned vc-tester):**
- G1 `uv run --project api pytest api/tests/scripts/test_snapshot_workflow_schedules.py -q -rs` -> 41 passed, 0 failed, **0 skipped** (a skip means PyYAML was missing and the structural tests silently did not run; that is a failure).
- G2 `uv run --project api pytest api/ -q` -> 0 failed; baseline recorded by this validation = 817 passed / 5 deselected on the current tree, so after EXECUTE it must read **820 passed / 5 deselected** (tester re-records the baseline if the tree has moved).
- G3 `uv run --project api python -c "import yaml,glob; [yaml.safe_load(open(f)) for f in glob.glob('.github/workflows/*.yml')]; print('ok')"` -> `ok`.
- G4a `grep -rnE "~2h|2h20m|~3h\+|21:10|3h before|least 3h|least_3h|lands well|well before UTC midnight" .github/workflows api/tests/scripts/test_snapshot_workflow_schedules.py api/scripts/BOOTSTRAP.md` -> no output (exit 1).
- G4b `grep -rnE "\b(17:47|18:17|18:47|19:17|19:47)\b|\"(47 17|17 18|47 18|17 19|47 19) \* \* \*\"" .github/workflows api/tests/scripts/test_snapshot_workflow_schedules.py api/scripts/BOOTSTRAP.md` -> no output, AND `grep -n "after liqtide-snapshot" .github/workflows/pairs-refresh-snapshot.yml` -> no output.
- G5 `git status --porcelain` (NOT `git diff --name-only HEAD`, which cannot see new untracked files) -> every path is one of the five workflows, `api/tests/scripts/test_snapshot_workflow_schedules.py`, `api/scripts/BOOTSTRAP.md`, or under `process/general-plans/active/pipeline-completeness_28-09-26/`; plus `git diff --numstat HEAD -- api/scripts/BOOTSTRAP.md` <= `2 2` (times only).
- G6 from repo root, `uv run --project api python <script>` where the script loads `steps[0]` of chain-growth (12), narrative (12), liqtide (13), asserts name `Warn when the run crossed UTC midnight`, `if == "github.event_name == 'schedule'"` and `cron_hour=` equals the cron hour, then for hours 00..23 runs `bash -e -c <run>` with a PATH-shim `date` (`+%H` -> `$FAKE_HOUR`, `+%H:%M` -> `$FAKE_HOUR:05`) and asserts rc 0, empty stderr, `::warning::` present iff `int(hour,10) < cron_hour` (72 cases). Reference implementation (executed on the scratch end state: green; red under the four mutations above) — save to a temp file OUTSIDE the repo and run from repo root:

```python
import glob, os, pathlib, stat, subprocess, tempfile, re, yaml
shim = pathlib.Path(tempfile.mkdtemp()) / "date"
shim.write_text('#!/bin/bash\ncase "$*" in *"+%H:%M"*) echo "$FAKE_HOUR:05";; *"+%H"*) echo "$FAKE_HOUR";; *) exec /bin/date "$@";; esac\n')
shim.chmod(shim.stat().st_mode | stat.S_IEXEC)
bad = 0
for name, want in (("chain-growth-snapshot.yml", 12), ("narrative-snapshot.yml", 12), ("liqtide-snapshot.yml", 13)):
    step = yaml.safe_load(open(f".github/workflows/{name}"))["jobs"]["snapshot"]["steps"][0]
    assert step["name"] == "Warn when the run crossed UTC midnight", name
    assert step.get("if") == "github.event_name == 'schedule'", f"{name}: guard not schedule-only: {step.get('if')!r}"
    run = step["run"]
    assert int(re.search(r"cron_hour=(\d+)", run).group(1)) == want, name
    for h in range(24):
        hh = f"{h:02d}"
        p = subprocess.run(["bash", "-e", "-c", run], capture_output=True, text=True,
                           env={**os.environ, "PATH": f"{shim.parent}:{os.environ['PATH']}", "FAKE_HOUR": hh})
        warned = "::warning::" in p.stdout
        ok = p.returncode == 0 and p.stderr == "" and warned == (h < want)
        bad += not ok
        if not ok: print("FAIL", name, hh, p.returncode, repr(p.stdout[:60]), repr(p.stderr[:80]))
print("G6", "FAIL" if bad else "ok")
raise SystemExit(1 if bad else 0)
```

**Execute-agent instructions:**
- E1 Guard step MUST carry `if: github.event_name == 'schedule'`; `10#` in the hour arithmetic; never `exit 1`; it is `steps[0]` (before checkout).
- E2 Keep strict `git add <dir>` lines in the three legacy workflows byte-identical; keep tolerant lines in the two new ones.
- E3 Do not touch any `api/` source file or `process/context/**`; no git add/commit/push.
- E4 Rewrite pairs and liquidity header stagger sentences for the NEW order: pairs first (30 min before liquidity, 60 before chain-growth); liquidity 30 after pairs and 30 before chain-growth. Chain/narrative/liqtide neighbor sentences remain true; drop every old clock time; keep no "~2h", "2h20m", "~3h+", "lands well", "well before UTC midnight".
- E5 Test edit exactly per D6 with the `if` assertion in place of "no if"; rename `test_cron_starts_at_least_3h_before_utc_midnight` (no `least_3h` may remain); do not weaken any existing assertion.
- E6 BOOTSTRAP.md §8: change only the two time strings (19:17→11:17, 19:47→11:47); numstat must stay `2 2`.

**Open gaps (none accepted by any human; carried under the autonomous-run policy):**
- K1 Real scheduler delay and cron firing unobservable here; post-merge `gh run list` for the first 2-3 nights (the delay grew ~2h/day recently, so a 10h budget could be consumed within days); every no-history run must start on the cron's UTC day.
- K2 Merge-day loss window, per workflow — **ACTION for the user at merge time.** A workflow merged after its OWN new cron time and before its old slot has no scheduled run that UTC day. narrative: day's point lost; LiqTide: that day's file (published ~00:25) is overwritten at the next publish and never recoverable (Standing Rule 8) — dispatch before ~00:25 UTC; chain-growth: harmless. If merged after 12:17 / 12:47 / 13:17 respectively, run `gh workflow run chain-growth-snapshot.yml` / `narrative-snapshot.yml` / `liqtide-snapshot.yml` the same UTC day; merge as early as possible.
- K3 Guard detects only "started after UTC midnight"; a start close to but before midnight, or a delay >= 24h, is undetected.
- K4 The narrative run moving from ~18:17 to ~12:47 shifts the sampling hour of pytrends' single hourly last-complete-hour reading; the archived series has a one-time diurnal-phase discontinuity. Reddit/CoinGecko/exchange are rolling windows and unaffected.
- Out-of-scope stale docs (UPDATE PROCESS must fix; forbidden to EXECUTE): `process/context/all-context.md` (about lines 14, 199-213, 356, 706-708) and `process/context/data-sources/all-data-sources.md:139` state the old times and the "~2h" delay.

**What This Coverage Does NOT Prove:**
- G1/G3: only that the YAML text has the intended cron/step shape; not that GitHub honours the schedule or how late it starts (K1).
- G6: only the shell arithmetic on a stubbed `date`; not that Actions evaluates `if: github.event_name == 'schedule'` as expected on a real run (G1/G6 assert the string only), and not delays >= 24h (K3).
- G2: no regression in the existing suite; it does not exercise any workflow.
- G4a/G4b: absence of the enumerated stale strings; not that every remaining comment is factually right (E4 and reviewer read cover order statements).
- G5: nothing outside the touchpoint list changed; not that the BOOTSTRAP §8 wording is good.
- Nothing offline proves data-day correctness at the new times (K2/K4) or that a 10h budget is enough (K1).

Dimension findings:
- Infra fit: PASS — guard is schedule-only, `steps[0]` before checkout works, crons parse, 13:17 + 600 = 1397 < 1440; delay-growth rationale now matches the measured numbers.
- Test coverage: PASS — G1-G6 each proven satisfiable on the end state and failing under mutation or on the old text; one residual hole (un-renamed test name) closed by `least_3h` in G4a.
- Breaking changes: PASS — no script, contract, dating or archive-key change; 38 existing tests unchanged and green.
- Security surface: PASS — permissions/triggers/concurrency unchanged; guard has no secrets and no `${{ }}` interpolation.
- Section D2 crons: PASS — 41 passed; boundary 13:59 ok, 14:00 fails; min stagger 30.
- Section D5 guard: PASS — schedule-only `if`; shell proven for all 24 hours x 3 workflows.
- Section D6 test edits: PASS — mutation-checked.
- Section D7 comments: PASS — new stagger sentences specified (E4); stale text gated by G4a/G4b.
- Section D4 data semantics: CONCERN (recorded, not fixable offline) — K2 per-workflow merge-day loss and K4 pytrends sampling-hour shift.
- Handoff hygiene: PASS — Resume updated; no literal stale verdict.

Accepted by: none — NO HUMAN accepted any gap in this validation. K1-K4 and the stale-docs item are structural/recorded; the CONDITIONAL verdict is carried under the autonomous-run policy, and K2 is an ACTION for the user at merge time.

Gate: CONDITIONAL

## Autonomous Goal Block
SESSION GOAL: T27 cron timing — 10h delay budget, midnight-crossing warning
Next phase: EXECUTE: process/general-plans/active/pipeline-completeness_28-09-26/pipeline-completeness-cron-timing_PLAN_29-09-26.md
Hard stops: no api/ source edits; no push/merge; no git commit without request
Gates: G1–G6 above
