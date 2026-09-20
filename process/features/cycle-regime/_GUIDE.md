# cycle-regime

<!-- Part of my_site -->

## Scope

Classifies the current market regime and cycle phase, and presents the macro backdrop that conditions every other signal in the app. Covers regime classification, cycle-phase estimation, macro series overlays, and the history of past regime transitions so a current read can be compared against precedent.

## Key Source Files

No source files exist yet — this repo contains no application code as of 2026-09-17.
Target locations once work begins:

- `api/analytics/regime/` -- classification and cycle estimation
- `api/routers/regime.py` -- regime HTTP surface
- `web/app/regime/` -- dashboard view

## Related Context

- `process/context/all-context.md` -- root router, stack decisions and open decisions
- `process/context/data-sources/all-data-sources.md` -- macro series sourcing is not yet solved

## Notes

Primary data candidate: the LiqTide open daily JSON (`https://liqtide.com/data/latest.json`),
which ships a net-liquidity series, a 0-100 composite regime score and its component breakdown,
free and keyless with attribution. Its methodology is published, so the composite can later be
reproduced from FRED, the NY Fed Markets API, DefiLlama, Stooq, Farside and CoinGecko if the
dependency needs removing or the weights need tuning. Cache every daily payload from the first
fetch — the provider is in beta and derived history is not recoverable after the fact. Details
in `process/context/data-sources/all-data-sources.md`.

Regime labels are inherently revised after the fact. The dashboard should distinguish the current provisional classification from settled historical labels, and should never silently restate history as if the label had always been known. `arch` (volatility) and `statsmodels` cover most of what this needs.

## Current Status

Status: not-started

## Folder Contents

```
process/features/cycle-regime/
  active/       -- in-progress plans for this feature (each task lives inside a {slug}_{date}/ task folder)
  completed/    -- archived completed plans
  backlog/      -- deferred/future plans
```

All artifacts (plans, specs, reports, references) colocate inside each `{slug}_{date}/` task folder. Do NOT create `reports/` or `references/` sibling dirs.
