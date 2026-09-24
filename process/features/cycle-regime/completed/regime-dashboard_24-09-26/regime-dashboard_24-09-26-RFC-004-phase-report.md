---
phase: rfc-004-regime-components-endpoint
date: 2026-09-24
status: COMPLETE_WITH_GAPS
feature: cycle-regime
plan: process/features/cycle-regime/completed/regime-dashboard_24-09-26/regime-dashboard_PLAN_24-09-26.md
---

# RFC-004 Phase Report — `GET /api/regime/components`

**Date**: 24-09-26
**Plan**: `regime-dashboard_PLAN_24-09-26.md` (§11, §15 RFC-004, Stage 0 decisions 1–6)
**Status**: 🔨 CODE DONE — endpoint tests green; not ✅ VERIFIED until the user confirms on the PC.
> **Post-merge note (24-09-26):** RFC-003 has since landed on main and was merged in. The ETF component now reads Farside first with the LiqTide archive filling gaps; with no data its reason is "no ETF flow history: Farside {status} ({reason})", no longer "RFC-003, not built".
RFC-003 is **not started** (user chose RFC-004 first) — not skipped.

## What Was Done

| File | Change |
|---|---|
| `api/analytics/regime/components.py` | additive: `ComponentSpec.applicable_from` (ETF = 2024-01-11), `status_for_range()` (the `not_applicable` rule, documented in its docstring), ETF reason now says "RFC-003, not built" |
| `api/analytics/regime/components_response.py` | new: `RegimeComponentsResult` → §11 response. Range filter, finite-only points, `last_fetched_utc` from cache file mtimes, published `label`→`regime_label`, fixed label/attribution/normalisation strings |
| `api/models/regime.py` | additive pydantic models (`ComponentPoint`, `RegimeComponent`, `ReproducedComposite`, `PublishedComposite`, `CompositeAgreement`, `RegimeComposite`, `RegimeComponentsResponse`); `ComponentStatus` Literal includes `not_applicable` |
| `api/routers/regime.py` | additive `GET /components?start&end` (ISO dates; a malformed date or start > end → 422). `/legs` untouched |
| `api/main.py` | `GZipMiddleware(minimum_size=1000)` |
| `api/tests/routers/test_regime_components.py` | new, 20 tests via real `TestClient` |
| plan | Status Strip, §11 example + status rules, RFC-004 decisions, handoff note |

## What's Functional Now

- `GET /api/regime/components` returns all six components, the reproduced and published composites, and agreement stats.
- One failed source only affects its own component. Live proof below: 4 sources were blocked and the endpoint still returned 200.
- The endpoint never calls `liqtide_adapter.fetch_latest`. A test fails if it does.
- Responses are about 3.7× smaller with gzip (25.6 KB → 7.0 KB in the live run).

## Test Gate Outcomes

- `uv run --project api pytest api/tests/routers/test_regime_components.py -q` → **20 passed**.
- `uv run --project api pytest api/ -q` → **252 passed, 2 failed, 1 deselected**. Both failures were already there before RFC-004 on this same checkout (baseline: 232 passed, 2 failed).
  - The failing tests are `test_board_integration.py::test_board_returns_populated_chart_series` and `::test_relative_performance_populated`.
  - They need a populated screener OHLCV cache, which this container lacks (`coins == []`). They are unrelated to RFC-004.
  - The RFC-002 report's "234 passed" was measured on a machine that has that cache.
- Live uvicorn run (container, 127.0.0.1:8000):
  - cold 1.80 s, warm 1.85 s, gzip 1.88 s. The cold time is under 10 s, so no backlog note was added.
  - Warm misses the < 1 s target only because FRED/DefiLlama are blocked by the proxy and there is no liquidity cache, so every request re-tries them. This needs re-measuring on the PC.
  - ETF: `ok`, 8 points, 2026-09-14 → 2026-09-23. Matches the RFC-002 table (8).
  - BTC dominance: `ok`, 117 points, 2025-07-12 → 2026-09-24. Matches (117).
  - net_liquidity / stablecoin / broad_dollar / rrp: `unavailable` (no cache and no network here). The 683 / 3214 / 5171 / 3258 counts could not be checked here.
  - Published: `ok`, 108 points. Reproduced: 0 points, because coverage was under 60% with only 2 components. Agreement is all null or 0, which is honest.

## What You Can Test (on your PC)

```bash
uv run --project api pytest api/tests/routers/test_regime_components.py -q
uv run --project api pytest api/ -q
uv run --project api uvicorn api.main:app --host 127.0.0.1 --port 8000
# second terminal — run twice (cold, then warm):
curl -s -o /dev/null -w "%{time_total}s %{size_download}B\n" http://127.0.0.1:8000/api/regime/components
curl -s http://127.0.0.1:8000/api/regime/components | python -c "import json,sys;b=json.load(sys.stdin);[print(c['id'],c['status'],len(c['points']),c['first_date']) for c in b['components']];print(b['composite']['agreement'])"
curl -s "http://127.0.0.1:8000/api/regime/components?end=2023-12-31" | python -m json.tool | findstr not_applicable
curl -s -o /dev/null -w "%{http_code}\n" "http://127.0.0.1:8000/api/regime/components?start=2026-09-10&end=2026-09-01"   # expect 422
```

Expect point counts 683 / 3214 / 5171 / 3258 / 8 / 117 (RFC-002 table). Expect a warm response in under 1 s. If the cold response takes more than 10 s, append it to `process/general-plans/backlog/board-endpoint-cold-start-latency_20-09-26.md`.

## Plan Deviations

1. **Extra `no_data` case.** A component whose data exists but has no points inside the requested window reports `no_data` ("no points in the requested date range") instead of `ok` with an empty list. This follows from §11's "reason explains the gap". It stays within the blast radius.
2. **`published.status` uses the requested window.** It is `ok` when the window contains published points, else `unavailable`. With no range given, this is the same as decision 4.
3. **`agreement` is not filtered by `start`/`end`.** It is whole-history stats. This is documented in §11.
4. **Fields added to each component beyond the §11 example:** `unit` and `notes`. They are already in the builders and the drill-down needs them. §11's example now shows them.
5. **Tests use real `TestClient`, not the `test_regime.py` bypass.** fastapi became importable after `uv sync` from the existing lockfile. No new dependencies were added.

## What Was Skipped or Deferred

- Live counts for the four FRED/DefiLlama components: needs the PC (the proxy blocks both hosts here).
- The warm < 1 s timing target: unverified until those four components have a cache.

## Test Infra Gaps Found

- `test_board_integration.py` fails whenever the screener cache is absent. It should be `integration`-marked or seeded. Classification: harness-drift. Not fixed (out of scope).

## Closeout Packet

- Classification: **Keep in active/testing** (user PC verification pending).
- Follow-up stubs: none created.
- CONTEXT_PARTIAL: none.

## Forward Preview

- **Test Infra Found**: fastapi `TestClient` works after `uv sync` in the container; `isolated_cache` plus `cache.write_liqtide_payload` seeds the published series.
- **Blast Radius Changes**: new module `components_response.py`; `api/main.py` now has gzip.
- **Commands to Stay Green**: the two pytest commands above.
- **Dependency Changes**: none (the uv virtualenv was populated from the existing lockfile; it is gitignored).

## Ready For RFC-005

The contract is stable for the `/regime` page. RFC-005 needs these facts:
- Component `status` ∈ ok | stale | unavailable | not_applicable | no_data.
- Points are never null.
- Published points use `regime_label`.
- `last_fetched_utc` is present for the as-of display.
