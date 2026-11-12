---
name: report:narrative-dashboard-rfc-004-stage0
description: "RFC-4 Stage 0 — nightly narrative snapshot workflow + snapshot_narrative.py: proposal, conflicts, decisions"
date: 24-09-26
metadata:
  node_type: memory
  type: report
  feature: narrative-mindshare
  phase: RFC-004-stage0
---

# RFC-4 Stage 0 — Nightly narrative snapshot

**BLUF:** RFC-4 can be built without changing any adapter, `trigger.py`, `/categories` or `web/`. It needs a new script, a new workflow, one `.gitignore` line, and one new test file. There are three points where the plan text doesn't match the code. Each needs a small user decision (see "Decisions needed" below). No source files were edited.

## Findings (code as of today)

| Area | What the code does | Consequence for RFC-4 |
|---|---|---|
| Reddit, creds unset | `_get_access_token` returns None → no fetch. `fetch_mentions` returns `status="unavailable"` with **no reason field** and **writes nothing**. | ADR-8 says the archived point should carry `credentials-not-configured`. The storage schema (`date, raw_value, normalized_value, source_status`) has no reason column. The reason can only live in script output and as a status value. **Conflict C1.** |
| pytrends | `fetch_trend(keyword)` writes `pytrends/{keyword}` with `as_of` = Google's last data date. If pytrends can't be imported, it degrades to unavailable. It is not in `pyproject.toml`. | Nightly job: `uv run --project api --with pytrends`. Rows are keyword-keyed (RFC-3 `history.py` reads `keywords[0]`). |
| `write_narrative_point` | Dedups on date with `keep="last"`, so a same-day re-run **replaces** the row. It has no guard against overwriting `source_status="backfilled"` rows. | There are no duplicates today, but a re-run does overwrite, and a nightly write could replace a backfill row for the same date. **Conflict C2.** |
| CoinGecko | `fetch_trending()` overwrites `narrative/coingecko_trending.parquet`, which `/categories` uses as its fallback. The legacy `coingecko/{id}` count is written only in `trigger.compute_narrative_categories`. | The script calls `fetch_trending()` plus `mapping.load_category_map()` / `map_coin_to_narrative_category()` and writes `coingecko-narrative/{id}` itself. It never touches `coingecko/{id}`. |
| Hyperliquid | `exchange_attention.run_daily()` already fetches once and does append-only writes (market JSON + per-category row; the first observation of the day stands). | Call it as-is. |
| `.gitignore` | `api/data/cache/*` then `!api/data/cache/liqtide/`. | Add `!api/data/cache/narrative/` after the liqtide line. This also tracks `coingecko_trending.parquet` (rewritten daily) and any local legacy `coingecko/` files. **Conflict C3.** |
| Precedent | `liqtide-snapshot.yml`: cron `30 23 * * *`, `contents: write`, exit 1 = fail / 2 = warn, `git add`, then commit-if-diff, then `git push`. It has no concurrency group and no rebase. | Two workflows pushing to `main` about 15 min apart can race if one runs slowly. Add a pull-rebase-retry step. |

## Proposal

### Script: `api/scripts/snapshot_narrative.py`
- **Calls adapters directly, not `compute_narrative_categories`.** For each seed category (`trigger.load_seed_categories()`):
  - pytrends: `fetch_trend(keywords[0])`
  - reddit: `fetch_mentions(keywords[0])`
  - CoinGecko: one `fetch_trending()` per run, then a count per category via the new map, written as `write_narrative_point("coingecko-narrative", id, as_of, count)`
  - Hyperliquid: `exchange_attention.run_daily()` once.
- **Effect on `/categories`:** its behaviour and contract are unchanged. It already reads the same `pytrends/{kw}` and `reddit/{kw}` series, so it simply sees more history. The legacy `coingecko/{id}` series and trigger/confirmation state are never written by the job.
- **Idempotency (first observation wins, like exchange):** before calling pytrends or reddit, the script skips the call if that series already has a row dated today UTC. This also saves rate limit. `coingecko-narrative` gets the same check. Exchange is already append-only. Residual: pytrends `as_of` can be yesterday's Google date, so a skipped check could still let the adapter replace a same-date row. The C2 decision covers this.
- **Per-source isolation:** each source is wrapped in try/except. The script prints one summary line per source, e.g. `reddit: unavailable (credentials-not-configured) 0/N categories written`.
- **Exit codes:** 0 = ran (some sources may have degraded); 2 = every source unavailable (the workflow warns but still commits); 1 = unexpected crash or write failure.
- **CLI:**
  - `--dry-run`: points `cache.CACHE_ROOT` at a temporary directory, so adapter-internal writes can't reach the real cache. It prints what would be written.
  - `--verify-only`: prints the per-source/category row count and the latest date, with no fetch. This is the plan's "DuckDB row counts before/after" query.

