---
phase: rfc-001-stage0
date: 2026-09-24
status: COMPLETE
feature: narrative-mindshare
plan: process/features/narrative-mindshare/active/narrative-dashboard_24-09-26/narrative-dashboard_PLAN_24-09-26.md
---

# RFC-1 Stage 0 — Findings (research only, STOP)

**Bottom line:** Stage 0 is stopped at the E1 hard gate. `api/data/watchlist.json` does not exist in
this container, so no widened map is proposed. Two user inputs are needed before Stage 1: (1) the real
watchlist, (2) an A/B choice on drift. No source/data/test files were written.

## What Was Done

### 1. Watchlist (E1) — BLOCKED
- `api/data/watchlist.json`: **absent** (`ls` fails). `read_watchlist()` returns `[]` when the file is
  missing (`_load_raw` → `{"coins": []}`), so it is indistinguishable from an empty watchlist.
- `api/data/watchlist.example.json` exists (`BTC, HYPE, ETH, SOL`) — per E1 this is NOT used as a proxy.
- `SCREENER_WATCHLIST_PATH` env override exists; not set here.
- **Needed from the user:** the content of their real `api/data/watchlist.json`, format:
  ```json
  { "coins": ["BTC", "ETH", "HYPE", "..."] }
  ```
  Upper-case ticker symbols (the store upper-cases on add). Or: run Stage 0 on the user's own PC.

### 2. Current state of the map and seeds
- Seeds (`api/data/narrative_categories.json`): `ai`, `rwa`, `l2s`, `memecoins` (id/label/keywords).
- `mapping.py::COIN_CATEGORY_MAP`: `BTC→store-of-value`, `ETH→l2s`, `HYPE→l2s`.
- **Finding:** `store-of-value` is not a seed category. BTC therefore always resolves to
  `narrative_state = "unavailable"` (has a mapping, category never computed) — documented in
  `badge.derive_narrative_state`. AC-1 requires this stay as is.
- Only `l2s` currently has member coins.

### 3. Proposed `narrative_category_map.json` schema and mapping rule
```json
{
  "version": 1,
  "map": { "BTC": "store-of-value", "ETH": "l2s", "HYPE": "l2s" }
}
```
- Keys: upper-case symbols. Values: a category id string.
- Rule (no inference): a coin is mapped only by explicit user approval, to one id. Never derived from
  name, description, CoinGecko tags or fuzzy match. Unlisted → `None` (`unmapped`).
- Recommended constraint: new entries may only point to an id present in `narrative_categories.json`
  seeds (or a seed approved at this Stage 0). Legacy `BTC→store-of-value` is kept as a grandfathered
  exception for AC-1. Mapping a new coin to a non-seed id would move it from `unmapped` to
  `unavailable`, which forces its badge down (see §4b).
- Load failure (missing/invalid JSON) → empty map, logged; not a crash (plan's post-phase test).

### 4. E5 drift — how a newly-mapped coin changes behaviour

**a) `/api/narrative/categories`** (`trigger.py::compute_narrative_categories`, ~L185-200):
1. `trending_count = sum(1 for s in trending.symbols if map_coin_to_category(s) == category_id)`.
2. That count is written to the `coingecko` narrative cache for the day (`write_narrative_point`,
   dedup-on-date, `keep="last"` — a same-day rewrite replaces).
3. The whole `coingecko` history is re-read, normalised within-source, and fed to `compute_trigger`
   → composite → `triggered`; then `apply_confirmation` → `confirmed`, `trust_weight`.
So: a newly-mapped coin to `l2s` (or any seed) that appears in CoinGecko trending raises that day's
count, and the change is **persisted** in the cache, so it also shifts normalisation of all later days.
Drift is not one-day-only.

**b) `/screener` `narrative_state`** (`screener_board.py::_coin_narrative_state`, L101-111):
- Unmapped coin today → `unmapped`. After mapping:
  - to a computed seed → `in-focus` / `confirmed-emerging` / `unconfirmed-emerging` / `rotated-out` /
    `unavailable` depending on that category's result;
  - to a non-seed id → `unavailable`.
- `badge.compute_badge` treats `narrative_state == "unavailable"` as a downgrade condition (see
  `test_confidence_badge.py::_expected` L44). So the confidence badge itself can change, not just the
  narrative label.

