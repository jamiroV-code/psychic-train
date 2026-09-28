---
name: pair-screener-pvl-iteration-001
date: 2026-09-25
domain: plan
iteration: 1
loop_status: CONTINUE
---

# Pair Screener — PVL Iteration 001

**Result:** 2 gaps found, 2 applied, 0 backlogged. Re-validate from V1.

| Gap | Source | Fix applied |
|---|---|---|
| CONCERN-1 — deep fetch is a no-op for BTC/ETH/HYPE/SOL (existing shallow cache; `since=None` only tops up forward) | First-pass validate-contract | RFC-001 backfill now calls existing `ccxt_adapter.fetch_ohlcv(..., since=<early date>, limit=5000)`; cap-hit page-forward; per-coin bars/first-date log; AC-11 test seeds a 501-bar cache and asserts final depth; adapter stays read-only |
| CONCERN-2 — `/api/pairs/{a}/{b}` self-pair and case handling unspecified | First-pass validate-contract | Self-pair → 422; tickers normalised to uppercase; unknown → 404; router tests added |

**Feasibility probe:** `pair-screener_FEASIBILITY_25-09-26.md` — VIABLE (offline ccxt 4.5.78 source read, no network). Known-gaps carried: server-side truncation for old `startTime`, real listing dates, bulk rate-limit behaviour.

TL;DR: both concerns fixed in the plan; next is a fresh validate pass.
