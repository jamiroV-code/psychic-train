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

**Last verified:** 2026-09-28 14:47 UTC · **main:** `e9c33fe` · **this branch:** `3a543ff`
**Revision 3a** (urgent amendment: PR #7 merged with T1b unfixed). Revisions 1/2/3 at 05:19 /
12:45 / 13:40 UTC.

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

**The repo's own docs corroborate this, and get one fact wrong.** `all-context.md` on main
(lines 47–48) states the fix left `_fetch_live`'s signature and call sites alone "deliberately, so
the **not-yet-started** `narrative-v2` RFC-3 (a separate, still-active plan that **will later add an
additive batched-fetch function to this same file**) is unaffected." The design intent is exactly as
described — but RFC-3 is not "not-yet-started": PR #7 has it implemented, marked ✅ VERIFIED and
open for review, and the batched function already exists on that branch. A session reading
`all-context.md` alone would conclude there is no batched path yet and therefore nothing to guard.
Correct this line as part of T8.

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

---

## 🎯 New Direction (2026-09-28, user): deployed always-on app + smooth UI

The goal moved from "keep the research tooling correct" to **"a workable app for everyday use."**
User decisions this session:

| Decision | Answer |
|---|---|
| How to run it | **Deployed, always-on** (reachable from any device, not just the PC) |
| UI | Own worktree — `claude/ui-shell` at `/home/user/psychic-train-ui`; user will give detailed direction there |
| Daily-driver page | No preference — treat all five as equal |
| Reddit (T4) | **Leave for now.** Mindshare keeps showing a permanently empty third source. |

### ⚠️ The constraint deployment runs into

Three shipped adapters are tagged **non-redistributable**: `etf_flows_adapter` (Farside),
`l2beat_adapter`, and `hyperliquid_narrative_adapter` (unverified terms). T12's LSE verdict says
the same for equities. `all-context.md` also records that auth and multi-tenancy are *deliberately
out of scope* "until the research tooling works."

An always-on deployment therefore **must be private to you**. That does not mean building real
auth — a single-user gate (Cloudflare Access, Tailscale, or HTTP basic at the proxy) satisfies it
cheaply. What it rules out is a publicly reachable URL. Flagging, not blocking: the decision is
yours and the work proceeds either way.

### What "deployed + full pipeline" actually requires

**P1 — Pipeline completeness** (needed regardless of where it deploys)
Today 3 GitHub crons cover liqtide / narrative / onchain. Nothing schedules the rest:
- `refresh_cache.py` — OHLCV tails, feeds `/screener` **and** `/pairs`
- `backfill_primaries.py` — FRED series, feeds `/regime`
- `compute_pairs.py` — pair stats, must re-run after each OHLCV refresh (T5)

Plus the split-brain: liqtide/narrative/onchain archives are committed to the repo, while
ohlcv/liquidity/legs/pairs are gitignored and local-only. A deployed instance needs one coherent
story for both.

**P2 — Deployability**
- `api/main.py` binds `127.0.0.1` by design and CORS is `localhost:3000` only — both need to change
- Parquet + DuckDB means **files on disk**, so a persistent volume is required; a stateless PaaS
  will not work without one
- Single-user access gate (see constraint above)
- Config/secrets: `API_BASE_URL`, CORS origins
- **Open decision: the deploy target itself.** Materially changes the work — see Open Decisions.

**P3 — UI** (parallel, own worktree, user-directed)
Currently: 5 routes, no nav, no global CSS, `layout.tsx` is 14 lines, `page.tsx` is a bare list of
links, 24 files use inline `style={{}}` against 9 using `className`. T14 and T24 fold into this.

### Active parallel lanes (3 — at the cap)

Set up 2026-09-28 15:03 UTC. Blast radii are deliberately disjoint; each lane's prompt names what
it must not touch, so they can run simultaneously without conflicting.

| Lane | Branch | Where | Owns | Must NOT touch |
|---|---|---|---|---|
| **P1 — pipeline** | `claude/p1-pipeline` | cloud session | `api/scripts/`, `.github/workflows/`, `.gitignore` | `web/`, `api/main.py`, `pytrends_adapter.py` |
| **P2 — deploy** | `claude/p2-deploy` | cloud session | `api/main.py`, deploy config + docs | `web/`, `api/scripts/`, workflows, `.gitignore` |
| **P3 — UI** | `claude/ui-shell` | local worktree `/home/user/psychic-train-ui`, also pushed | `web/` | everything under `api/` |

All three branch from `main` (`e9c33fe`). The planning branch
(`claude/pensive-dijkstra-ko69oi`) is not a work lane — it carries this file plus the pending T1b
fix in PR #6.

**Shared-file watch:** P1 and P2 could both want `.github/workflows/` (P1 for refresh crons, P2 for
a deploy workflow). P2 is explicitly instructed to write any workflow need up as a requirement for
P1 rather than implementing it. P2 is SPEC-first and should produce little code, which keeps the
overlap small — but check this at the next UPDATE.

**P2 has a hard stop built in:** it must surface the deploy-target choice and wait. Creating paid
infrastructure or a publicly reachable endpoint is irreversible and outward-facing, so it needs the
user's explicit go-ahead rather than a session's judgement call.

### Phase order

```
P0 (today)  merge PR #6's fix before ~20:20 UTC · clear the 4 leftover branches
P1          pipeline automation — the 3 missing scheduled jobs + one cache story
P2          deployability — needs a SPEC (deploy target + access gate are real decisions)
P3          UI — runs in PARALLEL with P1/P2, touches web/ only
```

P1 and P3 are disjoint (`api/` + workflows vs `web/`), so they fit the 3-worktree model with a slot
left for housekeeping.


---

## 🟢 T1/T1b confirmed on live data (2026-09-29) — plus a new cron finding

The first nightly run carrying both guards (run #5, `2026-09-28T23:18:44Z`, conclusion `success`,
commit `f13c0bd`) wrote:

| Series | 09-27 (pre-fix) | 09-28 (post-fix) |
|---|---|---|
| `pytrends/AI crypto` | 0.0 | **27.0** ✅ |
| `pytrends/memecoin` | 0.0 | **51.0** ✅ |
| `pytrends-blended/ai` | — (namespace did not exist) | **13.5** ✅ |
| `pytrends-blended/memecoins` | — | **8.0** ✅ |
| `pytrends/RWA crypto` | 0.0 | 0.0 |
| `pytrends/layer 2 crypto` | 0.0 | 0.0 |
| `pytrends-blended/rwa` | — | 0.0 |
| `pytrends-blended/l2s` | — | 0.0 |

**Both paths are confirmed working on live data**, not just by unit test — T1's single-keyword path
and T1b's batched path each produced real values where they previously wrote zeros.

**The remaining zeros are a different question, and probably not a bug.** After the fix a `0.0`
written with `source_status: fresh` comes from a *complete* hour — Google genuinely reported zero
interest — which is honest, unlike the pre-fix zeros taken from an incomplete hour. Not provable
from the archive alone; it needs the raw frame. But the likely reading is that **"RWA crypto" and
"layer 2 crypto" are too low-volume for Google Trends' 0–100 scale over a 7-day window**, so those
two narratives have honest data and no usable signal. That is a product problem, not a correctness
one. RFC-1's sufficiency gating should render them `insufficient` rather than a fake `0.50` —
worth confirming during the AC-14 walkthrough. **New task: T26.**

### 🔴 New: the GitHub scheduler delay is far worse than documented

| Run | Cron | Started | Delay |
|---|---|---|---|
| #3 (09-26) | `0 23` | 01:03:21Z | 2h03m |
| #4 (09-27) | `17 18` | 21:23:31Z | 3h06m |
| **#5 (09-28)** | `17 18` | **23:18:44Z** | **5h01m** |

Run #5 committed at **23:19:22Z — 41 minutes before UTC midnight.** Narrative points are dated by
the UTC day the run executes, so it came within 41 minutes of skipping a day. That is precisely the
failure the 2026-09-27 cron-timing fix existed to prevent, and its own claim — "even a ~2h20m delay
now lands every run before ~21:10 UTC" — is now contradicted three times over.

`api/tests/scripts/test_snapshot_workflow_schedules.py` pins each cron ≥3h before midnight, but it
can only test the *scheduled* time, never the *observed* delay — so the guard passed while reality
nearly failed. **New task: T27.** This belongs to P1 (`claude/p1-pipeline`), which owns the
workflows and is active right now.


---

## Lane status (2026-09-29 18:40 UTC)

All three lanes stalled overnight on the account's 5-hour rate limit, not on the work. Limits have
since reset. P3 alone cost **$70.57**; three concurrent Opus cloud sessions saturate the budget in
well under an hour, which is worth pacing around.

| Lane | Branch | Ahead of main | State |
|---|---|---|---|
| P1 — pipeline | `claude/p1-pipeline` | 6 commits | SPEC + PLAN + PVL (gate CONDITIONAL) + 2 new workflows + atomic-writes plan |
| P2 — deploy | `claude/p2-deploy` | 4 commits | **SPEC complete, decisions recorded.** Successor session `P2b` started for PLAN → VALIDATE → EXECUTE |
| P3 — UI | `claude/ui-shell` | 11 commits | Audit + "Direction D" + a built foundation (tokens, dark shell, `AppNav`, `OwlMark`, styled screener) |

### P2's decision, now locked

| Question | Answer |
|---|---|
| Hosting | **A home box the user already owns** — the *same PC* that holds the gitignored caches. ~$0/month. |
| Access gate | **Tailscale**, free tier |
| Always-on? | **No — intermittent.** Phase 1 is explicitly designed for downtime. |

This is a better answer than any cloud target: no public endpoint ever exists, which is the
*strongest* position against the non-redistributable-adapter constraint rather than merely an
adequate one; volume sizing becomes moot; and the cache split-brain evaporates because there is no
cache to move. T8's split-brain concern is therefore **descoped for Phase 1** (it returns in Phase 2
if a true always-on box ever replaces the PC).

