---
name: report:pair-screener-rfc-003-stage0
description: "RFC-003 Stage 0 — API field lists, on-disk results/provenance/spreads layout, staleness comparison + real-cache timing, read-path timing gate"
date: 27-09-26
metadata:
  node_type: memory
  type: report
  feature: cointegration-screener
  phase: RFC-003-stage-0
phase: rfc-003-stage-0
status: COMPLETE
plan: process/features/cointegration-screener/active/pair-screener_25-09-26/pair-screener_PLAN_25-09-26.md
---

# RFC-003 Stage 0 — Persistence + read-only API (findings, STOP for approval)

**Bottom line:** the plan's design holds, with one real problem found. The staleness check,
built the obvious way with the existing `cache.py` helpers, takes **2.6–3.8 s for 18 coins**.
That alone would break the p95 < 3 s target. Reading the same two facts from each Parquet file's
footer takes **45 ms** and gives identical answers for all 18 coins. I recommend the footer read.
Per-pair spread files are recommended over a list column: **8 ms vs 132 ms** per detail read.
The estimated whole read path is about 120–170 ms.

No repo code was changed. No writes went to the real cache (all measurement writes went to a temp
dir). No commits. `git status` is clean apart from this report.

## 1. Precedent confirmed

- `api/main.py`: `GZipMiddleware(minimum_size=1000)` is app-wide (line 51). Routers are registered
  at lines 53–56. RFC-003 adds one line, `app.include_router(pairs.router)`, after `narrative`.
- `api/models/regime.py`: typed `Literal[...]` status enums, `BaseModel`, ISO-date strings, and no
  null/NaN/0 stand-ins in point lists. Pairs will follow the same style (`Literal`, not `Enum`).
- `api/routers/regime.py`: `APIRouter(prefix=...)`, `response_model=...`, and
  `HTTPException(status_code=422, detail=...)` for bad input. No auth and no CORS change.
- `api/tests/routers/test_regime_components.py` uses `fastapi.testclient.TestClient` against the
  real app. The timing gate will copy that pattern (E8).
- `api/analytics/regime/components_response.py`: the analytics module builds the response and
  the router stays thin. `pairs_response.py` will do the same.
- `pairs_universe.load_universe()` raises `UniverseFileError` for a bad file.
  `enumerate_pairs()` returns `itertools.combinations` order. That order is the canonical
  `(coin_a, coin_b)` for storage.

## 2. Exact pydantic field lists (for approval)

### Shared sub-models

| Model | Fields |
|---|---|
| `PairStatus` | `Literal["ok", "insufficient_overlap", "coin_unavailable"]` |
| `ComputationStatus` | `Literal["fresh", "stale", "results_unavailable"]` |
| `HalfLifeState` | `Literal["computed", "not_mean_reverting"]` |
| `HalfLifeOut` | `state: HalfLifeState`, `days: float \| None` (None iff `not_mean_reverting`) |
| `JohansenOut` | `trace_stat: float`, `crit_value_95: float`, `rank_at_least_1: bool` |
| `EGDirectionOut` (detail only) | `dependent: str`, `independent: str`, `hedge_ratio: float`, `intercept: float`, `t_stat: float`, `p_value: float` |
| `SpreadPoint` | `date: str` (ISO), `spread: float`, `z_score: float` |

### `PairSummary` (one table row; matches §11 plus `johansen_reason`)

| Field | Type | Rule |
|---|---|---|
| `coin_a`, `coin_b` | `str` | canonical universe order |
| `status` | `PairStatus` | ADR-7 |
| `reason` | `str \| None` | set iff `status != "ok"` |
| `overlap_days` | `int \| None` | None only for `coin_unavailable` |
| `sample_start`, `sample_end` | `str \| None` (ISO) | None only for `coin_unavailable` |
| `eg_p_raw` | `float \| None` | min-p direction's p (D3); None iff not `ok` |
| `eg_p_bh` | `float \| None` | `stats.bh_adjust` output; None iff not `ok` |
| `eg_direction` | `str \| None` | `"{dependent}~{independent}"` of the lower-p direction, e.g. `"BTC~ETH"` |
| `eg_p_other_direction` | `float \| None` | the other direction's p |
| `johansen` | `JohansenOut \| None` | None if not `ok`, OR if refused (D2) |
| `johansen_reason` | `str \| None` | set iff `ok` and Johansen refused. Text is stats.py's own: `"Johansen numerically unstable: max\|imag(eig)\|=<x> > 1e-09"`. Pair stays `ok` (user decision). |
| `half_life` | `HalfLifeOut \| None` | None iff not `ok` |
| `z_score` | `float \| None` | latest spread z (ADR-4); None iff not `ok` |

