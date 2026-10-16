---
name: spec-amendment:narrative-baskets-a6
description: "Amendment A6 to the narrative-baskets SPEC (owner decisions 16-10-26): screener groups are the baskets, attention momentum not price, two tabs, open method, X and Reddit rules, Discovery outlier rules, clean UI."
date: 16-10-26
feature: narrative-baskets
metadata:
  node_type: memory
  type: spec
---

# Narrative Baskets: SPEC amendment A6 (16-10-26)

Binding. Where this file and `narrative-baskets_SPEC_02-10-26.md` differ, this file wins. "Momentum" always means MINDSHARE (attention) momentum, never price. No price line or price rank exists on /narrative.

## What changes

| SPEC item | Amendment |
|---|---|
| US-19, outcome 22, AC-31 | SUPERSEDED: one basket per coin; moving a coin removes it from its old basket. |
| AC-27, AC-32, AC-9 | Kept. A basket IS a screener group (D-1): names 1-40 chars, unique ignoring case, at most 12 groups including Main (11 baskets). Removal cascades to the one basket and the UI names it. |
| AC-28, outcome 20 | Lines are basket attention-momentum series (AC-37), not price. |
| AC-30 | SUPERSEDED (price maths dropped). Kept: "covers N of M coins", missing coins named. |
| AC-29, AC-33, outcome 21 | REPLACED by AC-36 (no share-of-total). |
| AC-34 | Extended by AC-38, AC-39. Signals: Wikipedia, Google Trends, exchange volume (Hyperliquid, Binance), CoinGecko, X, Reddit (optional). |
| "X not in v1" | X is IN under AC-38. YouTube, Telegram stay out. |
| AC-11, AC-24, AC-25 | Binding. AC-11 scope: the narrative modules and the /history and /mindshare shapes. |

## Owner decisions (16-10-26)

**D-1** Baskets are screener groups: one group per coin; group `main` ("Unassigned") is never scored; renaming a group renames the basket (identity = group id); the 12-group cap is accepted; deleting a group moves its coins to the last group (existing layout rule), so the UI warns first. **D-3** Ranks are percentiles against a top-100 market-cap reference universe, also for basket coins outside the top 100. X key exists (private env, spend caps); Reddit optional; Discovery on the top 100; spend ceiling 160 USD.

## New acceptance criteria

**AC-35 One basket per coin.** Moving a screener coin into a basket removes it from its old basket and the response names the old basket (null from Unassigned). Moving a coin to Unassigned (`main`) returns `basket: null`. The coin must be on the screener (AC-27). Proven by: pytest (move, unassign, cascade, empty basket stays, invalid id/symbol/unknown group), Playwright. FA.

**AC-36 Open attention method.** Per coin and source: attention = 7-day mean / 90-day mean, percentile-ranked against the top-100 reference universe (a coin outside it is placed in the distribution, not added). Coin score = mean of the ranks of AVAILABLE sources (weights in config, default 1/n); a missing source is never zero-filled; the coin shows "n of N sources". Basket score = equal-weight mean of member scores plus BREADTH (share of members whose score rose over the window), so one coin cannot carry a basket. Raw values sit beside every headline number. Under 90 daily points = `insufficient-history`. Proven by: pytest with hand-computed fixtures (full, one source missing, one dominant coin: breadth low, one coin outside the top 100), vitest. FA.

**AC-37 Spaghetti on attention.** "My baskets" first view: one line per basket = its score series over 7/30/90 days (default 30), rebased to 100 at window start, using today's membership (the page says so). No-data day = gap, not zero. No "rising/hottest/outperforming" text. Proven by: pytest payload, vitest, Playwright. FA (readability HY).

**AC-38 X is a low-trust vote.** Key only in the owner's private environment (`X_BEARER_TOKEN`), never in repo, tests, fixtures or logs. Hard caps on reads per run and per day and on USD per day (day counter outside git); at a cap the run stops and says "capped". Off by default; dry-run makes no network call and reports planned reads and USD. X weight is below the other sources; flagged for bot and cashtag spam; "unavailable" until a live probe passes, "insufficient history" until 90 own daily rows exist. Proven by: pytest (each cap, dry run zero calls, token absent from logs, reprs, exceptions), secret scan. FA.

**AC-39 Reddit optional.** Without keys Reddit shows "unavailable". No signal feeds a score before its probe record exists (AC-34).

**AC-40 Discovery tab.** Second tab: top 100 by market cap, public CoinGecko categories as narratives, ranked by mindshare momentum, independent of baskets. Proven by: pytest on fixtures, Playwright. FA.

**AC-41 Outlier rules.** Excluded: stablecoins, wrapped/staked duplicates, exchange tokens, 24h volume under the floor (config, about 20M USD). A coin is "gaining" only if at least 2 independent sources agree, 7d vs 30d. A coin's contribution is winsorized at the 95th percentile. Median is shown beside mean, with coins used. Proven by: pytest (each rule). FA.

**AC-42 Clean page.** Each tab: short header with window selector, chart first, ranked table of five columns, coins behind a basket expand. Design tokens only (no colour or font-size literals), one legend, no badges, one plain label per number, gaps as one muted "no data" mark, no horizontal scroll at 375/768/1280 px, empty/loading/error/partial states defined, old verdict clutter and keyword views removed. Accepted only after a before/after screenshot check by planner or owner. Proven by: vitest, Playwright, screenshots. HY.

## Open questions

OQ-11, OQ-16, OQ-17 RESOLVED (no extra views; cascade; 7/30/90, default 30). OQ-12 RESOLVED for the source list; live probes stay open (AC-34, plan slice G). D-1 and D-3 RESOLVED by the owner.
