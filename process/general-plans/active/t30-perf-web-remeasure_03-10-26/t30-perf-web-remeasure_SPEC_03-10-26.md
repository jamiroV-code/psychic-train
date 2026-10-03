---
name: spec:t30-perf-web-remeasure
description: "Brief T30 (proposed, NOT approved): re-measure the four web performance rows PERF left unmeasured (web test, tsc, build:islands time, island chunk size)"
date: 03-10-26
feature: general
---

# T30 - PERF-web re-measure (brief only, proposed)

**TL;DR:** PERF (PR #24, `487fa65`) recorded four web rows as unmeasured because `node_modules` was missing. The T18 worker ran `pnpm install --frozen-lockfile` in `web/` the same day, so they were likely measurable. Re-measure them. Status `proposed`: no worker may start until the user approves; no envelope exists yet.

Registry row: T30 in `process/MASTER-PLAN.md`.

## Rows to measure

`pnpm --filter web test` wall time; `pnpm --filter web exec tsc --noEmit` wall time; `cd web && pnpm build:islands` wall time; island chunk size (raw and gzip). Three runs each, record command, UTC time, SHA, machine caveat. Measure only; no code change.

## Not in scope

`compute_pairs.py` re-run (no local OHLCV cache; adopted ~56 s stays labelled by source), screener refresh at 30 coins and page load (need live ccxt or the user's PC): stay `unmeasured`.

## Ownership and tests

Owned: this task folder only. Tier RT0, full-suite budget 0 (timing runs are the deliverable; tracked files unchanged, `git status --porcelain` empty apart from the folder). Install step: `pnpm install --frozen-lockfile` in `web/` is allowed if it changes no tracked file.

## Acceptance

All four rows have numbers with command, UTC time and SHA in the report, or a stated reason a row is still unmeasured. A rows-table in the report.
