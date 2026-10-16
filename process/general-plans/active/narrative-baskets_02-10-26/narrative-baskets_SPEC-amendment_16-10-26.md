---
name: spec-amendment:narrative-baskets-a6
description: "Amendment A6 to the narrative-baskets SPEC (owner decisions 16-10-26): one basket per coin, attention momentum not price, two tabs, open method, X and Reddit rules, Discovery outlier rules, clean UI."
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
| US-19, outcome 22 (many narratives per coin), AC-31 | SUPERSEDED: one basket per coin; moving a coin removes it from its old basket. |
| AC-27, AC-32, AC-9 | Kept. Names free text, 1-40 chars, unique ignoring case. Removal cascades to the one basket and the UI names it. |
| AC-28, outcome 20 | Lines are basket attention-momentum series (AC-37), not price. |
| AC-30 | SUPERSEDED (price maths dropped). Kept: "covers N of M coins", missing coins named. |
| AC-29, AC-33, outcome 21 | REPLACED by AC-36 (no share-of-total). |
| AC-34 | Extended by AC-38, AC-39. Signals: Wikipedia, Google Trends, exchange volume (Hyperliquid, Binance), CoinGecko market/categories/trending, X, Reddit (optional). |
| "X not in v1" | X is IN under AC-38. YouTube, Telegram stay out. |
| AC-11, AC-24, AC-25 | Unchanged, binding. |

## New acceptance criteria

**AC-35 One basket per coin.** Assigning a coin held by another basket moves it and the response names the old basket. Proven by: pytest (move, cascade, empty basket stays), Playwright. FA.

**AC-36 Open attention method.** Per coin and source: attention = 7-day mean / 90-day mean, percentile-ranked within the universe. Coin score = mean of the ranks of AVAILABLE sources (weights in config, default 1/n). A missing source is never zero-filled; the coin shows "n of N sources". Basket score = equal-weight mean of member coin scores plus BREADTH (share of members whose score rose over the window), so one coin cannot carry a basket. Each source's raw value is shown beside every headline number. Proven by: pytest with hand-computed fixtures (full, one source missing, one coin missing, one dominant coin: breadth low), vitest. FA.

**AC-37 Spaghetti on attention.** "My baskets" first view: one line per basket = its score series over 7/30/90 days (default 30), rebased to 100 at window start. No-data day = gap, not zero. No "rising/hottest/outperforming" text. Proven by: pytest payload, vitest, Playwright. FA (readability HY).

**AC-38 X is a low-trust vote.** Key only in the owner's private environment (`X_BEARER_TOKEN`), never in repo, tests, fixtures or logs. Hard caps on reads per run and per day (config; day counter stored outside git); at the cap the run stops and says "capped". A dry-run mode makes no network call and reports planned reads and USD. X weight is below the other sources and X is flagged for bot and cashtag spam. Until a live probe passes it shows "unavailable" and feeds no score. Proven by: pytest (both caps, dry run makes zero calls, token absent from logs and reprs), secret scan. FA.

**AC-39 Reddit optional.** Without keys Reddit shows "unavailable". No signal feeds a score before its probe record exists (AC-34).

**AC-40 Discovery tab.** Second tab: top 100 by market cap, public CoinGecko categories as narratives, ranked by mindshare momentum, independent of baskets. Proven by: pytest on fixtures, Playwright. FA.

**AC-41 Outlier rules.** Excluded: stablecoins, wrapped/staked duplicates, exchange tokens, 24h volume under the floor (config, about 20M USD). A coin is "gaining" only if at least 2 independent sources agree, 7d vs 30d (never one-day jumps). A coin's contribution is winsorized at the 95th percentile. Median is shown beside mean, with coins used. Proven by: pytest (each rule). FA.

**AC-42 Clean page.** Each tab: short header with window selector, chart first, compact ranked basket table, coins behind a basket expand. Existing design tokens, restrained palette, no decorative badges, no duplicate legends or labels, one plain line label per number, gaps as one muted "no data" mark, mobile and tablet checked, empty/loading/error states defined, old verdict clutter and keyword views removed. Accepted only after a before/after screenshot check by planner or owner. Proven by: vitest states, Playwright at three widths, screenshots. HY.

## Open questions

OQ-11, OQ-16, OQ-17 RESOLVED (no extra views; cascade; 7/30/90, default 30). OQ-12 RESOLVED for the source list; live probes stay open (AC-34, plan slice G). NEW for the owner: plan D-1 (reuse screener groups as baskets) and D-3 (percentile universe).
