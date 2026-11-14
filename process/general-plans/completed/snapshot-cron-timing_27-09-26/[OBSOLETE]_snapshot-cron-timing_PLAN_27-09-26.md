---
name: plan:snapshot-cron-timing
description: "Move the three nightly snapshot crons earlier so GitHub's ~2h scheduler delay never pushes a run past UTC midnight; harden liqtide-snapshot.yml; add a pytest schedule guard"
date: 27-09-26
feature: none
---

# Snapshot Cron Timing — SIMPLE Plan

**TL;DR:** GitHub runs our 22:00/23:00/23:30 UTC crons ~2h late, so two of them land after midnight and
date their data as the next day (narrative lost 2026-09-25). Move all three to 17:47 / 18:17 / 18:47 UTC,
give liqtide the concurrency + retry-push the others already have, add a pytest guard, fix stale docs.
No snapshot script changes.

**Complexity**: SIMPLE
**Status**: CODE DONE (27-09-26) — checklist 1–7 applied, gates 1–4 green (guard 13 passed; full api 480 passed / 5 deselected). VERIFIED pending next scheduled runs on `main`.

## Overview
Scheduled snapshot workflows start ~2h late on GitHub; this plan moves them earlier so they never
cross UTC midnight, and hardens the liqtide workflow.

## Acceptance Criteria
- AC-1: crons are `47 17`, `17 18`, `47 18` (chain-growth, narrative, liqtide).
- AC-2: liqtide workflow has a `concurrency` group and the 3-attempt retry push.
- AC-3: new pytest guard passes; full `pytest api/` green.
- AC-4: context docs updated; no stale 22:00/23:00/23:30/22:45 workflow mentions.
- AC-5: no change to snapshot scripts' dating (`api/scripts`, `api/data` untouched).

## Phase Completion Rules
CODE DONE = checklist 1–6 applied and test gates 1–4 green. VERIFIED = additionally, the next
scheduled run of each workflow on `main` starts before 21:30 UTC and commits a same-day-dated file.

## Problem (evidence)

| Workflow | Cron (UTC) | Actual start (gh run list) | Effect |
|---|---|---|---|
| chain-growth-snapshot.yml | `0 22 * * *` | 09-26 23:56Z | 4 min from crossing midnight |
| narrative-snapshot.yml | `0 23 * * *` | 09-26 01:07Z, 09-27 01:03Z | points dated by `utc_today()` of the run → 2026-09-25 never exists |
| liqtide-snapshot.yml | `30 23 * * *` | 01:30–01:52Z daily | archive dated by provider `generated_utc` (real publish 00:25–01:12Z), so no gap yet — but only ~40 min margin after publish; header comment "~22:45 UTC refresh" is wrong |

LiqTide workflow also lacks `concurrency:` and the retry push loop (bare `git push`).

## Decision Summary

### Chosen Approach
Move crons earlier and off the top of the hour, keep order and ~30 min stagger:
chain-growth `47 17 * * *`, narrative `17 18 * * *`, liqtide `47 18 * * *`. Worst observed delay
~2h20m → every run starts before ~21:10 UTC, ~2h50m before midnight.

### Why This Over Alternatives
| Alternative | Why Rejected |
|---|---|
| Backdate late runs to the scheduled date in the scripts | An observation taken 01:07 on D+1 labelled D is silently wrong (Key Patterns: "numbers are never silently wrong"); GitHub also exposes no scheduled-date input |
| Keep times, add a "if after midnight, use yesterday" guard | Same mislabelling problem, plus hides the scheduler delay instead of absorbing it |
| External scheduler (cron-job.org → workflow_dispatch) | New outward-facing dependency + token secret; disproportionate |
| Only move narrative | chain-growth is 4 min from the same failure; liqtide margin after publish is thin |

### Risk Predictions
- Ops: GitHub delay could exceed ~2h50m on a bad day → guard test enforces a 3h buffer; residual risk accepted.
- Data: LiqTide at ~18:47–21:10 fetches the payload published ~00:25–01:12 the same UTC day — ~18–20h margin, strictly better than today's ~40 min.
- Data: narrative day boundary shifts from "just before midnight" to "~18–21h"; each point still honestly dated by observation day. Pytrends dates by Google's own index date, unaffected.
- Git: three pushes 30 min apart + retry loop on all three → race risk negligible.
- Maintainability: a future edit could drift a cron back late → pytest guard catches it.

### Key Constraints Accepted
- No change to any `api/scripts/snapshot_*.py` dating logic.
- Existing 09-26/09-27 rows stay as-is (honestly dated). 2026-09-25 narrative gap is unrecoverable (trending/exchange keep no history) — documented, not filled.
- Pytrends partial-hour zeros: investigation finding + backlog note only.

