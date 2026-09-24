---
phase: rfc-001-data-foundation
date: 2026-09-24
status: COMPLETE_WITH_GAPS
feature: narrative-mindshare
plan: process/features/narrative-mindshare/active/narrative-dashboard_24-09-26/narrative-dashboard_PLAN_24-09-26.md
---

# RFC-1 Phase Report — Data foundation (curated narrative map)

**Bottom line:** the curated, user-editable narrative map is in place under option B. `/categories` and
`/screener` are proven byte-identical against a snapshot taken before the change, including when newly
mapped coins are trending. 307 pytest passed / 2 deselected; 75 vitest passed (12 files). Not committed.

## Decisions (user-approved in chat, 2026-09-24)
- D1 drift = **B** (AC-1 strict; frozen legacy map for the trigger's CoinGecko count).
- D2 screener = **legacy 3-coin map** (`/screener` byte-identical).
- D3 E1 gate = **option 3** (curated well-known coins per seed category, not watchlist-sized).
- D4 coins only in the new map are labelled **"narrative-only"** on `/history` and `/narrative`.
- E4/OQ-4: the user approved the proposed map **as-is** — 29 new coins plus unchanged BTC/ETH/HYPE,
  including the borderline rows (AR, ENA, PENDLE, LINK, OM, HYPE in l2s). Quote: "good for now, just
  make sure i can change it to my wishes in the future".
- Extra done criteria from that answer: the JSON is the single user-editable place, edits apply without
  a restart (mtime reload), and it is validated on load (implemented, see below).

## What Was Done
- `api/data/narrative_category_map.json` (new, not git-ignored): `_comment` edit guide, `version: 1`,
  `map` of 32 entries (l2s 9, ai 7, rwa 7, memecoins 8, BTC→store-of-value grandfathered).
- `api/analytics/narrative/mapping.py`:
  - `LEGACY_COIN_CATEGORY_MAP`, frozen and documented; `COIN_CATEGORY_MAP` kept as an alias;
    `map_coin_to_category` is unchanged in behaviour (legacy only). `trigger.py` and `screener_board.py`
    are not edited.
  - `load_category_map(path=None, seeds_path=None)`: reloads when the mtime of either the map or the
    seed file changes (thread-locked cache). Missing/malformed file or non-object `map` → `{}` plus a
    warning. Entries with a non-uppercase/blank symbol, a non-string id, or an id that is not a seed (other
    than grandfathered BTC→store-of-value) are skipped with a warning naming the entry.
  - `map_coin_to_narrative_category(symbol) -> (category_id | None, narrative_only)`.
- `api/tests/routers/test_narrative_categories_contract.py` (new, 3 tests) plus golden
  `api/tests/routers/fixtures/narrative_categories_contract.json`, **captured before `mapping.py` was
  changed**. Two trending scenarios (legacy-only; with ARB/OP/FET/TAO/ONDO/LINK/DOGE/PEPE/WIF). It
  asserts: the full `assemble_narrative_categories` output for all 4 seeds, the per-seed CoinGecko cache
  point, and `_coin_narrative_state` for 8 symbols, all byte-identical; the two scenarios match each
  other; curated-only coins stay `unmapped` in the screener. The fixture triggers `ai`/`l2s`/`memecoins`,
  so the comparison is not vacuous.
- `api/tests/analytics/test_mapping.py` (+10 tests): legacy map frozen; the approved map loads with
  exact counts; legacy ⊆ curated; `narrative_only` flag; validation skips and warns; missing/malformed/
  non-object → empty; an on-disk edit takes effect without a restart.
- `process/features/narrative-mindshare/_GUIDE.md` Notes: "How to edit the narrative map".

## What Was Skipped or Deferred
- Stage 3 (widen `narrative_categories.json`): not needed; no new seed categories were approved.
- Verification query (`api/data/cache/narrative/pytrends/ai.parquet`): the file does not exist in this
  container (empty narrative cache; FRED/DefiLlama-style egress block). This is the manual/data-in-storage
  checklist item for the user's PC. The cache writer/reader was confirmed unchanged (ADR-2).
- Hyperliquid tickers remain unverified (RFC-2 must confirm, incl. `kPEPE`/`kBONK`/`kSHIB`).

## Test Gate Outcomes
| Gate | Result |
|---|---|
| `uv run --project api pytest api/ -q` | **307 passed, 2 deselected** (was 294; +13 new) |
| `pnpm --filter web test` | **75 passed, 12 files, 0 failed** |
| RFC-1 targeted (`test_mapping.py` + contract) | 16 passed |
| `cd web && pnpm test:e2e` | not run (no web change in RFC-1) |

## Plan Deviations
- Within blast radius: the plan's Stage 2 said `map_coin_to_category` reads from the JSON; under the
  approved option B it stays on the frozen legacy map and a new `map_coin_to_narrative_category` reads
  the JSON. This is the user decision, not an agent deviation. The plan text needs amending (below).
- Added a golden fixtures dir `api/tests/routers/fixtures/` (new path, test-only).

## Test Infra Gaps Found
None. `cache.CACHE_ROOT` monkeypatching isolates the contract test.

## Closeout Packet
- Classification: **Keep in active/testing** (the program continues with RFC-2; the data-in-storage
  check runs on the user's PC).
- For UPDATE PROCESS to amend in plan/SPEC: ADR-7 (the JSON drives only /history and /narrative; legacy
  frozen; curated-per-seed sizing), AC-1 (strict, plus "incl. newly-mapped trending coins" and
  `/screener`), OQ-4 (resolved under B), the RFC-1 E1 gate/checklist (option 3), Component Details for
  `narrative_category_map.json`, and RFC-2 (verify HL tickers).
- Next: RFC-2 Stage 0 (Hyperliquid formula + ticker verification).

## Forward Preview
- Test Infra Found: golden-snapshot pattern at `api/tests/routers/fixtures/`; `load_category_map(path, seeds_path)` is injectable for tests.
- Blast Radius Changes: `/history` (RFC-3) must call `map_coin_to_narrative_category`, never `map_coin_to_category`; never edit `LEGACY_COIN_CATEGORY_MAP`.
- Commands to Stay Green: `uv run --project api pytest api/ -q`; `pnpm --filter web test`; `cd web && pnpm test:e2e`.
- Dependency Changes: none.

Follow-up stubs created: none. CONTEXT_PARTIAL: none.

TL;DR: user-editable curated map shipped under option B; /categories and /screener proven unchanged; 307 + 75 tests green.
