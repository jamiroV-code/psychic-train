---
name: report:narrative-dashboard-rfc-003-stage0
description: "RFC-3 Stage 0 — /api/narrative/history response model, composite/rank/change maths, redistributable handling, files/tests, E3 harness list; presented, STOPPED for user decisions"
date: 24-09-26
metadata:
  node_type: memory
  type: report
  feature: narrative-mindshare
  phase: RFC-3-stage0
phase: rfc-003-stage0
status: BLOCKED
feature: narrative-mindshare
plan: process/features/narrative-mindshare/active/narrative-dashboard_24-09-26/narrative-dashboard_PLAN_24-09-26.md
---

# RFC-3 Stage 0 — `GET /api/narrative/history` + composite / rank / change maths

**BLUF:** RFC-3 can be built as planned: one read-only endpoint over the existing cache, reusing the
`/regime` grid/gap shape. Three user decisions are needed before Stage 1 (D1–D3 below). Everything
else is a technical call made here. Status `BLOCKED` = waiting for approval, not a defect.

Two code findings matter more than the rest:

1. **The archived CoinGecko count is legacy-map based.** `trigger.py` counts trending coins with
   `map_coin_to_category` (frozen map: BTC, ETH, HYPE). So `coingecko/ai`, `rwa` and `memecoins` can only
   ever hold `0`, and `normalize_within_source` turns an all-zero series into a flat `0.5`. Fed into a
   composite, that is a quietly wrong number. **Decision D1.**
2. **`/categories` never sees pytrends or reddit history (existing bug, not RFC-3's to fix).**
   `trigger.compute_narrative_categories` reads `read_narrative_series(source, category_id)`, but the
   pytrends and reddit writers store under the keyword (`pytrends/AI crypto.parquet`). The reads always
   come back empty. Fixing it would change `/categories` output and break AC-1, so the proposal is a backlog
   note only. `/history` reads by keyword and is not affected.

## 1. Proposed response model (pydantic, additive to `api/models/narrative.py`)

**Query:** `GET /api/narrative/history?categories=ai,l2s&start=YYYY-MM-DD&end=YYYY-MM-DD`
- `categories`: comma-separated seed ids. Optional; the default is all seeds. An unknown id → **422**
  naming it. Unknown ids are never silently dropped.
- `start`/`end`: `date | None` via FastAPI `Query`. Malformed → 422 (FastAPI). `start > end` → 422
  (same as `routers/regime.py::get_components`).
- There is no window parameter. The change window is fixed at 7 days (ADR-5), and a view window is just
  `start`/`end`.

```text
NarrativeHistoryResponse
  generated_utc: str                      # ISO UTC
  grid_dates: list[str]                   # union of all returned series + composite dates, in range
  categories: list[NarrativeHistoryCategory]
  comparison: NarrativeComparison
  change_in_attention: NarrativeChange

NarrativeHistoryCategory
  category_id, label, keywords: list[str]
  coins: list[NarrativeCoin]              # {symbol, narrative_only: bool}; from load_category_map()
  series: list[NarrativeHistorySeries]
  composite: NarrativeComposite

NarrativeHistorySeries
  source: "pytrends" | "reddit" | "coingecko" | "exchange_volume_share" | "exchange_new_listings"
  variant: "nightly-7d" | "backfill-269d" | None   # pytrends only; one series per variant
  cache_key: str                          # "AI crypto" for pytrends/reddit, "ai" otherwise
  redistributable: bool
  status: "ok" | "stale" | "unavailable" | "presumed-dead"
  reason: str | None                      # "no-archived-data", "last-point-9-days-old", ...
  first_date, last_date: str | None
  max_gap_days: int
  in_composite: bool                      # tells the UI which series feed the composite
  points: list[NarrativeHistoryPoint]

NarrativeHistoryPoint
  date: str
  raw_value: float | None                 # new_listing_count may be null on a real row (E2)
  normalized_value: float | None          # null only when raw_value is null
  point_status: str                       # stored source_status / volume_status / listing_status
  reason: str | None                      # stored *_reason (exchange), else None
  gap_before: bool

NarrativeComposite
  status: "ok" | "unavailable";  reason: str | None
  max_gap_days: int
  points: list[{date, value, coverage: float, sources_present: list[str],
                trust_weight: float, mixed_scale: bool, gap_before: bool}]

NarrativeComparison
  as_of: str | None
  entries: list[{category_id, rank: int | None, value: float | None,
                 status: "ok" | "unavailable", reason: str | None}]

NarrativeChange
  window_days: 7;  as_of: str | None
  entries: list[{category_id, delta: float | None, rank: int | None, baseline_date: str | None,
                 mixed_scale: bool, status, reason}]
```

These classes cover the plan's four named models (`NarrativeHistorySeries`, `NarrativeHistoryPoint`,
`NarrativeComparisonEntry`, `NarrativeChangeEntry`) plus their containers. The response is category-first
rather than the flat `series[]` in plan §11, because the UI draws one panel per category. That is a
plan-text change (see Conflicts).

