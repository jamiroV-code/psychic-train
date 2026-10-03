# London Strategic Edge — Verdict

**Date:** 2026-09-24
**Verdict: ADOPT-WITH-LIMITS (private use only)**

## Redistribution terms (AC8)

Source: `https://londonstrategicedge.com/terms/`, "Last updated: 19 January 2026". Accessed and
pasted by the user 2026-09-24 (access date = paste date).

Verbatim, §6:

> "Redistribute or resell our data, or operate a competing feed, download service or API sourced
> from London Strategic Edge"

> "Using our data in your own research, trading, models or internal work, including for
> commercial purposes, is permitted and free of charge. The restrictions above concern
> redistribution: making our data available to third parties, whether in bulk or through a
> competing feed, download service or API. For redistribution or enterprise licensing, contact
> support@londonstrategicedge.com."

Also relevant: §7 (no derivative works without express written consent), §14 (terms can change at
any time), §8 (data provided "as is").

`lse-data` client itself: MIT licence, PyPI 0.14.0.

**Public-launch answer: NO, without a separate LSE redistribution licence.** The terms explicitly
distinguish "use in your own research/trading/models" (permitted, including commercially) from
"making the data available to third parties" (prohibited without a separate agreement). my_site's
stated intent to open the app to other users later is exactly the redistribution case §6
prohibits. The user states current use is private, so this does not block today's work — it
blocks the specific future step of serving LSE-derived numbers to other users, which requires
contacting LSE first.

## Evidence summary (AC1–AC7, from `findings.md`)

- **Access/cost (AC1):** free key, no card, one 30-day AAPL pull costs 2,616 bytes against a
  53.7 GB/month cap — trivially cheap.
- **Coverage (AC2):** ~23 years of daily history on all 6 fixed symbols (2003-09-10 → today), 0
  missing NYSE sessions, but the feed also carries bars on non-trading days (NYSE holidays,
  weekends) that a consumer must filter.
- **Survivorship (AC3):** delisted tickers (SIVB, FRC) return 404 — bias is present. Any
  screener built on a current constituent list will silently exclude failed companies.
- **Accuracy (AC4):** cross-checked against yfinance (Stooq's keyless CSV is dead, 404 as of
  today — substituted per the plan's own Fallback clause). On a split-only adjustment basis,
  median absolute daily-close difference is well under 0.3% for all six symbols; the fatter tails
  (up to ~25% for NVDA) are explained, not unexplained — they cluster on after-close
  earnings/news dates, consistent with LSE's close capturing the last trade of the calendar day
  (including extended hours) rather than the official 4pm close.
- **Corporate actions (AC5):** both probed splits (AAPL 4:1 2020, NVDA 10:1 2024) confirm the
  default series is split-adjusted.
- **OHLC integrity (AC6):** zero violations across all checks and all six symbols.
- **Screener-scale feasibility (AC7):** a 50-symbol full-history backfill costs ~0.06% of the
  monthly quota and runs in under 2 minutes; a 3-year DuckDB query across all 50 symbols in
  1.8 seconds. Some individual symbols show row-count anomalies (see Known Gaps in
  `findings.md`) that are plausibly the same non-exchange-day-bar behavior seen in Phase 2, but
  were not independently re-confirmed for those specific tickers.

## Reasoning

LSE clears every quantitative bar this plan set: it is genuinely free, the free tier easily
covers a 50-symbol screener, its data is internally consistent (OHLC integrity, correct split
adjustment), and its cross-source agreement with yfinance is tight once compared on the same
adjustment basis. The two real caveats — non-exchange-day bars and a close that can include
extended-hours trading — are both real, characterized, and manageable behind an adapter rather
than being unknowns. The one hard constraint is licensing: LSE data cannot be shown to other
users without a separate agreement, which matches this project's declared intent to open up
"later, not now." That makes LSE adoptable now, with an explicit limit recorded rather than
silently assumed.

## Adapter rules for a future `api/data/` equity adapter (not built in this plan)

When an equity adapter is eventually built (separate, later plan, gated on this ADOPT-WITH-LIMITS
verdict — equities remain out of scope for now; "crypto only for now" is unchanged):

1. **Drop bars not on the exchange calendar.** LSE returns bars on NYSE holidays and weekends;
   filter every pull against a real exchange calendar before use.
2. **Series are split-adjusted price only.** Dividends are not incorporated — total-return
   calculations need a separate dividend series.
3. **Close ≠ official exchange close.** LSE's daily close can include extended-hours trading.
   Flag this in the adapter's output and treat closes around earnings/major-news dates with
   caution.
4. **Survivorship bias is present.** No delisted-name history is available; any universe built
   from LSE alone will silently exclude failed companies.
5. **`redistributable=false`.** Per Standing Rule 7 in `all-data-sources.md`, tag every
   LSE-derived value at the adapter boundary as non-redistributable until a separate licence is
   obtained.

## Context docs updated (AC10)

- `process/context/data-sources/all-data-sources.md` — Equity Providers table and Licensing
  section replaced with verified facts and the adapter rules above.
- `process/context/all-context.md` — Open Decisions "Equity data provider" row updated to
  ADOPT-WITH-LIMITS; Changes Since Last Update entry added.
- `process/general-plans/backlog/yfinance-equity-source_24-09-26.md` — noted that LSE is the
  chosen provider and yfinance was used only as a verification cross-check, not adopted.

**User confirmation:** the user proceeded to UPDATE PROCESS on 2026-09-24 after reviewing the
ADOPT-WITH-LIMITS summary. Recorded as the AC10 decision confirmation.
