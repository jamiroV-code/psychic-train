# charting-indicators

<!-- Part of my_site -->

## Scope

Price charts with technical indicator overlays: the visual core of my_site and the surface every other feature renders into. Covers candlestick/line series, timeframe and symbol selection, moving averages, oscillators such as RSI, and custom indicators. Indicator values are computed in the Python API and rendered here — this feature owns presentation, not calculation.

## Key Source Files

No source files exist yet — this repo contains no application code as of 2026-09-17.
Target locations once work begins:

- `web/app/charts/` -- chart routes
- `web/islands/*.svelte` -- LayerChart chart islands (the charting surface since 01-10-26)
- `web/components/chart/` -- React chart wrappers (the lightweight-charts ones were removed 01-10-26)
- `api/routers/indicators.py` -- indicator HTTP surface
- `api/analytics/indicators/` -- indicator implementations

## Related Context

- `process/context/all-context.md` -- root router, stack decisions and open decisions
- `process/context/data-sources/all-data-sources.md` -- charting library choice and OHLCV providers

## Notes

**Charting stack changed 01-10-26 (Direction D).** `lightweight-charts` was removed; charts are now
`layerchart` rendered as Svelte 5 islands, built by `pnpm build:islands` into `web/public/islands/`.
See `process/context/all-context.md` §Technology Stack and ADR-1 in
`process/general-plans/active/ui-shell_28-09-26/ui-shell_DIRECTION-D_28-09-26.md`. Islands are for
charts only — do not widen that boundary to ordinary UI. The most likely source of quiet bugs here is a mismatch between the timeframe requested and the timeframe the indicator was computed on — make the API response carry the timeframe it actually used rather than assuming it matches the request.

## Current Status

Status: not-started

## Folder Contents

```
process/features/charting-indicators/
  active/       -- in-progress plans for this feature (each task lives inside a {slug}_{date}/ task folder)
  completed/    -- archived completed plans
  backlog/      -- deferred/future plans
```

All artifacts (plans, specs, reports, references) colocate inside each `{slug}_{date}/` task folder. Do NOT create `reports/` or `references/` sibling dirs.
