---
name: innovate:personal-tracker-realignment
description: "INNOVATE Decision Summary for the personal-tracker realignment: chosen and rejected approach for areas A-H (freshness, retention, gain chips, charts, BTC leg chart, verdict removal, layout, equities), plus the S1-S10 slice table with estimates"
date: 03-10-26
feature: general-plans
metadata:
  node_type: memory
  type: innovate
---

[MODE: INNOVATE]

# Personal Tracker Realignment: INNOVATE Decision Summary

**TL;DR:** The user chose the recommended option in all eight areas (03-10-26). The core fix is data freshness: the forming candle must expire, and the gap bug is fixed by fetching the latest bars. Chips, charts and the BTC leg chart build on that. Verdict code is removed in four stages. Work is cut into ten slices (S1-S10), about 20-45 USD [estimate]. PLAN is NOT approved yet and a program budget decision is pending.

Sources: SPEC `personal-tracker-realignment_SPEC_02-10-26.md` (D1-D11, defects F1-F5); decisions.md D-14; master-planner.md section 6 (subagent caps).

## Decisions by area

**A. Freshness.** CHOSEN: `_cache_is_fresh` treats the forming candle as fresh only within a short per-timeframe TTL, using a stored `fetched_at`. Gap fix = TAIL fetch (`since=None`, `limit=N` latest bars). Stale when the last bar is older than 2 x timeframe + refresh interval (15m ~45 min, 1h ~2h15, 4h ~8h15, 1d ~2 days; 1w judged on its 1d). Chart payload gets additive fields `last_bar_ts`, `fetched_at`, `is_partial`, `server_time`, `stale`. Real-world check: ccxt Hyperliquid `fetch_time` vs host clock; skew shown as a number, warning above ~2 min, once per refresh, not per coin. Axis labelled UTC. Refresh = in-process background worker every 15 min, plus a refresh when stale data is loaded (thread pool 4-6, per-coin/timeframe locks, cached-first page per D3).
REJECTED: looping since-advancing fetch (slow, more calls); two-path fallback (two code paths to test); Task Scheduler job as primary (`deploy/**` is RT4 and blocked on R12; kept as optional last slice S10); request-time concurrent fetch alone (slow first paint).

**B. Retention.** CHOSEN: trim on write to ~200 bars per timeframe; weekly derived from daily; repo check of cache categories vs displayed pages (AC-14). REJECTED: trim on read (files keep growing); nightly trim (extra job, window of bloat).

**C. Gain chips.** CHOSEN (user F4): current candle open to latest price. Contract keeps `percent_change_by_timeframe` and adds per-timeframe `{pct, open_ts, is_partial}` or null with a reason, never 0. Ships WITH A, since chips are only correct after the forming-candle fix. REJECTED: rolling window (not what the user asked).

**D. Charts.** CHOSEN: spike LayerChart 2.5 Chart `transform` (30-minute spike); if it fails, ONE shared custom gesture helper modelled on `web/islands/panel-sync.svelte.js`. Zoom on ALL charts including coin boxes: Ctrl/Cmd+wheel, two-finger pinch, double-click/tap reset, small reset button when zoomed; plain wheel scrolls the page; one-finger drag pans only when zoomed. Axis text as SVG (sharp), lines canvas or SVG; time axis UTC with explicit tick formats; one shared island. Spaghetti: a line per coin, % from window start, 0% anchor, BTC and HYPE fixed reference lines (thicker, distinct), per-coin toggles stored in the server layout file, hover highlight; 1w shows ~28 weeks and states the span. REJECTED: switching chart library (large rewrite); fetching more daily history for 1w; hiding 1w.

**E. BTC leg chart.** CHOSEN: new function taking the already-built composite and boundaries (shared helper factored out of `compute_current_leg_state`; `/api/regime/legs` unchanged). Payload: BTC daily history, confirmed leg spans, boundary dates, `current_leg` {start date, days in leg, composite value, 14-day change, last boundary z-score, confirmation state, composite variant}. Estimated leg label (D-14 narrow exception), headed "Estimate (rule over the numbers shown)", two parts with all inputs and thresholds on screen: leg age vs the median length of earlier confirmed legs (early/mid/late by thirds, sample size shown) + composite 14-day change vs a stated threshold (rising/falling/flat). REJECTED: a model/score (opaque); a single verdict word (the thing being removed). Tests: golden boundary dates, short history, no-composite (N/A), grep gate for verdict words with an allow-list.

