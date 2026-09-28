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

**Last verified:** 2026-09-28 13:40 UTC · **main:** `e3a94bf` · **this branch:** `c02bfd6`
**Revision 3.** Revision 1 at 05:19 UTC, revision 2 at 12:45 UTC.

Every development session should start here: *what needs doing → what comes first → what can run
independently → which worktree → what can wait.*

This file is **not** a RIPER-5 plan artifact. It points at those and tracks what has no plan yet.
Maintained by the master planning session (see [§Maintaining this file](#maintaining-this-file)).

---

## ⚠️ Read This First — Branch Sprawl Is Now The Main Problem

**PR #8 merged** (main `a86a2f0` → `e3a94bf`). Since revision 2, three more branches appeared.
There are now **six unmerged branches**, and three of them duplicate work already done elsewhere.
Untangling this matters more than any single task below.

| Branch | PR | Scope | Verdict |
|---|---|---|---|
| `claude/vigilant-hamilton-grr18c` | #8 | pytrends `isPartial` fix | ✅ **merged** into main |
| `fix/narrative-sufficiency-gating-rfc1` | #7 | narrative-v2 RFC-1–7 (51 files) | **keep** — ready for review, but now `mergeable_state: dirty` |
| `claude/inspiring-pasteur-awqxk3` | #5 | chain-growth closeout + 2 path fixes | **keep** — merge first |
| `claude/narrative-v2` | — | narrative-v2 **RFC-1 only** | ❌ **abandon** — duplicate |
| `claude/split-all-context` | — | chain-growth closeout + `context-changelog.md` | **salvage the changelog only** |
| `claude/exciting-meitner-hy50kn` | — | LSE verdict, stale-status fixes, competing status board | **keep the first two** |
| `claude/kind-tesla-tat3vo`, `claude/compassionate-goldberg-o2iq49` | #1/#3/#4 | already on main | 🗑️ stale, deletable |

### The three duplications (verified by diffing, not assumed)

1. **`claude/narrative-v2` re-implements PR #7's RFC-1.** 13 of its 18 files overlap PR #7,
   including `scoring.py`, `history.py`, `models/narrative.py`, `routers/narrative.py`. PR #7 is
   strictly ahead (RFC-1–7 vs RFC-1, "next: RFC-2 Stage 0"). → **Abandon `claude/narrative-v2`.**
2. **`claude/split-all-context` re-does PR #5's chain-growth closeout** — the review-decision JSONs
   are byte-identical (same md5). But it **misses PR #5's two path fixes**, so it would leave a
   stale `active/` path in `probe_chain_sources.py`'s default output location. Its only unique
   contribution is `process/context/context-changelog.md`. → **Merge PR #5, then cherry-pick just
   the changelog.**
3. **`claude/exciting-meitner-hy50kn` adds a competing status board** — a
   `## Where We Are (status board, 2026-09-24)` section inside `all-context.md`, overlapping this
   file's job. Two status boards is exactly the split-brain this file exists to prevent. → **T24.**
   Its *other* two commits are genuinely valuable and not duplicated anywhere (T12, T11).

### 🔴 T1's fix still does not cover narrative-v2's new fetch path

Unchanged from revision 2, now sharper because PR #8 is on main:

- `_fetch_live` on main **is fixed** (`isPartial` filter, lines 66–67).
- PR #7's `fetch_trends_batched` → `_fetch_batch_live` has **no `isPartial` handling at all**
  (`grep` returns nothing). Same `df.iloc[-1]` on the same raw hourly frame.
- `snapshot_narrative.py:137` routes the nightly job through it → `pytrends-blended/{id}`.
- `momentum.py` reads `pytrends-blended` as its **primary basis**; `mindshare.py` reads it too.

PR #7's own RFC-3 gives `keywords[0]` a separate unbatched `_fetch_live` top-up, so that key
inherits main's fix. **The blended namespace does not.** After PR #7 merges as it stands,
`pytrends/{keywords[0]}` would be clean while `pytrends-blended/*` — the basis for both new views —
stays contaminated. → **T1b.**

### Merge order

1. **PR #5** — smallest, has the path fixes `split-all-context` lacks.
2. **PR #7** — resolve the `dirty` state (conflicts: `api/tests/data/test_pytrends_adapter.py`,
   `process/context/all-context.md`), **and fold T1b into that same rebase**.
3. **`claude/exciting-meitner-hy50kn`** — after deciding T24.
4. **`context-changelog.md`** cherry-picked from `split-all-context`; drop the rest of that branch.
5. Delete `claude/narrative-v2`, `claude/kind-tesla-tat3vo`,
   `claude/compassionate-goldberg-o2iq49`.

`process/context/all-context.md` is touched by PR #5, PR #7, `split-all-context` and
`exciting-meitner` — **four-way contention**, on top of the edit #8 already landed.

---

## Verified Ground Truth

Measured at 13:40 UTC on main `e3a94bf` merged into this branch.

| Check | Command | Result | Δ since rev 2 |
|---|---|---|---|
| Backend tests | `uv run --project api pytest api/ -q` | **626 passed, 5 deselected** | +3 (PR #8's tests) |
| Frontend unit | `cd web && pnpm test` | **181 passed, 22 files** | — |
| Typecheck | `pnpm --filter web exec tsc --noEmit` | exit 0 | — |
| Working tree | `git status` | clean | — |

PR #7 reports **708 / 193** on its branch — the figure to expect after it lands, not today's.
`process/context/tests/all-tests.md` still claims 486 / 153.

**Live narrative archive:** unchanged, last point **2026-09-27, all four keywords `0.0`**. The next
snapshot fires 18:17 UTC (+~2h scheduler delay ≈ **20:20 UTC**) and will be **the first run with
the fix on main.** Worth checking tomorrow that real values land.

**Container notes:** `cd web && pnpm install --frozen-lockfile` first on a fresh container. Egress
blocks Google Trends, Reddit, CoinGecko, Hyperliquid, FRED, DefiLlama — all real-cache walkthroughs
are user-PC steps.

---

## 🔴 URGENT

### T1 — pytrends partial-hour zeros · ✅ **half done, merged**

PR #8 landed the `isPartial` filter in `_fetch_live` plus tests and a SPEC/PLAN/REPORT closeout.
The single-keyword path is fixed on main. **T1b is the remaining half.**

### T1b — port the `isPartial` guard into `fetch_trends_batched`

Without it, narrative-v2's momentum and mindshare views launch on the same zeros T1 removed.

- **Worktree:** A · **Files:** `api/data/pytrends_adapter.py` (`_fetch_batch_live` /
  `fetch_trends_batched`), `api/tests/data/test_pytrends_adapter.py`
- **Do it inside PR #7's conflict resolution** — that file already needs touching there, and a
  separate PR would be a third concurrent edit to it.

### T23 — **NEW** — reconcile the six unmerged branches

Three pairs duplicate each other (see §Branch sprawl). Every day this persists, conflicts multiply
and sessions redo finished work. Decide keep/abandon per the table above, then merge in order.

- **Worktree:** A · **Depends on:** — · **Blocks:** T1b, T3, T8, T11, T12

---

## 🟠 HIGH PRIORITY

### T3 — narrative-v2 · **PR #7, blocked on conflicts + T1b**

RFC-1–6 ✅ VERIFIED, RFC-7 ✅ CODE DONE. Now `mergeable_state: dirty` and no longer draft.
Remaining after merge: the AC-14 real-machine walkthrough (user PC, plan Section 14) → RFC-7
VERIFIED → archive to `completed/`.

- **Depends on:** T23, T1b

### T4 — Reddit has never archived a single point

Still true: no `api/data/cache/narrative/reddit/` directory exists. `narrative-snapshot.yml` has no
`REDDIT_CLIENT_ID` / `REDDIT_CLIENT_SECRET`, so the source is skipped nightly as
`credentials-not-configured`. PR #7's mindshare view lists `reddit` as one of three sources — it
will render permanently empty until this is resolved.

- **user action** — add the secrets, or drop Reddit and update `data-sources/all-data-sources.md`.

### T5 — `/pairs` has zero automation

`backfill_pairs_universe.py` and `compute_pairs.py` are manual-only; `api/data/cache/pairs/` is
gitignored and empty. Fresh checkouts serve `results_unavailable`; the cache rots as new bars land.
The other three data domains all have nightly workflows.

- **Worktree:** B · new `.github/workflows/pairs-recompute.yml` · ~56s for 153 pairs.

### T7 — narrative-dashboard v1 closeout · still open

Two `review-decision.json` files remain `PENDING`; AC-3 and AC-12 have never run.

- **user PC** · **Depends on: T1b + T3** — a walkthrough against contaminated blended data proves
  nothing.

### T8 — refresh the context docs · contended four ways

Between PR #5, PR #7, `split-all-context` and `exciting-meitner`, most of revision 1's staleness
gets addressed — but only after conflict resolution, and test counts need a final pass afterwards.
`split-all-context` also proposes splitting change history into `context-changelog.md`, which is a
good idea independent of the rest of that branch.

- **Worktree:** C · **Do last**, after T23 · then `vc-audit-context`

---

## 🟡 NORMAL

| # | Task | Worktree | Depends on | Notes |
|---|---|---|---|---|
| T24 | **NEW — one status board, not two.** `exciting-meitner` adds `## Where We Are` to `all-context.md`; this file already does that job. Pick one home and make the other point at it. | C | T23 | split-brain risk |
| T12 | **Equity provider** — ✅ **answered on `exciting-meitner`**: LSE verdict is **ADOPT-WITH-LIMITS, private use only**. Terms §6 forbid redistribution; §7 forbids derivative works without consent. **Public launch: NO without a separate LSE licence.** Needs merging, then a decision on whether to adopt under those limits or pursue `yfinance`. | — decision | T23 | `completed/lse-data-verification_17-09-26/VERDICT.md` |
| T9 | **charting-indicators has zero code** — the 4th product area, its guide calls it "the visual core." No `api/routers/indicators.py`, no `web/app/charts/`. | after A | T14 | needs RESEARCH → SPEC |
| T10 | **No cross-signal confidence view** — the stated north star. Five siloed dashboards; only `confidence/badge.py` (142 lines, screener-only) combines anything, and it is deliberately locked against numeric accumulation, so this must be a new module. | after A | T3 | needs SPEC |
| T11 | **Lying plan status strips** — `exciting-meitner` fixes `liqtide-snapshot-tooling` and `momentum-screener`; PR #5 fixes `chain-growth`. Merging both closes this. | C | T23 | mostly done, unmerged |
| T13 | **No app CI, no linter, no formatter.** Nothing runs pytest/vitest/tsc on push; zero hits for eslint/prettier/ruff/black. With 6 branches in flight this is now actively expensive. | B | — | new `.github/workflows/ci.yml` |
| T14 | **No shared UI shell** — 5 routes, no nav, no global CSS; 24 files use inline `style={{}}` vs 9 using `className`. PR #7 adds 2 more views in the same pattern. | after A | — | blocks T9 |
| T15 | **Redistribution flags on 4 of 10 adapters** — Standing Rule 7 half-implemented. Untagged: ccxt, coingecko, defillama, fred, liqtide, pytrends, reddit. T12's verdict makes this sharper. | C | — | public-later gate |
| T16 | **No root README** — no documented way to start either service, no runbook for the ~8 manual scripts. | B | — | |

---

## 🟢 LOW PRIORITY / HOUSEKEEPING

| # | Task | Worktree | Notes |
|---|---|---|---|
| T25 | **NEW — delete stale branches.** `claude/kind-tesla-tat3vo` and `claude/compassionate-goldberg-o2iq49` hold content already on main (PRs #1/#3/#4, all closed). Plus `claude/narrative-v2` once abandoned. | C | after T23 |
| T17 | **`.agents/skills` is a byte-identical 17 MB duplicate** of `.claude/skills`. Fails `validate-skills.mjs` and `validate-context-discovery.mjs`. Should be a symlink. | C | |
| T18 | **Dead code:** `cache.write_confirmed_boundaries` / `read_confirmed_boundaries` — zero production callers. | C | |
| T19 | **Archive stale plans out of `active/`** — `momentum-screener_17-09-26/` holds 5 ✅VERIFIED sub-plans plus `dead-data-notice-unification` (DRAFT, abandoned 20-09-26). | C | after T11 |
| T20 | **`web/tsconfig.tsbuildinfo` is committed** — must be `git checkout`-ed after every `tsc`; caused one documented race. | B | `git rm --cached` |
| T21 | **`cache.py` refactor** — 634 lines, six near-identical per-domain path/read/write triplets. | **SOLO** | after everything merges |
| T22 | **Latent cache-isolation trap.** `isolated_cache` is opt-in and `conftest.py` documents why. `write_ohlcv` replaces whole series, so a future test that forgets the fixture would destroy the user's deep-fetch OHLCV history. **Checked: no current test trips it** — all 5 unisolated files monkeypatch `fetch_ohlcv`. | C | not a live bug |

Backlog notes filed by PR #7, carried here so they are not lost:
`screener-weekly-bars-flake_NOTE_28-09-26.md`, `mapping-tripwire-gap_NOTE_28-09-26.md`.

---

## Worktree Plan

### WT-A — `land-the-branches` ← **start here**
**Tasks:** T23 → T1b → merge PR #5 → merge PR #7
**Owns:** branch reconciliation, `api/data/pytrends_adapter.py`, `api/analytics/narrative/*`
This is merge and conflict work now, not fresh implementation.

### WT-B — `ops-and-automation`
**Tasks:** T5, T13, T16, T20
**Owns:** `.github/workflows/`, `api/scripts/compute_pairs.py`, `README.md`, `.gitignore`,
`web/package.json`, `api/pyproject.toml`
No overlap with A. Safe to run concurrently — and T13 would have caught the PR #7 conflict earlier.

### WT-C — `docs-and-housekeeping`
**Tasks:** T24, T8, T11, T15, T17, T18, T19, T22, T25
**Owns:** `process/`, `.agents/`, adapter constants, two dead functions in `cache.py`
**⚠️ T8, T11, T24, T25 all wait on T23.** T15, T17, T18, T22 can start now.

### Deliberately NOT parallelised
| Task | Why |
|---|---|
| T21 (`cache.py`) | central file — **solo**, after everything merges |
| T9, T10, T14 | all heavily rewrite `web/`; would collide with each other and with PR #7 |

### Not worktree work
T4 (repo secrets or a drop decision) · T7 and narrative-v2 AC-14 (user PC) · T12 (adopt LSE under
its limits, or pursue yfinance)

---

## Dependency Graph

```
T23 (reconcile branches) ─┬─> T1b ──> PR#7 (T3) ──> AC-14 ──> T7 ──> T10
                          │                    └──> T14 ──> T9
                          ├─> PR#5 ──> T11 ──> T19
                          ├─> exciting-meitner ──> T12, T11, T24
                          ├─> context-changelog ──> T8
                          └─> T25 (delete stale branches)

(everything merged) ──> T21

T5, T13, T16, T20, T15, T17, T18, T22, T4  —  no blockers
```

---

## Recommended Order

1. **T23** — decide keep/abandon across the six branches. Everything else is downstream.
2. **T1b**, folded into PR #7's conflict resolution.
3. **Merge PR #5 → PR #7 → exciting-meitner → the changelog cherry-pick.**
4. **T5** — `/pairs` still has no path to staying current.
5. **AC-14 walkthrough** for narrative-v2 (user PC) → archives the plan.
6. **T7** — the last two PENDING review decisions, once the data is trustworthy.
7. **T24 + T8** — one status board, one final context pass with real post-merge counts.
8. Housekeeping (T11, T15, T17, T18, T19, T20, T22, T25).
9. **T14 → T9 → T10** — remaining product build-out, each needing its own SPEC.
10. **T21** last, solo.

**Check tomorrow:** the 20:20 UTC narrative run is the first with T1's fix. Confirm real values
land in `api/data/cache/narrative/pytrends/*.parquet` instead of zeros.

---

## Known Gaps Carried Forward (accepted, not tasks)

Documented, understood, deliberately unfixed. Do not re-discover these as bugs.

- **2026-09-25 narrative gap** — unrecoverable; cause (cron timing) fixed 27-09-26.
- **2026-09-24 → 09-27 pytrends zeros** — also unrecoverable; the fix is forward-only.
- **BTC-dominance 209-day hole**, 2025-12-07 → 2026-07-04 — no free source deeper than LiqTide.
- **Spot-ETF flows cannot exist before 2024-01-11** — product launch date, structural.
- **2017 leg-boundary backtest window untestable** — no ≥60%-coverage date before 2018-01-11.
- **Full-vs-reduced composite agreement** — LiqTide has no historical endpoint; archive grows one
  day at a time.
- **Hyperliquid daily-history floor ~2020-08-19** — apparent, unconfirmed against their docs.
- **Hyperliquid redistribution terms unverified** — `HYPERLIQUID_REDISTRIBUTABLE = False`.
- **No pair is BH-significant** on the 18-coin universe (closest DOGE/BCH, raw 0.00057 → BH 0.087).
  A real result, not a bug.
- **`screener.spec.ts:103` flake** — 1 of 3 full Playwright runs on PR #7's branch; isolated re-run
  passed 15/15. Judged pre-existing but not proven against a clean base worktree.

---

## Maintaining This File

The master planning session owns this file. On **`UPDATE`**:

1. Re-verify ground truth — run both suites and `tsc`, re-read `git log`, re-list
   `process/*/active/`. Never copy numbers from context docs; they drift.
2. **`git fetch` and diff every branch, not just the ones with PRs.** Revision 3's main finding —
   three duplicated efforts — came from branches that had no PR open at all.
3. **Diff PR branches against each other**, not only against main. Revision 2's finding came only
   from reading two PRs side by side; neither PR's description revealed it.
4. Inspect live cache archives directly (`api/data/cache/**/*.parquet`).
5. Simulate merges with `git merge-tree` before claiming a conflict. Revision 2 corrected an assumed
   `pytrends_adapter.py` conflict that did not exist; revision 3 confirmed the real one via
   `mergeable_state: dirty`.
6. Remove completed tasks. Add new ones. Re-prioritise. Re-check dependencies.
7. Reorganise worktrees if file sets now intersect — **3 active maximum**.
8. Update the `Last verified` line, the revision number, and both SHAs.
9. Keep the chat answer concise; this file carries the detail.

**Standing rule:** a task earns a place here only if it has real project impact. Do not pad the list.