## SPEC (trivial lock)
Requirements locked: all three snapshot workflows start well before UTC midnight despite ~2h GitHub
delay; liqtide workflow gains concurrency + retry push; a pytest guard enforces schedule + safety
properties; docs corrected. Out of scope: script dating, backfill, pytrends fix.

## Implementation Checklist

1. `.github/workflows/chain-growth-snapshot.yml`: cron → `"47 17 * * *"`; rewrite header comment (17:47 UTC, off-the-hour, observed ~2h GitHub delay, 30/60 min before narrative/liqtide).
2. `.github/workflows/narrative-snapshot.yml`: cron → `"17 18 * * *"`; rewrite header comment (18:17 UTC, reason = ~2h delay pushed 23:00 runs past midnight → 2026-09-25 gap).
3. `.github/workflows/liqtide-snapshot.yml`:
   - cron → `"47 18 * * *"`; fix header comment: LiqTide actually publishes ~00:25–01:12 UTC (observed `generated_utc`), we run same UTC day ~18h later; archive keyed by `generated_utc[:10]`.
   - add `concurrency: {group: liqtide-snapshot, cancel-in-progress: false}` (block form, matching the others).
   - replace commit step with the narrative-style block: `git add api/data/cache/liqtide/` only, "nothing new to commit" early exit, commit, 3-attempt `git pull --rebase origin "${GITHUB_REF_NAME}" && git push` loop, `exit 1` on exhaustion.
   - keep: no `pull_request` trigger, `permissions: contents: write` only, `workflow_dispatch`.
4. New `api/tests/scripts/test_snapshot_workflow_schedules.py` (parametrized over the 3 files):
   - load via `yaml.safe_load` (PyYAML 6.0.3 is in `api/uv.lock` as a transitive dep of `uvicorn[standard]`); read triggers as `doc.get("on", doc.get(True))`.
   - each cron: exactly one schedule, parse `M H * * *`; assert `H*60+M + 180 < 1440`.
   - pairwise stagger between the three start minutes ≥ 20.
   - no `pull_request` / `pull_request_target` trigger; `permissions == {"contents": "write"}`; `concurrency.group` present and `cancel-in-progress` false.
   - commit step text contains `git pull --rebase` and `for attempt in 1 2 3`.
   - every `git add` line targets only its own dir: chain-growth `api/data/cache/onchain/`, narrative `api/data/cache/narrative/`, liqtide `api/data/cache/liqtide/`.
   - repo root resolved from `Path(__file__).resolve().parents[3]`.
5. Docs (grep `23:00|23:30|22:00|22:45|0 23|30 23|0 22` across `process/context/` to find all):
   - `process/context/all-context.md`: `.github/workflows/` line in Repository Structure (lines ~487-488, add chain-growth); line ~79 and ~156 mentions → new times; new dated "Changes Since Last Update (2026-09-27)" entry: ~2h GitHub cron delay, new times, corrected LiqTide publish time, 09-25 narrative gap, pytrends partial-hour finding; Open Questions entry for pytrends zeros.
   - `process/context/data-sources/all-data-sources.md` line ~113 ("Refreshes daily around 22:45 UTC") → observed 00:25–01:12 UTC `generated_utc`; Standing Rule 8 section (~171) workflow time if stated.
   - `process/context/tests/all-tests.md` line 35: api pytest count after new tests (record actual number from gate run).
   - Do NOT touch the unrelated 22:00 mentions at all-tests.md lines 84/157 (Brussels timezone lesson).
6. Backlog note `process/general-plans/backlog/pytrends-partial-hour-zeros_NOTE_27-09-26.md`: memecoin 34→0, RWA all 0; cause = `df.iloc[-1]` of hourly "now 7-d" is Google's incomplete `isPartial` hour; suggested follow-up: drop `isPartial` rows or use a daily aggregate. Plus the 09-25 gap note.
7. Run gates.

## Touchpoints
- Edit: `.github/workflows/{chain-growth,narrative,liqtide}-snapshot.yml`
- Create: `api/tests/scripts/test_snapshot_workflow_schedules.py`, backlog note
- Docs: `process/context/all-context.md`, `process/context/data-sources/all-data-sources.md`, `process/context/tests/all-tests.md`
- Read only: `api/scripts/snapshot_{narrative,chain_growth,liqtide}.py`, `api/data/liqtide_adapter.py:123-127`

## Public Contracts
None. No API, schema, or script behavior change. Archive file naming/dating unchanged.

## Blast Radius
3 workflow YAMLs + 1 new test + 3 context docs + 1 backlog note. Risk class: CI/scheduling config
(deploy/runtime adjacent, `contents: write` token) — mitigated by keeping permissions/triggers identical
and adding a test that pins them. Effect is only observable on the next scheduled run on `main`.

