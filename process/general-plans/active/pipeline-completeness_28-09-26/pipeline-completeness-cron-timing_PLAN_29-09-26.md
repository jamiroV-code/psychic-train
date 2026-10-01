---
name: plan:pipeline-completeness-cron-timing
description: "Move all five nightly workflows earlier for a 10h scheduler-delay budget, add a crossed-midnight runtime warning, and fix the false ~2h-late comments and guard test"
date: 29-09-26
feature: pipeline-completeness
---

# Pipeline Completeness — Cron Timing (T27) PLAN

Date: 29-09-26
Complexity: SIMPLE (config + one test file; no application source)
Status: ⏳ PLANNED — VALIDATE returned CONDITIONAL (0 FAIL / 8 CONCERN); PVL supplement cycle 1 applied 2026-10-01 (8 gaps folded into the plan body); VALIDATE must re-run from V1 before EXECUTE
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
| G4a stale-text grep (`~2h`, `2h20m`, `~3h+`, `21:10`, `3h before`, `least 3h`, `lands well`, `well before UTC midnight`) over workflows, guard test, BOOTSTRAP.md -> no output — AC-3 | Fully-Automated | False comments removed (`lands well` catches the phrase wrapped across two lines) |
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
2. Last completed: PLAN, VALIDATE first pass (independent), and PVL supplement cycle 1 (2026-10-01, 8 gaps applied to the plan body).
3. Validate-contract: written, status CONDITIONAL (first pass, not terminal); it must be re-run from V1 against this supplemented plan. EXECUTE is not legal until VALIDATE records a passing verdict or a supplement cycle completes with accepted gaps.
4. Context loaded: all five workflows, the guard test, BOOTSTRAP.md §8, `snapshot_narrative.py` (has_row dedupe), `snapshot_chain_growth.py` (utc_now dating), all-context.md (LiqTide publish window)
5. Next: orchestrator re-spawns vc-validate-agent from V1; after a passing verdict, ENTER EXECUTE MODE → vc-execute-agent (opus) applies checklist 1–5, then a spawned vc-tester runs G1–G6 (record G2 baseline first).
6. UPDATE PROCESS handoff (NOT for EXECUTE to edit): `process/context/all-context.md` (about lines 14, 199–213, 706–708) and `process/context/data-sources/all-data-sources.md:139` still state the old 17:47/18:17/18:47 cron times and the "~2h" delay; correct them at UPDATE PROCESS.

## Validate Contract

Status: CONDITIONAL
Date: 29-09-26
date: 2026-09-29
generated-by: outer-pvl
supersedes: 2026-09-29 (outer-pvl, inline single-agent contract, verdict PASS) — independent adversarial pass has current evidence; the inline verdict is void

Parallel strategy: sequential
Rationale: this VALIDATE was run as one agent doing the four dimensions and the section checks itself, backed by scratch-copy experiments (no Layer 1/2 subagents were spawned). EXECUTE score 2/7 (S6 CI/scheduling-adjacent, S7 7 files in blast radius); 3 workflow edits share one identical step and one test file, so consistency beats speed. Recommended for EXECUTE: 1 vc-execute-agent (opus) then 1 vc-tester (sonnet, EVL). Alternatives: parallel subagents (2, workflows vs test+docs) — saves minutes, adds a shared-constant coordination risk; workflow/agent team — over-scoped.

Verdict: **Gate: CONDITIONAL — first pass, NOT terminal.** 0 FAIL / 8 CONCERN. The plan is sound in shape (proven on a scratch copy, see Evidence) but the inline PASS was wrong: the specified guard step false-warns on `workflow_dispatch`, and three gates (G4, G5, G6) are dead, blind, or unspecified. Route to a PVL supplement cycle (SUPPLEMENT REQUEST in the validate report), then re-validate from V1. `PHASE_COMPLETE: VALIDATE` is NOT emitted.

**Evidence (scratch copies only; repo untouched):** baseline 38 existing tests pass; with the plan's end state (crons 11:17/11:47/12:17/12:47/13:17, buffer 600, guard step, renamed test, new parametrized test) = 41 passed (38 + 3). 13:17 = 797 + 600 = 1397 < 1440 holds; 14:17 fails the budget test; stagger min gap 30. Mutations (guard removed, wrong `cron_hour`, cron 14:17, 10-min stagger) each fail exactly the intended test. Guard shell, `bash -e`, stub `date`: warns at every hour < cron_hour, silent at cron_hour..23, `10#` handles 08/09 (bare `$((08))` errors), empty/garbage/failing `date` output gives rc 0 with stderr noise and no warning (never fails the job). Guard as `steps[0]` before checkout works (`date` needs no repo). Spurious warning on manual runs CONFIRMED (09:00 dispatch warns for all three; a liqtide dispatch at 12:47-12:59 warns even at the plan's own K2 timing). Fix `if: github.event_name == 'schedule'` proven: tests 41 passed with the schedule-only assertion, and dropping the `if` fails it.

