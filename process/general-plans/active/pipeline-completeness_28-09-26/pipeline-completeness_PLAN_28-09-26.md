---
name: plan:pipeline-completeness
description: "P1 - scheduled, safe refresh paths for OHLCV, pairs and FRED liquidity, plus a documented bootstrap route for a fresh checkout"
date: 28-09-26
feature: general
---

# Pipeline Completeness (P1) - Plan

Date: 28-09-26
Complexity: COMPLEX (single plan, single phase - not a phase program)
Status: ⏳ PLANNED
Branch: `claude/p1-pipeline` (rebased onto `main` bbdf625)
SPEC: `process/general-plans/active/pipeline-completeness_28-09-26/pipeline-completeness_SPEC_28-09-26.md`

TL;DR: two new nightly workflows (`pairs-refresh-snapshot.yml` 19:17 UTC, `liquidity-backfill-snapshot.yml` 19:47 UTC), three scripts given real exit codes, a bootstrap script + runbook, and a reshaped guard test. Nothing new is committed to git (D1), so **on GitHub Actions the commit steps are inert today** - the real value now is a nightly integration canary. Live behavior and real cron firing cannot be verified in this container.

## Overview

Three scripts that feed live pages have no schedule: `refresh_cache.py` (`/screener`, `/pairs` inputs), `backfill_primaries.py` (`/regime` inputs), `compute_pairs.py` (`/pairs`). A fresh checkout has empty `cache/ohlcv/`, `cache/liquidity/`, `cache/pairs/` and no `watchlist.json`. This plan adds the schedules, gives the scripts honest exit codes, and documents one bootstrap route. It changes nothing about what any page computes or shows.

Complexity justification (per `process/context/planning/all-planning.md`): about 20 checklist steps, two workflows that push to `main`, a reshaped guard test. That exceeds the SIMPLE band (8-15 steps, low risk), so this carries COMPLEX rigor (risk predictions, edge cases, honest verification limits) while remaining one plan and one EXECUTE pass. It is not a phase program (no dependent phases, one validation gate).

## What This Plan Does NOT Deliver (Honesty Statement - read first)

1. **The commit steps of both new workflows are inert on GitHub Actions today.** The runner is ephemeral and D1 keeps `cache/ohlcv/`, `cache/liquidity/`, `cache/pairs/` gitignored, so nothing persists between runs. The commit step will always report "nothing new to commit".
2. **What the schedule genuinely buys today:**
   - (a) a nightly integration canary - stated precisely: a total provider outage (every item unavailable, exit 2) raises a GitHub warning annotation only and does NOT fail the job; the job fails only on a crash (any exit code other than 0 or 2, e.g. 137 from an OOM or timeout kill) or when every item raised an exception (exit 1). It does not "fail loudly" on every provider change. Real value given this project's history of silent provider breakage (pytrends partial-hour zeros, the narrative keying bug, the cron-timing data gap);
   - (b) a schedule and safety shape that become fully functional, with zero rewrite, the moment P2 provides a persistent disk.
3. **The goal "every data surface has a scheduled, safe refresh path" is met in the sense that the schedule and the code path exist and are exercised - NOT in the sense that state persists across GitHub Actions runs.** The second half belongs to P2 and is outside P1's ownership boundary. This plan does not redefine the goal.
4. **Depth consequence (D4):** a GitHub-hosted `compute_pairs` run will always be shallow (at most 500 daily bars per coin, `DEFAULT_LIMIT`) versus the real ~2,230-bar quality of the deep-backfilled local cache, until a persistent host exists. A CI pairs result is a canary artifact, not a quality result.
5. **Unverifiable in this container** (egress proxy blocks ccxt/Hyperliquid, FRED, DefiLlama, Google Trends, Reddit, CoinGecko): any live fetch, and any real cron firing. See AC-13 and AC-14 (Known-Gap).

## Decisions (locked upstream - do not reopen D1, D2, D4)

| # | Decision | Notes |
|---|---|---|
| D1 | **Commit nothing new.** `cache/ohlcv/`, `cache/liquidity/`, `cache/pairs/`, `watchlist.json` stay gitignored. A documented bootstrap sequence is the fresh-checkout path. | Numbers below (AC-8). |
| D2 | One combined `pairs-refresh-snapshot.yml` running `refresh_cache` then `compute_pairs` as two sequential steps of the SAME job; separate `liquidity-backfill-snapshot.yml`. Crons 19:17 and 19:47 UTC. | Ordering is structural. |
| D3 | `main(argv=None, *, sleep=time.sleep) -> int` with 0/1/2 exit codes on all three scripts; per-item loops build a summary list so `exit_code()` is a pure function. | Table in Checklist §3. |
| D4 | Leave `DEFAULT_LIMIT = 500`. Deep history is a one-time manual bootstrap (`backfill_pairs_universe.py`, unchanged). | Changing it would alter `/screener`, out of scope. |
| D5 | New idempotent `api/scripts/bootstrap_watchlist.py` copies `watchlist.example.json` to `watchlist.json` when absent. No change to `api/data/watchlist.py`. | Orchestrator ruling SQ1. |
| D6 | Runbook at `api/scripts/BOOTSTRAP.md`. | |
| D7 (APPROVED by orchestrator; verified at VALIDATE) | `refresh_cache.py` additionally refreshes the **pairs-universe coins on `1d` only**. | See below. |

**D7 rationale (a gap found while planning, not covered by D1-D6):** `refresh_cache.py` refreshes only `watchlist ∪ {BTC, HYPE}` (all five timeframes). The pairs universe is 18 coins from `api/data/pairs_universe.json`; the example watchlist holds only BTC, HYPE, ETH, SOL. So 14 universe coins (XRP, DOGE, ADA, ...) would never be refreshed by the schedule, and `compute_pairs` would silently compute on frozen bars for them - defeating the SPEC's "pairs never serve stale results" story. Fix: `refresh_cache` reads `pairs_universe.load_universe()` and fetches those coins on `1d` only (the only timeframe `compute_pairs` reads; `1w` is derived from `1d`, so skipped for universe-only coins). Watchlist coins keep all five timeframes (unchanged `/screener` behavior). Cost: at most 14 extra fetches per night. Rejected alternative: document "universe must be a subset of the watchlist" (fragile, manual). If the orchestrator rejects D7, drop Checklist step 4b and the two D7 tests, and add the constraint to BOOTSTRAP.md.

**D7 evidence (VALIDATE, verified against source; D7 is safe for `/screener`):** `/screener` iterates the watchlist only (`api/analytics/screener_board.py:176` and `:224`); the regime path reads only BTC `1d` (`api/analytics/regime/leg_boundary.py:164`); the only code that lists the OHLCV directory is the manual diagnostic `api/scripts/check_weekly_anchor.py:51`, not a served path. So extra `cache/ohlcv/{SYM}/1d.parquet` files for universe-only coins cannot change any `/screener` value. `fetch_ohlcv` merges into the cached tail (`ccxt_adapter.py:388-392`), so a deep-backfilled `1d` file keeps its history.

**D7 documented side effect (not a defect):** `/pairs` provenance compares per-coin bar counts, so after any manual `refresh_cache` run `/pairs` reads `stale` until `compute_pairs` runs. BTC and HYPE already caused this; D7 widens it to all 18 universe coins. BOOTSTRAP.md must say so (Runbook Contents item 10).

**Also flagged (not a decision, a fact to record in BOOTSTRAP.md):** the pairs universe file is hand-edited; adding a coin needs the deep backfill for that coin, otherwise its history is shallow.

### D1 numbers (AC-8 - all figures are ESTIMATES, not measurements)

Committing everything would add an estimated **~1.5-3.3 GB/year** to the repo:

| Surface | Estimated growth | Why |
|---|---|---|
| `cache/ohlcv/` (~90-100 files) | ~365 MB - 1.1 GB/yr | every file fully overwritten nightly, so every file diffs every night |
| `cache/pairs/spreads/` (up to 153 files) | ~1.1 - 2.2 GB/yr | whole directory wholly replaced on each compute |
| `cache/liquidity/` (~5 files) | ~36 MB/yr | full-overwrite |

That is one to two orders of magnitude beyond the existing committed precedent (liqtide 408 KB, narrative 148 KB, onchain 436 KB in total). Those three also produce **zero diff on quiet nights**, because `merge_onchain_series` only writes `if result.inserted or result.revised`; OHLCV structurally cannot have that property (it changes by definition every night). `cache.py`'s own comment already draws the line: FRED and ccxt are themselves the durable primary archive, not a derived composite that could disappear, and Standing Rule 8 only mandates archiving *disappearing* derived composites.

**Fresh-checkout recovery time (AC-8, estimates; EXECUTE records nothing here - these are runbook numbers):**
- `bootstrap_watchlist.py`: under 1 second.
- `refresh_cache.py` (about 22 symbols x 4 fetched timeframes plus derived weekly; ccxt-rate-limited): estimated several minutes; not measured here (network blocked).
- `backfill_primaries.py` (5 FRED CSV downloads): estimated under 1 minute.
- `backfill_pairs_universe.py` (18 sequential deep fetches, `DEEP_LOOKBACK_LIMIT=5000`): estimated a few minutes; 18/18 succeeded with no throttling in the prior real run, bulk backoff never observed.
- `compute_pairs.py`: about 56 s for 153 pairs (recorded in `all-context.md`).
- **Total: roughly 10-15 minutes of wall-clock, dominated by the network steps; the deep backfill is a one-time manual step even on a fresh deploy.** Runbook must say "estimated" beside each figure.

## Scope

In scope: two new workflows; three script refactors (exit codes, summaries, `main`); one new bootstrap script; the runbook; the guard-test reshape and new tests; new unit test files for the three scripts.
Out of scope (hard): see Resume and Execution Handoff.

## Acceptance Criteria (SPEC traced; each names its proof and strategy)

