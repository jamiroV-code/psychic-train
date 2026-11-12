---
name: report:narrative-dashboard-rfc-002
description: "RFC-2 execute report — Hyperliquid exchange-attention adapter + analytics, new cache helpers, pytrends daily backfill script; all gates green, not committed"
date: 24-09-26
metadata:
  node_type: memory
  type: report
  feature: narrative-mindshare
  phase: RFC-2
phase: rfc-002
status: COMPLETE_WITH_GAPS
feature: narrative-mindshare
plan: process/features/narrative-mindshare/active/narrative-dashboard_24-09-26/narrative-dashboard_PLAN_24-09-26.md
---

# RFC-2 — Exchange attention adapter + pytrends backfill

**BLUF:** RFC-2 is code-complete and every automated gate is green:
- 29 new RFC-2 tests pass. One integration test is deselected by default.
- Full api suite: **336 passed, 3 deselected**.
- web vitest: **75 passed (12 files)**.
- RFC-1 contract test: **3 passed**.

Nothing is committed. Two things are still open:
- **Real-data checks:** no live Hyperliquid call has been made (the container proxy returns 403). pytrends has never run for real (it isn't installed). Both are steps for the user's PC.
- **Hyperliquid terms:** unchecked. `redistributable` stays `False` until the user confirms them.

## What Was Done

| File | Change |
|---|---|
| `api/data/cache.py` | Adds exchange helpers (D2). `write/read_exchange_market_snapshot` and `list_exchange_market_snapshot_dates` handle `cache/narrative/exchange/markets/{date}.json`, which is append-only and never overwritten. `write/read_exchange_series` handle `cache/narrative/exchange/{category}.parquet`; it is append-only and a date that already exists is never rewritten. Nulls are stored as nulls. Existing functions are untouched. |
| `api/data/hyperliquid_narrative_adapter.py` (new) | `fetch_daily_market_snapshot(exchange=None, now=None)` calls `_exchange().fetch_tickers(params={"type":"swap"})`. It keeps only active perps, excluding HIP-3 and delisted markets. It never raises. Failures return `unavailable` with one of these reasons: `exchange-unavailable`, `fetch-failed: <Exc>`, `parse-failed`, `empty-market-list`. Dating uses the UTC fetch date. `HYPERLIQUID_REDISTRIBUTABLE = False` is a single constant (D4). |
| `api/analytics/narrative/exchange_attention.py` (new) | Symbol resolution: `base == SYM`, else `baseName == "k"+SYM`. A coin with no market gets a per-coin `no-hyperliquid-market` entry. Volume share (D1): divided by all active non-HIP-3 perps, with an `unmapped` bucket that is part of the total. New-listing diff (D3) records `baseline_date`. Day 1 (E2): `null` / `unavailable` / `no-baseline-yet`. `run_daily()` reads `load_category_map()` on every run. Display-only: nothing in trigger.py, screener_board.py or routers/narrative.py imports it, and a test enforces that. |
| `api/scripts/backfill_pytrends_history.py` (new) | Backfill (D5): one daily window of 269 days per seed category. `isPartial` rows are dropped. A frame that isn't daily is rejected, never stored as daily. Rows are written with `source_status="backfilled"`. The existing series is read before writing, and any date whose status isn't `backfilled` is skipped. `--dry-run` is supported. pytrends is **not** added as a dependency. |
| Tests (new) | `tests/data/test_hyperliquid_narrative_adapter.py` (8 + 1 integration). `tests/analytics/test_exchange_attention.py` (13). `tests/scripts/test_backfill_pytrends_history.py` (9). All use `isolated_cache` and fakes; there are no network calls. |

## Plan-text conflicts, resolved here (UPDATE PROCESS should edit the plan)

1. **§1.5 said "no new cache surface" and §12b defined a separate exchange schema.** Resolved by D2: new `cache.py` helpers, and `write_narrative_point` is not used for exchange data.
2. **The §12b exchange columns grew.** They are now `date, volume_share, volume_status, volume_reason, new_listing_count, listing_status, listing_reason, baseline_date`. §12b listed `date, volume_share, new_listing_count, status`. Volume and listings have separate statuses because day 1 has a valid share but no listing baseline. The reason columns and `baseline_date` are required by the "never silently wrong" rule and by D3. §12b also needs the market-snapshot JSON path added.
3. **ADR-6's "all tracked coins" denominator** is replaced by D1: all active non-HIP-3 perps plus an `unmapped` bucket. The shares sum to 1.
4. **ADR-6's `redistributable=true`** is replaced by D4: `False`. Flipping it is a one-line change to `HYPERLIQUID_REDISTRIBUTABLE` in `api/data/hyperliquid_narrative_adapter.py` once the user has checked Hyperliquid's terms.
5. **ADR-6's VALIDATE note (ccxt shape "confirmed")** missed that ccxt upper-cases the `k` base (`KPEPE`). The new resolver handles this. `ccxt_adapter.resolve_market_symbol` was not changed, which is outside RFC-2's scope.
6. **The pytrends series is keyed by keyword, not category id (new finding).** The forward writer (`pytrends_adapter.fetch_trend`) stores under `("pytrends", "<keyword>")`, for example `pytrends/AI crypto.parquet`, not `pytrends/ai.parquet`. The backfill writes under the same keyword key (the seed's `keywords[0]`, which is what trigger.py passes). That is the only way the check that protects archived dates can see those dates. **RFC-3 must map keyword to category** when reading pytrends history. The same applies to reddit, which is also keyword-keyed. The plan text and the RFC-1 verification query assumed `pytrends/ai.parquet`.

## Plan Deviations

- Item 2 above: more storage columns than §12b listed. This stays within the blast radius.
- Item 6 above: the backfill series key is the keyword, to match the forward writer. This stays within the blast radius.
- There are no hard-stop-class deviations: no schema migration, auth, API surface or workflow was touched.

## Test Gate Outcomes

| Gate | Result |
|---|---|
| RFC-2 tests (3 files) | 29 passed, 1 deselected (integration) |
| `uv run --project api pytest api/ -q` | **336 passed, 3 deselected** (60.6s) |
| `pnpm --filter web test` | **75 passed, 12 files** |
| RFC-1 contract `test_narrative_categories_contract.py` | 3 passed |
| Forced failure → `unavailable`, never a share of 0 | Covered: timeout, network error, generic error, zero total volume |
| E2 day 1 versus a real zero | Covered, and the two are distinguishable |
| UTC 23:59:59 / 00:00:00 boundary | Covered, both in the adapter and in a `run_daily` round-trip through the real cache |
| Opt-in `-m integration -k hyperliquid` | Not run (proxy returns 403). Deferred to the user's PC |

`git status` shows no files written under `api/data/cache/` (the real cache is untouched).

## What Was Skipped or Deferred / Test Infra Gaps Found

- **Live Hyperliquid check (on the user's PC):**
  `uv run --project api pytest api/ -m integration -k hyperliquid -s`
  This prints the real `k` names. Then check which map coins return `no-hyperliquid-market`.
- **Real backfill (on the user's PC):**
  `uv run --project api --with pytrends python api/scripts/backfill_pytrends_history.py --dry-run`, then run it again without `--dry-run`.
  Verify with this DuckDB query:
  `select source_status, min(date), max(date), count(*) from 'api/data/cache/narrative/pytrends/*.parquet' group by 1`
- **Exchange data:** there is nothing to query for the plan's exchange DuckDB check until the RFC-4 nightly job runs `exchange_attention.run_daily()`.
- **Scale-mismatch caveat for RFC-5:** backfilled values come from a 269-day daily window. Forward values are the last point of a `now 7-d` window. Each Google request is scaled 0–100 on its own, so the two are **not on the same scale**. `DataQualityCaveat` must say so.
- **Other RFC-5 notes:** the exchange volume share is a rolling 24-hour figure dated by the UTC fetch day. Re-running the same day is append-only, so the first observation of the day stands.

## Closeout Packet

- Plan: `process/features/narrative-mindshare/active/narrative-dashboard_24-09-26/narrative-dashboard_PLAN_24-09-26.md`
- Classification: **Keep in active/testing.** The program continues to RFC-3, and the live checks above are user-PC steps.
- Verified: all automated gates listed above. Not verified: real Hyperliquid payload, real pytrends output, Hyperliquid terms.
- Remaining: UPDATE PROCESS applies conflict fixes 1–6 to the plan text and adds Hyperliquid to `data-sources/all-data-sources.md` (redistributable false, pending terms).
- Next: EVL confirmation run (vc-tester), then RFC-3.

## Forward Preview

- **Test Infra Found:** `isolated_cache` fixture; `integration` marker; fake `TrendReq` / fake exchange pattern.
- **Blast Radius Changes:** `cache.py` gains the exchange helpers. There are three new modules. `exchange_attention.run_daily()` is the entry point RFC-4's nightly job should call. `CategoryAttention.as_row()` defines the stored row.
- **Commands to Stay Green:** `uv run --project api pytest api/ -q`; `pnpm --filter web test`.
- **Dependency Changes:** none. pytrends remains optional (`--with pytrends`).

Follow-up stubs created: none. CONTEXT_PARTIAL: none.

TL;DR: RFC-2 is built and green (336 api, 75 web, contract test 3/3). Live Hyperliquid and pytrends runs, and the terms check, are user-PC steps. RFC-3 must read pytrends and reddit history by keyword, not by category id.