Test gates (C3 table; final list after supplement — G4/G5/G6 below REPLACE the inline versions):

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
- G2 `uv run --project api pytest api/ -q` -> 0 failed; tester records the baseline pass count BEFORE EXECUTE and the count must be baseline + 3.
- G3 `uv run --project api python -c "import yaml,glob; [yaml.safe_load(open(f)) for f in glob.glob('.github/workflows/*.yml')]; print('ok')"` -> `ok`.
- G4a `grep -rnE "~2h|2h20m|~3h\+|21:10|3h before|least 3h|lands well|well before UTC midnight" .github/workflows api/tests/scripts/test_snapshot_workflow_schedules.py api/scripts/BOOTSTRAP.md` -> no output (exit 1). (The inline `well before UTC midnight` alone was dead: in pairs and liquidity the phrase is wrapped across two comment lines and matches 0 times today; `lands well` catches the wrapped form.)
- G4b `grep -rnE "\b(17:47|18:17|18:47|19:17|19:47)\b|\"(47 17|17 18|47 18|17 19|47 19) \* \* \*\"" .github/workflows api/tests/scripts/test_snapshot_workflow_schedules.py api/scripts/BOOTSTRAP.md` -> no output, AND `grep -n "after liqtide-snapshot" .github/workflows/pairs-refresh-snapshot.yml` -> no output. (Proven satisfiable on a scratch end state.)
- G5 `git status --porcelain` (NOT `git diff --name-only HEAD`, which cannot see new untracked files) -> every path is one of the five workflows, `api/tests/scripts/test_snapshot_workflow_schedules.py`, `api/scripts/BOOTSTRAP.md`, or under `process/general-plans/active/pipeline-completeness_28-09-26/`; plus `git diff --numstat HEAD -- api/scripts/BOOTSTRAP.md` <= `2 2` (times only).
- G6 from repo root, `uv run --project api python <script>` where the script: for each of chain-growth (12), narrative (12), liqtide (13) loads `steps[0]` via yaml, asserts name `Warn when the run crossed UTC midnight` and `if == "github.event_name == 'schedule'"` and `cron_hour=` equals the cron hour; then for every hour 00..23 runs `bash -e -c <run>` with a PATH-shim `date` (`+%H` -> `$FAKE_HOUR`, `+%H:%M` -> `$FAKE_HOUR:05`) and asserts rc 0, empty stderr, and `::warning::` present iff `int(hour,10) < cron_hour` (72 cases). Reference implementation (proven green on the scratch end state, red when the `if` is absent) — save to a temp file OUTSIDE the repo and run from repo root:

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
- E1 Guard step MUST carry `if: github.event_name == 'schedule'`; `10#` in the hour arithmetic; never `exit 1`.
- E2 Keep strict `git add <dir>` lines in the three legacy workflows byte-identical; keep tolerant lines in the two new ones.
- E3 Do not touch any `api/` source file or `process/context/**`; no git add/commit/push.
- E4 Rewrite pairs and liquidity header stagger sentences for the NEW order: pairs first (30 min before liquidity, 60 before chain-growth); liquidity 30 after pairs and 30 before chain-growth. Chain/narrative/liqtide neighbor sentences remain true; drop every old clock time.
- E5 Test edit exactly per D6 with the `if` assertion in place of "no if"; do not weaken any existing assertion.

**Open gaps (none accepted by any human):**
- K1 Real scheduler delay and cron firing unobservable here; post-merge `gh run list` for the first 2-3 nights (not just "3+" — the measured delay grew ~2h/day recently, so a 10h budget could be consumed within days if that continues); every no-history run must start on the cron's UTC day.
- K2 Merge-day loss window, per workflow (the inline text framed only narrative at 12:47): a workflow that is merged after its OWN new cron time and before its old slot has no scheduled run that UTC day. narrative: day's point lost; LiqTide: that day's file (published ~00:25) is overwritten at the next publish and never recoverable (Standing Rule 8) — dispatch before ~00:25 UTC; chain-growth: harmless (full revisable series). Correct user action: after merge, `gh workflow run` the three no-history workflows the same UTC day if merged after 12:17/12:47/13:17 respectively; merge as early as possible, the current crons may already be crossing midnight.
- K3 Guard detects only "started after UTC midnight"; a start close to but before midnight, or a delay >= 24h, is undetected.
- K4 (new) Moving the narrative run from ~18:17 to ~12:47 shifts the sampling hour of pytrends' single hourly last-complete-hour reading (`_fetch_live`, `now 7-d`); the archived series has a one-time diurnal-phase discontinuity at the switch. The inline D4 claim "No meaning change" is overstated for pytrends; Reddit/CoinGecko/exchange are rolling windows and unaffected.
- Out-of-scope stale docs (UPDATE PROCESS must fix; forbidden to EXECUTE): `process/context/all-context.md` (cron times at ~lines 14, 199-213, 706-708) and `process/context/data-sources/all-data-sources.md:139` state the old 17:47/18:17/18:47 times and the "~2h" delay.

