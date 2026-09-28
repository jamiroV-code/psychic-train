---
name: plan:pipeline-completeness
description: "Make the data pipeline complete and self-sustaining — every served data surface has a scheduled refresh, and a fresh checkout has a documented route to a populated cache"
date: 28-09-26
feature: general
---

# Pipeline Completeness — SPEC

## Summary

Right now three scripts that feed live pages (`/screener`, `/pairs`, `/regime`) have to be run by
hand — nothing refreshes them on a schedule. On top of that, a brand-new checkout of the repo (or a
freshly deployed server) has empty caches for OHLCV prices, FRED macro series, and pair-cointegration
results, so those pages would show nothing or a "stale" banner the moment the app went live. This SPEC
defines what "the pipeline is complete and self-sustaining" means well enough that the app could be
deployed always-on and keep itself current without the user manually running scripts. It intentionally
does NOT decide the caching/repo-storage strategy — that tradeoff is real (repo bloat vs. empty-cache-on-
deploy) and is handed to INNOVATE as an open design question with the forces laid out, not an answer.

## User Stories / Jobs To Be Done

- As the solo trader running this app, I want the screener, pairs, and regime pages to always show
  current data without me remembering to run a script, so that the app is actually usable day to day
  instead of "half-manual."
- As the solo trader, I want a fresh clone or a newly deployed instance of the app to end up with a
  working cache on its own (or with one documented, low-effort step), so that "deploy it and it works"
  is true instead of "deploy it and discover every page is empty."
- As the solo trader (thinking ahead to opening this to other users), I want the refresh jobs to fail
  safely — never commit garbage, never silently go stale forever — so that a scheduling hiccup doesn't
  quietly corrupt or blank out a page other people are looking at.
- As the person who will eventually stop babysitting this app, I want the pair-cointegration table to
  never serve stale results because someone forgot to run the compute step after an OHLCV refresh — the
  two must be tied together, not just individually scheduled.
- As the maintainer, I want to know honestly what could NOT be verified from inside this dev
  environment (live-provider fetches, real GitHub Actions cron firing) so I know what still needs a
  real-world check after merge, instead of a plan that quietly assumes those things work.

## What The User Wants (Behavioral Outcomes)

- Every data surface the app currently serves (screener's OHLCV tails, regime's FRED primaries, pairs'
  cointegration table) refreshes on its own on a recurring schedule, with no manual step required for
  ordinary day-to-day operation.
- The pair-cointegration refresh always runs after the OHLCV refresh it depends on — the two are never
  scheduled independently in a way that lets one run without the other having just completed.
- Every new scheduled job behaves exactly like the three that already exist today: it only ever touches
  its own data, it never leaves a broken half-written cache behind, it doesn't fight with other jobs
  writing to the same branch, and a routine "nothing changed tonight" run causes no noise.
- A fresh checkout (new laptop, new deploy target, CI runner) ends up in one of two clearly documented
  states: (a) already has a working cache because the necessary data is committed to the repo, or (b) is
  empty but there is a documented, repeatable command sequence that populates it in a bounded amount of
  time — never a silent "the page is just blank and nobody knows why."
  - The docs must be plain about which parts of that non-committed-data flow can be automated as a
    scheduled job vs. which parts inherently take real wall-clock time (deep multi-year backfills) and
    are a one-time manual step even on a fresh deploy.
- The chosen cache strategy explicitly states, in writing, its ongoing repo-growth cost and how long a
  fresh checkout takes to reach a working state — so this decision is auditable, not implicit.
- Nothing about what the screener, pairs, or regime pages actually compute or display changes. This is
  entirely about making the existing computations run reliably and automatically.

## Flow / State Diagram

