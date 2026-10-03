---
phase: rfc-003
date: 2026-09-26
status: COMPLETE
feature: onchain-activity
plan: process/features/onchain-activity/completed/chain-growth_25-09-26/chain-growth_PLAN_25-09-26.md
---

# chain-growth RFC-3: storage and nightly workflow (fallback: no Dune, no backfill script)

**TL;DR:** RFC-3 is built exactly as the Stage 0 report specified, with a 14-day revision window.
- New code: additive `cache.py` merge helpers, a `.gitignore` negation, `snapshot_chain_growth.py` and a nightly `chain-growth-snapshot.yml` workflow.
- Tests: 22 new tests pass. The full suite is **467 passed / 5 deselected** (baseline 445 / 5, +22).
- Evidence pack: written. Its only validator failure is the intentionally PENDING review decision.
- Not committed.

## What Was Done

| File | Change |
|---|---|
| `api/data/cache.py` | **Appended only** (0 lines removed; no existing function changed). Adds `ONCHAIN_COLUMNS`, `ONCHAIN_REVISION_WINDOW_DAYS = 14`, `OnchainMergeResult`, `onchain_series_path`, `read_onchain_series`, `merge_onchain_series`. |
| `.gitignore` | `!api/data/cache/onchain/` added after the narrative block, with a comment. |
| `api/scripts/snapshot_chain_growth.py` | New script (details below). |
| `.github/workflows/chain-growth-snapshot.yml` | New workflow (details below). |
| `api/tests/data/test_cache_chain_growth.py` | 12 tests. |
| `api/tests/scripts/test_snapshot_chain_growth.py` | 10 tests. |
| `harness/rfc-003/*.json` | Risk evidence pack, 5 files. |

**How `merge_onchain_series` behaves:**
- New dates are inserted.
- A date within `today - 14 d` … `today` whose value changed is replaced: `revised=true`, `previous_value` keeps the old value, `as_of_utc` is updated. The window boundary is inclusive.
- An older date whose value changed is **kept as stored** and counted in `out_of_window_drift`.
- Nothing is ever deleted.
- Future dates (after the UTC `today`) are dropped.
- Float noise below 1e-9 relative is not counted as a change.
- The Parquet file is rewritten only when a row was inserted or revised.

**What `snapshot_chain_growth.py` does:**
- Flags: `--dry-run` (temporary `CACHE_ROOT`, restored in `finally`), `--verify-only`, `--only`, `--window-days` (must be ≥ 0).
- Reads the chain list with `load_chains()`.
- Fetches each live chain's full series from growthepie for `active_addresses` and `transactions`, plus the L2BEAT `range=max` transactions cross-check where configured.
- Waits `REQUEST_SPACING_SECONDS = 6` between requests. The `sleep` is injectable, so tests don't wait.
- Isolates each series: one failure prints its own line and the run continues.
- Skips chains with `source=none` before any fetch and writes no file for them.
- Prints one summary line per series, including history depth.
- Exit codes: 0 = at least one series ok; 2 = every series unavailable; 1 = unexpected crash.

**What the workflow does:**
- Triggers: cron `0 22 * * *` plus `workflow_dispatch`. There is no `pull_request` trigger.
- Permissions: `contents: write` only. Concurrency group: `chain-growth-snapshot`.
- Uses no secrets and no `env:` keys.
- Stages only `api/data/cache/onchain/`, and commits only when that diff is non-empty.
- Pushes with a 3-attempt `pull --rebase` retry, the same as `narrative-snapshot.yml`.

## What Was Skipped or Deferred
- `backfill_chain_growth.py`: not built. Each nightly run fetches full history, so the first run is the backfill (Stage 0 §2).
- Dune / `DUNE_API_KEY`: not applicable (NOT-VIABLE verdict).
- RFC-4: not started, as instructed.

## Test Gate Outcomes
- `uv run --project api pytest api/tests/data/test_cache_chain_growth.py api/tests/scripts/test_snapshot_chain_growth.py -q` → **22 passed**.
- `uv run --project api pytest api/ -q` → **467 passed, 5 deselected**.
- Scenarios covered by name:

  | Scenario | Test(s) |
  |---|---|
  | round-trip through the real writer and reader | `test_round_trip_columns_and_dtypes` |
  | in-window revision | `test_in_window_revision_replaces_and_keeps_trail` |
  | inclusive window boundary | `test_window_boundary_is_inclusive` |
  | out-of-window drift ignored and counted | `test_out_of_window_change_kept_and_counted` |
  | no deletes, duplicate dates deduped | `test_missing_dates_never_deleted_and_duplicates_dedupe` |
  | no rewrite when unchanged | `test_no_change_merge_does_not_rewrite` (bytes and mtime) |
  | UTC dates, future dates dropped | `test_future_dates_dropped_utc` |
  | dry-run writes nothing | `test_dry_run_writes_nothing_and_restores_root` |
  | partial failure leaves the others written, equal to a solo run (AC-12) | `test_partial_failure_leaves_others_written` |
  | unavailable chains never written (AC-7) | `test_full_run_writes_live_chains_and_skips_none_sources` |
  | request spacing (16 requests, 15 sleeps) | `test_spacing_between_every_request` |
  | exit code 2 when everything is unavailable | `test_all_unavailable_exit_2` |
  | `--verify-only` makes no fetch calls | `test_verify_only_makes_no_adapter_calls` |