**Option A — accept drift for newly mapped coins; narrow AC-1 to existing mappings.**
- Code: trigger keeps calling `mapping.map_coin_to_category` (now JSON-backed). One map everywhere.
- Consequence: `/categories` numbers for any seed that gains a member can differ from today on days
  that coin trends; the cached `coingecko` series diverges going forward. Newly-mapped coins' screener
  badges change.
- Tests: contract snapshot asserts byte-identity only for fixtures where trending contains BTC/ETH/HYPE
  or unmapped coins; a separate test asserts the *expected new* count when a newly-mapped coin trends
  (drift is pinned, not hidden). AC-1 wording in plan/SPEC must be amended.

**Option B — keep AC-1 strict; trigger uses the legacy 3-entry map.**
- Code: `trigger.py` switches to a frozen legacy lookup (e.g. `mapping.map_coin_to_category_legacy`
  backed by the current 3-entry dict), while the widened JSON map serves `/history`, the new
  `/narrative` surfaces, and (decision needed) `screener_board`. Two maps coexist — a second mapping
  path to document and keep consistent.
- Sub-question for B: does `/screener` use the legacy map (fully strict, new coins stay `unmapped`) or
  the widened map (badge drift accepted there only)?
- Consequence: `/categories` byte-identical for any trending fixture; `/history` and `/categories` can
  disagree on trending membership for new coins — must be labelled.
