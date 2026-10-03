---
name: spec:perf-baselines
description: "Worker brief PERF (proposed, not approved): measure-only performance baselines from the master-planner-recovery plan section 8 list; offline/local timings only; no code change"
date: 03-10-26
feature: general
---

# PERF - record performance baselines (worker brief, measure only)

**TL;DR:** Time what can be timed offline, write command, input size, UTC timestamp and commit next to each number, change no code. Status `proposed`: no worker may start until the user approves and VALIDATE passes. Rule being served: no optimization task is approved without a recorded baseline (recovery plan section 8).

Registry row: PERF in `process/MASTER-PLAN.md`. Envelope after VALIDATE and approval (`perf-baselines_REF_03-10-26.md`).

## Section 8 list and what is measurable here

The cloud sandbox cannot reach data providers (yfinance, ccxt, CoinGecko, pytrends, FRED, DefiLlama), so only offline or local-test timings are possible. Anything needing live data is recorded as `unmeasured: needs provider access / user PC`, never estimated.

| Item (plan section 8) | Measure | Command | Offline? |
|---|---|---|---|
| test suite wall time, api | `time uv run --project api pytest api/ -q` (record passed/deselected counts) | as shown | yes |
| test suite wall time, web | `time pnpm --filter web test`; `time pnpm --filter web exec tsc --noEmit` | as shown | yes |
| build time | `time (cd web && pnpm build:islands)`; island entry chunk gzip size from build output | as shown | yes |
| island entry chunk (adopted 185 kB gzipped) | re-measure, compare | build output | yes |
| `/api/pairs` read latency (adopted p95 135-232 ms) | in-process FastAPI `TestClient` over fixture or local-cache data, 30 calls, record p50/p95; label "in-process, fixture data, not network" | small script kept in the task folder only | only if it runs without network; else unmeasured |
| `compute_pairs.py` ~56 s / 153 pairs (adopted) | rerun only if inputs are local cache with no fetch; else keep adopted figure labelled by source | check script's data source first | likely no |
| screener refresh at 30 coins | needs live ccxt | - | no: unmeasured |
| page load | needs built app plus data; Playwright timing only if browsers are installed, else unmeasured | `cd web && pnpm test:e2e` timing | maybe |

Repeat each fast command 3 times and record all runs plus the median; suites over 2 minutes run once. Note machine facts (CPU count, cold vs warm cache) in the report.

## Where recorded

In the task folder report `perf-baselines_REPORT_03-10-26.md`, heading 6 (tests run) and 11 (unmeasured), as a table: item, value, command, input size, UTC time, commit SHA. The planner later moves accepted numbers into `process/context/operating-instructions.md` or a context doc. The worker does not edit context docs.

## Acceptance

Every row of the table has a measured value with its provenance or an explicit `unmeasured: <reason>`; `git status` shows no change outside the task folder; the three suites still pass (they are the measurement).

## Ownership

- Owned: this task folder only (`process/general-plans/active/perf-baselines_03-10-26/**`), including any throwaway timing script.
- Forbidden: all of `api/**`, `web/**`, `deploy/**`, `.github/**`, `process/context/**`, `process/MASTER-PLAN.md`, `CLAUDE.md`, `AGENTS.md`, `README.md`, `.claude/**`. Build output stays untracked (`web/` build artefacts must not be committed).
- Overlap: none. Running while T18 is in flight would time a moving tree: serialize PERF after T18 merges, or record the commit SHA of the tree measured.

## Tests

Tier RT0 (no code change). The measurement runs are the three suites once each plus repeats for timing only. Budget: 3 suite runs + timing repeats; no vc-tester confirmation of numbers beyond a spot re-run.

## Stop and report at `review` if

Any command needs network, any file outside the task folder would change, or a number looks implausible (re-run once, then report both).