| AC | Criterion (short) | proven by | strategy |
|---|---|---|---|
| 1 | Each unscheduled script has a recurring trigger | Guard test parametrized over the two new workflow files: `schedule` + `workflow_dispatch` present (asserted explicitly in `test_triggers_permissions_and_concurrency`, which also binds the 3 existing workflows), permissions/concurrency shape | Fully-Automated |
| 2 | `compute_pairs` runs after the same run's OHLCV refresh, structurally | `test_pairs_workflow_orders_refresh_before_compute`: one job, refresh step index < compute step index, compute step has no `if:` depending on the refresh outcome, refresh step never `exit`s on a non-crash code | Fully-Automated |
| 3 | Safety shape reproduced exactly | Generalized existing guard assertions run over the 5 workflows (perms `contents: write` only, concurrency `cancel-in-progress: false`, retry loop, "nothing new to commit", scoped `git add`), plus `test_no_force_add` | Fully-Automated |
| 4 | Crons staggered ≥20 min, before 21:00 UTC | Existing `test_crons_are_staggered` + `test_cron_starts_at_least_3h_before_utc_midnight` automatically cover the new files once added to `WORKFLOW_CACHE_DIRS` (19:17, 19:47) | Fully-Automated |
| 5 | `refresh_cache`/`backfill_primaries` exit 0/1/2 | `test_refresh_cache.py`, `test_backfill_primaries.py`: pure `exit_code()` cases (incl. all-items-raise -> 1, one-raises-others-ok -> 0) plus `main()` with stubbed fetchers, plus `main()` with no args works under pytest (argv not taken from `sys.argv`) | Fully-Automated |
| 6 | `compute_pairs` exit reflects outcome | New cases in `api/tests/scripts/test_compute_pairs.py` (pure `exit_code()` incl. an `insufficient_overlap`-only case + `main()` with stubbed `compute_and_persist`) | Fully-Automated |
| 7 | Fresh-checkout route documented | Doc-completeness checklist over `api/scripts/BOOTSTRAP.md` (every dir, command, duration named) + a grep gate; actually running it to deep-history parity is Known-Gap | Hybrid (doc check) + Known-Gap (live run) |
| 8 | Repo-growth cost and recovery time stated with reasoning | This plan's "D1 numbers" section and BOOTSTRAP.md; reviewer (VALIDATE) checks both numbers present | Agent-Probe |
| 9 | watchlist has a non-manual fresh-checkout story | `test_bootstrap_watchlist.py`: absent target gets created from example; existing target never overwritten; missing example returns 1 | Fully-Automated |
| 10 | Existing suite stays green | `uv run --project api pytest api/ -q`; baseline "to be confirmed by EXECUTE - expected 717 passed / 5 deselected" (SPEC quoted 711; do not trust either, record real before/after) | Fully-Automated |
| 11 | Quiet-night no-op where meaningful | (a) `nothing new to commit` path asserted in workflow text and exercised by the tolerant-`git add` subprocess test (nothing staged); (b) `backfill_primaries`: writing the same series twice through `cache.write_liquidity_series` yields byte-identical files. OHLCV has no quiet case (by design) - stated, not tested | Fully-Automated |
| 12 | Committed on `claude/p1-pipeline`, draft PR open | `git log --oneline -5` and `gh pr view --json isDraft,baseRefName,headRefName` (or GitHub MCP `list_pull_requests`) at the end of EXECUTE (needs push access and an authenticated `gh` or GitHub MCP; if blocked by the environment, record an EXECUTE concern and do not claim AC-12) | Hybrid |
| 13 | Real cron firing confirmed post-merge | Post-merge `gh run list --workflow pairs-refresh-snapshot.yml` shows scheduled runs. NOTE: because commits are inert (D1), `git log` on the cache dirs will show NOTHING; the observable is the Actions run history, not commits | Known-Gap (stub: BACKLOG NOTE, see Test Infra) |
| 14 | Live FRED/ccxt fetches succeed when the jobs really run | First scheduled/`workflow_dispatch` runs post-merge (canary), or a user-PC run of the runbook | Known-Gap (stub: BACKLOG NOTE) |
| 15 | Depth mismatch acknowledged with consequence | Honesty Statement item 4 above and BOOTSTRAP.md "Depth" section; reviewer checks presence | Agent-Probe |

Known-Gap is a named residual, never a terminal PASS: ACs 13 and 14 keep the gate CONDITIONAL and each gets a test-building backlog stub written at UPDATE PROCESS (`process/general-plans/backlog/pipeline-cron-firing-confirmation_NOTE_28-09-26.md`, `.../pipeline-live-fetch-canary_NOTE_28-09-26.md`).

## Touchpoints

**Created (10):**
| File | Content |
|---|---|
| `.github/workflows/pairs-refresh-snapshot.yml` | cron `17 19 * * *`; steps: checkout, setup-uv, `uv sync --project api`, refresh step, compute step, warn steps, commit step, fail-on-crash step |
| `.github/workflows/liquidity-backfill-snapshot.yml` | cron `47 19 * * *`; same skeleton with `backfill_primaries` |
| `api/scripts/bootstrap_watchlist.py` | idempotent copy example to real watchlist; `main(argv=None) -> int` |
| `api/scripts/BOOTSTRAP.md` | runbook (D6) |
| `api/tests/scripts/test_refresh_cache.py` | see Test Matrix |
| `api/tests/scripts/test_backfill_primaries.py` | see Test Matrix |
| `api/tests/scripts/test_bootstrap_watchlist.py` | see Test Matrix |
| `process/general-plans/backlog/pipeline-cron-firing-confirmation_NOTE_28-09-26.md` | AC-13 stub - written at UPDATE PROCESS, not EXECUTE |
| `process/general-plans/backlog/pipeline-live-fetch-canary_NOTE_28-09-26.md` | AC-14 stub - written at UPDATE PROCESS, not EXECUTE |
| (task folder reports) | EXECUTE report inside this task folder |

**Modified (5):**
| File | Change |
|---|---|
| `api/scripts/refresh_cache.py` | summaries + `exit_code()` + `main(argv=None, *, sleep=time.sleep)`; D7 universe coins on `1d`; `__main__` wrapper mapping unhandled exceptions to exit 1; keep `refresh_all()` as a thin wrapper returning the summary list (no other caller exists - verified by grep) |
| `api/scripts/backfill_primaries.py` | same pattern; keep `backfill_all()` thin wrapper |
| `api/scripts/compute_pairs.py` | `exit_code(summary)` + `main(argv=None, *, sleep=time.sleep)` returns 0/2; `__main__` wrapper for exit 1 |
| `api/tests/scripts/test_snapshot_workflow_schedules.py` | reshape + new tests (see Guard-Test Reshape) |
| `api/tests/scripts/test_compute_pairs.py` | append exit-code tests and a module-level autouse isolation fixture (T22); existing tests untouched |

**Read-only references:** `api/data/pairs_universe.py` (`load_universe`), `api/data/watchlist.py`, `api/data/cache.py`, `api/data/ccxt_adapter.py`, `api/data/fred_adapter.py`, `api/analytics/cointegration/pairs_response.py` (`ComputeSummary`), `api/tests/conftest.py`, `api/tests/pairs_fixtures.py`.

**NOT touched:** `.gitignore` (D1 - unchanged), all three existing workflow files.

## Public Contracts

- **Script CLI/exit-code contract (new, load-bearing for workflows):** 0 = at least one item succeeded; 2 = ran but nothing succeeded, with at least one item reporting a normal status such as unavailable (workflow warns); 1 = unexpected exception, or every item raised (`status="error"`) (workflow fails, commit skipped). Any OTHER code the workflow observes (137, 124, ...) is a crash too.

| Script | 0 | 2 | 1 |
|---|---|---|---|
| `refresh_cache` | ≥1 (symbol, timeframe) fetch with `status=="ok"` and not `insufficient_history` | none qualified, but at least one item produced a normal status | unhandled exception, OR every item recorded `status=="error"` |
| `backfill_primaries` | ≥1 series `status=="ok"` (`stale`/`unavailable` do not count) | none ok, but at least one series produced a normal status | unhandled exception, OR every series recorded `status=="error"` |
| `compute_pairs` | `summary.status_counts.get("ok", 0) >= 1` | `status_counts["ok"] == 0` (covers `pair_count == 0`, all `coin_unavailable`, all `insufficient_overlap`) | unhandled exception |

- `refresh_all()` and `backfill_all()` keep their names (no importers today) so a manual `python api/scripts/x.py` still works; the scripts still run as files and as `python -m api.scripts.x`.
- **Workflow behavior contract:** each workflow only ever stages its own owned directories; any exit code other than 0 or 2 (1, 137, 124, or an empty recorded code) skips the commit and fails the job; exit 2 warns and continues; the commit step never fails the job because a path is missing or ignored.
- No API, schema, or web contract changes. `/screener`, `/pairs`, `/regime` outputs unchanged.
- No secrets. ccxt public OHLCV and FRED CSV are keyless (Standing Rule 1).

## Data Flow

1. `pairs-refresh-snapshot.yml` job: checkout, `uv sync --project api`.
2. Step `refresh`: `python -m api.scripts.refresh_cache` reads watchlist (empty on a fresh runner, so BTC/HYPE only) ∪ benchmarks, plus universe coins on `1d`; writes `cache/ohlcv/{SYM}/{tf}.parquet`. Records `exit_code` in `$GITHUB_OUTPUT`; never exits the step itself.
3. Step `compute`: `python -m api.scripts.compute_pairs` reads `cache/ohlcv/` via `read_ohlcv` (no network), writes `cache/pairs/{results.parquet,provenance.json,spreads/}`. Runs unconditionally; on a fresh runner most pairs will be `coin_unavailable` (only BTC/HYPE plus `1d` universe coins fetched), which `compute_and_persist` handles gracefully (existing test proves a valid 153-row file).
4. Warn steps for exit 2; commit step (skipped unless BOTH recorded codes are 0 or 2); final step fails the job if either recorded code is neither 0 nor 2.
5. `liquidity-backfill-snapshot.yml` is the same skeleton over `backfill_primaries` and `cache/liquidity/`.

## Commit-Step Design (the failure mode the template does not cover)

The three existing workflows `git add` directories that are git-tracked and present. Ours stage **gitignored directories that, on a fresh runner, do not exist**. Verified empirically in a scratch repo mirroring the `.gitignore` shape:

| Situation | Result of bare `git add <dir>/` | Result of `git add -A -- <dir>/` |
|---|---|---|
| directory does not exist | exit 128, `fatal: pathspec ... did not match any files` | exit 128 |
| directory exists **and is gitignored** (our steady state under D1) | **exit 1**, "paths are ignored by one of your .gitignore files" | exit 1 |

So the risk is wider than "missing directory": even a populated, ignored directory fails the add. Either would fail the job every night.

**Specified handling:** each owned directory is staged with exactly
`git add -A -- <dir> 2>/dev/null || true`
(one line per owned directory, no `-f`/`--force`, ever - forcing would bypass D1). The following `git diff --staged --quiet` then sees nothing staged and takes the existing `nothing new to commit` exit 0 path. The retry loop and message shape are otherwise identical to the template. Trade-off stated: `|| true` also hides a genuinely broken add; this is acceptable because under D1 an empty stage is the expected outcome, and the run-step exit codes (not the add) carry failure signal. When P2 later un-ignores these paths, the same lines start staging real changes with no edit.

