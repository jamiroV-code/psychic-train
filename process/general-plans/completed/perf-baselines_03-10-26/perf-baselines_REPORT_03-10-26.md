# PERF report: performance baselines (measure only)

## 1 Task ID
PERF (branch `claude/perf-baselines`, base `main`)

## 2 Outcome
partial: api suite and `/api/pairs` measured; every web-dependent row is `unmeasured` because `web/node_modules` is absent and `pnpm install` needs network (stop condition in the envelope).

## 3 Summary
- Preflight passed: T18 gate (`write_confirmed_boundaries` gone from origin/main), task files present.
- Measured tree: `42d8ca8a9701031889118cd7c8f716fff36c6450` (= origin/main), 4 CPUs, Linux 6.18.44.
- api pytest: 870 passed, 1 skipped, 5 deselected, 1 xfailed; 296.30 s pytest, 5m08.7 s wall (run once, over 2 min; cold: first `uv run` in this sandbox).
- `/api/pairs` in-process, fixture data (153 pairs, 64,723 B body): p50 29.2 / 32.1 / 33.0 ms (median 32.1), p95 38.6 / 46.0 / 39.6 ms (median 39.6).
- Web test, tsc, build:islands, island chunk, page load: unmeasured (no node_modules; `pnpm install --offline` failed, store empty).
- No code change; only the task folder is touched. Not self-merged (network stop condition); stopped at review.

## 4 Files changed
- `process/general-plans/active/perf-baselines_03-10-26/perf_pairs_latency.py` (timing script)
- `process/general-plans/active/perf-baselines_03-10-26/perf-baselines_REPORT_03-10-26.md`

## 5 Commits
Branch `claude/perf-baselines`; commit SHA recorded by the PR (Master Planner records merge SHA).

## 6 Tests run
Commit SHA for all rows: `42d8ca8a9701031889118cd7c8f716fff36c6450`.

| Item | Value | Command | Input size | UTC time |
|---|---|---|---|---|
| api suite | 870 passed, 1 skipped, 5 deselected, 1 xfailed; 296.30 s (wall 308.7 s); single run | `time uv run --project api pytest api/ -q` | whole `api/` | 2026-10-03T15:20:37Z |
| `/api/pairs` p50, run 1 / 2 / 3 | 29.2 / 32.1 / 33.0 ms; median 32.1 ms | `PYTHONPATH=. uv run --project api python <task folder>/perf_pairs_latency.py` | 30 calls, 153 pairs, 2229 bars, body 64,723 B; in-process, fixture data, not network | 15:26:15Z / 15:26:21Z / 15:26:28Z |
| `/api/pairs` p95, run 1 / 2 / 3 | 38.6 / 46.0 / 39.6 ms; median 39.6 ms | same | same | same |
| `web test`, 3 attempts | failed in 0.88 / 0.73 / 0.72 s: `vitest: not found` (no node_modules). Not a timing | `time pnpm --filter web test` | - | 2026-10-03T15:25:50Z-52Z |
| `web tsc --noEmit`, 3 attempts | errors (cannot find module 'react'); 3.79 / 2.04 / 1.85 s. Not a valid timing | `time pnpm --filter web exec tsc --noEmit` | - | 2026-10-03T15:25:52Z-58Z |
| `pnpm install --frozen-lockfile --offline` | failed ERR_PNPM_NO_OFFLINE_TARBALL (store empty) | in `web/` | - | ~15:26Z |

Max latency outliers (184.8, 181.6 ms) occurred once each in runs 2 and 3, first-call-like spikes; they do not affect p50/p95 figures above. Machine: 4 CPUs; api run was cold (venv built by first `uv run`), pairs runs warm.

## 7 Tests NOT run
- web vitest, tsc, `build:islands`, island entry chunk gzip vs adopted 185 kB, page load (Playwright): need installed web deps (network).
- `compute_pairs.py`: reads local price cache via `cache.read_ohlcv` (no network), but `api/data/cache/` holds no OHLCV here (only liqtide, narrative, onchain), so it cannot run; adopted ~56 s / 153 pairs kept, source: recovery plan section 8 (not re-measured).
- Screener refresh at 30 coins: needs live ccxt.
- No spot re-run of the api suite (no code change since).

## 8 Deviations
- Web items not measured, stopped per the envelope's network rule. Repeats of failed web commands were run to confirm the failure is deterministic.
- Not self-merged.

## 9 Blockers
- Blocker: `web/node_modules` missing; install needs registry access. Fix: a session with network/pnpm store, or user PC run of the three web commands.
- Fix cycles used: 0.
- Registry-update request: PERF stays `review` (partial); not accepted/archived until web rows are measured or the planner accepts them as `unmeasured`.

## 10 Follow-up
Numbers the planner may move into operating-instructions.md: api suite about 5 min wall on 4 CPUs (870 passed / 1 skipped / 5 deselected / 1 xfailed); `/api/pairs` in-process fixture p50 about 32 ms, p95 about 40 ms (vs adopted network figure 135-232 ms, a different quantity). Re-run web rows where deps exist.

## 11 Context cost
Files loaded: CLAUDE.md, SPEC, operating-instructions grep lines, compute_pairs.py header, routers/pairs.py, pairs_fixtures.py, conftest.py excerpts; roughly 25k tokens. Role line: `ROLE: WORKER` in the task envelope. Merge/PR/session tools in my list: mcp__github__merge_pull_request, mcp__github__create_pull_request, mcp__github__update_pull_request_branch; session tools (mcp__claude-code-remote__create_session, archive_session, send_message and others) are present but unused.
unmeasured rows: web test wall time (no node_modules, needs network); web tsc time (same); build:islands time and island chunk gzip (same); page load (needs built app); `compute_pairs.py` re-run (no local OHLCV cache); screener refresh at 30 coins (needs live ccxt / user PC).