```
TODAY (half-manual):

  [user manually runs]        [nightly, automatic]
   refresh_cache.py     X      chain-growth-snapshot.yml ──► cache/onchain/  (committed)
   backfill_primaries.py X     narrative-snapshot.yml    ──► cache/narrative/ (committed)
   compute_pairs.py      X     liqtide-snapshot.yml      ──► cache/liqtide/  (committed)

   cache/ohlcv/     -- gitignored, empty on fresh checkout
   cache/liquidity/ -- gitignored, empty on fresh checkout
   cache/pairs/     -- gitignored, empty on fresh checkout
   watchlist.json   -- gitignored, only .example exists

  Fresh checkout / fresh deploy:
   /screener  ──► empty (no watchlist, no OHLCV)
   /pairs     ──► results_unavailable
   /regime    ──► (FRED path) degraded / no data


DESIRED (self-sustaining):

  ┌─────────────────────────────────────────────────────────────┐
  │  nightly, unattended, in order, each safe on its own:        │
  │                                                               │
  │   refresh_cache.py  ──► cache/ohlcv/  ──► compute_pairs.py    │
  │        │                                        │             │
  │        ▼                                        ▼             │
  │   feeds /screener                          feeds /pairs        │
  │        (pairs step runs AFTER ohlcv, same night, every night) │
  │                                                               │
  │   backfill_primaries.py ──► cache/liquidity/ ──► feeds /regime │
  └─────────────────────────────────────────────────────────────┘
           existing 3 jobs (onchain/narrative/liqtide) unchanged

  Fresh checkout / fresh deploy:
   EITHER cache arrives already populated (committed data), or
   ELSE a documented bootstrap sequence (commands + expected wall time)
        gets it populated — never a silent empty page.

   /screener  ──► shows current watchlist data
   /pairs     ──► shows fresh (or honestly-labeled stale) results, never silently empty
   /regime    ──► shows current FRED-derived series
```

## Acceptance Criteria (Testable Outcomes)

1. **Every currently-unscheduled refresh script that feeds a live page has a recurring automated
   trigger** (`refresh_cache.py` → `/screener` + `/pairs` inputs, `backfill_primaries.py` → `/regime`
   inputs, `compute_pairs.py` → `/pairs`).
   - proven by: `test_snapshot_workflow_schedules.py` extended to cover the new workflow file(s) —
     asserts a schedule trigger exists, `workflow_dispatch` present, correct permissions/concurrency
     shape.
   - strategy: Fully-Automated.

2. **`compute_pairs.py` always runs after the same night's OHLCV refresh completes, never
   independently** — the ordering guarantee is structural (e.g. same workflow run, or an explicit
   dependency the schedule can't violate), not just "scheduled a few minutes later and hoping."
   - proven by: a new test asserting the ordering/dependency mechanism exists (e.g. same job, or a
     documented trigger chain) — exact mechanism is an INNOVATE decision, but the test must prove
     ordering is enforced, not coincidental.
   - strategy: Fully-Automated (mechanism verifiable from workflow YAML / script structure).

3. **Each new scheduled job reproduces the existing safety shape exactly**: `permissions:
   contents: write` only, one `concurrency` group, a "nothing new to commit" short-circuit, a
   3-attempt `git pull --rebase` + push retry loop, and a `git add` scoped to only the directory that
   job owns.
   - proven by: `test_snapshot_workflow_schedules.py`'s existing shape assertions (permissions,
     concurrency, retry block, `git add` scoping), extended to the new workflow file(s).
   - strategy: Fully-Automated.

4. **No two new/existing scheduled jobs' cron start times collide or run within 20 minutes of each
   other, and every job starts early enough to finish before 21:00 UTC** (matching the existing guard's
   rule, given GitHub's observed ~2h scheduling delay).
   - proven by: `test_snapshot_workflow_schedules.py`'s existing pairwise-stagger and
     before-21:00-UTC assertions, extended to cover the new workflow(s).
   - strategy: Fully-Automated.

5. **`refresh_cache.py` and `backfill_primaries.py` each report success/degraded/failure via a real
   exit code** (matching the `snapshot_chain_growth.py` convention: 0 = clean, 2 = degraded-but-commit,
   1 = fail-the-job), so the new workflows can act on outcome the same way the existing three do.
   - proven by: new unit tests for each script's exit-code function (`test_refresh_cache.py`,
     `test_backfill_primaries.py` — neither exists today) covering the 0/1/2 cases with synthetic
     inputs, no network.
   - strategy: Fully-Automated.

