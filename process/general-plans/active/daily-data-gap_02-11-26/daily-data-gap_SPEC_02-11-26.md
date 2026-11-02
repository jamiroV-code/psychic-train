---
name: spec:daily-data-gap
description: "D18: preserve daily price history while visibly disclosing missing daily candles on the screener."
date: 02-11-26
feature: screener
---

# Daily data gaps (D18)

Status: requirements for owner review; no source implementation authorized by this artifact.

## Summary

Preserve existing daily price history while clearly warning when days are missing inside it. The screener must not present a discontinuous series as complete. This change does not fill gaps or issue additional exchange requests.

## User Stories / Jobs To Be Done

- As the owner, I want to see when a coin has missing daily candles so I can interpret its chart and indicators with that limitation in mind.
- As the owner, I want my existing deep history retained rather than discarded to hide a gap.
- As the owner, I want the warning to remain accurate after reloads and disappear when the missing data is repaired.

## What The User Wants (Behavioral Outcomes)

1. An affected screener coin displays "Daily data gap: N missing days", independent of the currently selected display timeframe.
2. The coin's drill-down shows the missing date ranges, explicitly in UTC, alongside the daily-data warning.
3. Multiple gaps are included in the total; each missing day is counted once.
4. Existing bars remain unchanged. No synthetic candles, zero prices or silent interpolation are introduced.
5. A reload or cached response retains the warning as long as the gap exists.
6. A repaired series loses its warning. Short history alone is not an internal gap; an old latest candle remains a separate freshness concern.
7. The warning explains that indicators using daily history may span the missing days. Existing indicator calculations do not change in this slice.

## Flow / State Diagram

```text
[Read stored daily history] --> [Internal missing daily intervals?]
                                      | no                 | yes
                                      v                    v
                              [No gap warning]     [Count and show missing days]
                                                           |
                                                           v
                                                  [Drill-down lists UTC ranges]
                                                           |
                                               [Missing candles later repaired]
                                                           |
                                                           v
                                                   [Warning disappears]
```

## Acceptance Criteria (Testable Outcomes)

- AC1. A series with one missing daily interval displays the correct missing-day count and inclusive UTC date range on its screener coin and drill-down.
  proven by: seeded daily-gap payload-to-screen scenario.
  strategy: Fully-Automated
- AC2. Multiple internal gaps produce distinct ordered ranges and a total equal to their combined missing days, including across month and year boundaries.
  proven by: multiple-gap and UTC-calendar-boundary scenarios.
  strategy: Fully-Automated
- AC3. Consecutive daily candles, empty history, and short but consecutive history never produce an internal-gap warning; stale latest data retains its separate freshness state.
  proven by: continuous/empty/short-history and stale-without-internal-gap scenarios.
  strategy: Fully-Automated
- AC4. A cached response and a browser reload show the same warning without triggering an extra exchange request for gap detection.
  proven by: cached-gap reload integration scenario with provider calls disabled.
  strategy: Fully-Automated
- AC5. Filling the missing intervals removes the warning on the next response and screen refresh.
  proven by: gap-to-repaired transition scenario.
  strategy: Fully-Automated
- AC6. Reporting a gap does not change stored timestamps, OHLCV values, indicator calculations or the existing deep-history retention behaviour.
  proven by: retained-history and unchanged-calculation regression scenarios.
  strategy: Fully-Automated
- AC7. The gap warning and UTC date ranges remain readable at 375, 768 and 1280 pixel widths and are accessible without relying on a tooltip or colour alone.
  proven by: seeded screener/drill-down browser checks at the three widths.
  strategy: Fully-Automated

## Out Of Scope

- Automatic or manual gap backfill controls and extra exchange requests.
- Negative caching/backoff for failed fetches (D7), which the owner chose to leave unchanged.
- Changing pairs, regime or indicator calculations, or adding warnings to those pages.
- Redesigning screener layout, sorting, or freshness logic.

## Constraints

- Owner decision: "Keep the gap and flag it in the UI".
- Preserve deep daily history. Missing values must never become zeros or fabricated candles.
- Python determines missing intervals; the web formats the supplied result.
- Detection must reflect stored timestamps, not rely solely on a transient fetch note.
- Current incomplete daily candles and days outside the stored first-to-last interval do not count as internal gaps.
- No changes to the live deployment, account configuration or running X/Reddit workers during design.

## Open Questions

None for this scoped warning. Broader treatment of gaps by pairs/regime consumers remains outside this slice.

## Background / Research Findings

Source backlog: `process/general-plans/backlog/ohlcv-negative-cache-and-1d-gap-replace_NOTE_04-10-26.md`, D18.

Observed in this worktree: `api/data/ccxt_adapter.py:632-635` preserves a non-contiguous daily tail and returns `gap-kept`. `api/analytics/screener_board.py:173-176` retains the dataframe, status and fetch timestamp, but does not propagate that note. Therefore a fetch-note-only warning would disappear on a later cache hit and is insufficient.

Test context: pytest backend, vitest components and Playwright browser scenarios, routed by `process/context/tests/all-tests.md`. Scenario names above are required future gates, not claims of existing or executed tests. The implementation plan must bind them to concrete files and commands before execution.

The user approved using fallback models while Claude quota is exhausted; subsequent delegated design work should explicitly select an available Codex model. No provider calls or tests were run to produce this requirements artifact.
