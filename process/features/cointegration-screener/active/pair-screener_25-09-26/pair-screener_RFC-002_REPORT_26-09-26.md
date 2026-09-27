---
name: report:pair-screener-rfc-002
description: "RFC-002 EXECUTE — pure cointegration stats engine (stats.py) + golden-value tests; live 5-pair sanity print"
date: 26-09-26
metadata:
  node_type: memory
  type: report
  feature: cointegration-screener
  phase: RFC-002
phase: rfc-002-stats-engine
status: COMPLETE
feature: cointegration-screener
plan: process/features/cointegration-screener/active/pair-screener_25-09-26/pair-screener_PLAN_25-09-26.md
---

# RFC-002 — Stats engine (EXECUTE report)

**Bottom line:** `stats.py` is built and pure: it takes price frames and does no I/O. The 20 new
tests pass and the full suite is green (440 passed, 3 deselected; 420 before). One fixture had to
change: fixture (c)'s construction was redesigned, because under D3 the Stage-0 design no longer
reached `not_mean_reverting` (see Deviations). Your review of the golden values and the live print
is still needed. RFC-003 has not been started.

## What Was Done

| File | Change |
|---|---|
| `api/analytics/cointegration/__init__.py` | new package |
| `api/analytics/cointegration/stats.py` | new: dataclasses, named constants, `compute_pair_stats`, `bh_adjust`, primitives |
| `api/tests/analytics/test_cointegration_stats.py` | new: 20 tests |
| `pair-screener_PLAN_25-09-26.md` | Status Strip RFC-002 set to CODE-COMPLETE; checklist ticked |

The engine implements all locked decisions:
- Log prices; the frames are inner-joined on UTC calendar date.
- `MIN_OVERLAP_DAYS=365`.
- Static full-sample OLS in both directions.
- `coint(..., autolag=EG_AUTOLAG="aic")` in both directions; the lower p ranks the pair. Ties go to `a_on_b`.
- D3: that direction's spread drives the z-score, the half-life and `spread`.
- AR(1): −ln2/β, and β≥0 gives `not_mean_reverting` with `days=None`.
- Z-score: latest spread against the full-sample mean and std (ddof=1).
- Johansen(0,1): `lr1[0]` against `cvt[0,1]`. ComplexWarning is suppressed only inside `johansen()`. If max|imag(eig)| > 1e-9, the Johansen result is refused.
- Statuses are `ok` / `insufficient_overlap` / `coin_unavailable`. The reason text names the day counts or the coin.
- `diagnostic_scope="whole_history_in_sample"` on every result.
- `_assert_finite` raises instead of ever returning NaN/inf for an `ok` pair.
- `bh_adjust` runs `multipletests(method="fdr_bh")` over `ok` pairs only.

## Test Gate Outcomes

| Gate | Result |
|---|---|
| `uv run --project api pytest api/tests/analytics/test_cointegration_stats.py -q` | **20 passed** (4.6 s) |
| `uv run --project api pytest api/ -q` | **440 passed, 3 deselected** (= 420 + 20) |
| Live sanity print (Hybrid) | run, below; awaiting user eyeball |

Test coverage:
- The 4 fixtures (a/b/c/d) plus `coin_unavailable` on either side.
- Overlap by date intersection, and exactly 365 days counting as ok.
- The exact geometric AR(1) case (β=−0.5, HL=1.386).
- A no-NaN/inf sweep and the diagnostic label.
- The named constants, and a check that the source has no I/O imports.
- D2: the warning is suppressed, and trace/crit are identical to the raw `coint_johansen` values.
- D2: the suppression is scoped (the warning still surfaces outside the Johansen call).
- D2: monkeypatched complex eigenvalues lead to the Johansen result being refused.
- A BH golden test computed by hand, plus the empty and all-non-ok cases.

TDD note: the tests were written after the implementation, in the same pass, not red-first.

## Golden Values

**Independent numpy oracles** (`np.polyfit` / `np.linalg.lstsq`, rel 1e-9): hedge ratios, spread,
AR(1) β, half-life and z-score for (a), (b) and (c).

**Pinned baseline** (statsmodels 0.15.0, rel 1e-6), with threshold assertions alongside:

| Fixture | p(A~B) | p(B~A) | rank dir | trace / cv95 | half-life | z |
|---|---|---|---|---|---|---|
| (a) cointegrated | 1.99e-19 | 1.84e-19 | b_on_a | 122.92 / 15.49 (rank≥1) | computed 3.14 d (β −0.2205) | −0.876 |
| (b) random walk | 0.6832 | 0.8730 | a_on_b | 4.90 / 15.49 (rank 0) | computed 128.8 d | 0.473 |
| (c) not mean-reverting (new build) | 0.9927 | 0.9816 | b_on_a | 685.8 (not asserted) | **not_mean_reverting**, β +0.000637 | −2.367 |
| (d) 300-day overlap | — | — | — | — | — | `insufficient_overlap`, "only 300 … need 365" |

BH golden: p = [.01, .04, .03, .20] over the ok pairs, with 2 non-ok pairs interleaved, gives
[.04, None, .0533, .0533, None, .20].

## Live Sanity Print (read-only, `cache.read_ohlcv`, no writes)