**pytrends nightly vs backfill:** each is a separate series (`variant`), normalised only against itself.
Nothing is spliced into one line. The backfill never writes a date that already has a nightly point,
so the two variants never share a date. The composite uses whichever variant exists on a date and sets
`mixed_scale` on points built from `backfill-269d`. How the composite treats backfilled points is
**Decision D2**.

## 2. Numerics

| Item | Rule | Source |
|---|---|---|
| Series keys | pytrends/reddit: `seed.keywords[0]` (what `trigger.py` and the backfill pass). coingecko: `category_id`. exchange: `read_exchange_series(category_id)` | trigger.py, RFC-2 report item 6 |
| Normalisation | `scoring.normalize_within_source` over the **full stored history of that series/variant**, then `start`/`end` filtering, so values do not move when the view window changes. A known property: a new all-time extreme rescales past values. The caveat text states this | scoring.py |
| Null raw values | Dropped before normalisation, never 0-filled. The row still appears with `raw_value: null` + reason | "never silently wrong" |
| Composite | Per date: skipna mean of `normalized_value` over the in-composite sources present | trigger.py pattern, ADR-5 |
| Min coverage | A composite point only exists when **≥ `MIN_AVAILABLE_SOURCES` (2)** sources have a value that date. Otherwise there is no point: absent, never NaN or 0. `coverage` = present ÷ in-composite sources | trigger.py `MIN_AVAILABLE_SOURCES` |
| trust_weight | `BASE_TRUST_WEIGHT` 0.6, capped to `REDUCED_SOURCE_TRUST_CAP` 0.4 when pytrends is absent that date. The same rule as trigger 47a, applied per point. No confirmation step | trigger.py constants |
| gap_before | `gap > NARRATIVE_MAX_GAP_DAYS = 2` calendar days (new constant: one missed nightly run is tolerated, two are flagged). Computed on the full series before filtering | same rule as `regime.components.gap_before_flags`. Reimplemented, not imported (ADR-4: different package) |
| Series status (read-only) | Empty → `unavailable/no-archived-data`. Last point ≤1 day old → `ok`. 2–7 days → `stale`. pytrends >`PYTRENDS_DEAD_THRESHOLD_DAYS` (7) → `presumed-dead`. Exchange uses its stored row statuses | pytrends_adapter, reddit/coingecko staleness |
| Rank (comparison) | `as_of` = latest date with any composite point (inside `end`). Descending, rank 1 = most attention. Ties use competition ranking (`method="min"`: 1, 1, 3) on values rounded to 6 dp, listed by `category_id` for stable output. A category with no composite point on `as_of` gets `rank: null`, `unavailable`, `no-composite-on-as-of`. It is never ranked last | new, ADR-5 |
| Change | `delta = composite(as_of) − composite(baseline)`, where baseline = latest point in `[as_of−9d, as_of−7d]`. `CHANGE_WINDOW_DAYS = 7` (ADR-5) and new `CHANGE_BASELINE_TOLERANCE_DAYS = 2` (matching the gap tolerance). No baseline → `delta: null`, `no-baseline-in-window`. Ranked the same way as comparison. `mixed_scale` is true if the two ends use different pytrends variants | ADR-5 |
| Dates / tz | Cache dates are UTC calendar strings (writers use `datetime.now(timezone.utc)`). history.py treats them as tz-naive calendar dates and never converts local time | cache.py, adapters |

Nothing here calls an adapter or `compute_narrative_categories`. Those fetch live data and write the
cache. `/history` is a **pure read** of the archive: no network, no writes.

## 3. `redistributable=false` sources

Every series carries `redistributable`, and nothing is hidden (personal-use app). The values:
- exchange: `HYPERLIQUID_REDISTRIBUTABLE` (False, RFC-2 D4).
- pytrends, reddit, coingecko: nothing is recorded in `data-sources/all-data-sources.md`. **My technical
  call:** `False` for all three (unofficial Google scraper, Reddit API terms, CoinGecko free-tier
  attribution terms), each set once as a module constant in history.py so it is a one-line flip later.
- Top level: `redistributable_all: bool` (AND of the returned series) so a future public mode has one
  switch to check. UPDATE PROCESS should record the three values in the data-sources group.

## 4. Files and tests

**Create:** `api/analytics/narrative/history.py` (pure functions plus `build_narrative_history(category_ids, start, end)`),
`api/tests/analytics/test_history.py`, `api/tests/routers/test_narrative_history.py`,
`harness/{risk-gate,context-snippets,verification,review-decision,adversarial-validation}.json` in this task folder.
**Modify (additive only):** `api/models/narrative.py` (new classes appended), `api/routers/narrative.py`
(adds `get_history`; `get_categories` untouched). **Not touched:** trigger.py, mapping.py, scoring.py,
cache.py, screener_board.py, any adapter, web/.

