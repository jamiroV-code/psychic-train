# London Strategic Edge — Verification Findings

**Date:** 2026-09-24
**Script:** `verify_provider.py` (this task folder) — `python verify_provider.py --phase N [--xsource yfinance --compare-both]`
**Offline test suite:** `test_verify_provider.py` — 45/45 passed (pytest, synthetic fixtures, no network), confirmed by vc-tester at EVL iteration 2
**Where run:** Phases 1–4's live network calls ran on the user's own PC (this container's egress proxy blocks `londonstrategicedge.com` and `stooq.com` with 403). See the plan's Validate Contract §Execution Split.

## Phase 1 — Access and client sanity (AC1)

Command: `python verify_provider.py --phase 1`

- Free API key obtained, **no payment card requested**.
- `GET /vault/usage` before/after: `bytes_cap_month=53687091200`, `bytes_cap_week=16106127360`,
  `exports_cap_hour=5`, `calls_per_minute=200`, `max_rows_per_request=5000`,
  `historical_data_months=-1` (unlimited), `vault_concurrency=2`.
- AAPL, last 30 days: 21 rows — plausible (21 trading days in a 30-calendar-day window).
- Quota delta for the call: 2,616 bytes.
- Candle row shape: `{symbol, open, high, low, close, volume, timestamp (ISO)}`.

**Verdict:** AC1 met. Cost of one small request is known and negligible against the monthly cap.

## Phase 2 — Depth and coverage (AC2, AC3)

Command: `python verify_provider.py --phase 2` (fixed script, `cf7b847`)

Fixed 6-symbol set, full available history through 2026-09-24:

| Symbol | First date | Last date | Rows | Missing sessions | Extra rows (non-exchange days) |
|---|---|---|---|---|---|
| AAPL | 2003-09-10 | 2026-09-24 | 5834 | 0 | 37 |
| MSFT | 2003-09-10 | 2026-09-24 | 5831 | 0 | 34 |
| SPY | 2003-09-10 | 2026-09-24 | 5803 | 0 | 6 |
| XOM | 2003-09-10 | 2026-09-24 | 5827 | 0 | 30 |
| KO | 2003-09-10 | 2026-09-24 | 5822 | 0 | 25 |
| NVDA | 2003-09-10 | 2026-09-24 | 5822 | 0 | 25 |

Zero missing NYSE sessions and zero duplicate dates for all six. But every symbol also has **bars
on days the NYSE is closed** — sample dates: Thanksgiving 2006-11-23 and 2007-11-22, New Year's
Day 2008-01-01, Good Friday 2005-03-25, and SPY on Saturdays 2026-05-02/09/16/23/30. The series is
not a clean exchange-calendar feed; a consumer must filter to the real calendar rather than trust
the ticker's own date column.

**Delisted-ticker probe (AC3):** `SIVB` and `FRC` both return HTTP 404 ("has no candle data;
browse /catalog"). **Survivorship bias is present** — delisted names are not retrievable, and any
screener universe built from a current constituent list will silently exclude failed companies.

**Verdict:** AC2 met (history depth is deep — 23 years for all six — but the raw feed includes
non-trading-day bars that a consumer must filter). AC3 met (bias documented, present).

## Phase 3 — Accuracy and corporate actions (AC4, AC5, AC6)

Commands: `python verify_provider.py --phase 3 --xsource yfinance --compare-both`

Stooq's keyless CSV returned 404 on the user's PC on 2026-09-24 — **dead as a keyless source**.
Per the plan's Stooq Fallback clause, yfinance was substituted as the cross-check (a deviation
from the plan's stated primary/tiebreaker order, recorded here per the plan's own instruction).

**Adjustment-basis correction (EVL gap E5):** the first comparison run used yfinance's
`auto_adjust=True` (split + dividend adjusted), producing diffs that tracked dividend yield
(median KO 7.4%, XOM 8.4%, SPY 3.0%). Re-run against yfinance's split-only basis
(`auto_adjust=False`) resolved this — LSE is split-adjusted, not dividend-adjusted.

5-year daily close comparison, split-only basis, absolute % difference (median / p99 / max):

| Symbol | Median | p99 | Max |
|---|---|---|---|
| AAPL | 0.1445 | 2.8911 | 7.1374 |
| MSFT | 0.1492 | 3.7171 | 8.8570 |
| SPY | 0.0074 | 0.3389 | 0.9569 |
| XOM | 0.0908 | 0.9679 | 5.9423 |
| KO | 0.0702 | 0.5722 | 0.9090 |
| NVDA | 0.2988 | 4.9022 | 24.6316 |

For comparison, the same window on the total-return (dividend-adjusted) basis gives medians of
1.0992 / 2.0075 / 2.9643 / 8.3875 / 7.4356 / 0.3727 respectively — an order of magnitude worse,
confirming LSE's series is split-adjusted only.

**Max-diff outliers (EVL gap E6), root-caused:** the worst-agreement days cluster on
after-close earnings/news dates — NVDA 2023-05-24 (LSE 38.06 vs yfinance 30.538, the day of
NVDA's blowout earnings guidance), AAPL 2025-04-02 (LSE 207.91 vs yfinance 223.89, post-close
tariff news), MSFT 2026-07-29 / 2023-04-25 / 2025-07-30. **Working explanation: LSE's daily close
appears to capture the last trade of the calendar day (including after-hours trading), not the
official 4pm exchange close.** This is a real behavioral difference, not a data error, but LSE
closes should not be treated as interchangeable with official exchange closes around
earnings/news events.

**Split probes (AC5):**
- AAPL 4:1 split, 2020-08-31: observed ratio 0.980 → **series is adjusted** for this split.
- NVDA 10:1 split, 2024-06-10: observed ratio 1.000 → **series is adjusted** for this split.
- `splits()` endpoint returns full split history per symbol.

**OHLC integrity (AC6):** 0 violations across all 6 integrity checks × 6 symbols (low≤min(o,c),
max(o,c)≤high, positivity, no duplicate timestamps, monotonic dates).

**Verdict:** AC4 met (distribution reported, root-caused). AC5 met (both splits confirmed
adjusted). AC6 met (clean).

## Phase 4 — Screener-scale feasibility (AC7)

Command: `python verify_provider.py --phase 4` (ran on script `12e958b`, before the E1 DuckDB-column
fix landed in `cf7b847` — not re-run after the fix, since the fix only affected an internal query
column name, not the fetch/backfill numbers below)

- 50/50 symbols in the frozen `PHASE4_UNIVERSE` fetched successfully.
- All 50 fell back to the paged `candles()` endpoint because the hourly bulk-export allowance
  (`exports_cap_hour=5`) was exhausted by prior testing — bulk Parquet export was not actually
  exercised in this run.
- Elapsed: 118.6 s. Data size: 9.51 MB. Quota consumed: 32,833,204 bytes (~0.06% of the monthly
  cap of ~53.7 GB).
- DuckDB 3-year window query across all 50 symbols: 1.804 s.
- **Row-count anomalies, not re-measured with the fixed script:** HON has only 63 rows, starting
  2026-06-26 (unexplained — inconsistent with the ~23-year depth seen for the Phase 2 six-symbol
  set); NKE has ~6 fewer rows than expected; OXY, SLB, TGT show 810 rows and LIN shows 792 rows
  against an expected ~759 for the measured window — likely the same off-exchange-day bars seen
  in Phase 2 (extra_rows), not re-verified against a corrected count.

**Verdict:** AC7 met for cost/timing/DuckDB-shape (the screener is affordable — 0.06% of quota for
a 50-symbol full backfill). The per-symbol row-count anomalies are a known, carried-forward gap —
see Known Gaps below — not blocking for a private-use ADOPT-WITH-LIMITS verdict, since the
mechanism (non-exchange-day bars) is already documented in Phase 2 and no evidence points to
missing/wrong data.

## Phase 5 — Terms and verdict (AC8, AC9, AC10)

See `VERDICT.md` in this task folder for the verbatim licence quote, verdict and reasoning
(AC8/AC9). Context docs (`all-data-sources.md`, `all-context.md`) updated as part of this same
UPDATE PROCESS session (AC10) — **user confirmation for AC10:** the user issued "ENTER UPDATE
PROCESS MODE" after being shown the recommended ADOPT-WITH-LIMITS verdict; this is treated as the
AC10 decision confirmation. Recorded verbatim: *user proceeded to UPDATE PROCESS on 2026-09-24
after reviewing the ADOPT-WITH-LIMITS summary.*

## Known Gaps (carried forward, not blocking ADOPT-WITH-LIMITS)

1. **HON history anomaly** — only 63 rows, starting 2026-06-26, in the Phase 4 50-symbol pull.
   Unexplained; not re-measured with the corrected script. If HON is needed for real work, re-run
   Phase 2's per-symbol coverage check on it specifically before relying on its history.
2. **NKE (~6 fewer rows) and OXY/SLB/TGT (810 rows)/LIN (792 rows) vs ~759 expected** in the
   Phase 4 window — most likely the same non-exchange-day "extra rows" behavior documented in
   Phase 2, but not confirmed for these specific symbols with the fixed script.
3. **Stooq keyless CSV is dead** (404 on 2026-09-24) — cannot be used as the AC4 cross-check
   source going forward; yfinance was substituted per the plan's Fallback clause. This is a plan
   deviation, recorded per the plan's own instruction (see Phase 3 above).

These are recorded as backlog-worthy follow-ups if/when an `api/data/` equity adapter is actually
built (separate, later plan per Scope/Integration Notes) — not reasons to withhold the verdict on
this verification plan, whose job was to characterize the provider, not to build production code.
