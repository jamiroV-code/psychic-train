---
name: master-plan
description: "Single source of truth for what needs doing across my_site: priority-ranked task list, worktree grouping, dependencies, and housekeeping. Maintained by the master planning session."
date: 28-09-26
metadata:
  node_type: root
  type: master-plan
  read_when: "starting any development session; deciding what to work on next; before creating a new plan artifact"
---

# my_site — Master Plan

**Last verified:** 2026-09-28 · **HEAD:** `a86a2f0` (branch `claude/pensive-dijkstra-ko69oi`, based on `main`)

This is the planning state for the whole project. Every development session should start here:
*what needs doing → what comes first → what can run in parallel → which worktree → what can wait.*

This file is **not** a RIPER-5 plan artifact. It does not replace `*_PLAN_*.md` files — it points at
them and tracks what has no plan yet. It is maintained by the master planning session (see
[§Maintaining this file](#maintaining-this-file)).

---

## Verified Ground Truth

Measured directly on 2026-09-28 at `a86a2f0` — **not** copied from context docs, which are stale.

| Check | Command | Result |
|---|---|---|
| Backend tests | `uv run --project api pytest api/ -q` | **623 passed, 5 deselected** (131s) |
| Frontend unit | `cd web && pnpm test` | **181 passed, 22 files** |
| Typecheck | `pnpm --filter web exec tsc --noEmit` | exit 0 |
| Working tree | `git status` | clean |

`process/context/tests/all-tests.md` claims 486 / 153 — **off by 137 pytest and 28 vitest**. See T8.

**Shipped surfaces:** `/screener`, `/regime`, `/narrative`, `/pairs`, `/onchain` (5 routes,
13 endpoints, 10 provider adapters, 3 nightly snapshot workflows).

**Container notes:** `web/node_modules` is absent on a fresh container — run
`cd web && pnpm install --frozen-lockfile` before any frontend command. Egress blocks Google
Trends, Reddit, CoinGecko, Hyperliquid, FRED and DefiLlama, so every real-cache walkthrough is a
user-PC step.

---

## 🔴 URGENT

### T1 — Fix pytrends partial-hour zeros (live, ongoing data loss)

`_fetch_live` takes `df.iloc[-1]` of the hourly `now 7-d` frame. That last row is Google's current,
incomplete hour (`isPartial=True`), which is usually 0.

**Verified in the live archive**, not inferred:

| Keyword | Recent nightly values |
|---|---|
| `AI crypto` | 23, 51, **0** |
| `RWA crypto` | **0, 0, 0** — every nightly point |
| `layer 2 crypto` | **0, 0** |
| `memecoin` | 34, **0, 0** |

Google Trends keeps no history, so **every night this runs, another day is destroyed and cannot be
recovered.** A backlog note was filed 27-09-26 and never actioned.

- **Worktree:** A · **Depends on:** — · **Blocks:** T7
- **Files:** `api/data/pytrends_adapter.py` (`_fetch_live`), `api/scripts/snapshot_narrative.py`,
  `api/scripts/backfill_pytrends_history.py`, `api/tests/data/`
- **Existing note:** `process/general-plans/backlog/pytrends-partial-hour-zeros_NOTE_27-09-26.md`
- **Candidate fixes (from the note):** drop `isPartial` rows before taking the last point, or store
  a daily aggregate over the last complete 24h. Either changes stored values → needs its own plan.

### T2 — Fix `normalize_within_source` flat-0.5

An all-constant series (including an all-zero one) returns a literal `0.5`, which `history.py` then
consumes as a real composite reading.

**This compounds T1.** Right now `/narrative` displays a fabricated `0.50` for the three
zero-filled categories instead of admitting insufficient data. It directly violates the repo's own
*"numbers are never silently wrong"* principle.

- **Worktree:** A · **Depends on:** land together with T1 so `/narrative` re-baselines once, not twice
- **Files:** `api/analytics/narrative/scoring.py`, `api/analytics/narrative/history.py`,
  `web/components/narrative/`
- **Already planned as:** narrative-v2 RFC-1 (see T3)

---

## 🟠 HIGH PRIORITY

### T3 — VALIDATE + EXECUTE the narrative-v2 plan

959-line COMPLEX plan, 7 RFCs, **status DRAFT — awaiting VALIDATE** since 25-09-26. RFC-1 is T2.
RFC-2→7 add a unified narrative config file, multi-keyword blending, a momentum view, a daily
mindshare view, and caveat de-duplication.

- **Worktree:** A · **Depends on:** T1/T2 fold into RFC-1
- **Plan:** `process/features/narrative-mindshare/active/narrative-v2_25-09-26/narrative-v2_PLAN_25-09-26.md`
- **Sequencing (from the plan's own strategy recommendation):** RFC-1→2→3 sequential, then RFC-4 and
  RFC-5 as two parallel execute agents (disjoint files), then RFC-6, RFC-7.

### T4 — Reddit has never archived a single data point

There is no `api/data/cache/narrative/reddit/` directory at all. `narrative-snapshot.yml` has no
`REDDIT_CLIENT_ID` / `REDDIT_CLIENT_SECRET`, so the source is skipped nightly and logged as
`credentials-not-configured`. The composite has silently been running on fewer sources than designed
since day one.

- **Worktree:** none — **user action** · **Depends on:** —
- **Decide:** add the two secrets to the GitHub repo, or formally drop Reddit from the composite and
  update `data-sources/all-data-sources.md`.

### T5 — `/pairs` has zero automation

`backfill_pairs_universe.py` and `compute_pairs.py` are manual-only. `api/data/cache/pairs/` is
gitignored and absent from the repo. Consequences:

1. A fresh checkout (including the user's PC after a clone) serves `computation_status:
   results_unavailable` until both scripts are run by hand.
2. The results cache silently goes stale as new daily bars arrive — the staleness check catches it,
   but nothing ever refreshes it.

The other three data domains (liqtide, narrative, onchain) all have nightly workflows. Pairs does not.

- **Worktree:** B · **Depends on:** —
- **Files:** new `.github/workflows/pairs-recompute.yml`, `api/scripts/compute_pairs.py`,
  `api/scripts/backfill_pairs_universe.py`, `.gitignore`
- **Note:** ~56s compute for 153 pairs — comfortably within an Actions run.

### T6 — Close out chain-growth (`/onchain`)

The feature shipped (6 RFCs code-done, EVL-confirmed, merged) but its plan still says
**"📋 PLANNED — no code exists yet."** Blocking its archival:

- AC-14 real-cache walkthrough — **user PC only** (egress blocked here). Checklist is in
  `chain-growth_RFC-006_REPORT_25-09-26.md` §"AC-14 user-PC checklist".
- `harness/rfc-003/review-decision.json` — `"decision": "PENDING"`
- `harness/rfc-004/review-decision.json` — `"decision": "PENDING"`

- **Worktree:** none — **user PC** · **Depends on:** — · **Then:** T11, T19
- **Folder:** `process/features/onchain-activity/active/chain-growth_25-09-26/`

### T7 — Close out narrative-dashboard v1

Stuck in `active/` since 24-09-26. AC-3 (cron actually firing) and AC-12 (real-cache walkthrough)
have never run; two `review-decision.json` files sit at `PENDING`.

- **Worktree:** none — **user PC** · **Depends on: T1 + T2** — a walkthrough against fabricated
  `0.50` readings proves nothing
- **Folder:** `process/features/narrative-mindshare/active/narrative-dashboard_24-09-26/`

### T8 — Refresh the context docs

`process/context/all-context.md` has **no mention anywhere** of work that has already shipped and
merged:

- the `/onchain` route and the whole `onchain-activity` feature folder
- `api/data/growthepie_adapter.py`, `api/data/l2beat_adapter.py` (adapters 9 and 10)
- `api/data/chain_growth_config.py`, `api/data/chains.json`
- `api/analytics/onchain/` (`growth.py`, `comparison.py`, `response.py`)
- `api/analytics/regime/benchmark.py`
- `.github/workflows/chain-growth-snapshot.yml`
- the `narrative-v2` plan

Test counts in `tests/all-tests.md` are wrong by 137 pytest / 28 vitest.

- **Worktree:** C · **Depends on:** — (re-run after each worktree merges)
- **Files:** `process/context/all-context.md`, `process/context/tests/all-tests.md`,
  `process/context/data-sources/all-data-sources.md`
- **Route:** `vc-update-process-agent` / `vc-generate-context`, then `vc-audit-context`

---

## 🟡 NORMAL

### T9 — charting-indicators has zero code

The 4th of the four stated product areas, described in its own guide as *"the visual core of my_site
and the surface every other feature renders into."* Nothing exists: no `api/routers/indicators.py`,
no `web/app/charts/`. `api/analytics/indicators/` exists but only serves the screener.

- **Worktree:** queue after A · **Depends on:** T14 (shared UI shell) recommended first
- **Needs:** RESEARCH → SPEC before any plan
- **Guide:** `process/features/charting-indicators/_GUIDE.md` (status: not-started)

### T10 — No cross-signal confidence view

The project's stated north star is *"turn separate signals into a confidence level that drives
position sizing."* Today there are five siloed dashboards; the only thing that combines signals is
`api/analytics/confidence/badge.py` (142 lines), and it is scoped to the screener board alone.

- **Worktree:** queue after A · **Depends on:** T3
- **Needs:** SPEC. Note `badge.py` is deliberately locked against numeric accumulation (guard test
  asserts it) — any combining surface must be a new module, not a `badge.py` refactor.

### T11 — Fix lying plan status strips

| Plan | Says | Reality |
|---|---|---|
| `chain-growth_PLAN_25-09-26.md` | "PLANNED — no code exists yet" | shipped, merged, `/onchain` live |
| `momentum-screener_PLAN_17-09-26.md` | "PLANNED" | first shipped feature |
| `liqtide-snapshot-tooling_PLAN_20-09-26.md` | "EXECUTE pending approval" | executed, report written |

- **Worktree:** C · **Depends on:** T6 (chain-growth's true final status)

### T12 — Equity data provider still unresolved

`lse-data-verification` has sat at ⏳ PLANNED since 17-09-26. No equity adapter exists in
`api/data/`. London Strategic Edge is personal-use-only, which collides with the "open to others
later" goal. A `yfinance` alternative note sits unread in backlog.

- **Worktree:** none — **decision** · Blocks every equity feature
- **Files:** `process/general-plans/active/lse-data-verification_17-09-26/`,
  `process/general-plans/backlog/yfinance-equity-source_24-09-26.md`

### T13 — No app CI, no linter, no formatter

The only automation is three snapshot crons. Nothing runs pytest / vitest / tsc on push. And there
is **no linter or formatter anywhere in the project** — `grep` for eslint, prettier, ruff, black
across `web/package.json` and `api/pyproject.toml` returns zero hits.

- **Worktree:** B · **Depends on:** —
- **Files:** new `.github/workflows/ci.yml`, `web/package.json`, `api/pyproject.toml`

### T14 — No shared UI shell

Five routes, no navigation component, no global stylesheet, no design tokens. `web/app/page.tsx` is
a bare `<ul>` of links; `layout.tsx` is 14 lines. 24 files use inline `style={{}}` against 9 using
`className`. Every dashboard reimplements its own layout.

- **Worktree:** queue after A · **Depends on:** — · **Blocks:** T9 (recommended)
- **Files:** `web/app/layout.tsx`, new global CSS, all of `web/components/*`
- **Route:** `vc-ui-ux-designer` / `vc-frontend-design`

### T15 — Redistribution flags on only 4 of 10 adapters

Standing Rule 7 (*"tag redistribution rights at the adapter boundary"*) is half-implemented. Tagged:
`etf_flows`, `growthepie`, `hyperliquid_narrative`, `l2beat`. Untagged: `ccxt`, `coingecko`,
`defillama`, `fred`, `liqtide`, `pytrends`, `reddit`. This is the mechanism that is supposed to make
the public-launch decision a config question rather than an audit.

- **Worktree:** C · **Depends on:** —
- **Files:** `api/data/*_adapter.py`, `process/context/data-sources/all-data-sources.md`

### T16 — No root README

No `README.md` anywhere — not at root, not in `api/`, not in `web/`. A fresh clone has no documented
way to start either service, and there is no runbook for the ~8 manual scripts
(`backfill_pairs_universe`, `compute_pairs`, `refresh_cache`, `backfill_primaries`,
`backfill_liqtide_series`, `backfill_pytrends_history`, `seed_e2e_cache`, `snapshot_*`).
`CLAUDE.md` / `AGENTS.md` document the agent harness, not the application.

- **Worktree:** B · **Depends on:** —

---

## 🟢 LOW PRIORITY / HOUSEKEEPING

### T17 — `.agents/skills` is a 17 MB byte-identical duplicate of `.claude/skills`

`diff -rq` returns zero differences across 35 directories; 34 MB of duplicated harness content is
committed. It fails two harness validators:

```
validate-skills.mjs            → ".agents/skills does not resolve to .claude/skills"
validate-context-discovery.mjs → ".agents/skills does not resolve to .claude/skills"
```

Should be a symlink. · **Worktree:** C

### T18 — Dead code in `cache.py`

`write_confirmed_boundaries` and `read_confirmed_boundaries` have **zero production callers** —
referenced only by their own tests. Already flagged in `all-context.md` ("has no caller") and never
removed. · **Worktree:** C · **Files:** `api/data/cache.py`

### T19 — Archive 7 stale plans out of `active/`

`process/general-plans/active/momentum-screener_17-09-26/` holds four ✅ VERIFIED sub-plans
(`ccxt-symbol-resolution`, `getjson-timeout-catch`, `reason-value-rendering`, `weekly-ohlc-anchor`,
`playwright-e2e`) plus `dead-data-notice-unification` — DRAFT, abandoned since 20-09-26.

- **Worktree:** C · **Depends on:** T11 · **Route:** `vc-audit-plans`

### T20 — `web/tsconfig.tsbuildinfo` is committed

Tracked in git, so it must be `git checkout`-ed after every `tsc --noEmit`. This already caused one
documented race (see the pair-screener RFC-005 deviations note). Gitignore it.

- **Worktree:** B · **Files:** `.gitignore`, `git rm --cached web/tsconfig.tsbuildinfo`

### T21 — `cache.py` refactor

634 lines containing six near-identical per-domain `*_path` / `read_*` / `write_*` triplets (ohlcv,
pairs, liqtide, liquidity-series, narrative, exchange, onchain). Every new feature adds another. A
generic series-store would collapse most of it.

- **Worktree: SOLO** — `cache.py` is touched by every feature; this must not run in parallel with
  anything · **Depends on:** A and B merged first

---

## Worktree Plan

Three active worktrees maximum, chosen so their file sets do not intersect.

### WT-A — `narrative-correctness` ← **start here**

**Tasks:** T1 → T2 → T3
**Owns:** `api/analytics/narrative/*`, `api/data/pytrends_adapter.py`,
`api/scripts/{snapshot_narrative,backfill_pytrends_history}.py`, `web/components/narrative/*`,
`web/lib/narrative-view-model.ts`
**Why first:** it is the only bug actively destroying unrecoverable data.

### WT-B — `ops-and-automation`

**Tasks:** T5, T13, T16, T20
**Owns:** `.github/workflows/`, `api/scripts/compute_pairs.py`,
`api/scripts/backfill_pairs_universe.py`, root `README.md`, `.gitignore`, `web/package.json`,
`api/pyproject.toml`
**Overlap with A:** none.

### WT-C — `docs-and-housekeeping`

**Tasks:** T8, T11, T15, T17, T18, T19
**Owns:** `process/`, `.agents/`, adapter module constants, two dead functions in `cache.py`
**Overlap with A or B:** none. T18's `cache.py` edit is a two-function deletion — if WT-A or WT-B
ever needs to touch `cache.py`, do T18 last.

### Deliberately NOT parallelised

| Task | Why |
|---|---|
| T21 (`cache.py` refactor) | central file, every feature depends on it — **solo**, after A + B merge |
| T9, T10, T14 | all heavily rewrite `web/` — would collide with each other; all need SPEC first |

### Not worktree work at all

| Task | Kind |
|---|---|
| T4 | GitHub repo secrets, or a decision to drop Reddit |
| T6, T7 | user-PC walkthroughs (container egress is blocked) + recording review decisions |
| T12 | a product decision, not code |

---

## Dependency Graph

```
T1 ─┬─> T2 ──> T3 ──> T10
    │           │
    └──────────>T7 (needs real data, not 0.50s)

T6 ──> T11 ──> T19

T14 ──> T9

(A + B merged) ──> T21

T5, T13, T16, T20, T8, T15, T17, T18, T4, T12  —  no blockers
```

---

## Recommended Order

1. **T1 + T2** — stop the data loss. Every day of delay costs a permanently unrecoverable day of
   Google Trends history.
2. **T8** — refresh context so the next agent is not planning against a repo state two features out
   of date.
3. **T5** — `/pairs` is the newest shipped feature and it has no path to staying current.
4. **T3** — the rest of narrative-v2.
5. **T6, T7** in parallel on the user's PC — unblocks two archivals and T11/T19.
6. Housekeeping (T11, T15, T17, T18, T19, T20) whenever a worktree has slack.
7. **T14 → T9 → T10** — the remaining product build-out, each needing its own SPEC.
8. **T21** last, solo.

---

## Known Gaps Carried Forward (accepted, not tasks)

These are documented, understood, and deliberately not being fixed. Do not re-discover them as bugs.

- **2026-09-25 narrative gap** — unrecoverable; cause (cron timing) already fixed on 27-09-26.
- **BTC-dominance 209-day hole**, 2025-12-07 → 2026-07-04 — no free source deeper than LiqTide
  exists; user chose to leave it.
- **Spot-ETF flows cannot exist before 2024-01-11** — product launch date, structural.
- **2017 leg-boundary backtest window is untestable** — reduced composite has no ≥60%-coverage date
  before 2018-01-11.
- **Full-vs-reduced liquidity composite agreement** — LiqTide has no historical endpoint; the
  archive grows one day at a time and currently holds 8 days.
- **Hyperliquid daily-history floor ~2020-08-19** — apparent, unconfirmed against Hyperliquid's docs.
- **Hyperliquid redistribution terms unverified** — `HYPERLIQUID_REDISTRIBUTABLE = False` pending a
  user terms read.
- **No pair is BH-significant** on the current 18-coin universe (closest: DOGE/BCH, raw 0.00057 →
  BH 0.087). This is a real result, not a bug.

---

## Maintaining This File

The master planning session owns this file. On **`UPDATE`**:

1. Re-verify ground truth — run both suites and `tsc`, re-read `git log`, re-list
   `process/*/active/`. Never copy numbers from context docs; they drift.
2. Inspect live cache archives directly (`api/data/cache/**/*.parquet`) — several of the findings
   above were only visible in the data, not in the code or the docs.
3. Remove completed tasks. Add newly discovered ones. Re-prioritise. Re-check dependencies.
4. Reorganise worktrees if file sets now intersect — **3 active maximum**.
5. Update the `Last verified` line and HEAD.
6. Keep the answer in chat concise; this file carries the detail.

**Standing rule:** a task earns a place here only if it has real project impact. Do not pad the list.