```
BTC-ETH  n=2229 2020-08-19..2026-09-25 p_ab=0.8613 p_ba=0.2571 dir=b_on_a hedge_ab=0.8899 hedge_ba=0.6706 trace=18.31 cv95=15.49 rank>=1=True  HL=162.2 z=-0.492
BTC-SOL  n=2203 2020-09-14..2026-09-25 p_ab=0.6808 p_ba=0.6606 dir=b_on_a hedge_ab=0.3901 hedge_ba=1.6450 trace=26.68 cv95=15.49 rank>=1=True  HL=288.4 z=-0.296
ETH-SOL  n=2203 2020-09-14..2026-09-25 p_ab=0.0066 p_ba=0.1454 dir=a_on_b hedge_ab=0.3601 hedge_ba=2.1471 trace=35.80 cv95=15.49 rank>=1=True  HL=65.7  z=-0.212
BTC-HYPE n=660  2024-12-05..2026-09-25 p_ab=0.6638 p_ba=0.6082 dir=b_on_a hedge_ab=-0.0994 hedge_ba=-0.5344 trace=5.16 cv95=15.49 rank>=1=False HL=70.2  z=2.042
LTC-BCH  n=2183 2020-10-04..2026-09-25 p_ab=0.3829 p_ba=0.7472 dir=a_on_b hedge_ab=0.4373 hedge_ba=0.8030 trace=10.89 cv95=15.49 rank>=1=False HL=140.9 z=-0.746
```
These match the Stage 0 samples (ETH-SOL p 0.0066 / HL ~66 d; BTC-HYPE has a negative hedge ratio).
The half-lives differ slightly from Stage 0 because D3 now uses the min-p direction's spread.

## Plan Deviations

1. **Fixture (c) was rebuilt** (within blast radius; test-only). The Stage-0 construction was `logB = 0.5 + 2·logA + explosive u`. It gives β>0 only on the B~A spread. Under D3 the rank-driving direction is A~B (p 0.971 < 1.0), whose spread has β=−0.00077, so that pair legitimately returns `computed`. D3 is locked, so I changed the fixture, not the code. New construction: each coin is a tiny random walk (σ 0.001) plus its own explosive AR component (φ 1.006 vs 1.003). The rank-driving spread then has β=+0.00064 and returns `not_mean_reverting`. The oracle confirms β≥0 independently. Johansen is still not asserted for (c).
2. **Added `bh_adjust` to `stats.py`.** You asked for a BH golden test. The plan puts the BH call in RFC-003's `pairs_response.py`, which should call this pure helper rather than re-implement it.
3. **Added a `johansen_reason` field** to `PairStatsResult`. When D2 refuses Johansen, the pair stays `ok` (EG, half-life and z-score are still valid) with `johansen=None` and the reason recorded. Stage 0 §4 floated a "coin_unavailable-style" label instead. I chose not to mark the whole pair unavailable. Say if you want that the other way.
4. **Added `diagnostic_scope`** (ADR-2c labelling field) and **`overlap_days: int | None`**. It is None for `coin_unavailable`, matching the §11 JSON.

## What Was Skipped or Deferred

- RFC-003: persistence, `compute_pairs.py`, the models and the router. Not started, as instructed.
- No commits. No `cache.py` or `ccxt_adapter.py` edits. No cache writes (confirmed with `git status`).

## Test Infra Gaps Found

- None. One environment note: a bare `python` call on this PC opens the Python 3.14 REPL and hangs. Always use `uv run --project api python`.

## Closeout Packet

- Plan: `pair-screener_PLAN_25-09-26.md`. RFC-002 is code-complete. Two verification boxes still need your review: the manual live-print review and user confirmation.
- Verified: both automated gates are green. Unverified: your review of the goldens, deviation #1 and #3, and the live print.
- Classification: **Keep in active/testing**, awaiting RFC-002 user sign-off.
- Next valid state: EVL confirmation run (vc-tester), then user review, then RFC-003 Stage 0.

## Forward Preview

- **Test Infra Found:** the numpy-oracle plus pinned-baseline pattern; `_frame(logp, start)` helper for OHLCV-shaped fixtures.
- **Blast Radius Changes:** new `api/analytics/cointegration/` package only.
- **Commands to Stay Green:** `uv run --project api pytest api/tests/analytics/test_cointegration_stats.py -q`; `uv run --project api pytest api/ -q` (~4 min).
- **Dependency Changes:** none.

CONTEXT_PARTIAL: none.
Follow-up stubs created: none.

## EVL fix cycle 2

- Gap: nothing asserted the `MIN_OVERLAP_DAYS` off-by-one boundary.
- Fix: added `test_one_below_min_overlap_is_insufficient` to `api/tests/analytics/test_cointegration_stats.py`. It mirrors `test_exactly_min_overlap_is_ok` and uses `stats.MIN_OVERLAP_DAYS - 1` (364 days of overlap). It asserts `status == "insufficient_overlap"`, `overlap_days == 364`, and no statistics via `_assert_no_stats`.
- `stats.py` unchanged; no engine code touched.
- Gates: `uv run pytest tests/analytics/test_cointegration_stats.py -q` → 21 passed; `uv run pytest -q` → 441 passed, 3 deselected.
- No commits.
