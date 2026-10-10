---
name: context:current-state
description: "Observed, timestamped state of the repo: branch, last commit, working tree, validator results, scheduled-job evidence, and what is unverified. Re-verify when stale."
keywords: current state, status, branch, commit, working tree, validators, baseline, ground truth, stale, verified, unverified, snapshot, cron
date: 10-10-26
---

# Current State

**Stamp: commit `fc12f27` (`origin/main`, PR #50; screener batches 1 to 4 and R12 merged), observed 2026-10-10 (UTC) from branch `claude/pensive-albattani-ou0cgv` (`origin/main` plus process docs).** Rows marked af7888f date from `af7888f` (2026-10-03), not re-run. "Historical" rows are copied with their source.

Staleness rule (master-planner.md): stale when the stamp is not an ancestor of HEAD (`git merge-base --is-ancestor fc12f27 HEAD` fails) or when more than 10 non-cache commits landed since it (`git log fc12f27..HEAD --oneline -- . ':(exclude)api/data/cache' | wc -l`). Nightly bot snapshot commits do not make it stale.

## Observed (af7888f unless marked)

| Fact | Value | Command |
|---|---|---|
| Working tree | `origin/main` `fc12f27` plus uncommitted process/ docs only | `git status --short` |
| Entry files | `CLAUDE.md` 13,443 B, `AGENTS.md` 12,572 B, `north-star.md` 5,225 B | `wc -c` |
| `process/context/all-context.md` | 193 lines, 11,380 B; router part 5,831 B | `wc -lc`, PLANNER-BUDGET block |
| Planner budget | planner_fixed 48,995 B, cap 56,000, headroom 7,005, rc=0 | PLANNER-BUDGET block |
| Root context docs | `operating-instructions.md` 6,509 B, `architecture.md` 6,572 B | `wc -c` |
| Remote heads | 5: `main`, `claude/pensive-albattani-ou0cgv`, `claude/inspiring-pasteur-awqxk3`, `claude/kind-tesla-tat3vo`, `claude/split-all-context`. The last three are deletable by the user (content rescued by T31); the planner cannot delete branches. PR #5 closed | `git ls-remote --heads origin` |
| Workflows | 6: `ci.yml` plus five snapshot jobs | `ls .github/workflows` |
| `.agents/skills` | 339 tracked regular files, not a symlink | `git ls-files .agents/skills \| wc -l` |
| `web/tsconfig.tsbuildinfo` | not tracked (empty `git ls-files`) | `git ls-files web/tsconfig.tsbuildinfo` |
| `README.md` | present at repo root | `ls README.md` |
| Tests, combined main (`fc12f27`, worker and tester reports, not re-run here) | pytest 1016 passed, 2 skipped, 5 deselected, 0 xfailed (996 + 17 R12 shape tests + 3 S11a, verified); vitest 335 in 43 files (331 in 42 at S11b, +4 at T44); seeded e2e 72 in 8 files (S11b). Playwright e2e is not in CI. T44 ran no pytest (nothing under api/ touched) | MASTER-PLAN.md T40-T44 |
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

## Screener behaviour (batches 1 to 4 merged, live PC probes pending)

**Freshness (S1, T32):** `api/data/freshness.py` decides staleness per timeframe (a forming candle is not fresh; `1w` judged on its daily bar). Each cached series has a `<tf>.meta.json` `fetched_at` sidecar, written after the parquet. 15m/1h/4h keep 200 bars, `1d` is never trimmed. Tail fetch asks for the latest bars (probe P-S1-1 checks `since=None`).

**Refresh worker (S8, T35):** an in-process loop started by the app lifespan refreshes watchlist plus benchmarks about every 15 min (`SCREENER_REFRESH_WORKER` 0 off, 1 on, unset on; `GET /api/refresh/status`, `POST /api/refresh/now`). Reads are cache-only. Accepted limits: non-watchlist scalp queues a fetch per tick; latch recovery after an offline start up to 3600 s. P-S8-1 (overnight, PC) outstanding.

**Gain chips and labels (S2, T34):** chips show the current candle, open to latest price, computed in Python (`gain.py`); chart axes use UTC labels. P-S2-1 outstanding.

**LSE equities (S3, T33):** `api/data/lse_adapter.py` and `equities_store.py` (plain `httpx`, key in `LSE_API_KEY`, private use, non-redistributable); no page yet. G-S3-6 stays skipped until the user runs `s3-probe/lse_probe.py` on the PC and copies the sanitised fixture to `api/tests/data/fixtures/lse_candles_probe_shape.json`.

**Verdict removal (S4, T36):** the verdict, confidence, benchmark and momentum modules, the confidence badge, both text strips and the scalp verdict are gone (two commits). The drill-down reads `GET /api/screener/{symbol}/chart`; `rsi.py` and `sma.py` remain. P-S4-1 (deploy web and API together) is the user's.

**Chart interaction and spaghetti (S6, T37):** every chart zooms with Ctrl/Cmd+wheel or pinch, pans by drag, resets on double-click (custom viewport; LayerChart transform rejected); axis text is vector SVG over Canvas lines. A spaghetti chart replaces the relative-performance chart; toggle persistence waits for S5 (backlog note). P-S6-1 (DPR 2 display, phone) is the user's.

**BTC leg chart (S7, T38):** `/api/regime/legs` and `/api/regime/btc-legs` read BTC OHLCV cache-only (FRED/DefiLlama may still fetch on TTL expiry); the chart states its span and carries the D-14 estimate label. The user must run the existing deep backfill once on the PC (P-S7-1). T39 fixed a zoom e2e helper.

**Layout API (S5a, T40):** a server-side layout file feeds groups and the 30-coin cap through the layout API; group sort is deferred (`screener-group-sort_NOTE_09-10-26.md`). The web side is S5b (T41, planned, plan re-validation pending). P-S5a-1 outstanding.

**Brussels time (S11a, T42):** axis and labels show Brussels time (`brussels-time.ts`, `chart-time-format.ts`). P-S11-2 (the 25 Oct 2026 DST change) outstanding; P-S11-1 (real PC labels) reported fine.

**Live updates (S11b, T43):** 60 s live polling, a freshness strip and in-place chart updates (no remount). Contrast and passive-poll follow-ups are in backlog (`screener-live-ondemand-states-contrast_NOTE_10-10-26.md`, `screener-passive-polls_NOTE_10-10-26.md`). P-S11-3/4/5 reported fine on 10-10-26.

**Linked small-chart zoom (T44, PR #50):** the small charts share one zoom; the reset button is removed on small charts only. The user confirmed it works on the PC.

**Deploy (R12):** kill-by-port before build, stale-build guard and post-start smoke check in `deploy/*.ps1`; PC acceptance 10-10-26 (user-reported, PowerShell 5.1). Accepted with known gaps: smoke HTTP non-200 and build-id-mismatch branches shape-tested only; exit 6 seen only for process-exited-before-answering; failed-smoke port stop could exit 5 first; invalid WebPort under -ReportOnly exits 2. Record: `process/general-plans/active/r12-deploy-fixes_03-10-26/r12-deploy-fixes-pc-record_REPORT_10-10-26.md`.

**Process lapse (T38) and known gap:** PR #40 was merged while the worker's report said `needs_input` (an S6 e2e test broke on S7's layout), so main was red on that browser test until PR #41. CI runs pytest, vitest, tsc and the island build only, not Playwright; seeded e2e gates are local/tester-only. Lesson: a worker never merges with an open `needs_input`; the planner verifies the e2e after each UI slice. 10-10-26 repeats (S11a merged with a needs_input on the pytest count, correct; R12 W4 self-merged PR #48; S11b 7.74 USD passed the 7 USD ask threshold unrecorded): see `process/archive/index.md` Approvals Log. Rule: envelopes say "needs_input means STOP, do not merge, do not open a new PR; cost is reported by the planner not the worker".

## Gate status

Gates 2 to 6 complete; reports in `process/general-plans/completed/master-planner-recovery_02-10-26/` (HANDOVER ACCEPTED by the user 03-10-26).

Planner budget: run the PLANNER-BUDGET block (master-planner.md section 12).

## Not run or unverified at the stamp

- Playwright in CI (none); e2e ran locally in batch 2 (screener 10, contrast 7 at T38).
- Real per-session token usage (backlog `token-usage-telemetry_NOTE_02-10-26.md`).
- Snapshot crons firing at their new times; the two canary jobs.
- Anything on the user's PC (deployed app, Task Scheduler, Tailscale, Windows deploy scripts, `.agents/skills` there) and live provider reachability.
- Branch-delete setting (session branch deletion is known to fail).

## Historical (copied, not re-run)

| Fact | Value | Source |
|---|---|---|
| Deploy target | home PC plus Tailscale, user walkthrough succeeded | MASTER-PLAN rev 6 |
| CLAUDE.md before Gate 3 | 28,903 B; AGENTS.md 37,885 B | Gate 3 report |
| GitHub scheduler start delay | 2h03m to 5h01m (09-26 to 09-30) | context-changelog.md |

## Next actions

1. Done: eight recovery worker tasks merged and archived; recovery cost 6.9042678 USD of 40.
2. User: delete the three held branches (`kind-tesla-tat3vo`, `inspiring-pasteur-awqxk3`, `split-all-context`). Decided 03-10-26: HANDOVER accepted; big-task subagent caps 3 subagents, 15 USD, 1 level (master-planner.md section 6).
3. Screener batches 1 to 4 (T32-T44) and R12 merged; plans stay in `active/` until the PC probes run. Open PC probes: P-S1-1, P-S2-1, P-S8-1, LSE probe, P-S4-1, P-S5a-1, P-S6-1, P-S7-1, P-S11-2 (25 Oct 2026 DST); BTC deep backfill once on the PC. Worker spend about 59.0 USD of 75 through S11b (34.73 through T39 + R12 W1 2.45, W2 4.56, W3 0.91, W4 0.77 + S5a 3.40 + S11a 4.40 + S11b 7.74), T44 unmetered, testers unmetered. Next: S5b (T41, re-validate plan first); S10 optional (R12 done, unblocked); S9 later. Registry: MASTER-PLAN.md.
4. Known gaps and backlog: R12 gaps above; S3 LSE probe pending (CONDITIONAL); AC-S11b-8r contrast notes; AC-8 group sort deferred; stale pytest 999 in the S11 plan tables (real baseline 1016); S8 items (b), (c) accepted limits.
5. Worker sessions to archive later (not archived now): T40, R12 W1-W4, T42, T43.
