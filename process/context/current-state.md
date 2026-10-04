---
name: context:current-state
description: "Observed, timestamped state of the repo: branch, last commit, working tree, validator results, scheduled-job evidence, and what is unverified. Re-verify when stale."
keywords: current state, status, branch, commit, working tree, validators, baseline, ground truth, stale, verified, unverified, snapshot, cron
date: 04-10-26
---

# Current State

**Stamp: commit `605424d` (`origin/main`, PR #36; screener batch 1 merged), observed 2026-10-04 (UTC) from branch `claude/pensive-albattani-ou0cgv`, which equals `origin/main` plus two envelope files and uncommitted process/ text.** Rows below marked af7888f were observed at the earlier stamp `af7888f` (2026-10-03) and not re-run. "Observed" rows were read or run at that stamp; "Historical" rows are copied and labelled with their source commit.

Staleness rule (master-planner.md): stale when the stamp is not an ancestor of HEAD (`git merge-base --is-ancestor 605424d HEAD` fails) or when more than 10 non-cache commits landed since it (`git log 605424d..HEAD --oneline -- . ':(exclude)api/data/cache' | wc -l`). Nightly bot snapshot commits do not make it stale.

## Observed (af7888f unless marked)

| Fact | Value | Command |
|---|---|---|
| Working tree | `origin/main` `605424d` plus two envelope files and uncommitted process/ text only (MASTER-PLAN.md, archive/index.md, this file, context docs, batch-1 plan header) | `git status --short` |
| Entry files | `CLAUDE.md` 13,443 B, `AGENTS.md` 12,572 B, `north-star.md` 5,225 B | `wc -c` |
| `process/context/all-context.md` | 193 lines, 11,380 B; router part 5,831 B | `wc -lc`, PLANNER-BUDGET block |
| Planner budget | planner_fixed 48,995 B, cap 56,000, headroom 7,005, rc=0 | PLANNER-BUDGET block |
| Root context docs | `operating-instructions.md` 6,509 B, `architecture.md` 6,572 B | `wc -c` |
| Remote heads | 5: `main`, `claude/pensive-albattani-ou0cgv`, `claude/inspiring-pasteur-awqxk3`, `claude/kind-tesla-tat3vo`, `claude/split-all-context`. The last three are deletable by the user (content rescued by T31); the planner cannot delete branches. PR #5 closed | `git ls-remote --heads origin` |
| Workflows | 6: `ci.yml` plus five snapshot jobs | `ls .github/workflows` |
| `.agents/skills` | 339 tracked regular files, not a symlink | `git ls-files .agents/skills \| wc -l` |
| `web/tsconfig.tsbuildinfo` | not tracked (empty `git ls-files`) | `git ls-files web/tsconfig.tsbuildinfo` |
| `README.md` | present at repo root | `ls README.md` |
| Tests, combined main after batch 1 (`605424d`, worker and tester reports, not re-run by this bookkeeping pass) | pytest 963 passed, 2 skipped, 5 deselected, 0 xfailed; vitest 245 passed in 33 files; `tsc` 0; `build:islands` 0. G-S2-8 e2e not run (allowed, U-4). Earlier (`753db23`): pytest 873/1/5/1, vitest 223 in 30 files | MASTER-PLAN.md T32-T35, batch-1 reports |
| CI | T30 and T31 PRs: api pytest and web vitest/tsc/island build both success (worker and tester checks) | MASTER-PLAN.md T30, T31 |

### Validator results (af7888f, not re-run 04-10-26)

| Validator | Failures | Warnings | Note |
|---|---|---|---|
| validate-all-context | 0 | 0 | |
| validate-context-discovery | 1 | 0 | `.agents/skills does not resolve to .claude/skills` (accepted baseline) |
| validate-skills | 1 | 0 | same cause (accepted baseline) |
| validate-guide-sync | 0 | 0 | |
| validate-plan-inventory | 0 | 6 | baseline warnings |
| validate-agent-parity (non-strict) | 0 | 18 | baseline `.claude/agents` vs `.codex/agents` drift |

`validate-backlog-notes` 45 failing notes (older schema), recorded earlier, not re-run now.

## Screener batch 1 behaviour (merged 04-10-26, live probes pending)

**Freshness (S1, T32):** `api/data/freshness.py` decides staleness per timeframe (a forming candle is not fresh; `1w` judged on its daily bar). Each cached series has a `<tf>.meta.json` `fetched_at` sidecar, written after the parquet. 15m/1h/4h keep 200 bars, `1d` is never trimmed. Tail fetch asks for the latest bars (probe P-S1-1 checks `since=None`).

**Refresh worker (S8, T35):** an in-process loop started by the app lifespan refreshes watchlist plus benchmarks about every 15 min (`SCREENER_REFRESH_WORKER` 0 off, 1 on, unset on; `GET /api/refresh/status`, `POST /api/refresh/now`). Reads are cache-only. Open, user decided 04-10-26 (a into S7; b, c accepted limits): `/api/regime/*` still fetches BTC 1d inline (fold into S7); non-watchlist scalp queues a fetch per tick (accept); latch recovery after an offline start can take up to 3600 s (accept). Probe P-S8-1 (overnight, PC) outstanding.

**Gain chips and labels (S2, T34):** chips show the current candle, open to latest price, computed in Python (`gain.py`); chart axes use UTC labels; rightmost tick label can clip (left for S6). Probe P-S2-1 outstanding. Left as is: `server_time` vs skew-corrected reference differ only with non-zero skew; `gain_by_timeframe` defaults `{}` in Python but is required in TS.

**LSE equities (S3, T33):** `api/data/lse_adapter.py` and `equities_store.py` (plain `httpx`, key in `LSE_API_KEY`, private use, non-redistributable); no page yet. G-S3-6 stays skipped until the user runs `s3-probe/lse_probe.py` on the PC and copies the sanitised fixture to `api/tests/data/fixtures/lse_candles_probe_shape.json`.

Do not deploy S1 before S8: S8 is merged, so a PC deploy is allowed once the user decides.

## Gate status

Gates 2 to 6 complete; reports in `process/general-plans/completed/master-planner-recovery_02-10-26/` (HANDOVER ACCEPTED by the user 03-10-26).

Planner budget: run the PLANNER-BUDGET block in master-planner.md section 12 (bytes only); figures are in the closeout reply, not stored here.

## Not run or unverified at the stamp

- Playwright and the island build locally (CI covers the island build; CI has no e2e); last local Playwright run 35/35 on 4 specs (28-09-26), 6 specs exist now.
- Real per-session token usage: only single-run first-request probes exist (backlog `token-usage-telemetry_NOTE_02-10-26.md`). AC-R9 token claims await the user's review.
- Compliance with the retry, same-failure and no-re-run rules (observable only at the Gate 6 pilot).
- Snapshot crons firing at their new times; the two canary jobs.
- Anything on the user's PC (deployed app, Task Scheduler, Tailscale, Windows deploy scripts, `.agents/skills` there) and live provider reachability.
- Branch-delete mechanism as a setting (worker branches were absent at 06:39Z, setting unread). Session branch deletion is known to fail (git and REST, probe).

## Historical (copied, not re-run)

| Fact | Value | Source |
|---|---|---|
| Deploy target | home PC plus Tailscale, user walkthrough succeeded | MASTER-PLAN rev 6 |
| CLAUDE.md before Gate 3 | 28,903 B; AGENTS.md 37,885 B | Gate 3 report |
| GitHub scheduler start delay | 2h03m to 5h01m (09-26 to 09-30) | context-changelog.md |

## Next actions

1. Done: eight worker tasks (T20, T16, T18, T19, PERF, T29, T30, T31) merged, independently verified and archived (docs); sessions archived except T31 (archive pending). Recovery cost 6.9042678 USD of 40.
2. User: delete the three held branches (`kind-tesla-tat3vo`, `inspiring-pasteur-awqxk3`, `split-all-context`). Decided 03-10-26: HANDOVER accepted; big-task subagent caps 3 subagents, 15 USD, 1 level (master-planner.md section 6).
3. Screener realignment batch 1 (S1, S2, S3, S8 = T32-T35) merged 04-10-26; plan `screener-batch1_03-10-26` stays in `active/` until the PC probes run (P-S1-1, P-S2-1, P-S8-1, LSE shape). Worker spend 17.6025729 USD plus two unmetered EVL tester runs, of the 45 USD ceiling (separate from the 6.9042678 USD recovery spend). Next: user decides the PC deploy and the three S8 open items; S4-S7, S9, S10 not yet planned. Registry: MASTER-PLAN.md.
