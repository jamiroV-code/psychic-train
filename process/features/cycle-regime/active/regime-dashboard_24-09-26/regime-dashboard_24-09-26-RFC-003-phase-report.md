---
phase: rfc-003-etf-flows-adapter
date: 2026-09-24
status: COMPLETE
feature: cycle-regime
plan: process/features/cycle-regime/active/regime-dashboard_24-09-26/regime-dashboard_PLAN_24-09-26.md
---

# RFC-003 Phase Report — Spot-BTC ETF flows adapter (Farside)

**Date**: 24-09-26
**Status**: 🔨 CODE DONE — live data cached and verified; not ✅ VERIFIED until the user confirms
**Stage 0**: `regime-dashboard-farside_FEASIBILITY_24-09-26.md` — VIABLE (binding constraints applied)

**TL;DR**: Farside's daily ETF totals are now cached from 2024-01-11 to 2026-09-23 (677 trading days) and feed the ETF component, which grew from 8 points to 673. All gates green: 256 passed.

## What Was Done

| File | Change |
|---|---|
| `api/data/etf_flows_adapter.py` | new — `fetch_btc_spot_flows(client=None, force=False) -> EtfFlowsResult(df, status, reason, redistributable=False, source)`. httpx GET with a browser User-Agent, 3 tries with backoff on timeout, network error, 429 and 5xx. A 403/503 or a Cloudflare challenge page returns `unavailable` straight away, with no retry and no bypass attempt. Parser uses stdlib `html.parser` and reads the `Total` column of `<table class="etf">` only. Results are cache-first: at most one request per UTC day (tracked by a `.last_attempt` marker; a failed attempt counts). Each fetch is overwrite-merged into `cache/etf_flows/btc_spot.parquet` (`date, net_flow_usd_m`). Never raises |
| `api/analytics/regime/components.py` | `build_etf_flows(history, farside=None)`: Farside US$m × 1e6 is the primary daily record, and the LiqTide archive only fills dates Farside lacks. Farside `stale` is passed through. When Farside is unavailable the builder falls back to the LiqTide archive and adds a note saying so. The spec's `source` text is updated. The orchestrator passes `etf_flows_adapter.fetch_btc_spot_flows()`. Maths unchanged: 5-day sum, tanh(Σ / $1bn) |
| `api/tests/data/test_etf_flows_adapter.py` | new — 16 tests + 1 opt-in `integration` live test |
| `api/tests/data/fixtures/farside_btc_etf_flows.html` | new fixture — parentheses, commas in daily cells, `-`, real `0.0`, unreported all-`-` row, malformed rows, `Total`/`Average` footer, a decoy `nav` table |
| `api/tests/analytics/test_components.py` | orchestrator test now stubs the Farside adapter (no network); +6 wiring tests |
| `api/data/cache/etf_flows/btc_spot.parquet` | new data (untracked — `.gitignore` only tracks `cache/liqtide/`) |

No dependency added; `pyproject.toml` and `uv.lock` untouched (user decision: stdlib `html.parser`).

## Plan Deviations

- **Unreported-row rule (from Stage 0 evidence, not stated in the plan):** Farside shows `0.0` in `Total` for today's row before the close, even though every fund cell is `-`. A row is only kept when at least one fund cell is numeric. Without this rule a fake zero-flow day would be written. Tested.
- **At-most-once-a-day marker:** the plan says "cache-first with TTL". This is implemented as a per-UTC-day attempt marker, so a failed fetch is not retried on every page load. `force=True` overrides it (used for the manual live run).
- **LiqTide archive kept as a fallback source for ETF flows:** the plan says "ETF component reads the RFC-003 adapter if present". Farside is used first. The existing LiqTide archive data (the RFC-002 behaviour) is kept only for dates Farside lacks, so the component does not lose data when Farside is blocked.
- **Stage 0's "add a parser dependency" constraint:** met by the stdlib `html.parser` option that constraint allows, per the user's decision.

## Test Gate Outcomes

1. `uv run --project api pytest api/tests/data/test_etf_flows_adapter.py -q` → **16 passed, 1 deselected**
2. `uv run --project api pytest api/ -q` → **256 passed, 2 deselected** (baseline 234 passed, 1 deselected; +16 adapter, +6 component; the new deselected test is the opt-in live one)
3. Live run (one request, `force=True`, real cache) → `ok None False 677`; verification query:
   ```
   [(datetime.datetime(2024, 1, 11, 0, 0), datetime.datetime(2026, 9, 23, 0, 0), 677)]
   ```
   min date 2024-01-11 as expected. Calendar check: the only weekdays missing between 2024-01-11 and 2026-09-24 are 28 US market holidays (including 2025-01-09, the national day of mourning) and today, which is not yet reported. There are no weekend rows and no zero values. This settles Stage 0's open "contiguous dates" gap: the 694 date rows seen in the probe minus 677 kept = 17 rows dropped (holidays listed with `-`, plus today).
4. Error handling → **both paths demonstrated:**
   - Tests: `test_timeout_unavailable_when_nothing_cached`, `test_challenge_page_is_unavailable_without_retry`, `test_layout_change_is_unavailable` (all `unavailable`); `test_timeout_falls_back_to_cache_as_stale` (`stale`, and no retry later the same day).
   - Real bad-URL run against a throwaway cache (`SCREENER_CACHE_ROOT` = scratchpad, `https://farside.invalid/...`) → `unavailable | network error: ConnectError | False 0`. The live `.last_attempt` marker was untouched (`2026-09-24|ok`).
- Integration test selection: `pytest api/ -m integration -k etf --collect-only` → `1/258 tests collected` (`test_etf_live_farside_single_request`). It was **not run live** in this session, because the gate allowed a single request and that request was used to populate the real cache.

**Real-data ETF component:** `ok`, 2024-01-18 → 2026-09-23, 673 points (was 8 from the LiqTide archive). For 2026-09-23 Farside's total is 346.9m, but the 2026-09-24 00:53 UTC LiqTide payload had 32.4m. LiqTide captured a partial day. Our contribution is 0.9901, against 0.9816 published by LiqTide from its partial figure.

## What Was Skipped or Deferred

- Live integration test run (see above). User step: `uv run --project api pytest api/ -m integration -k etf`.
- The user-confirmation checkbox is left unticked.
- RFC-004/005 surfaces (routers, `web/`) were not touched.

## Test Infra Gaps Found

None. Known gap (from Stage 0): Farside behaviour from a different network or IP is unverified.

## Closeout Packet

- Selected plan: `process/features/cycle-regime/active/regime-dashboard_24-09-26/regime-dashboard_PLAN_24-09-26.md`
- Verified: gates 1–4 above. Unverified: the user's own confirmation, and the opt-in live integration test.
- Classification: **Keep in active/testing** (RFC-004…006 remain; user confirmation pending).
- Follow-up plan stubs created: none. CONTEXT_PARTIAL: none.
- Next: user confirms RFC-003 → RFC-004 (`GET /api/regime/components`).

## Forward Preview

- **Test Infra Found:** `httpx.MockTransport` + `isolated_cache` is enough for adapter tests. Also patch `etf.time.sleep` to skip backoff waits.
- **Blast Radius Changes:** `build_regime_components()` now calls `etf_flows_adapter.fetch_btc_spot_flows()`, which is cache-first and makes at most one request a day. RFC-004 endpoint tests must monkeypatch it, as `test_components.py` does, to stay offline.
- **Commands to Stay Green:** `uv run --project api pytest api/ -q` (256 passed, 2 deselected).
- **Dependency Changes:** none.
