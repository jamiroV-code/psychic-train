---
name: plan:screener-batch1
description: "Screener realignment batch 1: S1 freshness core, S2 current-candle chips plus UTC chart labels, S3 LSE equities adapter (probe-first), S8 in-process background refresh worker (pulled forward). Amendments folded; S4-S7, S9, S10 are later batches"
date: 03-10-26
feature: general-plans
---

# Screener Batch 1: Freshness, Chips, Equities Adapter and Refresh Worker (S1, S2, S3, S8)

Date: 03-10-26
Status: PLANNED. Supplement cycle 1 applied (amendments folded into the slice sections, S8 added); awaiting re-VALIDATE. No worker envelopes written, no EXECUTE approval.
Complexity: COMPLEX (S1 first; then S2 and S8 in parallel; S3 parallel throughout; RT3 shared cache, models, adapters, app startup)

**TL;DR:** Charts and chips show stale or wrong numbers: the forming candle counts as fresh until it closes, and a cache over 500 bars behind never catches up. S1 fixes the data layer and adds freshness fields. S2 adds correct chips and UTC labels. S8 (pulled forward by the user) adds a background refresh worker so a page load only reads the cache and the web client's 10 s timeout never bites. S3 builds the LSE equities adapter, probe-first. Estimate 9-19 USD [estimate]. A worker reads its slice section, "Decisions locked", "Gate conventions" and its Validate Contract rows (line ranges via `grep -n '^## \|^### '` at spawn time).

Sources: SPEC `personal-tracker-realignment_SPEC_02-10-26.md`, its INNOVATE doc, `process/general-plans/backlog/screener-research-findings_NOTE_03-10-26.md`, decisions.md D-14, master-planner.md 4-6, operating-instructions.md (RT tiers), `process/context/tests/all-tests.md`. Router: `process/context/all-context.md`.

Context Envelope: general-plans | PLAN (supplement) | batch 1 | claude/pensive-albattani-ou0cgv | /home/user/psychic-train | tests, data-sources | api/, web/ | this file | pytest then vitest | contract CONDITIONAL.

## Overview

Goal: true, current, labelled screener data that never blocks on the exchange, and a tested equities adapter. Scope: S1, S2, S3, S8. Non-goals: verdict removal, layout, zoom/pan, spaghetti, BTC leg chart, equities page, scheduled task (S4-S7, S9, S10).

## Name check against the INNOVATE doc (real code read 03-10-26)