**What This Coverage Does NOT Prove:**
- G1/G3: only that the YAML text has the intended cron/step shape; not that GitHub honours the schedule or how late it starts (K1).
- G6: only the shell arithmetic on a stubbed `date`; not that Actions' `if: github.event_name == 'schedule'` evaluates as expected on a real run, and not delays >= 24h (K3).
- G2: no regression in the existing suite; it does not exercise any workflow.
- G4a/G4b: absence of the enumerated stale strings; not that every remaining comment is factually right (E4 and reviewer read cover order statements).
- G5: nothing outside the touchpoint list changed; not that the BOOTSTRAP §8 wording is good.
- Nothing offline proves data-day correctness at the new times (K2/K4) or that a 10h budget is enough (K1).

Dimension findings:
- Infra fit: CONCERN — guard step fires on `workflow_dispatch` (false "crossed midnight" warning; also at K2's own manual-run timing for liqtide); D1 rationale says "growing ~1h/day" while the last day's measured increments were ~+2h (narrative +1h55m, chain-growth +2h13m, liqtide +1h54m); cron/step shape itself is valid (parses, `steps[0]` before checkout works).
- Test coverage: CONCERN — G4's `well before UTC midnight` matches 0 times today (wrapped phrase) and G4 misses `3h before`/old clock times; G5 `git diff --name-only HEAD` is blind to untracked files; G6 procedure unspecified; G1 must assert 0 skipped. All corrected in the gate list above.
- Breaking changes: PASS — no script, contract, dating or archive-key change (verified against snapshot_narrative.py has_row, snapshot_chain_growth.py utc_now/merge_onchain_series, snapshot_liqtide.py/`write_liqtide_payload` first-write-by-payload-date); 38 existing tests unchanged and green.
- Security surface: PASS — permissions/triggers/concurrency unchanged; guard has no secrets and no `${{ }}` interpolation.
- Section D2 crons: PASS — proven on scratch (41 passed; boundary 13:59 ok, 14:00 fails).
- Section D5 guard: CONCERN — dispatch false-warn (fix: schedule-only `if`); shell otherwise verified; prose sentence "a delay >= 24h - ... wraps" is garbled.
- Section D6 test edits: PASS with the `if` assertion swapped in (mutation-checked: 4 mutations each caught).
- Section D7 comments: CONCERN — pairs header ("30 minutes after liqtide (18:47)") and liquidity ("after pairs (19:17)") become false/stale after the move and no gate caught them; now G4b + E4.
- Section D4 data semantics: CONCERN — no duplicate/missing point arises from the earlier cron itself (points dated by run day; `has_row` skips a same-day duplicate; LiqTide keyed by `generated_utc[:10]` first-write; chain-growth merge idempotent), BUT the merge-day advice is incomplete (K2), pytrends sampling hour shifts (K4), and D2's "liqtide has ~11h55m more tolerance than narrative" is wrong (narrative 24:00-12:47 = 11h13m; liqtide ~24:25-13:17 = 11h08m).
- Handoff hygiene: CONCERN — Resume section line 3 still contains the literal text of the inline PASS verdict, which falsely satisfies the mechanical PASS-grep that gates EXECUTE; the supplement must change it to CONDITIONAL/current status.

Accepted by: none — NO HUMAN accepted any gap in this validation. K1-K4 and the stale-docs item are structural/recorded, not accepted; CONDITIONAL rests on the SUPPLEMENT REQUEST being applied and re-validated.

Gate: CONDITIONAL

## Autonomous Goal Block
SESSION GOAL: T27 cron timing — 10h delay budget, midnight-crossing warning
Next phase: EXECUTE: process/general-plans/active/pipeline-completeness_28-09-26/pipeline-completeness-cron-timing_PLAN_29-09-26.md
Hard stops: no api/ source edits; no push/merge; no git commit without request
Gates: G1–G6 above