### 🔴 T28 — **NEW** — parquet writes are not atomic

Found by P2, being planned by P1 (`df2c3c9`). `api/data/cache.py`'s parquet writers call
`to_parquet(path)` directly at ~9 sites; only the two JSON writers use temp-then-rename. Several are
read-modify-write. On a PC that can lose power mid-write this can **truncate a file and destroy
existing history**, not merely lose the new row — and the gitignored caches (`ohlcv`, `liquidity`,
`pairs`, `legs`) have no git copy to restore from. OHLCV is the most expensive to rebuild (18
sequential deep fetches).

This became a live risk the moment the deploy target became an intermittently-powered home box.
The fix is small and already proven twice in that same file. **Owner: P1** (it claimed the file);
P2's auto-resume design is gated on it.

### T27 sharpened — it now covers five workflows

P1's two new crons (`pairs-refresh` 19:17, `liquidity-backfill` 19:47) inherited the stale "~2h
late" figure in their comments. At the measured 5h01m delay they start 00:18Z and 00:48Z — **past
UTC midnight.** Harmless for those two specifically (OHLCV/FRED/pairs are catch-up-safe, as P1
correctly reasoned), but the comments assert otherwise and will mislead. The real exposure remains
`narrative-snapshot.yml`. Relayed to P1 on 29-09 with the measured numbers.