**Test asserting it** (still satisfying the guard's "git add" assertion shape, see reshape): `test_tolerant_git_add_exits_zero_when_path_missing_or_ignored` extracts each `git add` line from the two new workflows, runs it with `bash -c` inside a temporary git repo whose `.gitignore` mirrors the real one, in two scenarios (directory absent; directory present and ignored), and asserts exit code 0 and nothing staged. Skipped with a clear reason only if `git` or `bash` is unavailable.

### Crash detection (C1 - any code other than 0 or 2 is a crash)

Testing only `== '1'` would leave a job green, and still committing, after an OOM or timeout kill (137, 124, 139). The two-code contract is therefore an allow-list:

- Commit step `if:` (pairs workflow): `(steps.refresh.outputs.exit_code == '0' || steps.refresh.outputs.exit_code == '2') && (steps.compute.outputs.exit_code == '0' || steps.compute.outputs.exit_code == '2')`. Liquidity workflow: the same with `steps.backfill` only.
- Final fail step `if:` (pairs): `(steps.refresh.outputs.exit_code != '0' && steps.refresh.outputs.exit_code != '2') || (steps.compute.outputs.exit_code != '0' && steps.compute.outputs.exit_code != '2')`. Liquidity: the same for `steps.backfill`. An empty recorded code also counts as a crash by this form.
- `test_crash_skips_commit_and_fails_job` asserts exactly these forms for both new workflows (commit `if:` requires both codes to be `0` or `2`; final step `if:` fires on anything else; final step contains `exit 1` and comes after the commit step).
- Residual, accepted as Known-Gap and noted in BOOTSTRAP.md limits: if `uv run` itself fails and exits 2 it still reads as "degraded".

## Guard-Test Reshape (`api/tests/scripts/test_snapshot_workflow_schedules.py`)

1. `WORKFLOW_CACHE_DIRS: dict[str, list[str]]`:
   - `chain-growth-snapshot.yml`: `["api/data/cache/onchain/"]`; `narrative-snapshot.yml`: `["api/data/cache/narrative/"]`; `liqtide-snapshot.yml`: `["api/data/cache/liqtide/"]`
   - `pairs-refresh-snapshot.yml`: `["api/data/cache/ohlcv/", "api/data/cache/pairs/"]`
   - `liquidity-backfill-snapshot.yml`: `["api/data/cache/liquidity/"]`
2. `TOLERANT_STAGING = {"pairs-refresh-snapshot.yml", "liquidity-backfill-snapshot.yml"}` - workflows whose owned dirs are gitignored.
3. Add helper `_staged_dirs(name)`: for each `git add` line, if the workflow is tolerant require the exact form `git add -A -- <dir> 2>/dev/null || true` and return `<dir>`; otherwise require the exact legacy form `git add <dir>` (unchanged strictness for the 3 existing workflows - they are not edited).
4. Replace `test_git_add_stages_only_own_cache_dir` with `test_git_add_stages_only_own_cache_dirs`: `set(_staged_dirs(name)) == set(dirs)` and no duplicates. Parametrize over `sorted(WORKFLOW_CACHE_DIRS.items())`.
5. All other existing tests keep their bodies (they only iterate `sorted(WORKFLOW_CACHE_DIRS)`), so the original 13 assertions still hold for the 3 existing workflows and now also run for the 2 new ones.
6. New tests: `test_no_force_add` (no `git add -f`/`--force` in any workflow file, all 5); `test_tolerant_git_add_exits_zero_when_path_missing_or_ignored` (2 workflows x 2 scenarios; the temp repo gets a MINIMAL ignore rule `api/data/cache/*` written into its own `.gitignore` instead of copying the live one, so a future P2 un-ignore cannot make the test misleading; each extracted line runs under `bash -e`, matching how Actions runs `run:` blocks); `test_pairs_workflow_orders_refresh_before_compute` (AC-2); `test_pairs_workflow_compute_runs_regardless_of_refresh_exit_code` (the compute step has no `if:` referencing `steps.refresh`, and the refresh and compute run-blocks contain no `exit` at all - they use `set +e`, record the code and never exit; the only `exit` in the file is the final fail step's `exit 1`); `test_crash_skips_commit_and_fails_job` (asserts the allow-list forms from Crash detection above, both new workflows); `test_new_workflows_run_the_expected_module` (modules invoked via `python -m api.scripts.<name>`).
7. (C6) In the existing `test_triggers_permissions_and_concurrency`, add `assert "workflow_dispatch" in triggers` so AC-1's `workflow_dispatch` requirement is actually asserted; all three existing workflows already declare it (chain-growth:18, narrative:19, liqtide:16), so it binds retroactively and needs no edit to those files.
8. (C6) Update the guard module docstring, which still says "three nightly snapshot workflows", to say five.

## Implementation Checklist

Order matters; commit at the end of EXECUTE per repo policy (commit directly on the current branch; do not touch `main`).

1. Record baseline: `uv run --project api pytest api/ -q 2>&1 | tail -5`; write the real passed/deselected counts into the EXECUTE report ("expected 717 / 5 deselected", but trust only the measured value). Also record the pre-state for the T22 gate: `ls api/data/cache/ohlcv api/data/cache/liquidity api/data/cache/pairs api/data/watchlist.json 2>&1 | head` (step 15's before/after content snapshot replaces any marker-file approach; no marker is required).
2. Write failing tests first (red), in `api/tests/scripts/`: `test_refresh_cache.py`, `test_backfill_primaries.py`, exit-code cases appended to `test_compute_pairs.py`, `test_bootstrap_watchlist.py`. **Structural isolation (T22, C4):** each of the four test files (`test_refresh_cache.py`, `test_backfill_primaries.py`, `test_bootstrap_watchlist.py`, `test_compute_pairs.py`) gets a module-level `autouse=True` fixture that depends on `isolated_cache` AND monkeypatches `watchlist_store.DEFAULT_WATCHLIST_PATH` to `tmp_path / "watchlist.json"`, so isolation holds for every test whether or not it names the fixture, including tests that would otherwise reach it only transitively. Module-local: do NOT edit `api/tests/conftest.py`. Also write: `main()` with no arguments works under pytest for each of the three scripts (C5); all-items-raise -> 1 and one-raises-others-ok -> 0 for `refresh_cache` and `backfill_primaries` (C3); an `insufficient_overlap`-only case for `compute_pairs.exit_code` (C2). See Safety Requirement.
3. `api/scripts/refresh_cache.py`: add a `FetchSummary` dataclass (`symbol`, `timeframe`, `ok`, `status`, `bars`, `insufficient_history`); `run_refresh(*, sleep, spacing) -> list[FetchSummary]` looping symbols x timeframes, each item wrapped so a per-item exception records `ok=False, status="error"` and continues (C3); `exit_code(summaries) -> int` (1 if the list is non-empty and EVERY item has `status=="error"`; else 0 if any `ok`; else 2); `main(argv=None, *, sleep=time.sleep) -> int` using `argparse` with no options (so `--help` works) and `parser.parse_args([] if argv is None else argv)` so a bare `main()` never consumes pytest's own `sys.argv` (C5), printing the same per-item lines as today, returning `exit_code`. Spacing constant `REQUEST_SPACING_SECONDS = 0.0` (no behavior change; SPEC puts rate tuning out of scope; `if spacing: sleep(spacing)`). `__main__`: `try: sys.exit(main(sys.argv[1:])) except Exception as exc: print(..., file=sys.stderr); sys.exit(1)` (same shape as `snapshot_chain_growth.py`). Keep `refresh_all()` as a thin wrapper.
4. **4b (D7):** in `run_refresh`, symbols = `sorted(watchlist ∪ BENCHMARK_SYMBOLS)` fetched on all `TIMEFRAMES` (unchanged), plus `sorted(load_universe()) - that set` fetched on `("1d",)` only. Import `load_universe` from `api.data.pairs_universe` at module level as `load_universe` so tests can monkeypatch `refresh_cache.load_universe`. If `load_universe` raises `UniverseFileError`, record it as one failed summary (`ok=False, status="error"`) and continue with the base set (never crash on a bad universe file).
5. `api/scripts/backfill_primaries.py`: same pattern - `SeriesSummary` (`label`, `series_id`, `ok`, `status`, `rows`, `first`, `last`), per-series isolation (a per-series exception records `status="error"`, C3), `exit_code` (1 if every series errored; else 0 if any `status=="ok"`; else 2), `main(argv=None, *, sleep=time.sleep)` using `parse_args([] if argv is None else argv)` (C5), `__main__` wrapper calling `main(sys.argv[1:])`, keep `backfill_all()` wrapper, output lines unchanged.
6. `api/scripts/compute_pairs.py`: add `exit_code(summary) -> int` implementing the table in Public Contracts (`summary.status_counts.get("ok", 0) == 0` gives 2, else 0 - C2; this covers `pair_count == 0`, all `coin_unavailable` and all `insufficient_overlap`); `main(argv=None, *, sleep=time.sleep) -> int` (argparse, no options, `parse_args([] if argv is None else argv)` so the existing untouched `test_script_main_prints_summary`, which calls `main()`, keeps passing - C5) prints the same lines then returns `exit_code(s)`; `__main__` wrapper calls `main(sys.argv[1:])` and maps exceptions to exit 1. `compute_and_persist` itself is NOT modified.
7. `api/scripts/bootstrap_watchlist.py`: `main(argv=None) -> int`; `--example` (default `api/data/watchlist.example.json`, resolved from `__file__`) and `--target` (default `watchlist_store.DEFAULT_WATCHLIST_PATH`, read at call time). Behavior: target exists then print "already present" and return 0 (never overwrite, never merge); target absent and example present then `mkdir -p` parent, copy, print, return 0; example missing then print error to stderr, return 1. Keep the same `_REPO_ROOT` `sys.path` prologue as sibling scripts.
8. Create `.github/workflows/pairs-refresh-snapshot.yml` from the chain-growth template with these exact differences: name `Pairs refresh snapshot`; cron `"17 19 * * *"`; `workflow_dispatch: {}`; `permissions: contents: write`; `concurrency: {group: pairs-refresh-snapshot, cancel-in-progress: false}`; header comment stating the honesty items (inert commits under D1, canary purpose, shallow-depth consequence, and that this supersedes MASTER-PLAN T5's `pairs-recompute.yml` name). Steps: checkout, `astral-sh/setup-uv@v3`, `uv sync --project api`; step `refresh` (id `refresh`, `set +e`, `uv run --project api python -m api.scripts.refresh_cache`, echo `exit_code=$code` to `$GITHUB_OUTPUT`, **no exit**); step `compute` (id `compute`, same pattern with `api.scripts.compute_pairs`, no `if:`); two `::warning::` steps `if: steps.<id>.outputs.exit_code == '2'`; commit step `if:` = the allow-list form from Crash detection (both recorded codes `'0'` or `'2'`) with the two tolerant `git add` lines (`api/data/cache/ohlcv/`, `api/data/cache/pairs/`) then the template's diff-quiet short-circuit, `chore: pairs refresh snapshot $(date -u +%Y-%m-%d)` commit, and the 3-attempt `git pull --rebase origin "${GITHUB_REF_NAME}" && git push` loop; final step `if:` = the Crash-detection form (either recorded code neither `'0'` nor `'2'`) running `echo "::error::..."; exit 1`.
9. Create `.github/workflows/liquidity-backfill-snapshot.yml`: cron `"47 19 * * *"`, concurrency group `liquidity-backfill-snapshot`, step `backfill` (`api.scripts.backfill_primaries`), warn on 2, commit step with one tolerant `git add -A -- api/data/cache/liquidity/ 2>/dev/null || true`, same allow-list commit gating and fail-on-crash pattern (any code other than 0 or 2, per Crash detection), commit message `chore: liquidity backfill snapshot ...`.
10. Reshape `test_snapshot_workflow_schedules.py` exactly as in Guard-Test Reshape (items 1-8, including the `workflow_dispatch` assertion and the docstring fix); add the new tests.
11. Write `api/scripts/BOOTSTRAP.md` (see Runbook Contents).
12. Green: `uv run --project api pytest api/tests/scripts -q` (fast subset first), then fix until green.
13. Structural workflow check (no network): `python -c "import yaml,sys; [yaml.safe_load(open(f)) for f in sys.argv[1:]]" .github/workflows/pairs-refresh-snapshot.yml .github/workflows/liquidity-backfill-snapshot.yml` exits 0. (If `actionlint` is installed, also run it; absence is not a failure.)
14. Dry local exercise of the scripts against an isolated cache (no network needed to prove no crash): covered by the unit tests; do NOT run any script against the real cache from EXECUTE.
15. **T22 verification (mandatory, do not skip; strengthened, C4).** `grep -L`/`grep -c` are file-level and blind to fixtures acquired transitively, and `find -newer` misses deletions and `api/data/watchlist.json`, so use these instead. Do NOT edit `api/tests/conftest.py`.
    - (a) Structural: each of the four test files has its module-level `autouse=True` isolating fixture (`grep -c "autouse=True" <file>` >= 1 each).
    - (b) Transitive-safe proof: `uv run --project api pytest api/tests/scripts/test_refresh_cache.py api/tests/scripts/test_backfill_primaries.py api/tests/scripts/test_bootstrap_watchlist.py api/tests/scripts/test_compute_pairs.py --setup-show -q 2>&1 | grep -c "SETUP    F isolated_cache"` must EQUAL `uv run --project api pytest <same four files> --collect-only -q 2>&1 | grep -c "::"` (today's `test_compute_pairs.py` alone shows 8 SETUPs vs 9 collected because `test_golden_bh_set` is pure; with the autouse fixture they must be equal).
    - (c) Before/after content snapshot around the new/extended tests only: `snap(){ find api/data/cache api/data/watchlist.json -type f -printf '%p\t%s\t%T@\n' 2>/dev/null | sort | sha256sum; }; a=$(snap); uv run --project api pytest api/tests/scripts/test_refresh_cache.py api/tests/scripts/test_backfill_primaries.py api/tests/scripts/test_bootstrap_watchlist.py api/tests/scripts/test_compute_pairs.py api/tests/scripts/test_snapshot_workflow_schedules.py -q; b=$(snap); [ "$a" = "$b" ] && echo REAL-CACHE-UNCHANGED || echo REAL-CACHE-TOUCHED` must print `REAL-CACHE-UNCHANGED`. It catches modifications, deletions (the RFC-005 incident was a deletion) and `api/data/watchlist.json`, where a rogue `bootstrap_watchlist.main([])` against the default target would create the developer's real file.
    - (d) Keep the canary `test_isolated_cache_redirects_cache_root` in each script test file.
    - EXECUTE pastes the (b) two counts and the (c) verdict into its report.
16. Full suite: `uv run --project api pytest api/ -q`; compare to step 1 baseline; expected delta = only added tests, zero failures, deselected unchanged.
17. Run validators for changed surfaces: `node .claude/skills/vc-generate-plan/scripts/validate-plan-artifact.mjs process/general-plans/active/pipeline-completeness_28-09-26/pipeline-completeness_PLAN_28-09-26.md`; `git diff --check`.
18. Scope check: `git diff --name-only bbdf625..HEAD` lists only files in the Touchpoints table (plus the plan/report artifacts); `git diff bbdf625..HEAD -- .gitignore web api/main.py api/data/watchlist.py api/data/pytrends_adapter.py api/tests/data/test_pytrends_adapter.py process/context` prints nothing.
19. Write the EXECUTE report inside this task folder (before/after pytest counts, every gate result, every AC status, the Known-Gaps).
20. Commit on `claude/p1-pipeline` (conventional prefix, e.g. `feat: schedule pairs/liquidity refresh workflows and script exit codes`); push; ensure a **draft** PR against `main` exists (`gh pr create --draft --base main`); PR body follows the attribution reminder and states the honesty items verbatim (inert commits, canary, depth). No `web/` etc. staged.

## Test Matrix (vc-test-coverage-plan output)

Context chain loaded: `process/context/all-context.md`, `process/context/tests/all-tests.md` (runners, `isolated_cache` guidance, integration marker), existing blast-radius tests `test_snapshot_workflow_schedules.py`, `test_compute_pairs.py`, `test_snapshot_chain_growth.py` (exit-code and injected-`sleep` idiom), `api/tests/conftest.py`, `api/tests/pairs_fixtures.py`.

**Area: `api/scripts/refresh_cache.py`**
| Tier | Scenario | Command | Proves | Does NOT prove |
|---|---|---|---|---|
| Fully-automated | `exit_code` 0 when ≥1 ok; 2 when none ok (all unavailable / insufficient); mixed | `uv run --project api pytest api/tests/scripts/test_refresh_cache.py -q` | pure exit-code policy | live ccxt behavior |
| Fully-automated | `main()` with stubbed `ccxt_adapter.fetch_ohlcv`: prints one line per item, returns policy code; universe-only coins fetched on `1d` only, watchlist coins on all five | same file | D7 + summary wiring | real exchange shape |
| Fully-automated | bad universe file recorded as failed item, base symbols still fetched | same file | no crash on config error | |
| Fully-automated | all items raise -> `exit_code` 1; one raises, others ok -> 0; `main()` with no args works under pytest | same file | C3 total-failure path; C5 argv handling | |
| Fully-automated | canary `test_isolated_cache_redirects_cache_root` in each of the four script test files (asserts `cache.CACHE_ROOT == tmp_path` and the default watchlist path is redirected, inside a test) | same file | T22 fixture is really in effect | |
| Known-gap | real ccxt/Hyperliquid fetch | - | - | AC-14 |

**Area: `api/scripts/backfill_primaries.py`**
| Fully-automated | `exit_code` 0 / 2 (`stale` and `unavailable` do not count as ok); per-series exception isolation (`status="error"`); all series raise -> 1; one raises, others ok -> 0; `main()` with no args works under pytest; `main()` with stubbed `fred_adapter.fetch_series`; same series written twice via `cache.write_liquidity_series` gives byte-identical files (AC-11) | `pytest api/tests/scripts/test_backfill_primaries.py -q` | policy + no-op determinism | live FRED |
|---|---|---|---|---|

**Area: `api/scripts/compute_pairs.py`**
| Fully-automated | `exit_code`: normal summary 0 (existing seeded 3 ok / 3 insufficient_overlap / 4 coin_unavailable); all `coin_unavailable` 2; `pair_count==0` 2; all `insufficient_overlap` (ok count 0) 2; `main()` with no args works under pytest (the existing untouched `test_script_main_prints_summary` keeps passing); `main()` with stubbed `compute_and_persist` returns matching code and still prints the summary lines | `pytest api/tests/scripts/test_compute_pairs.py -q` | AC-6 | statsmodels behavior (already covered) |
|---|---|---|---|---|
| Fully-automated | integration through the real `compute_and_persist` on the existing empty-cache fixture returns 2 (existing test proves 153 `coin_unavailable` rows) | same | end-to-end degraded path | |

**Area: `api/scripts/bootstrap_watchlist.py`**
| Fully-automated | absent target created from example (contents equal); existing target untouched (even if different); missing example returns 1; running twice is idempotent | `pytest api/tests/scripts/test_bootstrap_watchlist.py -q` (tmp_path args; touches no cache) | AC-9 | |
|---|---|---|---|---|

**Area: `.github/workflows/*.yml` (guard test)**
| Fully-automated | full reshaped guard suite over 5 workflows + new ordering / crash / tolerant-add / no-force tests | `pytest api/tests/scripts/test_snapshot_workflow_schedules.py -q` | AC-1, 2, 3, 4, 11(a) | that GitHub actually fires the cron or runs the YAML (AC-13); GitHub expression semantics beyond the string/structure checks |
| Hybrid | tolerant `git add` exits 0 in a temp repo with a minimal ignore rule, run under `bash -e` (precondition: `git` and `bash` on PATH) | same file | the real git failure modes (128 and 1) are neutralized | behavior under real Actions checkout |
| Known-gap | real scheduled run on GitHub | - | - | AC-13 (backlog stub) |

**Area: runbook (`BOOTSTRAP.md`)**
| Hybrid | doc-completeness checklist (below) + `grep -c` gates | manual review by EXECUTE, re-checked by VALIDATE | every directory/command/duration named | that the commands work end to end (needs live network; Known-gap) |
|---|---|---|---|---|
| Agent-Probe | AC-8, AC-15 numbers and depth discussion present and reasoned | reviewer reads plan + BOOTSTRAP.md | presence and reasoning | |

Gap resolution: AC-13, AC-14 - A) not writable here (no scheduler/network); B) post-merge `gh run list` observation / user-PC run; C) accepted as Known-Gap because it is the same precedent as the 3 existing workflows and regime AC-11; D) backlog NOTE per stubs above (kept CONDITIONAL, not PASS).

TDD stubs (red-first, for the Fully-automated rows; not written to disk during PLAN):
- `test("should return 2 when every fetch is unavailable or insufficient", () => { throw new Error("NOT IMPLEMENTED — TDD stub for: refresh_cache exit code 2") })`
- `test("should return 2 when every pair is coin_unavailable", () => { throw new Error("NOT IMPLEMENTED — TDD stub for: compute_pairs exit code 2") })`
- `test("should run compute step regardless of refresh exit code", () => { throw new Error("NOT IMPLEMENTED — TDD stub for: pairs workflow ordering") })`

## Safety Requirement (T22 - explicit and checkable)

`isolated_cache` is opt-in; `write_ohlcv` replaces whole series; a test that forgets it would destroy the user's deep-fetch OHLCV history, and a bare `bootstrap_watchlist.main([])` would create the developer's real `api/data/watchlist.json`. **Requirement (C4):** isolation is structural, not per-test. Each of the four test files gets a module-level `autouse=True` fixture that depends on `isolated_cache` and redirects `watchlist_store.DEFAULT_WATCHLIST_PATH` to `tmp_path / "watchlist.json"`; `conftest.py` stays untouched. Fetchers are additionally stubbed so no network is attempted. **Checkable via Checklist step 15** (autouse fixture presence, `--setup-show` isolated_cache SETUP count equal to the collected-test count, before/after content snapshot of `api/data/cache` plus `api/data/watchlist.json`, and the canary). EXECUTE must paste the (b) counts and (c) verdict into its report.

## Blast Radius

- ~15 files: 2 workflows (new), 3 scripts modified + 1 new, 1 runbook (new), 3 new test files, 2 test files modified, 2 backlog notes (UPDATE PROCESS).
- Risk class: **workflows that commit to `main`** (deploy/runtime-adjacent). Mitigated by the exact safety shape, tolerant staging, and the guard test. Not auth/billing/schema/API.
- Existing 3 workflows and `.gitignore` untouched. `web/`, `api/main.py`, deploy/CORS/host config untouched.
- Runtime effect on the repo today: a nightly Actions run per new workflow (canary) and no commits. Runtime effect on the user's PC: none unless they run the scripts.

## Risk Predictions and Edge Cases (vc-predict / vc-scenario, condensed)

| Risk | Likelihood | Mitigation in plan |
|---|---|---|
| `git add` on ignored/absent path fails the job nightly | Certain without handling (verified exit 1 / 128) | Tolerant add + subprocess test |
| Refresh crash skips compute, or crash (incl. 137/124 kills) still commits | Medium | `set +e` outputs, compute unconditional, commit gated on both codes being 0 or 2 (allow-list), final fail step on any other code; structural tests |
| ccxt rate-limit / Hyperliquid throttling on 22+ symbols | Unknown (no documented ceiling; known-gap) | no spacing change, no invented ceiling; canary will reveal; recorded as Known-Gap |
| Fresh-runner `compute_pairs` yields mostly `coin_unavailable` and exit 2 nightly | High on a fresh runner | Exit 2 is warn-not-fail by design; documented as canary-only; D7 makes universe coins present so pairs can be `ok` |
| Someone later flips `.gitignore` (P2) and the tolerant add starts committing 1+ GB/yr | Medium (future) | Future Work notes; D1 numbers recorded so that decision is auditable |
| Guard-test reshape weakens the 3 existing workflows' checks | Low | Legacy strict form retained for non-tolerant workflows; original 13 assertions still run |
| Test forgets `isolated_cache` (T22), or a bare `main([])` writes the real watchlist | Low-medium | Module-level autouse isolation fixtures + `--setup-show` count + before/after content snapshot |
| `2>/dev/null || true` hides a genuinely broken add | Low | Stated trade-off; exit codes carry failure signal |
| Two lanes both editing `.github/workflows/` (P2) | Low | P2 told to write requirements up, not implement; check at UPDATE |

Edge cases folded into tests: empty watchlist, empty/invalid universe, all-stale FRED, `pair_count == 0`, universe coin already in watchlist (not double-fetched), target watchlist already present, example file missing.

## T5 / T16 / T22 Alignment (for the master planning session)

- **T5:** MASTER-PLAN anticipates `.github/workflows/pairs-recompute.yml`. This plan's D2 **supersedes that name**: the pairs recompute is a step inside `pairs-refresh-snapshot.yml` so ordering after the OHLCV refresh is structural. The master session should mark T5 as addressed by this file name.
- **T16 (root README, same ops lane):** separate task, not pre-empted here. `api/scripts/BOOTSTRAP.md` is written to be linkable from that README and does not describe how to start the services.
- **T22:** handled via the Safety Requirement above; T22 stays "not a live bug" - this plan prevents the new tests from becoming the first to trip it.

## Runbook Contents (`api/scripts/BOOTSTRAP.md` - required sections; EXECUTE checks each)

1. Purpose and what "populated" means for `/screener`, `/pairs`, `/regime`.
2. Prerequisites (`uv sync --project api`, network access).
3. Ordered command sequence with exact commands: `bootstrap_watchlist` then `refresh_cache` then `backfill_primaries` then `backfill_pairs_universe` (one-time deep, manual) then `compute_pairs`. Note the order dependency: compute only after OHLCV.
4. A table naming every directory populated (`cache/ohlcv/`, `cache/liquidity/`, `cache/pairs/`, `api/data/watchlist.json`), which step fills it, and whether that step is scheduled-automatic, manual-one-time, or both.
5. Expected wall-clock per step, each labelled "estimated".
6. **Depth** section (AC-15): nightly refresh reaches ≤500 daily bars; the deep history (~2,230 bars, back to the ~2020-08-19 Hyperliquid floor) comes only from the one-time deep backfill; a CI/ephemeral pairs result is shallow.
7. Cache-strategy statement (D1) with the growth estimates and recovery-time estimate (AC-8), labelled estimates.
8. What the two new workflows do today (canary; commits inert) and what becomes real with a persistent disk (P2).
9. Known limits: live-fetch and cron firing unverified pre-merge; no documented rate-limit ceiling; if `uv run` itself fails and exits 2 the workflow reads it as "degraded" (Known-Gap).
10. **Staleness note (C7, D7 side effect):** after ANY `refresh_cache` run, `/pairs` reads `stale` until `compute_pairs` runs, because provenance compares per-coin bar counts. Always run `compute_pairs` after `refresh_cache`.

Doc-completeness gate (Hybrid): `grep -ci "stale" api/scripts/BOOTSTRAP.md` >= 1; `grep -c "cache/ohlcv\|cache/liquidity\|cache/pairs\|watchlist.json" api/scripts/BOOTSTRAP.md` ≥ 4; `grep -c "estimated" api/scripts/BOOTSTRAP.md` ≥ 5; `grep -ci "inert" api/scripts/BOOTSTRAP.md` ≥ 1; `grep -c "backfill_pairs_universe\|compute_pairs\|refresh_cache\|backfill_primaries\|bootstrap_watchlist" api/scripts/BOOTSTRAP.md` ≥ 5.

## Verification Evidence

| Gate / Scenario | Strategy | Proves SPEC criterion |
|---|---|---|
| `uv run --project api pytest api/tests/scripts/test_snapshot_workflow_schedules.py -q` (reshaped guard, 5 workflows) | Fully-Automated | AC-1, AC-3, AC-4 |
| Same file: `test_pairs_workflow_orders_refresh_before_compute`, `..._compute_runs_regardless_of_refresh_exit_code`, `test_crash_skips_commit_and_fails_job` | Fully-Automated | AC-2 |
| Same file: `test_tolerant_git_add_exits_zero_when_path_missing_or_ignored` (needs git+bash) | Hybrid | AC-3, AC-11 (a) |
| `pytest api/tests/scripts/test_refresh_cache.py api/tests/scripts/test_backfill_primaries.py -q` | Fully-Automated | AC-5, AC-11 (b) |
| `pytest api/tests/scripts/test_compute_pairs.py -q` | Fully-Automated | AC-6 |
| `pytest api/tests/scripts/test_bootstrap_watchlist.py -q` | Fully-Automated | AC-9 |
| Runbook doc-completeness greps + checklist read | Hybrid | AC-7 |
| Reviewer reads "D1 numbers" section and BOOTSTRAP.md for both numbers and reasoning | Agent-Probe | AC-8 |
| Reviewer reads Honesty Statement item 4 and BOOTSTRAP.md Depth section | Agent-Probe | AC-15 |
| `uv run --project api pytest api/ -q` before/after (record real counts; expected baseline 717 passed / 5 deselected, to be confirmed by EXECUTE) | Fully-Automated | AC-10 |
| `git log --oneline -5` + `gh pr view --json isDraft,baseRefName,headRefName` (needs push access and authenticated `gh`/GitHub MCP) | Hybrid | AC-12 |
| T22 gate: autouse fixtures present; `--setup-show` isolated_cache SETUP count equals collected count; before/after content snapshot incl. `watchlist.json` prints `REAL-CACHE-UNCHANGED` (Checklist step 15) | Fully-Automated | safety requirement (supports AC-10 integrity) |
| `test_triggers_permissions_and_concurrency` asserts `workflow_dispatch` on all 5 workflows | Fully-Automated | AC-1 |
| Scope gate: `git diff --name-only bbdf625..HEAD` limited to Touchpoints | Fully-Automated | AC-12 scope clause |
| Post-merge `gh run list --workflow pairs-refresh-snapshot.yml` / `liquidity-backfill-snapshot.yml` | Known-Gap (CONDITIONAL, backlog stub) | AC-13 |
| First scheduled or `workflow_dispatch` runs, or user-PC runbook run | Known-Gap (CONDITIONAL, backlog stub) | AC-14 |

Hard limits, stated: no live fetch and no real cron firing can be verified in this container; the plan's overall gate stays CONDITIONAL on AC-13 and AC-14.

## Test Infra Improvement Notes

- (none identified yet) beyond: the workflow guard test only checks YAML text/structure; a future `actionlint` step in CI would catch expression errors. Not added here (no CI beyond nightly snapshots; out of scope).
- This plan makes isolation autouse module-locally in the four touched script test files (C4). Consider (follow-up, not this plan) making `isolated_cache` autouse globally once `test_backfill_pairs_universe.py` and other unisolated files are audited - MASTER-PLAN T22.

## Future Work (named follow-ups, out of P1)

1. **`api/data/watchlist.py` loader fallback** to `watchlist.example.json` when the real file is absent (orchestrator ruling SQ1: outside P1's `api/scripts/`, `.github/workflows/`, `.gitignore` lane). D5's bootstrap copy is the interim path.
2. **`process/context/all-context.md` pointer** to `api/scripts/BOOTSTRAP.md` and the new workflows: **deferred to UPDATE PROCESS** (SQ2 - that file is under four-way write contention per MASTER-PLAN). Not written in PLAN or EXECUTE.
3. **T16 root README** (same ops lane) should later link `api/scripts/BOOTSTRAP.md`.
4. **P2 handoff:** a persistent disk makes these workflows real: state persists, commits (if the paths are un-ignored) or the host's own disk carries the cache. At that point revisit D1 (commit vs host-owned disk) and D4 (`DEFAULT_LIMIT` / a one-time deep seed on the host). The schedule and safety shape need no rewrite.
5. AC-13 / AC-14 backlog stubs (see AC section), written at UPDATE PROCESS.
6. Reconcile MASTER-PLAN T5 (name superseded) and update its lane table at the next planning session.

## Phase Completion Rules

- Status vocabulary honest: code and tests green means `CODE DONE`, not `VERIFIED`. This plan cannot reach `VERIFIED` without user confirmation of AC-13/AC-14 after merge.
- EXECUTE runs per-section test gates immediately after each checklist section (steps 3-10), not batched at the end.
- Failure ladder: fix inline if in blast radius; out-of-scope fix gets a new plan/stub; no fix path gets a backlog note.
- EXECUTE must not touch anything on the out-of-scope list; finding a need to touch one is a stop-and-report, not a decision.

## Validate Contract

Status: CONDITIONAL
Date: 29-09-26
date: 2026-09-29
generated-by: outer-pvl

Parallel strategy: sequential
Rationale: score 2/7 (S6 workflows that commit to `main`, S7 5+ files); dominant signal S7. Files are few and the three script edits share test files, so one sonnet-cheap review pass here (run inline by one validate agent, no Agent tool available) and one opus vc-execute-agent for EXECUTE, then one sonnet vc-tester for EVL. Estimated agents: EXECUTE 1 + EVL 1 = 2 (parallel-subagents would be ~3, agent-team not warranted; no cost guard triggered).

Decisions ruled by the orchestrator and NOT reopened: D1, D2, D3, D4, D5, D6 locked; D7 APPROVED; SQ1 (touch `api/data/watchlist.py`) and SQ2 (touch `process/context/all-context.md`) DENIED. No plan step violates SQ1 or SQ2 (verified: neither file is in Touchpoints; Checklist step 18 diffs both empty).

### Adversarial verification results (each checked against source, not the plan's assertion)

1. **D7 "leaves /screener unchanged": CONFIRMED.** `/screener` iterates the WATCHLIST only: `api/analytics/screener_board.py:176` (`coins = watchlist_store.read_watchlist()` then `for symbol in coins`) and `:224` (relative-performance, same). `/scalp` takes one symbol from the URL. The regime path reads only `BTC` `1d` (`api/analytics/regime/leg_boundary.py:164`). A repo-wide search for directory iteration over the OHLCV tree (`iterdir`/`glob`/`listdir`, excluding `.venv` and tests) finds exactly one hit, `api/scripts/check_weekly_anchor.py:51`, a manual diagnostic that is not served. Nothing lists "coins available in the cache", so extra `cache/ohlcv/{SYM}/1d.parquet` files for universe-only coins cannot change any `/screener` ranking, benchmark or relative-strength value. `fetch_ohlcv` merges into the cached tail (`ccxt_adapter.py:388-392`), so a deep-backfilled `1d` file keeps its history. One side effect to document (not a defect): `/pairs` provenance compares per-coin bar counts, so after any manual `refresh_cache` run `/pairs` reads `stale` until `compute_pairs` runs. BTC/HYPE already caused this; D7 widens it to all 18 coins. BOOTSTRAP.md must say "run `compute_pairs` after `refresh_cache`" (the order in Runbook section 3 already does).
2. **git-add handling: REPRODUCED independently** in a throwaway repo under the session scratchpad (real `.gitignore` copied; this working tree was never staged against). Directory absent: `git add <dir>/` exit 128, `git add -A -- <dir>/` exit 128. Directory present and ignored (`api/data/cache/*` rule): both exit 1 with "paths are ignored". Chosen form `git add -A -- <dir> 2>/dev/null || true`: exit 0 and nothing staged in both cases, also when the parent `api/data/cache` is absent, and under `bash -e` (what Actions uses); the following `git diff --staged --quiet` then prints "nothing new to commit" and exits 0. Adding `-f` DOES stage the ignored file (`-f` control run staged `api/data/cache/ohlcv/BTC/1d.parquet`), so `-f` would defeat D1. The plan never uses `-f`, and adds `test_no_force_add`. PASS.
3. **Guard-test reshape backward-compatible: CONFIRMED.** Current baseline of the two affected files run here: 22 passed (13 guard + 9 compute_pairs). The 13 are cron x3, staggered x1, triggers x3, retry x3, git-add x3. After `WORKFLOW_CACHE_DIRS` becomes `dict[str, list[str]]` every test except git-add iterates only over the keys, so they still bind. The git-add test becomes a set-equality check whose helper requires the exact legacy `git add <dir>` for the 3 existing workflows and the tolerant form only for the 2 new ones; strictness for the existing three is not weakened (it gains a duplicates check). Gap: see C6 (`workflow_dispatch` is not asserted by any guard test).
4. **Cron arithmetic: CONFIRMED.** Minutes-of-day: 17:47=1067, 18:17=1097, 18:47=1127 (verified in the three workflow files), new 19:17=1157, 19:47=1187. Before-21:00 rule (start+180<1440): 1157+180=1337 and 1187+180=1367, both below 1440. Stagger (>=20): 1157-1127=30, 1187-1157=30, 1157-1097=60, 1157-1067=90, 1187-1127=60, 1187-1097=90, 1187-1067=120. One cron per file. PASS.
5. **T22 isolation trap: the plan's step-15 checks are NOT sufficient.** See C4.
6. **Ordering and swallow analysis:** two steps of one job run on the same runner and share the checked-out workspace, so `compute_pairs` sees `refresh_cache`'s writes (chain-growth already relies on run-step then commit-step sharing files). The `set +e` / `$GITHUB_OUTPUT` / no-`exit` structure does make compute unconditional. But the crash detection can silently swallow real failures: see C1 and C2.
7. **Exit-code implementability:** all three mappings are computable from real return values (`OhlcvResult.status/df/insufficient_history`; `FredSeriesResult.status`; `ComputeSummary.pair_count/status_counts`), and `if [ "$code" -eq 1 ]`-style checks cannot mistake 2 for success because 2 only warns. Two mapping issues: C2 (compute) and C3 (per-item exceptions).
8. **Scope containment: PASS.** Every Touchpoint is in `api/scripts/`, `.github/workflows/`, `api/tests/scripts/`, or the plan's own task folder / `process/general-plans/backlog/` notes (written at UPDATE PROCESS). No `web/`, `api/main.py`, deploy/CORS, `pytrends_adapter.py` (or its test), `api/data/watchlist.py`, `ccxt_adapter.py`, `process/context/**`, or `.gitignore` in any step. `api/tests/conftest.py` is not edited (see C4: do not fix T22 there).

### Test gates

| criterion id | behavior | strategy | proving test | gap-resolution |
|---|---|---|---|---|
| AC-1 | both new workflows have `schedule`, `workflow_dispatch`, `permissions: contents: write`, concurrency group with `cancel-in-progress: false` | Fully-Automated | `uv run --project api pytest api/tests/scripts/test_snapshot_workflow_schedules.py -q` (needs C6: add a `workflow_dispatch` assertion) | B |
| AC-2 | refresh step index < compute step index in ONE job; compute has no `if:` on refresh; refresh/compute run-blocks contain no `exit` | Fully-Automated | same file: `test_pairs_workflow_orders_refresh_before_compute`, `test_pairs_workflow_compute_runs_regardless_of_refresh_exit_code` | B |
| AC-3 | safety shape on all 5 workflows; only own dirs staged; no `-f`; commit skipped and job failed on crash | Fully-Automated | same file: generalized existing tests, `test_git_add_stages_only_own_cache_dirs`, `test_no_force_add`, `test_crash_skips_commit_and_fails_job`, `test_new_workflows_run_the_expected_module` | B |
| AC-3 / AC-11a | tolerant `git add` exits 0 and stages nothing when dir absent or present-and-ignored | Hybrid (precondition: `git` and `bash` on PATH) | same file: `test_tolerant_git_add_exits_zero_when_path_missing_or_ignored` | B |
| AC-4 | crons 19:17 / 19:47: one per file, start+180<1440, >=20 min stagger vs all 5 | Fully-Automated | same file: `test_cron_starts_at_least_3h_before_utc_midnight`, `test_crons_are_staggered` (arithmetic verified above) | B |
| AC-5 | `refresh_cache` and `backfill_primaries` exit 0 / 2 / 1 policy; D7 universe coins on `1d` only; bad universe file recorded not crashed | Fully-Automated | `pytest api/tests/scripts/test_refresh_cache.py api/tests/scripts/test_backfill_primaries.py -q` | B |
| AC-6 | `compute_pairs` exit code reflects outcome (rule per C2) | Fully-Automated | `pytest api/tests/scripts/test_compute_pairs.py -q` | B |
| AC-9 | watchlist bootstrap: create if absent, never overwrite, missing example returns 1, idempotent | Fully-Automated | `pytest api/tests/scripts/test_bootstrap_watchlist.py -q` | B |
| AC-10 | whole api suite stays green; baseline measured by EXECUTE (expected 717 passed / 5 deselected, UNCONFIRMED) | Fully-Automated | `uv run --project api pytest api/ -q` before and after | A |
| AC-11b | writing the same FRED series twice through `cache.write_liquidity_series` gives byte-identical files | Fully-Automated | `test_backfill_primaries.py` | B |
| AC-7 | runbook complete: every dir, command and duration named | Hybrid (doc check) | the four `grep -c` gates under Runbook Contents plus the section checklist | B (live run of the runbook = D) |
| AC-8, AC-15 | growth and recovery numbers with reasoning; depth mismatch and consequence | Agent-Probe | reviewer reads plan "D1 numbers", Honesty item 4, and BOOTSTRAP.md Depth section | B |
| AC-12 | commit on `claude/p1-pipeline`, draft PR against `main` | Hybrid (precondition: push access and authenticated `gh` or GitHub MCP) | `git log --oneline -5`; `gh pr view --json isDraft,baseRefName,headRefName` (or MCP `list_pull_requests`) | B |
| T22 safety | new tests cannot write the real cache or watchlist | Fully-Automated | strengthened commands in Test-gate command list, item 9 (C4) | B |
| Scope | only Touchpoint files changed | Fully-Automated | `git diff --name-only bbdf625..HEAD` and the empty-diff command in Checklist step 18 | B |
| AC-13 (cron actually fires) | named residual, not proven here | none (no proving strategy in this container) | post-merge `gh run list --workflow pairs-refresh-snapshot.yml` | D (backlog stub `pipeline-cron-firing-confirmation_NOTE_28-09-26.md`) |
| AC-14 (live ccxt/FRED fetch works) | named residual, not proven here | none (no proving strategy in this container) | first scheduled or `workflow_dispatch` run post-merge, or user-PC runbook run | D (backlog stub `pipeline-live-fetch-canary_NOTE_28-09-26.md`) |

Failing stubs (red-first, copy verbatim into the test files; Hybrid, Agent-Probe and residual rows get none):
- AC-1: `test("should schedule both new workflows with dispatch, write-only permissions and a non-cancelling concurrency group", () => { throw new Error("NOT IMPLEMENTED — TDD stub: AC-1 new workflow triggers/permissions/concurrency") })`
- AC-2: `test("should run compute step after refresh step in one job regardless of refresh exit code", () => { throw new Error("NOT IMPLEMENTED — TDD stub: AC-2 pairs workflow ordering") })`
- AC-3: `test("should stage only owned dirs with the tolerant form and never force-add", () => { throw new Error("NOT IMPLEMENTED — TDD stub: AC-3 tolerant staging and no -f") })`
- AC-3 crash: `test("should skip the commit and fail the job when a script exits with a crash code", () => { throw new Error("NOT IMPLEMENTED — TDD stub: AC-3 crash skips commit") })`
- AC-4: `test("should keep every cron 3h before UTC midnight and 20 min apart across 5 workflows", () => { throw new Error("NOT IMPLEMENTED — TDD stub: AC-4 cron slots") })`
- AC-5: `test("should return 2 when every fetch is unavailable or insufficient", () => { throw new Error("NOT IMPLEMENTED — TDD stub: AC-5 refresh_cache exit code 2") })`
- AC-5 backfill: `test("should return 2 when no FRED series is ok", () => { throw new Error("NOT IMPLEMENTED — TDD stub: AC-5 backfill_primaries exit code 2") })`
- AC-6: `test("should return 2 when no pair computed ok", () => { throw new Error("NOT IMPLEMENTED — TDD stub: AC-6 compute_pairs exit code 2") })`
- AC-9: `test("should copy the example watchlist only when the target is absent", () => { throw new Error("NOT IMPLEMENTED — TDD stub: AC-9 bootstrap_watchlist") })`
- AC-11b: `test("should write a byte-identical liquidity file when the series is unchanged", () => { throw new Error("NOT IMPLEMENTED — TDD stub: AC-11b no-op determinism") })`

Legacy line form (retained for existing consumers):
- workflows: [Fully-automated: `uv run --project api pytest api/tests/scripts/test_snapshot_workflow_schedules.py -q`] | [hybrid: same file, tolerant-add test, needs git + bash]
- scripts: [Fully-automated: `uv run --project api pytest api/tests/scripts/test_refresh_cache.py api/tests/scripts/test_backfill_primaries.py api/tests/scripts/test_compute_pairs.py api/tests/scripts/test_bootstrap_watchlist.py -q`]
- suite: [Fully-automated: `uv run --project api pytest api/ -q`]
- runbook: [hybrid: doc-completeness greps] | [agent-probe: AC-8 and AC-15 reviewer read]
- live behavior: [known-gap: AC-13 and AC-14, documented, backlog stubs]

### Test-gate command list (EXECUTE runs these; C-items are REQUIRED amendments from this validate pass)

1. Baseline BEFORE any edit: `uv run --project api pytest api/ -q 2>&1 | tail -5` (record the real counts; do not quote 717/5). Then, AFTER the baseline run, create the marker: `touch <scratchpad>/p1-marker` (the marker must not predate the baseline run, otherwise pre-existing tests confound the check).
2. Per section, right after each Checklist section (steps 3-10): the matching single-file pytest line from the Test gates table.
3. `uv run --project api pytest api/tests/scripts -q` (fast subset), then step 16 full suite: `uv run --project api pytest api/ -q` (expect only added tests, zero failures, deselected unchanged).
4. `uv run --project api python -c "import yaml,sys; [yaml.safe_load(open(f)) for f in sys.argv[1:]]" .github/workflows/pairs-refresh-snapshot.yml .github/workflows/liquidity-backfill-snapshot.yml` exits 0 (PyYAML 6.0.3 is installed in the api env).
5. Runbook greps: `grep -c "cache/ohlcv\|cache/liquidity\|cache/pairs\|watchlist.json" api/scripts/BOOTSTRAP.md` >= 4; `grep -c "estimated" api/scripts/BOOTSTRAP.md` >= 5; `grep -ci "inert" api/scripts/BOOTSTRAP.md` >= 1; `grep -c "backfill_pairs_universe\|compute_pairs\|refresh_cache\|backfill_primaries\|bootstrap_watchlist" api/scripts/BOOTSTRAP.md` >= 5.
6. `node .claude/skills/vc-generate-plan/scripts/validate-plan-artifact.mjs <this plan>` (passes today: 0 failures, 0 warnings) and `git diff --check`.
7. Scope: `git diff --name-only bbdf625..HEAD` lists only Touchpoint files plus this task folder; `git diff bbdf625..HEAD -- .gitignore web api/main.py api/data/watchlist.py api/data/pytrends_adapter.py api/tests/data/test_pytrends_adapter.py api/data/ccxt_adapter.py process/context .github/workflows/chain-growth-snapshot.yml .github/workflows/narrative-snapshot.yml .github/workflows/liqtide-snapshot.yml` prints nothing.
8. AC-12 (Hybrid): `git log --oneline -5` and `gh pr view --json isDraft,baseRefName,headRefName` (or MCP `list_pull_requests`); if push or PR creation is blocked by the environment, record it as an EXECUTE concern, do not claim AC-12.
9. **T22 (strengthened, replaces the step-15 trio; C4):**
   - (a) Every test in the three new/extended test files gets isolation structurally: a module-level `autouse` fixture in each of `test_refresh_cache.py`, `test_backfill_primaries.py`, `test_bootstrap_watchlist.py` and `test_compute_pairs.py` that depends on `isolated_cache` AND monkeypatches `watchlist_store.DEFAULT_WATCHLIST_PATH` to `tmp_path / "watchlist.json"` (module-local, so `conftest.py` stays untouched).
   - (b) Transitive-safe proof (works through `seeded` etc.): `uv run --project api pytest api/tests/scripts/test_refresh_cache.py api/tests/scripts/test_backfill_primaries.py api/tests/scripts/test_bootstrap_watchlist.py api/tests/scripts/test_compute_pairs.py --setup-show -q 2>&1 | grep -c "SETUP    F isolated_cache"` must EQUAL `uv run --project api pytest <same four files> --collect-only -q 2>&1 | grep -c "::"` (measured here on today's `test_compute_pairs.py`: 8 SETUPs vs 9 collected, because `test_golden_bh_set` is pure; with the autouse fixture in place they must be equal).
   - (c) Before/after content snapshot of everything the new code could touch, run around the new tests only (not the whole suite, so old unisolated tests cannot confound it): `snap(){ find api/data/cache api/data/watchlist.json -type f -printf '%p\t%s\t%T@\n' 2>/dev/null | sort | sha256sum; }; a=$(snap); uv run --project api pytest api/tests/scripts/test_refresh_cache.py api/tests/scripts/test_backfill_primaries.py api/tests/scripts/test_bootstrap_watchlist.py api/tests/scripts/test_compute_pairs.py api/tests/scripts/test_snapshot_workflow_schedules.py -q; b=$(snap); [ "$a" = "$b" ] && echo REAL-CACHE-UNCHANGED || echo REAL-CACHE-TOUCHED`. This catches modifications, deletions (the RFC-005 incident was a deletion) and `api/data/watchlist.json`; the plan's `find -newer` cannot see deletions or the watchlist. (Pre-state in this container: `api/data/cache/{ohlcv,liquidity,pairs}` exist with 0 files, `api/data/watchlist.json` absent.)
   - (d) Keep the planned canary `test_isolated_cache_redirects_cache_root` in each script test file.

### Dimension findings

- Infra fit: CONCERN — structure verified (one job shares the workspace; PyYAML present; `python -m api.scripts.*` works from repo root; crons and slots correct). Crash detection only tests `exit_code == 1`, so kill signals (137 OOM/timeout) or any other non-0/2 code would leave the job green and still commit (C1). Per-item exceptions collapse into a warn-only exit 2 (C3).
- Test coverage: CONCERN — T22 checks are file-level and cannot see deletions (C4); planned `argparse` `main()` shape breaks the existing `test_script_main_prints_summary` (C5); `workflow_dispatch` not asserted (C6); compute exit rule inconsistent with the 0-means-something-worked contract (C2).
- Breaking changes: PASS — `/screener`, `/pairs`, `/regime` outputs unchanged; `refresh_all()` / `backfill_all()` in `refresh_cache.py` / `backfill_primaries.py` have no callers (the only other `backfill_all` is `backfill_pairs_universe.py`'s own, unrelated); D7 verified not to reach `/screener`. The one contract-visible edit to existing behavior is `compute_pairs.main()` signature (see C5).
- Security surface: PASS — no secrets; `permissions: contents: write` is mandated by SPEC AC-3 even though commits are inert under D1 (accepted, consistent with the 3 existing workflows); tag-pinned `actions/checkout@v4` and `astral-sh/setup-uv@v3` same as the existing three; no `-f`; keyless providers.
- Section 1 (workflows, steps 8-9): CONCERN — commit and crash conditions (C1); everything else feasible, `git add` handling verified.
- Section 2 (scripts, steps 3-6): CONCERN — C2, C3, C5.
- Section 3 (guard-test reshape, step 10): CONCERN (low) — backward compatible; C6 dispatch gap; module docstring still says "three workflows".
- Section 4 (bootstrap_watchlist, step 7): PASS — call-time path resolution is correct (`DEFAULT_WATCHLIST_PATH` read at call time per `watchlist.py`); isolation risk covered by C4.
- Section 5 (runbook, step 11): PASS — sections and greps are checkable; add the "run compute_pairs after refresh_cache because /pairs reads stale otherwise" note (Adversarial result 1).
- Section 6 (T22 verification, step 15): CONCERN — C4.

### Concerns requiring plan supplement (first-pass CONDITIONAL; no user available to accept)

- C1 (Infra, MEDIUM): workflow crash detection. `refresh`/`compute`/`backfill` steps and the commit/fail steps only test `exit_code == '1'`. A code such as 137 (OOM/timeout kill), 139, 124, or `uv` itself failing (uv exits 2, indistinguishable from "all unavailable") is neither 1 nor 2, so the step stays green, the commit runs, no error is raised. Fix: treat any code that is not `0` or `2` as a crash. Commit-step `if:` = `steps.refresh.outputs.exit_code == '0' || steps.refresh.outputs.exit_code == '2'` combined with the same for compute (equivalently `!= '0' && != '2'` negated); final fail step `if:` = any exit_code that is neither `'0'` nor `'2'`. Update `test_crash_skips_commit_and_fails_job` to assert this form. Residual (accept as Known-Gap, note in BOOTSTRAP.md limits): `uv run` internal failure exiting 2 still reads as "degraded".
- C2 (Test coverage, LOW-MEDIUM): `compute_pairs` exit rule. Public Contracts says "0 = at least one item succeeded" but the compute row returns 0 when pairs exist that are all `insufficient_overlap` (zero pairs computed). Fix: exit 2 iff `summary.status_counts.get("ok", 0) == 0` (covers `pair_count == 0`, all `coin_unavailable`, all `insufficient_overlap`); else 0. The existing seeded fixture (3 ok / 3 insufficient_overlap / 4 coin_unavailable) still returns 0. Add one `insufficient_overlap`-only case to the exit-code tests. Note: SPEC AC-6's "stale" outcome cannot occur post-compute (provenance is written from the current cache), so it needs no branch.
- C3 (Infra, MEDIUM): per-item exception handling turns a systematic bug or provider shape change into a warn-only run. `fetch_ohlcv` never raises by contract, so an exception is unexpected. Fix: record per-item exceptions with `status="error"`; `exit_code`: 1 if every item errored (none produced a normal status), else 0/2 as planned; same for `backfill_primaries`. Add cases "all items raise -> 1" and "one raises, others ok -> 0". Also amend Honesty Statement item 2(a): the canary raises a GitHub warning annotation on total unavailability (exit 2) and fails the job only on a crash or total exception; it does not "fail loudly" on every provider change.
- C4 (Test coverage / SAFETY, MEDIUM): T22 verification is insufficient. `grep -L isolated_cache` is file-level: any one mention (a comment, one test) satisfies it for every test in the file; it cannot see fixtures obtained transitively (today `test_compute_pairs.py` mentions `isolated_cache` only twice, while 8 of its 9 tests get it via `seeded`, so the planned "`grep -c` >= pre-change count plus new tests" is either vacuous or unsatisfiable). `find -newer` cannot see deletions, and does not cover `api/data/watchlist.json` (a rogue `bootstrap_watchlist.main([])` with the default target would create the developer's real watchlist, the exact RFC-005 failure class), `cache/legs`, `cache/narrative`, `cache/liqtide`; the marker's position relative to the baseline run is also ambiguous. Fix: replace step 15 with the strengthened commands in Test-gate command list item 9 (autouse isolating fixture in each of the four test files, `--setup-show` count equals collected count, before/after content snapshot including the watchlist). Do NOT edit `conftest.py` (out of scope).
- C5 (Breaking / Test coverage, MEDIUM): planned `main(argv=None)` with `parser.parse_args(argv)` will parse pytest's own `sys.argv` when called with no arguments. Verified: `argparse` with `sys.argv=['pytest','api/tests/scripts','-q']` raises `SystemExit(2)` "unrecognized arguments". The existing, untouched `test_script_main_prints_summary` calls `compute_pairs.main()` with no arguments and expects `0`, so it would fail, contradicting "existing tests untouched". Fix in Checklist steps 3, 5, 6: `main(argv=None, *, sleep=time.sleep)` uses `parser.parse_args([] if argv is None else argv)`; the `__main__` wrapper calls `main(sys.argv[1:])` (so `--help` and bad flags still work from the CLI). Add one test that `main()` (no args) works under pytest for each of the three scripts.
- C6 (Test coverage, LOW): AC-1 requires `workflow_dispatch` on the new workflows and SPEC says the guard asserts it, but no existing or planned test does. Fix: add `assert "workflow_dispatch" in triggers` to `test_triggers_permissions_and_concurrency` (all 3 existing workflows have it: verified at chain-growth:18, narrative:19, liqtide:16). Also make the tolerant-add subprocess test copy a minimal ignore rule (`api/data/cache/*`) into the temp repo instead of the live `.gitignore` (so a future P2 un-ignore does not make the test misleading), run it with `bash -e` (as Actions does), and update the module docstring ("three nightly snapshot workflows" -> five). Clarify the `test_pairs_workflow_compute_runs_regardless_of_refresh_exit_code` sentence in the reshape section: assert the refresh and compute run-blocks contain no `exit` at all.
- C7 (Documentation, LOW, optional): AC-12 is labelled Fully-Automated but needs push access and authenticated `gh` or GitHub MCP; relabel Hybrid (done in the table above). Runbook: add the compute-after-refresh staleness note (Adversarial result 1).

Open gaps: C1-C7 above (all fixable inside the plan; none needs an out-of-scope file).
Known-gap: AC-13: known-gap: documented as NEW PLAN REQUIRED — see backlog/pipeline-cron-firing-confirmation_NOTE_28-09-26.md (written at UPDATE PROCESS)
Known-gap: AC-14: known-gap: documented as NEW PLAN REQUIRED — see backlog/pipeline-live-fetch-canary_NOTE_28-09-26.md (written at UPDATE PROCESS)
Known-gap: live behavior: no live ccxt/Hyperliquid/FRED fetch and no real cron firing is verifiable in this container (egress proxy); ccxt/Hyperliquid bulk rate-limit ceiling stays undocumented.

What This Coverage Does NOT Prove (what this coverage does NOT prove):
- Guard tests: that GitHub really fires the cron, resolves the `if:` expressions as intended, or that the YAML runs on a runner; only text/structure and the local git behavior of the tolerant add. A future `actionlint` step would catch expression errors.
- Script tests: real ccxt/Hyperliquid or FRED response shapes, real rate limiting, or a real fresh-runner run; all fetchers are stubbed.
- `compute_pairs` tests: statsmodels numerics on real data (already covered elsewhere); a CI pairs result is a shallow (<=500 bars) canary, not a quality result.
- Tolerant-add test: behavior under a real Actions checkout (`actions/checkout` state, token permissions, branch protection on `main`).
- Runbook checks: that the documented command sequence works end to end or that its estimated durations are right; the numbers in AC-8 are estimates, not measurements.
- Whole-suite gate: the 717/5 baseline is unconfirmed until EXECUTE measures it.
- Until C1 is applied: that a killed or crashed step fails the job.

Gate: CONDITIONAL
Accepted by: none yet. First-pass CONDITIONAL with no user available in this session; NOT accepted. Concerns awaiting a supplement cycle (vc-plan-agent PVL-supplement, then re-validate from V1): C1 workflow crash detection, C2 compute exit rule, C3 per-item exception handling, C4 T22 verification strength, C5 argparse `main()` vs existing test, C6 dispatch assertion and test hygiene, C7 AC-12 label and runbook note. EXECUTE is NOT legal until Gate: PASS or a recorded supplement cycle or explicit user acceptance.

## Autonomous Goal Block

```
SESSION GOAL: P1 pipeline completeness - two nightly workflows (pairs-refresh 19:17 UTC, liquidity-backfill 19:47 UTC), 0/1/2 exit codes on refresh_cache / backfill_primaries / compute_pairs, bootstrap_watchlist.py, BOOTSTRAP.md, reshaped workflow guard test
Charter + umbrella plan: N/A - single plan: process/general-plans/active/pipeline-completeness_28-09-26/pipeline-completeness_PLAN_28-09-26.md
Autonomy: proceed without approval pauses on reversible steps; subagent delegation stays mandatory; blocked items go to backlog (feedback_autonomous_phase_execution.md)
Hard stops / safety constraints:
- Do NOT touch web/, api/main.py, deploy/CORS/host config, api/data/pytrends_adapter.py and its test, api/data/watchlist.py, api/data/ccxt_adapter.py, process/context/**, .gitignore, or the 3 existing workflows; a need to is stop-and-report
- Never use git add -f / --force; nothing new is committed (D1)
- Never run any script against the real cache from EXECUTE; every test that can reach a cache path must be isolated (T22)
- No live-provider probes; no claim that cron firing or live fetches are verified
- EXECUTE is illegal while Gate is CONDITIONAL without a recorded supplement cycle (C1-C7) or explicit user acceptance
Next phase: PVL supplement cycle (vc-plan-agent), re-validate from V1, then EXECUTE: process/general-plans/active/pipeline-completeness_28-09-26/pipeline-completeness_PLAN_28-09-26.md
Validate contract: inline in plan (## Validate Contract)
Execute start: fully-auto: uv run --project api pytest api/ -q (record baseline first) then per-section pytest in api/tests/scripts | hybrid: tolerant git-add test + doc greps | probe: AC-8/AC-15 reviewer read | high-risk pack: no (workflows are runtime-adjacent, not auth/billing/schema/API)
```

## Resume and Execution Handoff

1. **Selected plan file:** `/home/user/psychic-train/process/general-plans/active/pipeline-completeness_28-09-26/pipeline-completeness_PLAN_28-09-26.md`
2. **Last completed step:** PLAN written (SPEC locked earlier; INNOVATE decisions D1-D6 approved; D7 added by PLAN and needs confirmation).
3. **Validate-contract status:** written 29-09-26 (outer-pvl), Gate: CONDITIONAL, first pass. D7 confirmed (orchestrator-approved; `/screener` unchanged, verified). Tolerant `git add` design verified. PVL supplement cycle 1 has folded C1-C7 into the plan body (the Validate Contract above is left as written); VALIDATE re-runs from V1 before EXECUTE.
4. **Supporting context loaded:** `process/MASTER-PLAN.md` (P1, T5, T16, T22), the SPEC, `process/context/all-context.md`, `process/context/tests/all-tests.md`, `process/context/planning/all-planning.md`, `chain-growth-snapshot.yml`, `snapshot_chain_growth.py`, `test_snapshot_workflow_schedules.py`, `test_compute_pairs.py`, `conftest.py`.
5. **Next step for a fresh agent:** run VALIDATE on this plan; after PASS (or accepted CONDITIONAL with cycle) and explicit `ENTER EXECUTE MODE`, spawn vc-execute-agent with the exact plan path above and start at Checklist step 1.

**Files EXECUTE may touch (exhaustive):** the Touchpoints tables above - `.github/workflows/pairs-refresh-snapshot.yml`, `.github/workflows/liquidity-backfill-snapshot.yml`, `api/scripts/{refresh_cache,backfill_primaries,compute_pairs,bootstrap_watchlist}.py`, `api/scripts/BOOTSTRAP.md`, `api/tests/scripts/{test_refresh_cache,test_backfill_primaries,test_bootstrap_watchlist,test_compute_pairs,test_snapshot_workflow_schedules}.py`, plus its own report inside this task folder.

**HARD OUT OF SCOPE (stop and report if a need arises):** `web/`; `api/main.py`; any deploy/CORS/host-binding config; `api/data/pytrends_adapter.py`; `api/tests/data/test_pytrends_adapter.py`; `api/data/watchlist.py`; `process/context/**` (including `all-context.md` - UPDATE PROCESS only); `.gitignore`; the three existing workflow files; `api/data/ccxt_adapter.py` (`DEFAULT_LIMIT` stays 500).

**Validator commands:** `node .claude/skills/vc-generate-plan/scripts/validate-plan-artifact.mjs <plan>`; `node .claude/skills/vc-audit-vc/scripts/validate-agent-parity.mjs --strict` only if agent-surface files change (none planned).

**Next Step:** say **ENTER VALIDATE MODE** (required before EXECUTE); the RIPER-5 flow then continues to `ENTER EXECUTE MODE` after the validate-contract is written.
