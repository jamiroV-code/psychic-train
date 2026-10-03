---
name: context:north-star
description: "Product direction for my_site: a personal-use, Tailscale-only data tracker that shows data, not verdicts. Pages, invariants and non-goals."
keywords: north star, product direction, goal, purpose, personal use, tailscale, verdicts, screener, narrative, equities, non-goals, invariants, scope
date: 03-10-26
---

# North Star

**my_site is a personal-use data-tracking tool for one trader. It shows data as clearly as possible so the user draws their own market conclusions. It shows data, not verdicts.**

Decided 02-10-26 by the user. Sources: `process/general-plans/active/personal-tracker-realignment_02-10-26/` and `process/general-plans/active/narrative-baskets_02-10-26/` (the two SPECs). Decision log: decisions.md.

## What the app is

- A personal-use tracker for a solo trader. One user, the author.
- Reached only over Tailscale on the user's home PC. No public endpoint, now or planned.
- Its job is display: price, % change, RSI, attention levels, liquidity components, pair statistics. The user interprets them.
- It does not compute or show bullish/bearish calls, confidence badges, signal agreement, trend or momentum tags, PASS/FAIL views, `triggered`/`confirmed` flags, narrative state labels or trust weights. That output is deleted, not hidden.

## What changed (02-10-26)

| Before | Now |
|---|---|
| Turn separate signals into one confidence level that sizes positions | Show clean data; conclusions are the user's |
| Personal first, wider audience as a later goal | Personal use only; no wider audience planned |
| Data-provider terms shaped every adapter | Provider terms matter only for private use (for example LSE's private-use terms); they no longer shape the design |
| Charts/indicators as a fourth product page | Not built; RSI on the screener replaces it |

## Pages

| Page | Purpose | State |
|---|---|---|
| `/screener` | Small coin boxes: price line, % change and RSI (Wilder, 14) per timeframe (15m/1h/4h/1d/1w); user-named groups with drag and sort; add/remove coins in the UI; hard cap of 30 coins; BTC leg strip on top; one spaghetti chart of % change vs BTC and HYPE | Realignment queued (registry P4) |
| `/narrative` | User-defined narratives as baskets of screener coins; view 1 equal-weight basket performance rebased to 100; view 2 mindshare as share of total attention; daily resolution; raw data only | Redesign queued (registry P5) |
| `/regime` | Six liquidity components and the composite index, shown as data | Shipped; verdict wording to audit |
| `/pairs` | Cointegration screen of a fixed 18-coin universe, significance banner and p-value ranking kept as data | Shipped |
| `/onchain` | Chain-growth data with data-quality labels | Shipped |
| `/equities` | LSE equity data on its own page; the user adds tickers with an Add button; private-use note shown | Queued (registry P6) |

## Invariants (kept from the original design)

1. **Numbers are never silently wrong.** Missing, partial, stale or insufficient data shows an explicit state. Never 0, NaN, zero-fill or a silently shortened lookback.
2. **Python computes everything.** Every indicator, statistic and series is computed in `api/` and sent as data. The web app formats and renders; it never re-implements a calculation.
3. **Providers sit behind adapters.** Every provider is wrapped in one adapter under `api/data/` with a common shape, so swapping a provider is a one-file change.
4. **Free tiers are a constraint.** Fetching is cached and rate-limited at the adapter layer.
5. **History that cannot be re-fetched is archived nightly.** Narrative, LiqTide and chain-growth snapshots stay on their scheduled jobs. The pytrends partial-hour fix stays protected.
6. **No verdict logic returns under another name.** Every requirement stays testable.

## Data choices that follow

- Crypto prices: ccxt (Hyperliquid), no key.
- Equities: London Strategic Edge, verdict ADOPT-WITH-LIMITS, used under its private-use terms.
- Narrative attention, v1 candidates: Hyperliquid volume, Wikipedia pageviews, Google Trends, Reddit, CoinGecko trending. Each must pass a live probe on the user's PC before it is shown.
- Storage: Parquet files queried with DuckDB. Lean retention: about 200 bars of 15m data per coin; nothing stored that no page shows.
- Refresh: a coin older than 15 minutes refreshes on page load; no background job needed for the screener.

## Non-goals

- Signal generation, scoring, ranking-as-advice, or any bullish/bearish output.
- A computed "outperforming" label, rank text or "rising/hottest" verdict on any chart.
- Auth, billing, multi-tenancy or any second user.
- Public deployment or a publicly reachable URL.
- Trade execution or order placement.
- A standalone charts/indicators page.
- A preset equities ticker list.
- New paid market-data feeds, and yfinance as a provider.
- Retroactive correction of already-archived narrative or LiqTide history.

## How to use this file

Read it when a task touches product scope, a page's purpose, or whether a feature belongs. If a request conflicts with this file, the user decides; record the outcome in decisions.md. Current facts (branch, commit, test results) live in current-state.md, not here.
