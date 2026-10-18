---
name: spec:narrative-baskets-universe-narratives
description: "T108: tradeable universe (top 100, explicit exclusion reasons, backup volume floor plus thin label) and a narratives.json where every in-universe coin sits in a recognisable narrative; counts from the committed 18-10-26 snapshot, the 47-missing-CoinGecko cause, tradeability test, config design, ACs and slices. Docs only; no code changed."
date: 18-10-26
feature: narrative-baskets
metadata:
  node_type: memory
  type: spec
---

[MODE: SPEC]

**Status:** draft for owner review. Owner decisions of 18-10-26 are taken as given (Section 0). Everything needing a live provider call is marked UNVERIFIED. Counts below come from a read-only script over committed files (scratchpad, not the repo).

## 0. Owner decisions taken as given

Goal: find ATTENTION on coins the owner can trade (a trade = profit from a price going up or down). Universe = top 100 by market cap. OUT, with the reason shown on the page and never silent: stablecoins; wrapped/staked/bridged copies; coins with no real market on Binance, Coinbase, Kraken or Hyperliquid (spot or perps). IN: everything else, including exchange tokens (LEO OKB CRO GT KCS BGB MX, BNB), memecoins and gold tokens. **This reverses D-20** (`process/context/decisions.md:180`, exchange tokens excluded 17-10-26); a new decision entry must supersede it. The 20M floor goes; a small backup floor plus a "thin volume" label replace hiding. Every in-universe coin sits in at least one recognisable narrative (one primary, optionally one second), at least 3 coins per narrative. A coin with no usable source is never cut: ladder volume (exchange composite, else CoinGecko) > Wikipedia > Google Trends (keyword = full coin name) > Reddit > "low data" with the reason shown.

## 1. Counts from the committed snapshot

Source: `api/data/cache/attention/universe.json`, newest snapshot **2026-10-18, 100 symbols** (previous snapshot 2026-10-17, 100); each row has `id, symbol, market_cap, volume_24h` (CoinGecko `total_volume`, an all-venue aggregate). Categories: `api/data/cache/attention/categories.json`, snapshot 2026-10-18, 10 categories.

**1a. 24h-volume bands (all 100 symbols).** Below 5M: **19**. Below 10M: **28**. Below 20M: **39** (cumulative).

| Band | Symbols (volume in $M) |
|---|---|
| < 5M (19) | BCAP 0, BUIDL 0, EURSAFO 0, EUTBL 0, USTB 0, USYC 0 (these six have `volume_24h` null/0), FIGR_HELOC 0.2, OUSD 0.2, LEO 0.2, USDF 0.4, BFUSD 0.6, GT 1.0, GHO 1.0, M 1.0, USDD 2.2, USDY 2.3, PI 2.6, NEXO 3.0, CRO 5.0 (4.96) |
| 5 to < 10M (+9 = 28) | SKY 5.9, STABLE 7.2, AKE 8.1, PRL 8.7, CC 8.8, KAS 8.8, XDC 9.0, BGB 9.0, USDGO 9.2 |
| 10 to < 20M (+11 = 39) | USDS 10.6, NIGHT 11.9, VVV 13.6, WLFI 13.7, PYUSD 14.5, STX 15.6, RAIN 16.4, USDE 17.1, MORPHO 17.5, MNT 19.2, GRAM 19.3 |

Of these, the ones that are real tradeable-class coins (not stablecoin/tokenized fund; 76 coins in the classes below): < 5M: **5** (LEO, CRO, GT, PI, NEXO); < 10M: **13** (+CC, SKY, BGB, KAS, PRL, AKE, STABLE, XDC minus none; list = LEO CC CRO SKY BGB GT KAS PI NEXO PRL AKE STABLE XDC); < 20M: **21** (+RAIN, GRAM, WLFI, MNT, MORPHO, VVV, STX, NIGHT). So a 5M backup floor would cut 5 in-scope coins, three of them exchange tokens the owner wants IN (LEO, CRO, GT): see Q1.