### `PairsResponse` (`GET /api/pairs`)

| Field | Type | Rule |
|---|---|---|
| `generated_utc` | `str` | time of this response |
| `computed_at` | `str \| None` | **new vs §11:** `provenance.computed_at`; None iff `results_unavailable` |
| `computation_status` | `ComputationStatus` | see §4 |
| `stale_reason` | `str \| None` | see §4 and decision D-3 |
| `universe_size` | `int` | current `pairs_universe.json` length |
| `pair_count` | `int` | `len(pairs)` |
| `min_overlap_days` | `int` | `stats.MIN_OVERLAP_DAYS` |
| `diagnostic_scope` | `Literal["whole_history_in_sample"]` | from `stats.DIAGNOSTIC_SCOPE` |
| `diagnostic_disclosure` | `str` | fixed text, see below |
| `pairs` | `list[PairSummary]` | `[]` iff `results_unavailable`; sorted by `eg_p_bh` ascending, non-`ok` rows last |

**Proposed whole-history disclosure text** (one server-side constant, so the UI never re-words it):

> "These statistics use each pair's entire shared price history at once (in-sample). They
> describe how the two coins moved together in the past. They are not a trading signal, and they
> do not show whether the relationship still holds today."

### `PairDetailResponse` (`GET /api/pairs/{a}/{b}`), proposed wrapper shape

| Field | Type | Rule |
|---|---|---|
| `generated_utc`, `computed_at`, `computation_status`, `stale_reason`, `diagnostic_scope`, `diagnostic_disclosure` | as above | same values as the table response |
| `pair` | `PairDetail \| None` | None when `results_unavailable`, or when `stale` because the pair involves a coin added since the last compute |

`PairDetail` = every `PairSummary` field, plus:

| Field | Type | Rule |
|---|---|---|
| `eg_a_on_b`, `eg_b_on_a` | `EGDirectionOut \| None` | both directions: hedge ratio, intercept, t-stat, p. None iff not `ok` |
| `spread_direction` | `str \| None` | same as `eg_direction`, naming which spread is plotted |
| `half_life_ar1_beta` | `float \| None` | the AR(1) β behind the half-life |
| `spread` | `list[SpreadPoint]` | `[]` iff not `ok`. Per-point `z_score` = (spread − full-sample mean) / std(ddof=1), per ADR-4 |

### Path-param contract (confirmed, unchanged from §11)

Evaluated in this order:

1. Uppercase both.
2. If `a == b`, return **422** `"a and b must be different coins"`.
3. If either is not in the universe, return **404** `"<TICKER> is not in the pair-screener universe"`.
4. Lookup accepts either order (`ETH/BTC` finds the stored `BTC,ETH` row). The response keeps the
   stored canonical order.

A path like `/api/pairs/a/b/c` is already rejected by the router (not a malformed-ticker case).
"Malformed" 422 is for tickers that do not match `^[A-Z0-9]{1,15}$` after uppercasing.

## 3. On-disk layout (recommended: per-pair spread files)

All paths come from three additive `cache.py` helpers built from `CACHE_ROOT` at call time (E6),
added in Stage 1, not now:

```
CACHE_ROOT/pairs/
  results.parquet              # one row per pair, flat columns (below), ~13 KB for 153 pairs
  provenance.json              # schema per ADR-8 Amendment, unchanged
  spreads/{A}_{B}.parquet      # columns date(date32), spread(float64), z_score(float64); ~56 KB each; ok pairs only
```

- `pairs_results_path()`, `pairs_provenance_path()`, `pairs_spread_path(a, b)`. The write site
  calls `path.parent.mkdir(parents=True, exist_ok=True)` (E9), because `bootstrap_cache_dirs()`
  has no `"pairs"` entry. That function stays untouched, so the change remains additive-only.
- `results.parquet` columns (flattened, since nested JSON is avoided in Parquet): all `PairSummary`
  scalars, plus `johansen_trace_stat`, `johansen_crit_95`, `johansen_rank_at_least_1`,
  `half_life_state`, `half_life_days`, `half_life_ar1_beta`, and both directions'
  `eg_{ab,ba}_{hedge_ratio,intercept,t_stat,p_value}`. The detail endpoint then needs exactly one
  extra file (the spread).

**Measured on a realistic synthetic set** (153 pairs, spread lengths from the real bar counts), in
a temp dir:

