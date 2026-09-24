# narrative-mindshare

<!-- Part of my_site -->

## Scope

Tracks attention and narrative strength across sectors and assets, so that a price or statistical signal can be read against how crowded or ignored its story is. Covers attention time series, relative mindshare between sectors, and change-in-attention measures.

## Key Source Files

Real, shipped code as of 2026-09-24 (narrative-dashboard RFC-1..6, code-complete, EVL-confirmed,
committed to branch `claude/kind-tesla-tat3vo` @ `7ef8eb3`):

- `api/analytics/narrative/{scoring,trigger,mapping}.py` — the original RFC-003 backend (unchanged
  behavior); `history.py` and `exchange_attention.py` (new) — composite/comparison/change maths and
  the display-only exchange proxy
- `api/routers/narrative.py` — `get_categories` (unchanged) + new `get_history`
  (`GET /api/narrative/history`)
- `api/models/narrative.py` — `NarrativeCategory` (unchanged) + new additive history models
- `api/data/{pytrends,reddit,coingecko}_adapter.py` (unchanged) + `hyperliquid_narrative_adapter.py`
  (new, 9th adapter in the repo, keyless ccxt Hyperliquid perps)
- `api/data/narrative_category_map.json` — new, user-editable curated map (see Notes below);
  `api/analytics/narrative/mapping.py::LEGACY_COIN_CATEGORY_MAP` stays frozen and drives
  `/categories`/`/screener`
- `api/scripts/{snapshot_narrative.py,backfill_pytrends_history.py}` — nightly forward-archive +
  one-off pytrends backfill; `.github/workflows/narrative-snapshot.yml` — the second scheduled
  workflow in this repo (after `liqtide-snapshot.yml`)
- `web/app/narrative/page.tsx`, `web/components/narrative/*` — the standalone dashboard
- `web/components/screener/NarrativeStrip.tsx` — unchanged, proven byte-compatible

## Related Context

- `process/context/all-context.md` -- root router, stack decisions and open decisions
- `process/context/data-sources/all-data-sources.md` -- the data-availability problem for this feature is documented there

## Notes

**How to edit the narrative map (added 2026-09-24, narrative-dashboard RFC-1):**
- Edit `api/data/narrative_category_map.json` → `"map"`. Keys are UPPERCASE tickers; values are a
  seed category id from `api/data/narrative_categories.json` (`ai`, `rwa`, `l2s`, `memecoins`).
- No code change or restart: the API re-reads the file when its modification time changes.
- Bad entries (lowercase symbol, unknown category) are skipped with a logged warning; the rest load.
- This map drives only `/api/narrative/history` and `/narrative` (coins not in the legacy map show as
  "narrative-only"). `/api/narrative/categories` and `/screener` stay on the frozen legacy
  BTC/ETH/HYPE map in `api/analytics/narrative/mapping.py` (option B) — do not edit that to widen coverage.

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

Status: **code-complete, pending user verification** (24-09-26). All 6 RFCs of the
`/narrative` dashboard shipped, EVL-confirmed, committed and pushed
(`process/features/narrative-mindshare/active/narrative-dashboard_24-09-26/`). Outstanding before
archival: AC-3 (nightly cron actually firing) and AC-12 (real-cache walkthrough) both require the
user's own machine (this sandbox's egress proxy blocks all four providers); two manual-first
risk-pack review decisions are `PENDING`. See the plan's Resume and Execution Handoff for the exact
checklist. The plan stays in `active/` until those land.

## Folder Contents

```
process/features/narrative-mindshare/
  active/       -- in-progress plans for this feature (each task lives inside a {slug}_{date}/ task folder)
  completed/    -- archived completed plans
  backlog/      -- deferred/future plans
```

All artifacts (plans, specs, reports, references) colocate inside each `{slug}_{date}/` task folder. Do NOT create `reports/` or `references/` sibling dirs.
