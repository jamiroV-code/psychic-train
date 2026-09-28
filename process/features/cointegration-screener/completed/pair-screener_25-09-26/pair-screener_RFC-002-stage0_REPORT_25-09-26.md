---
name: report:pair-screener-rfc-002-stage0
description: "RFC-002 Stage 0 findings — statsmodels call shapes, result dataclass shape, four golden fixture designs, ComplexWarning evidence, real-cache timing"
date: 25-09-26
metadata:
  node_type: memory
  type: report
  feature: cointegration-screener
  phase: RFC-002-stage-0
phase: rfc-002-stage-0
status: COMPLETE
feature: cointegration-screener
plan: process/features/cointegration-screener/active/pair-screener_25-09-26/pair-screener_PLAN_25-09-26.md
---

# RFC-002 Stage 0 — Pre-Phase Research (STOP for user approval)

**Bottom line:** the stats design works as the ADRs describe and all four golden fixtures behave
as planned. There is one big finding: computing all 153 pairs takes **~46 s** with `coint()`'s
default lag search. The RFC-003 target is p95 < 3 s. Almost all of that time is the Engle-Granger
lag search (Johansen takes ~5 ms per pair). No code or tests were written. No repo files changed
except this report.

## What Was Done

- Read the plan's RFC-002 section, ADR-1..8, the validate-contract rows (incl. E4), the RFC-001
  Stage 0 report and Standing Lesson table (`tests/all-tests.md`).
- Ran one throwaway script (scratchpad `rfc002_stage0.py`, not in the repo). It **read** the real
  cache directly with `pd.read_parquet` and wrote nothing. Env: statsmodels 0.15.0, numpy 2.5.3,
  pandas 3.0.6.
- Cache as found: 18 coins, 660 (HYPE) – 2,229 bars; all 153 pairs have ≥ 365 overlapping days
  (HYPE pairs have the least: 660 days).

## 1. Call shapes (confirmed)

| Call | Shape used |
|---|---|
| `coint(y, x, trend="c", method="aeg")` | `[0]` t-stat, `[1]` p-value, `[2]` crit (1/5/10%). Default `autolag="aic"`, `maxlag=None` |
| `coint_johansen(np.column_stack([la, lb]), 0, 1)` | `lr1[0]` = trace stat for r=0; `cvt[0, 1]` = 95% critical value (column order is 90/95/99). `lr1` is float64 |
| AR(1) half-life | OLS of `Δspread` on `[1, spread_lag]` → β. Proposed: closed form `β = cov(Δs, s_lag)/var(s_lag)` (numpy, no statsmodels needed). Checked against `sm.OLS(...).fit().params` and the two match to ~1e-15 |
| Hedge ratio | Same closed-form OLS `y = α + b·x` on log prices. Matches `sm.OLS` exactly |
| `multipletests(p, method="fdr_bh")` | Belongs to RFC-003; `method` must always be passed explicitly (default is `hs`) |

## 2. Proposed result shape (`stats.py`)

```python
@dataclass(frozen=True)
class EGResult:            # one direction
    dependent: str; independent: str
    hedge_ratio: float; intercept: float     # log-space (ADR-1)
    t_stat: float; p_value: float

@dataclass(frozen=True)
class JohansenResult:
    trace_stat_r0: float; crit_95: float; rank_at_least_1: bool

@dataclass(frozen=True)
class HalfLife:
    state: Literal["computed", "not_mean_reverting"]
    days: float | None; ar1_beta: float     # days None iff not_mean_reverting

@dataclass(frozen=True)
class PairStatsResult:
    symbol_a: str; symbol_b: str
    status: Literal["ok", "insufficient_overlap", "coin_unavailable"]
    reason: str | None
    overlap_days: int; sample_start: date | None; sample_end: date | None
    eg_a_on_b: EGResult | None; eg_b_on_a: EGResult | None
    eg_min_p: float | None; eg_rank_direction: Literal["a_on_b", "b_on_a"] | None
    johansen: JohansenResult | None
    half_life: HalfLife | None
    zscore: float | None
    spread: pd.Series | None   # spread of the rank-driving direction; used by the detail endpoint (RFC-003)
```