**Credit where due:** P1 honored P2's hard rule — no-history jobs (narrative, liqtide, chain-growth)
stay pinned to GitHub Actions and were *not* consolidated onto the PC — and was explicit that its
new commit steps are inert while those caches stay gitignored. That cross-lane constraint held
without either lane being able to talk to the other directly.


---

## Revision 4 — 2026-10-01: all three lanes finished, nothing merged

**main is `936bd3c`** and contains only nightly snapshot commits. Every lane's work is still on its
branch. The app is running on the user's PC (P2's walkthrough succeeded) but the UI is not
integrated, because `claude/ui-shell` has not been merged.

### All three lanes merge cleanly — nothing technical blocks merging

Verified with `git merge-tree` on all three pairs: **no conflicts.** The only file two lanes both
touch is `.gitignore` (P1 adds `api/data/cache/**/*.tmp`, P3 adds `web/public/islands/`) and the
edits are additive. **Merge order does not matter.**

| Lane | Branch | Ahead | Verified state |
|---|---|---|---|
| P1 | `claude/p1-pipeline` | +16 | 3 plans, UPDATE PROCESS closeout (WITH_GAPS). T27 and T28 both fixed. |
| P2 | `claude/p2-deploy` | +9 | SPEC → PLAN → validate (CONDITIONAL, user-accepted) → EXECUTE. Tailscale launchers, CORS tightening, different-PC migration runbook. |
| P3 | `claude/ui-shell` | +12 | **223 vitest passed / 30 files, `tsc` exit 0, island build succeeds.** Green. |