| Layout | Size | Detail read (median / max) |
|---|---|---|
| **Per-pair `spreads/{A}_{B}.parquet`** | 6.5 MB total, ~56 KB each | **7.9 / 9.5 ms** |
| List-column inside `results.parquet` | 4.8 MB single file | 131.7 / 169.9 ms (whole file read every detail call, and every table call too unless column-pruned) |

**Write order and atomicity** (so a crashed run never looks `fresh`):

1. Clear and rewrite `spreads/`, so spreads for removed pairs do not linger.
2. Write `results.parquet`.
3. Write `provenance.json` **last**.

Each file is written to `*.tmp` and then `os.replace`d. If provenance is missing, the status is
`results_unavailable`.

## 4. Staleness comparison (5 checks) and real-cache timing

### The checks, run in this order on every request

All failing reasons are collected and joined with `"; "`:

| # | Check | Stale when | Example reason text |
|---|---|---|---|
| 1 | universe | `set(current) != set(provenance.universe)` | `universe changed: added HYPE; removed OP` |
| 2 | last bar date | current max date for any coin `> per_coin_last_bar_date` | `ETH has newer bars (cache 2026-09-27, results 2026-09-25)` |
| 3 | bar count | current count `!= per_coin_bar_count` (see D-4) | `SOL bar count changed 2203 → 2210` |
| 4 | statsmodels version | `statsmodels.__version__ != provenance.statsmodels_version` | `computed with statsmodels 0.15.0; installed 0.16.1` |
| 5 | EG autolag | `stats.EG_AUTOLAG != provenance.eg_autolag` | `computed with eg_autolag=aic; current None` |

Every stale reason ends with `" — run compute_pairs.py to refresh"`.

A coin whose cache file vanished counts as changed (bar count 0, date None). That is caught by
checks 2 and 3, never skipped.

### Timing: how to read per-coin last-bar date and bar count (real cache, 18 coins, 9 warm runs)

| Method | Median | Max | Notes |
|---|---|---|---|
| A. existing `ohlcv_last_refresh` + `ohlcv_bar_count` per coin (36 DuckDB queries) | **2644 ms** | 3138 ms (a second run took 3790 ms) | each call opens a fresh DuckDB connection (~47 ms each) |
| B. one DuckDB `read_parquet([...18 files], filename=true) GROUP BY filename` | 77 ms | 97 ms | needs a new query, and would be a new cache.py function |
| C. pyarrow footer row count only | 24 ms | 33 ms | no date |
| **J. pyarrow footer: `num_rows` + `timestamp` column max statistic** | **45 ms** | 103 ms | **matches helper A exactly for 18/18 coins**; every file is 1 row group with min/max stats present |

Real cache values now: every coin's last bar is 2026-09-25. Bar counts: BTC/ETH/DOGE/LTC/ATOM 2229,
LINK 2226, SOL 2203, XRP 2196, AVAX 2194, BCH 2183, DOT 2109, ADA 2069, NEAR 2051, OP 1578,
APT 1438, ARB 1283, SUI 1242, HYPE 660.

**Recommendation (D-5):** use method J.

- Implement it inside `pairs_response.py` via `cache.ohlcv_path()` (which is `CACHE_ROOT`-resolved)
  plus `pyarrow.parquet.ParquetFile(...).metadata`, so `cache.py` gets no extra function.
- If a file has no min/max statistics, fall back to that coin's existing helpers. That path is slow
  but correct, never silent.
- `write_ohlcv` uses pandas → pyarrow, which writes statistics by default, so the fallback should
  never fire in practice.

## 5. Read-path timing target and how it is measured

- **Target:** plan p95 < 3 s (hard gate). Expected actual ≈ 120–170 ms:

  | Step | Time |
  |---|---|
  | summary parquet read | 11 ms |
  | footer staleness | 45 ms |
  | provenance JSON | ~0 |
  | pydantic + gzip | ~tens of ms |

- **Measured estimate:** summary read + DuckDB-union staleness: median 121 ms, max 171 ms. With
  footer staleness it should be lower. With method A it was median 2199 ms, max **6095 ms**, which
  would fail the gate.
- **Gate (E8, Fully-Automated):** a new test in `api/tests/routers/test_pairs.py`.
  1. Under `isolated_cache`, seed 18 coins of OHLCV plus a realistic `results.parquet`,
     `provenance.json` and 153 spread files.
  2. Using `TestClient`, send 1 warm-up request, then 20 timed `GET /api/pairs` requests and 20
     timed `GET /api/pairs/BTC/ETH` requests.
  3. Assert p95 < 3.0 s for each.
  4. Print the median and p95 so the phase report records the real numbers.

  I also recommend a soft internal budget of p95 < 500 ms, reported but not asserted, to catch a
  regression to method A early.
