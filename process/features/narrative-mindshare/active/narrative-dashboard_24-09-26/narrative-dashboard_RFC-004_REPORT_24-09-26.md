---
phase: rfc-004-nightly-narrative-snapshot
date: 2026-09-24
status: COMPLETE_WITH_GAPS
feature: narrative-mindshare
plan: process/features/narrative-mindshare/active/narrative-dashboard_24-09-26/narrative-dashboard_PLAN_24-09-26.md
---

# RFC-4 — Nightly narrative snapshot: report

**BLUF:** The nightly script, workflow, `.gitignore` carve-out, 10 new tests, and the RFC-4 risk-evidence pack are done. The api suite passes (388 passed, 3 deselected). The `/categories` contract test passes 3/3. `cache.py`, `trigger.py`, `history.py`, the adapters and `liqtide-snapshot.yml` are unchanged. Nothing is committed. Three things are still open: the user's review decision, one `workflow_dispatch` run, and a real-network run (this container's egress is blocked).

## What Was Done

| File | Change |
|---|---|
| `api/scripts/snapshot_narrative.py` (new) | Loops over the seed categories and calls sources directly. It never calls `compute_narrative_categories`, so it writes no legacy `coingecko/` series and no trigger state. **pytrends:** reads the adapter's `_fetch_live` result and writes it itself via `write_narrative_point`, so the date check can run before the write. **Reddit:** `fetch_mentions` runs only when both credentials are set; otherwise no row is written and it prints `reddit: unavailable (credentials-not-configured)` (C1). **CoinGecko:** one `fetch_trending`, counted per category via `map_coin_to_narrative_category`, written to `coingecko-narrative/{id}`. It only archives a live `ok` result dated today, never a stale cached snapshot. **Exchange:** `exchange_attention.run_daily()`. **C2 (first observation wins):** each key is checked before writing and skipped if today's row already exists; pytrends also skips when its own `as_of` date exists, which protects `backfilled` rows. **Failures:** handled per source, with one summary line each. **Exit codes:** 0 = ran; 2 = every source unavailable; 1 = crash. **CLI:** `--dry-run` runs against a temporary copy of `cache/narrative/` and restores `CACHE_ROOT`; `--verify-only` prints row count and latest date per series without fetching. |
| `.github/workflows/narrative-snapshot.yml` (new) | cron `0 23 * * *` + `workflow_dispatch`; `permissions: contents: write`; `concurrency: narrative-snapshot`; `uv run --project api --with pytrends python -m api.scripts.snapshot_narrative`. Exit 1 fails the job; exit 2 raises a warning. Stages only `api/data/cache/narrative/` and commits if there is a diff. Pushes with `git pull --rebase` + `git push`, retried 3 times with no force-push. Zero `secrets.` references. |
| `.gitignore` | Adds `!api/data/cache/narrative/` after the liqtide negation, then re-ignores `api/data/cache/narrative/coingecko_trending.parquet` (C3), with a comment. |
| `api/tests/scripts/test_snapshot_narrative.py` (new, 10 tests) | See the gates table below. |
| `harness/rfc-004/*.json` (new, 5 files) | Risk pack. `review-decision.json` = PENDING. RFC-3's `harness/*.json` files are untouched. |

`.gitignore` was checked with `git check-ignore -v --no-index`:
- **Tracked:** `narrative/{pytrends,reddit,coingecko-narrative,exchange}/*.parquet`, `narrative/exchange/markets/*.json`, `liqtide/*`.
- **Ignored:** `narrative/coingecko_trending.parquet` (line 25) and `ohlcv/*` (line 18).

## Test Gate Outcomes