**F. Verdict removal.** CHOSEN: STAGED: (1) API models + contract test + web types in lockstep; (2) delete web components; (3) delete analytics modules and `/scalp`; (4) CSS/copy + grep gate. D1 also drops `select_active_benchmark`, the "Benchmark:" label and `active_benchmark`. Narrative-owned fields are out of scope. REJECTED: big-bang (one huge unreviewable change); late removal (new work would build on dead code).

**G. Layout.** CHOSEN: server file `layout.json` next to `watchlist.json`: `{version, groups:[{id,name,coins}], hidden_lines}`; atomic temp+rename with a process-level lock; corrupt file falls back to one default group; GET/PUT whole document with a version check. 30-cap enforced in the API (existing extras kept, new adds blocked). Reordering via buttons + move-to-group menu now, drag later. REJECTED: native drag-and-drop alone (poor phone touch); a small DnD library (deferred).

**H. Equities.** CHOSEN: separate page and store (`equities.json`); LSE adapter probe-first (live capture on the user's PC saved as the fixture); key in env var; daily/weekly only; git-ignored parquet; `redistributable=false`. P6 depends on P4 for the shared box/RSI/chart island; the adapter can be built earlier. REJECTED: mixing equities into the crypto screener (different data and cadence).

## Slice table

Estimates are [estimate]; no slice has been measured. "Lane" = capped subagent lane (3 subagents, 15 USD per slice, one level).

| Slice | Scope | Tier | Deps | Lane | Estimate |
|---|---|---|---|---|---|
| S1 | Freshness core: `ccxt_adapter.py`, `cache.py` + tests | RT3 | none | yes | 60-90 calls, ~1h, 2-5 USD |
| S2 | Chips + chart labels: `momentum.py`, `screener_board.py`, `simple-lines.svelte` labels | RT3 | S1 | yes | 2-5 USD |
| S3 | Equities adapter, probe-first: new `api/data` lse*, ticker store | RT2 | parallel with S1 | no | 1-2 USD |
| S4 | Verdict removal, staged: models, types, ~20 source + ~12 test files | RT3 | S2 | yes | 4-9 USD |
| S5 | Layout/groups/cap: `watchlist.py`, new `layout.py`, ScreenerBoard, CoinPanel | RT3 | S4 | yes | 3-6 USD |
| S6 | Charts zoom/pan/DPR/spaghetti: `simple-lines.svelte`, new spaghetti component | RT1-RT3 | S2, S4 | no | 3-6 USD |
| S7 | BTC leg chart + label: new function, web component | RT3 | S4 | no | 2-4 USD |
| S8 | In-process refresh worker: API startup, refresh module | RT3 | S1 | yes | 2-4 USD |
| S9 | Equities page | RT1 | S3, S5 | no | 1-3 USD |
| S10 | Optional scheduled task: `deploy/**`, brief only | RT4 | S8, R12 | no | 3-8 USD |

Order: S1, then S2 (+S3 in parallel), then S4, then S5/S6/S7 in parallel (max 3 workers), S8 right after S1/S2, S10 last and optional. Total [estimate] ~20-45 USD, driven by the capped subagent lane. This needs a program budget decision from the user.

PC probes per slice: cache timestamps (S1); chip vs exchange site (S2); live LSE capture (S3); browser at DPR 2 (S6); phone pinch (S6); overnight refresh run (S8); 30-coin rate-limit check (S5/S8).

## Unverified facts to confirm before locking

- ccxt Hyperliquid `since`+`limit` returns the oldest 500 (PC probe).
- LayerChart `transform` works as needed (spike).
- LayerChart canvas DPR scaling (spike, browser at DPR 2).

## Next phase

PLAN needs the user's go. Plan format per `vc-generate-plan` (COMPLEX) with a validate-contract per slice. The first plan covers S1 + S2 (+S3 in parallel) only.