- **Manual evidence:** after the real `compute_pairs.py` run, capture
  `curl -w "%{time_total}"` against the running API on the real cache.

## 6. Where `compute_pairs.py` fits (confirmed)

- It is its own script, `api/scripts/compute_pairs.py`, not a step inside
  `backfill_pairs_universe.py`, as the ADR-8 Amendment chose.
- No CLI args, idempotent, and it reads only `cache.read_ohlcv` (E5).
- It prints the elapsed time and per-status counts.
- Ops order: run backfill first, then `compute_pairs.py`.
- Expected runtime is ~46 s (`EG_AUTOLAG="aic"`). This is informational, not gated.
- The router never imports `stats.compute_pair_stats` or `bh_adjust`, only constants
  (`EG_AUTOLAG`, `MIN_OVERLAP_DAYS`, `DIAGNOSTIC_SCOPE`).

## 7. Other Stage 0 items

- **Universe file unreadable at request time** (`UniverseFileError`): return **500** with the
  loader's message. Never an empty 200. This is a config error, not a data state (D-6).
- **Last-known-good rows when the universe changed** (D-2):
  - Serve only rows whose both coins are still in the current universe.
  - Pairs with newly added coins are absent, and `stale_reason` names the added coin.
  - `pair_count` is then less than C(n,2). That is honest and flagged.
  - This satisfies "never serve rows for a coin list that does not match the current universe"
    while still serving last-known-good rows.
- **Corrupt or unreadable `results.parquet`/`provenance.json`:** status `results_unavailable`,
  with the parse error in the reason field (D-3). It never produces a stack trace or a 500.
- **statsmodels installed:** 0.15.0, which matches the provenance example.
- **Protected files:** none touched. `cache.py` is unchanged in Stage 0.

## Decisions that need your approval

| # | Decision | Recommendation |
|---|---|---|
| D-1 | Spread storage layout | Per-pair `spreads/{A}_{B}.parquet` (8 ms vs 132 ms) |
| D-2 | Rows served when the universe changed | Keep only rows with both coins in the current universe; flag the added/removed coins in `stale_reason` |
| D-3 | Reason text for `results_unavailable` | Reuse `stale_reason` for any non-`fresh` state (e.g. "no results yet — run compute_pairs.py"). This changes §11's "null unless stale" to "null iff fresh". The alternative is to leave it null and let the UI use fixed text. |
| D-4 | Bar-count check | Stale on **any change** (≠), not only an increase. This catches a shrunk or deleted cache. The plan says "increased". |
| D-5 | Staleness read method | Parquet footer stats inside `pairs_response.py` (45 ms). Not the existing helpers (2.6–3.8 s, which would break the gate). |
| D-6 | Bad universe file at request time | 500 with the loader's message |
| D-7 | Additive fields beyond §11 | Response `computed_at`; `diagnostic_scope` + `diagnostic_disclosure` (with the text above); `johansen_reason`; detail wrapper `{..., pair: PairDetail \| null}`; `eg_a_on_b`/`eg_b_on_a` objects; `spread_direction`; `half_life_ar1_beta` |
| D-8 | Timing gate | TestClient, 20 requests per endpoint, hard p95 < 3 s, soft 500 ms reported |

## Plan Deviations

None in Stage 0 (no code). D-3, D-4 and D-7 would amend the plan text slightly if approved.

## Forward Preview

- **Test infra:** `isolated_cache` plus `TestClient`; need a realistic-size seeder helper for the
  timing test.
- **Blast radius:** as planned. New: `api/models/pairs.py`,
  `api/analytics/cointegration/pairs_response.py`, `api/scripts/compute_pairs.py`,
  `api/routers/pairs.py`, 2 test files. Additive: `cache.py` (3 helpers) and `main.py` (1 line).
- **Commands to stay green:**
  `uv run --project api pytest api/tests/routers/test_pairs.py api/tests/scripts/test_compute_pairs.py -q`,
  then the full `pytest api/ -q`.
- **Dependency changes:** none. pyarrow and statsmodels are already installed.

TL;DR: the design holds. Use Parquet footers for the staleness check (45 ms, not 2.6 s) and
per-pair spread files (8 ms detail reads). Eight small decisions (D-1..D-8) need your OK before
Stage 1.
