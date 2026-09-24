# cycle-regime

<!-- Part of my_site -->

## Scope

Classifies the current market regime and cycle phase, and presents the macro backdrop that conditions every other signal in the app. Covers regime classification, cycle-phase estimation, macro series overlays, and the history of past regime transitions so a current read can be compared against precedent.

## Key Source Files

Shipped 2026-09-24 (`regime-dashboard_24-09-26` — see Current Status):

- `api/analytics/regime/components.py`, `api/analytics/regime/components_response.py` -- the six
  liquidity-impulse components (net liquidity, stablecoin supply, broad dollar, ON-RRP, spot-ETF
  flows, BTC dominance) plus a reproduced tide-index composite and a passthrough of LiqTide's own
  published index for comparison. This is a **separate maths path** from `liquidity_composite.py` /
  `leg_boundary.py` (which still feed the momentum screener's leg-boundary detection) — the two are
  intentionally not merged.
- `api/data/etf_flows_adapter.py` -- Farside spot-BTC-ETF flows adapter (personal-use only)
- `api/routers/regime.py` -- `GET /api/regime/components` (new) + `GET /api/regime/legs` (existing,
  unchanged)
- `api/models/regime.py` -- pydantic response models for both endpoints
- `web/app/regime/page.tsx` -- the `/regime` dashboard route
- `web/components/regime/{RegimeDashboard,ComponentPanel,Readout,DrillDown}.tsx` -- seven synced
  `lightweight-charts` panels, hover readout, per-panel drill-down
- `web/lib/api/regime.ts`, `web/lib/types/regime.ts`, `web/lib/format-regime-value.ts`,
  `web/lib/regime-chart-sync.ts`, `web/lib/regime-line-segments.ts`

## Related Context

- `process/context/all-context.md` -- root router, stack decisions, open decisions and questions
  (see the AC-11 walkthrough gap, the BTC-dominance/ETF depth limits, and the two distinct
  full-vs-reduced composite comparison questions)
- `process/context/data-sources/all-data-sources.md` -- LiqTide methodology, the Farside adapter,
  and the per-series `max_gap_days` cadence pointer
- `process/context/tests/all-tests.md` -- current green counts and the cloud-container Playwright
  notes relevant to this feature's E2E spec

## Notes

Primary data candidate: the LiqTide open daily JSON (`https://liqtide.com/data/latest.json`),
which ships a net-liquidity series, a 0-100 composite regime score and its component breakdown,
free and keyless with attribution. Its own history is too short (~2024-09 at best) for the 3+ year
default view this dashboard needs, so the six components are **reproduced independently** from FRED,
DefiLlama and Farside primaries (see `components.py`), and LiqTide's published index is shown as a
second, clearly labelled line for comparison rather than as the only source. A real-data check
found 5/6 components exact and Pearson r = 0.964 against LiqTide's published composite.

Regime labels are inherently revised after the fact. LiqTide's own `regime_label` is shown only on
LiqTide's own published line, marked as LiqTide's — this project invents no regime labels of its
own on this dashboard. `arch` (volatility) and `statsmodels` remain unused so far; this dashboard
needed no new statistical library beyond what regime-dashboard's own transforms use.

Every gap is typed and shown honestly, never filled: `not_applicable` (before a series could
possibly exist, e.g. ETF flows before 2024-01-11), `no_data` (before a series' actual first point,
e.g. BTC dominance), `unavailable` (a live fetch/adapter failure), `stale` (serving a cached value
past its TTL). Nothing is drawn on the charts beyond the series themselves — no markers, bands, or
invented overlays (north-star rule, unchanged from the rest of the app).

## Current Status

Status: **code-complete, one open item.** All six RFCs (`RFC-001`..`RFC-006`) are implemented and
committed to `main`. Every automated test gate is green (pytest, vitest, tsc, `next build`,
Playwright — see `all-tests.md`). The one remaining item is **AC-11**, the real-cache user
walkthrough, which cannot run in this environment (egress to FRED/DefiLlama is blocked) and must
be completed on the user's own PC before the plan is archived. See the plan's own "Resume and
Execution Handoff" section for the exact next steps:
`process/features/cycle-regime/active/regime-dashboard_24-09-26/regime-dashboard_PLAN_24-09-26.md`.

A LiqTide raw-JSON archive now runs nightly via `.github/workflows/liqtide-snapshot.yml` (23:30
UTC, commits to `main`) — no manual scheduling step is needed.

## Folder Contents

```
process/features/cycle-regime/
  active/       -- in-progress plans for this feature (each task lives inside a {slug}_{date}/ task folder)
    regime-dashboard_24-09-26/  -- the shipped dashboard's plan, RFC phase reports, feasibility doc
  completed/    -- archived completed plans
  backlog/      -- deferred/future plans (e.g. FRED ALFRED point-in-time vintages)
```

All artifacts (plans, specs, reports, references) colocate inside each `{slug}_{date}/` task folder. Do NOT create `reports/` or `references/` sibling dirs.