| INNOVATE / SPEC says | Actual code | Plan consequence |
|---|---|---|
| S1 = `ccxt_adapter.py`, `cache.py`; SPEC cites `_cache_is_fresh` ~179-191, cache-first ~352 | `_cache_is_fresh` is `ccxt_adapter.py:173-184`, cache-first return 354-355, the gap bug is `effective_since` at 371-374; payload also needs `models/screener.py`, `screener_board.py`, `screener.ts` | S1 owns those plus new pure `api/data/freshness.py` |
| S2 file = `momentum.py` | `compute_percent_change` (113-123) and `compute_percent_change_by_timeframe` (126-133) are used only at `screener_board.py:146`; verdict code is S4's | new chip logic in `api/analytics/indicators/gain.py`; S2 only deletes the two functions and `PCT_CHANGE_MIN_BARS` |
| B: trim every timeframe to ~200 | `1d` feeds pairs (`compute_pairs.py`, `pairs_response.py:156`), BTC legs (`leg_boundary.py:164`), deep backfill (`backfill_pairs_universe.py:92`) | trim 15m/1h/4h only (user ruling 03-10-26: 1d never trimmed) |
| `fetch_time` at `hyperliquid.py:117/420-431` | exists in ccxt 4.5.78 (VALIDATE, offline) | response level needs the PC probe |
| LSE adapter "`api/data` lse*" | no `lse-data` dependency; user ruled out the SDK | `lse_adapter.py`, `equities_store.py`, plain `httpx` |
| D5 "~28 weekly bars enough" | Wilder RSI keeps weight (13/14)^k of its seed: 35% at 28 bars, 1.4% at 72 (500 daily) | keep 500+ daily bars |
| S8 "after S1/S2" | board calls `fetch_ohlcv` at `screener_board.py:134-143, 202-203, 229` | S8 sets a cache-only context flag in the router, so it does not edit `screener_board.py` (S2's file) |

## Decisions locked for this batch

- **B1 fetched_at: sidecar per (symbol, timeframe).** `cache/ohlcv/<SYM>/<tf>.meta.json` = `fetched_at` + `schema: 1`, written atomically AFTER the parquet via `json` + `tempfile.mkstemp(dir=..., prefix=".<name>.", suffix=".tmp")` + `os.replace`, temp removed on any exception. Rejected: parquet footer metadata (breaks `test_cache_atomic_writes.py::test_no_bypass` and the interruption tests), extra column (changes `OHLCV_COLUMNS`), mtime only (implicit). A crash can only leave the sidecar older than the parquet (extra refetch, never a missed one). Migration: none; no sidecar means parquet mtime; the first successful refresh creates the sidecar. `1w` stores its daily leg's value. Rule (D2): the text of `cache.py`, comments and docstrings included, contains `.to_parquet(` exactly once (`test_no_bypass` counts the literal).
- **B2 retention.** `retain_bars=200` on write for 15m, 1h, 4h only. `1d` is never trimmed (500+ bars); `1w` derives from all cached daily bars (about 72 weeks).
- **B3 tail fetch.** With `since=None`: explicit `limit=TAIL_LIMIT` always (15m/1h/4h 200, 1d 500; `limit=None` would request from epoch 0). The request start lives in one helper `_tail_since(timeframe, now)` returning `None` today (fallback if the PC probe shows `since=None` does not return the latest bars: `now_ms - (TAIL_LIMIT - 1) x timeframe_ms`). Contiguous with the cache (oldest fetched open <= cached last open + 1 timeframe): merge, newest wins. Non-contiguous sub-daily: cache REPLACED, `note="gap-replaced"`. Non-contiguous `1d` (D18): cached deep history is KEPT, tail appended, `note="gap-kept"`. A successful empty `[]` response (D5) writes nothing and leaves cache and sidecar unchanged; status from B5 on the cached newest bar. Newest bar older than the staleness threshold gives status `stale` (existing unused `Status` value). Explicit `since` keeps today's path (`backfill_pairs_universe.py`).
- **B4 freshness.** Fresh only if `fetched_at` is inside the current bar AND younger than `FORMING_TTL`: 15m 180 s, 1h 300 s, 4h 900 s, 1d 900 s (1d = AC-13's 15 minutes) [estimate]. Tests inject a clock via `ccxt_adapter._now()`.
- **B5 staleness.** `stale` = (reference now - newest bar open) > 2 x timeframe + 900 s: 15m 2700, 1h 8100, 4h 29700, 1d 173700 s (strict); `1w` judged on its `1d` bar. `is_partial` = open + timeframe > reference now. Reference now = host clock corrected by the measured skew when known.
- **B6 clock skew.** Measured inside the live fetch path (tests never touch the network): `fetch_time` bracketed by two host reads, skew = host midpoint minus exchange time, cached 15 minutes per process. Warning above 120 s; missing or failing `fetch_time` = unknown, no warning.
- **B7** chip availability is independent of the 60-bar chart threshold.
- **B8** SVG axis text is NOT in S2 (structural, with zoom/pan/DPR in S6).
- **B9 refresh worker (S8).** In-process loop started by the app lifespan; default on, off when `SCREENER_REFRESH_WORKER=0` or when `SCREENER_CACHE_ROOT` is set to a non-default root (tests, E2E) so a throwaway cache is never background-refreshed. While it runs, board, scalp and relative-performance reads are CACHE-ONLY and queue a refresh for stale or missing pairs; with it off, behaviour is exactly S1's fetch-through. The web client timeout (`web/lib/api/screener.ts:13`, 10 s) is NOT changed (user, D7).

## Gate conventions (all slices; folds A-ALL-1..6)

1. Every pytest gate runs with `UV_FROZEN=1`. RT3 snapshot rule: `git diff --name-only --diff-filter=MDR origin/main...HEAD | grep -E '/fixtures/'` prints nothing (adding files is allowed).
2. Baselines (measured at origin/main af7888f, re-recorded by each worker at spawn): pytest 870 passed, 1 skipped, 5 deselected, 1 xfailed; vitest 223 passed in 30 files; tsc exit 0; islands exit 0.
3. Every NEW payload timestamp is ISO-8601 UTC with seconds and a trailing `Z` (`2026-10-03T14:15:00Z`); `ChartBar.timestamp` is unchanged.
4. Report heading 6 records every gate run with SHA and UTC time; the tester re-runs only gates whose paths changed (`git diff --quiet <sha> HEAD -- <paths>`).
5. Worker cap: an envelope gives the worker only its slice section, these conventions and its contract rows, by line range; the defect and amendment index is for the planner.
6. Workers branch from `main`: this plan and contract must be on `main` before any envelope is issued, otherwise the `origin/main...HEAD` scope checks list the process files as strays.

## Sequencing

S1 first. After the S1 merge SHA exists, S2 and S8 start in parallel (both branch from `main` at that SHA). They are file-disjoint: S2 owns `gain.py`, `momentum.py`, `screener_board.py`, `models/screener.py`, the web files and two test files; S8 owns `ccxt_adapter.py` (merged S1 file), `refresh_worker.py`, `routers/refresh.py`, `routers/screener.py`, `main.py`, `tests/conftest.py` and its own tests. If a worker finds it needs the other's file, it stops at `review` and the planner serializes (S2 then S8). S3 runs in parallel from the start. Max 3 concurrent workers (S3 + S2 + S8 at peak). Merges are serialized (master-planner.md 5.6): one at a time, each rebased on the current `origin/main` with CI re-run. Do not deploy S1 to the PC before S8 has merged (S1 alone makes a board opened after idle fetch up to 120 pairs inline: the D7 latency S8 removes).

## Program budget

User decision 03-10-26: 45 USD ceiling for the whole screener program, checked per slice before each spawn; 15 USD cap per slice for subagents. Batch 1 [estimate]: S1 2-5, S2 3-6, S3 1-2, S8 3-6 = 9-19 USD; nothing spent yet on this program (the recovery spend of 6.9042678 USD is separate and not counted). That leaves 26-36 USD for S4-S7, S9, S10 (INNOVATE: 16-36), so the ceiling may bind: re-check after S2 and S8.

## S1: Freshness core (RT3, capped subagent lane: yes)

**Goal:** the forming candle expires, the gap bug is gone, sub-daily history is bounded, every chart payload says how fresh it is, and the existing red proof for this feature turns green.

**Owned (exact):** `api/data/ccxt_adapter.py`, `api/data/cache.py`, `api/data/freshness.py` (new, pure), `api/models/screener.py`, `api/analytics/screener_board.py`, `web/lib/types/screener.ts`; new tests `api/tests/data/test_freshness.py`, `test_ccxt_tail_fetch.py`, `test_cache_fetched_at_retention.py`, `test_ccxt_clock_skew.py`, `api/tests/routers/test_screener_freshness_payload.py`; edits to `api/tests/deploy/test_fresh_deploy_degrade.py` (only the parametrized case `screener_chart_carries_staleness_marker`: drop `xfail(strict=True)`, assert `chart["stale"] is True and chart["last_bar_ts"] and chart["server_time"]` on its 30-day-aged BTC cache; D1), `api/tests/data/test_ccxt_symbol_resolution.py` (only `test_a_cold_cache_still_reaches_the_exchange`: give the fake bar the injected clock's current-bar open, keep `status == "ok"`; D3), fixture-builder edits in `web/components/screener/__tests__/ScreenerBoard.test.tsx` and `DrillDownView.test.tsx`; `process/general-plans/active/screener-batch1_03-10-26/s1-probe/**`; report `screener-batch1-s1_REPORT_<dd-mm-yy>.md`; backlog stub `process/general-plans/backlog/ohlcv-negative-cache-and-1d-gap-replace_NOTE_<dd-mm-yy>.md` (failed-fetch retry cost D7, 1d gap-kept D18). Any other existing test that breaks stops the worker at `needs_input`.

**Forbidden:** CLAUDE.md, AGENTS.md, README.md, `.claude/**`, `.github/**`, `deploy/**`, `api/scripts/**` (so `seed_e2e_cache.py` and `refresh_cache.py` are not edited: the seed stamps `fetched_at` = now through `write_ohlcv`; `refresh_cache.py:74` counts a `stale` coin as not ok, benign, report it in heading 9), `process/MASTER-PLAN.md`, `process/context/current-state.md`, `process/archive/**`, S2, S3 and S8 files.

**Frozen for S3 and S8 (do not change signature or behaviour):** `cache._atomic_to_parquet(df, path)`, `cache.CACHE_ROOT`, `cache.OHLCV_COLUMNS`, `cache.bootstrap_cache_dirs()`, `ccxt_adapter._derive_weekly_from_daily(daily_df, source)`, `ccxt_adapter.fetch_ohlcv` signature.

**Design:**
1. `freshness.py`: constants (timeframe seconds, `FORMING_TTL`, `RETAIN_BARS`, `TAIL_LIMIT`, 900 s allowance) and pure `current_bar_open`, `cache_is_fresh`, `is_stale`, `is_partial`. No ccxt import; S2, S3, S8 import it.
2. `cache.py`: `write_ohlcv(symbol, timeframe, df, *, retain_bars=None, fetched_at=None)` keeps the newest N rows after the existing sort/dedupe, writes the parquet through the unchanged `_atomic_to_parquet`, then the sidecar (B1; default now). New `read_fetched_at` = sidecar, else parquet mtime, else None.
3. `ccxt_adapter.py`: `_now()`; `_cache_is_fresh(cached, timeframe, fetched_at=None, now=None)` delegates to `freshness`; the tail path (B3) replaces 371-374; trim sub-daily on every write; `OhlcvResult` gains `fetched_at` and `note` APPENDED after `status`, both defaulted (`test_relative_performance.py:39` builds it with 5 positional args; D4); `1w` passes the daily `fetched_at`; `last_clock_skew()` plus the opportunistic measurement (B6) reusing the already-built exchange. `fetch_ohlcv(exchange=)` stays the injection point.
4. `models/screener.py` (additive, defaulted): `ChartSeries` gains `last_bar_ts`, `fetched_at`, `is_partial`, `server_time`, `stale` (timestamps in the `Z` form, convention 3); `ScreenerBoardResponse` gains `server_time`, `clock_skew_seconds`, `clock_skew_warning`. An unavailable chart has nulls and `stale=False`. `screener_board._chart_series` fills them from the `OhlcvResult` (1w: `stale` from the daily result).
5. `screener.ts` mirrors exactly (hand-synced); the two web fixtures get the new fields.

**Tests (names):**
- `test_freshness.py` (5): `test_stale_threshold_per_timeframe_boundary`, `test_one_week_staleness_is_judged_on_its_daily_bar`, `test_is_partial_true_inside_bar_false_after_close`, `test_cache_is_fresh_requires_fetch_inside_current_bar`, `test_forming_ttl_boundary_per_timeframe`.
- `test_ccxt_tail_fetch.py` (12; fake exchange returns the OLDEST `limit` bars when `since` is given and the LATEST `limit` when None; fake clock): `test_tail_fetch_uses_since_none_and_latest_limit`, `test_500_bar_gap_regression_catches_up` (15m cache 576 bars behind), `test_forming_candle_refresh_after_ttl`, `test_forming_candle_not_refetched_inside_ttl`, `test_new_bar_boundary_forces_refetch_even_inside_ttl`, `test_non_contiguous_tail_replaces_cache_and_notes_gap`, `test_old_newest_bar_returns_status_stale`, `test_failed_fetch_keeps_cache_and_fetched_at`, `test_explicit_since_path_unchanged_for_backfill`, `test_one_week_derivation_uses_daily_fetched_at`, `test_empty_tail_response_keeps_cache_and_fetched_at`, `test_one_day_gap_keeps_deep_history_and_notes_gap_kept`.
- `test_cache_fetched_at_retention.py` (6): `test_sidecar_round_trip_and_written_after_parquet`, `test_legacy_parquet_without_sidecar_uses_mtime`, `test_sidecar_never_newer_than_parquet_after_crash`, `test_trim_on_write_15m_1h_4h_keeps_newest_200`, `test_one_day_bars_are_never_trimmed`, `test_write_defaults_fetched_at_to_now`.
- `test_ccxt_clock_skew.py` (5): `test_skew_is_host_midpoint_minus_exchange_time`, `test_skew_warning_above_120s_only`, `test_skew_measured_once_per_15_minutes`, `test_missing_fetch_time_means_unknown_not_error`, `test_fetch_time_exception_means_unknown`.
- `test_screener_freshness_payload.py` (4): `test_chart_series_carries_freshness_fields`, `test_unavailable_chart_has_null_freshness`, `test_board_carries_clock_skew_fields`, `test_pydantic_fields_match_typescript_interfaces`.

**Gates and probe:** exact commands and expected outputs in "S1 exact gates" (G-S1-1..11, P-S1-1). Red today: tests first, run G-S1-1 once on the untouched base and record it; behavioural reds: `test_forming_candle_refresh_after_ttl`, `test_500_bar_gap_regression_catches_up`, `test_trim_on_write_15m_1h_4h_keeps_newest_200`; the flipped deploy case is red today with `--runxfail`. The PC probe `s1-probe/probe_freshness.py` (read-only) prints (a) the cache table with age and sidecar, (b) host UTC, `fetch_time` and skew, (c) which end of history `since=None, limit=5` and `since=3d ago, limit=5` return, (d) wall-clock seconds and live-call count of one `GET /api/screener/board?timeframe=1h` with expired TTLs, stated against the 10 s web timeout in the report.

**Lane:** capped subagent lane yes (RT3): at most 3 subagents, 15 USD, one level: one `vc-tester` confirming gates from report heading 6 and CI, and one read-only reviewer diffing `models/screener.py` against `screener.ts` and checking the existing fake exchanges satisfy the tail call. Worker opus, subagents sonnet. **Budget [estimate]:** 120 tool calls, 90 minutes, 4 CI polls, 2-5 USD, 2 full-suite runs.

**Risks:** (1) a board opened after idle refetches up to 30 coins x 4 frames at 0.3-0.8 s (36-96 s) plus 12.5 s `load_markets` cold, above the web client's 10 s abort; solved by S8, so do not deploy S1 alone; failed fetches are not negatively cached. (2) Legacy parquet on the PC: no migration; 500-bar 15m files shrink at their next write. (3) Sidecar collisions: one file per (symbol, timeframe), atomic. (4) Tail response semantics are verified at request level only; `stale` status and `_tail_since` make a wrong assumption visible and fixable. (5) Seeded E2E bars go non-fresh after their TTL; cached bars are still served.

**Rollback:** revert the PR. Sidecars are git-ignored; trimmed 15m/1h/4h bars are re-fetchable (up to 5000 candles); 1d untouched; model fields additive.

## S2: Current-candle chips and chart labels (RT3, capped subagent lane: yes)

**Goal:** each gain chip shows the current candle (open to latest price) with an explicit N/A; every coin-box and drill-down chart states its last bar in UTC with age and a plain `stale` marker.

Starts only after the S1 merge SHA exists (branch from `main` at it). A needed change in `freshness.py`, `cache.py` or `ccxt_adapter.py` stops at `review`. Runs in parallel with S8 (file-disjoint, see Sequencing).

**Owned (exact):** `api/analytics/indicators/gain.py` (new); `api/analytics/indicators/momentum.py` (delete only `compute_percent_change`, `compute_percent_change_by_timeframe`, `PCT_CHANGE_MIN_BARS`); `api/analytics/screener_board.py`; `api/models/screener.py`; `web/lib/types/screener.ts`; `web/lib/chart-time-format.ts`, `web/lib/chart-freshness.ts` (new); `web/lib/island-loader.ts`; `web/islands/simple-lines.svelte`; `web/components/chart/MiniChart.tsx`; `web/components/chart/ChartFreshness.tsx` (new); `web/components/screener/CoinPanel.tsx`, `DrillDownView.tsx`, `ScreenerBoard.tsx`; tests `api/tests/analytics/test_gain.py`, `api/tests/routers/test_screener_gain_contract.py` (new), edits to `api/tests/analytics/test_momentum.py` (remove the golden test at line 171 and its imports), `api/tests/routers/test_screener.py` (`_df` fixtures: open = previous close so chips are non-flat; chip tests at 192 and 205 keep asserting `None` for thin slots and gain `gain_by_timeframe` assertions), `web/lib/__tests__/chart-time-format.test.ts`, `chart-freshness.test.ts`, `web/components/chart/__tests__/ChartFreshness.test.tsx` (new), `ScreenerBoard.test.tsx`, `DrillDownView.test.tsx`, `web/e2e/screener.spec.ts` (only test 4, lines 141-157: replace the "never `0.0%`" regex by "every chip is `N/A` or matches `^[+-]?\d+\.\d%$`, `chart-unavailable` still visible, API `gain_by_timeframe` for THIN has `pct` or `reason` per timeframe"; D8); report `screener-batch1-s2_REPORT_<dd-mm-yy>.md`; backlog stub `process/general-plans/backlog/island-axis-labels-render-check_NOTE_<dd-mm-yy>.md` only if the spike reaches fallback step 3.

**Forbidden:** the S1 global list, S3 and S8 files, `api/data/**`, `api/routers/**`, `api/main.py`, `RelativePerformanceChart.tsx`, the verdict components.

**Design:**
1. Contract (additive): `CoinPanel.gain_by_timeframe: dict[Timeframe, GainChip]`, `GainChip` = `pct: float|None`, `open_ts: str|None` (`Z` form, convention 3), `is_partial: bool`, `stale: bool`, `reason: UnavailableReason|None` (a superset of INNOVATE's `{pct, open_ts, is_partial}`). `percent_change_by_timeframe` stays, filled from the chip `pct`. TS mirror in lockstep.
2. Formula (`gain.py`; Python is the single source of truth): newest bar of the timeframe, `pct = (close - open) / open x 100`, `open_ts` its open, `is_partial` and `stale` from `freshness`. 15m/1h/4h/1d use their own newest bar (1d = since 00:00 UTC). 1w uses the newest bucket of `_derive_weekly_from_daily` (Monday 00:00 UTC anchor) and is N/A with `reason=insufficient-history` unless the Monday date of that bucket is present among the daily timestamps (explicit check; the derivation labels a bucket with its Monday even when the Monday bar is missing, D9). N/A with a reason, never 0, also for: empty frame, NaN or non-positive open, adapter status `bad_symbol`/`unavailable` with no data. A flat candle (open = close) is a real 0.0.
3. `build_coin_panel` replaces `compute_percent_change_by_timeframe` (line 146) with the chip builder (all five frames are already fetched there).
4. `chart-time-format.ts` (pure): UTC axis (island uses `scaleUtc`; `Intl.DateTimeFormat` with `timeZone: "UTC"`). 15m/1h/4h ticks `HH:mm`, first tick of each UTC day `DD MMM`; 1d/1w `DD MMM`, `MMM YY` when the span exceeds 365 days. `timeframe` is an OPTIONAL prop through `island-loader.ts`, `simple-lines.svelte` and `MiniChart`; when absent the axis is exactly today's (`scaleTime`, `ticks={4}`), so `RelativePerformanceChart.tsx` and its vitest are unchanged. `ScreenerBoard` passes the board timeframe to `CoinPanel`; `DrillDownView` passes its own.
5. `chart-freshness.ts` + `ChartFreshness.tsx`: caption `Last bar 2026-10-03 14:15 UTC, opened 7 min ago (forming)` (closed bar: `Last bar 2026-10-03 14:00 UTC, 22 min ago`) aged against the payload `server_time`, not the browser clock; units `<1 min`, `N min` (under 120), `N h` (under 48), else `N d`; a plain `stale` marker (`data-testid="stale-marker"`) when `stale`; rendered under the chart in `CoinPanel` and `DrillDownView`.
6. **U3 spike (axis `format` on `scaleUtc`), worker step 8a before the Svelte change:** implement the UTC axis, run `pnpm build:islands` (compiles Svelte, does NOT type-check LayerChart props), then screenshot the seeded E2E stack in the cloud container (`PLAYWRIGHT_CHROMIUM_PATH=/opt/pw-browsers/chromium-1194/chrome-linux/chrome`) and read the PNG. Fallback chain: (1) `format` function on `Axis` with `scaleUtc`; (2) pre-formatted tick values (`ticks` as `Date[]` from `chart-time-format.ts`); (3) if labels still render wrong, keep the old axis, ship captions and the marker (DOM, fully tested), write the backlog stub, S2 stays at `review` for AC-S2-3r only.
7. Stays for S6: zoom/pan/pinch, DPR sharpness, SVG axis text, spaghetti.

**Tests (names):**
- `test_gain.py` (11): `test_chip_15m_golden_open_to_latest`, `test_chip_1h_golden`, `test_chip_4h_golden`, `test_chip_1d_is_since_midnight_utc_golden`, `test_chip_1w_monday_anchor_golden` (daily Mon 28 Sep to Thu 1 Oct 2026, opens 100/102/101/105, closes 102/101/104/106: open 100, close 106, +6.0%, `open_ts` 2026-09-28T00:00:00Z), `test_chip_1w_without_monday_bar_is_na`, `test_empty_frame_is_na_never_zero`, `test_nan_or_zero_open_is_na`, `test_flat_candle_is_real_zero`, `test_is_partial_and_stale_flags_follow_reference_time`, `test_adapter_status_maps_to_reason`.
- `test_screener_gain_contract.py` (2): `test_gain_chip_fields_match_typescript`, `test_percent_change_by_timeframe_equals_chip_pct`.
- Vitest: `chart-time-format.test.ts` (per-timeframe goldens, day-boundary tick, year rule, run under `TZ=Pacific/Kiritimati`), `chart-freshness.test.ts`, `ChartFreshness.test.tsx`; ScreenerBoard and DrillDownView tests assert caption, stale marker and `gain-chip-1d` text from `gain_by_timeframe`; `RelativePerformanceChart.test.tsx` stays green untouched.

**Gates and probe:** "S2 exact gates" (G-S2-1..10, P-S2-1). Red today: base chips are first-to-last close, so the 1w and 1d goldens fail by value; new modules are absent. P-S2-1 (user PC): (1) BTC 1h and 1d chip `pct`/`open_ts` from `curl "http://127.0.0.1:8000/api/screener/board?timeframe=1h"` against the exchange chart's current candle open and last price; (2) UTC ticks, caption and `stale` marker (stop the API for a while).

**Lane:** capped subagent lane yes (RT3): one `vc-tester` and one read-only reviewer (Python/TS lockstep; coverage honesty: jsdom never mounts the island). Cap 3 subagents, 15 USD, one level. **Budget [estimate]:** 150 tool calls (D19), 100 minutes, 4 CI polls, 3-6 USD, 2 full-suite runs.

**Risks:** (1) LayerChart `Axis` taking a `format` function on `scaleUtc` is unverifiable offline (no precedent in the repo); the spike chain above covers it. (2) Existing fixtures are flat, so chips would read 0.0; fixed here. (3) `CoinPanel` gains a `timeframe` prop; S4/S5 edit it later (sequential).

**Rollback:** revert the PR; chips return to the old meaning, S1 fields stay.

## S3: LSE equities adapter, probe-first (RT2 plus secret-hygiene gates, capped subagent lane: no)

**Goal:** a tested adapter and ticker store for London Strategic Edge daily/weekly equity bars for a later page (S9), with live verification deferred to a user-PC probe. Tier (user, U-2): RT2 plus the secret gates below and the user's acceptance, instead of an RT4 evidence pack.

**Step 0 (user PC; blocks live verification only):** `s3-probe/lse_probe.py` + README, committed first. It reads `LSE_API_KEY` from the environment only (never a flag, never printed or written), uses plain `httpx` with an explicit timeout (no SDK; REST paths ASSUMED from the SDK's `candles`/`usage` calls) for AAPL daily (last 60 days), tries `timeframe="1w"` (D9 derives weekly from daily otherwise), a bad ticker and `/vault/usage` (shape only). Auth is ASSUMED header-only: the probe tries `Authorization: Bearer` then `X-API-Key` and prints only the scheme name and HTTP status, never a URL carrying the key, headers or a response body. Raw responses go to `api/data/cache/equities/_probe/` (git-ignored). It writes a SANITISED fixture `s3-probe/out/lse_candles_probe_shape.json`: symbol `TEST`, a deterministic synthetic walk (fixed seed), same keys, types and timestamp format as the real response; it never copies a real number. The repo is public and LSE forbids redistribution, so no real LSE price is ever committed (user). The user copies the file to `api/tests/data/fixtures/lse_candles_probe_shape.json`.

**Fixture absent (deterministic):** code the adapter against the documented shape (rows `{symbol, open, high, low, close, volume, timestamp ISO}`, up to 5000 rows per request) with an injectable `httpx` transport and isolated URL/auth constants; tests use `lse_candles_synthetic.json`; `test_probe_fixture_parses` is `skipif` the file is missing. It and live fetching are Known-Gap: write `process/general-plans/backlog/lse-live-shape-verification_NOTE_03-10-26.md`, list the skip in heading 7, and the S3 gate stays CONDITIONAL (no vacuous green) until the probe passes that test (user, U-2). The envelope inlines the row shape, the goldens and the adapter rules (`process/context/data-sources/all-data-sources.md:225-252`); the verdict and findings files exist only on `origin/claude/exciting-meitner-hy50kn`.

**Owned (exact):** `api/data/lse_adapter.py`, `api/data/equities_store.py` (new); `api/tests/data/test_lse_adapter.py`, `test_equities_store.py` (new); `api/tests/data/fixtures/lse_candles_synthetic.json` and the optional `lse_candles_probe_shape.json`; `.gitignore` (append `api/data/equities.json` only; `api/data/cache/equities/` is already ignored); `process/general-plans/active/screener-batch1_03-10-26/s3-probe/**`; `process/general-plans/backlog/lse-live-shape-verification_NOTE_03-10-26.md`; report `screener-batch1-s3_REPORT_<dd-mm-yy>.md`.

**Forbidden:** the S1 global list, `api/pyproject.toml`, `api/uv.lock`, `api/data/cache.py`, `api/data/ccxt_adapter.py` (read-only import of `_derive_weekly_from_daily` allowed), `api/models/**`, `api/routers/**`, `web/**`, S1, S2 and S8 files.

**Design:**
1. Env key `LSE_API_KEY`. Plain `httpx` GETs (already a dependency); every call passes an `httpx.Timeout` constant of at most 15 s; the key travels only in a request header, never in the URL or query. A missing key gives `unavailable`/`missing-key`, no network call, no raise. `result.reason` is a closed enum string, never `str(exc)`. Transport injectable for tests.
2. `fetch_equity_ohlcv(symbol, timeframe, transport=None, now=None) -> EquityOhlcvResult` (`df`, `status` in `ok|unavailable|stale|bad_symbol`, `reason`, `redistributable=False`, `source`, `caveats`), shaped like `fred_adapter.FredSeriesResult`. Only `1d` and `1w`; else `unavailable`/`unsupported-timeframe`. 1w from daily with the existing `_derive_weekly_from_daily`. A 404 ticker is `bad_symbol`.
3. Session calendar (D11): drop weekends and NYSE holidays from a small explicit rule set in `lse_adapter.py`; do NOT use `USFederalHolidayCalendar` (it observes New Year 2011 on Fri 2010-12-31 when NYSE was open, and includes Columbus and Veterans Day, when NYSE is open). Rules: New Year (Sunday moves to Monday; a Saturday is NOT observed), MLK (3rd Mon Jan), Presidents (3rd Mon Feb), Good Friday, Memorial (last Mon May), Juneteenth from 2022 (Sat to Fri, Sun to Mon), July 4 (Sat to Fri, Sun to Mon), Labor (1st Mon Sep), Thanksgiving (4th Thu Nov), Christmas (Sat to Fri, Sun to Mon). Special closures (2012-10-29/30, 2018-12-05, 2025-01-09) are not modelled: caveat `special-closures-not-modelled`. Other caveats: `split-adjusted-only`, `close-may-include-extended-hours`, `survivorship-bias`.
4. Cache `cache.CACHE_ROOT/"equities"/<SYM>/{1d,1w}.parquet` through `cache._atomic_to_parquet`; the footer tag is set with `df.attrs = {"mysite.redistributable": "false", "source": "lse"}` before the helper call (the helper has no metadata argument and is frozen), read back with `pd.read_parquet(path).attrs` or `pq.read_schema(path).pandas_metadata["attributes"]`, never through `cache.read_ohlcv` (DuckDB drops attrs). `lse_adapter.py` must not contain the literal `.to_parquet(`. A `fetched_at` sidecar in B1 style, TTL 6 h; path read at call time.
5. `equities_store.py`: `{"tickers": [...]}` in `api/data/equities.json`, override env `SCREENER_EQUITIES_PATH` resolved at call time, atomic temp+rename, idempotent add, ticker `^[A-Z][A-Z0-9.\-]{0,9}$`, NO 30-cap, removing a missing ticker raises `TickerNotFoundError`. No router, no web (S9). Tests use `isolated_cache` and `monkeypatch.setenv("SCREENER_EQUITIES_PATH", tmp)`, never the real `api/data/equities.json` or cache.
6. RSI: tests feed adapter output to the existing `momentum.compute_rsi`; if S4 moves it, S4 updates this test.

**Tests (names):** `test_lse_adapter.py` (16): `test_parse_documented_row_shape_to_ohlcv_frame`, `test_non_session_days_are_dropped` (2006-11-23, 2007-11-22, 2008-01-01, 2005-03-25 and SPY Saturdays 2026-05-02/09/16/23/30 out; an ordinary Tuesday kept), `test_session_calendar_nyse_traps` (2010-12-31, 2021-12-31, 2006-10-09, 2005-11-11 kept; 2015-07-03, 2022-06-20 dropped), `test_missing_key_is_unavailable_and_makes_no_call`, `test_http_error_or_timeout_never_raises`, `test_404_ticker_is_bad_symbol`, `test_unsupported_timeframe_is_unavailable`, `test_result_and_parquet_are_tagged_redistributable_false`, `test_weekly_is_monday_anchored_from_daily`, `test_cache_is_fresh_for_six_hours_then_refetched`, `test_rsi_on_equity_bars_via_compute_rsi`, `test_probe_fixture_parses` (skipif absent), `test_cache_path_is_gitignored`, `test_api_key_never_in_result_repr_logs_or_exception_text` (sentinel key `LSE_TEST_SENTINEL_KEY_0123456789` via `monkeypatch.setenv`; an `httpx.MockTransport` asserts the key arrives only in a header; force 401, 404, 500, `ConnectError`, `ReadTimeout`; the sentinel is absent from `repr(result)`, `reason`, `caveats`, `caplog.text` and exception text), `test_request_uses_explicit_timeout_and_header_auth`, `test_committed_lse_fixtures_are_synthetic_only` (every `api/tests/data/fixtures/lse_*.json` row has symbol `TEST` or `SYNTH`). `test_equities_store.py` (at least 6): add/remove/idempotent/uppercase, invalid ticker rejected, more than 30 accepted, interrupted write keeps the old file, path override honoured at call time.

**Gates and probe:** "S3 exact gates" (G-S3-1..9). Red today: modules absent; `api/data/equities.json` is not git-ignored. P-S3-1 (user PC): run `lse_probe.py` once (README: needs only `httpx`; set `LSE_API_KEY` for the session only; run; copy the sanitised fixture); it also answers weekly support and the bar-timestamp convention.

**Lane:** no subagents (RT2). **Budget [estimate]:** 80 tool calls, 60 minutes, 3 CI polls, 1-2 USD, 1 full-suite run.

**Risks:** (1) calendar rules dropping a real session (goldens); (2) shape, auth scheme, `1w`, timestamp hour verified only by the probe; (3) importing the private `_derive_weekly_from_daily`; (4) redistribution and key leaks: synthetic fixtures, sentinel test, header-only auth.

**Rollback:** revert the PR; delete `api/data/cache/equities/` and `api/data/equities.json` locally.

## S8: In-process background refresh worker (RT3, capped subagent lane: yes)

**Goal:** the API refreshes the cache itself every 15 minutes and on demand, so a page load only reads the cache (D3, D7) and never waits on the exchange; the 10 s web client timeout is unchanged.

Starts after the S1 merge SHA exists (branch from `main` at it); runs in parallel with S2 (file-disjoint).

**Code read:** `api/main.py` is a module-level `app = FastAPI(title=...)` with no lifespan, routers included at the bottom. Lifespan runs only for `with TestClient(app)` (one user: `api/tests/scripts/test_seed_onchain_fixture.py:113`). `refresh_cache.py` plans watchlist + BTC + HYPE over `cache.TIMEFRAMES` plus universe coins on `1d`; the worker mirrors only the first part. `fetch_ohlcv` holds `_exchange_lock` around the ccxt call, so live calls are serial whatever the pool size.

**Owned (exact):** `api/data/refresh_worker.py` (new); `api/routers/refresh.py` (new); `api/routers/screener.py` (wrap reads); `api/main.py` (lifespan + `include_router`); `api/data/ccxt_adapter.py` (add the cache-only context flag and the refresh-request hook; S1 behaviour unchanged when the flag is off); `api/tests/conftest.py` (one line: `os.environ.setdefault("SCREENER_REFRESH_WORKER", "0")` at the top); tests `api/tests/data/test_refresh_worker.py`, `api/tests/routers/test_refresh_router.py`, `api/tests/deploy/test_refresh_startup.py` (new); `process/general-plans/active/screener-batch1_03-10-26/s8-probe/**`; report `screener-batch1-s8_REPORT_<dd-mm-yy>.md`.

**Forbidden:** the S1 global list (so no `deploy/**`, no `api/scripts/**`), S1/S2/S3 files, `api/analytics/screener_board.py`, `api/models/screener.py`, `web/**`, `api/pyproject.toml`, `api/uv.lock`.

**Design:**
1. `RefreshWorker` (`refresh_worker.py`): a daemon thread loop; first tick 20 s after start, then every `SCREENER_REFRESH_INTERVAL_SECONDS` (default 900). Per tick: plan = sorted(watchlist + BTC + HYPE) x (15m, 1h, 4h, 1d), then derive 1w by calling `fetch_ohlcv(sym, "1w")` after the coin's 1d. Only pairs failing `freshness.cache_is_fresh` are fetched. A pool of 4 threads runs pairs; one non-blocking lock per (symbol, timeframe) so two refreshers never work on one file (a busy pair is skipped, not queued twice). Time and sleep are injectable (fake clock in tests); the exchange is injectable through `fetch_ohlcv(exchange=)`.
2. Failure isolation: every pair runs inside `try/except`; an exception is counted and logged without values or secrets and never leaves the thread; the loop itself is wrapped so it cannot die. Rate-limit-aware backoff: if a tick has no `ok`/`stale` pair and at least one `unavailable`, the next delay doubles (cap 3600 s) and resets after a tick with any success.
3. Cache-only reads (`ccxt_adapter`): a `ContextVar` flag with a context manager `cached_reads_only()`. Inside it `fetch_ohlcv` returns the cached frame (status per B5, `note="refresh-queued"` when it asked for a refresh) with ZERO exchange work, and calls the registered hook `request_refresh(symbol, timeframe)` for a stale or missing pair (non-blocking, deduplicated). A missing cache returns an empty frame with status `unavailable`, as today. `routers/screener.py` wraps `board`, `scalp` and `relative-performance` in that context only while the worker is running; with the worker off, behaviour is S1's fetch-through. This is the load-triggered refresh (D3): the page renders from cache immediately and a reload shows fresher data.
4. `routers/refresh.py`: `GET /api/refresh/status` returns `running`, `interval_seconds`, `last_tick_started`, `last_tick_finished`, `last_tick_ok`, `last_tick_failed`, `next_tick_at`, `queue_depth`, `backoff_seconds` (timestamps in the `Z` form); `POST /api/refresh/now` returns 202 and queues one run (never fetches inside the request; at most one pending run). The API is Tailscale-only; CORS already allows POST.
5. `main.py`: a `lifespan` context starts the worker and stops it (join with timeout, idempotent). The worker is not started when `SCREENER_REFRESH_WORKER=0` or when `SCREENER_CACHE_ROOT` is set to a non-default root (B9), so tests and the seeded E2E never background-refresh a throwaway cache and the real cache is never touched by the suite (`test_zz_real_data_guard.py` stays green).

**Tests (names):** `test_refresh_worker.py` (12; fake clock, fake exchange, no network): `test_tick_refreshes_watchlist_plus_benchmarks_all_timeframes`, `test_tick_skips_fresh_pairs`, `test_one_week_is_derived_not_fetched`, `test_per_pair_lock_never_two_refreshers_on_one_file` (two threads, barrier), `test_request_refresh_dedupes_and_never_blocks`, `test_stale_on_load_queues_refresh_and_board_reads_cache`, `test_cache_only_mode_makes_zero_exchange_calls`, `test_one_pair_failure_does_not_stop_the_tick`, `test_unavailable_streak_backs_off_and_resets_on_success`, `test_loop_ticks_every_interval_with_fake_clock`, `test_stop_joins_threads_and_is_idempotent`, `test_worker_exception_never_escapes_the_loop`. `test_refresh_router.py` (3): `test_status_endpoint_shape_and_counts`, `test_refresh_now_returns_202_and_queues_without_fetching`, `test_refresh_now_allows_one_pending_run`. `test_refresh_startup.py` (3): `test_lifespan_starts_and_stops_worker`, `test_worker_off_when_env_is_zero`, `test_worker_off_when_cache_root_is_overridden`.

**Gates and probe:** "S8 exact gates" (G-S8-1..9, P-S8-1). Red today: `refresh_worker.py`, `routers/refresh.py` and `cached_reads_only` do not exist; the board fetches inline. P-S8-1 (user PC, after S1 and S8 are merged and pulled): (1) overnight run: leave the API up 8 h or more, then `curl http://127.0.0.1:8000/api/refresh/status` shows ticks about every 15 minutes, failures low, and the board shows no `stale` marker; (2) 30-coin rate-limit check: with 30 coins read one tick's duration and failed count from the status endpoint and confirm no sustained backoff; (3) API restart: stop and start the API, the board answers from cache at once, the worker resumes after about 20 s; (4) re-run S1's probe item (d): board wall-clock with warm cache, stated against the 10 s web timeout.

**Lane:** capped subagent lane yes (RT3): one `vc-tester` and one read-only reviewer (thread-safety and lifespan review); cap 3 subagents, 15 USD, one level. **Budget [estimate]:** 130 tool calls, 100 minutes, 4 CI polls, 3-6 USD, 2 full-suite runs.

**Risks:** (1) the shared exchange singleton: live calls already serialize on `_exchange_lock`; kept. (2) cache-only mode applies only while the worker runs; the off path equals S1. (3) A cold cache shows `unavailable` until the first tick finishes (about 1-3 minutes for 30 coins); the page does not poll (a later web slice can poll the status endpoint). (4) `test_seed_onchain_fixture.py` (lifespan user) is protected by the conftest default and root-override rule. (5) Board compute time beyond fetches (about 3.3 s for 4 coins in the backlog latency note) is not addressed here; P-S8-1 (4) measures it. (6) A hand-run `refresh_cache.py` during a tick: writes are atomic, last writer wins.

**Rollback:** revert the PR (the lifespan and router disappear; the S1 fetch-through path returns). Setting `SCREENER_REFRESH_WORKER=0` disables the worker without a revert.

## Later batches (not in this plan; dependencies only)

| Slice | Scope | Depends on |
|---|---|---|
| S4 | Verdict removal in 4 stages (models/contract/types, web components, analytics + `/scalp`, CSS/copy + grep gate); drops `select_active_benchmark` | S2 |
| S5 | Layout, groups, 30-cap: `watchlist.py`, new `layout.py`, ScreenerBoard, CoinPanel | S4 |
| S6 | Zoom/pan/DPR, SVG axis text (B8), spaghetti chart | S2, S4 |
| S7 | BTC leg chart plus estimated leg label (D-14) | S4 |
| S9 | Equities page | S3, S5 |
| S10 | Optional scheduled task (`deploy/**`, RT4, brief only) | S8, R12 |

## Touchpoints

Changed: `api/data/{ccxt_adapter,cache,freshness,lse_adapter,equities_store,refresh_worker}.py`, `api/models/screener.py`, `api/analytics/{screener_board.py,indicators/gain.py,indicators/momentum.py}`, `api/routers/{screener,refresh}.py`, `api/main.py`, `api/tests/conftest.py`, the web files listed per slice, `web/e2e/screener.spec.ts` (one test), `.gitignore` (one line), the listed tests, task-folder probes and reports. Read only (constrain B2): `api/scripts/{seed_e2e_cache,refresh_cache,backfill_pairs_universe}.py`, `leg_boundary.py`, `pairs_response.py`.

## Public Contracts

- `ChartSeries`, `ScreenerBoardResponse` (S1) and `CoinPanel.gain_by_timeframe` (S2) additive, each hand-mirrored in `screener.ts` (RT3 pair, new contract-sync tests). `percent_change_by_timeframe` keeps its name, meaning becomes current-candle gain (F4).
- New endpoints `GET /api/refresh/status`, `POST /api/refresh/now` (S8); screener endpoints unchanged in shape.
- `fetch_ohlcv` signature unchanged; `OhlcvResult` gains defaulted `fetched_at`, `note`; `cache.write_ohlcv` gains keyword-only `retain_bars`, `fetched_at`; `ccxt_adapter.last_clock_skew()`, `cached_reads_only()`.
- On disk (git-ignored): sidecars, equities cache, `equities.json`. New env: `LSE_API_KEY`, `SCREENER_EQUITIES_PATH`, `SCREENER_REFRESH_WORKER`, `SCREENER_REFRESH_INTERVAL_SECONDS` (the planner documents them at UPDATE PROCESS).
- Security scan (STRIDE, quick): the key lives only in the environment and one header; LSE data stays out of git; `POST /api/refresh/now` allows one pending run on a Tailscale-only API.

## Blast Radius

About 55 files in `api/` and `web/`; shared cache, response contract and app startup (RT3) for S1/S2/S8, localized backend (RT2 plus secret gates) for S3. Other `fetch_ohlcv` consumers (pairs, leg boundary, `refresh_cache.py`, backfill) are protected by the unchanged `since` path, no-trim for 1d, the cache-only flag being off by default and the full-suite gate.

## Acceptance Criteria

The criterion table is the "Test gates" table in the Validate Contract (id, behaviour, strategy, proving test, gap resolution); every id there is bidirectionally linked to its gate. SPEC links: AC-S1-* = F1 (causes A, B, D), AC-13, AC-14, D5; AC-S2-* = F4, F1 D, AC-5; AC-S3-* = D9, D10, D11, AC-15; AC-S8-* = D3, D7, AC-13.

## Verification Evidence

| Gate / Scenario | Strategy | Proves SPEC criterion |
|---|---|---|
| G-S1-1, G-S1-8 S1 tests and flipped deploy case | Fully-Automated | F1 A/B/D, AC-13, AC-14 (AC-S1-1..9) |
| full pytest, vitest, tsc, islands gates of every slice | Fully-Automated | no regression; contract lockstep (AC-S1-7) |
| G-S2-1 gain tests, G-S2-4 TZ run | Fully-Automated | F4 (AC-S2-1..3) |
| G-S3-1 adapter and store, G-S3-5/9 secret gates | Fully-Automated | D9, D10, D11, AC-15 (AC-S3-1..4) |
| G-S8-1 worker, router, startup tests | Fully-Automated | D3, D7, AC-13 (AC-S8-1..4) |
| G-S2-8 E2E screener spec | Hybrid (chromium + seeded stack; NOT-RUN with reason allowed) | F4 contract on seeded data (AC-S2-6) |
| P-S1-1, P-S2-1, P-S8-1, P-S3-1 PC probes | Agent-Probe | real-world checks (AC-S1-2r/6r, AC-S2-3r/5, AC-S8-5, AC-S3-5); AC-S3-5 CONDITIONAL until run |

## Risk Predictions (condensed 5-persona pass)

Security: the only secret is `LSE_API_KEY` (sentinel test, header-only, timeout); synthetic fixtures plus a guard test keep LSE data out of the public repo. Performance: the board is cache-only once S8 runs; S1 alone is a latency regression, so it is not deployed before S8. Data integrity: gap-replace (sub-daily) and gap-kept (1d) protect pairs and legs; `stale`, N/A reasons and the `stale` status keep numbers honest. Maintainer: small pure modules, cache-only flag off by default. User: chips change value (intended).

## Implementation Checklist (atomic; one slice per worker)

**S1:** 1 baseline. 2 tests first (5 new files, deploy case flip, cold-cache fixture, 2 web fixtures); red run on untouched source. 3 `freshness.py`. 4 `cache.py` sidecar, `retain_bars`, `read_fetched_at`. 5 `ccxt_adapter.py` tail path, `_tail_since`, trim, appended fields. 6 clock skew. 7 models, `screener_board`, `screener.ts`. 8 `s1-probe` and stub. 9 G-S1-1 green (max 2 fix cycles per gate), then G-S1-2..10 once. 10 report, PR, CI, tester.
**S2** (after S1 merged): 1 baseline. 2 tests first, red run. 3 `gain.py`, `GainChip` in models and `screener.ts`, chip wiring, old functions and golden test deleted, `test_screener.py` fixtures. 4 `chart-time-format.ts`, `chart-freshness.ts`. 5 U3 spike with screenshot, then island and loader `timeframe`. 6 `ChartFreshness.tsx` and wiring. 7 E2E test 4. 8 G-S2-1..10. 9 report, PR, tester, probe steps.
**S3:** 1 baseline. 2 `s3-probe` committed first. 3 tests first, red run. 4 `equities_store.py`, `lse_adapter.py`, `.gitignore` line, backlog stub. 5 G-S3-1..9 (G-S3-6 CONDITIONAL). 6 report, PR.
**S8** (after S1 merged): 1 baseline. 2 tests first, red run. 3 `cached_reads_only` and hook in `ccxt_adapter.py`. 4 `refresh_worker.py`, `routers/refresh.py`, `routers/screener.py` wrap, `main.py` lifespan, conftest default. 5 `s8-probe` README. 6 G-S8-1..9. 7 report, PR, tester.

## Phase Completion Rules

A slice is `CODE DONE` when its PR is open with green gates in the report; `VERIFIED` only after independent confirmation (tester or CI on the head SHA, master-planner.md section 4) AND its user-PC evidence. Per the user (U-1, 03-10-26): S1, S2 and S8 may merge after the offline gates, and their registry tasks stay at `review` until the PC probes exist; S3 stays CONDITIONAL until the live probe passes `test_probe_fixture_parses`. A diff touching CLAUDE.md or AGENTS.md stops at `review`. Known-Gap is a residual, never a PASS.

## Amendment index (folded 03-10-26; the overlay section is gone)

| Id | Now lives in |
|---|---|
| A-ALL-1..6 | Gate conventions 1-6 |
| A-S1-1..9; D1-D6, D18 | S1 Owned, Frozen, Design, Tests, probe; B1 and B3; S1 exact gates |
| A-S2-1..8; D8-D10, D19 | S2 Owned, Design 2, 4, 6, Budget; G-S2-8/9; Gate convention 3 |
| A-S3-1..9; D11-D13 | S3 tier line, Step 0, Design 1-5, Tests; S3 exact gates |
| D14, D15, D16, D17 | exact gate tables; Gate convention 2; Resume (no literal PASS string); Gate convention 5 |
| D7, U-1..U-5 | S8, Sequencing; Phase Completion Rules, Resolved questions |

## Validate Contract

Status: CONDITIONAL (cycle-2 re-VALIDATE verdict: 0 FAIL, 4 CONCERN needing a plan fix, 3 advisories; supplement cycle 2 required before PASS)
Date: 03-10-26
date: 2026-10-03
generated-by: outer-pvl
supersedes: 2026-10-03 (outer-pvl, first-pass CONDITIONAL) - cycle-2 re-validation of the folded plan (HEAD c245f14, code origin/main af7888f) has current evidence
Gate: CONDITIONAL

**TL;DR (cycle 2):** the 11 first-pass concerns are resolved by the fold. Re-validation of S1, S2, S3 and the new S8 finds no FAIL. S2 and S3 are executable (their only conditions are the user-accepted live-probe items U-1, U-2, U-4). S1 and S8 have concerns that need a plan fix, so the PASS stamp is NOT given: N1 (S8) the exchange "markets failed" latch never resets, so the worker cannot recover after one failed start; N2 (S1) `test_weekly_recursion_does_not_deadlock` breaks under the new `stale` status and is not owned; N3 (S1) `stale` must apply only to the `since=None` path or the deep-backfill script and its test break; N4 (S8) nothing drains the refresh queue between ticks and `POST /api/refresh/now` has no worker-off behaviour. Next: PVL supplement cycle 2 (the last allowed fix cycle), then re-VALIDATE. Details: "Cycle-2 re-validation record" below.

**Validation record (first pass, plan HEAD e8824f8 against origin/main af7888f; one agent ran V1-V3 by direct reads and runs, confidence MEDIUM-HIGH, no source changed):** every cited path and line anchor exists; every gate command runs offline here. Baseline: pytest 870 passed, 1 skipped, 5 deselected, 1 xfailed (228 s); vitest 223 in 30 files; tsc and islands exit 0; `TZ=Pacific/Kiritimati pnpm --filter web exec vitest run <path>` works. Inline offline probes: ccxt 4.5.78 request shapes for `since=None` / explicit `since` / `limit=None`; `has['fetchTime']` true; `df.attrs` round-trips into the parquet footer; `USFederalHolidayCalendar` wrong for NYSE; `_derive_weekly_from_daily` hides a missing Monday bar. LSE facts match the verification findings. `.gitignore:18 api/data/cache/*` covers `equities/`, `_probe/`, `*.meta.json`; `api/data/equities.json` is not ignored.

### Verdict per slice

Cycle 2 (re-VALIDATE of the folded plan): S1 CONDITIONAL, fix needed (N2, N3), then probe-pending AC-S1-2r/6r accepted under U-1. S2 CONDITIONAL, executable as written (AC-S2-3r/5 probe-pending and hybrid E2E accepted under U-1/U-4; advisory N7; starts after the S1 merge SHA). S3 CONDITIONAL, executable as written (live probe pending, accepted under U-2; advisory N6). S8 CONDITIONAL, fix needed (N1, N4; advisory N5), then AC-S8-5 probe-pending accepted under U-1. Net: no FAIL; the PASS stamp is not given because S1 and S8 have concerns that need a plan fix (supplement cycle 2). Cycle 1 (superseded): S1-S3 CONDITIONAL, S8 not yet validated.

Parallel strategy: parallel-subagents: independent worker sessions (S1, S3 first; S2, S8 after the S1 merge); capped lane of at most 3 sonnet subagents in S1, S2, S8. Workers opus.

Test gates: the table below (strategy is one of the three proving strategies; Known-Gap is only ever a named residual via gap-resolution D), then the legacy line form, then exact gates per slice.

### Test gates

gap-resolution: A proven now / B added by this plan's checklist / C deferred to a named later step / D backlog stub (residual, keep-active).

| criterion id | behavior | strategy | proving test | gap-resolution |
|---|---|---|---|---|
| AC-S1-1 | forming candle refetched after TTL and at a bar boundary | Fully-Automated | G-S1-1 `test_forming_candle_refresh_after_ttl`, `test_forming_candle_not_refetched_inside_ttl`, `test_new_bar_boundary_forces_refetch_even_inside_ttl` | B |
| AC-S1-2 | 500+ bar gap catches up in one refresh | Fully-Automated | G-S1-1 `test_500_bar_gap_regression_catches_up`, `test_tail_fetch_uses_since_none_and_latest_limit` | B |
| AC-S1-2r | real Hyperliquid returns the latest bars for `since=None` | Agent-Probe | P-S1-1 (c) on the user PC | C (fallback B3 `_tail_since`; stub if not run) |
| AC-S1-3 | 15m/1h/4h trimmed to 200, 1d never | Fully-Automated | G-S1-1 trim tests | B |
| AC-S1-4 | staleness thresholds, 1w judged on its 1d | Fully-Automated | G-S1-1 `test_stale_threshold_per_timeframe_boundary`, `test_one_week_staleness_is_judged_on_its_daily_bar`, `test_old_newest_bar_returns_status_stale` | B |
| AC-S1-5 | payload fields on chart and board, TS mirror, aged cache gets a marker over HTTP | Fully-Automated | G-S1-1 payload tests, G-S1-4, G-S1-8 (flipped deploy case) | B |
| AC-S1-6 | skew once per refresh, warning above 120 s, unknown is silent | Fully-Automated | G-S1-1 skew tests | B |
| AC-S1-6r | real `fetch_time` works and skew is plausible | Agent-Probe | P-S1-1 (b) | C |
| AC-S1-7 | no migration, pairs/legs/BTC unaffected, atomic-write tests intact | Fully-Automated | G-S1-1 legacy test, G-S1-2, G-S1-9 | B |
| AC-S1-8 | empty tail response keeps cache | Fully-Automated | G-S1-1 `test_empty_tail_response_keeps_cache_and_fetched_at` | B |
| AC-S1-9 | a 1d gap keeps deep daily history | Fully-Automated | G-S1-1 `test_one_day_gap_keeps_deep_history_and_notes_gap_kept` | B |
| AC-S2-1 | chip = current candle open to latest, Monday-anchored week | Fully-Automated | G-S2-1 `test_gain.py` goldens | B |
| AC-S2-2 | N/A with a reason, never 0; real flat is 0.0 | Fully-Automated | G-S2-1 | B |
| AC-S2-3 | UTC ticks, browser-zone independent | Fully-Automated | G-S2-3, G-S2-4 (formatter) | B |
| AC-S2-3r | the island actually draws those labels | Agent-Probe | S2 Design 6 screenshot, P-S2-1 (2) | C/D (stub) |
| AC-S2-4 | `Last bar ... UTC, <age>` caption and `stale` marker, coin box and drill-down | Fully-Automated | G-S2-3 component tests | B |
| AC-S2-5 | chips equal the exchange chart | Agent-Probe | P-S2-1 (1) | C |
| AC-S2-6 | E2E thin-history spec matches the new contract | Hybrid | G-S2-8 (precondition: chromium + seeded stack) | B (run: C) |
| AC-S3-1 | parse, non-session days dropped (incl. NYSE traps), weekly derived, never raises | Fully-Automated | G-S3-1 | B |
| AC-S3-2 | missing key -> unavailable, no call | Fully-Automated | G-S3-1 | B |
| AC-S3-3 | `redistributable=false` on result and parquet footer; cache ignored; key never leaks; fixtures synthetic | Fully-Automated | G-S3-1 (sentinel, header-auth, synthetic-fixture tests), G-S3-5, G-S3-8, G-S3-9 | B |
| AC-S3-4 | ticker store separate, no cap, atomic | Fully-Automated | G-S3-1 | B |
| AC-S8-1 | the loop refreshes watchlist + BTC + HYPE every interval, skips fresh pairs, derives 1w | Fully-Automated | G-S8-1 tick, skip, derive, interval tests | B |
| AC-S8-2 | never two refreshers on one file; failures isolated; backoff on unavailable streaks | Fully-Automated | G-S8-1 lock, isolation, backoff tests | B |
| AC-S8-3 | board reads are cache-only while the worker runs and queue a refresh for stale pairs (D3) | Fully-Automated | G-S8-1 `test_cache_only_mode_makes_zero_exchange_calls`, `test_stale_on_load_queues_refresh_and_board_reads_cache` | B |
| AC-S8-4 | start/stop with the app; off by env or cache-root override; status and refresh-now endpoints | Fully-Automated | G-S8-1 router and startup tests, G-S8-8 | B |
| AC-S8-5 | overnight run, 30-coin rate limits, restart, warm board under 10 s | Agent-Probe | P-S8-1 | C (stub if not run) |
| AC-S3-5 | real LSE response matches the parse | Agent-Probe | G-S3-6 + `lse_probe.py` | D (stub `lse-live-shape-verification_NOTE_03-10-26.md`); CONDITIONAL until run |

Legacy line form: S1 [Fully-automated: G-S1-1 command | hybrid: `s1-probe/probe_freshness.py` (live Hyperliquid egress on the user PC) | agent-probe: tail semantics, skew, board latency | known-gap: none once P-S1-1 ran]; S1/S2 web [Fully-automated: `pnpm --filter web test`, tsc, `pnpm build:islands` | agent-probe: island axis screenshot | known-gap: zoom/sharpness (S6)]; S2 [Fully-automated: G-S2-1 and G-S2-4 commands | hybrid: `cd web && pnpm test:e2e -- screener.spec.ts` (chromium + seeded stack) | agent-probe: chip vs exchange | known-gap: island label render until probed]; S3 [Fully-automated: G-S3-1 command | agent-probe: `lse_probe.py` on the user PC | known-gap: live LSE shape, stub `lse-live-shape-verification_NOTE_03-10-26.md`]; S8 [Fully-automated: G-S8-1 command | agent-probe: P-S8-1 on the user PC | known-gap: real rate-limit behaviour until P-S8-1 ran].

### S1 exact gates (repo root; expected results are for the EVL tester)

| Gate | Command | Expected |
|---|---|---|
| G-S1-1 | `UV_FROZEN=1 uv run --project api pytest api/tests/data/test_freshness.py api/tests/data/test_ccxt_tail_fetch.py api/tests/data/test_cache_fetched_at_retention.py api/tests/data/test_ccxt_clock_skew.py api/tests/routers/test_screener_freshness_payload.py -q` | 32 passed, 0 failed, 0 skipped (5+12+6+5+4) |
| G-S1-2 | `UV_FROZEN=1 uv run --project api pytest api/ -q` | 0 failed; at least 903 passed (870+32, +1 for the flipped deploy case); 1 skipped; 5 deselected; 0 xfailed |
| G-S1-3 | `pnpm --filter web test` | 223 passed in 30 files (S1 only edits fixtures) |
| G-S1-4 | `pnpm --filter web exec tsc --noEmit --incremental false` | exit 0, no output |
| G-S1-5 | `cd web && pnpm build:islands` | exit 0 (`built in`) |
| G-S1-6 | `git diff --check` | exit 0, no output |
| G-S1-7 | `S1-scope` in the command block below | prints nothing |
| G-S1-7b | `FORBIDDEN` in the command block below | prints nothing |
| G-S1-8 | `UV_FROZEN=1 uv run --project api pytest api/tests/deploy/test_fresh_deploy_degrade.py -q` | 11 passed, 0 xfailed (today: 10 passed, 1 xfailed) |
| G-S1-9 | `UV_FROZEN=1 uv run --project api pytest api/tests/data/test_cache_atomic_writes.py -q` | all passed, incl. `test_no_bypass` |
| G-S1-10 | `FIXTURES` in the command block below | prints nothing |
| G-S1-11 | red-first record: report heading 6 holds a G-S1-1 run on the untouched base naming at least `test_forming_candle_refresh_after_ttl`, `test_500_bar_gap_regression_catches_up`, `test_trim_on_write_15m_1h_4h_keeps_newest_200` as behavioural reds | present (tester reads the report) |
| P-S1-1 | user PC: `uv run --project api python process/general-plans/active/screener-batch1_03-10-26/s1-probe/probe_freshness.py` | (a) cache table with age and sidecar; (b) skew in seconds within 120 or `unknown`; (c) `since=None, limit=5` newest open within one timeframe of host now, and `since=3d ago, limit=5` returns the OLDEST bars after `since`; (d) board wall-clock seconds and live-call count |

### S2 exact gates (S1 merge SHA recorded as the base; counts below are relative to the S1-merged baseline recorded at step 1)

| Gate | Command | Expected |
|---|---|---|
| G-S2-1 | `UV_FROZEN=1 uv run --project api pytest api/tests/analytics/test_gain.py api/tests/routers/test_screener_gain_contract.py api/tests/routers/test_screener.py api/tests/analytics/test_momentum.py -q` | 0 failed; `test_gain.py` 11 and contract 2 passed; the removed golden test absent |
| G-S2-2 | `UV_FROZEN=1 uv run --project api pytest api/ -q` | 0 failed; passed = S1-merged baseline + 12 (13 new, 1 removed); 0 xfailed |
| G-S2-3 | `pnpm --filter web test` | 0 failed; 33 files (30 + `chart-time-format`, `chart-freshness`, `ChartFreshness`); `RelativePerformanceChart.test.tsx` unchanged and green |
| G-S2-4 | `TZ=Pacific/Kiritimati pnpm --filter web exec vitest run lib/__tests__/chart-time-format.test.ts` | 1 file passed |
| G-S2-5 | `pnpm --filter web exec tsc --noEmit --incremental false` | exit 0 |
| G-S2-6 | `cd web && pnpm build:islands` | exit 0 |
| G-S2-7 | `git diff --check` (exit 0) plus `S2-scope`, `FORBIDDEN` (S2 base = the S1 merge SHA's main) in the command block below | prints nothing |
| G-S2-8 | hybrid: `cd web && PLAYWRIGHT_CHROMIUM_PATH=/opt/pw-browsers/chromium-1194/chrome-linux/chrome pnpm test:e2e -- screener.spec.ts` | screener.spec.ts all passed; NOT-RUN with a stated reason is allowed (U-4) and then P-S2-1 covers it on the PC |
| G-S2-9 | `S2-dangling` in the command block below | prints nothing |
| G-S2-10 | `FIXTURES` in the command block below | prints nothing |
| P-S2-1 | user PC: (1) BTC 1h and 1d chip `pct`/`open_ts` from `curl "http://127.0.0.1:8000/api/screener/board?timeframe=1h"` vs the exchange chart's current candle open and last price; (2) screener and a drill-down show UTC ticks, the caption, and the `stale` marker after stopping the API | chip within rounding of the exchange candle; labels in UTC; marker appears |

### S3 exact gates

| Gate | Command | Expected |
|---|---|---|
| G-S3-1 | `UV_FROZEN=1 uv run --project api pytest api/tests/data/test_lse_adapter.py api/tests/data/test_equities_store.py -q` | 0 failed; exactly 1 skipped (`test_probe_fixture_parses`, only while the probe fixture is absent); adapter file 16 tests, store at least 6 |
| G-S3-2 | `UV_FROZEN=1 uv run --project api pytest api/ -q` (RT2, once) | 0 failed; skipped 2 (baseline 1 + the probe-fixture skip); xfailed 1 if S1 is not yet merged, else 0 |
| G-S3-3 | `git diff --check` | exit 0 |
| G-S3-4 | `S3-scope`, `FORBIDDEN`, `S3-gitignore` in the command block below | first two print nothing; third prints exactly `+api/data/equities.json` |
| G-S3-5 | `S3-key-grep` in the command block below | first: only `os.environ` reads; second: prints nothing; tester reads every `print(` in `lse_probe.py` and confirms no argument can carry the key, headers or a URL containing the key (hybrid review) |
| G-S3-6 | `UV_FROZEN=1 uv run --project api pytest api/tests/data/test_lse_adapter.py -q -k probe_fixture_parses -rs` on the real shape file | 1 passed (CONDITIONAL until run on the PC) |
| G-S3-7 | `git check-ignore api/data/equities.json api/data/cache/equities/AAPL/1d.parquet api/data/cache/equities/_probe/x.json` | prints all three paths, exit 0 |
| G-S3-8 | `S3-fixtures` in the command block below | only `lse_candles_synthetic.json`, optionally `lse_candles_probe_shape.json`, and the `s3-probe` script and README; no raw probe output |
| G-S3-9 | `S3-secret-scan` in the command block below | prints nothing |

### S8 exact gates (S1 merge SHA recorded as the base; counts relative to the S1-merged baseline)

| Gate | Command | Expected |
|---|---|---|
| G-S8-1 | `UV_FROZEN=1 uv run --project api pytest api/tests/data/test_refresh_worker.py api/tests/routers/test_refresh_router.py api/tests/deploy/test_refresh_startup.py -q` | 18 passed, 0 failed, 0 skipped (12+3+3) |
| G-S8-2 | `UV_FROZEN=1 uv run --project api pytest api/ -q` | 0 failed; passed = S1-merged baseline + 18; skipped/deselected/xfailed unchanged |
| G-S8-3 | `pnpm --filter web test` | 0 failed; same counts as the S1-merged baseline (S8 edits no web file) |
| G-S8-4 | `pnpm --filter web exec tsc --noEmit --incremental false` | exit 0 |
| G-S8-5 | `cd web && pnpm build:islands` | exit 0 |
| G-S8-6 | `git diff --check` | exit 0, no output |
| G-S8-7 | `S8-scope` and `FORBIDDEN` in the command block below | print nothing |
| G-S8-8 | `UV_FROZEN=1 uv run --project api pytest api/tests/deploy api/tests/routers/test_board_integration.py api/tests/routers/test_screener.py -q` | 0 failed (existing deploy, CORS, health, real-data-guard and board tests unaffected) |
| G-S8-9 | `FIXTURES` in the command block below | prints nothing |
| P-S8-1 | user PC: the four checks in the S8 section | status shows ticks about every 15 min; no sustained backoff at 30 coins; restart serves cache at once; warm board under 10 s |

### Scope and secret-hygiene commands (run from the repo root; the labels above refer to these)

```
# FORBIDDEN (every slice): nothing may match
git diff --name-only origin/main...HEAD | grep -E '^(CLAUDE\.md|AGENTS\.md|README\.md|\.claude/|\.github/|deploy/|api/scripts/|process/MASTER-PLAN\.md|process/context/current-state\.md|process/archive/)'
# (api/scripts/ is forbidden to every slice)

# FIXTURES: no modified, deleted or renamed fixture (adds are allowed)
git diff --name-only --diff-filter=MDR origin/main...HEAD | grep -E '/fixtures/'

# S1-scope: every changed file must be on the owned list (prints the strays)
git diff --name-only origin/main...HEAD | grep -vE '^(api/data/(ccxt_adapter|cache|freshness)\.py|api/models/screener\.py|api/analytics/screener_board\.py|web/lib/types/screener\.ts|api/tests/data/(test_freshness|test_ccxt_tail_fetch|test_cache_fetched_at_retention|test_ccxt_clock_skew|test_ccxt_symbol_resolution)\.py|api/tests/routers/test_screener_freshness_payload\.py|api/tests/deploy/test_fresh_deploy_degrade\.py|web/components/screener/__tests__/(ScreenerBoard|DrillDownView)\.test\.tsx|process/general-plans/active/screener-batch1_03-10-26/(s1-probe/.*|screener-batch1-s1_REPORT_[0-9-]+\.md)|process/general-plans/backlog/ohlcv-negative-cache-and-1d-gap-replace_NOTE_[0-9-]+\.md)$'

# S2-scope
git diff --name-only origin/main...HEAD | grep -vE '^(api/analytics/indicators/(gain|momentum)\.py|api/analytics/screener_board\.py|api/models/screener\.py|web/lib/types/screener\.ts|web/lib/(chart-time-format|chart-freshness|island-loader)\.ts|web/islands/simple-lines\.svelte|web/components/chart/(MiniChart|ChartFreshness)\.tsx|web/components/screener/(CoinPanel|DrillDownView|ScreenerBoard)\.tsx|api/tests/analytics/(test_gain|test_momentum)\.py|api/tests/routers/(test_screener_gain_contract|test_screener)\.py|web/lib/__tests__/(chart-time-format|chart-freshness)\.test\.ts|web/components/chart/__tests__/ChartFreshness\.test\.tsx|web/components/screener/__tests__/(ScreenerBoard|DrillDownView)\.test\.tsx|web/e2e/screener\.spec\.ts|process/general-plans/active/screener-batch1_03-10-26/screener-batch1-s2_REPORT_[0-9-]+\.md|process/general-plans/backlog/island-axis-labels-render-check_NOTE_[0-9-]+\.md)$'

# S2-dangling: the deleted functions and constant are gone everywhere
grep -rn -e compute_percent_change -e PCT_CHANGE_MIN_BARS api/analytics api/routers api/tests api/scripts

# S8-scope
git diff --name-only origin/main...HEAD | grep -vE '^(api/data/(ccxt_adapter|refresh_worker)\.py|api/routers/(refresh|screener)\.py|api/main\.py|api/tests/conftest\.py|api/tests/data/test_refresh_worker\.py|api/tests/routers/test_refresh_router\.py|api/tests/deploy/test_refresh_startup\.py|process/general-plans/active/screener-batch1_03-10-26/(s8-probe/.*|screener-batch1-s8_REPORT_[0-9-]+\.md))$'

# S3-scope
git diff --name-only origin/main...HEAD | grep -vE '^(api/data/(lse_adapter|equities_store)\.py|api/tests/data/(test_lse_adapter|test_equities_store)\.py|api/tests/data/fixtures/lse_candles_(synthetic|probe_shape)\.json|\.gitignore|process/general-plans/active/screener-batch1_03-10-26/(s3-probe/.*|screener-batch1-s3_REPORT_[0-9-]+\.md)|process/general-plans/backlog/lse-live-shape-verification_NOTE_03-10-26\.md)$'

# S3-gitignore: exactly one added line
git diff origin/main...HEAD -- .gitignore | grep '^[+-][^+-]'

# S3-key-grep
grep -n "LSE_API_KEY" process/general-plans/active/screener-batch1_03-10-26/s3-probe/lse_probe.py api/data/lse_adapter.py
grep -nE "print\(|logging|logger|sys\.std(out|err)" api/data/lse_adapter.py

# S3-fixtures
git ls-files | grep -iE 'lse_(candles|probe)'

# S3-secret-scan
git diff origin/main...HEAD | grep -nE '^\+.*Bearer [A-Za-z0-9._-]{12,}'
git diff origin/main...HEAD | grep -nE '^\+.*LSE_API_KEY *=[^=]*[A-Za-z0-9]{8,}'
```

### Failing stubs

Each Fully-Automated test named in the slice "Tests (names)" lists is the red-first start: the worker creates it first as `def test_x(): raise NotImplementedError("NOT IMPLEMENTED - TDD stub: <behaviour>")` (vitest: `throw new Error("NOT IMPLEMENTED - TDD stub: ...")`), runs the slice's first gate on the untouched base, records the red run in report heading 6, then replaces each stub with the real test. Stubs are never committed as passing. `test_probe_fixture_parses` is Agent-Probe (skipif): no stub.

### Red-today evidence (origin/main af7888f; scratch scripts only, nothing committed)

| Criterion | Red today? | Evidence |
|---|---|---|
| AC-S1-1 | RED (behaviour) | 1h cache with a forming newest bar: 0 exchange calls (base `_cache_is_fresh` true inside the bar) |
| AC-S1-2 | RED (behaviour) | 15m cache 6 days behind: one call `(since=<cached max>, limit=500)`; cache still 76 bars behind afterwards |
| AC-S1-3 | RED (behaviour) | a 500-bar 15m pull kept 500 bars |
| AC-S1-4/5/6 | RED (missing symbols) | `api.data.freshness` absent; `ChartSeries` fields are `[available, price, reason, sma]`; no `_now`, `last_clock_skew`, `read_fetched_at`; `OhlcvResult` has 5 fields |
| AC-S1-5 over HTTP | RED today | `pytest api/tests/deploy/test_fresh_deploy_degrade.py --runxfail -k staleness_marker` fails: "an aged cache is displayed with no staleness marker" |
| AC-S2-1/2 | RED (value / module) | golden Mon 28 Sep - Thu 1 Oct: expected 1w +6.0%; base returns 1w `None` and 1d `3.92`; `gain.py` absent; `test_screener.py:205` thin-slot test is green today and stays green |
| AC-S2-3/4 | RED (modules absent) | `chart-time-format.ts`, `chart-freshness.ts`, `ChartFreshness.tsx` do not exist |
| AC-S2-6 | GREEN today, RED after S2 without the E2E edit | seeded THIN 1d chip becomes +0.032%, rendered "+0.0%", matching the old regex |
| AC-S3-1..4 | RED (modules absent) | `lse_adapter.py`, `equities_store.py` absent; `api/data/equities.json` not ignored |
| AC-S8-1..4 | RED (modules absent) | `refresh_worker.py`, `routers/refresh.py`, `cached_reads_only` absent; board fetches inline |
| AC-S1-2r, 6r, AC-S2-3r, 5, AC-S3-5, AC-S8-5 | NOT-RUN | live exchange, vendor or browser |

### Unverified facts: owner and deterministic fallback

| # | Fact | Status after VALIDATE | Owner | Fallback |
|---|---|---|---|---|
| U1 | ccxt `since=None` returns the LATEST bars | request level VERIFIED offline (probe 1); response level (what Hyperliquid returns, any server cap) unverified | P-S1-1 (c) | B3 `_tail_since` helper; `stale` status makes a wrong assumption visible |
| U2 | `fetch_time` works on Hyperliquid | method and capability flag exist (probe 2); runtime result and latency unverified | P-S1-1 (b) | missing or failing = unknown, no warning (tests exist) |
| U3 | LayerChart `Axis` `format` on a `scaleUtc` bottom axis | unverifiable offline (node_modules blocked to scouts; island not mountable in jsdom; `build:islands` compiles Svelte but does not type-check props; no precedent of `scaleUtc` in the repo; `d3-scale` v4 exports it per its public API, not confirmed locally) | S2 Design 6 spike plus screenshot, then P-S2-1 (2) | 3-step chain in S2 Design 6; DOM captions and `stale` marker ship regardless |
| U4 | LSE REST paths, auth scheme, timestamp hour, weekly support | ASSUMED from the SDK | `lse_probe.py` (Step 0, user PC) | adapter against the documented shape with an injectable transport and isolated URL/auth constants; AC-S3-5 stays CONDITIONAL with the stub |
| U5 | The S8 worker is safe with the single exchange singleton and survives an API restart on the PC | designed (serial `_exchange_lock`, tests with fakes); real behaviour unverified | P-S8-1 | `SCREENER_REFRESH_WORKER=0` disables it; S1 fetch-through remains |

### Cycle-2 re-validation record

**Plan HEAD c245f14 against origin/main af7888f (the branch differs from main only under `process/`, so the code under test is main); one agent ran V1-V3 by direct reads and runs, confidence MEDIUM-HIGH, no source changed.** `validate-plan-artifact.mjs`: 0 failures, 0 warnings. Re-run baselines: pytest 870 passed, 1 skipped, 5 deselected, 1 xfailed (198 s); vitest 223 passed in 30 files; tsc exit 0; `pnpm build:islands` exit 0; the `TZ=Pacific/Kiritimati ... vitest run <file>` form works. G-S1-8 today: 10 passed, 1 xfailed; with `--runxfail` the staleness-marker case fails on "an aged cache is displayed with no staleness marker" (red-today confirmed). The scope and hygiene commands FORBIDDEN, FIXTURES, S8-scope, S3-gitignore, `git diff --check`, S2-dangling and G-S3-7 `git check-ignore` all execute (on the plan branch they list only `process/` files: Gate convention 6; G-S3-7 prints all three paths, rc 0). Cited anchors verified for S1 (`ccxt_adapter.py:173-184, 354-355, 371-374`, `cache.py:79-139`, `test_cache_atomic_writes.py:161` `test_no_bypass`, interrupted-write cases with `_temps == []`), S2 (`screener_board.py:134-146`, `momentum.py:32, 113-133`, `test_momentum.py:17, 171-179`, `test_screener.py` chip tests, `simple-lines.svelte:63, 71-72`, `screener.spec.ts:141-157`, `web/lib/api/screener.ts:13`), S3 (`all-data-sources.md`, `.gitignore:18`, `httpx`/`pyarrow` dependencies), S8 (`main.py` module-level `app` with no lifespan, `routers/screener.py`, `refresh_cache.py:44-97`, `conftest.py`, `SCREENER_CACHE_ROOT` at `cache.py:34`, `ccxt_adapter.py:96-131` lock and exchange singleton, `test_seed_onchain_fixture.py:113` the only `with TestClient(app)`). Scratch red-today runs (nothing committed): a 1h cache whose newest bar is the current hour causes 0 exchange calls; a 500-bar 15m pull keeps 500 bars; `OhlcvResult` has 5 fields; after one failed `load_markets()` a recovered exchange still answers `unavailable` until `reset_exchange_cache()` (N1). S3 NYSE rule set (Design 3) implemented in a scratch script: every plan golden plus 12 further known NYSE closures and 5 open days match, 0 mismatches; the `USFederalHolidayCalendar` trap reproduced (it observes 2010-12-31); the five SPY dates are Saturdays; Good Friday via `dateutil.easter` (a pandas dependency, no `pyproject.toml` change). ccxt 4.5.78: `has['fetchTime']` True, `timeout` 10000 ms, `rateLimit` 50.

**File-disjointness (scope regexes of the command block run over every owned file):** S2 and S8: disjoint (no common file). S1 and S8 share only `api/data/ccxt_adapter.py` (sequential by design: S8 starts after the S1 merge SHA and builds on its `fetch_ohlcv`, `OhlcvResult`, `freshness`). S1 and S2 share `api/models/screener.py`, `api/analytics/screener_board.py`, `web/lib/types/screener.ts` and the two web test fixtures (sequential). S3 is disjoint from all three. S8 needs no edit to `screener_board.py`: `routers/screener.py` wraps `build_screener_board`, `build_scalp_view` and `build_relative_performance` in the context, so the board's own `fetch_ohlcv` calls (lines 134-143, 202-203, 229) and `leg_boundary.py:164` run inside it.

**S8 design review:** live calls serialize on `_exchange_lock` (RLock, `ccxt_adapter.py:96`), so the 4-thread pool adds no live concurrency; the `ContextVar` flag is set per request thread (FastAPI sync endpoints run in the thread pool) and `ThreadPoolExecutor` workers do not inherit it, so refresher fetches stay live; the per-pair non-blocking lock covers refreshers only, so a request-time fetch-through on the same file by a non-wrapped consumer (pairs router, hand-run `refresh_cache.py`) is last-writer-wins with atomic parquet and sidecar writes (unique `mkstemp` names), the plan's residual risk 6; the lifespan runs on the event loop but the worker is a daemon thread, and `stop()` must join with a short timeout (it blocks the loop at shutdown). Cold cache: first tick 20 s after start, so the board shows `unavailable` until its pairs are fetched (1-3 minutes [estimate]); reacting to a page load before that needs N4. Offline or sandbox start: N1. Determinism: fake clock and fake exchange are injected, so no network and no sleeping, provided rate-limit tests use `NetworkError` or set `BACKOFF_BASE_SECONDS` to 0 (N5). `GET /api/refresh/status` carries all nine requested fields. `deploy/**` and `api/scripts/**` are in no owned list (S8-scope and FORBIDDEN gates). The seeded E2E (G-S2-8) runs with a redirected cache root, so the worker is off and S1 fetch-through applies: after a seeded bar's TTL a board request may try a live `load_markets` through the egress proxy in the cloud container (G-S2-8 may be NOT-RUN with a reason, U-4).

**Budgets:** S1 2-5, S2 3-6, S3 1-2, S8 3-6 USD [estimates, plan text], total 9-19; every slice is under the 15 USD per-slice cap and uses at most 2 subagents (one `vc-tester`, one read-only reviewer) against the cap of 3, one level; 9-19 leaves 26-36 USD of the 45 USD program ceiling for S4-S7, S9, S10 (INNOVATE: 16-36 [estimate]), so the ceiling may bind and is re-checked after S2 and S8, as the plan says. The N1/N4 fixes add two small tests to S8 (inside its estimate).

### Cycle-2 findings (new defects; none is a FAIL)

| id | slice | severity | defect and evidence | fix route |
|---|---|---|---|---|
| N1 | S8 | CONCERN | `api/data/ccxt_adapter.py:98, 110-123`: a failed `load_markets()` latches `_markets_unavailable` for the whole process ("retry happens on the next process start"). The worker's backoff (Design 2) can never reach a success, so one offline start, or one 10 s timeout at the 20 s first tick (the plan measures a 12.5 s cold `load_markets`), stops refreshing until the API restarts. `reset_exchange_cache()` (126-131) exists. Reproduced with a scratch script. | S8 Design 2: at the start of each tick, if the latch is set, retry the market load once (new `retry_markets_if_latched()` in `ccxt_adapter.py`, or `reset_exchange_cache()`); the per-fetch latch stays, so `test_load_markets_failure_is_latched_not_retried_per_fetch` (`test_ccxt_symbol_resolution.py:164`) stays green; add `test_markets_latch_retried_once_per_tick_and_backoff_resets` (AC-S8-2). |
| N2 | S1 | CONCERN | `api/tests/data/test_ccxt_symbol_resolution.py:189-211` `test_weekly_recursion_does_not_deadlock` asserts `status in ("ok", "unavailable")` after a fetch whose only bar is `_BAR` (2023-11-14, line 36); B3 turns that into `stale`, so G-S1-2 fails, and the S1 edit allowance for this file is one test only. Predicted from B3 (S1 code is absent), not run. | S1 Owned: also allow that one assertion to accept `stale` (same file, already in the S1-scope regex); record it in report heading 9. |
| N3 | S1 | CONCERN | B3 does not scope the `stale` status to the `since=None` path. `api/scripts/backfill_pairs_universe.py:97` treats `status != "ok"` as failure and `api/tests/scripts/test_backfill_pairs_universe.py:18-19` feeds bars about May 2024 (far older than the 2 x 1d threshold): an unscoped `stale` breaks that test (not owned; `api/scripts/**` is forbidden) and real backfills of delisted coins. | B3: `stale` is assigned only on the `since=None` path; the explicit-`since` path keeps returning `ok`; add an old-newest-bar assertion to `test_explicit_since_path_unchanged_for_backfill`. |
| N4 | S8 | CONCERN | Design 1, 3 and 4 queue refresh requests (`request_refresh`, `POST /api/refresh/now`) but name no consumer between ticks (the loop sleeps up to 900 s): the load-triggered refresh (D3), a coin just added to the watchlist, and `/now` would all wait for the next tick. `/now` with the worker off has no defined answer (a 202 would be false). "Stale or missing" is undefined for the queue trigger. | S8 Design 1, 3, 4: the loop waits on an `Event` with the delay as timeout and is woken by `request_refresh` and `/now`; a woken run drains the queue with the same locks and pool; trigger = `not freshness.cache_is_fresh`; `/now` with the worker off returns 503 `worker-not-running` and the status shows `running: false`; add `test_now_and_load_requests_wake_the_loop_without_sleeping` (fake clock, wake `Event`). With N1: worker file 14 tests, G-S8-1 20 passed (14+3+3), G-S8-2 baseline + 20. |
| N5 | S8 | advisory | B9 turns the worker off whenever `SCREENER_CACHE_ROOT` is set; `deploy/start-api.ps1:24` sets it from the optional `CacheRoot` (README: leave empty), so an operator who sets it silently gets no worker, and `test_lifespan_starts_and_stops_worker` cannot run under a redirected root. `api/tests/conftest.py` has no `import os` (the "one line" is two). | Tri-state `SCREENER_REFRESH_WORKER`: `0` off, `1` forces on even with a root override, unset = on unless the root is overridden; status shows `disabled_reason`; fold the `import os` and the no-sleep test rule (use `NetworkError` or `BACKOFF_BASE_SECONDS = 0`, as `test_adapter_contracts.py` does) into S8 Owned and Design. |
| N6 | S3 | advisory | The plan says the LSE verdict and findings exist only on `origin/claude/exciting-meitner-hy50kn`; they are on origin/main at `process/general-plans/completed/lse-data-verification_17-09-26/VERDICT.md` and `findings.md` (row shape at `findings.md:18`). The cited `all-data-sources.md:225-252` misses the LSE row (line 221): use 219-252. 2007-01-02 (Ford day of mourning) lies inside a 5000-row window but is absent from the special-closures caveat. | Fix the sentence, the range and the caveat list. |
| N7 | S2 | advisory | G-S2-9 greps `api/analytics api/routers api/tests api/scripts` without `--include`, so `__pycache__/*.pyc` print `binary file matches` (3 lines today). | Add `--include='*.py'` to the S2-dangling command. |

### Dimension findings (cycle 2)

- Infra fit: CONCERN - S8 N1, N4 (lifespan, daemon thread, env flags and `SCREENER_CACHE_ROOT` handling fit the module-level `app`, single-process uvicorn launcher and `_exchange_lock`); S2 and S3 fit.
- Test coverage: CONCERN - N2 (unowned test break); all gate commands exist and run, exact-gate tables carry expected outputs, red-today evidence is reproduced per slice; S8 tests are deterministic by design once N5's no-sleep rule is applied.
- Breaking changes: CONCERN - N3; every other consumer verified: fakes build `OhlcvResult` with 5 arguments (`test_relative_performance.py:39`, `test_screener.py:84`, `test_screener_integration.py:62`), so appended defaulted fields are safe; no test constructs `ChartSeries`, `CoinPanel` or `ScreenerBoardResponse`; web consumers of the changed types are the two owned fixtures; the sidecar design is compatible with `test_no_bypass`, the interrupted-write cases (temp removed on exception) and `_derive_weekly_from_daily`; `percent_change_by_timeframe` users are `test_screener.py`, `test_momentum.py`, `ScreenerBoard.test.tsx`, `CoinPanel.tsx`, `screener.spec.ts` (all owned by S2).
- Security surface: PASS - S3 key header-only, sentinel and synthetic-fixture tests, secret-scan gates run; S8 `POST /api/refresh/now` is unauthenticated on a Tailscale-only API, accepts no body, allows one pending run and logs no values; no slice edits `deploy/**` or `api/scripts/**`.
- S1 feasibility: CONCERN (N2, N3). S2 feasibility: PASS (N7 advisory; U3 spike chain has a deterministic fallback). S3 feasibility: PASS (N6 advisory; CONDITIONAL on the live probe, U-2). S8 feasibility: CONCERN (N1, N4; N5 advisory).
- Unverified facts (ccxt `since=None` response, `fetch_time`, LayerChart `Axis` format on `scaleUtc`, LSE REST paths and auth): each has a named PC probe or spike and a deterministic fallback (table below); U5 (worker with the exchange singleton) has P-S8-1 and `SCREENER_REFRESH_WORKER=0`.

### Envelope line ranges and size room (as of this verdict; supplement cycle 2 will shift lines, so re-derive with `grep -n '^## \|^### '` at spawn time)

The plan is 91,363 B after this cycle-2 record (76,248 B before it), over the 36,000 B worker entry cap, so each envelope cites line ranges. CLAUDE.md is 13,443 B, so the room left for the envelope is 36,000 - 13,443 - plan bytes (cap 8,000 B). Ranges below are current lines of this file.

| Slice | Plan ranges (lines) | Plan bytes | Max envelope bytes |
|---|---|---|---|
| S1 | 38-43 (B1-B6), 48-55 (conventions), 65-95 (S1), 280-294 (legend, header, S1 rows), 315-331 (S1 exact gates), 381-383 (FORBIDDEN), 385-386 (FIXTURES), 388-389 (S1-scope), 418-420 (stubs) | 17,277 | 5,280 (must stay under this) |
| S2 | 44-45 (B7-B8), 48-55, 97-127 (S2), 280-283, 295-301 (S2 rows), 333-347 (S2 exact gates), 381-383, 385-386, 391-392 (S2-scope), 394-395 (S2-dangling), 418-420 | 13,774 | 8,000 (cap; room 8,783) |
| S3 | 48-55, 129-157 (S3), 280-283, 302-305 and 311 (S3 rows), 349-361 (S3 exact gates), 381-383, 385-386, 400-416 (S3 scope, gitignore, key grep, fixtures, secret scan), 418-420 | 13,743 | 8,000 (room 8,814) |
| S8 | 41-42 (B4-B5), 46 (B9), 48-55, 73 (S1 frozen list), 78 (S1 design item 3), 159-186 (S8), 280-283, 306-310 (S8 rows), 363-376 (S8 exact gates), 381-383, 385-386, 397-398 (S8-scope), 418-420 | 14,051 | 8,000 (room 8,506) |

Adding the "Cycle-2 findings" rows that touch a slice (N1-N5 for S8, N2-N3 for S1) after the plan agent has folded them into the slice sections costs those slices roughly 1,000-1,500 B more: S1's envelope room then drops to about 4,000 B, so the S1 envelope must stay short (a pointer list, no pasted plan text), or the planner trims B1-B6 to the clauses S1 needs.

### Cycle-2 SUPPLEMENT REQUEST (for the plan agent; each id is a `##` heading slug)

- Gap 1 (N1): Section s8-in-process-background-refresh-worker-rt3-capped-subagent-lane-yes, Design 2 | latch retry once per tick, no per-fetch retry | new test | CONCERN.
- Gap 2 (N4): same section, Design 1, 3, 4 | wake `Event`, queue drain, trigger definition, `/now` 503 when off | new test, counts 14 and 20 | CONCERN.
- Gap 3 (N2): Section s1-freshness-core-rt3-capped-subagent-lane-yes, Owned | allow `test_weekly_recursion_does_not_deadlock` to accept `stale` | CONCERN.
- Gap 4 (N3): Section decisions-locked-for-this-batch (B3) and S1 tests | `stale` only on `since=None`; old-bar assertion in `test_explicit_since_path_unchanged_for_backfill` | CONCERN.
- Advisories to fold in the same pass: N5 (S8 env tri-state, `import os`, no-sleep rule, `disabled_reason`), N6 (S3 sentence, range 219-252, 2007-01-02 caveat), N7 (S2-dangling `--include='*.py'`); update the Test gates rows AC-S8-2, AC-S8-3, AC-S8-4 and G-S8-1/G-S8-2 counts, and the Resume section.

### Not verifiable offline

Live Hyperliquid and LSE; LayerChart label rendering; chip vs exchange chart; GitHub CI; every new test; the S8 worker against the real exchange, overnight and across an API restart on the Windows PC; the S1 and S8 behaviour of the real `since=None` response, `fetch_time` and 30-coin rate limits; the E2E (G-S2-8) in the cloud container.

### What this coverage does NOT prove

- G-S1-1/2 and G-S8-1 use fake exchanges and clocks: they prove our tail, TTL, trim, skew and worker logic, NOT that Hyperliquid returns the latest bars for `since=None`, that `fetch_time` works, nor real latency, rate limits or overnight stability (P-S1-1, P-S8-1).
- G-S1-8 proves the aged-cache marker through FastAPI with a dead exchange stub, not a live feed.
- Web gates prove types, jsdom behaviour and that the island compiles; jsdom never mounts the island, so they do NOT prove labels are drawn or in UTC on screen, nor zoom or sharpness (S6).
- G-S2-1 proves chip arithmetic on synthetic frames, NOT agreement with the exchange chart (P-S2-1). G-S2-8, when run in a container, uses seeded bars.
- G-S3-1 uses a synthetic fixture and a mock transport: it proves parsing, filtering, tagging and key hygiene, NOT the real LSE shape, auth scheme, timestamp hour or weekly support (G-S3-6, P-S3-1); special closures and corporate actions are not modelled.
- None of the gates prove behaviour with the user's real cache files beyond the P-S1-1 listing.

### Open gaps

U1/U2 pending P-S1-1; U3 and AC-S2-5 pending P-S2-1; AC-S3-5 pending the LSE probe; AC-S8-5 pending P-S8-1. known-gap: live LSE end-to-end: documented as NEW PLAN REQUIRED - see backlog/lse-live-shape-verification_NOTE_03-10-26.md. known-gap: island axis label render: documented - see backlog/island-axis-labels-render-check_NOTE_<dd-mm-yy>.md (only if the S2 spike reaches fallback 3). Cycle 2: N1-N4 above are plan gaps awaiting supplement cycle 2 (not known-gaps).

Accepted by: the user (decisions 03-10-26, relayed by the coordinator): U-1 S1/S2 may merge after the offline gates and stay at `review` until the PC probes; U-2 S3 stays CONDITIONAL until the live probe passes, accepted as RT2 plus the secret-hygiene gates; U-3 amendments folded into the slice sections (done in this cycle); U-4 hybrid E2E is acceptable, NOT-RUN with a stated reason is allowed; U-5 S8 pulled into batch 1, client timeout unchanged. The cycle-2 re-VALIDATE has run (verdict above). The user-accepted items cover only the live-probe conditions (AC-S1-2r/6r, AC-S2-3r/5, the AC-S2-6 run, AC-S3-5, AC-S8-5: U-1, U-2, U-4); they do not cover N1-N4, which need plan fixes, so the gate stays CONDITIONAL and the PASS stamp is not given.

Mechanics: `results.tsv` has header, baseline, supplement cycle 1 and re-VALIDATE cycle 2 rows; report `screener-batch1-pvl-iteration-001_REPORT_03-10-26.md` (the iteration-002 report is written by the orchestrator at the cycle boundary, vc-autoresearch Boundary).

## Autonomous Goal Block

SESSION GOAL: screener batch 1 - S1 freshness core, S2 chips and UTC labels, S3 LSE equities adapter (live shape pending probe), S8 background refresh worker
Charter + umbrella plan: N/A - single plan (no umbrella exists)
Autonomy: after re-VALIDATE and the user's EXECUTE approval the planner writes four envelopes (master-planner.md section 8, at most 8,000 bytes, citing line ranges) and spawns S1 and S3 (opus; subagents sonnet, capped lane for S1, S2, S8); S2 and S8 only after the S1 merge SHA exists; workers run gates once after the last edit and stop on the same failure twice.
Hard stop conditions / safety constraints:
- No envelope or worker before the re-VALIDATE verdict and the user's approval.
- S2 and S8 never before the S1 merge SHA; S1 is not deployed to the PC before S8 merged; S3 never touches `cache.py`, `ccxt_adapter.py`, `pyproject.toml`, `uv.lock`; no slice touches `deploy/**` or `api/scripts/**`.
- A diff touching CLAUDE.md, AGENTS.md, README.md, `.claude/`, `.github/`, `deploy/` stops at `review`.
- The LSE_API_KEY value is never printed, logged, committed or written; no real LSE price is committed.
- Push, merge, deploy, branch deletion or spend above 15 USD per slice or 45 USD in total needs the user's approval.
Next phase: re-VALIDATE (vc-validate-agent from V1), then EXECUTE - plan path process/general-plans/active/screener-batch1_03-10-26/screener-batch1_PLAN_03-10-26.md
Validate contract: the section above, inline (CONDITIONAL, supplement cycle 1 applied)
Execute start: S1: `UV_FROZEN=1 uv run --project api pytest <G-S1-1 files> -q` red run on the untouched base, then implement; S3: commit `s3-probe/` first; probes P-S1-1, P-S2-1, P-S8-1, `lse_probe.py` | high-risk pack: no (U-2)

## Resolved questions (user, 03-10-26)

1. 1d is NEVER trimmed (amends D5): only 15m/1h/4h are trimmed to about 200 bars; daily stays 500+ so weekly RSI(14) and BTC legs are well-founded.
2. S3 does NOT add `lse-data`: plain HTTP calls; `api/pyproject.toml` and `api/uv.lock` stay untouched.
3. No real LSE prices are ever committed; fixtures hold synthetic prices only; real data stays local and git-ignored.
4. U-1..U-5 as listed under "Accepted by" above; U-5 means S8 is in batch 1 and S1 does not change the web client timeout.

## Worker envelopes

Written AFTER re-VALIDATE and the user's approval (not now): one per slice, at most 8,000 bytes, saved as `screener-batch1-s{1,2,3,8}_REF_<dd-mm-yy>.md` in this task folder, using the master-planner.md section 8 template (branches `claude/<task-id>-<slug>`, ids assigned at registration). S2's and S8's envelopes are issued only after the S1 merge SHA exists.

## Test Infra Improvement Notes

(none identified yet) Candidates: a shared fake-exchange module (`FakeExchange`, `StubExchange`, `_DailyExchange`); `lse_adapter` in the shared adapter-contract test note; jsdom never mounts the Svelte islands.

## Resume and Execution Handoff

1. Selected plan file: `process/general-plans/active/screener-batch1_03-10-26/screener-batch1_PLAN_03-10-26.md`
2. Last completed step: PVL supplement cycle 1 (amendments folded, S8 added, 03-10-26).
3. Validate-contract status: written 03-10-26, CONDITIONAL; supplement applied, awaiting re-VALIDATE.
4. Context loaded: SPEC, INNOVATE, findings note, operating-instructions.md, master-planner.md, decisions.md, all-tests.md, `api/main.py`, `refresh_cache.py`, deploy tests.
5. Next step for a fresh agent: run vc-validate-agent from V1 on this plan (it must also validate S8); after the verdict and the user's explicit approval write the four envelopes and spawn S1 and S3 (S2 and S8 after the S1 merge). Next instruction (RIPER-5): say **ENTER VALIDATE MODE**.