Rules: every stats field is `None` unless `status == "ok"`. For `ok`, every float must be finite;
anything else is an internal error, never a stand-in value (AC-8). The z-score and half-life use
the spread from the **rank-driving (min-p) direction**. The plan does not say which direction to
use, so this is decision D3 below.

## 3. Golden fixtures (per Standing Lesson + E4)

All fixtures use a fixed seed (`20260925`), 1,000 daily UTC bars and log-space construction.
Two ways the expected values are produced:
- **Hand-computed, checked independently:** hedge ratio, AR(1) β, half-life and z-score. The test
  computes them with closed-form numpy formulas written separately from `stats.py`. There is also
  a tiny exact case: spread `[1, .5, .25, .125, .0625]` → β = −0.5 exactly and HL = ln2/0.5 = 1.386.
  I confirmed this in the script.
- **Pinned baseline:** the EG p-values and the Johansen trace. These are asymptotic test statistics
  and can't be derived by hand (E4). The fixtures are built to land far from the decision
  threshold, and the exact statsmodels output is recorded as a reviewed baseline.

| Fixture | Construction | Measured (pinned) | Assertions |
|---|---|---|---|
| (a) cointegrated | `logB = 0.5 + 2·logA + e`, e = AR(1) φ=0.8, σ=0.02; A = RW σ=0.03 | p(B~A)=1.8e-19, p(A~B)=2.0e-19; trace 122.9 vs cv 15.49; b=1.98849; β=−0.2205 → HL=3.14 d (theory for φ=0.8: ln2/0.2=3.47) | both p < 0.01; rank ≥1 True; `computed`; b ≈ 2 ± 0.05 |
| (b) non-cointegrated | two independent RWs | p=0.873 / 0.683; trace 4.9 vs 15.49 | both p > 0.3; rank ≥1 False |
| (c) not mean-reverting | `logB = 0.5 + 2·logA + u`, u explosive φ=1.004 | β=+0.00268 ≥ 0 → `not_mean_reverting`, `days None` | state + None only. **Note:** Johansen reports rank ≥1 True here (trace 342), because the explosive spread gets mistaken for a relationship. The test must not assert on Johansen for this fixture. |
| (d) short overlap | fixture (a) sliced so the overlap is 300 days | — | `insufficient_overlap`; reason names 300 and 365; every stats field None |

Also planned: a `coin_unavailable` case (empty DataFrame). There will be a no-NaN/inf sweep over
every numeric field of every fixture.

Evidence the `not_mean_reverting` branch is real, not just theoretical: **2 of the 153 real pairs**
have β ≥ 0. Plain random walks almost never trigger it (1 in 200 seeds). That is why fixture (c)
uses an explosive spread instead of a random walk.

## 4. ComplexWarning — evidence and recommendation

- It fires on **153/153 real pairs and on every fixture**, 4 warnings per call: "Casting complex
  values to real discards the imaginary part".
- `j.eig` is `complex128` but the **largest imaginary part is exactly 0.0** on all 153 real pairs
  and on the fixtures. `lr1` and `cvt` come out as float64. So the cast throws nothing away.
- **Recommendation:** suppress `numpy.exceptions.ComplexWarning` only inside a `warnings.catch_warnings()`
  block around the `coint_johansen` call, with a comment pointing here. Add a guard: if
  `max|imag(eig)| > 1e-9`, the pair returns `coin_unavailable`-style "Johansen numerically unstable"
  instead of a number, so it is never silently wrong. I'd rather do this than take `.real`
  ourselves, because the outputs are already real. The warning is noise, and the guard covers the
  case where it is not.

## 5. Timing (real cache, warm OS cache, single process, this PC)

