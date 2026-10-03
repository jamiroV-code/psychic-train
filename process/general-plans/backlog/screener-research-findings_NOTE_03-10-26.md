---
name: note:screener-research-findings
description: "Backlog: RESEARCH facts (03-10-26) a later PLAN needs for the screener realignment (P4/P6): SPEC item status, verdict-code retirement list, RT3 coupling, risks"
date: 03-10-26
feature: general
---

# Screener research findings (backlog note)

- **Source:** planner RESEARCH, 03-10-26, read-only, on `personal-tracker-realignment_SPEC_02-10-26.md`. Decisions D1-D11 are in that SPEC (`## Decisions 03-10-26`).
- **Use:** input for INNOVATE/PLAN of P4 and P6. No work started.

## SPEC item status (code vs SPEC)

| Item | Status |
|---|---|
| RSI(14, Wilder) per timeframe | partial (indicator exists; per-timeframe board wiring to confirm) |
| Groups, coin order, chart toggles, server layout file | missing |
| 30-coin cap (API-enforced) | missing (absent today) |
| Spaghetti chart, fixed BTC/HYPE lines | partial (benchmark chart exists, auto-switch to remove) |
| BTC leg strip, confirmed legs only | partial (`LegTimelineBanner`, verdict-coupled) |
| 15-minute background refresh | missing |
| Verdict deletion | exists (must be removed) |
| Equities (LSE) | missing (no equities code) |

## Verdict-code retirement (about 20 source + 12 test files)

- `api/analytics/confidence/badge.py`
- `api/analytics/indicators/momentum.py` (PASS/FAIL functions); `trend.py` `compute_trend`
- `screener_board.py` verdict wiring and `build_scalp_view`
- `api/routers/screener.py` `/scalp`
- `api/models/screener.py` verdict models
- web: `ConfidenceBadge.tsx`, `SignalDetailPanel.tsx`, `NarrativeStrip.tsx`, `LegTimelineBanner.tsx`; verdict parts of `CoinPanel`, `DrillDownView`, `ScreenerBoard`
- `web/lib/types/screener.ts`, `web/lib/api/screener.ts`
- `globals.css` confidence-badge rules; `web/app/page.tsx` copy line
- Tests that break: about 12 test files covering the above (list them at PLAN time with `rg`).

## RT3 coupling

- `api/models/screener.py` and `web/lib/types/screener.ts` change in lockstep.
- Contract-sync test `test_screener_integration.py:141` must be updated with them.

## Risks

- Serial board fetch: about 24 s cold for 4 coins; up to 150 sequential OHLCV calls at 30 coins x 5 timeframes.
- First pull is 500 bars; 15m 500 bars is about 5.2 days vs the about 2 days target.
- Nightly OHLCV commits are no-ops because `cache/ohlcv` is git-ignored.
- No drag-and-drop library in `web/`.
- CI has no Playwright; E2E is not in CI.
- D6 tension: weekly span (see SPEC D6).
