---
name: plan:narrative-baskets-universe-narratives
description: "T111: PLAN for the tradeable universe (top 100, reasoned exclusions, label-only volume) and the 11 hand-edited attention narratives with unlimited memberships. Slices U1-U6, owner-decision overrides of the T108 SPEC, snapshot-id mapping, gates, rollback. Docs only; no code changed."
date: 18-10-26
feature: narrative-baskets
metadata:
  node_type: memory
  type: plan
---

# Universe and narratives: PLAN (slices U1-U6)

[MODE: PLAN]

**Date:** 18-10-26. **Complexity:** COMPLEX (6 slices, 3 waves). **SPEC:** `narrative-baskets-universe-narratives_SPEC_18-10-26.md` (T108, merged as #141). **Status:** PLANNED, not validated; VALIDATE is next. **Base read:** `main` at 8f2bf4b. PR #137 (T105 snapshots) is merged. **PR #139 (T107 chart panels) and #140 (T106 `min_category_coins`, sources panel) were NOT merged in the tree I read:** `min_category_coins` appears nowhere in `api/` or `web/`, `api/routers/discovery.py` has no sources route, and `DiscoveryTab.tsx` has no sources panel. Every file cite below is `main` at 8f2bf4b; slices that touch files #139/#140 also change must be re-measured by the planner at dispatch (UNVERIFIED what those PRs change).

## Overview and Context

Context router: `process/context/all-context.md`; tests: `process/context/tests/all-tests.md`. Next step: VALIDATE, then the owner's ENTER EXECUTE MODE (RIPER-5). Phase Completion Rules: a slice is done when its red tests are green, its Acceptance Criteria below hold, and its report lists the owner probes.

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

## 3. Design (what changes, verified against main)

- **Eligibility today** (`discovery.py:155-168`): reads `min_volume_24h_usd`, `exclude`, `exclude_category_ids`, `include_despite_category` and CoinGecko category members; `load_universe` (`universe.py:231-251`) drops `stablecoins`, `wrapped`, `exchange_tokens` from `attention_universe.json` silently and returns bare symbols. `build_discovery` builds categories from `cfg["categories"]` (`discovery.py:195`) and returns `DiscoveryResponse` with only `universe_size`/`eligible_size` (`models/discovery.py:38-46`).
- **New eligibility** (replaces the above): top-100 snapshot rows (symbol, `id`, `market_cap`, `volume_24h`) -> class exclusion (stablecoin, wrapped-staked, tokenized fund; reason recorded) -> tradeability (`tradeable` / `no-market` / `unknown`) -> IN. Volume only sets `thin_volume`. Narrative membership comes from `attention_narratives.json`, never from CoinGecko categories.
- **Config** (`discovery.json`): remove `min_volume_24h_usd`, `exclude`, `exclude_category_ids`, `include_despite_category`, `categories`; add `universe_rules` {`thin_volume_label_below_usd` 20000000, `min_narrative_coins` 3, `classes` (symbol lists: `stablecoin`, `wrapped_staked`, `tokenized_fund`), `not_tradeable` {symbol: reason}, `force_include` [symbols]}. `attention_universe.json` keeps `reference`; its three lists move into `classes` (U2). A symbol in both `force_include` and `not_tradeable` is a config error (AC-U7).
- **Narratives file** `api/data/attention_narratives.json`: `{"status": "proposed"|"reviewed", "narratives": [{"id","name","coins":[{"symbol","primary"}]}]}`. Validation (raises, naming narrative and symbol): ids unique; symbols uppercase and unique per narrative; each symbol has exactly one `primary: true` across all narratives. NOT an error: fewer than 3 in-universe coins (hidden), in-universe coin with no entry (goes to `unassigned`).
- **Response (additive):** `universe_size` 100, `shown_size`, `excluded: [{symbol, reason, detail}]`, `excluded_counts`, `unassigned: [symbol]`, `hidden_narratives: [{id, name, coins}]`, per coin `thin_volume`, `volume_24h`, `data_quality` (`normal`|`low-data`), `low_data_reason`, `tradeability` (`tradeable`|`unverified`), per narrative `memberships` flag. The field `categories` keeps its name in JSON (the web and the history route key on it) and now carries narratives; `categories_as_of` carries the narratives file stamp. UNVERIFIED: web type file `web/lib/types/discovery.ts` not read; U3 reads it first.
- **Ladder** (U5): per coin the volume step is the existing exchange-activity slot with CoinGecko fallback (`discovery.py:129-132`), then Wikipedia, Trends, Reddit through the existing weighted `_coin` loop (`discovery.py:122-143`); `None` today means the coin is dropped from the category (`discovery.py:196` filters falsy). New: a `None` result becomes a `low-data` row with a reason, not a drop.

## 4. Slices, order, gates

| Slice | Wave | Parallel with | Model | Tier | Est. USD | Touches `.github/` |
|---|---|---|---|---|---|---|
| U1 narratives file + loader + Discovery reads it | 1 | U4 | opus (code) | RT2 | 2.5 | NO |
| U2 classes, reasons, tradeability stub, label-only volume | 2 | none (shares `discovery.py`) | opus | RT2 | 3.0 | NO |
| U3 web: counts line, reasons, thin label, Unassigned, hidden | 3 | U5 | opus | RT1 | 2.0 | NO |
| U4 CoinGecko/Wikipedia symbol list from the universe | 1 | U1 | opus | RT2 (RT3 live probe by owner) | 2.0 | NO |
| U5 source ladder, low-data rows, venue lists | 3 | U3 | opus | RT2 | 3.0 | NO |
| U6 D-20 supersede, decisions.md, docs | 3 | U3, U5 | sonnet (non-code) | RT0 | 0.5 | NO |
| Snapshot-id mapping layer | inside U1 | | | | | |

Total about 13 USD; the planner states the real ceiling (assumed ~12 left): if so, defer U5's venue-list part to a later task. Per-slice cap 15, ask at 7. Max 2 workers at a time; the pairs above share NO files (checked in the file lists below).

**Order:** U1 || U4 -> **G-OWN** -> U2 -> (U3 || U5) -> U6 (U6 may also run any time after U1; it only edits docs).

**G-OWN (owner gate, blocking):** U1 ships `attention_narratives.json` with `"status": "proposed"` and a rendered coin-to-narrative table in the U1 report. The owner reviews the COMPLETE list once and flips it to `"reviewed"` (or sends edits). The API serves a `proposed` file but the response carries `narratives_status: "proposed"`; U2 and U3 may be coded against it but U3's merge and any "live" claim wait for `reviewed`. AC-N1 tests the flag.

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

### U1: narratives file, loader, Discovery on narratives (+ snapshot-id mapping)
- **Objective:** Discovery categories = narratives; 3-coin rule owned by the narratives loader; ids mappable from old snapshots.
- **Create:** `api/data/attention_narratives.json`; `api/analytics/attention/narratives.py` (loader, validation, `load_narratives()`, `memberships(universe_symbols)` -> narrative id -> symbols, `unassigned`, `hidden`); `api/data/attention_narrative_id_map.json` (old CoinGecko category id -> narrative id); `api/tests/analytics/attention/test_narratives.py`.
- **Edit:** `api/analytics/attention/discovery.py` (`build_discovery` lines 171-208 and `eligibility` 155-168: members from `narratives.memberships`, loop over narratives not `cfg["categories"]`; keep the eligibility floor code until U2); `api/analytics/attention/discovery_history.py` (`category_history` 132-167: id check against narratives, members from narratives, accept an old id through the map); `api/analytics/attention/signal_snapshots.py` (`_record` 222-238: also write `narrative_ids` NEW records; reader `read_snapshots` 288-303 maps stored `category_ids` through the id map on READ, never rewrites); `api/data/discovery.json` (remove `categories` only); `api/tests/analytics/attention/test_discovery.py`, `test_discovery_history.py`, `test_signal_snapshots.py` (existing assertions on category ids updated).
- **NOT touch:** `api/data/narratives.json`, `narrative_categories.json`, `narrative_category_map.json`, `api/data/cache/attention/signals/*`, `categories_store` module, `web/`, `.github/`, the SPEC.
- **Ownership of the 3-coin rule:** `attention_narratives.json` + `narratives.py` own it (`min_narrative_coins` in `universe_rules`). If #140 later lands `min_category_coins`, the follow-up rebase deletes it or defaults it to this value (one owner); not decided in code here.
- **Snapshot/history migration (decision 11):** frozen files keep `category_ids` (e.g. `layer-1`, `meme-token`). Map: `layer-1`->`layer-1`, `layer-2`->`layer-2`, `decentralized-finance-defi`->`defi`, `meme-token`->`memecoins`, `artificial-intelligence`->`ai-data-compute`, `real-world-assets-rwa`->`real-world-assets`, `privacy-coins`->`privacy`, `oracle`->`infrastructure`, `gaming`->none (unmapped, shown as `retired`). Reader returns both the raw and mapped id; the history chart (`DiscoveryHistoryChart.tsx:92`, selection by category id) keeps working with new ids; days before the switch carry the old membership definition (a visible `definition_changed` date in the history payload, see AC-N4). `config_hash` (`signal_snapshots.py:218`) changes on U1 by design: first run after merge reports `config-changed` for that day (existing behaviour, `signal_snapshots.py:276`), nothing is rewritten.
- **Tasks (red first):** 1 write failing tests; 2 loader + validation; 3 seed JSON from section 5 (`proposed`); 4 wire `build_discovery`; 5 history route; 6 snapshot write/read mapping; 7 render the owner table into the report.
- **Red tests:** `test_loads_proposed_file`, `test_duplicate_primary_is_error_naming_symbol`, `test_no_primary_is_error`, `test_lowercase_symbol_is_error`, `test_narrative_with_two_coins_is_hidden_not_error`, `test_memberships_count_every_narrative_toward_min`, `test_coin_in_three_narratives_counted_in_each`, `test_unassigned_new_coin_listed_not_error`, `test_discovery_uses_narratives_not_categories`, `test_history_accepts_old_category_id_via_map`, `test_snapshot_reader_maps_old_ids_without_rewrite` (sha256 of fixture unchanged), `test_new_snapshot_writes_narrative_ids`.
- **ACs:** AC-N1..N4, AC-U1', AC-U2'. **Tier RT2** (`pytest` touched files, then `pytest api/ -q` once). **Model:** opus. **Rollback:** revert the PR (old `discovery.json` returns; no data rewritten).

### U2: classes, exclusion reasons, label-only volume, D-20 behaviour
- **Objective:** replace the volume floor and category exclusion with reasoned exclusion and `thin_volume`.
- **Create:** `api/analytics/attention/universe_classes.py` (classify row -> `stablecoin|wrapped-staked|tokenized-fund|normal`; tradeability result type); `api/tests/analytics/attention/test_universe_classes.py`.
- **Edit:** `universe.py` (stop dropping lists silently: return rows + exclusions; keep `load_universe(path)->(symbols,reason)` signature for callers `discovery_history.py` and `refresh_attention.py` UNVERIFIED which others call it: grep before edit); `discovery.py` (new eligibility, `thin_volume`, no volume cut); `api/data/discovery.json` (`universe_rules`); `api/data/attention_universe.json` (lists -> `classes`; `reference` kept; `exchange_tokens` list removed); `api/models/discovery.py` (additive fields); tests `test_universe.py`, `test_discovery.py`.
- **NOT touch:** `web/`, `decisions.md` (U6), `.github/`, `signal_snapshots.py`.
- **Tasks:** red tests; classes (16 stablecoins incl. USDG RLUSD U; 8 tokenized funds as `no-market` via the tradeability step with detail `tokenized fund`); tradeability input = a stubbed per-venue map (real lists arrive in U5; until then `unknown` -> `tradeability-unverified`, so coins are NOT cut); `thin_volume` flag; reasons closed list `stablecoin|wrapped-staked|no-market|not-tradeable-config`; counts; config validation.
- **Red tests:** `test_stablecoin_count_is_16_on_fixture_snapshot`, `test_leaked_stablecoins_usdg_rlusd_u_excluded`, `test_tokenized_funds_reason_no_market`, `test_wrapped_staked_excluded_with_reason`, `test_failed_venue_list_is_unknown_coin_stays_in`, `test_no_volume_cut_zero_and_null_volume_stays`, `test_thin_volume_label_below_20m_only_label`, `test_leo_cro_gt_pi_nexo_shown_without_force_include`, `test_force_include_and_not_tradeable_both_is_config_error`, `test_uni_jup_aero_cake_hype_eligible`, `test_excluded_counts_sum_to_universe_minus_shown`, `test_removed_config_keys_rejected` (old keys in cfg raise a clear error).
- **ACs:** AC-U3..U5, AC-U6', AC-U7, AC-U8. **Tier RT2.** **Model:** opus. **Rollback:** revert PR; the three JSON files return to old keys together.

### U3: web
- **Objective:** show "N of 100 shown, M excluded" with reasons, thin label, Unassigned bucket, hidden narratives.
- **Edit/create:** `web/components/narrative/DiscoveryTab.tsx` (line under `discovery-as-of`, `NO_DATA_LINES` add nothing new), `DiscoveryTable.tsx` (thin tag in coin row 213-232, unassigned/hidden `<details>` like `discovery-empty-categories` 161-166), new `DiscoveryExclusions.tsx`, `web/lib/types/discovery.ts` (UNVERIFIED path, read first), test files beside existing ones (`web/__tests__/` UNVERIFIED layout).
- **NOT touch:** `api/`, `DiscoveryHistoryChart.tsx` (unless a type break forces a one-line change, then report), `.github/`.
- **Red tests (vitest):** `shows_n_of_100_shown_m_excluded_with_reason_counts`, `lists_excluded_coin_with_reason_on_expand`, `thin_volume_tag_rendered_for_thin_coin_only`, `unassigned_bucket_rendered_when_nonempty`, `hidden_narrative_listed_not_in_table`, `proposed_narratives_banner_when_status_proposed`.
- **ACs:** AC-U10, AC-N5, AC-N6. **Tier RT1** (`pnpm --filter web test`, `exec tsc --noEmit`). **Model:** opus. **Rollback:** revert PR (API fields additive, old web ignores them).

### U4: CoinGecko and Wikipedia cover the universe
- **Objective:** the SPEC section 3 fix: symbol list from the universe snapshot, id from the snapshot row, counted `no-id`.
- **Edit:** `api/scripts/refresh_attention.py` (`_symbols` 115-121 reads `wiki_articles.json` keys; `_run_coingecko` 134-139 builds ids from `fetch_top100` which drops stablecoins/wrapped at `coingecko_attention.py:65`; `outcome_summary` UNVERIFIED line ~50), `api/data/attention/coingecko_attention.py` (only if ids need `id` passthrough), tests under `api/tests/scripts/` or `api/tests/data/` (locate before edit). **Create:** none.
- **NOT touch:** `universe.py`/`discovery.py` (U1/U2 own them), `.github/` (the workflow keeps calling the same entrypoint), `wiki_articles.json` (the 45-missing mapping is a later task).
- **Red tests:** `test_symbols_from_universe_snapshot_not_wiki_keys`, `test_id_taken_from_snapshot_row`, `test_missing_id_is_counted_no_id_outcome`, `test_explicit_symbols_arg_still_wins`, `test_stablecoin_not_requested`.
- **ACs:** AC-U11. **Tier RT2 + owner PC probe P-CG** (live, after merge). **Model:** opus. **Rollback:** revert PR; the previous symbol source returns.

### U5: source ladder, low-data rows, venue lists
- **Objective:** a coin with no usable source is a visible `low-data` row; venue lists replace the stub.
- **Create:** `api/data/attention/tradeable_markets.py` (one `load_markets` call per venue, dated store beside the universe snapshot; ccxt use UNVERIFIED, not read), tests. **Edit:** `discovery.py` (`_coin` None -> low-data row; `build_discovery` 190-196), `models/discovery.py` (`DiscoveryCoin` low-data fields; `covered_weight` 0 allowed), `refresh_attention.py` ONLY the new venue-list step (coordinate: U4 merged first, then U5 edits the same file: **U4 and U5 are never parallel**; they are in different waves).
- **NOT touch:** `.github/` (if the venue-list job needs a workflow step it is a follow-up for the planner, **flagged loudly**: the PLAN assumes no workflow change; the refresh entrypoint runs the step), source weights, `exchange_volume.py` series logic.
- **Red tests:** `test_no_source_coin_shown_low_data_with_reason`, `test_ladder_order_volume_wikipedia_trends_reddit`, `test_low_data_not_scored_zero_and_not_in_mean`, `test_coin_with_only_coingecko_volume_uses_fallback`, `test_venue_fetch_failure_marks_unknown`, `test_hyperliquid_scaled_names_kpepe_matches_pepe`, `test_any_venue_true_is_tradeable`.
- **ACs:** AC-U9', AC-U8 (venue half). **Tier RT2; owner probe P-VEN.** **Model:** opus. **Rollback:** revert PR (stub tradeability returns, coins stay in as unverified).

### U6: D-20 supersede and docs
- **Edit:** `process/context/decisions.md` (new entry after D-20; D-20 status line set to `superseded by D-NN`), `process/context/all-context.md` and `context-changelog.md` only if they cite exclusion lists (UNVERIFIED, grep first). **NOT touch** code. **Tier RT0** (`git diff --check`; `validate-context-discovery.mjs`). **Model:** sonnet. **Rollback:** revert PR.
- **Entry text (to paste, number = next free D-id at the time):**
  > ### D-NN Exchange tokens are IN as a narrative (supersedes D-20)
  > - **Decision:** owner decided 2026-10-18: exchange tokens (BNB, WBT, LEO, CRO, OKB, HTX, BGB, GT, KCS and later ones) are IN the Discovery universe as the narrative "Exchange tokens", and HYPE, PUMP, NEXO have it as primary. There is no volume floor and no volume cut; volume under 20M only adds a "thin volume" label. Exclusions are stablecoins, tokenized funds (reason "no market"), wrapped/staked/bridged copies and coins with no market on Binance, Coinbase, Kraken or Hyperliquid; each shows its reason on the page. Placement lives in `api/data/attention_narratives.json` and `universe_rules` in `discovery.json`.
  > - **Date:** 18-10-26. **Reason:** the goal is attention on coins the owner can trade; exchange tokens are tradeable and have their own attention. **Alternatives:** keep the exclusion list (rejected by the owner); keep a 5M backup floor (rejected).
  > - **Consequences:** thin exchange tokens will often be "low data"; `exchange_tokens` list and `include_despite_category` are removed from the config.
  > - **Status:** active. D-20 status becomes superseded.

## 7. Interactions (decision 11)
- **#140 (T106) not merged on main:** its `min_category_coins` and sources panel are UNVERIFIED. Ownership: narratives loader owns the 3-rule (U1). A rebase task after #140 merges maps `min_category_coins` to `universe_rules.min_narrative_coins` and extends the sources panel with the `low_data_reason` (U5). If #140 merges first, U1 and U3 must be re-measured by the planner before dispatch (conflicts on `discovery.py`, `DiscoveryTab.tsx`).
- **#139 (T107) not merged:** the chart panels use category ids from `DiscoveryTable.tsx:151` and `DiscoveryHistoryChart.tsx:92`; U1's id map keeps stored ids resolvable; nothing in #139 is edited by this PLAN.
- **Frozen snapshots:** `signals/2026-10-17_w*.json` (the three present) store `category_ids` and a `config` copy; read-only, mapped on read only.

## 8. Acceptance Criteria (mapped to SPEC)
| ID | Criterion | Source | Slice |
|---|---|---|---|
| AC-U1' | `attention_narratives.json` loads; duplicate or missing primary, bad symbol are named errors; < 3 in-universe coins is NOT an error (hidden) and an uncovered coin is NOT an error (Unassigned) | rewrites AC-U1 | U1 |
| AC-U2' | Every in-universe coin has exactly one primary narrative or sits in Unassigned; any number of other memberships; BNB LEO OKB HYPE PUMP NEXO appear under Exchange tokens | rewrites AC-U2 | U1 |
| AC-U3 | `exclude_category_ids` gone; UNI JUP AERO CAKE HYPE eligible on the 2026-10-18 fixture | SPEC AC-U3 | U2 |
| AC-U4 | classification on the fixture: stablecoin 16, tokenized fund 8 (reason no-market), USDG RLUSD U stablecoins | SPEC AC-U4 (exchange-token count 9 now a narrative size, not a class) | U2 |
| AC-U5 | every excluded coin has a closed-list reason; `excluded_counts` sums to `universe_size - shown_size` | SPEC AC-U5 (list without `volume-below-floor`) | U2 |
| AC-U6' | no volume cut at any level; null/zero volume stays; under 20M shows `thin_volume: true`; `backup_floor_usd` absent from code and config | rewrites AC-U6 | U2 |
| AC-U7, AC-U8 | `force_include`+`not_tradeable` same symbol = config error; failed venue = unknown, coin stays `tradeability-unverified` | SPEC | U2, U5 |
| AC-U9' | no-source coin shown `low-data` with reason, never dropped, never scored 0 | sharpens AC-U9 | U5 |
| AC-U10 | web: "N of 100 shown, M excluded" with reasons | SPEC | U3 |
| AC-U11 | runner covers every in-universe symbol with a snapshot id; missing id = counted `no-id` | SPEC | U4 |
| AC-U12 | superseding decision recorded in `decisions.md` | SPEC | U6 |
| AC-N1 | `narratives_status` ("proposed"/"reviewed") in the response; web banner while proposed | new (G-OWN) | U1, U3 |
| AC-N2 | multi-membership: a coin in 3 narratives is counted in each aggregate and each counts to the minimum | new | U1 |
| AC-N3 | Unassigned bucket lists new top-100 coins with no narrative; response flags them; no error | new | U1, U3 |
| AC-N4 | old snapshot ids resolve through the map; frozen files byte-identical; history payload shows `definition_changed` date | new | U1 |
| AC-N5 | hidden narrative (< 3 coins) listed under "hidden" with its count, not in the table | new | U1, U3 |
| AC-N6 | label-only volume visible in the UI as a tag | new | U3 |

## 9. Owner PC probes (after each slice; providers unreachable here)
| After | Probe | Expect |
|---|---|---|
| U1 | open Discovery, check coin-to-narrative table in the U1 report vs the page; flip `status` to `reviewed` | G-OWN done |
| U2 | `GET /api/narrative/discovery?window=30` locally | 16 stablecoin exclusions, `shown_size` near 84 minus no-market; no `volume-below-floor` |
| U4 (P-CG) | run the refresh for `coingecko` locally; read `probe_records.json` | `coins_ok` near the in-universe count (was 56 of 103); `no-id` counted |
| U5 (P-VEN) | run venue-list step with network; read the stored map | Binance and Hyperliquid lists loaded; PEPE/SHIB alias resolved; any failed venue shows `unknown` not `no market` |
| U3 | open the tab | counts line, thin tags, Unassigned empty (or lists M) |

## 10. Risks
- G-OWN delay blocks U2/U3 live claim; mitigated by the `proposed` flag so coding proceeds.
- #139/#140 merge order changes `discovery.py`/`DiscoveryTab.tsx`: re-measure before dispatch.
- Unlimited memberships inflate narrative counts and correlate aggregates (no cross-narrative total, as today).
- Many thin exchange tokens produce low-data rows until Trends/Reddit per coin exist.
- Changing the config changes `config_hash`: one `config-changed` day in the snapshot job, expected.
- Live unknowns: Binance reachability (HTTP 451 from US runners), Coinbase/Kraken lists absent (W7), CoinGecko 429 history, ccxt behaviour (UNVERIFIED).
- UNVERIFIED reads: `web/lib/types/discovery.ts`, `outcome_summary`, test file locations in `api/tests/scripts`, `categories_store`, ccxt.

## 11. Validate Contract (to be filled by VALIDATE)

Verification gates, placeholders only:
| Gate | Command / check | Pass criterion | Filled by |
|---|---|---|---|
| G1 | `uv run --project api pytest api/tests/analytics/attention -q` | TBD by VALIDATE | PENDING |
| G2 | `uv run --project api pytest api/ -q` (once per RT2 slice) | TBD | PENDING |
| G3 | `pnpm --filter web test` and `exec tsc --noEmit` (U3) | TBD | PENDING |
| G4 | `git diff --stat origin/main -- .github/ api/data/narratives.json api/data/cache/attention/signals/` | empty | PENDING |
| G5 | `git diff --check`; plan validator on this file | TBD | PENDING |
| G6 | frozen snapshot sha256 unchanged | TBD | PENDING |
