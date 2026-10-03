## 1 Task ID
T30 - re-measure the four web performance rows PERF left unmeasured (measure only)

## 2 Outcome
done

## 3 Summary
All four rows measured, 3 runs each, on commit `e8e5101fa458573efeab4e9839656a39aebc0f5b` (origin/main). Cold start: no `web` dependencies and no island build output existed before run 1; `pnpm install --frozen-lockfile` took 6.8 s and changed no tracked file (`git status --porcelain` empty after it and at the end).
Medians: vitest 12.53 s, tsc 4.40 s, build:islands 7.30 s.
`web/public/islands/spread-chart.js` is a 301 B re-export stub (218 B gzip). The 787 kB / 185 kB figure adopted from DIRECTION-D belongs to the hashed entry chunk `chunks/entry-ZflJZzTV.mjs`: 787,646 B raw, 184,870 B gzip (`gzip -c`), matching the adopted 787 kB / 185 kB. The row 4 command in the envelope names the stub, so both are reported.

## 4 Files changed
Only this report: `process/general-plans/active/t30-perf-web-remeasure_03-10-26/t30-perf-web-remeasure_REPORT_03-10-26.md`. No tracked file changed; island build output (`web/public/islands`) is git-ignored.

## 5 Commits
Branch `claude/t30-perf-web-remeasure`, based on `e8e5101`. Report commit SHA: the PR head.

## 6 Tests run
Machine: 4 CPUs (`nproc`), node v22.22.0, pnpm 10.28.0, Linux 6.18 container. Cold: dependencies and island output absent before run 1; tsc run with `--incremental false` (writes no tsbuildinfo). Runs interleaved (test, tsc, island build) x3; wall time from `date +%s.%N`. All exit codes 0. Commit SHA for every run: `e8e5101fa458573efeab4e9839656a39aebc0f5b`.

| Row | Run | Value | Command | UTC start |
|---|---|---|---|---|
| 1 vitest | 1 | 12.57 s | `pnpm --filter web test` | 2026-10-03T19:32:30Z |
| 1 vitest | 2 | 12.19 s | same | 2026-10-03T19:32:54Z |
| 1 vitest | 3 | 12.53 s | same | 2026-10-03T19:33:18Z |
| 1 vitest | median | **12.53 s** | | |
| 2 tsc | 1 | 4.82 s | `pnpm --filter web exec tsc --noEmit --incremental false` | 2026-10-03T19:32:42Z |
| 2 tsc | 2 | 4.40 s | same | 2026-10-03T19:33:07Z |
| 2 tsc | 3 | 4.38 s | same | 2026-10-03T19:33:31Z |
| 2 tsc | median | **4.40 s** | | |
| 3 islands | 1 | 7.28 s (cold, no prior output) | `cd web && pnpm build:islands` | 2026-10-03T19:32:47Z |
| 3 islands | 2 | 7.54 s | same | 2026-10-03T19:33:11Z |
| 3 islands | 3 | 7.30 s | same | 2026-10-03T19:33:35Z |
| 3 islands | median | **7.30 s** | | |
| 4 stub `spread-chart.js` | 1/2/3 | 301 B raw, 218 B gzip (identical after all 3 runs) | `wc -c`; `gzip -c f \| wc -c` | after each run |
| 4 entry chunk `chunks/entry-ZflJZzTV.mjs` | 1/2/3 | vite reports 787.50 kB / gzip 184.71 kB on all 3 runs (same hash); measured after run 3: 787,646 B raw, 184,870 B gzip (`gzip -c`; `gzip -9` gives 182,485 B) | `wc -c`; `gzip -c f \| wc -c` | after run 3 |

Row 4 vs adopted 185 kB gzip (787 kB raw): entry chunk 184.87 kB gzip is 0.13 kB under, equal within rounding; raw 787.6 kB equals 787 kB. The 301 B stub figure is not comparable (stub, not the bundle).

Install: `cd web && pnpm install --frozen-lockfile`, 2026-10-03T19:32:11Z, 6.8 s; `git status --porcelain` empty afterwards.

## 7 Tests NOT run
`compute_pairs.py` re-run, screener refresh at 30 coins, page load: out of scope per SPEC (need OHLCV cache / live ccxt); stay `unmeasured`. pytest, Playwright: not required at RT0.

## 8 Deviations
1. tsc run with `--incremental false` (operating-instructions suggests it; avoids tsbuildinfo). Row 2 command otherwise as specified.
2. Runs interleaved via a scratchpad script (not `time`); wall-clock from `date +%s.%N`.
3. Row 4 reported for both the stub named in the envelope and the entry chunk that carries the adopted figure.
4. A first attempt using `bash -c` was denied by a safety check and not run; nothing was removed or retried around it.

## 9 Blockers
None. Fix cycles used: 0. Registry-update request: mark T30 accepted, then archived with the merge SHA.

## 10 Follow-up
Numbers the planner may move into operating-instructions.md (cold 4-CPU container, `e8e5101`): vitest suite ~12.5 s; `tsc --noEmit` ~4.4 s; `build:islands` ~7.3 s; island entry chunk 787.6 kB raw / 184.9 kB gzip. The stub `spread-chart.js` is only 301 B, so size budgets should name `chunks/entry-*.mjs`.

## 11 Context cost
Files loaded: CLAUDE.md, T30 SPEC, operating-instructions.md (grep excerpts), package.json and vite.islands.config.mjs excerpts; roughly 15k tokens. The line that told me I am a WORKER: the first line of the envelope, `ROLE: WORKER`.
Tools by full name: `mcp__github__merge_pull_request` present; `mcp__github__create_pull_request` present; `mcp__github__update_pull_request_branch` present.
Session tools: mcp__claude-code-remote__create_session present, not called; mcp__claude-code-remote__archive_session present, not called; mcp__claude-code-remote__send_message present, not called; mcp__claude-code-remote__unarchive_session present, not called; mcp__claude-code-remote__interrupt_session present, not called; mcp__claude-code-remote__set_session_title present, not called; mcp__claude-code-remote__set_session_tags present, not called; mcp__claude-code-remote__list_sessions present, not called; mcp__claude-code-remote__get_session present, not called; mcp__claude-code-remote__list_events present, not called; mcp__claude-code-remote__get_event present, not called; mcp__ccd_session__spawn_task present, not called; mcp__ccd_session__dismiss_task present, not called.
`unmeasured` rows: none.
