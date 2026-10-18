---
name: plan:narrative-baskets-universe-narratives
description: "T111 PLAN, validated by T112 on main b61bdf9: tradeable universe (top 100, reasoned exclusions, label-only volume) and 11 hand-edited attention narratives with unlimited memberships. Slices U1-U6 with corrected file:line cites, the real state of #139/#140/#141, response contract, Validate Contract with baselines and gates. Docs only; no code changed."
date: 18-10-26
feature: narrative-baskets
metadata:
  node_type: memory
  type: plan
---

# Universe and narratives: PLAN (slices U1-U6)

[MODE: VALIDATE]

Date: 18-10-26
Complexity: COMPLEX (6 slices, 3 waves)
Status: VALIDATED: Gate: PASS
Validation: T112, 18-10-26, on `main` b61bdf9 (PRs #137, #139, #140, #141, #142 all merged). The T111 draft was written against 8f2bf4b and had stale cites and one stale premise; every correction is in "Validation record" at the end. The Validate Contract below carries the baselines and gates. Next step: the owner's ENTER EXECUTE MODE, then U1 and U4.

**Summary:** **SPEC:** `narrative-baskets-universe-narratives_SPEC_18-10-26.md` (T108, merged as #141). **Base read (VALIDATE):** `main` at b61bdf9. **#139 (T107 chart panels) and #140 (T106 `min_category_coins`, sources route and panel, `excluded` counts object) ARE merged.** The first draft of this PLAN said they were not; that was wrong for main today. Consequences, all handled below: `min_category_coins` exists in config, validation, response, web and about 12 tests (U1 owns its move to `universe_rules.min_narrative_coins`); `GET /api/narrative/sources` and `DiscoverySourcesPanel.tsx` exist and call `eligibility()` (U2 and U5 own the edits); the response already has an `excluded` OBJECT of four counts that the web reads (the new reasoned list gets a new name, `excluded_coins`, see section 3); the nightly workflow runs `refresh_attention.py --sources categories`, which reads two config keys this PLAN removes (U1 and U2 own that fix). Every file:line cite below is `main` b61bdf9.

## Overview and Context

Context router: `process/context/all-context.md`; tests: `process/context/tests/all-tests.md`. Next step: the owner's ENTER EXECUTE MODE (RIPER-5); VALIDATE is done (T112, see the Validate Contract). Phase Completion Rules: a slice is done when its red tests are green, its Acceptance Criteria below hold, and its report lists the owner probes.

## 1. Goal and non-goals

**Goal:** Discovery shows ATTENTION on coins the owner can trade. Universe = top 100 by market cap; each coin is IN or OUT with a visible reason; every IN coin sits in one or more of 11 owner-reviewed narratives; no coin is cut for volume or for lack of data.

**Non-goals:** Coinbase and Kraken adapters (W7); Trends by coin name and Reddit per coin beyond the ladder wiring point; changing source weights; trading logic; live provider calls; editing `api/data/narratives.json` (older RFC-2 file), `api/data/narrative_categories.json`, `narrative_category_map.json`; rewriting any frozen file under `api/data/cache/attention/signals/`; any `.github/` change.

## 2. Overrides of the SPEC (owner decisions 18-10-26, binding)

| # | Owner decision | SPEC text it overrides | Effect in this PLAN |
|---|---|---|---|
| 1 | Goal = attention on tradeable coins; top 100 | none (confirms SPEC 0) | universe stays `TOP_N=100` (`universe.py:222`) |
| 2 | OUT with shown reason: stablecoins (16 today incl. USDG RLUSD U), tokenized funds as `no-market`, wrapped/staked/bridged, no market on Binance/Coinbase/Kraken/Hyperliquid. Failed venue list = `unknown`, coin stays as `tradeability-unverified` | SPEC 4 (kept), Q4 settled | closed reason list in U2; `unknown` rule = AC-U8 |
| 3 | NO volume floor, NO volume cut; volume only adds `thin volume` label under 20M; null/zero volume never excludes | SPEC 0/5 backup floor 5M, `volume-below-floor`, **AC-U6**, Q1 | `backup_floor_usd` removed from the design; `thin_volume_label_below_usd`=20,000,000; LEO CRO GT PI NEXO need no `force_include` |
| 4 | Exchange tokens IN as a narrative | reverses D-20 (`decisions.md:180`) | superseding entry text in section 6; written in U6 |
| 5 | 11 narratives; Gaming dropped; Oracles merged into Infrastructure; owner placements HYPE, PUMP, NEXO, XRP | SPEC 2a (12 narratives, HYPE=DeFi, PUMP=Memecoins, XRP=Payments), Q2, Q8 | section 5 list |
| 6 | A coin may belong to ANY number of narratives; every membership counts to the 3-minimum; exactly one `primary` per coin | SPEC 5 "at most one non-primary", **AC-U2**, Q3 | validation in U1; aggregates count a coin in each narrative (as `discovery.py:9`) |
| 7 | < 3 in-universe coins = hidden, not an error; new top-100 coin with no narrative = `Unassigned` bucket, flagged | SPEC 5 coverage error, Q6 | no load error; `unassigned` list in the response |
| 8 | New file `api/data/attention_narratives.json` | SPEC Q5 | `api/data/narratives.json` untouched |
| 9 | No usable source: never cut; ladder volume (exchange composite, else CoinGecko) > Wikipedia > Trends (full coin name, later) > Reddit > `low data` + reason | AC-U9 (kept, sharpened) | U5 |
| 10 | Unknown tickers M U GRAM BTW AKE PRL RAIN STABLE NIGHT WLFI per SPEC proposals, UNVERIFIED; owner reviews the full coin list ONCE before it goes live | SPEC 8 Q8 | **Gate G-OWN** (section 4) |
| 11 | T106/T107 interaction: decide ownership and snapshot migration | SPEC 5 "Interactions" (open) | section 7 |

Superseded SPEC items: AC-U1, AC-U2, AC-U6 are rewritten in section 8; Q1-Q8 are all answered by the table above except the NEXO final pick (SPEC proposal DeFi; owner allows Exchange tokens or DeFi, see U1 file note).

## 3. Design (what changes, verified against main b61bdf9)

- **Eligibility today** (`discovery.py:158-204`): `_volumes` 158-160 reads `volume_24h` from the newest universe snapshot; `_excluded_symbols` 163-168 reads `exclude`, `exclude_category_ids`, `include_despite_category`; `eligibility` 175-183 applies the `min_volume_24h_usd` floor (null volume fails); `_excluded_counts` 186-204 builds the `excluded` object (`exclusion_list`, `below_volume_floor`, `no_category`, `no_source_data`, `models/discovery.py:39-44`) and reads `cfg["categories"]` at 190. `load_universe` (`universe.py:23-43`, `TOP_N=100` at 14) drops the lists `stablecoins`, `wrapped`, `exchange_tokens` of `attention_universe.json` silently and returns bare symbols. `build_discovery` (207-249) loops `cfg["categories"]` at 232 and drops a coin with no usable source at 233 (`and coins[s]`).
- **New eligibility** (replaces the above, U2): top-100 snapshot rows (symbol, `id`, `market_cap`, `volume_24h`) -> class exclusion (stablecoin, wrapped-staked, tokenized fund; reason recorded) -> tradeability (`tradeable` / `no-market` / `unknown`) -> IN. Volume only sets `thin_volume`. Narrative membership comes from `attention_narratives.json`, never from CoinGecko categories.
- **Config** (`discovery.json`). U1 removes `categories` (the array at the end) and the top-level `min_category_coins` (line 25) and adds `universe_rules: {"min_narrative_coins": 3}`. U2 removes `min_volume_24h_usd`, `exclude`, `exclude_category_ids`, `include_despite_category` and adds to `universe_rules`: `thin_volume_label_below_usd` 20000000, `classes` (symbol lists `stablecoin`, `wrapped_staked`, `tokenized_fund`), `not_tradeable` {symbol: reason}, `force_include` [symbols]. `validate_config` (`discovery.py:47-59`) rejects every removed key with a clear message (a stale local copy fails loudly). A symbol in both `force_include` and `not_tradeable` is a config error (AC-U7). **`attention_universe.json` is NOT edited by this PLAN** (see Q-V1 below): the Baskets tab reads it through `load_reference` (`basket.py:9,75`).
- **Narratives file** `api/data/attention_narratives.json`: `{"status": "proposed"|"reviewed", "as_of": "YYYY-MM-DD", "narratives": [{"id","name","coins":[{"symbol","primary"}]}]}`. `as_of` is new (the first draft had no date to put in `categories_as_of`). Validation (raises, naming narrative and symbol): ids unique and match `^[a-z0-9-]{1,40}$`; symbols match `^[A-Z0-9_]{1,24}$` and are unique per narrative; each symbol has exactly one `primary: true` across all narratives; `as_of` is an ISO date; `status` is one of two values. NOT an error: fewer than `min_narrative_coins` in-universe coins (hidden), an in-universe coin with no entry (goes to `unassigned`). The symbol regex is a trust boundary: `store.store_path` (`api/data/attention/store.py:18-19`) builds `<cache>/attention/<source>/<SYMBOL>.parquet` from the symbol with no sanitising.
- **Two thresholds, one value.** `universe_rules.min_narrative_coins` (3) decides HIDDEN (fewer than 3 member coins in the universe: not listed in the table, listed under `hidden_narratives`). `ranked` (`discovery.py:243`, `len(rows) >= min_coins`) stays as today: a visible narrative with fewer than 3 coins WITH DATA is listed as "too few coins to rank" (`DiscoveryTable.tsx:138-151`). Both read the same value; the response field `min_category_coins` keeps its name (the web reads it at `DiscoveryTab.tsx:107`) and is filled from `min_narrative_coins`.
- **Ladder meaning (decision 9).** Scoring stays the weighted mean of the sources that have data (`discovery._coin` 125-146; weights unchanged by non-goal). The ladder (volume > Wikipedia > Trends > Reddit) fixes the ORDER in which the `low_data_reason` text names what is missing and which volume source feeds the exchange slot (exchange composite, else CoinGecko: `discovery.py:132-135`). It does not change scores.
- **Response contract (frozen here so U3 can code against it while U5 is built).** Everything is additive except the one rename noted. `categories` keeps its JSON name and carries narratives.

| Field | Type | Slice | Note |
|---|---|---|---|
| `narratives_status` | `"proposed"` or `"reviewed"` | U1 | from the file; web banner while `proposed` |
| `categories_as_of` | string | U1 | the narratives file `as_of` (today: categories snapshot date) |
| `min_category_coins` | int | U1 | name kept; value = `universe_rules.min_narrative_coins` |
| `unassigned` | list of symbol | U1 | IN coins with no narrative |
| `hidden_narratives` | list of {id, name, coins: [symbol]} | U1 | fewer than `min_narrative_coins` member coins |
| per coin `primary` | bool | U1 | this narrative is the coin's primary one (replaces the undefined "memberships flag" of the first draft) |
| history `membership_as_of` | string | U1 | on `DiscoveryCategoryHistory`: the membership used for EVERY day of the chart is the one dated here (see U1 migration) |
| `universe_size` | int, 100 on a full snapshot | U2 | today `len(load_universe)` = the list-filtered count |
| `shown_size` | int | U2 | distinct coins in visible narratives |
| `excluded_coins` | list of {symbol, reason, detail} | U2 | NEW NAME. `excluded` (the object) stays |
| `excluded_counts` | dict reason -> int | U2 | `shown_size + sum(excluded_counts) = universe_size` (AC-U5) |
| `excluded` | OBJECT of 4 counts (unchanged shape) | U2 | kept, deprecated, filled for the old web: `exclusion_list` = stablecoin + wrapped-staked + no-market + not-tradeable-config; `below_volume_floor` = 0; `no_category` = unassigned + hidden-narrative; `no_source_data` = no-source-data. Removal is a follow-up after U3 (section 10) |
| per coin `thin_volume`, `volume_24h`, `tradeability` (`tradeable`/`unverified`) | bool, float or null, str | U2 | |
| per coin `data_quality` (`normal`/`low-data`), `low_data_reason` | str, str | U5 | `low-data` = no usable source, `covered_weight` 0, `change` and `raw_change` null (`web/lib/types/discovery.ts:16-17` already allow null; `models/discovery.py:20-21` change to `float | None`) |

- **Closed reason list for `excluded_coins`/`excluded_counts`:** `stablecoin`, `wrapped-staked`, `no-market`, `not-tradeable-config`, `unassigned`, `hidden-narrative` (IN coin that sits only in hidden narratives), and, until U5 ships, `no-source-data` (today's drop at `discovery.py:233`; U5 makes it 0 and a test pins it). The first draft's AC-U5 identity could not hold without `unassigned`, `hidden-narrative` and the interim `no-source-data`.
- **Config hash and narratives.** `config_hash` (`signal_snapshots.py:50-51`) covers `cfg` only. The narratives file is not in `cfg`, so a membership edit would not change the hash. U1 adds the file's sha256 prefix (`narratives_sha`) to each new record and folds it into `current_hash`.
- **Q-V1 (owner, non-blocking, default applied).** The Baskets tab ranks against `load_reference` = top 100 minus the three lists of `attention_universe.json`, exchange tokens included. Decision 4 reverses D-20 for Discovery. To avoid a silent change of Baskets scores, this PLAN leaves `attention_universe.json`, `load_universe` and `load_reference` byte-identical in behaviour and adds a new row-based loader for Discovery. If the owner wants Baskets to follow the new universe, that is a separate task.

## 4. Slices, order, gates

| Slice | Wave | Parallel with | Model | Tier | Est. USD | Touches `.github/` |
|---|---|---|---|---|---|---|
| U1 narratives file + loader + Discovery reads it + snapshot-id mapping | 1 | U4 | opus (code) | RT3 | 3.0 | NO |
| U4 CoinGecko/Wikipedia symbol list from the universe | 1 | U1 | opus | RT2 (RT3 live probe by owner) | 2.0 | NO |
| U2 classes, reasons, tradeability stub, label-only volume | 2 | none (shares `discovery.py`) | opus | RT3 | 3.5 | NO |
| U3 web: counts line, reasons, thin label, Unassigned, hidden, banner | 3 | U5, U6 | opus | RT1 (+ hybrid e2e fixture) | 2.5 | NO |
| U5 source ladder, low-data rows, venue lists | 3 | U3, U6 | opus | RT3 | 3.0 | NO |
| U6 D-20 supersede, decisions.md, docs | 3 (any time after U1) | U3, U5 | sonnet (non-code) | RT0 | 0.5 | NO |

Total about 14.5 USD (first draft 13; the extra scope is the `refresh_attention.py` categories runner, `sources.py`, the router contract test and the Baskets guard). The planner states the real ceiling. If it is below the total, defer U5's venue-list part   to a later task: U5 still ships the low-data rows. Per-slice cap 15, ask at 7. Max 2 workers at a time.

**Order:** U1 || U4 -> U2 -> (U3 || U5 || U6). U2 starts once U1 is merged, whatever the narratives `status` says: the first draft said both "G-OWN blocks U2" (section 4 order line) and "U2 and U3 may be coded against `proposed`" (G-OWN paragraph); the second reading is kept because `status` changes no code path. G-OWN blocks only U3's merge and any "live" claim.

**G-OWN (owner gate, blocking for U3 merge and "live"):** U1 ships `attention_narratives.json` with `"status": "proposed"` and a rendered coin-to-narrative table in the U1 report (generated from the file, checked against the 2026-10-18 snapshot: 75 of the 76 non-stablecoin, non-fund coins are placed, `M` is unassigned). The owner reviews the COMPLETE list once and flips it to `"reviewed"` (or sends edits). The API serves a `proposed` file with `narratives_status: "proposed"`. AC-N1 tests the flag.

### File ownership and collision proof

| File | U1 | U4 | U2 | U3 | U5 | U6 |
|---|---|---|---|---|---|---|
| `api/analytics/attention/discovery.py` | edit | - | edit | - | edit | - |
| `api/analytics/attention/discovery_history.py` | edit | - | edit | - | - | - |
| `api/analytics/attention/signal_snapshots.py` | edit | - | - | - | edit (`_record` low-data row) | - |
| `api/analytics/attention/sources.py` | - | - | edit | - | edit | - |
| `api/analytics/attention/universe.py` | - | - | edit (add only) | - | - | - |
| `api/analytics/attention/narratives.py` | create | - | - | - | - | - |
| `api/analytics/attention/universe_classes.py` | - | - | create | - | - | - |
| `api/models/discovery.py` | edit | - | edit | - | edit | - |
| `api/data/discovery.json` | edit | - | edit | - | - | - |
| `api/data/attention_narratives.json`, `attention_narrative_id_map.json` | create | - | - | - | - | - |
| `api/data/attention/tradeable_markets.py` | - | - | - | - | create | - |
| `api/scripts/refresh_attention.py` | `_run_categories` hunk 181-192 | `_outcome` 41-47, `OUTCOME_ORDER` 38, `_symbols` 115-121, `_run_coingecko` 133-139 | `_run_categories` hunk (drop `exclude_category_ids`) | - | new venue step only | - |
| `api/data/attention/coingecko_attention.py` | - | only if `id` passthrough is needed | - | - | - | - |
| `api/tests/scripts/test_refresh_attention.py` | categories tests 159-195 | new tests appended | categories test (ids) | - | venue-step tests | - |
| `api/tests/analytics/attention/test_discovery.py`, `test_discovery_history.py`, `test_sources.py`, `api/tests/routers/test_discovery.py`, `test_discovery_history.py` | edit | - | edit | - | edit | - |
| `api/tests/analytics/attention/test_signal_snapshots.py` | edit | - | - | - | edit | - |
| `api/tests/analytics/attention/test_universe.py` | - | - | edit (add) | - | - | - |
| `web/components/narrative/Discovery*.tsx`, `web/lib/types/discovery.ts`, `__tests__/DiscoveryTab.test.tsx`, `web/e2e/narrative.spec.ts` | - | - | - | edit | - | - |
| `process/context/decisions.md` (+ context docs if they cite the lists) | - | - | - | - | - | edit |

Parallel pairs and why they are safe: **U1 || U4** share only `refresh_attention.py` and `test_refresh_attention.py`, in disjoint hunks (U1: lines 181-192 and the categories tests at 159-195; U4: lines 38-56, 115-139 and appended tests). Merge U4 first (smaller), U1 rebases. **U3 || U5 || U6** share no file (U3 web only; U5 API only; U6 docs only). U2 runs alone because U1, U2 and U5 all edit `discovery.py`, `models/discovery.py` and the router contract test, in that order.

## 5. The 11 narratives (proposal, owner-reviewed at G-OWN)

Ids: `majors-store-of-value`, `layer-1`, `layer-2`, `defi`, `memecoins`, `ai-data-compute`, `real-world-assets`, `privacy`, `payments-settlement`, `infrastructure`, `exchange-tokens`. Starting memberships from SPEC section 2 with the owner overrides applied (every UNVERIFIED mark kept in a `note` field, not in code paths):

| Narrative | Primary members | Extra (non-primary) memberships |
|---|---|---|
| Majors / store of value | BTC ETH XRP | XAUT PAXG (primary RWA) |
| Layer 1 | SOL TRX ADA AVAX CC SUI HBAR DOT ETC ALGO KAS ATOM PI APT GRAM? | ETH XRP HYPE NEAR ICP INJ XDC |
| Layer 2 | MNT ARB POL STX | |
| DeFi | UNI ENA AAVE ASTER MORPHO SKY JST JUP AERO LIT CAKE RAIN? BTW? WLFI? | HYPE LINK ONDO INJ NEXO? |
| Memecoins | DOGE SHIB PEPE | PUMP |
| AI and data/compute | TAO WLD RENDER VVV PRL? AKE? | NEAR ICP |
| Real-world assets | ONDO XDC XAUT PAXG | |
| Privacy | ZEC XMR NIGHT? | |
| Payments and settlement | XLM BCH LTC STABLE? | XRP |
| Infrastructure | LINK QNT FIL ZRO | |
| Exchange tokens | BNB WBT LEO CRO OKB HTX BGB GT KCS HYPE PUMP NEXO | |

`M` has no proposal (SPEC 2a): it lands in `Unassigned` until the owner places it (that is allowed by decision 7; G-OWN asks). `U` is a stablecoin? (UNVERIFIED): class `stablecoin` pending the owner; if wrong it goes to `Unassigned` too. Memberships are written once per narrative in the file: a coin with n memberships has n entries and exactly one `primary: true` (HYPE, PUMP, NEXO: the Exchange-tokens entry; XRP: Majors).

## 6. Slices in detail (Implementation Checklist)

All cites are `main` b61bdf9. Test commands run from the repo root with `UV_FROZEN=1`; web commands run inside `web/` (see the Validate Contract for why).

### U1: narratives file, loader, Discovery on narratives (+ snapshot-id mapping, `min_category_coins` move)
- **Objective:** Discovery categories = narratives; the 3-coin rule owned by the narratives loader and `universe_rules.min_narrative_coins`; old snapshot ids resolve; the nightly categories runner keeps working.
- **Create:** `api/data/attention_narratives.json`; `api/analytics/attention/narratives.py` (`NARRATIVES_PATH`, `load_narratives()`, validation, `memberships(universe_symbols, min_coins)` -> visible narrative id -> symbols, plus `hidden` and `unassigned`); `api/data/attention_narrative_id_map.json`; `api/tests/analytics/attention/test_narratives.py`.
- **Edit (cites on main):**
  - `discovery.py`: `validate_config` 47-59 (drop the `min_category_coins` check 56-58; require `universe_rules.min_narrative_coins`, integer >= 1; reject the keys `categories` and `min_category_coins`); `_excluded_counts` 186-204 (line 190 reads `cfg["categories"]`: use the union of visible narrative members); `build_discovery` 207-249 (loop at 232 over visible narratives from `narratives.memberships`; `min_coins` at 230 from `universe_rules`; add `narratives_status`, `unassigned`, `hidden_narratives`, `categories_as_of` from the file `as_of`; `primary` per coin). **Keep `eligibility` 175-183, `_excluded_symbols` 163-168, the floor and the `categories_store` read at 216-219 as they are**: U2 removes them. U1 changes where the MEMBERS come from, not who is eligible. Without that the `exclude_category_ids` step (which needs the CoinGecko category lists) would have nothing to read.
  - `discovery_history.py` `category_history` 132-167: id check at 138 against narratives, accept an old id through the map (`meme-token` -> `memecoins`; a retired id such as `gaming` stays a 404 `UnknownSubject`); members at 146-147 from narratives; add `membership_as_of` to the payload.
  - `signal_snapshots.py`: `config_hash` 50-51 stays; `take_snapshot` 96-117 folds `narratives_sha` into `current_hash` and the record; `_record` 54-70 writes `membership_definition: "attention-narratives-v1"` and `narratives_sha`; `read_snapshots` 120-135 returns each row with `narrative_ids` (stored `category_ids` mapped through the id map when the record has no `membership_definition`; retired ids go to `retired_ids`), raw `category_ids` untouched, file never rewritten.
  - `models/discovery.py`: `DiscoveryResponse` 47-60 (fields of the contract table, section 3), `DiscoveryCoin` 18-25 (`primary`), `DiscoveryCategoryHistory` 126-129 (`membership_as_of`).
  - `api/data/discovery.json`: remove the `categories` array and `min_category_coins` (line 25); add `"universe_rules": {"min_narrative_coins": 3}`.
  - `api/scripts/refresh_attention.py` `_run_categories` 181-192: lines 185-186 read `cfg["categories"]` and `cfg["exclude_category_ids"]`. The scheduled workflow runs `--sources categories` (`.github/workflows/attention-refresh.yml:68`) and its verify step (lines 92-137) marks the job FAILED when the `categories:` line contains ` error `: leaving this hunk alone turns the nightly job red. New: ids = the keys of `attention_narrative_id_map.json` plus `cfg["exclude_category_ids"]` (U2 drops that part); names from the map file; the CoinGecko category snapshot stays a seeding hint, nothing scores from it. The workflow itself is not touched.
  - tests: `test_discovery.py` (`cfg()` 29-38 and `CATS` produce a config with the removed keys; `world()` 41-56 must also point `narratives.NARRATIVES_PATH` at a fixture; the `min_category_coins` tests at 274-279 and 476-527 move to `min_narrative_coins`; the `categories-missing` test at line 70 stays valid in U1), `test_discovery_history.py` (21 tests, id checks), `test_signal_snapshots.py` (11 tests), `api/tests/routers/test_discovery.py:38-41` (the exact key-set assertion gains the U1 fields) and `test_discovery_history.py`, `api/tests/scripts/test_refresh_attention.py:159-195` (categories runner tests).
- **NOT touch:** `api/data/narratives.json`, `narrative_categories.json`, `narrative_category_map.json`, `api/data/attention_universe.json`, `api/data/cache/attention/` (all of it, including the three frozen `signals/2026-10-17_w*.json`), `categories_store.py`, `universe.py`, `sources.py`, `web/`, `.github/`, the SPEC.
- **Ownership of the 3-coin rule (decision 11, real state):** #140 is merged, so `min_category_coins` is live. U1 moves it: config key `universe_rules.min_narrative_coins` (same value 3), `validate_config` checks the new key and rejects the old one, response field `min_category_coins` keeps its name and is filled from the new key, web unchanged. One owner: the `universe_rules` block.
- **Snapshot and history migration (decision 11):** frozen files keep `category_ids` (`layer-1`, `meme-token`, ...). Map: `layer-1`->`layer-1`, `layer-2`->`layer-2`, `decentralized-finance-defi`->`defi`, `meme-token`->`memecoins`, `artificial-intelligence`->`ai-data-compute`, `real-world-assets-rwa`->`real-world-assets`, `privacy-coins`->`privacy`, `oracle`->`infrastructure`, `gaming`->none (retired). The map is lossy in meaning (`oracle` was 1 coin, `infrastructure` is 4); it only makes old ids resolvable. **History chart, corrected:** `category_history` (`discovery_history.py:132-167`) never reads signal snapshots; it rebuilds every day of the window from the stored series with TODAY'S membership. So days before the switch are not "old definition"; they are recomputed with the new membership, and nothing breaks at a date. The first draft's `definition_changed` date cannot be derived from the chart; the payload gets `membership_as_of` instead (the narratives file `as_of`), so a reader knows which membership drew the whole line. `read_snapshots` has no production caller yet (only tests and `summarize`), so the mapping is cheap and safe.
- **`config_hash`:** U1 and U2 each change `cfg`, so the snapshot job reports `config-changed` for the day it runs after each merge (existing behaviour, `signal_snapshots.py:108`; `refresh_attention._snapshot_signals` 207-223 logs it as a warning and never fails). The stored record of that day is kept, the new definition lands the next day.
- **Tasks (red first):** 1 write failing tests; 2 loader + validation; 3 seed JSON from section 5 (`proposed`, `as_of` = the dispatch date); 4 wire `build_discovery`; 5 history route and `membership_as_of`; 6 snapshot write and read mapping; 7 `_run_categories`; 8 render the owner table into the report.
- **Red tests (new):** `test_loads_proposed_file`, `test_duplicate_primary_is_error_naming_symbol`, `test_no_primary_is_error`, `test_lowercase_symbol_is_error`, `test_symbol_with_path_characters_is_error` (`../X`, `A/B`), `test_bad_narrative_id_is_error`, `test_narrative_with_two_coins_is_hidden_not_error`, `test_memberships_count_every_narrative_toward_min`, `test_coin_in_three_narratives_counted_in_each`, `test_unassigned_new_coin_listed_not_error`, `test_discovery_uses_narratives_not_categories`, `test_min_narrative_coins_drives_hidden_and_min_category_coins_field`, `test_removed_keys_categories_and_min_category_coins_rejected`, `test_history_accepts_old_category_id_via_map`, `test_history_payload_carries_membership_as_of`, `test_snapshot_reader_maps_old_ids_without_rewrite` (sha256 of a fixture copy unchanged), `test_new_snapshot_writes_narrative_ids_and_marker`, `test_narratives_edit_changes_snapshot_hash`, `test_run_categories_works_without_removed_config_keys`, `test_router_discovery_new_fields_present` (TestClient, fixture world, no network).
- **ACs:** AC-N1..N5 (API half), AC-U1', AC-U2'. **Tier RT3.** **Model:** opus. **Rollback:** revert the PR (the old `discovery.json` returns; no data rewritten; the nightly categories runner returns to the old keys with it).

### U2: classes, exclusion reasons, label-only volume, D-20 behaviour
- **Objective:** replace the volume floor and category exclusion with reasoned exclusion and `thin_volume`.
- **Create:** `api/analytics/attention/universe_classes.py` (classify a row -> `stablecoin|wrapped-staked|tokenized-fund|normal`; the tradeability result type); `api/tests/analytics/attention/test_universe_classes.py`; `api/tests/analytics/attention/fixtures/universe_2026-10-18.json` (a COPY of the newest committed snapshot, `api/data/cache/attention/universe.json`; tests redirect `universe_store` to it and never read the live cache path, which the nightly job rewrites and prunes to 14 days).
- **Edit (cites on main):**
  - `universe.py`: ADD `load_universe_rows(path=None)` (snapshot rows, cap order, `TOP_N` 14). `load_universe` 23-43 and `load_reference` 46-47 stay behaviourally identical (Baskets, Q-V1). The first draft listed the callers as `discovery_history.py` and `refresh_attention.py`; the real callers are `discovery.py:213`, `discovery_history.py:110,140`, `sources.py:98` and, through `load_reference`, `basket.py:9,75`. `refresh_attention.py` does not call it.
  - `discovery.py`: replace `_excluded_symbols`/`eligibility` 163-183 with the class + tradeability + `force_include` flow (signature `eligibility(cfg, rows)`), delete the `categories_store` read at 216-219 (and with it the `categories-missing` reason), rewrite `_excluded_counts` 186-204 to the closed reason list, `thin_volume`, `excluded_coins`, `excluded_counts`, fill the legacy `excluded` object (section 3).
  - `discovery_history.py`: `coin_history` 110-114 gates on `sym in symbols` from `load_universe`: an exchange token that is now IN would 404. Use the IN set. `category_history` 140-147: drop the `categories_store` read at 143-145 and the new `eligibility` signature.
  - `sources.py`: line 98-100 (`load_universe`, `categories_store`, `eligibility(cfg, symbols, cats)`) use the IN set; the helper row `categories` (135, `LABELS` 26) becomes a `narratives` row (state `ok` when the file loads, note `status proposed` while proposed). `test_sources.py:33,107,118` pin the old row id and change with it. The web panel renders any row generically (`DiscoverySourcesPanel.tsx:72-84`), no web change.
  - `models/discovery.py`: `DiscoveryResponse` 47-60 and `DiscoveryCoin` 18-25 (U2 fields of section 3).
  - `api/data/discovery.json`: remove `min_volume_24h_usd`, `exclude`, `exclude_category_ids`, `include_despite_category`; extend `universe_rules`.
  - `api/scripts/refresh_attention.py` `_run_categories` 185: drop the `exclude_category_ids` part (hunk only).
  - tests: `test_discovery.py` (delete the D-20 pins at 185-191 and rewrite `test_exclusion_list_and_stablecoins` 83; `cfg()` 29-38 loses the removed keys; every volume-floor test is rewritten to the label-only rule), `test_universe.py` (6 tests; 55-57 `test_shipped_config_has_exchange_tokens` stays true because `attention_universe.json` is untouched), `test_discovery_history.py`, `test_sources.py`, `api/tests/routers/test_discovery.py`.
- **NOT touch:** `web/`, `decisions.md` (U6), `.github/`, `signal_snapshots.py`, `attention_universe.json`, `basket.py`.
- **Tasks:** red tests; classes from the 2026-10-18 snapshot (16 stablecoins: USDT USDC USDS USDE DAI USD1 PYUSD USDD USDG RLUSD USDF BFUSD USDGO OUSD GHO U; 8 tokenized funds: USDY BUIDL USYC USTB EUTBL EURSAFO BCAP FIGR_HELOC, reason `no-market`, detail `tokenized fund`); tradeability input = a stubbed per-venue map (real lists arrive in U5; until then every other coin is `unverified` and is NOT cut); `thin_volume` flag; closed reasons; counts; config validation.
- **Red tests (new):** `test_stablecoin_count_is_16_on_fixture_snapshot`, `test_leaked_stablecoins_usdg_rlusd_u_excluded`, `test_tokenized_funds_reason_no_market`, `test_wrapped_staked_excluded_with_reason`, `test_failed_venue_list_is_unknown_coin_stays_in`, `test_no_volume_cut_zero_and_null_volume_stays`, `test_thin_volume_label_below_20m_only_label`, `test_leo_cro_gt_pi_nexo_shown_without_force_include`, `test_force_include_and_not_tradeable_both_is_config_error`, `test_uni_jup_aero_cake_hype_eligible`, `test_excluded_counts_sum_to_universe_minus_shown`, `test_removed_config_keys_rejected`, `test_legacy_excluded_object_still_sums`, `test_basket_reference_unchanged_on_fixture` (`load_reference` on the fixture equals the list computed from `main`'s lists), `test_coin_history_accepts_exchange_token_now_in_universe`, `test_sources_eligible_size_is_the_in_set`, `test_discovery_end_to_end_on_fixture` (TestClient + fixture world: counts line inputs, 16 + 8 + unassigned 1, no network).
- **ACs:** AC-U3..U5, AC-U6', AC-U7, AC-U8 (config half). **Tier RT3.** **Model:** opus. **Rollback:** revert the PR; `discovery.json` returns to the U1 keys.

### U3: web
- **Objective:** show "N of 100 shown, M excluded" with reasons, thin label, Unassigned, hidden narratives, proposed banner. The coverage line already exists; U3 rewrites it, it does not add one.
- **Edit/create (cites on main):** `web/components/narrative/DiscoveryTab.tsx` (`EXCLUDED_TEXT` 37-42 and `coverageLine` 45-51 move from the legacy `excluded` object to `excluded_counts`; keep the `discovery-coverage` testid at 134-136; add the proposed banner and render the new component), `DiscoveryTable.tsx` (thin tag in `CoinRow` 50-104, Signal column 73-82; unassigned and hidden `<details>` beside `emptyLine` 132-137 and `unrankedGroup` 138-151), new `DiscoveryExclusions.tsx`, `web/lib/types/discovery.ts` (read: `DiscoveryCoin` 14-23, `DiscoveryExcluded` 39-44, `DiscoveryResponse` 47-64; add the contract fields), `web/components/narrative/__tests__/DiscoveryTab.test.tsx` (23 tests; the fixture at 43 and the exact line text at 173-176 change), new `DiscoveryExclusions.test.tsx`, and the Playwright fixture `web/e2e/narrative.spec.ts` (`discoveryBody` 207-233 and the assertion at 269, "50 of 90 top coins shown": keep that wording or change both).
- **NOT touch:** `api/`, `DiscoveryHistoryChart.tsx` (it selects by id at 88 and 102 and needs no change), `DiscoverySourcesPanel.tsx`, `.github/`.
- **Red tests (vitest):** `shows_n_of_100_shown_m_excluded_with_reason_counts`, `lists_excluded_coin_with_reason_on_expand`, `thin_volume_tag_rendered_for_thin_coin_only`, `unassigned_bucket_rendered_when_nonempty`, `hidden_narrative_listed_not_in_table`, `proposed_narratives_banner_when_status_proposed`, `old_response_without_new_fields_still_renders` (a response with only the legacy `excluded` object does not crash).
- **ACs:** AC-U10, AC-N5, AC-N6. **Tier RT1** (`cd web && pnpm test`, `cd web && pnpm exec tsc --noEmit --incremental false`) plus the hybrid e2e of `narrative.spec.ts` (CI does not run Playwright; the tester runs it). **Model:** opus. **Rollback:** revert the PR (API fields additive, the legacy `excluded` object is still served).
- **Merge condition:** after G-OWN (`reviewed`).

### U4: CoinGecko and Wikipedia cover the universe
- **Objective:** the SPEC section 3 fix: symbol list from the universe snapshot, id from the snapshot row, counted `no-id`.
- **Edit (cites on main):** `api/scripts/refresh_attention.py`: `_symbols` 115-121 (default list = symbols of `universe_store.read_latest()` minus `coingecko_attention.STABLECOIN_SYMBOLS`/`WRAPPED_SYMBOLS` (33-34); fall back to the `wiki_articles.json` keys, then `DEFAULT_SYMBOLS`); `_run_coingecko` 133-139 (ids from the snapshot rows, a missing id yields `SourceSeries("coingecko", s, [], "unavailable", "no-id")` instead of `None`; call `fetch_top100` only when there is no snapshot); `_outcome` 41-47 and `OUTCOME_ORDER` 38 (map reason `no-id` to the outcome `no-id`); `outcome_summary` is at line 50 (the first draft's "~50" is confirmed). **Hard constraint:** the line format `coingecko: N/M ok, ...` must keep its prefix (`main()` 271-273); the workflow verify step matches `^coingecko: (\d+)/(\d+) ok` (`.github/workflows/attention-refresh.yml`, verify step) and fails the job on zero ok. `coingecko_attention.py` only if `id` passthrough needs it (`fetch_top100_markets` 73 already returns `id`). The wiki_articles keys count is 103; the snapshot has 100 symbols.
- **Tests:** `api/tests/scripts/test_refresh_attention.py` (26 tests; add), `api/tests/data/attention/test_coingecko_attention.py` (16 tests; only if touched).
- **NOT touch:** `universe.py`/`discovery.py`/`sources.py` (U1/U2), the `_run_categories` hunk (U1/U2), `.github/`, `wiki_articles.json` (the 45-missing mapping is a later task).
- **Known limit (not a defect of this slice):** U4 filters stablecoins with the existing 10-symbol constant, so the 8 stablecoins the constant misses (USDG RLUSD USDF BFUSD USDGO OUSD GHO U) are still requested. Switching to the U2 class lists is a one-line follow-up (section 10).
- **Red tests:** `test_symbols_from_universe_snapshot_not_wiki_keys`, `test_id_taken_from_snapshot_row`, `test_missing_id_is_counted_no_id_outcome`, `test_explicit_symbols_arg_still_wins`, `test_stablecoin_not_requested`, `test_coingecko_result_line_keeps_n_of_m_ok_prefix`.
- **ACs:** AC-U11. **Tier RT2 + owner PC probe P-CG** (live, after merge; wall-clock about 84 symbols x 6 s pacing = about 8.5 minutes, UNVERIFIED against the job limit). **Model:** opus. **Rollback:** revert the PR; the previous symbol source returns.

### U5: source ladder, low-data rows, venue lists
- **Objective:** a coin with no usable source is a visible `low-data` row; venue lists replace the stub.
- **Create:** `api/data/attention/tradeable_markets.py` (one `load_markets` call per venue through ccxt 4.5.78, which is installed; the dated store sits beside the universe snapshot; the response shape of `load_markets` against a live venue is UNVERIFIED, tests use fake exchange objects), tests.
- **Edit (cites on main):** `discovery.py` (`_coin` 125-146: a `None` result becomes a low-data row; `build_discovery` 226-228 keeps `status: no-data` / `no-attention-data` when NO coin has any data, and 233 stops dropping), `models/discovery.py` (`DiscoveryCoin` 18-25: `change`/`raw_change` nullable, `data_quality`, `low_data_reason`), `sources.py` (note text: how many IN coins are low-data; `eligible_size` unchanged), `signal_snapshots.py` `_record` 54-70 (a low-data row is recorded with `score: null`), `refresh_attention.py` ONLY a new opt-in runner `markets` (not in `DEFAULT_SOURCES`: a US runner gets HTTP 451 from Binance and a failing default source must not colour the nightly job). U4 merges first; U4 and U5 are never parallel (different waves).
- **NOT touch:** `.github/` (**flagged loudly:** with no workflow step the venue lists are only refreshed by the owner's PC run, so in CI every coin stays `tradeability: unverified`. Calling `--sources markets` from the workflow is a follow-up for the planner, outside this PLAN), source weights, `exchange_volume.py` series logic.
- **Red tests:** `test_no_source_coin_shown_low_data_with_reason`, `test_low_data_reason_names_missing_steps_in_ladder_order` (replaces the first draft's `test_ladder_order_volume_wikipedia_trends_reddit`, whose subject, an order of preference, does not exist in the weighted-mean scorer), `test_low_data_not_scored_zero_and_not_in_mean`, `test_all_coins_without_data_still_no_data_status`, `test_no_source_data_reason_count_is_zero_after_u5`, `test_coin_with_only_coingecko_volume_uses_fallback`, `test_venue_fetch_failure_marks_unknown`, `test_hyperliquid_scaled_names_kpepe_matches_pepe`, `test_any_venue_true_is_tradeable`, `test_markets_runner_not_in_default_sources`, `test_snapshot_records_low_data_row_with_null_score`.
- **ACs:** AC-U9', AC-U8 (venue half). **Tier RT3; owner probe P-VEN.** **Model:** opus. **Rollback:** revert the PR (stub tradeability returns, coins stay in as unverified).

### U6: D-20 supersede and docs
- **Edit:** `process/context/decisions.md` (new entry after D-21, the last entry on main, so the id is **D-22**; D-20's status line set to `superseded by D-22`), `process/context/all-context.md` and `context-changelog.md` only if they cite the exclusion lists (grep first). **NOT touch** code. **Tier RT0** (`git diff --check origin/main...HEAD`; `validate-context-discovery.mjs` must not report more than the one failure main already has, see the Validate Contract). **Model:** sonnet. **Rollback:** revert the PR.
- **Entry text (to paste; the Consequences line is corrected against Q-V1):**
  > ### D-22 Exchange tokens are IN as a narrative (supersedes D-20)
  > - **Decision:** owner decided 2026-10-18: exchange tokens (BNB, WBT, LEO, CRO, OKB, HTX, BGB, GT, KCS and later ones) are IN the Discovery universe as the narrative "Exchange tokens", and HYPE, PUMP, NEXO have it as primary. There is no volume floor and no volume cut; volume under 20M only adds a "thin volume" label. Exclusions are stablecoins, tokenized funds (reason "no market"), wrapped/staked/bridged copies and coins with no market on Binance, Coinbase, Kraken or Hyperliquid; each shows its reason on the page. Placement lives in `api/data/attention_narratives.json` and `universe_rules` in `discovery.json`.
  > - **Date:** 18-10-26. **Reason:** the goal is attention on coins the owner can trade; exchange tokens are tradeable and have their own attention. **Alternatives:** keep the exclusion list (rejected by the owner); keep a 5M backup floor (rejected).
  > - **Consequences:** thin exchange tokens will often be "low data". `exclude`, `exclude_category_ids`, `include_despite_category` and the volume floor are removed from `discovery.json`. `attention_universe.json` keeps its three lists for the Baskets reference only (its scores are unchanged); moving Baskets to the new universe is a separate decision.
  > - **Status:** active. D-20 status becomes superseded.

## 7. Interactions (decision 11; real state of main b61bdf9)

- **#140 (T106) is merged.** What it put on main and who now owns each part:
  - `min_category_coins`: config `discovery.json:25`, validation `discovery.py:56-58`, response field `models/discovery.py:57`, web `DiscoveryTab.tsx:107` / `DiscoveryTable.tsx:14,111,140`, e2e fixture `narrative.spec.ts:226`, about 12 tests (`test_discovery.py:274-279,476-527`, `tests/routers/test_discovery.py:38`, `DiscoveryTab.test.tsx:44`). **Instruction for U1:** the value moves to `universe_rules.min_narrative_coins`; `validate_config` checks the new key and rejects the old one; the response and web keep the name `min_category_coins` (no web edit); the old-key tests are rewritten, not deleted without a replacement.
  - Sources route and panel: `routers/discovery.py:31-34`, `sources.py` (142 lines), `DiscoverySourcesPanel.tsx` (90 lines), `DiscoverySourceRow` with a free-text `note` (`models/discovery.py:66-77`). **Instruction for U2:** `sources.py:98-100,135` follow the new IN set and the `categories` helper row becomes `narratives`. **Instruction for U5:** the low-data reason is a per-coin response field (`low_data_reason`); the sources panel shows the count in its existing `note` column (no new column, no web edit). A second place for the reason text would drift.
  - `excluded` object (`models/discovery.py:39-44`, `discovery.py:186-204`, web `DiscoveryTab.tsx:37-51`, `types/discovery.ts:39-44`): kept and filled by U2 (section 3); the reasoned list is `excluded_coins`.
- **#139 (T107) is merged.** The chart panels select by category id: `DiscoveryTable.tsx:122` (`onSelect({kind: "category", id})`), `DiscoveryHistoryChart.tsx:88,102`. U1's id map keeps stored and bookmarked ids resolvable through the history route; no file of #139 is edited by this PLAN.
- **#141 (T108) is merged:** the SPEC. **#142 (T111) is merged:** the first draft of this PLAN.
- **Frozen snapshots:** `api/data/cache/attention/signals/2026-10-17_w{7,30,90}.json` (3 files, tracked) store `category_ids`, nine category ids in `categories`, and a `config` copy with `config_hash` e2a3706ca33e8df0. Read-only; mapped on read only; their sha256 are pinned in G8.
- **Nightly workflow:** `.github/workflows/attention-refresh.yml` runs `--sources categories` on its schedule and parses `coingecko: N/M ok`. Both are protected by U1 and U4 (above). The file itself is not edited.

## 8. Acceptance Criteria (mapped to SPEC)
| ID | Criterion | Source | Slice |
|---|---|---|---|
| AC-U1' | `attention_narratives.json` loads; duplicate or missing primary, bad symbol are named errors; < 3 in-universe coins is NOT an error (hidden) and an uncovered coin is NOT an error (Unassigned) | rewrites AC-U1 | U1 |
| AC-U2' | Every in-universe coin has exactly one primary narrative or sits in Unassigned; any number of other memberships; BNB LEO OKB HYPE PUMP NEXO appear under Exchange tokens | rewrites AC-U2 | U1 |
| AC-U3 | `exclude_category_ids` gone; UNI JUP AERO CAKE HYPE eligible on the 2026-10-18 fixture | SPEC AC-U3 | U2 |
| AC-U4 | classification on the fixture: stablecoin 16, tokenized fund 8 (reason no-market), USDG RLUSD U stablecoins | SPEC AC-U4 (exchange-token count 9 now a narrative size, not a class) | U2 |
| AC-U5 | every excluded coin has a closed-list reason (`stablecoin`, `wrapped-staked`, `no-market`, `not-tradeable-config`, `unassigned`, `hidden-narrative`, and `no-source-data` until U5); `shown_size + sum(excluded_counts) = universe_size` | SPEC AC-U5 (list without `volume-below-floor`, with the two non-exclusion reasons the identity needs) | U2 |
| AC-U6' | no volume cut at any level; null/zero volume stays; under 20M shows `thin_volume: true`; `backup_floor_usd` absent from code and config | rewrites AC-U6 | U2 |
| AC-U7, AC-U8 | `force_include`+`not_tradeable` same symbol = config error; failed venue = unknown, coin stays `tradeability-unverified` | SPEC | U2, U5 |
| AC-U9' | no-source coin shown `low-data` with reason, never dropped, never scored 0 | sharpens AC-U9 | U5 |
| AC-U10 | web: "N of 100 shown, M excluded" with reasons | SPEC | U3 |
| AC-U11 | runner covers every in-universe symbol with a snapshot id; missing id = counted `no-id` | SPEC | U4 |
| AC-U12 | superseding decision recorded in `decisions.md` | SPEC | U6 |
| AC-N1 | `narratives_status` ("proposed"/"reviewed") in the response; web banner while proposed | new (G-OWN) | U1, U3 |
| AC-N2 | multi-membership: a coin in 3 narratives is counted in each aggregate and each counts to the minimum | new | U1 |
| AC-N3 | Unassigned bucket lists new top-100 coins with no narrative; response flags them; no error | new | U1, U3 |
| AC-N4 | old snapshot and history ids resolve through the map; frozen files byte-identical (G8); the category history payload carries `membership_as_of` (the chart recomputes all days with today's membership; it does not read snapshots) | new, corrected by VALIDATE | U1 |
| AC-N5 | hidden narrative (< 3 coins) listed under "hidden" with its count, not in the table | new | U1, U3 |
| AC-N6 | label-only volume visible in the UI as a tag | new | U3 |
| AC-N7 | the nightly `--sources categories` runner works with `categories` and `exclude_category_ids` gone; the workflow file is untouched | new, VALIDATE | U1, U2 |
| AC-N8 | Baskets reference (`load_reference`) is unchanged on the 2026-10-18 fixture (Q-V1) | new, VALIDATE | U2 |
| AC-N9 | the legacy `excluded` object is still served, shape unchanged, and sums with `shown_size` to `universe_size` | new, VALIDATE | U2 |
| AC-N10 | a symbol or narrative id with path characters in any hand-edited file is a named load error | new, VALIDATE | U1, U2 |

## 9. Owner PC probes (after each slice; providers unreachable from the build container)
| After | Probe | Expect |
|---|---|---|
| U1 | open Discovery, check the coin-to-narrative table in the U1 report against the page; flip `status` to `reviewed` | G-OWN done; page shows 11 narratives (hidden ones listed apart); `M` under Unassigned |
| U1 | `uv run --project api python api/scripts/refresh_attention.py --sources categories` locally (network) | `categories: snapshot written`, no ` error `; the nightly job stays green |
| U2 | `GET /api/narrative/discovery?window=30` locally | `universe_size` 100; `excluded_counts`: stablecoin 16, no-market 8, unassigned 1 (`M`), `no-source-data` N (shrinks to 0 after U5); no `volume-below-floor`; the legacy `excluded` object present and summing |
| U4 (P-CG) | run the refresh for `coingecko` locally; read `probe_records.json` | `coins_ok` near the in-universe count (was 56 of 103); `no-id` counted; the log line still starts `coingecko: N/M ok`; wall-clock noted |
| U5 (P-VEN) | run `--sources markets` with network; read the stored map | Binance and Hyperliquid lists loaded; PEPE/SHIB alias resolved; a failed venue shows `unknown`, never `no market` |
| U3 | open the tab | counts line with reasons, thin tags, banner while `proposed`, Unassigned lists `M` |

## 10. Risks and follow-ups
- G-OWN delay blocks U3's merge and any "live" claim; coding proceeds against `proposed`.
- Unlimited memberships inflate narrative counts and correlate aggregates (no cross-narrative total, as today).
- Many thin exchange tokens produce low-data rows until Trends/Reddit per coin exist.
- Changing the config changes `config_hash` at U1, U2 and U5: one `config-changed` warning day per merge in the snapshot job, expected and non-failing.
- Chart lines: after U1 every narrative line is recomputed with today's membership for all days (`membership_as_of`); a reader comparing a pre-switch screenshot with the new chart sees a level shift that is not a data change.
- Live unknowns (UNVERIFIED, owner probes): Binance reachability (HTTP 451 from US runners), Coinbase/Kraken lists absent (W7), CoinGecko 429 history, the live `load_markets` shape in ccxt 4.5.78, U4 wall-clock against job limits.
- Production tradeability stays `unverified` until a workflow step runs `--sources markets` (`.github/` is outside this PLAN; planner follow-up).
- **Follow-ups (not in U1-U6):** (1) remove the legacy `excluded` object after U3 is live; (2) switch U4's stablecoin filter to the U2 class lists; (3) workflow step for `--sources markets`; (4) Baskets reference vs the new universe (Q-V1); (5) the 45 missing Wikipedia articles.
- Resolved from the first draft's UNVERIFIED list: `web/lib/types/discovery.ts` (read, layout in U3), `outcome_summary` (`refresh_attention.py:50`), test locations (`api/tests/scripts/test_refresh_attention.py`, `api/tests/data/attention/test_coingecko_attention.py`, `web/components/narrative/__tests__/`), `categories_store` (read; kept as a hint writer, nothing scores from it after U1/U2), ccxt (4.5.78 installed, `ccxt>=4.3` in `api/pyproject.toml`; live behaviour stays a probe).

## Touchpoints

API: `api/analytics/attention/{discovery,discovery_history,signal_snapshots,sources,universe}.py`, new `narratives.py`, `universe_classes.py`, `api/data/attention/tradeable_markets.py`, `api/models/discovery.py`, `api/routers/discovery.py` (no edit expected), `api/scripts/refresh_attention.py`, config `api/data/discovery.json`, new data `attention_narratives.json`, `attention_narrative_id_map.json`. Web: `web/components/narrative/Discovery{Tab,Table,Exclusions}.tsx`, `web/lib/types/discovery.ts`, tests and `web/e2e/narrative.spec.ts`. Docs: `process/context/decisions.md`. Read-only inputs: `api/data/cache/attention/{universe,categories}.json`, `signals/*`.

## Public Contracts

`GET /api/narrative/discovery` (additive fields, section 3; `excluded` object kept; `categories` carries narratives), `GET /api/narrative/discovery/history?category=` (accepts old ids; payload gains `membership_as_of`), `GET /api/narrative/sources` (row ids change: `categories` -> `narratives`), the signal snapshot record (new `membership_definition`, `narratives_sha`; reader adds `narrative_ids`), `refresh_attention.py` log lines (`coingecko: N/M ok` prefix unchanged), the nightly workflow's `--sources categories` call.

## Blast Radius

Consumers of what changes: the Discovery tab, its history chart and sources panel; the nightly attention workflow (verify step); the signal snapshot job; the Baskets tab through `load_reference` (guarded, must not change). About 20 API files, 5 web files, 1 doc file across 6 slices; tests: roughly 190 attention-suite tests are in scope of edits (`test_discovery.py` 69, `test_discovery_history.py` 21, `test_sources.py` 15, `test_signal_snapshots.py` 11, `test_universe.py` 6, router tests 22, `test_refresh_attention.py` 26) plus vitest `DiscoveryTab.test.tsx` (23).

## Verification Evidence

Baselines and command outputs of T112 are in the Validate Contract and the T112 report (`process/general-plans/active/narrative-baskets_02-10-26/`, the PR for this validation). Each execute slice records its own post-merge numbers in its report heading 5; those become the next slice's baseline.

## Resume and Execution Handoff

1. Read this PLAN (all of it) and the SPEC only if a cite needs context. 2. Start from `origin/main` at dispatch; re-run the baseline commands of the contract for the files you touch and compare with the table (a different number means main moved: use the new number and say so in report heading 5). 3. Branch `claude/<task-id>-<slug>`, one slice per branch, draft PR, never merge. 4. Red tests first, then code; stay inside the slice file list and the ownership table (section 4); anything outside it is a stop-and-report. 5. Run the slice gates of the contract; put commands and numbers in report heading 5. 6. Owner probes are the owner's; list them in report heading 10. 7. Order: U1 || U4 -> U2 -> U3 || U5 || U6.

## Validate Contract

Status: PASS
Date: 18-10-26
date: 2026-10-18
generated-by: outer-pvl
Code under test: `main` b61bdf9 (merge of #142; #137, #139, #140, #141 merged). Measured in a scratch worktree of that commit, `UV_FROZEN=1 uv sync --project api --frozen`, `cd web && pnpm install --frozen-lockfile`, 18-10-26 UTC. The verdict is the status line at the top of this file. Method: two layers run in sequence by one worker (T112): Layer 1 four dimensions on the PLAN, Layer 2 per-slice feasibility with every cite re-verified; findings F1-F25 in the Validation record; every FAIL and CONCERN was fixed in the PLAN text above before the verdict, none is left open.

### Baselines (main b61bdf9)

| What | Command (from the repo root unless noted) | Result |
|---|---|---|
| Attention suite | `UV_FROZEN=1 uv run --project api pytest api/tests/analytics/attention -q` | 147 passed, 24.9 s |
| Full API | `UV_FROZEN=1 uv run --project api pytest api/ -q` | 1620 passed, 1 skipped, 5 deselected, 260.7 s |
| Web unit | `cd web && pnpm test` | 558 passed in 62 files, 39 s |
| Typecheck | `cd web && pnpm exec tsc --noEmit --incremental false` | exit 0 |
| Island build | `cd web && pnpm build:islands` | exit 0, 11 s |
| Plan validator | `node .claude/skills/vc-generate-plan/scripts/validate-plan-artifact.mjs <this plan>` | before T112: 0 failures, 5 warnings (missing Touchpoints, Public Contracts, Blast Radius, Verification Evidence, Resume and Execution Handoff); after: see G5 |
| Context validator | `node .claude/skills/vc-audit-context/scripts/validate-context-discovery.mjs` | exit 1, 1 failure already on main (`.agents/skills does not resolve to .claude/skills`), 0 warnings; U6 must not add to it |
| Frozen snapshots | `sha256sum` of `api/data/cache/attention/signals/2026-10-17_w{7,30,90}.json` | the three hashes of G8 |
| Playwright | `cd web && pnpm exec playwright test --list` | NOT measured: the listing errors in the scratch worktree (no browser setup there; e2e is not a CI job). UNVERIFIED count |

Collected per touched test file: `test_discovery.py` 69, `test_discovery_history.py` 21, `test_sources.py` 15, `test_signal_snapshots.py` 11, `test_universe.py` 6, `test_fixpack_p5.py` 6, `test_basket_scoring.py` 11, `test_primitives.py` 8 (attention suite total 147); `routers/test_discovery.py` 12, `routers/test_discovery_history.py` 10, `scripts/test_refresh_attention.py` 26, `data/attention/test_coingecko_attention.py` 16, `test_categories_store.py` 5, `tooling_guards/test_attention_workflow_guard.py` 16; vitest `DiscoveryTab.test.tsx` 23, `DiscoveryHistoryChart.test.tsx` 25, `NarrativeTabs.test.tsx` 8. The documented `pnpm --filter web test` prints "No projects matched" when run from the repo root of a fresh checkout here (no root `package.json`; the workspace file is `web/pnpm-workspace.yaml`): use the `cd web && pnpm ...` forms above.

### Test gates (one line per tier per area; exact commands)

Pass rule for every count gate: 0 failed; skipped and deselected unchanged (1 and 5); the passed count is at least `baseline + named red tests added in the slice - tests deleted or replaced`, and the report lists each deleted or replaced test with its reason. The baseline of a slice is the post-merge number of the previous slice (U1 and U4 start from the table above). Named red tests (minimum new tests, parametrised cases add more): U1 20, U2 17, U3 7, U4 6, U5 11, U6 0.

| Gate | Slices | Command | Pass criterion |
|---|---|---|---|
| G1 attention suite | U1, U2, U5 (RT3), U4 (RT2) | `UV_FROZEN=1 uv run --project api pytest api/tests/analytics/attention -q` (U4: also `api/tests/scripts/test_refresh_attention.py api/tests/data/attention/test_coingecko_attention.py`) | rule above; first-pass numbers floors from baseline 147: U1 >= 147+20-d, U2 >= (U1 result)+17-d |
| G2 full API | U1, U2, U5 twice (RT3) + one tester run; U4 once | `UV_FROZEN=1 uv run --project api pytest api/ -q` | rule above; floors from 1620: U1 >= 1640-d, U4 >= 1626-d, U2 >= (post-merge U1+U4)+17-d, U5 >= (post-merge U2)+11-d |
| G3 workflow guards | U1, U4 | `UV_FROZEN=1 uv run --project api pytest api/tests/tooling_guards/test_attention_workflow_guard.py api/tests/scripts/test_ci_workflow.py -q` | all pass (guard file 16 collected); proves the workflow file is intact and its inputs still exist |
| G4 web unit | U3 (RT1); U1, U2, U5 as RT3 regression | `cd web && pnpm test` | U1, U2, U5, U4: exactly 558 passed in 62 files (no web edit); U3: >= 565-d, plus the touched files first: `cd web && pnpm exec vitest run components/narrative/__tests__/DiscoveryTab.test.tsx components/narrative/__tests__/DiscoveryExclusions.test.tsx` |
| G5 typecheck and islands | U3; U1, U2, U5 as RT3 regression | `cd web && pnpm exec tsc --noEmit --incremental false` and `cd web && pnpm build:islands` | both exit 0 |
| G6 forbidden paths | every slice | `git fetch origin main && git diff --stat origin/main...HEAD -- .github api/data/narratives.json api/data/narrative_categories.json api/data/narrative_category_map.json api/data/attention_universe.json api/data/cache` | empty output |
| G7 slice scope | every slice | U1, U2, U4, U5: `git diff --stat origin/main...HEAD -- web` empty. U3: `-- api .github` empty. U6: `git diff --stat origin/main...HEAD -- api web .github` empty. U4 additionally `-- api/analytics api/models api/data/discovery.json` empty | empty output |
| G8 frozen snapshots | every slice | the `sha256sum -c` block directly under this table | three lines `OK`; `git ls-files api/data/cache/attention/signals` still lists exactly 3 files |
| G9 hygiene | every slice | `git diff --check origin/main...HEAD` and the secret scan `git diff -U0 origin/main...HEAD \| grep -nE "^\+.*(Bearer [A-Za-z0-9._-]{12,}\|(API_?KEY\|SECRET\|TOKEN\|PASSWORD)[A-Z_]* *[:=] *[\"'][A-Za-z0-9+/_-]{12,})"` | `diff --check` exit 0; scan prints nothing |
| G10 plan and context validators | this PLAN (T112 and any later edit); U6 | `node .claude/skills/vc-generate-plan/scripts/validate-plan-artifact.mjs process/general-plans/active/narrative-baskets_02-10-26/narrative-baskets-universe-narratives_PLAN_18-10-26.md`; U6 also `node .claude/skills/vc-audit-context/scripts/validate-context-discovery.mjs` | plan: 0 failures and 0 warnings; context: not more than the 1 existing failure, same message |
| G11 U4 dry run | U4 | `UV_FROZEN=1 uv run --project api python api/scripts/refresh_attention.py --dry-run --sources coingecko` | exit 0; prints `coingecko: dry run, would fetch N symbols`; N is 92 on the 2026-10-18 snapshot (100 symbols minus the 8 constant stablecoins), was 103 |
| G12 named end-to-end per surface | U2 (API, TestClient, fixture world, network blocked by the `wired` pattern of `routers/test_discovery.py`): `test_discovery_end_to_end_on_fixture`; U1: `test_router_discovery_new_fields_present`; U3 (web): the vitest fetch-injected `DiscoveryTab` tests plus the seeded Playwright `cd web && pnpm test:e2e -- narrative` run by the tester (needs `PLAYWRIGHT_CHROMIUM_PATH`, see all-tests.md) | pass; the e2e run is hybrid (CI does not run Playwright) and its count is recorded by the tester because no baseline exists |

G8 command (run from the repo root):

```
cd api/data/cache/attention/signals && sha256sum -c <<'EOF'
eb4730e44d5f7f17d86fc1e704a87c69b1a247d4fc1ab41aca0555f226bbcdde  2026-10-17_w30.json
597fb394fcfc3207c5f8adfc35e57827f39cf81e6cff031787678a2e76d6aef1  2026-10-17_w7.json
09946558044b0bfa7093dfeb5fe1ab586eca6b762fd89301b807eb01ec9909ac  2026-10-17_w90.json
EOF
```


Tier per slice: U1 RT3, U2 RT3, U3 RT1 (+ hybrid e2e), U4 RT2 (+ owner probe), U5 RT3, U6 RT0. Test budget: RT3 two full-suite runs, RT1/RT2 one, RT0 none. RT4 is not required: no auth, secret, deploy or `.github/` change.
Model per slice: U1 opus, U2 opus, U3 opus, U4 opus, U5 opus, U6 sonnet. Cost estimates in section 4 (total 14.5 USD); per-slice cap 15, ask the planner at 7.

### Owner probes and rollback
Probes: section 9 (P-CG, P-VEN, the U1 categories-runner check, the G-OWN review). Rollback: revert the slice PR; no slice rewrites data (G8, G6); the first-write-wins snapshot job keeps its stored records, so a reverted config only makes the next snapshot day report `config-changed` once.

### Hard stops (verbatim for the /goal block)
- Any change under `.github/`, `api/data/narratives.json`, `api/data/narrative_categories.json`, `api/data/narrative_category_map.json`, `api/data/attention_universe.json` or `api/data/cache/`: stop and report.
- A frozen snapshot hash of G8 differs: stop and report.
- A needed edit outside the slice's file list or the ownership table of section 4: stop and report, do not widen the slice.
- `needs_input`: stop; do not merge; do not open a new PR. Never merge any PR.
- A baseline on fresh main differs from the table above by anything other than a merged earlier slice: stop and report the numbers.
- Slice cost at 7 USD: ask the planner; hard cap 15 per slice.

### Dimension findings (after the fixes in this PLAN)

| Dimension | Status | Evidence |
|---|---|---|
| infra/setup-fit | PASS | every edit target exists on main with the corrected cite; baselines recorded; commands exercised (the `--filter` form corrected, F19); one FAIL fixed (F1, the nightly categories runner) |
| test-coverage | PASS | red-test patterns exist (`world()`/`cfg()` helpers, router `wired` fixture, vitest fetch injection); tiers corrected (F22); a named end-to-end per surface (G12); fixture copy for snapshot-dependent counts (F14); live behaviour is a known gap with owner probes |
| breaking-changes | PASS | FAILs F2, F3, F4 fixed by renaming the new list, keeping the category-store read until U2, and leaving Baskets untouched; CONCERNs F5-F10, F12, F15, F21, F23-F25 fixed in the slice texts and the response contract |
| security-surface | PASS | no new route or route input; hand-edited file inputs validated with regexes before they reach `store_path` (F11); no secrets; no network on the request path; nothing under `.github/` or the frozen snapshots is touched (G6, G8) |

### Open gaps
None blocking. Recorded known gaps: (1) live-only behaviour is UNVERIFIED and covered by owner probes only (Binance reachability, Coinbase and Kraken lists, the live `load_markets` shape, U4 wall-clock, whether `U` and the unknown tickers are what the SPEC proposes); (2) production tradeability stays `unverified` until a workflow step runs `--sources markets` (planner follow-up, outside this PLAN); (3) Playwright count has no baseline; (4) Q-V1 (Baskets reference) is defaulted to "unchanged", the owner may overrule it; (5) the follow-ups of section 10.

### What This Coverage Does NOT Prove
The gates read committed files and fixtures; none calls a provider. They do not prove that CoinGecko, Wikipedia, Binance or Hyperliquid answer as the fakes do, that the venue lists load from a US runner, that the nightly job stays inside its time limit with about 92 CoinGecko symbols, that the 11-narrative table is what the owner wants (G-OWN), that thin exchange tokens have enough attention data to rank, or how the page looks (vitest asserts structure and text, not layout; the hybrid e2e covers one seeded flow). The Baskets guard proves the reference list is unchanged on the 2026-10-18 fixture, not on later snapshots. The U6 gate proves the documents parse, not that the decision text is right.

### Accepted by
session (T112 worker, 18-10-26, docs only), on the planner's envelope; no concern is accepted by the owner yet: Q-V1 and the G-OWN review are the owner's.

## Validation record (T112, 18-10-26)

Severity is the state BEFORE the fix in this PLAN; all are resolved in the text above. No owner decision of section 2 is contradicted; no slice is infeasible once the corrections are applied. Where a first-draft statement could not be done as written, it says so here.

| # | Sev. | Finding (file:line on main b61bdf9) | Resolution |
|---|---|---|---|
| F1 | FAIL | `refresh_attention.py:185-186` (`_run_categories`) reads `cfg["categories"]` and `cfg["exclude_category_ids"]`, both removed by U1/U2. The workflow runs `--sources categories` on its schedule (`attention-refresh.yml:68`) and marks the job FAILED when that line has ` error ` (`:114`). Not in any slice file list | U1 and U2 own the hunk 181-192; test `test_run_categories_works_without_removed_config_keys`; AC-N7 |
| F2 | FAIL | the response already has `excluded` as an OBJECT of 4 counts (`models/discovery.py:39-44,56`); the first draft's `excluded: [...]` list would change its type. The web reads `data.excluded[k]` (`DiscoveryTab.tsx:37-51`, `types/discovery.ts:39-44,57`), the e2e fixture sets it (`narrative.spec.ts:225`), tests pin it (`DiscoveryTab.test.tsx:43,173`, `routers/test_discovery.py:38-41`). "Old web ignores additive fields" was false for this one | new list is `excluded_coins`, counts in `excluded_counts`, legacy object kept and filled; AC-N9; U3 test `old_response_without_new_fields_still_renders` |
| F3 | FAIL | U1 as written ("members from narratives, keep the floor code until U2") leaves `_excluded_symbols` 163-168 needing category members from `categories_store` (216-219) that U1 stops providing; `exclude_category_ids` could not be evaluated | U1 keeps the `categories_store` read and `eligibility` until U2; only the MEMBER source changes |
| F4 | FAIL | the first draft's cites `universe.py:222` and `231-251` do not exist (the file has 47 lines: `TOP_N` 14, `load_universe` 23-43). Callers of `load_universe` are `discovery.py:213`, `discovery_history.py:110,140`, `sources.py:98` and, via `load_reference`, `basket.py:9,75`; `refresh_attention.py` is not one. Moving the three lists out of `attention_universe.json` would silently change Baskets scores | Q-V1 default: `attention_universe.json`, `load_universe`, `load_reference` unchanged; new `load_universe_rows`; test `test_basket_reference_unchanged_on_fixture`; AC-N8 |
| F5 | CONCERN | `sources.py:98-100,135` (`eligibility(cfg, symbols, cats)`, helper row `categories`), `LABELS` 26 and `test_sources.py:33,107,118` are in no slice list | U2 owns the edits, U5 the low-data note; ownership table |
| F6 | CONCERN | first draft section 7: "#140 not merged, `min_category_coins` appears nowhere". It is live: `discovery.json:25`, `discovery.py:56-58,230`, `models/discovery.py:57`, web, e2e, about 12 tests | U1 moves it to `universe_rules.min_narrative_coins`; section 7 rewritten |
| F7 | CONCERN | U1 and U4 (parallel) both edit `refresh_attention.py` and `test_refresh_attention.py` | disjoint hunks declared, U4 merges first, U1 rebases; ownership table |
| F8 | CONCERN | `definition_changed` cannot be derived: `category_history` (`discovery_history.py:132-167`) never reads signal snapshots; it recomputes all days with today's membership | `membership_as_of` in the history payload; AC-N4 and U1 migration text corrected |
| F9 | CONCERN | `config_hash` (`signal_snapshots.py:50-51`) covers `cfg` only; the narratives file is outside it | `narratives_sha` in record and hash; test `test_narratives_edit_changes_snapshot_hash` |
| F10 | CONCERN | the narratives schema had no date, yet `categories_as_of` must carry a stamp | `as_of` added to the file schema and validated |
| F11 | CONCERN | hand-edited symbols and ids reach `store.store_path` (`store.py:18-19`), which builds a file path with no sanitising | regexes `^[A-Z0-9_]{1,24}$` and `^[a-z0-9-]{1,40}$`; tests; AC-N10 |
| F12 | CONCERN | AC-U5's identity `sum = universe - shown` fails without reasons for `unassigned`, hidden-only coins and (until U5) `no-source-data` (`discovery.py:233`) | closed list extended, AC-U5 rewritten |
| F13 | CONCERN | `test_ladder_order_volume_wikipedia_trends_reddit` has no subject: the scorer is a weighted mean of available sources (`discovery.py:125-146`), not an ordered fallback | ladder = order of the `low_data_reason` text and the volume source choice; test renamed |
| F14 | CONCERN | counts "on the fixture snapshot" would read `api/data/cache/attention/universe.json`, which the nightly job rewrites and prunes to 14 days | U2 creates a fixture copy of the 2026-10-18 snapshot |
| F15 | CONCERN | `routers/test_discovery.py:38-41` asserts exact key sets; `test_discovery.py:185-191` pins the D-20 exclusion list; `cfg()` 29-38 and `world()` 41-56 build configs with the removed keys | listed in U1/U2 edits with the intended change |
| F16 | CONCERN | U4: `no-id` must not break the workflow regex `^coingecko: (\d+)/(\d+) ok`; the stablecoin constant (`coingecko_attention.py:33`) covers 8 of the 16 stablecoins | prefix kept (test); limit documented, follow-up |
| F17 | CONCERN | U5's venue lists cannot run in CI without a workflow step; Binance returns HTTP 451 on US runners | opt-in `markets` runner, loud flag, follow-up (3) |
| F18 | CONCERN | first draft contradicted itself on whether G-OWN blocks U2 | G-OWN blocks U3's merge and "live" only |
| F19 | INFO | `pnpm --filter web ...` prints "No projects matched" from the repo root here | contract uses `cd web && pnpm ...` |
| F20 | INFO | `validate-context-discovery.mjs` already exits 1 on main (1 failure, `.agents/skills`) | U6 criterion "no more than the existing failure" |
| F21 | CONCERN | "per narrative `memberships` flag" was undefined | replaced by per-coin `primary: bool` |
| F22 | CONCERN | tiers: U1, U2, U5 change shared response models used by 3 routes and the snapshot job, which is RT3 in operating-instructions.md | RT3 for those three |
| F23 | CONCERN | the coverage line already exists (`DiscoveryTab.tsx:37-51,134-136`) and `narrative.spec.ts:269` asserts its wording | U3 rewrites it; e2e fixture and assertion in the U3 file list |
| F24 | CONCERN | two meanings of "low data": the web pill means covered weight under 30 (`DiscoveryTable.tsx:59,77-78`), the API `low-data` means no usable source | both kept; API `low-data` = `covered_weight` 0 with a reason; stated in the contract table |
| F25 | CONCERN | `shown_size` meaning with hidden narratives, unassigned coins and low-data rows was open | `shown_size` = distinct coins in visible narratives; the rest are counted by reason |

### Cite corrections (first draft -> main b61bdf9)

| First draft | Now |
|---|---|
| `universe.py:222` (`TOP_N`) | `universe.py:14` |
| `universe.py:231-251` (`load_universe`) | `universe.py:23-43` |
| `discovery.py:155-168` (eligibility) | `discovery.py:158-183` (`_volumes` 158, `_excluded_symbols` 163, `eligibility` 175) |
| `discovery.py:171-208` (`build_discovery`) | `discovery.py:207-249` |
| `discovery.py:195-196` (`cfg["categories"]`, falsy filter) | `discovery.py:232-233` |
| `discovery.py:122-143`, `129-132` (`_coin`, fallback) | `discovery.py:125-146`, `132-135` |
| `discovery.py:9` | unchanged (docstring line 9) |
| `models/discovery.py:38-46` | `models/discovery.py:47-60` (`DiscoveryExcluded` 39-44) |
| `discovery_history.py:132-167` | unchanged (correct) |
| `signal_snapshots.py:222-238` (`_record`) | `signal_snapshots.py:54-70` |
| `signal_snapshots.py:288-303` (`read_snapshots`) | `signal_snapshots.py:120-135` |
| `signal_snapshots.py:218`, `:276` (`config_hash`, config-changed) | `signal_snapshots.py:50-51`, `:108` |
| `DiscoveryHistoryChart.tsx:92` | `DiscoveryHistoryChart.tsx:88` (subject), `:102` (category fetch) |
| `DiscoveryTable.tsx:151` (category id) | `DiscoveryTable.tsx:122` |
| `DiscoveryTable.tsx:213-232` (coin row) | `DiscoveryTable.tsx:50-104` (`CoinRow`; Signal column 73-82) |
| `DiscoveryTable.tsx:161-166` (empty categories) | `DiscoveryTable.tsx:132-137` |
| `refresh_attention.py:115-121`, `134-139` | `115-121` (correct), `133-139` |
| `refresh_attention.py` `outcome_summary` "~50" | line 50 (confirmed) |
| `coingecko_attention.py:65` | `coingecko_attention.py:65` (correct; constants 33-34) |
| `decisions.md:180` D-20 | `decisions.md:180` (correct); next free id D-22 |