## Verification Evidence
| Gate / Scenario | Strategy | Proves SPEC criterion |
|---|---|---|
| `uv run --project api pytest api/tests/scripts/test_snapshot_workflow_schedules.py -q` | Fully-Automated | crons start ≥3h before midnight, stagger ≥20 min, safety properties pinned |
| `uv run --project api pytest api/ -q` | Fully-Automated | no regression (baseline 395 passed / 3 deselected + new tests) |
| `git diff --check` | Fully-Automated | no whitespace/conflict markers |
| `git diff --stat -- api/scripts api/data` empty | Fully-Automated | no script dating change |
| Next scheduled runs on `main` (`gh run list --workflow <file>`) start before 21:30Z and commit same-day-dated files | Hybrid (post-merge, user/next session) | real-world fix |

## Test Infra Improvement Notes
(none identified yet) — workflows had no test coverage before this plan; the new guard is the first.

## Resume and Execution Handoff
1. Selected plan: `process/general-plans/active/snapshot-cron-timing_27-09-26/snapshot-cron-timing_PLAN_27-09-26.md`
2. Last completed: PLAN + VALIDATE (fast mode); EXECUTE not started
3. Validate-contract: written below (Gate: PASS)
4. Context loaded: all-context.md, tests/all-tests.md, data-sources/all-data-sources.md, the 3 workflow files, api/uv.lock
5. Next step: on "ENTER EXECUTE MODE", run checklist 1→7 in order on branch `claude/snapshot-cron-timing`

## Validate Contract

generated-by: outer-pvl
date: 2026-09-27
Date: 27-09-26
Gate: PASS

### Net gate derivation
| Layer 1 | Status |
|---|---|
| Infra fit | PASS — GitHub cron syntax standard; off-:00 minutes follow GitHub guidance |
| Test coverage | PASS — pytest collects `api/tests/scripts/`; PyYAML present in lock (transitive) |
| Breaking changes | PASS — no contracts; archive dating unchanged |
| Security surface | PASS — permissions/triggers unchanged and newly pinned by test; no secrets added |

| Layer 2 | Status |
|---|---|
| Items 1–3 workflows | PASS — cron lines and commit blocks located, unique |
| Item 4 test | PASS — `on:`→True handled; paths resolvable |
| Items 5–6 docs | PASS — stale mentions located (all-context 79/156/487-488, data-sources 113); unrelated 22:00 at all-tests 84/157 excluded |

Totals: 0 FAILs / 0 CONCERNs / 7 PASSes → **Net Gate: PASS**

### Test gates (EXECUTE + EVL)
1. `uv run --project api pytest api/tests/scripts/test_snapshot_workflow_schedules.py -q` → all pass
2. `uv run --project api pytest api/ -q` → 0 failed
3. `git diff --check` → clean
4. `git diff --stat -- api/scripts api/data` → empty

Failing stub (red-first):
test("should reject any snapshot cron starting less than 3h before UTC midnight") — raise NotImplementedError until item 4 lands; verify it FAILS against the current `0 23`/`30 23` crons before editing workflows.

### Execute-agent instructions
- E1: Write the guard test first and confirm it fails on current YAML (narrative/liqtide/chain-growth all violate the 3h buffer), then edit workflows.
- E2: If `import yaml` fails under `uv run --project api`, fall back to regex on `cron:` lines and text checks — do not add a dependency.
- E3: Do not modify any `api/scripts/` or `api/data/` file; do not rewrite existing archive rows.
- E4: Record the actual new pytest count in all-tests.md, not an estimate.
- E5: No commit/push unless the user asks (then commit on the current branch).

### Known gaps
- Real scheduler behaviour only verifiable after merge to `main` (Hybrid row above).
- 2026-09-25 narrative data is unrecoverable.
- Pytrends partial-hour zeros: backlog only.

## Autonomous Goal Block
```
SESSION GOAL: Snapshot cron timing fix (move crons earlier, harden liqtide workflow, pytest guard)
Charter + umbrella plan: N/A — single plan
Autonomy: auto-proceed on reversible steps per feedback_autonomous_phase_execution.md
Hard stop conditions / safety constraints:
- No change to snapshot script dating or existing archive files
- No new workflow permissions/triggers/secrets; no push to main without user ask
Next phase: EXECUTE: process/general-plans/active/snapshot-cron-timing_27-09-26/snapshot-cron-timing_PLAN_27-09-26.md
Validate contract: inline in plan
Execute start: uv run --project api pytest api/ -q | git diff --check | high-risk pack: no
```
