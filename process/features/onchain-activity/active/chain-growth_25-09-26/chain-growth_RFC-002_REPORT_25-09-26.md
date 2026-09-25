---
phase: rfc-002
date: 2026-09-25
status: COMPLETE
feature: onchain-activity
plan: process/features/onchain-activity/active/chain-growth_25-09-26/chain-growth_PLAN_25-09-26.md
---

# chain-growth RFC-2 — Config + adapters (fallback: growthepie + L2BEAT, no Dune)

**TL;DR** — Built `chains.json` (9 chains), a skip+warn config loader, a growthepie adapter
(per-chain, bulk export, master.json support check) and an L2BEAT cross-check adapter. 33 new
tests pass; full suite **445 passed / 5 deselected** (was 412 / 3; +2 deselected = the new opt-in
integration tests). No existing file changed. Not committed.

## What Was Done

| File (new) | What it does |
|---|---|
| `api/data/chains.json` | 6 live chains (ethereum, base, arbitrum, optimism, polygon→`polygon_pos`, robinhood launch 2026-07-01 + `limited_history: true`); solana/bnb/tron with `source: "none"`, `unavailable_reason: "source-unavailable"`. L2BEAT cross-checks: base, arbitrum, optimism→`op-mainnet`, robinhood. `_comment` explains how to edit. |
| `api/data/chain_growth_config.py` | `load_chains(path=None) -> list[ChainConfig]`. Frozen dataclasses. Skips bad entries with a named warning (bad/duplicate id, missing label, bad date, unknown source, growthepie without `source_key`, secret-looking field, no valid metrics). Unknown metrics (e.g. `new_addresses`) ignored with warning. Bad `cross_check` dropped, chain kept. Missing/broken file → `[]`. Never raises. |
| `api/data/growthepie_adapter.py` | `fetch_chain_metric(chain_key, metric)` → `/v1/metrics/chains/{chain}/{daa|txcount}.json`; `fetch_chain_metrics(keys, metric)` per-chain isolated loop; `fetch_export(metric, keys)` → `/v1/export/{metric}.json` split by `origin_key`, missing chain → `chain-not-in-export`; `fetch_supported_chains(metric)` → `master.json` `metrics.{key}.supported_chains`. Unix seconds or ms both handled (>1e11 = ms), UTC dates. Null/NaN/negative values dropped, never zero-filled. `REDISTRIBUTABLE=True`, `ATTRIBUTION="Source: growthepie, https://www.growthepie.com."`. Never raises. |
| `api/data/l2beat_adapter.py` | `fetch_activity(project, range_="max")` → `?range=`; parses `chart.types` by column name; empty chart → `unavailable` / `empty-chart` (Optimism's `optimism` slug); invalid range rejected before any request. `REDISTRIBUTABLE=False`. Never raises. |
| `api/tests/data/test_{growthepie,l2beat}_adapter.py`, `test_chain_growth_config.py` + 5 fixtures | Recorded-shape fixtures matching the user-confirmed responses. |

## What Was Skipped or Deferred
- Dune adapter / SQL / tests / `DUNE_API_KEY`: not built (NOT-VIABLE verdict, locked fallback).
- `stale` status: in the type, not produced here — the cache layer (RFC-3) owns staleness.

## Test Gate Outcomes
- `uv run --project api pytest api/tests/data/test_growthepie_adapter.py api/tests/data/test_l2beat_adapter.py api/tests/data/test_chain_growth_config.py -q` → **33 passed, 2 deselected**.
- `uv run --project api pytest api/ -q` → **445 passed, 5 deselected** (baseline 412 / 3).
- Named scenarios: adapter-contract-shape, redistribution-flag-per-source, no-client-side-secrets
  (`test_no_secret_in_results`, config secret-field rejection), config-driven-chain-list,
  per-chain isolation (`test_per_chain_failure_isolation`: 3 chains in one run — one raises, one
  malformed, one ok; ok result equals a solo call → E7).
- Hybrid (not run here, egress blocked): `-m integration` tests, one per adapter.

**User-PC integration check (from repo root):**
```bash
uv run --project api pytest api/tests/data/test_growthepie_adapter.py api/tests/data/test_l2beat_adapter.py -m integration -q
```

## Plan Deviations
1. Metric names are `active_addresses` / `transactions` (per the execute handoff), not Stage 0's
   `daa` / `tx_count`. growthepie keys stay `daa` / `txcount` inside the adapter (`METRIC_KEYS`).
2. growthepie endpoint is the user-confirmed per-chain `/v1/metrics/chains/{chain}/{metric}.json`
   plus bulk `/v1/export/{metric}.json`, replacing Stage 0's unconfirmed `/v1/metrics/{metric}.json`
   (403). Signature changed accordingly (per-chain function + bulk function).
3. Isolation test (P7/E7) lives in `test_growthepie_adapter.py` (planned in Stage 0).
4. Added `limited_history` config field for Robinhood (requested in handoff).
All within blast radius (new files in `api/data/` and `api/tests/data/` only).

## Test Infra Gaps Found
- Real endpoints unreachable from this container; integration tests need the user's PC.

## Closeout Packet
- Plan: `process/features/onchain-activity/active/chain-growth_25-09-26/chain-growth_PLAN_25-09-26.md`
- Finished: RFC-2 fallback scope. Verified: fixture tests + full suite. Unverified: live endpoints (integration run).
- Remaining: UPDATE PROCESS plan amendments listed in the Stage 0 report §8, plus deviation 1–2 above.
- Classification: **Keep in active/testing** (program continues with RFC-3).
- Follow-up stubs: none created. CONTEXT_PARTIAL: none.
- Next: RFC-3 Stage 0 (storage + nightly archive + backfill) — not started.

## Forward Preview
### Test Infra Found
- `httpx.MockTransport` + JSON fixtures in `api/tests/data/fixtures/`.
### Blast Radius Changes
- 4 source files + 3 tests + 5 fixtures, all new. Nothing in narrative/regime/screener touched.
### Commands to Stay Green
- `uv run --project api pytest api/ -q` → 445 passed, 5 deselected.
### Dependency Changes
- None (httpx already a dependency).
