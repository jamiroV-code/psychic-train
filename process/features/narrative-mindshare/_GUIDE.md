# narrative-mindshare

<!-- Part of my_site -->

## Scope

Tracks attention and narrative strength across sectors and assets, so that a price or statistical signal can be read against how crowded or ignored its story is. Covers attention time series, relative mindshare between sectors, and change-in-attention measures.

## Key Source Files

No source files exist yet — this repo contains no application code as of 2026-09-17.
Target locations once work begins:

- `api/analytics/narrative/` -- scoring and normalisation
- `api/routers/narrative.py` -- narrative HTTP surface
- `web/app/narrative/` -- dashboard view

## Related Context

- `process/context/all-context.md` -- root router, stack decisions and open decisions
- `process/context/data-sources/all-data-sources.md` -- the data-availability problem for this feature is documented there

## Notes

Scoped 2026-09-17 to **free proxies only, explicitly labelled**: Google Trends via the unofficial
`pytrends`, the Reddit API free tier, CoinGecko trending endpoints, and exchange volume /
new-listing activity as an attention proxy. No paid vendor until the signal demonstrably changes a
sizing decision on this project's own history.

That constraint shapes the build. Narrative values render with a visible data-quality caveat and
carry less weight than price-derived signals in any combined read. A failed fetch degrades this
feature to "unavailable" rather than taking a dashboard down — `pytrends` in particular is
unofficial and breaks periodically. Normalise within a source and compare change over time; levels
are not comparable across these providers.

## Current Status

Status: not-started

## Folder Contents

```
process/features/narrative-mindshare/
  active/       -- in-progress plans for this feature (each task lives inside a {slug}_{date}/ task folder)
  completed/    -- archived completed plans
  backlog/      -- deferred/future plans
```

All artifacts (plans, specs, reports, references) colocate inside each `{slug}_{date}/` task folder. Do NOT create `reports/` or `references/` sibling dirs.