6. **`compute_pairs.py`'s exit code reflects real outcome** (currently always returns 0 regardless of
   whether the compute actually produced usable results) — a compute run that produces
   `computation_status: stale` or fails outright must NOT report success to the workflow layer.
   - proven by: new/extended unit tests on `compute_pairs.py`'s exit-code path, synthetic fixtures, no
     network.
   - strategy: Fully-Automated.

7. **A fresh checkout has a documented, working route to a populated cache for OHLCV, FRED/liquidity,
   and pairs data** — either because the relevant cache directories are committed and land populated on
   checkout, or because a written runbook (exact commands, expected wall-clock time, and which steps are
   one-time-manual vs. scheduled-automatic) gets a fresh deploy to a working state.
   - proven by: a runbook doc reviewed for completeness (does it name every directory, every command,
     every expected duration) — this is a documentation completeness check, not a live run.
   - strategy: Hybrid (doc-completeness check is automatable/reviewable here; actually exercising the
     runbook against a real fresh checkout that reaches parity with the deep 5000-bar history is a
     known-gap — see below).

8. **The chosen cache/repo-storage strategy states, in the plan, its estimated repo-growth cost (e.g.
   MB/year) and its estimated fresh-checkout recovery time** — this is a requirement on the INNOVATE/PLAN
   output, not something this SPEC or its own tests check computationally.
   - proven by: manual review of the INNOVATE decision summary / PLAN document for the presence of both
     numbers with stated reasoning.
   - strategy: Agent-Probe (reviewed by the next phase's author, not machine-checkable).

9. **`api/data/watchlist.json` has a resolved, non-manual story on a fresh checkout** — either
   committed with real content, or auto-derived from `watchlist.example.json` (or equivalent) as part of
   the bootstrap path, so `/screener` is not empty purely because the watchlist file is missing.
   - proven by: a test that a fresh-checkout-equivalent environment (temp dir with only the gitignored
     files absent) can produce a usable watchlist via the documented mechanism.
   - strategy: Fully-Automated (mechanism/script testable without live network), assuming the chosen
     mechanism is a local file operation, not a live fetch.

10. **The full existing test suite stays green** — no regression from the 711 passed / 5 deselected
    baseline (`uv run --project api pytest api/ -q`), plus the new tests from criteria 1, 5, 6, 9 above.
    - proven by: `uv run --project api pytest api/ -q` re-run after implementation, comparing count.
    - strategy: Fully-Automated.

11. **Quiet-night behavior is preserved for the new jobs where meaningful** — i.e. where a refresh
    genuinely produces no new information (no plausible "quiet" case for full-overwrite OHLCV, but
    `backfill_primaries.py`'s FRED series may have days with no revision), the job does not manufacture
    a commit.
    - proven by: unit test asserting no-op behavior when the underlying data is unchanged, for whichever
      of the new jobs can have a genuine no-op case.
    - strategy: Fully-Automated.

12. **Work is committed to `claude/p1-pipeline` and a draft PR is open against the target branch**,
    reflecting this SPEC's scope only (no `web/`, no `api/main.py`/deploy/CORS, no
    `pytrends_adapter.py` changes).
    - proven by: `git log` / `gh pr view` showing the branch and an open draft PR.
    - strategy: Fully-Automated (git/gh commands are runnable in this container).

13. **Real GitHub Actions cron firing on the new workflow(s) is confirmed post-merge**, mirroring the
    precedent already accepted for the three existing snapshot workflows (their actual firing was
    confirmed via `git log` on the cache directories after the fact, not verified pre-merge).
    - proven by: post-merge observation of `git log` on the new workflow's owned cache directory
      showing automated `github-actions[bot]` commits landing on schedule.
    - strategy: Known-Gap (cannot be verified in this container — no live GitHub Actions scheduler
      access here; this is a post-merge, real-world confirmation step, same shape as the existing
      three jobs).

14. **Live data fetches (FRED, ccxt/exchange OHLCV) succeed against the real providers when the new
    jobs actually run** (as opposed to succeeding against synthetic test fixtures).
    - proven by: cannot be proven here — this container's egress proxy blocks FRED and any live
      exchange fetch.
    - strategy: Known-Gap (requires either a user-PC run or observing the first few real scheduled runs
      post-merge, same precedent as the pair-screener's Hyperliquid deep-fetch and the regime
      dashboard's AC-11 real-cache walkthrough).

15. **A from-scratch (ephemeral, no committed OHLCV) nightly `refresh_cache.py` run only reaches
    ~500 daily bars (~1.4 years) per symbol, not the ~2,230-bar / ~2020-08-19-floor deep history the
    pair screener was originally built against** — this SPEC requires that this depth mismatch is
    explicitly acknowledged and its consequence for `/pairs` result quality is documented, not silently
    accepted or silently fixed by changing `DEFAULT_LIMIT` without a deliberate decision (that decision,
    if any, belongs to INNOVATE/PLAN, not this SPEC).
    - proven by: presence of the depth-mismatch discussion in the INNOVATE/PLAN documents, referencing
      this SPEC's Open Design Question section.
    - strategy: Agent-Probe (documentation-presence check, not machine-testable).

## Out Of Scope

- `web/` — any frontend changes. Owned by a parallel session on `claude/ui-shell`.
- `api/main.py`, deploy configuration, CORS policy, host binding, container/runtime setup. Owned by
  P2 on `claude/p2-deploy`.
- `api/data/pytrends_adapter.py` and `api/tests/data/test_pytrends_adapter.py`. A fix for this file is
  pending in PR #6 — do not touch it here even incidentally.
- Changing what `/screener`, `/pairs`, or `/regime` compute or display. This work is purely about making
  the existing computations run automatically and reliably — no new metrics, no new endpoints, no
  changed formulas.
- Adding new data providers or adapters.
- Deciding the final cache/repo-storage strategy for `cache/{ohlcv,liquidity,pairs}/` and
  `watchlist.json` — this SPEC defines the requirement that a decision be made and justified with
  concrete numbers; the decision itself is explicitly INNOVATE's job (see Open Design Question below).
- Rate-limit/backoff tuning for ccxt/Hyperliquid or FRED beyond reproducing the existing safety shape —
  no new numeric rate-limit ceiling is being introduced or invented here; this remains a known gap
  (see Constraints).
- `process/MASTER-PLAN.md` reconciliation — this file does not exist in the repo or its history; this
  SPEC is derived from the user's brief alone (see Open Questions).

## Constraints

- **Safety shape is non-negotiable.** Any new workflow that commits to `main`/the working branch MUST
  reproduce the existing three workflows' safety shape exactly: `permissions: contents: write` only, a
  `concurrency` group (no overlapping runs), a "nothing new to commit" short-circuit, a 3-attempt
  `git pull --rebase && git push` retry loop, and a `git add` scoped narrowly to the directory that job
  owns. This is a hard constraint carried from research, not a suggestion.
- **Schedule slot constraints**: any new cron must be a single cron per workflow file, start at least
  180 minutes before UTC midnight (i.e., before 21:00 UTC) given GitHub's observed ~2h scheduling delay,
  and be at least 20 minutes staggered from every other workflow's start time (existing: 17:47, 18:17
  (18:17 per current narrative-snapshot.yml), 18:47 UTC). Free candidate slots per research: 19:17,
  19:47, 20:17, 20:47.
- **Guard-test data model constraint**: `test_snapshot_workflow_schedules.py` currently assumes exactly
  one workflow file → exactly one cache directory (1:1 `WORKFLOW_CACHE_DIRS` mapping) and asserts each
  `git add` is for exactly one directory. Any design where one workflow stages two cache directories, or
  where the OHLCV-refresh-then-pairs-compute ordering is expressed as two steps in one workflow file,
  requires reshaping this test's data model — this is real design surface for INNOVATE/PLAN, not a
  simple "add a row" change.
- **No numeric rate-limit ceiling is documented anywhere in the repo** for ccxt/Hyperliquid or FRED.
  Any new schedule must not silently assume unlimited throughput; the existing known-gap ("18/18 deep
  fetches succeeded with no throttling observed, but bulk rate-limit/backoff was never tested against
  real conditions") stays a known-gap and must not be treated as resolved by this work.
- **This container cannot verify live behavior.** The egress proxy here blocks Google Trends, Reddit,
  CoinGecko, Hyperliquid, FRED, and DefiLlama. No AC requiring a live fetch or real GitHub Actions cron
  firing can be fully verified inside this session — those are marked Known-Gap above, matching the
  precedent already set by the regime dashboard's AC-11 and the pair screener's Hyperliquid depth
  question.
- Must not regress the `api/` test suite baseline: 711 passed / 5 deselected.
- Must not touch `web/`, `api/main.py`, deploy config, CORS, host binding, or
  `api/data/pytrends_adapter.py` / its test file (see Out Of Scope).

## Open Design Question — Cache / Repo-Storage Strategy (for INNOVATE, not decided here)

The user explicitly asked that this be weighed, not defaulted. This SPEC states it as a **requirement
on the decision** (criterion 8: the chosen strategy must state its repo-growth cost per year and its
fresh-checkout recovery time), and lists the forces INNOVATE must weigh — it does not pick an answer.

Forces to weigh:

- **Fresh-checkout / fresh-deploy usability.** An always-on deployed instance with empty `cache/ohlcv/`,
  `cache/liquidity/`, `cache/pairs/` serves nothing useful on `/screener`, `/pairs`, or `/regime` until
  something populates them — and per the ephemeral-runner finding, a from-scratch GitHub Actions runner
  has the identical empty state as a fresh local checkout.
- **Repo growth cost.** OHLCV is full-overwritten every refresh (not appended), so every committed file
  shows as changed every night regardless of whether the underlying data materially changed. Estimated
  churn: ~90-100 OHLCV files (~1-3MB total, but every file touched nightly), `cache/pairs/spreads/` up
  to ~153 files (~3-6MB, whole directory atomically replaced every compute run), `cache/liquidity/` ~5
  files (<100KB, full-overwrite). Compare to the already-committed precedent: liqtide 408KB/10 files,
  narrative 148KB/21 files, onchain 436KB/16 files — those are far smaller AND (per
  `merge_onchain_series`) frequently produce zero git diff on quiet nights, a property OHLCV cannot have
  because it changes by definition every night.
- **Ephemeral-runner futility.** A from-scratch nightly refresh on a runner with no prior OHLCV state
  would only ever reach `DEFAULT_LIMIT = 500` daily bars (~1.4 years) via `refresh_cache.py` — never the
  ~2,230-bar / ~2020-08-19-floor depth that `backfill_pairs_universe.py`'s one-time deep fetch
  (`DEEP_LOOKBACK_LIMIT = 5000`) produced. If the deploy target's cache is never seeded from committed
  data or a one-time deep-backfill step, the pair screener's real-world quality is materially degraded,
  not just briefly stale.
- **The pairs↔OHLCV staleness coupling.** `pairs_response._staleness_reasons` compares stored pairs
  provenance against the LIVE OHLCV cache's per-coin bar count/last-bar-date. Committing `cache/pairs/`
  without also committing (or otherwise ensuring) `cache/ohlcv/` guarantees a permanent `stale` state
  ("bar count changed 2230 → 0") — the two directories cannot be treated independently in whatever
  strategy is chosen.
- **The documented precedent and its stated boundary.** Standing Rule 8 commits derived composites
  whose "history is not recoverable after the fact" (liqtide, narrative, onchain). `cache.py`'s own
  comment frames FRED/DefiLlama/ccxt as themselves being the durable primary archive, not a derived
  composite that could disappear — the stated reason `cache/liquidity/` stays ignored today. OHLCV is
  re-fetchable from the exchange indefinitely (unlike LiqTide, which has no historical endpoint). This
  precedent is a strong hint toward NOT committing OHLCV/liquidity/pairs — but the user has explicitly
  flagged that "deployed instance with empty caches" is a real cost the precedent doesn't account for,
  since the precedent was set before there was any concept of a deployed, always-on target.
- **The deployed-host-owns-its-disk future.** Once P2's deploy work lands, an always-on host has its own
  persistent disk — a cache populated once (by a one-time deep-backfill run) and then kept warm by
  nightly scheduled jobs may make the "fresh checkout has an empty cache" problem irrelevant for the
  deployed instance specifically, even though it remains real for local dev checkouts. INNOVATE should
  weigh whether the fresh-checkout problem and the fresh-deployment problem need the same answer or can
  have different ones.

INNOVATE must produce a decision that names its per-year repo-growth estimate and its fresh-checkout
recovery time (criterion 8) — whatever the decision, that reasoning must be visible in the plan.

## Open Questions

- **`process/MASTER-PLAN.md` does not exist** — absent from the working tree and from git history. The
  user's brief referenced it as a planning source of truth. This SPEC is derived from the user's request
  and the supplied research findings alone. Owner: user — confirm whether this file should exist
  somewhere else, was renamed, or was never created; reconcile this SPEC against it if it later appears.
- **Exact new cron time(s)** for the new workflow(s) — narrowed to four free candidate slots (19:17,
  19:47, 20:17, 20:47 UTC) by research, but the final pick(s) depend on how many new workflow files
  INNOVATE's chosen ordering mechanism produces (one combined workflow vs. two staggered ones). Owner:
  INNOVATE/PLAN.
- **Whether the OHLCV→pairs ordering is enforced as one workflow (two sequential steps) or two
  workflows with an explicit trigger/dependency** — directly affects whether
  `test_snapshot_workflow_schedules.py`'s 1:1 `WORKFLOW_CACHE_DIRS` data model needs reshaping. Owner:
  INNOVATE/PLAN.
- **Whether `DEFAULT_LIMIT` (500 bars) should ever be changed for the scheduled refresh**, given the
  depth mismatch against the deep-backfilled 5000-bar/2230-bar real history — this SPEC deliberately
  does not resolve it (see AC 15 and the Open Design Question), but INNOVATE must at least decide
  whether to touch it or explicitly leave it as a documented limitation. Owner: INNOVATE/PLAN.

None of the above block writing this SPEC — they are handed to INNOVATE/PLAN as scoped, named
questions, not silent gaps.

## Background / Research Findings

Key facts that shaped the requirements above (full detail supplied by the orchestrator's research
findings; not re-derived here):

- Baseline test count: 711 passed / 5 deselected (`uv run --project api pytest api/ -q`, ~200s).
- Three existing scheduled workflows (chain-growth-snapshot.yml 17:47 UTC, narrative-snapshot.yml
  18:17 UTC, liqtide-snapshot.yml 18:47 UTC) share one proven safety shape: schedule +
  workflow_dispatch triggers, `permissions: contents: write` only, a named `concurrency` group,
  checkout + uv setup + sync, a `set +e` run step producing an exit-code-driven degraded/fail split
  (0/2/1), and a narrowly-scoped commit step with a "nothing to commit" short-circuit and a 3-attempt
  `git pull --rebase`/push retry loop.
- `snapshot_chain_growth.py` is the only script with the mature `exit_code()`/`main(argv, *, sleep)`
  convention; `refresh_cache.py` and `backfill_primaries.py` have neither a real exit code nor any test
  coverage today; `compute_pairs.py` has `main() -> int` but always returns 0 regardless of outcome.
- Confirmed on real inspection: `cache/ohlcv/`, `cache/liquidity/`, `cache/pairs/` are fully gitignored
  and absent even on a populated local clone — a GitHub Actions fresh checkout is in the identical
  state. `cache.read_ohlcv`/`ohlcv_footer_stats` degrade gracefully on empty input rather than crashing;
  `compute_and_persist()` on a fully empty cache still writes a valid 153-row results file where every
  pair is `coin_unavailable` (existing passing test proves this).
- Depth mismatch: nightly refresh (`DEFAULT_LIMIT = 500`) reaches ~1.4 years of daily bars; the deep
  one-time backfill (`DEEP_LOOKBACK_LIMIT = 5000`) reached ~2,230 bars back to a ~2020-08-19 Hyperliquid
  floor. A from-scratch nightly refresh could never reach that depth on its own.
- `pairs_response._staleness_reasons` compares stored provenance against the live OHLCV cache (bar
  count/last-bar-date per coin) plus universe membership, statsmodels version, and `EG_AUTOLAG` —
  committing `cache/pairs/` without `cache/ohlcv/` guarantees permanent `stale`.
- Estimated churn (labelled as estimates by research): ~90-100 OHLCV files (~1-3MB, changed nightly by
  design since `write_ohlcv` full-overwrites); `cache/pairs/spreads/` up to 153 files (~3-6MB, whole dir
  replaced each compute run); `cache/liquidity/` ~5 files (<100KB, full-overwrite). Already-committed
  precedent is far smaller and can go quiet-night-zero-diff (liqtide 408KB/10 files, narrative
  148KB/21 files, onchain 436KB/16 files; `merge_onchain_series` only rewrites on `inserted`/`revised`).
- Standing Rule 8 (data-sources doc, verbatim): cache every derived third-party composite on arrival,
  because "derived feeds disappear; their history is not recoverable after the fact." `cache.py`'s own
  comment frames FRED/DefiLlama/ccxt as themselves durable primary archives, not derived composites —
  the stated reason `cache/liquidity/` (and by extension OHLCV) stays gitignored today. The user has
  explicitly flagged this precedent as a strong hint, not a foregone conclusion, for a deployed context.
- No documented numeric rate-limit ceiling exists anywhere in the repo for ccxt/Hyperliquid or FRED;
  the existing recorded known-gap about bulk rate-limit/backoff behavior across sequential deep fetches
  remains open.
- Schedule slot math: guard test requires one cron per file, start + 180min < 1440min (before 21:00
  UTC), pairwise ≥20-min stagger against all workflows. Occupied: 17:47, 18:17, 18:47. Free: 19:17,
  19:47, 20:17, 20:47.
- Guard test structural constraint: `test_snapshot_workflow_schedules.py`'s `WORKFLOW_CACHE_DIRS` is a
  1:1 filename→directory map, and `test_git_add_stages_only_own_cache_dir` asserts an exact single
  `git add {dir}` per workflow — any 1-workflow-multiple-dirs or ordering-within-one-workflow design
  requires reshaping this test's data model, not just adding a row.
- Ownership boundaries confirmed clean by research: nothing in `api/scripts/`, `.github/workflows/`, or
  `.gitignore` requires touching `web/`, `api/main.py`, `api/data/pytrends_adapter.py`, or its test file.
- `process/MASTER-PLAN.md` is absent from the working tree and from all git history — recorded above as
  an Open Question, not resolved.