- Other checks:
  - `yaml.safe_load` parses the workflow.
  - `git diff --check` is clean.
  - `git diff` of `cache.py` and `.gitignore` removes 0 lines.
  - All 6 `git check-ignore -v` cases match Stage 0 §3: both `onchain/` paths, `narrative/pytrends` and `liqtide` are not ignored; `coingecko_trending` and `ohlcv` are still ignored.
- Workflow diff against `narrative-snapshot.yml`, excluding comment lines. Only these differ:
  - the workflow name;
  - the cron (`0 22`);
  - the concurrency group;
  - the run command (script name; no `--with pytrends`);
  - the warn step's name and text;
  - the commit step's name;
  - the `git add` path;
  - the commit message.
- Evidence pack:
  - `validate-risk-artifacts.mjs` fails only on `review-decision.json decision must be approved…`, the expected PENDING.
  - `validate-evidence-pack.mjs` expects a flat `harness/` directory and cannot read the `rfc-003/` subfolder. This is the same layout narrative uses for `harness/rfc-004/`, so it is a tooling limit, not a missing artifact.

## Plan Deviations
These are Stage 0 §7 items, approved with the "go" and now applied. UPDATE PROCESS should write them into the plan text:
1. `write_chain_growth_point` became `merge_onchain_series`, and the path is `onchain/{source}/{chain}/{metric}`.
2. There is no backfill script; `--only` covers refilling one chain by hand.
3. No `DUNE_API_KEY` or env mapping; the workflow has no secrets.
4. The AC-9 redistributable flag comes from the adapter constant, not a per-row column.
5. AC-7: a failed or unavailable chain writes **nothing**. RFC-4 derives unavailable/stale from absence or from the age of `as_of_utc`.

One addition beyond Stage 0: `OnchainMergeResult` also counts `dropped_future` and `rows`. It is used only for summaries and tests, and stays inside the blast radius.

## First Run After Merge (user steps)
1. Merge to `main`. Then either wait for 22:00 UTC, or trigger the workflow by hand: GitHub → Actions → "Chain-growth daily snapshot" → Run workflow, or `gh workflow run chain-growth-snapshot.yml`.
2. Optional local preview from the repo root, with no writes: `uv run --project api python -m api.scripts.snapshot_chain_growth --dry-run`.
3. What the first run's log shows:
   - `solana/…`, `bnb/…`, `tron/…: skipped (source-unavailable)`.
   - One line per series (12 growthepie + 4 L2BEAT), for example `growthepie/base/active_addresses: ok inserted=<full history> revised=0 drift=0 rows=N first=YYYY-MM-DD last=YYYY-MM-DD`. The `first=` values answer the RFC-1 history-depth known gap for RFC-4.
   - Any failed series shows as `…: unavailable (<reason>)`.
   - Later nights show small `inserted` counts and occasional `revised` counts. If nothing changed, nothing is committed.
4. Review the commit `chore: chain-growth snapshot YYYY-MM-DD`, which should contain only files under `api/data/cache/onchain/`. Then record APPROVE or REJECT in `harness/rfc-003/review-decision.json`.

## Test Infra Gaps Found
- Live endpoints and the real cron run cannot be tested from this container, because egress is blocked. The run is a user-side (Hybrid) check.
- `actionlint` is not installed, so the workflow was checked by a manual diff instead.
- The evidence-pack validator does not support per-RFC subfolders.

## Closeout Packet
- Plan: `process/features/onchain-activity/completed/chain-growth_25-09-26/chain-growth_PLAN_25-09-26.md`.
- Finished: RFC-3 code, tests and evidence pack.
- Verified: automated gates, YAML, gitignore and diff checks.
- Unverified: the live run and the first commit on `main`; the review decision is PENDING.
- Classification: **Keep in active/testing**.
- Follow-up stubs: none. CONTEXT_PARTIAL: none.
- Next: EVL confirmation run (vc-tester), then RFC-4 Stage 0.

## Forward Preview
### Test Infra Found
- `isolated_cache` together with monkeypatched adapters and an injected `sleep`: this is the pattern to reuse for fetching scripts.
### Blast Radius Changes
- Modified: `cache.py` (additive), `.gitignore` (+3 lines).
- New: 1 workflow, 1 script, 2 test files, 5 evidence JSON files.
- Nothing in narrative, regime or screener code changed.
### Commands to Stay Green
- `uv run --project api pytest api/ -q` → 467 passed, 5 deselected.
### Dependency Changes
- None.
