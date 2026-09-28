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

**Last verified:** 2026-09-28 12:45 UTC · **main:** `a86a2f0` · **this branch:** `8b34573`
**Revision 2** — first UPDATE. Revision 1 was written at 05:19 UTC.

This is the planning state for the whole project. Every development session should start here:
*what needs doing → what comes first → what can run in parallel → which worktree → what can wait.*

This file is **not** a RIPER-5 plan artifact. It points at those and tracks what has no plan yet.
Maintained by the master planning session (see [§Maintaining this file](#maintaining-this-file)).

---

## ⚠️ Read This First — Three PRs Are In Flight

Since revision 1, three other sessions opened draft PRs. **Nothing has merged.** `main` is still at
`a86a2f0`. Merge order and one semantic gap now matter more than any individual task below.

| PR | Branch | Scope | Size | State |
|---|---|---|---|---|
| [#5](https://github.com/jamiroV-code/psychic-train/pull/5) | `claude/inspiring-pasteur-awqxk3` | chain-growth closeout → `completed/`, both review decisions recorded `approved`, context docs | 36 files | draft, clean vs main |
| [#7](https://github.com/jamiroV-code/psychic-train/pull/7) | `fix/narrative-sufficiency-gating-rfc1` | narrative-v2 RFC-1–7 | 51 files, +3663/-130 | draft, clean vs main; RFC-1–6 ✅ VERIFIED, RFC-7 CODE DONE |
| [#8](https://github.com/jamiroV-code/psychic-train/pull/8) | `claude/vigilant-hamilton-grr18c` | pytrends `isPartial` fix (T1) | 7 files | draft, clean vs main |
| [#6](https://github.com/jamiroV-code/psychic-train/pull/6) | `claude/pensive-dijkstra-ko69oi` | this file | 1 file | draft, clean vs main |

### 🔴 The gap: T1's fix does not cover narrative-v2's new fetch path

This is the single most important finding of this revision. Verified by reading both diffs.

- **PR #8** adds an `isPartial` filter — but **only inside `_fetch_live`**, the single-keyword path.
- **PR #7** adds a *second*, independent fetch path: `fetch_trends_batched` →
  `_fetch_batch_live` (RFC-3 anchor-chained batching). `grep isPartial` over PR #7's
  `pytrends_adapter.py` returns **nothing**. It does the same `df.iloc[-1]` on the same raw hourly
  frame that causes the bug.
- `api/scripts/snapshot_narrative.py:137` routes the nightly job through
  `fetch_trends_batched`, writing the `pytrends-blended/{narrative id}` namespace.
- `momentum.py` reads `pytrends-blended` as its **primary basis** (`BASIS_BLENDED`, falling back to
  composite); `mindshare.py` reads it for its pytrends source.

**Net effect if both PRs merge as they stand:** the two headline new views of narrative-v2 —
momentum and mindshare — would be built on exactly the partial-hour zeros that T1 exists to
eliminate. The old keyword-keyed path would be fixed; the new blended path would not.

**→ New task T1b below.** Do not merge PR #7 without it.

### Merge conflicts (simulated with `git merge-tree`, not assumed)

| Pair | Conflicts |
|---|---|
| #7 ↔ #8 | `api/tests/data/test_pytrends_adapter.py` (add/add), `process/context/all-context.md` (content). **`api/data/pytrends_adapter.py` auto-merges cleanly** — the two edits touch different regions. |
| #5 ↔ #8 | `all-context.md`, `data-sources/all-data-sources.md`, `tests/all-tests.md` |

All three PRs edit `process/context/all-context.md`. Whoever merges second and third resolves it.

### Recommended merge order

1. **PR #5** — onchain closeout. Smallest blast radius, unblocks T6/T11/T19.
2. **PR #8** — the targeted pytrends fix. Small, and stops the nightly loss sooner.
3. **PR #7** — largest. Rebase onto main after #8, resolve the two conflicts, and **fold T1b into
   that resolution** rather than shipping the gap and fixing it later.

---

## Verified Ground Truth

Measured on `main` at 12:45 UTC 2026-09-28. Unchanged from revision 1.

| Check | Command | Result |
|---|---|---|
| Backend tests | `uv run --project api pytest api/ -q` | **623 passed, 5 deselected** (138s) |
| Frontend unit | `cd web && pnpm test` | **181 passed, 22 files** |
| Typecheck | `pnpm --filter web exec tsc --noEmit` | exit 0 |
| Working tree | `git status` | clean |

PR #7 reports **708 / 193** on its branch — that is the post-merge figure to expect, not today's.
`process/context/tests/all-tests.md` still claims 486 / 153.

**Shipped on main:** `/screener`, `/regime`, `/narrative`, `/pairs`, `/onchain` — 5 routes,
13 endpoints, 10 adapters, 3 nightly workflows.

**Container notes:** `web/node_modules` is absent on a fresh container — `cd web && pnpm install
--frozen-lockfile` first. Egress blocks Google Trends, Reddit, CoinGecko, Hyperliquid, FRED and
DefiLlama, so every real-cache walkthrough is a user-PC step.

---

## 🔴 URGENT

### T1 — pytrends partial-hour zeros · **PR #8 open, covers half**

`_fetch_live` takes `df.iloc[-1]` of the hourly `now 7-d` frame — Google's incomplete `isPartial`
hour, usually 0. Still live in the archive as of this revision:

| Keyword | Last three nightly points |
|---|---|
| `AI crypto` | 23, 51, **0** |
| `RWA crypto` | **0, 0, 0** |
| `layer 2 crypto` | 8, **0, 0** |
| `memecoin` | 34, **0, 0** |

Google keeps no history, so every affected night is unrecoverable. The next narrative snapshot
fires at 18:17 UTC (+~2h GitHub scheduler delay ≈ **20:20 UTC**).

- **Status:** fix written in PR #8 (4-line `isPartial` filter + tests + SPEC/PLAN/REPORT closeout)
- **Worktree:** — (in PR) · **Depends on:** — · **Blocks:** T7

### T1b — **NEW** — port the `isPartial` guard into `fetch_trends_batched`

PR #7's batched path has no partial-hour handling (see §The gap above). Without this, narrative-v2's
momentum and mindshare views launch on zero-contaminated data.

- **Worktree:** A · **Depends on:** PR #8's approach (reuse the same filter)
- **Files:** `api/data/pytrends_adapter.py` (`_fetch_batch_live` or `fetch_trends_batched`),
  `api/tests/data/test_pytrends_adapter.py`
- **Do it as part of PR #7's rebase** — a separate PR would be a third edit to the same file.

### T2 — `normalize_within_source` flat-0.5 · ✅ **FIXED in PR #7 (RFC-1, VERIFIED)**

`normalize_with_sufficiency()` added alongside the untouched original; `insufficient` /
`provisional` / `mature` threaded through API, model and UI so thin data never renders as a fake
`0.50`. Closes on PR #7 merge.

---

## 🟠 HIGH PRIORITY

### T3 — narrative-v2 · **PR #7, nearly done**

RFC-1–6 ✅ VERIFIED, RFC-7 ✅ CODE DONE. Remaining: the AC-14 real-machine walkthrough (user PC,
checklist in the plan's Section 14), then RFC-7 → VERIFIED and the plan archives to `completed/`.

- **Depends on:** T1b folded in first · **Then:** unblocks T7, T10

### T4 — Reddit has never archived a single point

Still true at this revision: no `api/data/cache/narrative/reddit/` directory exists.
`narrative-snapshot.yml` has no `REDDIT_CLIENT_ID` / `REDDIT_CLIENT_SECRET`, so the source is
skipped nightly as `credentials-not-configured`. PR #7's mindshare view lists `reddit` as one of
three sources — it will render permanently empty until this is resolved.

- **Worktree:** none — **user action** · Add the secrets, or formally drop Reddit and update
  `data-sources/all-data-sources.md`.

### T5 — `/pairs` has zero automation

`backfill_pairs_universe.py` and `compute_pairs.py` are manual-only; `api/data/cache/pairs/` is
gitignored and empty. A fresh checkout serves `results_unavailable`, and the cache silently rots as
new daily bars arrive. The other three domains all have nightly workflows.

- **Worktree:** B · **Files:** new `.github/workflows/pairs-recompute.yml`,
  `api/scripts/compute_pairs.py` · ~56s compute for 153 pairs, fine for Actions.

### T6 — chain-growth closeout · ✅ **DONE in PR #5**

The user ran the AC-14 real-archive `/onchain` walkthrough on their own PC on 2026-09-28 and
approved both review gates ("looks good, approve both"). Both `review-decision.json` files now read
`"decision": "approved"`; the task folder moved to `completed/`. Closes on PR #5 merge.

### T7 — narrative-dashboard v1 closeout · still open

Two `review-decision.json` files remain `PENDING`
(`harness/review-decision.json`, `harness/rfc-004/review-decision.json`). AC-3 (cron firing) and
AC-12 (real-cache walkthrough) have never run. PR #5 closed out onchain only, not this.

- **Worktree:** none — **user PC** · **Depends on: T1 + T1b + T2** — a walkthrough against
  zero-contaminated, fabricated-0.50 data proves nothing.

### T8 — refresh the context docs · partially covered, now contended

All three in-flight PRs edit `all-context.md`, and #5 also edits `data-sources/` and `tests/`.
Between them most of revision 1's staleness (the missing `/onchain` route, the growthepie/L2BEAT
adapters, `chain_growth_config`, `api/analytics/onchain/`) gets addressed — but only after conflict
resolution, and the test counts will need a final pass once all three land.

- **Worktree:** C · **Do last**, after the three PRs merge · **Then:** `vc-audit-context`

---

## 🟡 NORMAL

| # | Task | Worktree | Depends on | Notes |
|---|---|---|---|---|
| T9 | **charting-indicators has zero code** — the 4th product area, its own guide calls it "the visual core." No `api/routers/indicators.py`, no `web/app/charts/`. | after A | T14 | needs RESEARCH → SPEC |
| T10 | **No cross-signal confidence view** — the stated north star. Five siloed dashboards; only `confidence/badge.py` (142 lines, screener-only) combines anything, and it is deliberately locked against numeric accumulation, so this must be a new module. | after A | T3 | needs SPEC |
| T11 | **Lying plan status strips** — `chain-growth_PLAN` "no code exists yet" (fixed by PR #5), `momentum-screener_PLAN` "PLANNED", `liqtide-snapshot-tooling` "EXECUTE pending approval". | C | PR #5 | 2 of 3 remain |
| T12 | **Equity provider unresolved** since 17-09-26 (`lse-data-verification` ⏳PLANNED). LSE is personal-use-only, colliding with the public-later goal. `yfinance` alternative sits unread in backlog. | — decision | — | blocks all equity work |
| T13 | **No app CI, no linter, no formatter.** Nothing runs pytest/vitest/tsc on push; zero hits for eslint/prettier/ruff/black. With 4 PRs now in flight, this is more costly than at revision 1. | B | — | new `.github/workflows/ci.yml` |
| T14 | **No shared UI shell** — 5 routes, no nav, no global CSS; 24 files use inline `style={{}}` vs 9 using `className`. PR #7 adds 2 more views to the same pattern. | after A | — | blocks T9 |
| T15 | **Redistribution flags on 4 of 10 adapters** — Standing Rule 7 half-implemented. Untagged: ccxt, coingecko, defillama, fred, liqtide, pytrends, reddit. | C | — | matters for public-later |
| T16 | **No root README** — no documented way to start either service, no runbook for the ~8 manual scripts. | B | — | |

---

## 🟢 LOW PRIORITY / HOUSEKEEPING

| # | Task | Worktree | Notes |
|---|---|---|---|
| T17 | **`.agents/skills` is a byte-identical 17 MB duplicate** of `.claude/skills` (`diff -rq` → no differences). Fails `validate-skills.mjs` and `validate-context-discovery.mjs` with *".agents/skills does not resolve to .claude/skills"*. Should be a symlink. | C | |
| T18 | **Dead code:** `cache.write_confirmed_boundaries` / `read_confirmed_boundaries` — zero production callers, tests only. Flagged in `all-context.md` and never removed. | C | |
| T19 | **Archive stale plans out of `active/`** — `momentum-screener_17-09-26/` holds 5 ✅VERIFIED sub-plans plus `dead-data-notice-unification` (DRAFT, abandoned since 20-09-26). | C | after T11 |
| T20 | **`web/tsconfig.tsbuildinfo` is committed** — must be `git checkout`-ed after every `tsc`; already caused one documented race. | B | `git rm --cached` |
| T21 | **`cache.py` refactor** — 634 lines, six near-identical per-domain path/read/write triplets. Every feature adds another. | **SOLO** | after everything merges |
| T22 | **NEW — latent cache-isolation trap.** `isolated_cache` is opt-in, not autouse, and `conftest.py` documents why ("that change has not been run"). `write_ohlcv` replaces the whole series, so a future test that forgets the fixture would destroy the user's OHLCV cache — which on their PC holds the expensive 18-coin deep-fetch history. **Checked: no current test trips this** — all 5 unisolated files monkeypatch `fetch_ohlcv` with a fake. A guard (autouse fixture, or a test asserting `CACHE_ROOT != DEFAULT_CACHE_ROOT`) would close it. | C | not a live bug |

New backlog notes filed by PR #7, carried here so they are not lost:
`screener-weekly-bars-flake_NOTE_28-09-26.md`, `mapping-tripwire-gap_NOTE_28-09-26.md`.

---

## Worktree Plan

Revision 1's WT-A is now essentially delivered inside PRs #7 and #8. The active shape has changed.

### WT-A — `narrative-landing` ← **start here**
**Tasks:** T1b, then drive PRs #8 → #7 to merge in order
**Owns:** `api/data/pytrends_adapter.py`, `api/analytics/narrative/*`, `web/components/narrative/*`
**Note:** this is now mostly *merge and conflict-resolution* work, not fresh implementation.

### WT-B — `ops-and-automation`
**Tasks:** T5, T13, T16, T20
**Owns:** `.github/workflows/`, `api/scripts/compute_pairs.py`, root `README.md`, `.gitignore`,
`web/package.json`, `api/pyproject.toml`
**Overlap with A:** none. Safe to run concurrently with the PR landings.

### WT-C — `docs-and-housekeeping`
**Tasks:** T8, T11, T15, T17, T18, T19, T22
**Owns:** `process/`, `.agents/`, adapter constants, two dead functions in `cache.py`
**⚠️ Changed:** T8 must now wait until PRs #5/#7/#8 land — all three edit `all-context.md`, so doing
it earlier guarantees a fourth conflict on the same file. The rest of WT-C can start immediately.

### Deliberately NOT parallelised
| Task | Why |
|---|---|
| T21 (`cache.py`) | central file — **solo**, after everything merges |
| T9, T10, T14 | all heavily rewrite `web/`; would collide with each other and with PR #7 |

### Not worktree work
T4 (repo secrets or a drop decision) · T7 (user-PC walkthrough + 2 review decisions) ·
T12 (product decision) · AC-14 for narrative-v2 (user PC)

---

## Dependency Graph

```
PR#5 ──> T6 ✅ ──> T11 ──> T19
                      │
PR#8 (T1, half) ──────┼──> T8 (context, after all three land)
                      │
T1b ──> PR#7 (T2 ✅, T3) ──> AC-14 (user PC) ──> T7 ──> T10
                      │
                      └──> T14 ──> T9

(everything merged) ──> T21

T5, T13, T16, T20, T15, T17, T18, T22, T4, T12  —  no blockers
```

---

## Recommended Order

1. **T1b** — close the batched-path gap before PR #7 lands, not after.
2. **Land PR #5 → #8 → #7**, resolving `all-context.md` each time.
3. **T5** — `/pairs` still has no path to staying current.
4. **AC-14 walkthrough** for narrative-v2 (user PC) → archives the plan.
5. **T7** — the last two PENDING review decisions, once the data is trustworthy.
6. **T8** — one final context pass with real post-merge test counts.
7. Housekeeping (T11, T15, T17, T18, T19, T20, T22) in any slack.
8. **T14 → T9 → T10** — remaining product build-out, each needing its own SPEC.
9. **T21** last, solo.

---

## Known Gaps Carried Forward (accepted, not tasks)

Documented, understood, deliberately unfixed. Do not re-discover these as bugs.

- **2026-09-25 narrative gap** — unrecoverable; cause (cron timing) fixed 27-09-26.
- **BTC-dominance 209-day hole**, 2025-12-07 → 2026-07-04 — no free source deeper than LiqTide.
- **Spot-ETF flows cannot exist before 2024-01-11** — product launch date, structural.
- **2017 leg-boundary backtest window untestable** — no ≥60%-coverage date before 2018-01-11.
- **Full-vs-reduced composite agreement** — LiqTide has no historical endpoint; archive grows one
  day at a time (8 days held).
- **Hyperliquid daily-history floor ~2020-08-19** — apparent, unconfirmed against their docs.
- **Hyperliquid redistribution terms unverified** — `HYPERLIQUID_REDISTRIBUTABLE = False` pending a
  user terms read.
- **No pair is BH-significant** on the 18-coin universe (closest DOGE/BCH, raw 0.00057 → BH 0.087).
  A real result, not a bug.
- **`screener.spec.ts:103` flake** — 1 of 3 full Playwright runs on PR #7's branch; isolated
  re-run passed 15/15. Judged pre-existing but *not* proven against a clean base worktree.

---

## Maintaining This File

The master planning session owns this file. On **`UPDATE`**:

1. Re-verify ground truth — run both suites and `tsc`, re-read `git log`, re-list
   `process/*/active/`. Never copy numbers from context docs; they drift.
2. **List open PRs and diff their branches.** Revision 2's most important finding came only from
   reading two PR diffs against each other — neither PR's own description revealed it.
3. Inspect live cache archives directly (`api/data/cache/**/*.parquet`) — several findings were
   visible only in the data, not in the code or the docs.
4. Simulate merges with `git merge-tree` before claiming a conflict. Revision 2 corrected an
   assumed `pytrends_adapter.py` conflict that does not actually exist.
5. Remove completed tasks. Add new ones. Re-prioritise. Re-check dependencies.
6. Reorganise worktrees if file sets now intersect — **3 active maximum**.
7. Update the `Last verified` line, the revision number, and both SHAs.
8. Keep the chat answer concise; this file carries the detail.

**Standing rule:** a task earns a place here only if it has real project impact. Do not pad the list.