| Config | 153 pairs total | per-pair mean | p95 | EG share | Johansen |
|---|---|---|---|---|---|
| `coint` default `autolag="aic"` (ADR as written) | **46.0 s** | 296 ms | 513 ms | ~98% | 4.6 ms |
| `coint(..., autolag=None)` (fixed maxlag, statsmodels default formula) | 7.6 s | 44 ms | 63 ms | ~82% | 6.7 ms |

- Extrapolation: the RFC-003 target (p95 < 3 s per request) is **missed by ~15×** on a cold
  compute, and still ~2.5× with the lag search off.
- The bottleneck is `coint()`'s AIC lag search in the ADF step, run twice per pair. This is the
  "real, not-yet-measured risk" named in the validate-contract, now measured.
- The ADRs don't pin `autolag`, so I did not change anything. ADR-8's planned fallback (an
  in-process TTL cache) makes *repeat* requests fast, but the first request after startup or
  expiry would still take ~46 s. Options are listed in D1.

## 6. Other real-data observations (FYI, no action)

- EG (min p < 0.05) and Johansen agree on 128/153 pairs. Example: BTC-SOL has EG p = 0.66 but
  trace 26.7 > 15.49. A disagreement column will be common, which is the AC-6 "two opinions" point.
- Sample rows: ETH-SOL EG p = 0.0066, HL 66 d; BTC-ETH p = 0.26/0.86, HL 548 d; BTC-HYPE has a
  negative hedge ratio (−0.10).

## What Was Skipped or Deferred

- RFC-002 Stages 1–7, the tests and the live sanity print: not started (Stage 0 STOP).

## Test Gate Outcomes

- None run. No code changed. The baseline from RFC-001 still stands.

## Plan Deviations

- None. The script read the cache with `pd.read_parquet` instead of `cache.read_ohlcv`. This is
  read-only and gives the same result.

## Test Infra Gaps Found

- None new.

## Closeout Packet

- Plan: `pair-screener_PLAN_25-09-26.md`; Stage 0 complete; awaiting approval of D1–D4.
- Next valid state: RFC-002 Stage 1 after approval.

## Forward Preview

- **Test Infra Found:** closed-form numpy OLS works as an independent oracle; pinned-baseline pattern for EG/Johansen.
- **Blast Radius Changes:** none.
- **Commands to Stay Green:** `uv run --project api pytest api/tests/analytics/test_cointegration_stats.py -q`, then `uv run --project api pytest api/ -q`.
- **Dependency Changes:** none (statsmodels 0.15.0 from RFC-001).

## Decisions Needing User Approval

- **D1 — Performance (affects RFC-003, not RFC-002 logic).** Choose one:
  (a) keep `autolag="aic"` and rely on ADR-8's TTL cache. First request ~46 s.
  (b) `autolag=None` with a fixed maxlag. ~7.6 s, still above 3 s. Needs a small ADR-2 note,
  because p-values will shift slightly.
  (c) keep AIC but run the pairs in parallel across processes, or precompute at startup. Both
  would need an ADR-8 change.
  (d) relax the 3 s target for the cold first request.
  My lean: (a) plus (d), i.e. accept a slow first request and a fast warm one. Decide at
  RFC-003 Stage 0. RFC-002 will expose `autolag` as a named module constant, so any choice is a
  one-line change.
- **D2 — ComplexWarning:** scoped suppression plus the imaginary-part guard (§4). Approve?
- **D3 — Which spread drives the z-score and half-life:** the min-p (rank-driving) direction's
  spread. Approve?
- **D4 — Result dataclass shape (§2) and the four fixtures (§3)**, including fixture (c) not
  asserting on Johansen. Approve?

TL;DR: The design is sound and the fixtures are verified. `coint`'s lag search makes the 153-pair
compute take ~46 s against a 3 s target. The fix belongs at RFC-003 and needs your decision (D1).
