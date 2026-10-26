---
name: report:narrative-baskets-universe-t189-tradeability
description: "T189: reasoned exclusion `not-tradeable` in Discovery (zero 24h volume; no listed market once every tracked list is loaded) and a read-only venue-list module over stored Hyperliquid data. Binance list not stored: unknown, never excluded."
date: 26-10-26
feature: narrative-baskets
metadata:
  node_type: memory
  type: report
---

# T189 not-tradeable exclusion and venue lists: REPORT

## 1 Task ID

T189 (plan slice U5 narrowed to tradeability; owner decision 26-10-26; planner re-scope to "option 2" the same day). Branch `claude/t189-not-tradeable`, one draft PR to `main`, not merged.

## 2 Outcome

DONE within the narrowed scope. First pass STOPPED under the envelope's stop rule (no `markets` source exists and Binance has no stored per-symbol list or volume); the planner then approved the smaller version: zero-volume rule plus the stored Hyperliquid perp list, Binance = unknown. No network code written.

## 3 Summary

**Rule (owner, 26-10-26): no trading market = excluded.** Per symbol, `tradeable_markets.tradeability(symbol, venues, volume_24h)` answers:

- `tradeable`: a fresh tracked list (Binance or Hyperliquid, spot or perp) has it with 24h volume above zero, or listed with no stored volume;
- `not_tradeable`, detail `zero 24h volume`: the universe snapshot's 24h volume is exactly 0 and no fresh list shows volume (null volume is NOT zero);
- `not_tradeable`, detail `no listed market on Binance or Hyperliquid`: every tracked list is loaded and fresh, and none has it with volume. Cannot fire today (Binance missing);
- `unknown`: anything else. A missing, failed or stale list proves nothing either way (fail-closed toward keeping coins).

**Discovery.** New reason `not-tradeable` in the closed list (`universe_classes.REASONS`), after `not-tradeable-config`. Order per coin unchanged otherwise: `force_include` > class (stablecoin, wrapped-staked, tokenized fund = `no-market`) > `not_tradeable` config > venue verdict. So tokenized funds with zero volume keep their reason `no-market`; only non-class coins get `not-tradeable`. Counted in `excluded_counts` and in the legacy `excluded.exclusion_list`, so both identities still hold (`shown_size + sum = universe_size`). An unknown coin stays IN with `tradeability: "unverified"` (existing value kept).

**Additive payload** (no field renamed, no reason string changed): `tradeability_unknown` (int, shown coins with `unverified`) and `venue_lists` ([{venue, status ok|missing|failed|stale, as_of}]).

**Web (text and one tag):** reason label "not tradeable (zero trading volume)" in the counts line; sentence "No trading market: zero 24h trading volume, or not listed on Binance or Hyperliquid."; a separate note "Tradeability unknown: N (Binance list not loaded yet)" (failed: "failed to load", stale: "out of date"); a per-coin "tradeability unknown" tag next to "thin volume"; footer now "Coins whose tradeability is unknown stay in: a missing or out-of-date exchange list never excludes a coin."; the `no-market` sentence now says "Tokenized funds: no exchange market to trade them on." (it no longer claims a Coinbase/Kraken check).

**Venue module** `api/data/attention/tradeable_markets.py` (pure reader; a test asserts no httpx/ccxt/requests/urllib/socket in it). Inputs, newest file dated on or before `today` (point in time):

1. `cache/attention/markets/{venue}/{YYYY-MM-DD}.json`: the store a later `markets` runner writes. **Contract for that slice:**
   `{"venue": "binance", "as_of": "YYYY-MM-DD", "status": "ok" | "failed", "reason": "...", "markets": [{"symbol": "<venue base name>", "kind": "spot" | "perp", "volume_24h": float | null}]}`.
   `status` other than `ok`, a missing `markets` list, unreadable JSON or a market without `symbol` = `failed`. Several markets for one coin (spot + perp, PEPE + 1000PEPE) merge: positive volume wins, then null, then 0. Staleness: `today - as_of > 2 days` = `stale` (2 days old is still fresh). A store file wins over the fallback below.
2. Hyperliquid fallback while (1) is empty: the narrative job's perp list `cache/narrative/exchange/markets/{date}.json` (names only) plus 24h volume from `cache/attention/hyperliquid_volume/{SYM}.parquet` (newest point within 2 days of the list date, else "not stored").

