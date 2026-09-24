---
phase: rfc-001-stage0
date: 2026-09-24
status: BLOCKED
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