### 🔴 Decide before merging P3: the charting stack was replaced

P3 went well beyond a UI shell. `web/package.json` on that branch:

- **removed**: `lightweight-charts`
- **added**: `svelte` 5, `layerchart` 2.5, `@skeletonlabs/skeleton` + `-react` 5, `tailwindcss` 4,
  `d3-scale`, `vite` + `@sveltejs/vite-plugin-svelte`
- **new build step**: `build:islands` (a separate vite build) now runs before `next build`, emitting
  `web/public/islands/` — a 787 kB entry chunk, 185 kB gzipped

Every chart on all five routes was converted to a Svelte island (`/pairs`, `/regime`, `/narrative`,
`/onchain`, `/screener`), and the `lightweight-charts` code was deleted. P3 recorded the decision
itself in an ADR-1 ("islands, not SvelteKit").

**This contradicts `process/context/all-context.md`**, which lists `lightweight-charts` as a settled
stack choice and cites it as one of the two reasons the web/api split exists at all ("Charting is
the reverse: `lightweight-charts` is the best free financial charting library and it is a browser
library"). If the user directed this — likely, given they were steering P3 interactively — it is a
legitimate decision that now needs promoting out of a branch-local ADR into the context docs, and
the bundle size is worth comparing against what it replaced. If it was not directed, it is the
single largest unreviewed architectural change in the project.

### ✅ T27 — fixed by P1, and it corrected me

All five crons moved to **11:17–13:17 UTC**, giving ~11h of margin before UTC midnight; even the
worst observed delay lands comfortably. P1 also added a guard that warns when a run crosses UTC
midnight — which is exactly the thing the schedule test structurally cannot catch.

P1's commit `60fd926` corrects my framing: *"the scheduler delay varies by hours, it is not steadily
growing."* It is right. Full series: 2h03m, 3h06m, 5h01m, 4h01m, 4h01m — variance, not a trend. My
"worsening" read was wrong.

### ✅ T28 — fixed by P1

`ba82986 fix(cache): make every parquet write in cache.py atomic`.

### ✅ T1/T1b — holding across three live nights

| Series | 09-28 | 09-29 | 09-30 |
|---|---|---|---|
| `pytrends/AI crypto` | 27 | 72 | 50 |
| `pytrends/memecoin` | 51 | 84 | 85 |
| `pytrends-blended/ai` | 13.5 | 38.5 | 25.0 |
| `pytrends-blended/memecoins` | 8.0 | 28.5 | 29.0 |
| `pytrends/RWA crypto` | 0 | **74** | 0 |
| `pytrends/layer 2 crypto` | 0 | 0 | 0 |
| `pytrends-blended/rwa` | 0 | **0** | 0 |
| `pytrends-blended/l2s` | 0 | 0 | 0 |

### T26 revised, and a new discrepancy inside it

**The "RWA is too low-volume" hypothesis is refuted** — `RWA crypto` returned **74.0** on 09-29. The
persistent zero is `layer 2 crypto` / `l2s`, across both paths, every night.

**New, and more interesting:** on 09-29 `pytrends/RWA crypto` = 74.0 while `pytrends-blended/rwa` =
0.0, *the same night from the same job*. The blended value is a mean of anchor-chained keywords, so
a term at 74 in its own unbatched request can legitimately rescale to ~0 against a larger anchor.
That may be correct arithmetic — but it writes **`0.0` with `source_status: fresh`**, which is the
same *shape* as the bug T1 just fixed: a number that reads as a measurement but actually means
"below the anchor's resolution". Worth confirming RFC-1's sufficiency gating surfaces these as
`insufficient` rather than as a real zero. Owner: whoever next touches the narrative lane.

### Correction I owe three sessions

I told P1, P2 and P3 the pytest baseline was **717 / 5**. Measured on main today: **714 / 5**. I
double-counted T1b's three new tests — the 714 I measured on 09-28 already included them. P2 caught
it independently and recorded `baseline 714/5` in its own commit, which is what verifying rather
than trusting is for.


---

## Revision 5 — 2026-10-01: all three lanes MERGED

`main` is now `94f3981`. PR #11 (pipeline), #10 (deploy), #9 (Direction D) all squash-merged, zero
conflicts. **Post-merge gates run together**, which no individual lane had done:

| Gate | Result |
|---|---|
| `uv run --project api pytest api/ -q` | **866 passed, 1 skipped, 5 deselected, 1 xfailed** (was 714/5) |
| `pnpm --filter web test` | **223 passed, 30 files** (was 181/22) |
| `pnpm --filter web exec tsc --noEmit` | exit 0 |
| `pnpm build:islands` | succeeds |

### Closed by the merges

| Task | How |
|---|---|
| **T5** `/pairs` no automation | `pairs-refresh-snapshot.yml` — OHLCV refresh then compute in one job, so compute always sees that run's bars |
| **T27** cron timing | All five crons → 11:17–13:17 UTC (~11h margin) + a midnight-crossing warning |
| **T28** non-atomic parquet writes | `cache.py` now temp-then-rename throughout |
| **T12** equity provider | LSE verdict: ADOPT-WITH-LIMITS, private use only, no redistribution without a licence |
| **Deployment** (open since setup) | Home PC + Tailscale, ~$0/mo, `deploy/` launchers + runbook |
| **T14 / T24** UI shell, one status board | Direction D shipped a real shell; context docs now carry the stack decision |
| **T8** context refresh | `all-context.md` reconciled 01-10 — stack, runtimes, deployment, changelog |

### Still open

| # | Task | Note |
|---|---|---|
| **T26** | `layer 2 crypto` / `l2s` reads 0.0 every night, both paths. And `pytrends-blended/rwa` wrote **0.0 as `fresh`** on a night when `pytrends/RWA crypto` read 74.0 — same *shape* as the bug T1 fixed. Confirm sufficiency gating catches it. | data quality |
| **T4** | Reddit still archives nothing (`credentials-not-configured` every night). The mindshare view lists it as a permanently empty source. | user action |
| **T7** | narrative-dashboard v1 — two `review-decision.json` still `PENDING` | user PC |
| **T9** | charting-indicators still has zero code — now cheaper, since the island/LayerChart surface it would build on exists | needs SPEC |
| **T10** | No cross-signal confidence view — the stated north star | needs SPEC |
| **T13** | Still no CI, no linter, no formatter. Three lanes merged without a single automated check on the PRs. | ops |
| **T16** | No root README (`deploy/README.md` covers deployment only) | docs |
| **T15, T17, T18, T19, T21, T22, T25** | Housekeeping, unchanged. T17 (`.agents/skills` 17 MB duplicate) still fails the context validator. | |

### Bundle cost of Direction D, measured

`lightweight-charts` shipped **172 kB raw / 54 kB gzipped**. The island entry chunk is **787 kB raw /
185 kB gzipped** (1.1 MB on disk across chunks) — roughly **3.4× more gzipped chart runtime**. Not
apples-to-apples: the island chunk also carries the Svelte runtime, LayerChart and `d3-scale`, while
the old 54 kB was charting alone with the React wrappers as separate app code. Accepted deliberately
as the price of the design system; recorded in `all-context.md` so it is not rediscovered as a
surprise.

### Getting the update onto the running PC

Merging changed nothing on the user's machine. `start-api.ps1` does a stage-A `git pull` on start, but
the web app is **built** (`next start`, never the dev server), so per `deploy/README.md`: *"If a
`git pull` changes anything under `web\`, rebuild before the change appears."* Direction D also adds
dependencies, so an install is needed before the rebuild. Closing and reopening the app does **not**
pick it up.


---

## Revision 6 — 2026-10-01: CI exists, and a user-PC fix was nearly lost

### ✅ T13 — CI is wired

`.github/workflows/ci.yml`: pytest, vitest, `tsc --noEmit`, and the island build, on every
`pull_request` and on pushes to `main`. Read-only (`contents: read`), no secrets, cancels superseded
runs — the **opposite** safety profile to the five snapshot workflows, which need write access and
must never cancel mid-archive. Skips pushes touching only `api/data/cache/**` so the nightly bots
don't trigger it. Pinned by `api/tests/scripts/test_ci_workflow.py` (6 tests), including that a
`pull_request`-triggered workflow never holds write access.

**Deliberately excluded, with the reasons written into the file:**
- **Playwright** — needs a seeded cache plus the `PLAYWRIGHT_CHROMIUM_PATH` pin, and carries a known
  intermittent flake. A gate that fails randomly on day one teaches people to ignore the gate. Add
  it once that flake is root-caused.
- **A linter/formatter** — none is configured in this repo. Choosing a rule set and fixing what it
  finds is its own change with its own opinions, not CI wiring. **Still open.**
- **`integration`-marked tests** — real network, opt-in by design.

### 🔴 The uvicorn fix existed only on the user's PC

`deploy/start-api.ps1` launched the bare `uvicorn` console script. On Windows that fails with
`uv trampoline failed to canonicalize script path` — uv installs console scripts as trampoline
`.exe` shims, and launching one through `uv run` could not resolve its own path. The user found and
fixed it themselves (`uv run --project api python -m uvicorn ...`, which skips the shim) and verified
it end to end: API up, web up, phone over Tailscale with Wi-Fi off, HTTP 200.

**That fix was never committed.** It would have been lost on the next clone, and nothing would have
caught it — this is a failure CI *structurally cannot* reach: no Windows, no PowerShell, no Tailscale
on a runner. Now committed, with a regression test pinning the module form.

**The general lesson, worth more than the fix:** P2's own SPEC said the PowerShell scripts "were
written in a container that has no PowerShell" and that automated tests "only check their text". That
was an honest disclosure, and this is exactly the class of bug it predicted. Treat every `deploy/*.ps1`
behaviour as unverified until it has run on the real machine, and when the user fixes something
there, **get it committed the same day**.

### Ground truth

| Gate | Result |
|---|---|
| pytest | **873 passed**, 1 skipped, 5 deselected, 1 xfailed |
| vitest | 223 passed, 30 files |
| `tsc --noEmit` | exit 0 |
| `build:islands` | succeeds |

### Still open

T26 (`l2s` always zero; `pytrends-blended/rwa` writing `0.0` as `fresh` on a night the unbatched path
read 74) · T4 (Reddit archives nothing) · T7 (two `PENDING` review decisions) · T9 (charting-indicators
has no code) · T10 (no cross-signal confidence view — the stated north star) · **linter/formatter**
(the half of T13 left undone) · T16 (no root README) · T15, T17, T18, T19, T21, T22, T25 housekeeping.

**Also unverified:** P1's new cron times (11:17–13:17 UTC) have not yet had a real firing observed on
`main`, and P1's own closeout flags that `etf_flows_adapter.py::merge_into_cache` still writes
non-atomically, so T28's atomicity prerequisite is not fully met.


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

### T1b — port the `isPartial` guard into `fetch_trends_batched` · ✅ **FIXED, awaiting merge**

**Fixed on `claude/pensive-dijkstra-ko69oi` (commit `a0a7b09`), open in PR #6 — not yet on main.**
`_fetch_batch_live` now drops `isPartial=True` rows and returns `None` when nothing complete
survives, so `fetch_trends_batched` inherits the guard and reports `unavailable` /
`batch-fetch-failed` rather than a fabricated value. 3 regression tests added; full suite 714
passed / 5 deselected. **Must merge before the ~20:20 UTC cron.**

The state it fixes — PR #7 merged at 14:44:57Z (main `e9c33fe`) with the gap open. Its merge commit
`ca8e68b` pulled in PR #8's fix, so the file *contained* an `isPartial` guard at lines 66–67 inside
`_fetch_live` only. Verified on main at the time:

| Function (main `e9c33fe`) | Lines | `isPartial` guard |
|---|---|---|
| `_fetch_live` | 50–80 | ✅ yes (66–67) |
| `_fetch_batch_live` | 190–218 | ❌ **none** — returns the raw frame |
| `fetch_trends_batched` | 219+ | ❌ **none** — takes `df.iloc[-1]` |

The nightly path is live and unguarded:
`snapshot_narrative.py:137` → `fetch_trends_batched(...)` → line 177
`cache.write_narrative_point(BLENDED_SOURCE, ...)` → `momentum.py:169` reads `BASIS_BLENDED` as its
**first-choice** basis; `mindshare.py` reads it too.

**Deadline: the next narrative cron, 18:17 UTC + ~2h GitHub delay ≈ 20:20 UTC**, is the first run
that writes `pytrends-blended/*`. Whatever it writes from Google's incomplete hour is
**unrecoverable** — Google Trends keeps no history. Every subsequent night compounds it, and the two
brand-new views are the consumers.

- **Worktree:** A · **Files:** `api/data/pytrends_adapter.py` (`_fetch_batch_live` — filter there,
  so `fetch_trends_batched` inherits it), `api/tests/data/test_pytrends_adapter.py`
- **Shape of the fix:** the same four lines already proven in `_fetch_live` and in
  `backfill_pytrends_history.py::daily_points` — drop `isPartial=True` rows before selecting, and
  return `None` when nothing complete survives rather than a fabricated value.

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
| T27 | **Move the snapshot crons much earlier.** Observed GitHub delays are 2h03m → 3h06m → **5h01m** and worsening; the 09-28 narrative run landed 41 min before UTC midnight. An 18:17 cron is not safe. Also worth adding: a guard that detects a run which executed on a different UTC day than intended, since the schedule test cannot see real delays. | **P1** | — | 🔴 raise to URGENT if another run lands after 23:30Z |
| T26 | **"RWA crypto" and "layer 2 crypto" may be too low-volume for Google Trends.** Both wrote an honest 0.0 on the first post-fix night while AI crypto and memecoin returned real values. Needs the raw frame to confirm, then either different keywords or an accepted "no signal" state for those two narratives. | C | T3 | data-quality, not correctness |
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
