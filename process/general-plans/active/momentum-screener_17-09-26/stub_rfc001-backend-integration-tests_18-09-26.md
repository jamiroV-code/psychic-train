---
name: stub_rfc001-backend-integration-tests
feature: momentum-screener
phase: RFC-001 (follow-up)
date: 18-09-26
---

## Session Goal

Close the RFC-001 backend gap left by this cloud sandbox's total package-registry blockage (see `momentum-screener_PLAN_17-09-26.md` → `## Deviations`): run RFC-001's backend test suite against the REAL `fastapi`, `duckdb`, `pyarrow`, `ccxt`, and `pandas-ta-classic` packages, not the local sandbox-only shims. This is what promotes RFC-001 from "code-complete, partially verified" to "✅ VERIFIED".

## Status: RESOLVED (18-09-26) — backend half closed, frontend half still open on the sibling stub

## Implementation Checklist

- [x] In an environment with real network access to PyPI, run `uv sync` from `api/`.
- [x] Run the exact failing gate command: `uv run pytest api/` (full suite, all directories) — **43 passed**, user-confirmed on their own machine.
- [x] Two genuine bugs surfaced by this real run (not sandbox noise, exactly as anticipated): (1) `import pandas_ta` should have been `import pandas_ta_classic` — the real PyPI distribution's actual import name; (2) `compute_rsi`/`compute_sma`'s insufficient-history path relied on an assumption about `pandas-ta-classic`'s return shape that didn't hold (open upstream issue #145). Both fixed in `api/analytics/indicators/momentum.py` and `trend.py` — see `momentum-screener_PLAN_17-09-26.md` → `## Deviations` items 8–9 for full detail.
- [x] Previously-unexecuted router tests now pass for real: `api/tests/routers/test_watchlist.py` (was `importorskip`-skipped, now genuinely runs), `test_screener.py`, `test_relative_performance.py`.
- [x] `api/data/cache.py`'s real DuckDB-over-Parquet path — covered by the 43-passed full-suite run (no separate isolated confirmation needed; the router/integration tests exercise it).
- [x] Backend confirmed green — RFC-001's backend half is verified.

## Blast Radius

`api/` only — no `web/` files (see the sibling frontend stub). Every file already exists; this is verification, not new implementation, unless a real-dependency run surfaces an actual bug.

## Verification Evidence

Exact command that must go green: `uv run pytest api/` (run from repo root, or `python -m pytest api -q` per `api/pyproject.toml`'s `pythonpath = ["."]` config — note: must be invoked with `api` as the target from repo root, not `cd api && pytest`, or module resolution breaks — this tripped up the orchestrator's own first attempt at reproducing the 38/39 result this session).