Aliases: a reviewed explicit table (`ALIASES`), no generic prefix strip (KAS, KAITO are real). Hyperliquid `kPEPE kSHIB kBONK kFLOKI kNEIRO kLUNC` (seen in the stored list); Binance `1000PEPE 1000SHIB 1000BONK 1000FLOKI 1000LUNC 1000SATS 1000RATS 1000CAT 1000CHEEMS 1000XEC 1MBABYDOGE 1000000MOG` (Binance USD-M naming, UNVERIFIED until P-VEN). Case folded.

A later `markets` runner plugs in by writing (1); Discovery, the module API and the web need no change. With both lists fresh, the `no listed market` rule starts excluding.

**Today, from the stored data** (universe snapshot 2026-10-25, 100 coins; Binance `missing`; Hyperliquid `ok` as of 2026-10-25, 55 universe coins listed incl. PEPE, SHIB via kPEPE, kSHIB):

| Outcome | n | Coins |
|---|---|---|
| Excluded `not-tradeable` (new) | 1 | JAAA (zero 24h volume) |
| Zero volume but already out as tokenized fund (`no-market`, unchanged) | 4 | USYC BUIDL USTB EURSAFO |
| Other tokenized funds (`no-market`, unchanged) | 2 | USDY FIGR_HELOC |
| Stablecoins (unchanged) | 16 | USDT USDC USDS USDE DAI USD1 USDG PYUSD RLUSD USDF USDD U BFUSD USDGO OUSD GHO |
| IN, `tradeable` (on Hyperliquid) | 55 | |
| IN, `unknown` (not on Hyperliquid, Binance not loaded) | 22 | WBT LEO RAIN XAUT CRO QNT BTW OKB M HTX BGB JST KCS GT PI NEXO AKE PEARL XDC NIGHT BDX VET |

Eligible: 77 (78 before: JAAA out). The planner's "unknown 47" was coins not on Hyperliquid by raw name; with aliases it is 45, of which 23 are excluded anyway (16 stablecoins, 6 funds, JAAA) and 22 are IN-unknown. Venue verdict alone, ignoring classes: 40 unknown.

**Other tests depending on live eligibility counts:** none on `main` (grep for 78/72 and live `eligible_coins` asserts). PR #174 pins a constant `PINNED_ELIGIBLE` (78, reviewed 2026-10-24; JAAA not in it) and only asserts `> 0` / a prefix on the live set: not broken. #174 also edits `discovery.py`, `models/discovery.py`, `web/lib/types/discovery.ts` and `DiscoveryTab.test.tsx`: expect a textual merge conflict for whichever lands second (additive on both sides).

## 4 Files changed

- New: `api/data/attention/tradeable_markets.py`, `api/tests/data/attention/test_tradeable_markets.py`, this report.
- API: `api/analytics/attention/universe_classes.py` (stub `venue_lists`/`VENUES`/old `tradeability` removed; `build(rows, rules, venues=None, today=None)`), `api/analytics/attention/discovery.py` (`eligibility(..., today=)`, legacy sum, two new fields), `api/models/discovery.py` (`DiscoveryVenueList`, two fields, comments).
- Web: `web/components/narrative/{DiscoveryExclusions,DiscoveryTab,DiscoveryTable}.tsx`, `web/lib/types/discovery.ts`.
- Tests edited: `test_universe_classes.py`, `test_discovery.py`, `routers/test_discovery.py`, `DiscoveryExclusions.test.tsx`, `DiscoveryTab.test.tsx`.
- Not touched: `.github/`, `pyproject.toml`, `uv.lock`, `api/data/discovery.json`, data caches, weights, scoring.

## 5 Commits

1. red: `test(discovery): red tests for not-tradeable exclusion and venue lists (T189)` (API 13 failing + module import error; web 7 failing).
2. green: implementation, two mutation-driven tests, a fix to one red test (JAAA appended as row 101 was cut by TOP_N; it now replaces the 100th coin EUTBL at the same cap) and this report.

## 6 Tests run

