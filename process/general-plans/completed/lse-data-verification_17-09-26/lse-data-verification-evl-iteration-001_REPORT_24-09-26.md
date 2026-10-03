---
domain: tests
iteration: 1
date: 2026-09-24
plan: lse-data-verification_PLAN_17-09-26.md
gaps_found: 4
fail_count: 2
concern_count: 2
loop_status: CONTINUE
---

# EVL iteration 001 — first live run on the user's PC

**Result:** Phases 1–2 ran. Phase 3 stopped (Stooq 404, Alpaca key not set). Phase 4 crashed after fetching. Route: vc-execute-agent supplement, scoped to the gaps below.

| Gap | Sev | Evidence (user's pasted output) |
|---|---|---|
| E1 Phase 4 DuckDB query crash | FAIL | `BinderException: Referenced column "date" not found` in `query_store`; the store's columns don't include `date` (history() export shape ≠ normalized). Metrics were lost because the query runs before they print |
| E2 Stooq cross-check endpoint 404 | FAIL | `404 Not Found` for `stooq.com/q/d/l/?s=aapl.us&i=d&d1=20210925&d2=20260925`; d2 is tomorrow; the endpoint may have changed |
| E3 Phase 2 row counts inconsistent with 0 missing sessions | CONCERN | Same range 2003-09-10..2026-09-24, 0 missing each, but rows vary 5803 (SPY)..5834 (AAPL), so there are extra off-calendar and/or duplicate dates the table doesn't report |
| E4 Phase 4 vs export cap | CONCERN | `/usage` shows `exports_cap_hour: 5`; 50 bulk `history()` exports cannot fit in an hour. The fallback path and its cost need to be explicit and printed |

Live facts recorded (for findings): free tier = 50 GiB/month, 15 GiB/week, 5 exports/hour, 200 calls/min, 5000 rows/request, historical_data_months −1 (unlimited); one 21-row AAPL request cost 2616 bytes; daily history for all 6 fixed symbols starts 2003-09-10; SIVB and FRC return 404 "no candle data", so delisted names are absent (survivorship bias present).