`test_history.py` (analytics, all with `isolated_cache` + the real `write_narrative_point`/`write_exchange_point`):
- Real cache round-trip: pytrends written under the keyword key is read back for the right category (AC-2).
- Golden composite on 3 synthetic sources; skipna with one source missing; coverage and sources_present.
- Only 1 source on a date → no composite point (not 0, not NaN); 0 sources → none; all dates thin → `unavailable`.
- Within-source boundary: raw values on very different scales give the same composite as values pre-scaled per source (AC-10). No raw cross-source mean exists.
- Nightly vs backfill: two series, each normalised separately; `mixed_scale` set per D2.
- Normalisation is stable under `start`/`end` filtering.
- gap_before at exactly 2 days (False) and at 3 days (True); the flag survives filtering.
- Rank golden values: tie (1, 1, 3), stable order, missing-on-as_of → null rank.
- Change: exact 7-day baseline; 9-day fallback; 10-day → null + reason; ranked.
- Exchange: `new_listing_count` null row (no-baseline-yet) is carried with reason and not treated as 0.
- tz boundary: points written at 23:59:59 and 00:00:00 UTC land on different dates, and grid dates match.
- trust_weight 0.4 when pytrends is absent.
- Import guard: history.py does not import adapters, and trigger.py does not import history.py.

`test_narrative_history.py` (router, TestClient + `isolated_cache` + seeded cache):
- 200 shape; `grid_dates` = sorted union; every point date ∈ grid.
- `categories=ai` filter; unknown id → 422; `start>end` → 422; malformed date → 422.
- One source dir empty → 200, that series `unavailable`, others unchanged (AC-9).
- Empty cache → 200, every series `unavailable`, composite `unavailable`, no 500.
- gzip: `Accept-Encoding: gzip` on a >1 KB body → `content-encoding: gzip`.
- `redistributable` present on every series; `narrative_only` coins flagged.
- `/history` makes no network call (adapters monkeypatched to raise) and writes no cache files.
- Re-run the unmodified `test_narrative_categories_contract.py` (must stay 3/3) plus a grep check that `get_categories` shares nothing with `get_history` except `load_seed_categories`.

**Gates:** `uv run --project api pytest api/ -q` (baseline 336 passed / 3 deselected); `pnpm --filter web test` (75). Manual: the curl in the plan.

**E3 harness pack** (`harness/` in this task folder; risk class = public API contract):
- `risk-gate.json`: class, `mustStopBeforeFinalize: true`.
- `context-snippets.json`: `get_history` route, the model classes, the cache-read keying, the unchanged `get_categories`.
- `verification.json`: pytest runs, contract test, curl output, 422/empty-cache/one-source-down cases.
- `review-decision.json`: vc-code-reviewer APPROVE or REJECT with a rationale.
- `adversarial-validation.json`: path traversal via `categories`, prevented by allow-listing to seed ids, since cache paths are built from these strings; huge `start`/`end` ranges; the no-writes/no-network guarantee.

## 5. Plan-text conflicts (for UPDATE PROCESS)

1. §11 shows a flat `series[]` keyed by `category_id` with one composite list. The proposal is
   category-first, with composite, comparison and change entries carrying explicit `status`/`reason`.
2. §11 / §12b / RFC-1 verification assume `pytrends/{category}.parquet`. The real keying is the keyword
   (RFC-2 item 6), and reddit is the same.
3. §11 `status` enum lacks `variant` (nightly vs backfill), `in_composite` and `mixed_scale`.
4. ADR-4 lists per-source `trust_weight`. It is proposed per composite point instead (reusing trigger's constants).
5. ADR-5 "rank … recomputed per date requested" plus a single `as_of`. The proposal ranks only at `as_of`
   (the latest composite date within `end`). A per-date rank history is not built.
6. ADR-6 / §11 exchange `redistributable=true` is already superseded by RFC-2 D4 (False).
7. The coingecko archive is legacy-map-only (D1). The plan assumes it reflects the curated map.
8. Backlog: the `/categories` keyword-vs-category read mismatch (finding 2). It needs its own plan, since the fix changes AC-1 output.

## Decisions needed from the user

- **D1 — CoinGecko in /history.** The archive only counts BTC/ETH/HYPE, so ai/rwa/memecoins are always 0.
  (a) **Recommended:** show the series labelled "legacy-map count", keep it **out of** the composite
  everywhere, and add a curated-map count to RFC-4's nightly job under a new key (`coingecko-curated/{id}`)
  that joins the composite once it exists. (b) Show it and include it in the composite as is.
  (c) Drop it from `/history`.
- **D2 — Backfilled pytrends in the composite.** (a) **Recommended:** include it (whichever variant exists
  on the date) and flag those points and any change figure spanning both `mixed_scale`. (b) Display it only:
  the composite uses nightly pytrends only, which means little composite history until the nightly archive grows.
- **D3 — Exchange volume share in the composite.** Plan §11's example (`coverage: 0.75`) implies 4 sources.
  (a) **Recommended:** include `volume_share` as a composite source, but keep `new_listing_count` display-only
  (sparse counts). (b) Keep all exchange data display-only (composite = pytrends + reddit + coingecko).

Everything else in §1–§4 is a technical call made in this report, and I will build it as written unless
you object.

TL;DR: `/history` is a read-only, category-first endpoint using the `/regime` grid/gap shape. The composite
needs ≥2 sources per date and the rank and 7-day change are defined above. Waiting on D1 (the legacy-only
CoinGecko count), D2 (backfilled pytrends in the composite) and D3 (exchange share in the composite).