- Gate set `pytest api/tests/analytics/attention api/tests/data/attention api/tests/routers api/tests/scripts api/tests/tooling_guards`: 1528 passed, 1 deselected, 0 failed (run before the two mutation tests; the full run below covers the final tree).
- Full `pytest api` on the final tree: **2265 passed, 1 skipped, 5 deselected, 0 failed**; `main` 112e32c baseline 2213 passed, 1 skipped, 5 deselected (+52 = 42 new module cases + 10 new Discovery/router tests, 4 replaced in place, see 8; skipped and deselected unchanged).
- Web: `pnpm test` 577 passed in 63 files; touched files 42 passed; `tsc --noEmit` exit 0; `pnpm build:islands` exit 0.
- ruff on touched files: new module clean; the remaining findings (I001 import style, TRY004, C401, C408, UP037) are the same as on `main`.
- `git diff --check` clean; secret scan (grep for key/token/secret patterns on the diff) clean; file-set check clean.
- Mutation check, 17 hand mutants on the verdict, staleness, aliases, case folding, merge, point in time, HL volume window, store status, the build branch, force_include, legacy sum, the unknown count and the `today` pass-through: 15 killed first pass; 2 survived (store `status` ignored when `markets` present; unknown count over eligible instead of shown), two tests added, both killed: 17/17.

## 7 Tests NOT run

Playwright e2e (`web/e2e/narrative.spec.ts`; it mocks routes; coins with `tradeability: "unverified"` now also show the new tag; no assertion counts tags). Live Binance/Hyperliquid (not reachable from the container; owner probe below).

## 8 Deviations

- Replaced tests: `test_no_volume_cut_zero_and_null_volume_stays` -> `test_zero_volume_is_not_tradeable_null_and_low_volume_stay` (owner rule reverses it); `test_thin_volume_label_below_20m_only_label` uses `TINY: 1.0` instead of `ZERO: 0` (zero is now excluded); `test_failed_venue_list_is_unknown_coin_stays_in` rewritten for the new venue type (old stub API removed); `test_excluded_counts_sum_to_universe_minus_shown` gains a zero-volume coin and the new key.
- Per-coin tag added in `DiscoveryTable.tsx` (the envelope asked for a "visible flag"); beyond the counts-line text.
- A positive venue volume beats a zero snapshot volume (a fresh market is proof of a market); stated in the module docstring.
- Discovery history, sources and the Trends checker call `eligibility` without `today`: they read the stored lists as of the UTC date (only the flag differs; exclusion uses the row's own volume).

## 9 Blockers

None for this scope. The `no listed market` rule needs a Binance list: no runner exists (stop finding of the first pass).

## 10 Follow-up

- Planner: a `markets` slice (ccxt `load_markets` + tickers for Binance and Hyperliquid, spot and perp, writing the contract in 3; opt-in, Binance answers HTTP 451 from US runners) plus a workflow step.
- When it lands: the counts label "not tradeable (zero trading volume)" should widen to "not tradeable (no market)" (text only), and tests that call `eligibility` on the real cache must isolate it.
- **Owner probe P-VEN-lite (PowerShell, repo root, after merge):**

```powershell
git pull
$env:UV_FROZEN = "1"
uv run --project api python -c "from api.analytics.attention import discovery as d, universe; rows,_ = universe.load_universe_rows(); u = d.eligibility(d.load_config(), rows); print({k: (v.state, v.as_of, len(v.volumes)) for k, v in u.venues.items()}); print('excluded:', sorted((s, r, x) for s, (r, x) in u.out.items() if r in ('not-tradeable', 'no-market'))); print('unknown:', sorted(s for s, t in u.tradeability.items() if t == 'unverified'))"
```

Expect: binance `missing`, hyperliquid `ok` with today's or yesterday's date; JAAA excluded with `zero 24h volume`; the unknown list as in the table (it moves with the snapshot).

## 11 Context cost

Read: CLAUDE.md, the envelope and planner message, PLAN sections U2/U5/9/10 and the SPEC tradeability section (grep), `discovery.py`, `universe_classes.py`, `models/discovery.py`, `refresh_attention.py` (runners), `exchange_volume.py`, `hyperliquid_narrative_adapter.py` (head), `cache.py` exchange-store helpers, `store.py`, web Discovery components and tests, PR #174's guard test. No other root context docs opened.
