---
name: current-state-archived-21-10-26
description: "Verbatim current-state.md as stamped at bfb7793 on 13-10-26 (screener batches, PC run-book, historical validators, next actions), moved 21-10-26 at T118 to bring current-state.md within its 8,000 B ceiling. History only, not current truth."
date: 21-10-26
---

# Archived current-state.md (stamp `bfb7793`, 2026-10-13)

# Current State

**Stamp: commit `bfb7793` (`origin/main`; PR #60 merge, last code merge; nightly data-snapshot bot commits can sit on top; screener batches 1 to 5 and R12 merged), observed 2026-10-13 (UTC) from branch `claude/pensive-albattani-ou0cgv` (`origin/main` plus process docs).** Rows marked af7888f date from `af7888f` (2026-10-03), not re-run. "Historical" rows are copied with their source.

Staleness rule (master-planner.md): stale when the stamp is not an ancestor of HEAD (`git merge-base --is-ancestor bfb7793 HEAD` fails) or when more than 10 non-cache commits landed since it (`git log bfb7793..HEAD --oneline -- . ':(exclude)api/data/cache' | wc -l`). Nightly bot snapshot commits do not make it stale.

## Observed (af7888f unless marked)

| Fact | Value | Command |
|---|---|---|
| Working tree | `origin/main` `bfb7793` plus uncommitted process/ docs only | `git status --short` |
| Entry files | `CLAUDE.md` 13,443 B, `north-star.md` 5,225 B | `wc -c` |
| `process/context/all-context.md` | 193 lines, 11,380 B; router part 5,831 B | `wc -lc`, PLANNER-BUDGET block |
| Planner budget | planner_fixed 48,995 B, cap 56,000, headroom 7,005, rc=0 | PLANNER-BUDGET block |
| Root context docs | `operating-instructions.md` 6,509 B, `architecture.md` 6,572 B | `wc -c` |
| Remote heads | main, `claude/pensive-albattani-ou0cgv` plus task branches; three held branches deletable by the user (content rescued by T31) | `git ls-remote --heads origin` |
| Workflows | 6: `ci.yml` plus five snapshot jobs | `ls .github/workflows` |
| `.agents/skills` | 339 tracked regular files, not a symlink | `git ls-files .agents/skills \| wc -l` |
| `web/tsconfig.tsbuildinfo` | not tracked (empty `git ls-files`) | `git ls-files web/tsconfig.tsbuildinfo` |
| `README.md` | present at repo root | `ls README.md` |
| Tests, main `bfb7793` (worker/tester reports, not re-run here) | pytest 1134 passed, 1 skipped, 5 deselected (T51 worker: 1127 + 7); vitest 476 in 59 files and seeded e2e 92 in 11 files (S9E tester/worker; T51 touched api/ only). Playwright e2e is not in CI | MASTER-PLAN.md T45-T51 |
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

## Screener behaviour (batches 1 to 5 merged, live PC probes pending)

Shipped on main (batches 1 to 4; batch 5 equities below): layout UI with groups, add/remove coins with the 30-coin cap, RSI numbers, spaghetti hidden-lines saved on the server, linked small-chart zoom, live polling (60 s) with a freshness strip, Brussels time.

**Freshness (S1, T32):** `api/data/freshness.py` decides staleness per timeframe (a forming candle is not fresh); each cached series has a `<tf>.meta.json` `fetched_at` sidecar; 15m/1h/4h keep 200 bars, `1d` is never trimmed. P-S1-1 checks `since=None`.

**Refresh worker (S8, T35):** an in-process loop started by the app lifespan refreshes watchlist plus benchmarks about every 15 min (`SCREENER_REFRESH_WORKER` 0 off, 1 on, unset on; `GET /api/refresh/status`, `POST /api/refresh/now`). Reads are cache-only. Accepted limits: non-watchlist scalp queues a fetch per tick; latch recovery after an offline start up to 3600 s. P-S8-1 (overnight, PC) outstanding.

**Gain chips and labels (S2, T34):** chips show the current candle, open to latest price, computed in Python (`gain.py`); chart axes use UTC labels. P-S2-1 outstanding.

**LSE equities (batch 5, T45-T51, PRs #54-#60; plan accepted WITH KNOWN GAPS, folder still in `active/`):** the `/equities` page reuses the crypto board by parameter: add/remove tickers (30 cap, API 409, counted apart), groups, spaghetti (no reference lines), drill-down, RSI, linked zoom, Brussels time, 60 s polling and a freshness strip (latest daily bar, next expected refresh). Reads are cache-only. A market-hours refresh worker (`api/data/equities_refresh.py`) ticks about 30 min after the US close with 3 retries; a catch-up runs 20 s after start when a ticker is behind (T51). The adapter matches the live service (T49; facts in `lse-live-shape-verification_NOTE_03-10-26.md`, closed). Private use, synthetic fixtures only. AC-S9E-1 is CONDITIONAL on the unmeasured 30/60 min constants (P-S9-2); other gaps: `equities-known-gaps_NOTE_13-10-26.md`.

**PC run-book (user-reported 13-10-26):** the API reads `LSE_API_KEY` at start and `deploy/start-api.ps1` does not pass it, so set it in the PowerShell window first (clipboard; length about 41; a first attempt stored 1 character); restart the API after; rebuild web with `deploy\build-web.ps1`; ports 3000/8000 on the Tailscale address (not recorded). Key handling proposal: `lse-api-key-deploy-handling_NOTE_13-10-26.md`.

**Verdict removal (S4, T36):** verdict, confidence, benchmark and momentum modules, the badge, both text strips and the scalp verdict are gone. The drill-down reads `GET /api/screener/{symbol}/chart`. P-S4-1 (deploy web and API together) is the user's.

**Chart interaction and spaghetti (S6, T37):** Ctrl/Cmd+wheel or pinch zoom, drag pan, double-click reset on every chart; axis text is vector SVG. A spaghetti chart replaces the relative-performance chart. P-S6-1 (DPR 2 display, phone) is the user's.

**BTC leg chart (S7, T38):** `/api/regime/legs` and `/api/regime/btc-legs` read BTC OHLCV cache-only; the chart carries the D-14 estimate label. The user must run the deep backfill once on the PC (P-S7-1).

**Layout API and layout UI (S5a T40, S5b T41, PR #51 `20e9f20`):** a server-side layout file with groups and the 30-coin cap; groups with rename, reorder, delete, move and remove-with-confirm, an add form (`n / 30 coins`), RSI on boxes and the drill-down, saved spaghetti toggles. Tester PASS WITH_GAPS; plan `screener-batch3_09-10-26` accepted with known gaps, still in `active/`. P-S5a-1 and P-S5b-1 outstanding; residuals AC-8r group sort (`screener-group-sort_NOTE_09-10-26.md`) and AC-S5b-8r (`screener-ondemand-states-contrast_NOTE_10-10-26.md`).

**Brussels time (S11a, T42):** axis and labels show Brussels time (`brussels-time.ts`, `chart-time-format.ts`). P-S11-2 (the 25 Oct 2026 DST change) outstanding; P-S11-1 (real PC labels) reported fine.

**Live updates (S11b, T43):** 60 s live polling, a freshness strip and in-place chart updates (no remount). Contrast and passive-poll follow-ups are in backlog (`screener-live-ondemand-states-contrast_NOTE_10-10-26.md`, `screener-passive-polls_NOTE_10-10-26.md`). P-S11-3/4/5 reported fine on 10-10-26.

**Linked small-chart zoom (T44, PR #50):** the small charts share one zoom; the reset button is removed on small charts only. The user confirmed it works on the PC.

**Phone and iPad access:** works after the user added the README firewall rule 'my_site tailnet' (TCP 3000 and 8000 from 100.64.0.0/10 on the Tailscale interface); the README B9 firewall step was required on this machine (README follow-up note for a later docs slice). The PC's Tailscale address is user-local and not recorded.

**Deploy (R12):** kill-by-port before build, stale-build guard and post-start smoke check in `deploy/*.ps1`; PC acceptance 10-10-26 (user-reported). Accepted with known gaps: some smoke branches shape-tested only; invalid WebPort under -ReportOnly exits 2. Record: `process/general-plans/active/r12-deploy-fixes_03-10-26/r12-deploy-fixes-pc-record_REPORT_10-10-26.md`.

**Process lapses and rules:** workers merged with an open `needs_input` (T38, main red until T39) and self-merged (R12 W4); cost passed the 7 USD ask point unrecorded (S11b, T41). CI has no Playwright; seeded e2e is local/tester-only. Rules: envelopes say "needs_input means STOP, do not merge, do not open a new PR" and "after your report, stop; do not wait on CI"; the planner reads worker cost from the session record after the worker is idle/archived and checks the 7 USD point. Detail: `process/archive/index.md` Approvals Log.

Gates 2 to 6 complete (reports in `process/general-plans/completed/master-planner-recovery_02-10-26/`). Planner budget: PLANNER-BUDGET block; this file is over its 8,000 B ceiling (pre-existing).

## Not run or unverified at the stamp

- Playwright in CI (none); e2e ran locally in batch 2 (screener 10, contrast 7 at T38).
- Real per-session token usage (backlog `token-usage-telemetry_NOTE_02-10-26.md`).
- Snapshot crons firing at their new times; the two canary jobs.
- Anything on the user's PC (deployed app, Task Scheduler, Tailscale, Windows deploy scripts, `.agents/skills` there) and live provider reachability.
- Branch-delete setting (session branch deletion is known to fail).

## Historical

Deploy target home PC plus Tailscale (user walkthrough succeeded); GitHub scheduler start delay 2h03m to 5h01m (context-changelog.md); CLAUDE.md was 28,903 B before Gate 3.

## Next actions

1. Done: eight recovery worker tasks merged and archived; recovery cost 6.9042678 USD of 40.
2. User: delete the three held branches (`kind-tesla-tat3vo`, `inspiring-pasteur-awqxk3`, `split-all-context`). Decided 03-10-26: HANDOVER accepted; big-task subagent caps 3 subagents, 15 USD, 1 level (master-planner.md section 6).
3. Screener batches 1 to 5 (T32-T51) and R12 merged; plans stay in `active/` until the PC probes run and the user says go. Open probes: P-S1-1, P-S2-1, P-S8-1, P-S4-1, P-S5a-1, P-S5b-1, P-S6-1, P-S7-1, P-S9-2 (equities page on the PC, when the final daily bar appears after the close), P-S9-3 (phone/iPad on the equities page), P-S11-2 (25 Oct 2026 DST); BTC deep backfill once. Done: P-S9-1, P-S11-1/3/4/5, zoom fix. Worker spend 86.13 of the 100 USD ceiling (raised from 75 on 12-10-26): 69.43 before batch 5 + 3.62 + 1.72 + 3.38 + 3.38 + 1.01 + 3.59; about 13.9 left; T51, planner, validator and tester sessions unmetered. Tester PASS on S9A-S9E; S9F (T49) and T51 checked by CI plus the planner's diff read only, the user's decision. Registry: MASTER-PLAN.md.
4. Next: S10 (optional scheduled task) not started, needs its own estimate and go; archive the batch 3, R12 and batch 5 folders on the user's explicit go; follow-ups: AC-8 group sort, contrast slice, `equities-known-gaps_NOTE_13-10-26.md`, `lse-api-key-deploy-handling_NOTE_13-10-26.md`.
5. Worker sessions to archive later (not archived now): T40, R12 W1-W4, T42, T43, T41, and T45-T50 (`session_01D3a21vGbbh7Jm7kYCxe5vR`, `session_01M9p9gPbZqhgVZapoadX5eQ`, `session_01R8x2RhVF7MTRhzVtG6NP8W`, `session_01Hcd3ZQPzPN1s6om5zoQobY`, `session_01BJ52mKHgXHYs8DPELeHpdc`, `session_01YHqbhmpwYL18wnvzvSFDta`), once these docs are on main.
