---
name: report:pair-screener-rfc-003
description: "RFC-003 EXECUTE report — compute_pairs.py, persisted results cache + provenance, 5-check staleness, GET /api/pairs + /api/pairs/{a}/{b}, real run + timing"
date: 27-09-26
metadata:
  node_type: memory
  type: report
  feature: cointegration-screener
  phase: RFC-003
phase: rfc-003
status: COMPLETE
feature: cointegration-screener
plan: process/features/cointegration-screener/active/pair-screener_25-09-26/pair-screener_PLAN_25-09-26.md
---

# RFC-003 — Persistence + read-only API (EXECUTE report)

**Bottom line:** RFC-003 is code-complete and every gate is green.

- **Tests:** 34 new tests pass. The full suite has **475 passed / 3 deselected** (441 + 34).
- **Real compute:** `compute_pairs.py` ran against the real cache in **55.8 s**. All 153 pairs are
  `ok`.
- **Significance:** **0 pairs are significant after BH at 5%.** 21 pairs have raw p < 0.05. The
  best pair, DOGE~BCH, has raw p 0.00057 and BH p 0.087.
- **Real-cache read timing:** table p95 **135 ms**; detail p95 **232 ms**. Both are far under the
  3 s gate and under the 500 ms soft budget.

Nothing is committed.

## What Was Done

| File | Change |
|---|---|
| `api/data/cache.py` | **Additive:** `ohlcv_footer_stats`, `ohlcv_footer_stats_many` (D-5, user-revised); `pairs_results_path`, `pairs_provenance_path`, `pairs_spreads_dir`, `pairs_spread_path` (E6). Plus a `"pairs"` entry in `bootstrap_cache_dirs` (E9, user-approved). Other functions are unchanged. |
| `api/models/pairs.py` | new: the Stage 0 field lists exactly (D-7), plus the disclosure constant |
| `api/analytics/cointegration/pairs_response.py` | new: compute path (`compute_and_persist`) and read path (`read_table`, `read_detail`) |
| `api/scripts/compute_pairs.py` | new: no-args script that prints a summary |
| `api/routers/pairs.py` | new: both endpoints and the path-param contract |
| `api/main.py` | one import name + one `include_router` line |
| `api/tests/pairs_fixtures.py` | new: shared synthetic seeders (small universe; realistic 153-pair cache) |
| `api/tests/data/test_cache_pairs_helpers.py` | new: 5 tests; footer stats **match `ohlcv_bar_count`/`ohlcv_last_refresh`** on fixtures |
| `api/tests/scripts/test_compute_pairs.py` | new: 9 tests (AC-1, AC-5 golden and hand-computed BH, E5 network isolation, E6 isolated paths, universe re-run, Johansen-refused stays `ok`, script output) |
| `api/tests/routers/test_pairs.py` | new: 20 tests (shape, no-NaN, sort, staleness cases a–e, bar-count decrease, D-2, corrupt cache, bad universe 500, detail, 404/422/self-pair precedence/case, timing gate) |

Key behaviours:

- **Compute path:**
  - It reads only `cache.read_ohlcv`.
  - It deletes `provenance.json` first. It then builds spreads in `spreads.tmp/` and swaps them in,
    writes `results.parquet`, and writes provenance **last**, each via a temp file and replace.
  - An interrupted run therefore reads as `results_unavailable`.
  - Spread files from removed pairs are dropped.
- **Read path:**
  - It never calls `compute_pair_stats` or `bh_adjust`. The router tests patch both to raise.
  - Staleness runs 5 checks: universe, newer last bar, bar count changed either direction,
    statsmodels version, and `eg_autolag`.
  - `stale_reason` explains every state that isn't fresh.
  - On a universe change, only surviving pairs are served (D-2).
  - A corrupt cache gives `results_unavailable` with the error text.
  - A bad universe file gives 500 with the loader's message.

## Real Run (real cache in my_project-main)

`uv run --project api python api/scripts/compute_pairs.py`

| Measure | Value |
|---|---|
| Runtime (script-reported) | **55.8 s** (wall 65 s incl. `uv` start). The RFC-002 estimate was ~46 s. |
| ok / insufficient_overlap / coin_unavailable | **153 / 0 / 0** |
| not_mean_reverting (within ok) | **0** |
| Johansen refused (within ok) | **0** |
| BH-adjusted EG p < 0.05 | **0** (raw p < 0.05: 21; BH < 0.10: 1, DOGE~BCH 0.087) |
| Johansen rank ≥ 1 at 95% | 34 of 153 |
| Spread files written | 153 |

Five lowest raw p-values:

| Pair | Raw p | BH p | Half-life | z-score |
|---|---|---|---|---|
| DOGE~BCH | 0.00057 | 0.087 | 114 d | −0.12 |
| ETH~BCH | 0.0017 | 0.128 | 95 d | 0.44 |
| ETH~LINK | 0.0044 | 0.128 | 140 d | 0.44 |
| SOL~DOT | 0.0044 | 0.128 | 134 d | 0.39 |
| DOGE~DOT | 0.0045 | 0.128 | 61 d | 0.12 |

BTC/ETH detail, spot check:

- Direction `ETH~BTC`, raw p 0.257, BH 0.723.
- Johansen trace 18.31 > 15.49, so rank ≥ 1. EG and Johansen disagree, and both are shown.
- Half-life 162 d, z −0.49, 2229 spread points.
- `eth/btc` in lowercase and reversed order resolves to the same row.

`provenance.json` (real):

```json
{"computed_at": "2026-09-27T17:05:13Z",
 "universe": ["BTC","ETH","SOL","HYPE","XRP","DOGE","ADA","AVAX","LINK","LTC","BCH","DOT","SUI","NEAR","APT","ARB","OP","ATOM"],
 "per_coin_last_bar_date": {"<all 18>": "2026-09-25"},
 "per_coin_bar_count": {"BTC":2229,"ETH":2229,"SOL":2203,"HYPE":660,"XRP":2196,"DOGE":2229,"ADA":2069,"AVAX":2194,"LINK":2226,"LTC":2229,"BCH":2183,"DOT":2109,"SUI":1242,"NEAR":2051,"APT":1438,"ARB":1283,"OP":1578,"ATOM":2229},
 "statsmodels_version": "0.15.0", "eg_autolag": "aic"}
```

## Test Gate Outcomes

| Gate | Result |
|---|---|
| `uv run pytest tests/routers/test_pairs.py tests/scripts/test_compute_pairs.py tests/data/test_cache_pairs_helpers.py -q` | **34 passed** |
| Full `uv run pytest -q` | **475 passed, 3 deselected** (441 + 34) |
| Timing gate (synthetic realistic 153-pair cache, 20 requests each) | table median 98 / p95 141 ms; detail median 177 / p95 253 ms. Both under 500 ms. |
| Timing against **real** results (TestClient, 20 requests each, `computation_status: fresh`) | table median 90 / **p95 135 ms**; detail median 172 / **p95 232 ms**. Both under 500 ms. |

## Plan Deviations

1. **D-5 was implemented as a `cache.py` helper.** This was your revised decision. It is still
   additive: two new functions. `bootstrap_cache_dirs` gained `"pairs"` (E9), with your approval.
2. **An extra `pairs_spreads_dir()` helper** sits alongside the three planned path helpers. The
   compute path needs the directory itself, for the staging swap and to clear stale files. It is
   additive and `CACHE_ROOT`-resolved.
3. **The manual check used TestClient, not curl.** It ran in-process against the real app on the
   real cache, not `curl` against a running uvicorn. It exercises the same code path, including
   gzip negotiation. A live `curl` is still worth a look during your review.
4. **Red-first was not done literally.** The tests were written together with the code and
   passed on the first run. Each test asserts real behaviour, not a stub (for example, the network
   test patches the adapter to raise).
5. **The real runtime is 55.8 s, not ~46 s.** This is informational only and not gated.

## What Was Skipped or Deferred

- RFC-004 (web) was not started, as instructed.
- The plan's "User confirmed working" box is left unticked for your review.

## Test Infra Gaps Found

- The RFC-003 test files take about 90 s. Each compute test re-runs EG with `autolag="aic"` on
  500-bar fixtures. That is acceptable, but it is the slowest new test group; a shared
  module-scoped computed fixture would cut it.

## Closeout Packet

- **Plan:** `process/features/cointegration-screener/active/pair-screener_25-09-26/pair-screener_PLAN_25-09-26.md`.
  RFC-003 is marked CODE-COMPLETE and the checklist is ticked, except the user-confirmation box.
- **Verified:** all automated gates; the real compute run; real-cache read timing.
- **Unverified:** a live-server `curl`; your review of the endpoint shapes and the staleness
  banner text.
- **Classification:** keep in `active/`, awaiting your review. Next: RFC-004 (web).
- **Follow-up stubs:** none.
- **CONTEXT_PARTIAL:** none.

## Forward Preview

### Test Infra Found

- `api/tests/pairs_fixtures.py`:
  - `seed_small_universe` (5 coins: ok / insufficient / unavailable);
  - `seed_realistic_results` (153 pairs, 2229-day spreads, fresh provenance, no 46 s compute);
  - `write_universe` (monkeypatches `pairs_universe.default_universe_path`).
- RFC-005's E2E seeder can reuse these.

### Blast Radius Changes

- Only as planned, plus `pairs_spreads_dir`.
- No edits to `ccxt_adapter.py` or to the screener, watchlist, regime or narrative files.

### Commands to Stay Green

- `cd api && uv run pytest tests/routers/test_pairs.py tests/scripts/test_compute_pairs.py tests/data/test_cache_pairs_helpers.py -q`
- `cd api && uv run pytest -q`

### Dependency Changes

- None.

### Notes for RFC-004

- The API contract is in `api/models/pairs.py`.
- The UI must show:
  - `diagnostic_disclosure` verbatim;
  - `stale_reason` on a stale or `results_unavailable` banner;
  - `johansen_reason` when `johansen` is null on an `ok` row.
- With 0 BH-significant pairs on real data, the table's default view has no "significant" rows.
  The UI should present that honestly.

TL;DR: RFC-003 is done and green (475 passed). The real compute takes 56 s; all 153 pairs are `ok`
and none survive BH at 5%. Reads take about 135–232 ms at p95.