| Gate | Result |
|---|---|
| `uv run --project api pytest api/tests/scripts/test_snapshot_narrative.py -q` | **10 passed**: full run writes 4×4; curated counts ai=2, l2s=1, others 0; no legacy `coingecko/` and no non-seed file; same-day re-run skips 16/16, keeps the first values and doesn't re-call pytrends or Reddit; backfilled date preserved; Reddit unset gives no row, the reason line and exit 0; pytrends raising + Hyperliquid down leaves the others written, exit 0; stale trending not archived; all sources down gives exit 2; dry-run leaves the file tree identical and restores `CACHE_ROOT`; `--verify-only` makes no fetch. |
| `uv run --project api pytest api/ -q` | **388 passed, 3 deselected** (was 378 + 10 new). |
| `/categories` contract test | **3/3 passed**. |
| Workflow YAML `yaml.safe_load` | Parses. The first draft failed (an unquoted `: ` inside a `run:` value); I fixed it with a block scalar. `actionlint` isn't installed, so it didn't run. |
| Local real `--dry-run` | Exit 2 because egress is blocked: all 4 sources degraded, each with its own line, Reddit showing `credentials-not-configured`. The real cache was untouched. |
| `git diff` of cache.py / trigger.py / history.py / liqtide-snapshot.yml | Empty. |

## Plan Deviations
- **pytrends is called via the adapter's private `_fetch_live`, not `fetch_trend`.** `fetch_trend` writes internally with keep-last, which would break C2's "never overwrite a backfilled date." This stays within the blast radius; no adapter change.
- **Concurrency group is `narrative-snapshot`, not shared with liqtide** (liqtide left untouched as instructed). Push races are handled by the 30-minute offset plus the rebase-retry push.
- **Runbook text is now stale, for UPDATE PROCESS to fix in plan §19** (the plan file was not edited):
  - It says "Reddit rows read `credentials-not-configured`". Under C1 no row is written; the reason appears only in the job log (and in `/history` as absence).
  - Adding the two GitHub secrets is not enough on its own. The workflow deliberately maps no secrets into the step's `env`, so enabling Reddit later also needs a two-line `env:` edit to the workflow. That edit is a user decision.

## What Was Skipped or Deferred / Test Infra Gaps Found
- The one-time `workflow_dispatch` run and the user review of the workflow (plan done criterion; `review-decision.json` is PENDING).
- A real-network run (container egress is blocked). Run on the user's PC: `uv run --project api --with pytrends python -m api.scripts.snapshot_narrative` twice, then `--verify-only`.
- `actionlint` is not available.
- **Existing RFC-2 behaviour, noted but not changed:** when the Hyperliquid snapshot is unavailable, `run_daily` still appends unavailable rows for that date, so a later successful re-run on the same day stays "unavailable" (append-only). My script counts this as failed, not written.
- **Legacy `coingecko/{id}` would also be tracked by the negation** if it ever existed in a checkout. CI never creates it (a fresh checkout plus this script doesn't write it). A local user commit could include it; this was not re-ignored because the C3 decision named only the trending file.

## Closeout Packet
- Plan: `process/features/narrative-mindshare/active/narrative-dashboard_24-09-26/narrative-dashboard_PLAN_24-09-26.md`
- Classification: **Keep in active/testing.** The E3 pack exists, but its review decision is pending and `mustStopBeforeFinalize` is true.
- Verified: all automated gates above. Not verified: live providers, the GitHub Actions run itself.
- Next: orchestrator EVL (vc-tester) → user reviews the workflow, runs `workflow_dispatch` once, and fills in `harness/rfc-004/review-decision.json` → RFC-6 once RFC-5 lands.

## Forward Preview
- **Test Infra Found:** stub `pytrends_adapter._fetch_live`, `reddit_adapter.fetch_mentions`, `coingecko_adapter.fetch_trending` and `hyperliquid_narrative_adapter.fetch_daily_market_snapshot` under `isolated_cache`; `sn.run_snapshot()` returns per-source summaries.
- **Blast Radius Changes:** new `.github/workflows/narrative-snapshot.yml`; `api/data/cache/narrative/**` becomes git-tracked (except the trending snapshot).
- **Commands to Stay Green:** `uv run --project api pytest api/ -q`; `uv run --project api python -m api.scripts.snapshot_narrative --verify-only`.
- **Dependency Changes:** none (pytrends is added per run via `--with`).

Follow-up stubs created: none. CONTEXT_PARTIAL: none.

TL;DR: RFC-4 is built and green (10 new tests, api 388 passed, contract 3/3), with the core modules unchanged and nothing committed. It is waiting on the user's workflow review, one manual dispatch, and the risk-pack decision.
