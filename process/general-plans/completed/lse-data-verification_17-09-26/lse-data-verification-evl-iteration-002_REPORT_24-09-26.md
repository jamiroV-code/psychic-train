---
domain: tests
iteration: 2
date: 2026-09-24
plan: lse-data-verification_PLAN_17-09-26.md
gaps_found: 2
fail_count: 0
concern_count: 2
loop_status: CONTINUE
---

# EVL iteration 002: live Phases 2–4 on the user's PC (fixed script cf7b847; Phase 4 ran on 12e958b)

**Result:** every phase ran. Two measurement gaps block a clean AC-4 reading. Route: vc-execute-agent supplement.

| Gap | Sev | Evidence |
|---|---|---|
| E5 Cross-check compares different adjustment bases | CONCERN | `fetch_yfinance` uses `auto_adjust=True` (split + dividend adjusted). The diff tracks dividend yield: median KO 7.4%, XOM 8.4%, SPY 3.0%, MSFT 2.0%, AAPL 1.1%, NVDA 0.37%. Split probes show LSE is split-adjusted, so LSE is most likely NOT dividend-adjusted. The comparison must be against the split-only yfinance `Close` (`auto_adjust=False`) |
| E6 Max-diff outliers are unexplained | CONCERN | NVDA max 25.0% (p99 5.3%), MSFT max 11.5%. No listing of which dates drive the tail |

Live facts recorded (for findings):
- Phase 2: every ticker has **bars on NYSE-closed days**, e.g. Thanksgiving (2006-11-23 …), New Year's Day, Good Friday 2005-03-25, and for SPY Saturdays in May 2026. extra_rows are AAPL 37, MSFT 34, XOM 30, KO 25, NVDA 25, SPY 6. There are 0 duplicate dates and 0 missing sessions. SIVB/FRC return 404, so survivorship bias is present.
- Phase 3: AAPL 4:1 (2020-08-31) ratio 0.98 and NVDA 10:1 (2024-06-10) ratio 1.00, so the default series is **split-adjusted**. `splits()` returns the full split history. OHLC integrity shows 0 violations in all 6 checks × 6 symbols.
- Phase 4 (older script, all 50 fell back to candles() because the hourly exports were exhausted): 50/50 ok, 118.6 s, 9.51 MB, DuckDB 3-year query 1.80 s, 32.8 MB of quota (≈0.06% of the monthly cap). Anomalies: HON has only 63 rows, from 2026-06-26; OXY/SLB/TGT 810, LIN 792 and NKE 753 against ~759 expected for the window.
