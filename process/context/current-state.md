---
name: context:current-state
description: "Observed, timestamped state of the repo: commit, workflows, tests, validator results, scheduled-job evidence, and what is unverified. Re-verify when stale."
keywords: current state, status, branch, commit, working tree, validators, baseline, ground truth, stale, verified, unverified, snapshot, cron
date: 21-10-26
---

# Current State

**Stamp: commit `faf416b` (`origin/main`, PR #144 merge, last code merge), observed 2026-10-21 (UTC) from branch `claude/t118-process-catch-up` (`origin/main` plus process docs).** Nightly data-snapshot bot commits sit below it. The previous full state (stamp `bfb7793`, 13-10-26: screener batches, PC run-book, old validator table, next actions) is verbatim in `process/archive/current-state-archived_21-10-26.md`.

Staleness rule (master-planner.md): stale when the stamp is not an ancestor of HEAD or when more than 10 non-cache commits landed since it (`git log faf416b..HEAD --oneline -- . ':(exclude)api/data/cache' | wc -l`). Nightly bot commits do not make it stale.

## Observed

| Fact | Value | Command |
|---|---|---|
| Last code merges | PR #145 (T113, U1) and PR #144 (T114, U4), 2026-10-21 | `git log --merges` |
| Open PR | #146 (T115, U2), draft | GitHub API |
| Workflows | 7: `ci.yml`, `attention-refresh.yml`, `chain-growth-snapshot.yml`, `liqtide-snapshot.yml`, `liquidity-backfill-snapshot.yml`, `narrative-snapshot.yml`, `pairs-refresh-snapshot.yml` | `ls .github/workflows` |
| Scheduled attention refresh | commits `attention refresh` landed on 18, 19 and 20 Oct 2026 (also `attention extra refresh`, narrative, chain-growth and liqtide snapshots); runs start late | `git log origin/main --format='%ad %s'` |
| Frozen signal snapshots | 9 tracked files under `api/data/cache/attention/signals/` (3 windows x 17, 18, 19 Oct); the count grows daily | `git ls-files api/data/cache/attention/signals \| wc -l` |
| `.agents/skills` | not a symlink to `.claude/skills` (baseline validator failure) | `validate-context-discovery` |

## Tests and CI (worker report, not re-run here)

From the T115 PR body on `faf416b`: full API 1684 passed, 1 skipped, 5 deselected; web vitest 558 in 62 files; tsc exit 0. Playwright e2e is not in CI. The CI state of the merged PRs was not re-read for this stamp (UNVERIFIED).

## Validator results (run 2026-10-21 on this branch)

| Validator | Result |
|---|---|
| validate-context-discovery | 1 failure: `.agents/skills does not resolve to .claude/skills` (baseline, same on `main`) |
| other validators | see the T118 report; baseline failures as before (`validate-backlog-notes` 45 older notes; plan-inventory and agent-parity warnings) |

## What runs

Screener, equities, Baskets (P5), data integration tooling (P9) and the weighted Discovery signal (P10: W1 scoring, W2 history endpoint, W3 chart, W9 daily frozen snapshots) are merged. Universe and narratives: U1 and U4 merged, U2 in review, U3 U5 U6 queued. Registry: `process/MASTER-PLAN.md`; decisions D-22..D-26 in decisions.md.

## Not run or unverified

- Live provider reachability from the cloud (providers unreachable); the owner's PC (deployed app, Task Scheduler, Tailscale).
- Open owner probes from the 13-10-26 state (P-S1-1, P-S2-1, P-S8-1, P-S4-1, P-S5a-1, P-S5b-1, P-S6-1, P-S7-1, P-S9-2, P-S9-3, P-S11-2 the 25 Oct 2026 DST change; BTC deep backfill).
- Reddit API access: requested by the owner on 18-10-26, awaiting approval; X stays off.
- Calibration of the weighted signal: scheduled checks on 2027-01-18 and 2027-04-18 (MASTER-PLAN P10).
- Independent review: T96-T107 and part of T113 and T114 were merged before it (D-26).

## Next actions

1. Finish T115 review (T117), then slices U3, U5, U6 in full RIPER-5 (D-26).
2. Owner: probes above; Reddit access; weights are the owner's call (D-24).
3. Archive of finished plan folders and worker sessions only on the owner's go.