- Tests: contract snapshot includes a newly-mapped coin in the trending fixture and asserts
  byte-identity (the plan's E5 scenario passes as written); plus a test that `/history` does count it.

**Not chosen** — user decision.

### 5. Existing tests that pin current behaviour
- `api/tests/analytics/test_mapping.py`: mapped coin → category; case-insensitive; unmapped → `None`.
- `api/tests/analytics/test_narrative_trigger.py`: trigger/confirmation/degraded-source/presumed-dead
  (15 tests; mostly `compute_trigger`/`apply_confirmation`, source adapters).
- `api/tests/routers/test_narrative.py`: empty list, seed metadata, single/all-source failure.
- `api/tests/routers/test_screener.py` (+ `test_screener_integration.py`): data-binding with empty
  categories → `unavailable`.
- `api/tests/analytics/test_confidence_badge.py`: full badge truth table incl. `unmapped`/`unavailable`.
- **Contract snapshot test** (`test_narrative_categories_contract.py`, new): full `/categories` response
  for all 4 seeds with mocked pytrends/reddit/CoinGecko trending and isolated `CACHE_ROOT`, captured
  pre-RFC and asserted byte-identical after; includes a scenario with a newly-mapped coin in trending
  for each seed that gains a member. Under A that scenario asserts the new expected value; under B it
  asserts byte-identity.

### 6. Cache signatures (confirmed)
- `read_narrative_series(source, category_id) -> DataFrame` ordered by date; empty frame if missing.
- `write_narrative_point(source, category_id, date, raw_value, source_status="fresh")` — dedup on
  date, **overwrites** (keep last). RFC-2 backfill must not blindly rewrite dates it doesn't own.

## What Was Skipped or Deferred
- Widened map / seed list proposal — blocked by E1 (no watchlist).
- OQ-4 per-coin screener-state table and seed-exposure list — needs watchlist.

## Test Gate Outcomes
Not run (Stage 0 is research only).

## Plan Deviations
None.

## Test Infra Gaps Found
None new.

## Closeout Packet
- Plan: see frontmatter. Finished: Stage 0 research. Unverified: everything implementation-side.
- Next valid state: user supplies watchlist + A/B (and B sub-choice) → re-run Stage 0 to produce the
  per-coin map + OQ-4 table → E4 sign-off → Stage 1.

## Forward Preview
- Test Infra Found: `CACHE_ROOT` and `SCREENER_WATCHLIST_PATH` overrides allow isolated contract tests.
- Blast Radius Changes: Option B adds a second lookup in `mapping.py` and touches `trigger.py`.
- Commands to Stay Green: `uv run --project api pytest api/ -q`; `pnpm --filter web test`; `cd web && pnpm test:e2e`.
- Dependency Changes: none.

TL;DR: blocked on missing watchlist (E1); user must also pick drift option A or B.

---

# Update 2026-09-24 — user decisions recorded, map proposed (Stage 0 still; nothing implemented)

**Bottom line:** the proposed map below (29 coins across the 4 seeds, plus BTC as the legacy entry) is
ready for your approval. The Hyperliquid listing of each coin is **unverified**: there is no offline
ccxt market metadata here (no Hyperliquid cache; `ccxt.hyperliquid().markets` is empty without network).

## Recorded Decisions (user-approved in chat, 2026-09-24)
| # | Decision | Choice |
|---|---|---|
| D1 | E5 drift | **B** — keep AC-1 strict; the trigger's CoinGecko count uses a frozen legacy 3-entry map |
| D2 | Screener map | **Legacy 3-entry map** — `/screener` `narrative_state` byte-identical |
| D3 | E1 watchlist gate | **Option 3** — no watchlist sizing; curated well-known coins per seed category (~5–8 each) |
| D4 | Labelling | Coins mapped only in the new map show as **"narrative-only"** on `/history` and `/narrative` |

The E1 gate is closed by D3, not by reading a watchlist. E4 still applies: nothing is written to
`narrative_category_map.json` until you approve the table below.

## Proposed `narrative_category_map.json`
Seed ids from `api/data/narrative_categories.json`: `ai`, `rwa`, `l2s`, `memecoins`.
HL = Hyperliquid perp ticker. HL status for every row: **unverified** (the HL column is from memory,
not checked). HL lists some low-priced memecoins with a `k` prefix (1,000 units), e.g. `kPEPE` —
the map key stays the plain symbol, and any HL ticker translation belongs to RFC-2's adapter.

| Symbol | Category | HL ticker | Legacy? | Rationale |
|---|---|---|---|---|
| BTC | store-of-value (**non-seed**) | BTC | legacy | Kept exactly as is for AC-1; never computed, so it stays `unavailable` |
| ETH | l2s | ETH | legacy | Settlement layer for the L2 ecosystem (existing entry) |
| HYPE | l2s | HYPE | legacy | Existing entry, kept as is (it's really an app-chain; not re-classified) |
| ARB | l2s | ARB | new | Arbitrum, the largest optimistic rollup |
| OP | l2s | OP | new | Optimism / OP Stack (Base and other chains build on it) |
| STRK | l2s | STRK | new | Starknet, a ZK rollup |
| ZK | l2s | ZK | new | ZKsync, a ZK rollup |
| MNT | l2s | MNT | new | Mantle, a modular L2 |
| POL | l2s | POL | new | Polygon (ex-MATIC), L2/zkEVM ecosystem |
| IMX | l2s | IMX | new | Immutable X, a gaming L2 |
| FET | ai | FET | new | Artificial Superintelligence Alliance (Fetch.ai/Ocean/SingularityNET merger) |
| TAO | ai | TAO | new | Bittensor, a decentralized ML network |
| RENDER | ai | RENDER | new | Render, GPU compute for AI/graphics |
| WLD | ai | WLD | new | Worldcoin, an OpenAI-adjacent identity project |
| VIRTUAL | ai | VIRTUAL | new | Virtuals Protocol, an AI-agent launchpad |
| AI16Z | ai | AI16Z | new | ai16z / ElizaOS, the AI-agent framework token |
| AR | ai | AR | new | Arweave / AO, permanent storage + AI compute narrative (weakest fit; drop if unsure) |
| ONDO | rwa | ONDO | new | Ondo Finance, tokenized treasuries |
| ENA | rwa | ENA | new | Ethena, a synthetic dollar with a treasury-backed product (borderline fit) |
| PENDLE | rwa | PENDLE | new | Pendle, yield trading heavily tied to RWA yields (borderline fit) |
| MKR | rwa | MKR | new | Maker/Sky, the largest on-chain RWA collateral holder |
| POLYX | rwa | POLYX | new | Polymesh, a securities-token chain |
| OM | rwa | OM | new | MANTRA, an RWA chain (was heavily delisted/crashed in 2025; drop if unsure) |
| LINK | rwa | LINK | new | Chainlink, the oracle/CCIP layer used by tokenization pilots (borderline fit) |
| DOGE | memecoins | DOGE | new | Dogecoin, the original memecoin |
| PEPE | memecoins | kPEPE | new | Pepe |
| WIF | memecoins | WIF | new | dogwifhat, Solana memecoin |
| BONK | memecoins | kBONK | new | Bonk, Solana memecoin |
| SHIB | memecoins | kSHIB | new | Shiba Inu |
| POPCAT | memecoins | POPCAT | new | Popcat, Solana memecoin |
| FARTCOIN | memecoins | FARTCOIN | new | Fartcoin, Solana memecoin |
| TRUMP | memecoins | TRUMP | new | Official Trump memecoin |

Counts (new entries): l2s 7 (+2 legacy), ai 7, rwa 7, memecoins 8.
**Borderline rows to decide on:** HYPE-in-l2s (legacy, left alone), AR, ENA, PENDLE, LINK, OM.
**Seed categories gaining members:** `ai`, `rwa`, `memecoins` (new), `l2s` (more members). Under B,
none of them change on `/categories`.

## Resulting code shape for B (to implement in Stage 1+ after approval)
- `mapping.py`:
  - `LEGACY_COIN_CATEGORY_MAP` — the frozen 3-entry dict (renamed from `COIN_CATEGORY_MAP`; keep the
    old name as an alias so existing imports and `test_mapping.py` keep working).
  - `map_coin_to_category(symbol)` — **unchanged behaviour, legacy map only**. This is what
    `trigger.py` (~L185-200) and `screener_board.py::_coin_narrative_state` already call, so
    neither file needs editing.
  - New `load_category_map()` (JSON, same pattern as `trigger.load_seed_categories`; bad or missing
    file → empty map) and `map_coin_to_narrative_category(symbol) -> (category_id | None, narrative_only: bool)`,
    where `narrative_only = symbol in curated map and not in the legacy map`. Used only by
    `/history` and the `/narrative` UI.
- Consistency guard: every legacy entry must also be in the JSON map with the same value (a test enforces this).
- The `/history` response carries a `narrative_only` flag per mapped coin; the UI labels those coins "narrative-only".

**Contract tests**
- `test_narrative_categories_contract.py`: full `/api/narrative/categories` response (all 4 seeds),
  mocked pytrends/reddit/CoinGecko trending, isolated `CACHE_ROOT`. The fixture includes new coins
  that trend (e.g. ARB, FET, ONDO, DOGE). It asserts **byte-identity** with the pre-RFC snapshot and
  that the `coingecko` cache point for each seed is unchanged.
- Screener: a coin mapped only in the new map (e.g. ARB) still reads `unmapped` in `/screener`
  `narrative_state`; BTC/ETH/HYPE are unchanged; the full screener response for a fixed fixture is byte-identical.
- `test_mapping.py`: legacy lookup unchanged; new lookup covers the approved table and sets
  `narrative_only` correctly; unmapped → `None`; bad JSON → empty map; the legacy⊆JSON guard.

## Plan/SPEC text for UPDATE PROCESS to amend (not edited here)
- **ADR-7:** the JSON map no longer replaces `COIN_CATEGORY_MAP` for the trigger or screener; it
  drives only `/history` and `/narrative`. The legacy map is frozen. Sizing is by a curated list
  per seed category (D3), not by the watchlist.
- **AC-1:** the wording holds strictly (not narrowed). Add: "including when a coin mapped only in the
  new map appears in CoinGecko trending," and say that `/screener` is byte-identical too.
- **OQ-4:** resolve — no `/screener` or `/categories` drift under B; the new "narrative-only" label
  is the visible difference between the two views.
- **RFC-1 Stage 0 E1 gate text / Verification Checklist:** record the option-3 resolution in place of
  the "watchlist confirmed non-empty" item.
- **Component Details `narrative_category_map.json`:** "sized at RFC-1 Stage 0 against the real
  watchlist" → curated per seed category.
- **RFC-2:** confirm each HL ticker (incl. the `k` prefix) when the adapter is built; drop any that
  aren't listed.

TL;DR: decisions B, legacy screener map, and option 3 are recorded. A 29-coin map (+ legacy BTC) is
proposed; every HL ticker is unverified; approve or strike rows, then Stage 1 can start.
