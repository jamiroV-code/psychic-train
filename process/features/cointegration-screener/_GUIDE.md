# cointegration-screener

<!-- Part of my_site -->

## Scope

Scans candidate pairs for a cointegrating relationship and ranks them for tradability. Covers pair universe selection, Engle-Granger and Johansen testing, spread construction, half-life of mean reversion, and current z-score of the spread. This is the most statistically demanding area of the app and the one most sensitive to data quality.

## Key Source Files

No source files exist yet — this repo contains no application code as of 2026-09-17.
Target locations once work begins:

- `api/analytics/cointegration/` -- tests, spread construction, half-life
- `api/routers/screener.py` -- screener HTTP surface
- `web/app/screener/` -- results table, pair detail view

## Related Context

- `process/context/all-context.md` -- root router, stack decisions and open decisions
- `process/context/data-sources/all-data-sources.md` -- history depth is the binding constraint for this feature

## Notes

Data note: crypto history is free and deep via ccxt. Equity history is the constraint — most
free tiers cap it well short of what a credible test needs. London Strategic Edge is the leading
free candidate but is unverified and its data is personal-use only, so anything built on it
cannot be served to other users if the app opens up. See the data-sources group before choosing.

Two hazards deserve explicit guarding. First, multiple-testing: screening hundreds of pairs produces cointegrated-looking results by chance, so the ranking must account for how many pairs were tested rather than reporting raw p-values. Second, sample length: free equity tiers that cap history at one year are not enough for a credible test — check the available history before trusting a verdict, and surface the sample length alongside every result.

## Current Status

Status: not-started

## Folder Contents

```
process/features/cointegration-screener/
  active/       -- in-progress plans for this feature (each task lives inside a {slug}_{date}/ task folder)
  completed/    -- archived completed plans
  backlog/      -- deferred/future plans
```

All artifacts (plans, specs, reports, references) colocate inside each `{slug}_{date}/` task folder. Do NOT create `reports/` or `references/` sibling dirs.