**1b. Classes (heuristic, my reading of ticker and category; names marked UNVERIFIED were not checked against a provider).** Stablecoins **16** (the 8 in `attention_universe.json` `stablecoins`: USDT USDC USDS USDE DAI USD1 PYUSD USDD; plus 8 not listed there: USDG RLUSD USDF BFUSD USDGO OUSD GHO and U (UNVERIFIED)). Wrapped/staked copies **0** (no WBTC/stETH-style symbol is in this top 100; the `wrapped` list matches nothing; WBT is WhiteBIT's exchange coin, not wrapped BTC). Tokenized funds / treasuries **8** (USDY BUIDL USYC USTB EUTBL EURSAFO BCAP FIGR_HELOC): no exchange market expected, so they fall out on the tradeability test with reason "no market", not as a class. Exchange tokens **9** (config 6 present: LEO CRO OKB BGB GT KCS; MX absent; plus BNB, and WBT, HTX proposed). Normal **67**. In-scope before tradeability: 67 + 9 = **76**.

**1c. Waterfall today (code order), 100 to what the owner sees.**

| Step | Rule (cite) | Removed | Left |
|---|---|---|---|
| 0 | snapshot, top 100 by cap (`universe.py:14,35-36`) | | 100 |
| 1 | `stablecoins` list (`universe.py:26`, `attention_universe.json`) | 8 | 92 |
| 2 | `wrapped` list (same) | 0 | 92 |
| 3 | `exchange_tokens` list in `universe.py:26` (LEO CRO OKB BGB GT KCS) | 6 | 86 (= `universe_size`) |
| 4 | `exclude` in `discovery.json` (same 6, already gone) | 0 | 86 |
| 5 | category `exchange-based-tokens` minus BNB (`discovery.py:162-165`) | **10**: HYPE WBT UNI PUMP ASTER HTX JUP AERO NEXO CAKE | 76 |
| 6 | floor 20M (`discovery.py:159,166-167`; null volume also fails) | **30** | 46 (= `eligible_size`) |
| 7 | member of none of the 9 categories (`discovery.py:196`) | **7**: USDG RLUSD U (stablecoins missing from the list), WLD DOT ATOM ZRO (real coins CoinGecko gives no listed category) | 39 coins |
| 8 | a coin counts in each of its categories (`discovery.py:9`) | | **51 rows** |

Findings from the waterfall: (a) step 5 silently removes real DeFi/DEX coins (UNI, JUP, AERO, CAKE, HYPE, ASTER) because CoinGecko also tags them exchange-based; (b) step 7 drops WLD, DOT, ATOM, ZRO because they have no one of the 9 category tags; (c) three stablecoins leak past the lists; (d) nothing in the response says any of this.

## 2. Per-coin table (whole snapshot, 100 rows)

Columns: vol = 24h volume $M; class; primary / second narrative (default = from the committed categories snapshot, mapped to the 12 narratives; **(P)** = planner proposal where categories give none or a wrong one; **?** = UNVERIFIED what the coin is); wiki = `wiki_articles.json` article mapped (y/n); CG = a CoinGecko series is stored (`cache/attention/coingecko/<SYM>.parquet`); src = how many of the stores wikipedia / coingecko / hyperliquid_volume hold a parquet for it today (0-3; Binance, Trends, Reddit, X, GitHub, DefiLlama stores are not committed: no `exchange_volume`, `trends`, `reddit`, `xsearch` directory exists under `api/data/cache/attention/`). Hyperliquid has 1 day of history (needs 90), so it is stored but not usable (`probe_records.json`: `insufficient-history`, `coins_ok` 0).

| sym | vol | class | primary | second | wiki | CG | src |
|---|---|---|---|---|---|---|---|
| BTC | 16391.1 | normal | Majors | - | y | y | 3 |
| ETH | 6954.2 | normal | Majors | Layer 1 | y | y | 3 |
| USDT | 31074.3 | stablecoin | - | - | n | n | 0 |
| BNB | 558.1 | exchange token | Exchange tokens (P) | - | y | y | 3 |
| XRP | 1020.1 | normal | Payments | Layer 1 | y | y | 3 |
| USDC | 8102.8 | stablecoin | - | - | n | n | 0 |
| SOL | 2011.8 | normal | Layer 1 | - | y | y | 3 |
| TRX | 281.9 | normal | Layer 1 | - | y | y | 3 |
| FIGR_HELOC | 0.2 | tokenized fund | - | - | n | n | 0 |
| ZEC | 704.1 | normal | Privacy | - | y | y | 3 |
| HYPE | 438.3 | normal | DeFi | Layer 1 | n | y | 2 |
| DOGE | 446.8 | normal | Memecoins | - | y | y | 3 |
| XMR | 179.9 | normal | Privacy | - | y | y | 3 |
| USDS | 10.5 | stablecoin | - | - | n | n | 0 |
| WBT | 50.9 | exchange token | Exchange tokens (P) | - | n | n | 0 |
| LINK | 236.8 | normal | Infrastructure | DeFi | y | y | 3 |
| LEO | 0.2 | exchange token | Exchange tokens (P) | - | y | y | 1 |
| ADA | 236.7 | normal | Layer 1 | - | y | y | 3 |
| RAIN | 16.4 | normal | DeFi (C?) | - | n | n | 0 |
| NEAR | 555.9 | normal | Layer 1 | AI | y | y | 2 |
| XLM | 98.5 | normal | Payments | Layer 1 | y | y | 3 |
| BCH | 121.0 | normal | Payments (P) | - | y | y | 3 |
| USDE | 17.1 | stablecoin | - | - | n | n | 0 |
| LTC | 205.1 | normal | Payments (P) | - | y | y | 3 |
| DAI | 150.7 | stablecoin | - | - | n | n | 0 |
| UNI | 274.5 | normal | DeFi | - | y | y | 3 |
| AVAX | 223.7 | normal | Layer 1 | - | y | y | 3 |
| USD1 | 497.0 | stablecoin | - | - | n | n | 0 |
| CC | 8.8 | normal | Layer 1 | - | n | n | 0 |
| SUI | 350.3 | normal | Layer 1 | - | n | y | 2 |
| HBAR | 174.0 | normal | Layer 1 | - | y | y | 3 |
| GRAM | 19.3 | normal | Layer 1 (C?) | - | n | n | 0 |
| BTW | 27.4 | normal | DeFi (C?) | - | n | n | 0 |
| XAUT | 66.7 | normal | Real-world assets | Majors | n | y | 1 |
| USDG | 272.7 | stablecoin | - | - | n | n | 0 |
| TAO | 120.5 | normal | AI | - | n | y | 2 |
| SHIB | 35.7 | normal | Memecoins | - | y | y | 2 |
| PYUSD | 14.5 | stablecoin | - | - | n | n | 0 |
| CRO | 5.0 | exchange token | Exchange tokens (P) | - | y | y | 1 |
| QNT | 54.9 | normal | Infrastructure (P) | - | n | y | 1 |
| ENA | 235.0 | normal | DeFi | - | n | y | 2 |
| RLUSD | 60.3 | stablecoin | - | - | n | n | 0 |
| USYC | 0.0 | tokenized fund | - | - | n | n | 0 |
| OKB | 20.2 | exchange token | Exchange tokens (P) | - | n | y | 1 |
| USDY | 2.3 | tokenized fund | - | - | n | n | 0 |
| AAVE | 198.3 | normal | DeFi | - | y | y | 2 |
| BUIDL | 0.0 | tokenized fund | - | - | n | n | 0 |
| ONDO | 78.5 | normal | Real-world assets | DeFi | n | y | 2 |
| PUMP | 98.6 | normal | Memecoins | DeFi | n | n | 0 |
| ASTER | 114.4 | normal | DeFi | - | n | n | 0 |
| USDF | 0.3 | stablecoin | - | - | n | n | 0 |
| WLD | 222.5 | normal | AI (P) | - | y | y | 3 |
| DOT | 132.3 | normal | Layer 1 (P) | - | y | y | 3 |
| PAXG | 43.4 | normal | Real-world assets | Majors | n | y | 2 |
| WLFI | 13.7 | normal | DeFi (P?) | - | n | n | 0 |
| M | 1.0 | normal | - | - | n | n | 0 |
| USDD | 2.2 | stablecoin | - | - | n | n | 0 |
| MNT | 19.2 | normal | Layer 2 | - | n | y | 2 |
| EURSAFO | 0.0 | tokenized fund | - | - | n | n | 0 |
| MORPHO | 17.5 | normal | DeFi | - | n | y | 2 |
| PEPE | 155.8 | normal | Memecoins | - | y | y | 2 |
| SKY | 5.9 | normal | DeFi | - | n | n | 0 |
| ICP | 37.3 | normal | Layer 1 | AI | y | y | 2 |
| U | 88.8 | stablecoin? | - | - | n | n | 0 |
| HTX | 67.5 | exchange token | Exchange tokens (P) | - | n | n | 0 |
| BFUSD | 0.6 | stablecoin | - | - | n | n | 0 |
| BGB | 9.0 | exchange token | Exchange tokens (P) | - | n | y | 1 |
| USDGO | 9.2 | stablecoin | - | - | n | n | 0 |
| ARB | 108.1 | normal | Layer 2 | - | n | y | 2 |
| ETC | 42.6 | normal | Layer 1 | - | y | y | 3 |
| JST | 21.8 | normal | DeFi | - | n | n | 0 |
| VVV | 13.6 | normal | AI | - | n | n | 0 |
| GT | 1.0 | exchange token | Exchange tokens (P) | - | n | n | 0 |
| KCS | 58.0 | exchange token | Exchange tokens (P) | - | n | n | 0 |
| ALGO | 40.0 | normal | Layer 1 | - | y | y | 3 |
| KAS | 8.8 | normal | Layer 1 | - | y | y | 3 |
| POL | 45.8 | normal | Layer 2 | - | y | y | 3 |
| BCAP | 0.0 | tokenized fund | - | - | n | n | 0 |
| JUP | 44.1 | normal | DeFi | - | n | y | 2 |
| RENDER | 44.7 | normal | AI | - | n | y | 2 |
| ATOM | 35.0 | normal | Layer 1 (P) | - | y | y | 2 |
| PI | 2.6 | normal | Layer 1 | - | n | n | 0 |
| FIL | 138.1 | normal | Infrastructure (P) | - | y | y | 3 |
| OUSD | 0.2 | stablecoin | - | - | n | n | 0 |
| USTB | 0.0 | tokenized fund | - | - | n | n | 0 |
| AERO | 33.8 | normal | DeFi | - | n | y | 2 |
| INJ | 117.9 | normal | Layer 1 | DeFi | n | y | 2 |
| NEXO | 3.0 | normal | DeFi (P?) | - | n | n | 0 |
| LIT | 48.1 | normal | DeFi | - | n | n | 0 |
| ZRO | 60.9 | normal | Infrastructure (P) | - | n | y | 2 |
| GHO | 1.0 | stablecoin | - | - | n | n | 0 |
| PRL | 8.7 | normal | AI (C?) | - | n | n | 0 |
| APT | 62.2 | normal | Layer 1 | - | n | y | 2 |
| CAKE | 64.1 | normal | DeFi | - | y | y | 3 |
| AKE | 8.1 | normal | AI (C?) | - | n | n | 0 |
| STX | 15.6 | normal | Layer 2 | - | y | y | 2 |
| STABLE | 7.2 | normal | Payments (P?) | - | n | n | 0 |
| XDC | 9.0 | normal | Real-world assets | Layer 1 | n | y | 1 |
| NIGHT | 11.9 | normal | Privacy (P?) | - | n | n | 0 |
| EUTBL | 0.0 | tokenized fund | - | - | n | n | 0 |

**2a. Coins per proposed narrative** (primary + second; 76 in-scope coins, 75 with a proposal):

| Narrative | Coins | Count | Note |
|---|---|---|---|
| Layer 1 | ETH(2) XRP(2) SOL TRX HYPE(2) ADA NEAR AVAX CC SUI HBAR GRAM? DOT ICP ETC ALGO KAS ATOM PI INJ APT XDC(2) XLM(2) | 23 | large; fine |
| DeFi | HYPE LINK(2) RAIN? UNI BTW? ENA AAVE ONDO(2) PUMP(2) ASTER WLFI? MORPHO SKY JST JUP AERO INJ(2) NEXO? LIT CAKE | 20 | large; fine |
| Exchange tokens | BNB WBT LEO CRO OKB HTX BGB GT KCS | 9 | ok |
| AI | NEAR(2) TAO WLD ICP(2) VVV RENDER PRL? AKE? | 8 (6 primary) | ok |
| Payments | XRP XLM BCH LTC STABLE? | 5 | ok |
| Majors / store of value | BTC ETH PAXG(2) XAUT(2) | 4 (2 primary) | **only 2 primary**: BTC, ETH. Counts 4 only if "second" counts: see Q3 |
| Memecoins | DOGE SHIB PEPE PUMP | 4 | ok |
| Infrastructure | LINK QNT FIL ZRO | 4 | absorbs Oracles (LINK; PYTH not in top 100 today) |
| Real-world assets | ONDO XDC PAXG XAUT | 4 | |
| Layer 2 | MNT ARB POL STX | 4 | |
| Privacy | ZEC XMR NIGHT? | 3 | at the minimum; NIGHT is UNVERIFIED, so 2 verified |
| Gaming and metaverse | none | **0** | AXS SAND MANA GALA IMX are not in today's top 100 (the `gaming` category list has no snapshot member). **Under 3: propose keeping the id in config but hiding it while < 3 coins (shown as "0 coins today"), or dropping it.** |

Oracles today: 1 coin (LINK) in the snapshot, confirming the merge into Infrastructure. **Coins with no narrative proposal: M** (categories say L1/Meme/AI at once, i.e. noise; not known what it is: UNVERIFIED). Category data alone is unreliable: it tags BTC only as L1, gives ZEC "L1 + Privacy", puts 8 yield-bearing dollars under DeFi/RWA, and `layer-1`/`layer-2`/`artificial-intelligence` each return exactly 99-100 members because the fetch is the category's own top 100 (`coingecko_attention.py:104`), not membership of our top 100. So `narratives.json` must be a hand-edited file seeded from this table, with CoinGecko categories only as a hint.

## 3. Why 47 of 103 coins have no CoinGecko series (T97)

**Evidence.** `probe_records.json`: coingecko `coins_checked` 103, `coins_ok` 56, `max_days` 100, as of 2026-10-18. 103 is the number of keys in `api/data/wiki_articles.json`; the refresh takes its symbol list from those keys (`refresh_attention.py:115-121`, `_symbols`), not from the universe. The CoinGecko runner then builds `ids` from `fetch_top100` of **today** (`refresh_attention.py:134-137`), which strips stablecoins and wrapped coins (`coingecko_attention.py:65`), and **silently skips any symbol not in `ids`** (`refresh_attention.py:139`, `... if s in ids else None`; `_collect` drops `None`, `:61-62`), so no row, no "capped" state.

Reconciliation against the committed data: 103 keys; **48 are not in today's top 100** (e.g. TON, VET, MKR, FET, TIA, SEI, FLOKI, WIF, BONK...), of which 2 (PYTH, TIA) still have a stored series from an older day, so **46 have none**; **1 more is USDT**, a stablecoin that `fetch_top100` removes: 46 + 1 = **47 = 103 - 56**. All 54 in-snapshot keys that were fetched have the full 100 days (`ok`), so there is **no rate-limit or history-gap signature in the stored result**. The reverse gap is bigger: **45 of today's 100 snapshot symbols are not in `wiki_articles.json` at all** (SUI is a key; AKE, ASTER, PUMP, WLFI, STABLE, NIGHT, USDG... are not), so they are never requested for CoinGecko or Wikipedia either.

**Cause: missing id mapping from a stale symbol list (keys of the Wikipedia file), not a rate limit.** UNVERIFIED: earlier runs may have hit HTTP 429 (pace 6 s per call, `coingecko_attention.py:23`; 100 series = about 10 minutes of pacing alone); the committed state cannot show it, and the run log is not in the repo.

**Proposed fix (slice U4, no code now).** (1) Symbol list for the CoinGecko and Wikipedia runners = in-universe symbols from the universe snapshot (`universe_store.read_latest`, which already stores `id`), not the keys of `wiki_articles.json`; (2) `id` from the snapshot row, so no extra markets call and no stablecoin filter side effect; (3) report skipped-for-missing-id as a counted outcome (`no-id`) in `outcome_summary` (`refresh_attention.py:49`) instead of dropping silently; (4) budget: either raise the per-run cap or fetch only symbols whose series is shorter than 100 days or whose last day is stale (incremental), to fit the job time; (5) live check after: expect `coins_ok` near the in-scope count.

## 4. Tradeability test design

Rule: a coin is tradeable iff it has a market on at least one of Binance, Coinbase, Kraken, Hyperliquid (spot or perp), USD, USDT or USDC quote. Evidence available in the repo today, all weak:

| Venue | What exists | Use |
|---|---|---|
| Hyperliquid | daily active-perp name list `api/data/cache/narrative/exchange/markets/2026-10-18.json`: 178 base names, **54 in the 100 snapshot**; plus 73 `hyperliquid_volume` parquets, 45 in the snapshot | positive evidence. Names like `kPEPE`/`kSHIB` are scaled (`hyperliquid_narrative_adapter.py:19`); PEPE and SHIB show as absent from the list: **alias handling needed (UNVERIFIED)** |
| Binance | `exchange_volume.fetch_binance_series` tries `<SYM>/USDT` (`exchange_volume.py:44`); no stored series is committed; Binance reached over ccxt may be blocked from US runners (HTTP 451, referenced in the weighted-signal SPEC decision 9) | a successful series proves a USDT market; the run itself is UNVERIFIED |
| Coinbase, Kraken | no adapter (W7) | none; **UNVERIFIED** until built |

Design: `tradeable_markets.py` builds, per refresh, `{symbol: {binance, hyperliquid, coinbase, kraken}}` from a market-list call per venue (ccxt `load_markets`, one call each, no per-coin history), stored beside the universe snapshot (dated, newest kept). Coin is tradeable if any flag is true. Rules in the config: `force_include` (coin counts as tradeable regardless; for example a listing the lists miss or an alias like PEPE) and `not_tradeable` (coin excluded with the owner's reason string, wins over `force_include` only if both present, to be reported as a config error instead). If a venue list failed to fetch, that venue is "unknown", never "false"; a coin with every venue unknown stays IN with status `tradeability-unverified`. Until a live run, the repo can only show Hyperliquid-positive coins: 54 of 100; the remaining in-scope coins are UNVERIFIED, not excluded. Tokenized funds (USDY BUIDL USYC USTB EUTBL EURSAFO BCAP FIGR_HELOC) are the expected "no market" cases; also UNVERIFIED until the live lists are read.

## 5. Config design

**`api/data/narratives.json`** (new; hand-edited, the owner's list):
```
{"narratives": [{"id": "layer-1", "name": "Layer 1", "coins": [{"symbol": "SOL", "primary": true}, {"symbol": "ETH", "primary": false}]}, ...]}
```
Validation at load (a failure raises with the narrative and symbol, like `validate_config`, `discovery.py:47`): ids unique; each narrative has >= `min_coins` (3) coins **among the current in-universe coins** (below it: marked `hidden: too-few-coins`, not an error, because market moves change membership); each coin has exactly one `primary: true` across all narratives and at most one non-primary membership (two narratives max); every in-universe, tradeable coin appears at least once (a coverage error lists the missing symbols); symbols uppercase and unique inside a narrative. Relation to today: `discovery.json` `categories` (9 CoinGecko ids, `discovery.json:41-51`) is replaced by `narratives.json`; the CoinGecko categories snapshot stays only as a hint for seeding. Name clash: `api/data/narratives.json` already exists (2,263 bytes, the older narrative RFC-2 file, not read here: UNVERIFIED what it holds); use a different name, e.g. `attention_narratives.json`, unless the owner prefers a rename (Q5).

**`universe_rules`** (in `discovery.json`, replacing `min_volume_24h_usd`, `exclude`, `exclude_category_ids`, `include_despite_category`): `backup_floor_usd` (proposal 5,000,000), `thin_volume_label_below_usd` (proposal 20,000,000, label only), `exclude_classes` (`stablecoin`, `wrapped_staked`, `tokenized_fund_no_market`), `classes` (symbol lists per class, replacing the lists in `attention_universe.json`; exchange tokens are no longer an exclusion), `not_tradeable`, `force_include`. A coin under the backup floor is cut with reason `volume-below-floor` unless in `force_include`.

**Discovery eligibility becomes:** universe (top 100) → class exclusions → tradeability → backup floor (or `force_include`) → narrative membership. Each removal is recorded with a reason string. The category-based exclusion (step 5 above) disappears.

**Response fields (additive, `api/models/discovery.py` UNVERIFIED not read):** `universe_size` (100), `shown_size`, `excluded: [{symbol, reason, detail}]` with reasons `stablecoin | wrapped-staked | no-market | not-tradeable-config | volume-below-floor | no-narrative`, `excluded_counts: {reason: n}`, per coin `thin_volume: bool`, `volume_24h`, `data_quality: normal | low-data` with `low_data_reason`, and per narrative `hidden`/`coins_used`. The web line: "N of 100 shown, M excluded: 16 stablecoins, 8 no market, ...".

**Interactions (not fixed here; UNVERIFIED, I did not read PR #140 or T107):** T106 (PR #140) adds a `min_category_coins=3` rule and a sources panel: the narrative minimum overlaps and must have one owner (proposal: `narratives.json` validation, `min_category_coins` removed or defaulting to it); the sources panel needs the new low-data reasons. T107 (chart panels) and the stored signal snapshots key by CoinGecko category id (`cache/attention/signals/*` holds `layer-1`, `meme-token`, ...): renaming ids needs a migration or a mapping, or history for `meme-token` etc. is orphaned.

## 6. Acceptance criteria

- **AC-U1** `narratives.json` loads; a duplicate primary, a narrative with < 3 in-universe coins, or an uncovered in-universe coin is reported by name (unit test per case).
- **AC-U2** Every in-universe coin is in exactly one primary narrative and at most one second; BNB/LEO/OKB appear under "Exchange tokens".
- **AC-U3** Discovery eligibility no longer reads `exclude_category_ids`; UNI, JUP, AERO, CAKE, HYPE are eligible on the 2026-10-18 snapshot (fixture test).
- **AC-U4** With the 2026-10-18 snapshot, classification yields stablecoin 16, tokenized fund 8, exchange token 9 (these counts asserted in a test against the committed fixture; USDG, RLUSD, U are stablecoins).
- **AC-U5** Every excluded coin has a reason from the closed list; `excluded_counts` sums to `universe_size - shown_size`.
- **AC-U6** The 20M floor is gone; a coin below `backup_floor_usd` and not in `force_include` is excluded with `volume-below-floor`; a coin between floor and `thin_volume_label_below_usd` is shown with `thin_volume: true`.
- **AC-U7** `force_include`/`not_tradeable` override tradeability; a symbol in both is a config error.
- **AC-U8** A venue list that failed is "unknown", not "no market" (test with one failing venue).
- **AC-U9** A coin with no usable attention source stays shown with `data_quality: low-data` and a reason; never dropped, never scored 0.
- **AC-U10** The web shows "N of 100 shown, M excluded" with the reasons (U3).
- **AC-U11** CoinGecko runner covers every in-universe symbol that has an `id` in the snapshot; a missing id is a counted `no-id` outcome (U4).
- **AC-U12** A superseding decision (D-20 reversed) is recorded in `decisions.md`.

## 7. Out of scope

Coinbase and Kraken adapters (W7); Google Trends by coin name and Reddit per coin (later slice); changing source weights; the history chart; live provider calls; the Wikipedia article mapping for the 45 snapshot coins not in `wiki_articles.json` beyond using the T99/T102 candidates (`wiki_articles_candidates.json` holds 7: SUI APT ARB TAO RENDER INJ QNT, not yet applied); trading signals or order logic; any code edit in this task.

## 8. Proposed slices

| Slice | Content | Files | Tier | Rough USD |
|---|---|---|---|---|
| U1 | `narratives.json` + loader + validation; Discovery reads narratives, not CoinGecko categories | new JSON + loader, `discovery.py`, `discovery.json`, tests | RT1 | 1.5 |
| U2 | classification (`classes`), exclusion reasons, backup floor, `thin_volume`, drop exchange-token and category exclusion; supersede D-20 | `universe.py`, `discovery.py`, `discovery.json`, `attention_universe.json`, `models/discovery.py`, `decisions.md`, tests | RT1-RT2 | 2.0 |
| U3 | web: "N of 100 shown, M excluded", reasons, thin label | `web/` | RT2 | 1.5 |
| U4 | CoinGecko/Wikipedia symbol list from the universe, id from snapshot, `no-id` outcome, pacing budget | `refresh_attention.py`, `coingecko_attention.py`, tests; live run RT3 | RT1 + RT3 | 1.5 |
| U5 | per-coin source ladder and low-data reasons; tradeability lists per venue (Hyperliquid, Binance first) | `discovery.py`, new `tradeable_markets.py` | RT1-RT3 | 2.0 |
| later | Trends keyword = full coin name; Coinbase/Kraken adapters | | | |

Order: U1 and U4 can run in parallel; U2 after U1; U3 after U2; U5 after U2. Dollar figures are guesses.

## 9. Risks

- Category data is wrong for the owner's purpose (Section 2): the hand-edited file is the only reliable source, and 14 coins in my table are **?** or **(P)** and need owner review.
- Top 100 changes daily; a narrative may fall under 3 coins overnight (hidden, not a crash) and new coins appear uncovered (a coverage error would fail the page: prefer an "unassigned" bucket with an alert; Q6).
- Reversing D-20: LEO, CRO, GT, BGB, KCS are thin on CoinGecko volume (0.2-9M) and likely have thin real attention data; they will mostly be "low data".
- CoinGecko `total_volume` for tokenized funds is 0 or null: a floor alone would cut them, but so would a real-but-unlisted coin; the thin label avoids hiding.
- Renaming category ids orphans stored signal history (Section 5).
- Live-only unknowns: Binance reachability from the runner, Coinbase/Kraken lists, `PEPE`/`SHIB` Hyperliquid aliases, whether earlier CoinGecko runs hit 429.

## 10. Open questions for the owner (not decided here)

1. **Backup floor level.** Counts of in-scope coins cut: 5M cuts 5 (LEO CRO GT PI NEXO), 10M cuts 13, 20M cuts 21. Proposal 5M; but 3 of those 5 are exchange tokens you want IN: also `force_include` them, or no floor for exchange tokens?
2. **Final narrative list.** Keep all 12? Gaming has 0 coins today (hide or drop?), Privacy sits at the minimum 3 (one UNVERIFIED), Majors has 2 primary coins.
3. **Does "at least 3 coins" count second memberships?** (Majors reaches 4 only with PAXG and XAUT as seconds.)
4. **Tokenized treasuries and funds** (BUIDL, USYC, USTB, USDY...): confirm they are OUT as "no market" and not shown with a "fund" label.
5. **File name:** `narratives.json` already exists in `api/data/` (older RFC-2 file); new name or rename?
6. **A new top-100 coin with no narrative:** show it in an "Unassigned" bucket, or hide until you assign it?
7. **`not_tradeable` / `force_include` starting entries:** suggestions only: `force_include`: LEO, CRO, GT (thin), PEPE, SHIB (alias); `not_tradeable`: none yet. Your call.
8. **Doubtful coins** to confirm: HYPE (DeFi or Exchange token?), NEXO (DeFi or Exchange token?), PUMP (Memecoin or DeFi?), WBT/HTX as exchange tokens, XRP (Payments or Majors?), the unknown tickers M, U, GRAM, BTW, AKE, PRL, RAIN, STABLE, NIGHT, WLFI.