### Workflow: `.github/workflows/narrative-snapshot.yml`
- `cron: "0 23 * * *"`: 30 min before liqtide. The plan's `15 23` also works, but 23:00 gives more margin. Plus `workflow_dispatch`.
- `permissions: contents: write`. No `secrets:` references at all.
- `concurrency: { group: cache-snapshot-push, cancel-in-progress: false }`. Adding the same group to liqtide would touch its file, which I'd skip unless you ask.
- Steps: checkout → setup-uv → `uv sync --project api` → `uv run --project api --with pytrends python api/scripts/snapshot_narrative.py` (exit-code handling mirrors liqtide) → `git add api/data/cache/narrative/` → commit if there is a diff: `chore: narrative snapshot YYYY-MM-DD` → `git pull --rebase` then push, with 3 retries.

### Files
- New: `api/scripts/snapshot_narrative.py`, `.github/workflows/narrative-snapshot.yml`, `api/tests/scripts/test_snapshot_narrative.py`, and `harness/{risk-gate,context-snippets,verification,review-decision,adversarial-validation}.json` for RFC-4.
- Edit: `.gitignore` (one line, plus possibly one exclusion line per C3).
- Not touched: adapters, `cache.py`, `trigger.py`, `history.py`, routers, `web/`.

### Tests (`api/tests/scripts/test_snapshot_narrative.py`, all `isolated_cache` with fetchers monkeypatched, no network)
1. `--dry-run` writes nothing under the real or isolated cache root.
2. A same-day re-run gives no duplicate rows, and the first values stand (pytrends, reddit, coingecko-narrative, exchange).
3. Reddit creds unset (`monkeypatch.delenv`): exit 0, the summary shows `credentials-not-configured`, and reddit writes behave per C1.
4. `coingecko-narrative/{id}` is written with the new-map count, and `coingecko/{id}` is **not** created.
5. Partial failure (pytrends raises, Hyperliquid unavailable): the other sources are still written, exit 0, and each failure gets a summary line.
6. All sources down: exit 2.
7. A backfilled pytrends row for the same date is not overwritten (per C2).
8. Regression: the existing `/categories` contract test and `test_history.py` stay green. Gate command: `uv run --project api pytest api/ -q`.

### Risk-evidence pack (E3, `harness/`, RFC-4 entries)
- `risk-gate.json`: class = deploy/runtime (a scheduled job with `contents: write` that pushes to `main`); `mustStopBeforeFinalize: true`.
- `context-snippets.json`: workflow permissions/push lines, the `.gitignore` negation, the script's write calls.
- `verification.json`: pytest results, local dry-run output, a local real run twice with before/after counts, `actionlint` if available.
- `review-decision.json`: filled in by the user after reviewing the workflow file.
- `adversarial-validation.json`: no secrets in the workflow; no `pull_request_target`; the job only stages `api/data/cache/narrative/`; the push token is limited to the repo; no untrusted input reaches shell interpolation.

## Plan-text conflicts
- **C1** ADR-8 "archived point carries `credentials-not-configured`": there is no reason column.
- **C2** The plan's "second run doesn't duplicate": true already, but `keep="last"` overwrites, which differs from the exchange first-wins rule. A nightly write can also clobber backfill rows.
- **C3** The carve-out tracks the trending snapshot file and any legacy files too.
- RFC-4 Stage 4 "Ops Runbook: optional secrets": this is documentation only. The workflow references no secrets (the carried decision).
- The Reddit reason copy in `format-unavailable-reason.ts` is owned by RFC-5; RFC-4 does not touch it.

## Decisions needed
1. **C1: Reddit with creds unset.** (a) *Recommended:* write no reddit row. `history.py` already treats absence as unavailable, and the reason appears in the script summary only. (b) Write a row with `raw_value=NaN, source_status="credentials-not-configured"`. That persists the reason, but it needs a check or change in `history.py` so the row isn't counted as a present point, which is RFC-3 scope.
2. **C2: Same-day overwrite.** (a) *Recommended:* the script pre-checks and skips a source/category already written today, and never writes over a `backfilled` date. (b) Accept `keep="last"` as is.
3. **C3: Tracked files.** (a) *Recommended:* add `api/data/cache/narrative/coingecko_trending.parquet` as an ignore line after the negation, so only archive series are committed. (b) Track everything under `narrative/`.
4. **Cron:** `0 23 * * *` (recommended) or the plan's `15 23 * * *`.

TL;DR: The design is a direct-adapter nightly script, first-write-wins, with per-source degradation and no secrets, plus a workflow like liqtide's with a shared concurrency group and rebase-retry push. It needs four quick decisions (C1–C3 and the cron time) before implementation.
