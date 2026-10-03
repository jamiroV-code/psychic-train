---
name: plan:screener-batch1
description: "Screener realignment batch 1: S1 freshness core (cache TTL, tail fetch, trim, staleness, payload fields), S2 current-candle chips plus UTC chart labels, S3 LSE equities adapter (probe-first). Slices S4-S10 listed as later batches"
date: 03-10-26
feature: general-plans
---

# Screener Batch 1: Freshness, Chips and Equities Adapter (S1, S2, S3)

Date: 03-10-26
Status: PLANNED. VALIDATE pending; no EXECUTE approval; worker envelopes not written.
Complexity: COMPLEX (S1 then S2 sequential, S3 parallel; RT3 shared cache, models, adapters)

**TL;DR:** Charts and chips show stale or wrong numbers: the forming candle counts as fresh until it closes, and a cache over 500 bars behind never catches up. S1 fixes the data layer and adds freshness fields to the API. S2 builds correct chips and UTC labels on top. S3 builds the LSE equities adapter in parallel, probe-first. Estimate 5-12 USD [estimate]. One decision differs from INNOVATE: 1d bars are NOT trimmed to 200 (B2).

Sources: SPEC `personal-tracker-realignment_SPEC_02-10-26.md` (D1-D11, F1-F5), its INNOVATE doc, `process/general-plans/backlog/screener-research-findings_NOTE_03-10-26.md`, decisions.md D-14, master-planner.md 4-6, operating-instructions.md (RT tiers), `process/context/tests/all-tests.md` (baseline at `753db23`: pytest 873 passed, vitest 223; workers re-record). Router: `process/context/all-context.md`.

Context Envelope: general-plans | PLAN | batch 1 | claude/pensive-albattani-ou0cgv | /home/user/psychic-train | tests, data-sources | api/data, api/models, api/analytics, web/lib, web/components, web/islands | this file | pytest then vitest | contract pending.

## Overview

Goal: true, current, labelled screener data, and a tested equities adapter. Scope: S1, S2, S3. Non-goals: verdict removal, layout, zoom/pan, spaghetti, BTC leg chart, refresh worker, equities page, scheduled task (S4-S10).

## Name check against the INNOVATE doc (real code read 03-10-26)

| INNOVATE / SPEC says | Actual code | Plan consequence |
|---|---|---|
| S1 = `ccxt_adapter.py`, `cache.py` + tests; SPEC cites `_cache_is_fresh` ~179-191, cache-first ~352 | `_cache_is_fresh` is `ccxt_adapter.py:173-184`, cache-first return 354-355, the gap bug is the incremental `effective_since` at 371-374. The payload also needs `api/models/screener.py`, `screener_board.py`, `web/lib/types/screener.ts` | S1 owns those plus a new pure `api/data/freshness.py` |
| S2 file = `momentum.py` | `compute_percent_change` (113-123) and `compute_percent_change_by_timeframe` (126-133) are used only at `screener_board.py:146`; the verdict code in the same file is S4's | new chip logic in new `api/analytics/indicators/gain.py`; S2 only deletes the two functions and `PCT_CHANGE_MIN_BARS` from `momentum.py` |
| B: trim every timeframe to ~200 | `1d` feeds pairs (`compute_pairs.py`, `pairs_response.py:156`), BTC legs (`leg_boundary.py:164`) and the deep backfill (`backfill_pairs_universe.py:92`) | trim 15m/1h/4h only (B2) |
| `fetch_time` at `hyperliquid.py:117/420-431` | `api/.venv` is blocked for scouts by the scout hook; ccxt source not readable | unverified; the S1 probe confirms on the PC; code treats a missing or failing `fetch_time` as "unknown" |
| LSE adapter "`api/data` lse*" | no `lse-data` in `api/pyproject.toml`; the harness uses the SDK, which the user ruled out (Resolved 2) | new `lse_adapter.py`, `equities_store.py`; plain `httpx` HTTP |
| contract-sync `test_screener_integration.py:141` | class at 127, method 141; checks only `ConfidenceState` | S1 adds a NEW contract-sync file; S4 changes the old one |
| D5 "~28 weekly bars enough" | Wilder RSI keeps weight (13/14)^k of its seed: 28 weekly bars leave 35%, 72 bars (500 daily) 1.4%, under 1% needs 76+ | keep 500+ daily bars; RSI(14) first value needs 15 closes, stable needs 76+ |

## Decisions locked for this batch

- **B1 fetched_at storage: sidecar, one per (symbol, timeframe).** `cache/ohlcv/<SYM>/<tf>.meta.json` = `fetched_at` (UTC ISO) + `schema: 1`, written atomically AFTER the parquet. Rejected: parquet footer metadata (needs `pq.write_table`, breaking `test_cache_atomic_writes.py::test_no_bypass`, exactly one `.to_parquet(` in `cache.py`, and the monkeypatched interruption tests); extra column (changes `OHLCV_COLUMNS`); mtime only (implicit, hard to fake, `1w` is rewritten without a fetch). A crash can only leave the sidecar older than the parquet, which causes an extra refetch, never a missed one. Migration: none; a parquet without a sidecar uses its file mtime (the time of the last successful merge); the first successful refresh creates the sidecar. `1w` stores its daily leg's value.
- **B2 retention.** `write_ohlcv(..., retain_bars=200)` for 15m, 1h, 4h (15m = 2.1 days). `1d` is never trimmed (500-bar first pull or more); `1w` derives from all cached daily bars (about 72 weeks). Deviation from D5; reason in the name check. Display windowing is not in S1.
- **B3 tail fetch.** With `since=None`: `fetch_ohlcv(since=None, limit=TAIL_LIMIT)` (15m/1h/4h 200, 1d 500). Contiguous with the cache (oldest fetched open <= cached last open + 1 timeframe): merge, newest wins (the forming bar is overwritten). Not contiguous: cache REPLACED by the tail, result `note="gap-replaced"`. If the newest returned bar is older than the staleness threshold the status is `stale` (an existing, so far unused `Status` value). An explicit `since` keeps today's path (`backfill_pairs_universe.py`).
- **B4 freshness.** Fresh only if `fetched_at` is inside the current bar AND younger than `FORMING_TTL`: 15m 180 s, 1h 300 s, 4h 900 s, 1d 900 s (1d matches the 15-minute rule, AC-13) [estimate, tune on the PC]. Tests inject a clock via `ccxt_adapter._now()`.
- **B5 staleness.** `stale` = (reference now - newest bar open) > 2 x timeframe + 900 s: 15m 2700 s, 1h 8100 s, 4h 29700 s, 1d 173700 s (strict). `1w` is judged on its `1d` bar. `is_partial` = bar open + timeframe > reference now. Reference now = host clock corrected by the measured skew when known.
- **B6 clock skew.** Measured inside the live fetch path (never in the board build, so tests never touch the network): `fetch_time` bracketed by two host reads, skew = host midpoint minus exchange time, cached 15 minutes per process (once per refresh cycle, not per coin). Warning above 120 s. Missing `fetch_time` or an error = unknown, no warning.
- **B7** chip availability is independent of the 60-bar chart threshold (a chip needs the current candle, plus the Monday daily bar for 1w).
- **B8** SVG axis text is NOT in S2: moving `simple-lines.svelte` from canvas to SVG axes is structural and belongs with zoom/pan/DPR in S6. S2 only does UTC scale, tick formats, captions.

## Sequencing

S1 -> merge -> S2 (S2 branches from `main` after the S1 merge SHA; they share `screener_board.py`, `models/screener.py`, `screener.ts`). S3 starts now, parallel to S1; no shared files. Max 3 concurrent workers (batch 1 peaks at 2). Merges are serialized (master-planner.md 5.6): the first of S1/S3 ready merges; the other rebases and re-runs CI.

## Program budget

User decision 03-10-26: 45 USD ceiling for the whole screener program, checked per slice before each spawn. Batch 1 [estimate]: S1 2-5, S2 2-5, S3 1-2 = 5-12 USD, leaving 33-40 USD for S4-S10 (re-check after S2). Recovery spend (6.9042678 USD so far) is separate, not counted. Subagent cap 15 USD per slice (master-planner.md section 6).

## S1: Freshness core (RT3, capped subagent lane: yes)

**Goal:** the forming candle expires, the gap bug is gone, sub-daily history is bounded, and every chart payload says how fresh it is.

**Owned (exact):** `api/data/ccxt_adapter.py`, `api/data/cache.py`, `api/data/freshness.py` (new, pure), `api/models/screener.py`, `api/analytics/screener_board.py`, `web/lib/types/screener.ts`; new tests `api/tests/data/test_freshness.py`, `test_ccxt_tail_fetch.py`, `test_cache_fetched_at_retention.py`, `test_ccxt_clock_skew.py`, `api/tests/routers/test_screener_freshness_payload.py`; fixture-builder edits only in `web/components/screener/__tests__/ScreenerBoard.test.tsx` and `DrillDownView.test.tsx`; minimal edits to `api/tests/data/test_ccxt_symbol_resolution.py` only if an existing assertion breaks; `process/general-plans/active/screener-batch1_03-10-26/s1-probe/**`; report `screener-batch1-s1_REPORT_<dd-mm-yy>.md` in the task folder.

**Forbidden:** CLAUDE.md, AGENTS.md, README.md, `.claude/**`, `.github/**`, `deploy/**`, `process/MASTER-PLAN.md`, `process/context/current-state.md`, `process/archive/**`, S2 and S3 files, `api/scripts/**` (`seed_e2e_cache.py` writes through `cache.write_ohlcv`, which stamps `fetched_at` = now by default, so no edit; check with `grep -n write_ohlcv api/scripts/seed_e2e_cache.py`).

**Design:**
1. `freshness.py`: constants (timeframe seconds, `FORMING_TTL`, `RETAIN_BARS`, `TAIL_LIMIT`, 900 s allowance) and pure `current_bar_open`, `cache_is_fresh`, `is_stale`, `is_partial`. No ccxt import; S2 and S3 import it.
2. `cache.py`: `write_ohlcv(symbol, timeframe, df, *, retain_bars=None, fetched_at=None)` keeps the newest N rows after the existing sort/dedupe, writes the parquet through the unchanged `_atomic_to_parquet`, then the sidecar (default now). New `read_fetched_at` = sidecar, else parquet mtime, else None. `OHLCV_COLUMNS` and the single `.to_parquet(` stay.
3. `ccxt_adapter.py`: `_now()`; `_cache_is_fresh(cached, timeframe, fetched_at=None, now=None)` delegates to `freshness`; tail path (B3) replaces 371-374; trim sub-daily on every write; `OhlcvResult` gains defaulted `fetched_at`, `note` (test doubles still construct it); `1w` passes the daily `fetched_at`; `last_clock_skew()` plus the opportunistic measurement (B6) reusing the already-built exchange. `fetch_ohlcv(exchange=)` stays the injection point.
4. `models/screener.py` (additive, defaulted): `ChartSeries` gains `last_bar_ts`, `fetched_at`, `is_partial`, `server_time`, `stale`; `ScreenerBoardResponse` gains `server_time`, `clock_skew_seconds`, `clock_skew_warning`. An unavailable chart has nulls and `stale=False` (its `reason` says why). `screener_board._chart_series` fills them from the `OhlcvResult` (1w: `stale` from the daily result).
5. `screener.ts` mirrors exactly (hand-synced, as its header requires); the two web fixtures get the new fields.

**Tests (names):**
- `test_freshness.py`: `test_stale_threshold_per_timeframe_boundary` (15m/1h/4h/1d at threshold and +1 s), `test_one_week_staleness_is_judged_on_its_daily_bar`, `test_is_partial_true_inside_bar_false_after_close`, `test_cache_is_fresh_requires_fetch_inside_current_bar`, `test_forming_ttl_boundary_per_timeframe`.
- `test_ccxt_tail_fetch.py` (fake exchange: oldest `limit` bars when `since` is given, LATEST `limit` bars when None; fake clock): `test_tail_fetch_uses_since_none_and_latest_limit`, `test_500_bar_gap_regression_catches_up` (15m cache 6 days behind = 576 bars), `test_forming_candle_refresh_after_ttl`, `test_forming_candle_not_refetched_inside_ttl`, `test_new_bar_boundary_forces_refetch_even_inside_ttl`, `test_non_contiguous_tail_replaces_cache_and_notes_gap`, `test_old_newest_bar_returns_status_stale`, `test_failed_fetch_keeps_cache_and_fetched_at`, `test_explicit_since_path_unchanged_for_backfill`, `test_one_week_derivation_uses_daily_fetched_at`.
- `test_cache_fetched_at_retention.py`: `test_sidecar_round_trip_and_written_after_parquet`, `test_legacy_parquet_without_sidecar_uses_mtime`, `test_sidecar_never_newer_than_parquet_after_crash`, `test_trim_on_write_15m_1h_4h_keeps_newest_200`, `test_one_day_bars_are_never_trimmed`, `test_write_defaults_fetched_at_to_now`.
- `test_ccxt_clock_skew.py`: `test_skew_is_host_midpoint_minus_exchange_time`, `test_skew_warning_above_120s_only`, `test_skew_measured_once_per_15_minutes`, `test_missing_fetch_time_means_unknown_not_error`, `test_fetch_time_exception_means_unknown`.
- `test_screener_freshness_payload.py`: `test_chart_series_carries_freshness_fields`, `test_unavailable_chart_has_null_freshness`, `test_board_carries_clock_skew_fields`, `test_pydantic_fields_match_typescript_interfaces` (parses `ChartSeries` and `ScreenerBoardResponse` names from `screener.ts`, same method as the `ConfidenceState` check).

**Gates (repo root, once after the last edit; each run recorded with SHA and UTC time in report heading 6):**
- G-S1-1 `uv run --project api pytest api/tests/data/test_freshness.py api/tests/data/test_ccxt_tail_fetch.py api/tests/data/test_cache_fetched_at_retention.py api/tests/data/test_ccxt_clock_skew.py api/tests/routers/test_screener_freshness_payload.py -q`
- G-S1-2 `UV_FROZEN=1 uv run --project api pytest api/ -q` (no new failures vs baseline)
- G-S1-3 `pnpm --filter web test`; G-S1-4 `pnpm --filter web exec tsc --noEmit --incremental false`; G-S1-5 `cd web && pnpm build:islands`
- G-S1-6 `git diff --check`; G-S1-7 scope: `git diff --name-only origin/main...HEAD` is inside the owned list, and `git diff --name-only origin/main...HEAD | grep -E '^(CLAUDE\.md|AGENTS\.md|README\.md|\.claude/|\.github/|deploy/|process/MASTER-PLAN\.md|process/context/current-state\.md|process/archive/)'` prints nothing.

**Red today:** tests first; run G-S1-1 once on the untouched base and record it. Behavioural reds on base: `test_forming_candle_refresh_after_ttl` (base `_cache_is_fresh` is True inside the bar, exchange never called), `test_500_bar_gap_regression_catches_up` (base asks `since=<cached max>, limit=500`; the fake returns the oldest 500, cache stays 76 bars behind), `test_trim_on_write_15m_1h_4h_keeps_newest_200` (base keeps 500). The rest are red by missing symbol or field.

**User-PC probe (hybrid; `s1-probe/probe_freshness.py` + README, read-only, run by the user):** (a) lists every `api/data/cache/ohlcv/*/*.parquet` with bar count, last bar, mtime, sidecar value, age; (b) prints host UTC, `fetch_time` and the skew in seconds (B6 real-world check); (c) calls `fetch_ohlcv(BTC/USDC:USDC, 15m, limit=5)` with and without a `since` 3 days back and prints which end of history each returns (confirms the unverified claim that `since=None` gives the LATEST bars).

**Lane:** capped subagent lane yes (RT3): at most 3 subagents, 15 USD, one level. Planned: one `vc-tester` confirming G-S1-1..5 from report heading 6 and CI (re-run only if `git diff --quiet <sha> HEAD` shows a change); one read-only reviewer diffing `models/screener.py` against `screener.ts` and checking the existing fake exchanges satisfy the tail call. Workers opus, subagents sonnet.

**Budget [estimate]:** 110 tool calls, 90 minutes, 4 CI polls, 2-5 USD, 2 full-suite runs (worker 1, tester or CI 1).

**Risks:** (1) rate limits at 30 coins: a cold board is up to 30 x 4 live calls (about 3 minutes sequential, one time); TTLs bound the rest; S8 solves it; failed fetches are not negatively cached (as today). (2) Existing parquet files on the PC: no migration step; legacy 500-bar 15m files shrink at their next successful write. (3) Sidecar collisions: one file per (symbol, timeframe), atomic replace; same-file writers write the same value. (4) Tail semantics unverified until the probe; the `stale` status makes a wrong assumption visible. (5) Seeded E2E bars stop being fresh after their TTL, so a long E2E run may try the (blocked) exchange once and still serve cached bars with status `unavailable`; E2E is not an S1 gate.

**Rollback:** revert the PR. Sidecars are git-ignored and ignored by old code; trimmed 15m/1h/4h bars are re-fetchable (up to 5000 candles); 1d untouched; model fields additive.

## S2: Current-candle chips and chart labels (RT3, capped subagent lane: yes)

**Goal:** each gain chip shows the current candle (open to latest price) with an explicit N/A; every coin-box and drill-down chart states its last bar in UTC with age and a plain `stale` marker.

Starts only after S1 is merged; a needed change in `freshness.py`, `cache.py` or `ccxt_adapter.py` stops at `review`.

**Owned (exact):** `api/analytics/indicators/gain.py` (new); `api/analytics/indicators/momentum.py` (delete only `compute_percent_change`, `compute_percent_change_by_timeframe`, `PCT_CHANGE_MIN_BARS`); `api/analytics/screener_board.py`; `api/models/screener.py`; `web/lib/types/screener.ts`; `web/lib/chart-time-format.ts`, `web/lib/chart-freshness.ts` (new); `web/lib/island-loader.ts`; `web/islands/simple-lines.svelte`; `web/components/chart/MiniChart.tsx`; `web/components/chart/ChartFreshness.tsx` (new); `web/components/screener/CoinPanel.tsx`, `DrillDownView.tsx`, `ScreenerBoard.tsx`; tests `api/tests/analytics/test_gain.py`, `api/tests/routers/test_screener_gain_contract.py` (new), edits to `api/tests/analytics/test_momentum.py` (remove the golden test at line 171 and its imports), `api/tests/routers/test_screener.py` (`_df` fixtures use open = previous close so chips are not flat; chip tests at 192 and 205), `web/lib/__tests__/chart-time-format.test.ts`, `chart-freshness.test.ts`, `web/components/chart/__tests__/ChartFreshness.test.tsx` (new), `ScreenerBoard.test.tsx`, `DrillDownView.test.tsx`; report `screener-batch1-s2_REPORT_<dd-mm-yy>.md`.

**Forbidden:** the S1 global list, S3 files, `api/data/**`, `RelativePerformanceChart.tsx`, the verdict components, `web/e2e/**`.

**Design:**
1. Contract (additive): `CoinPanel.gain_by_timeframe: dict[Timeframe, GainChip]`, `GainChip` = `pct: float|None`, `open_ts: str|None`, `is_partial: bool`, `stale: bool`, `reason: UnavailableReason|None` (a superset of INNOVATE's `{pct, open_ts, is_partial}`; `stale` and `reason` make N/A explicit). `percent_change_by_timeframe` stays, filled from the chip `pct`, so existing consumers keep working while its meaning becomes the corrected one. TS mirror in lockstep.
2. Formula (`gain.py`, Python is the single source of truth): newest bar of the timeframe, `pct = (close - open) / open x 100`, `open_ts` = its open (UTC ISO), `is_partial` and `stale` from `freshness`. 15m/1h/4h/1d use their own newest bar (1d = since 00:00 UTC). 1w uses the newest bar of `_derive_weekly_from_daily` (Monday 00:00 UTC anchor: Monday's daily open to the newest daily close). N/A with a reason, never 0: empty frame, NaN or non-positive open (`insufficient-history`), adapter status `bad_symbol`/`unavailable` with no data (matching reason), or 1w when the daily frame lacks the Monday bar of the newest week. A flat candle (open = close) is a real 0.0.
3. `build_coin_panel` replaces `compute_percent_change_by_timeframe` (line 146) with the chip builder (all five frames are already fetched there).
4. `chart-time-format.ts` (pure): axis in UTC (island uses `scaleUtc`; `Intl.DateTimeFormat` with `timeZone: "UTC"`, never the browser zone). 15m/1h/4h ticks `HH:mm`, first tick of each UTC day `DD MMM`; 1d/1w `DD MMM`, `MMM YY` when the span exceeds 365 days. `island-loader.ts` and `simple-lines.svelte` accept an optional `timeframe`; `MiniChart` forwards it; `ScreenerBoard` passes the board timeframe to `CoinPanel`; `DrillDownView` passes its own.
5. `chart-freshness.ts` + `ChartFreshness.tsx`: caption `Last bar 2026-10-03 14:15 UTC, opened 7 min ago (forming)` (closed bar: `Last bar 2026-10-03 14:00 UTC, 22 min ago`), age measured against the payload `server_time`, not the browser clock (skew-proof, testable); units `<1 min`, `N min` (under 120), `N h` (under 48), else `N d`. A plain `stale` marker (`data-testid="stale-marker"`) when `stale`. Rendered under the chart in `CoinPanel` and `DrillDownView`.
6. **Stays for S6:** zoom/pan/pinch, DPR sharpness, SVG axis text (B8), spaghetti chart.

**Tests (names):**
- `test_gain.py`: `test_chip_15m_golden_open_to_latest`, `test_chip_1h_golden`, `test_chip_4h_golden`, `test_chip_1d_is_since_midnight_utc_golden`, `test_chip_1w_monday_anchor_golden` (daily Mon 28 Sep to Thu 1 Oct 2026, opens 100/102/101/105, closes 102/101/104/106: week open 100, close 106, +6.0%, `open_ts` 2026-09-28T00:00:00Z), `test_chip_1w_without_monday_bar_is_na`, `test_empty_frame_is_na_never_zero`, `test_nan_or_zero_open_is_na`, `test_flat_candle_is_real_zero`, `test_is_partial_and_stale_flags_follow_reference_time`, `test_adapter_status_maps_to_reason`.
- `test_screener_gain_contract.py`: `test_gain_chip_fields_match_typescript`, `test_percent_change_by_timeframe_equals_chip_pct`. Updated: `test_per_coin_multi_timeframe_gain_readout`, `test_per_coin_gain_readout_thin_slot_is_none_not_zero`.
- Vitest: `chart-time-format.test.ts` (goldens per timeframe, day-boundary tick, year rule, plus a run under `TZ=Pacific/Kiritimati`), `chart-freshness.test.ts` (forming, closed, no bar), `ChartFreshness.test.tsx` (stale marker present/absent); ScreenerBoard and DrillDownView tests assert caption and stale marker and the `gain-chip-1d` text from `gain_by_timeframe`.

**Gates:** G-S2-1 `uv run --project api pytest api/tests/analytics/test_gain.py api/tests/routers/test_screener_gain_contract.py api/tests/routers/test_screener.py api/tests/analytics/test_momentum.py -q`; G-S2-2 `UV_FROZEN=1 uv run --project api pytest api/ -q`; G-S2-3 `pnpm --filter web test`; G-S2-4 `TZ=Pacific/Kiritimati pnpm --filter web exec vitest run lib/__tests__/chart-time-format.test.ts`; G-S2-5 `pnpm --filter web exec tsc --noEmit --incremental false`; G-S2-6 `cd web && pnpm build:islands`; G-S2-7 `git diff --check` plus the G-S1-7 scope checks against S2's list.

**Red today:** base chips are first-to-last close, so `test_chip_1w_monday_anchor_golden` and `test_chip_1d_is_since_midnight_utc_golden` fail by value; `test_flat_candle_is_real_zero`, the Kiritimati run and the caption tests fail on missing modules.

**User-PC probes (hybrid; needed for acceptance (d)):** (1) chip vs the exchange website: for BTC compare the 1h and 1d chips with the current candle's open and last price on the Hyperliquid chart; read `open_ts` and `pct` from `curl "http://127.0.0.1:8000/api/screener/board?timeframe=1h"` (`gain_by_timeframe`); (2) open the screener and a drill-down and check UTC ticks, the caption and the `stale` marker (stop the API for a while to see it appear). Sharpness is not judged here (S6).

**Lane:** capped subagent lane yes (RT3), same shape as S1: one `vc-tester` and one read-only reviewer (both sonnet; the reviewer also checks coverage honesty: jsdom never mounts the island, so it is proven by the formatter tests, the island build and the PC probe). Cap 3 subagents, 15 USD, one level.

**Budget [estimate]:** 100 tool calls, 90 minutes, 4 CI polls, 2-5 USD, 2 full-suite runs.

**Risks:** (1) LayerChart `Axis` taking a `format` function and `scaleUtc` on the bottom axis is unverified (node_modules is blocked for scouts); mitigation: island build plus PC probe; fallback is pre-formatted tick values. (2) Existing fixtures are flat (open = close), so chips would read 0.0; fixtures are updated here. (3) `CoinPanel` gains a `timeframe` prop; S4/S5 edit it after S2 (sequential). (4) S4 also edits `momentum.py`; S2 removes only three names.

**Rollback:** revert the PR; chips return to the old meaning, S1 fields stay.

## S3: LSE equities adapter, probe-first (RT2, capped subagent lane: no)

**Goal:** a tested adapter and ticker store for London Strategic Edge daily/weekly equity bars for a later page (S9), with live verification deferred to a user-PC probe.

**Step 0 (user PC; blocks live verification only):** `s3-probe/lse_probe.py` + README, committed first by the worker. It reads `LSE_API_KEY` from the environment only (never a flag, never printed or written), calls the provider REST API with plain `httpx` (no SDK; endpoint paths ASSUMED from the SDK's `candles`/`usage` calls and confirmed by this probe) for AAPL daily (last 60 days), tries `timeframe="1w"` (is weekly supported; D9 derives it from daily otherwise), a bad ticker (error shape) and `/vault/usage` (shape only). Raw responses go to `api/data/cache/equities/_probe/` (git-ignored, never committed). It then writes a SANITISED fixture `s3-probe/out/lse_candles_probe_shape.json`: same keys, types and timestamp format, symbol `TEST`, prices a deterministic synthetic walk. Reason: the repo is public and LSE terms forbid redistribution (VERDICT.md section 6), so no real LSE price is committed. The user copies it to `api/tests/data/fixtures/lse_candles_probe_shape.json` and tells the planner.

**Fixture absent (deterministic):** the worker codes the adapter against the documented shape in `findings.md` (rows `{symbol, open, high, low, close, volume, timestamp ISO}`; `candles(symbol, "1d", start=, end=, limit<=5000, order="asc")`) and an inline synthetic builder. `test_probe_fixture_parses` is `skipif` the file is missing. That test and live fetching are Known-Gap: the worker writes the backlog stub `process/general-plans/backlog/lse-live-shape-verification_NOTE_03-10-26.md`, lists the skip in report heading 7, and the S3 gate stays CONDITIONAL (no vacuous green) until the user runs the probe and that test passes.

**Owned (exact):** `api/data/lse_adapter.py`, `api/data/equities_store.py` (new); `api/tests/data/test_lse_adapter.py`, `test_equities_store.py` (new); `api/tests/data/fixtures/lse_candles_synthetic.json` (worker-built) and the optional user-supplied probe fixture; `.gitignore` (append `api/data/equities.json` only; `api/data/cache/equities/` is already ignored by `api/data/cache/*`, verified with `git check-ignore`); `process/general-plans/active/screener-batch1_03-10-26/s3-probe/**`; `process/general-plans/backlog/lse-live-shape-verification_NOTE_03-10-26.md`; report `screener-batch1-s3_REPORT_<dd-mm-yy>.md`.

**Forbidden:** the global list, `api/pyproject.toml`, `api/uv.lock`, `api/data/cache.py`, `api/data/ccxt_adapter.py` (a read-only import of `_derive_weekly_from_daily` is allowed), `api/models/**`, `api/routers/**`, `web/**`, S1 and S2 files.

**Design:**
1. Env key `LSE_API_KEY` (same name as the harness). Plain `httpx` GETs (already a dependency; URL constants confirmed by the probe), no `lse-data`. A missing key gives `unavailable`/`missing-key`, no network call, no raise. The HTTP transport is injectable for tests.
2. `fetch_equity_ohlcv(symbol, timeframe, transport=None, now=None) -> EquityOhlcvResult` (`df`, `status` in `ok|unavailable|stale|bad_symbol`, `reason`, `redistributable=False`, `source`, `caveats`). Only `1d` and `1w`; anything else is `unavailable`/`unsupported-timeframe`. 1w derives from daily with the existing Monday-anchored `_derive_weekly_from_daily`. A 404 ticker is `bad_symbol` (delisted names 404).
3. VERDICT adapter rules: drop bars on non-session days (weekends plus NYSE holidays built from `pandas.tseries.holiday` rules and `dateutil.easter`, no new dependency); caveats `split-adjusted-only`, `close-may-include-extended-hours`, `survivorship-bias`; `redistributable=False` always.
4. Cache `cache.CACHE_ROOT/"equities"/<SYM>/{1d,1w}.parquet` through `cache._atomic_to_parquet` (signature stays backward compatible with S1), footer tag `mysite.redistributable=false` plus source, a `fetched_at` sidecar in B1 style, TTL 6 h; path read at call time (the RFC-005 lesson).
5. `equities_store.py`: `{"tickers": [...]}` in `api/data/equities.json`, override env `SCREENER_EQUITIES_PATH` resolved at call time, atomic temp+rename, idempotent add, ticker `^[A-Z][A-Z0-9.\-]{0,9}$`, NO 30-cap, removing a missing ticker raises `TickerNotFoundError`. Separate from the crypto watchlist. No router, no web (S9).
6. RSI: tests feed adapter output to the existing `momentum.compute_rsi`; no new RSI code. S4 keeps `compute_rsi`; if it moves it, S4 updates this test.

**Tests (names):** `test_lse_adapter.py`: `test_parse_documented_row_shape_to_ohlcv_frame`, `test_non_session_days_are_dropped` (goldens from findings.md: 2006-11-23, 2007-11-22, 2008-01-01, Good Friday 2005-03-25, Saturdays out; an ordinary Tuesday kept), `test_missing_key_is_unavailable_and_makes_no_call`, `test_http_error_or_timeout_never_raises`, `test_404_ticker_is_bad_symbol`, `test_unsupported_timeframe_is_unavailable`, `test_result_and_parquet_are_tagged_redistributable_false`, `test_weekly_is_monday_anchored_from_daily`, `test_cache_is_fresh_for_six_hours_then_refetched`, `test_rsi_on_equity_bars_via_compute_rsi`, `test_probe_fixture_parses` (skipif absent), `test_cache_path_is_gitignored`. `test_equities_store.py`: add/remove/idempotent/uppercase, invalid ticker rejected, more than 30 accepted, interrupted write keeps the old file, path override honoured at call time.

**Gates:** G-S3-1 `uv run --project api pytest api/tests/data/test_lse_adapter.py api/tests/data/test_equities_store.py -q`; G-S3-2 `UV_FROZEN=1 uv run --project api pytest api/ -q` (RT2: once); G-S3-3 `git diff --check`; G-S3-4 scope check as in S1; G-S3-5 `grep -n "LSE_API_KEY" process/general-plans/active/screener-batch1_03-10-26/s3-probe/lse_probe.py api/data/lse_adapter.py` shows only `os.environ` reads, no print or write of the value; G-S3-6 (CONDITIONAL until the probe runs) `test_probe_fixture_parses` passes on the real shape file.

**Red today:** the modules do not exist; behavioural reds written first are the holiday goldens and the missing-key test.

**User-PC probe:** run `lse_probe.py` once (README: needs only `httpx`; set `LSE_API_KEY` for the session only, run, copy the sanitised fixture); it also answers "is weekly supported" and the bar-timestamp convention. A live end-to-end run of the adapter after merge is a second PC check, Known-Gap with the backlog stub until done.

**Lane:** no subagents (RT2). **Budget [estimate]:** 70 tool calls, 60 minutes, 3 CI polls, 1-2 USD, 1 full-suite run.

**Risks:** (1) holiday rules dropping a real session (goldens); (2) shape assumptions (`1w`, timestamp hour) verified only by the probe; (3) importing the private `_derive_weekly_from_daily`; (4) redistribution: no real LSE price in git.

**Rollback:** revert the PR; delete `api/data/cache/equities/` and `api/data/equities.json` locally.

## Later batches (not in this plan; dependencies only)

| Slice | Scope | Depends on |
|---|---|---|
| S4 | Verdict removal in 4 stages (models/contract/types, web components, analytics + `/scalp`, CSS/copy + grep gate); drops `select_active_benchmark` | S2 |
| S5 | Layout, groups, 30-cap: `watchlist.py`, new `layout.py`, ScreenerBoard, CoinPanel | S4 |
| S6 | Zoom/pan/DPR, SVG axis text (B8), spaghetti chart | S2, S4 |
| S7 | BTC leg chart plus estimated leg label (D-14) | S4 |
| S8 | In-process 15-minute refresh worker; AC-14 cache-category audit | S1 |
| S9 | Equities page | S3, S5 |
| S10 | Optional scheduled task (`deploy/**`, RT4, brief only) | S8, R12 |

## Touchpoints

Changed: `api/data/{ccxt_adapter,cache,freshness,lse_adapter,equities_store}.py`, `api/models/screener.py`, `api/analytics/{screener_board.py,indicators/gain.py,indicators/momentum.py}`, `web/lib/{types/screener,chart-time-format,chart-freshness,island-loader}.ts`, `web/islands/simple-lines.svelte`, `web/components/{chart,screener}/*`, `.gitignore` (one line), the listed tests, task-folder probes and reports. Read only (constrain B2): `api/scripts/{seed_e2e_cache,refresh_cache,backfill_pairs_universe}.py`, `leg_boundary.py`, `pairs_response.py`.

## Public Contracts

- `ChartSeries`, `ScreenerBoardResponse` (S1) and `CoinPanel.gain_by_timeframe` (S2) additive, each hand-mirrored in `screener.ts` (RT3 pair, enforced by new contract-sync tests). `percent_change_by_timeframe` keeps its name but changes meaning to the current-candle gain (F4, intended).
- `fetch_ohlcv` signature unchanged; `OhlcvResult` gains defaulted `fetched_at`, `note`; `cache.write_ohlcv` gains keyword-only `retain_bars`, `fetched_at`; new `ccxt_adapter.last_clock_skew()`.
- On disk: `<tf>.meta.json` sidecars, equities cache, `equities.json` (all git-ignored). New env: `LSE_API_KEY`, `SCREENER_EQUITIES_PATH` (the planner adds them to operating-instructions.md at UPDATE PROCESS).
- Security scan (STRIDE, quick): the key lives only in the process environment, never logged or committed; LSE data stays private-use and out of git; no new network surface or router; probes are read-only.

## Blast Radius

About 45 files in `api/` and `web/`; shared cache and response contract (RT3) for S1/S2, localized backend (RT2) for S3. Other `fetch_ohlcv` consumers (pairs, leg boundary, `refresh_cache.py`, backfill) are protected by the unchanged `since` path, no-trim for 1d and the full-suite gate.

## Acceptance Criteria

| ID | Criterion (SPEC link) | proven by | strategy |
|---|---|---|---|
| AC-S1-1 | Forming candle refetched after its TTL and at a bar boundary (F1 A, AC-13) | G-S1-1 `test_forming_candle_refresh_after_ttl`, `test_new_bar_boundary_forces_refetch_even_inside_ttl` | Fully-Automated |
| AC-S1-2 | Cache over 500 bars behind catches up in one refresh (F1 B) | G-S1-1 `test_500_bar_gap_regression_catches_up`; real semantics by PC probe | Fully-Automated + Agent-Probe |
| AC-S1-3 | 15m/1h/4h trimmed to 200 on write, 1d never (AC-14, D5) | G-S1-1 trim tests | Fully-Automated |
| AC-S1-4 | Staleness thresholds per timeframe, 1w on 1d (F1 D) | G-S1-1 `test_stale_threshold_per_timeframe_boundary` | Fully-Automated |
| AC-S1-5 | Payload freshness and skew fields; TS mirror in lockstep (F1) | G-S1-1, G-S1-4 | Fully-Automated |
| AC-S1-6 | Skew measured once per refresh, warning above 120 s (F1 real-world check) | G-S1-1 fake exchange; real skew by PC probe | Fully-Automated + Agent-Probe |
| AC-S1-7 | No cache migration; pairs and legs unaffected | G-S1-1 legacy-mtime test, G-S1-2; PC probe lists real files | Fully-Automated + Hybrid |
| AC-S2-1 | Chip = current candle open to latest, goldens incl. Monday week (F4) | G-S2-1 `test_gain.py` | Fully-Automated |
| AC-S2-2 | Thin data is N/A with a reason, never 0; real flat is 0.0 (F4, AC-5) | G-S2-1 | Fully-Automated |
| AC-S2-3 | UTC ticks with the specified formats, browser-zone independent (F1 D) | G-S2-3, G-S2-4, G-S2-6; visual by PC probe | Fully-Automated + Agent-Probe |
| AC-S2-4 | `Last bar <time> UTC, <age>` and `stale` marker on coin box and drill-down (F1) | G-S2-3 component tests | Fully-Automated |
| AC-S2-5 | Chips agree with the exchange chart | PC probe (1) | Agent-Probe |
| AC-S3-1 | Parse of the documented shape, non-session days dropped, weekly derived, never raises (D9, AC-15) | G-S3-1 | Fully-Automated |
| AC-S3-2 | Missing key gives `unavailable`, no call (D10) | G-S3-1 | Fully-Automated |
| AC-S3-3 | `redistributable=false` on result and parquet; cache ignored; no key in repo (D11) | G-S3-1, G-S3-5 | Fully-Automated |
| AC-S3-4 | Ticker store: separate file, no cap, atomic (AC-15) | G-S3-1 | Fully-Automated |
| AC-S3-5 | Real LSE response matches the parse | G-S3-6 + user probe | Agent-Probe; CONDITIONAL until run (Known-Gap with backlog stub, never a terminal PASS) |

## Verification Evidence

| Gate / Scenario | Strategy | Proves SPEC criterion |
|---|---|---|
| G-S1-1 new S1 pytest files | Fully-Automated | F1 A/B/D, AC-13, AC-14 (AC-S1-1..7) |
| G-S1-2, G-S2-2, G-S3-2 full pytest | Fully-Automated | no regression in pairs, legs, board (AC-S1-7) |
| G-S1-3/4/5, G-S2-3/5/6 vitest, tsc, islands | Fully-Automated | contract lockstep, labels, island builds (AC-S1-5, AC-S2-3, AC-S2-4) |
| G-S2-1 gain tests, G-S2-4 TZ run | Fully-Automated | F4 (AC-S2-1..3) |
| G-S3-1 adapter and store, G-S3-5 key grep | Fully-Automated | D9, D10, D11, AC-15 (AC-S3-1..4) |
| PC probe S1 (cache ages, skew, tail semantics) | Agent-Probe | F1 real-world check (AC-S1-2, AC-S1-6) |
| PC probe S2 (chip vs exchange, labels) | Agent-Probe | F4, F1 (AC-S2-3, AC-S2-5) |
| PC probe S3 (live LSE capture, fixture test) | Agent-Probe | AC-15 (AC-S3-5), CONDITIONAL until run |

Known gaps: live LSE end-to-end (stub); zoom/sharpness (S6); 30-coin limits (S8).

## Risk Predictions (condensed 5-persona pass)

Security: the only secret is `LSE_API_KEY`; LSE data in a public repo is closed by the sanitised-fixture rule. Performance: TTLs bound calls; a cold 30-coin board is slow once (S8 removes it). Data integrity: gap-replace and no-trim for 1d protect pairs and legs; `stale`, N/A reasons and the `stale` status keep "numbers never silently wrong". Maintainer: sidecar and `freshness.py` are small and pure. User: chips change value (intended; the S2 report says so).

## Implementation Checklist (atomic; one slice per worker)

**S1:** 1 baseline. 2 tests first (5 files, 2 fixture edits), red run on untouched source. 3 `freshness.py`. 4 `cache.py` sidecar, `retain_bars`, `read_fetched_at`. 5 `ccxt_adapter.py` (`_now`, delegating `_cache_is_fresh`, tail path over 371-374, trim, `OhlcvResult` fields, 1w `fetched_at`). 6 clock skew. 7 `models/screener.py`. 8 `screener_board` fields. 9 `screener.ts`. 10 `s1-probe`. 11 G-S1-1 green (max 2 fix cycles per gate). 12 G-S1-2..7 once. 13 report, PR, CI, tester.
**S2** (after S1 merged): 1 baseline. 2 tests first, red run. 3 `gain.py`. 4 `GainChip` in models and `screener.ts`. 5 chip wiring; delete old functions and golden test. 6 `test_screener.py` fixtures. 7 `chart-time-format.ts`, `chart-freshness.ts`. 8 island and loader `timeframe`, `scaleUtc`. 9 `ChartFreshness.tsx` and wiring. 10 G-S2-1..7. 11 report, PR, tester, PC probe steps.
**S3:** 1 baseline. 2 `s3-probe` script + README, committed first. 3 tests first, red run. 4 `equities_store.py`. 5 `lse_adapter.py`. 6 `.gitignore` line. 7 backlog stub. 8 G-S3-1..5, G-S3-6 CONDITIONAL. 9 report, PR.

## Phase Completion Rules

A slice is `CODE DONE` when its PR is open with green gates in the report; `VERIFIED` only after independent confirmation (tester or CI on the head SHA, master-planner.md section 4) AND its user-PC evidence. S1 and S2 stay at `review` after merge until the PC probe evidence exists; S3 stays CONDITIONAL until the live-shape fixture test passes. A diff touching CLAUDE.md or AGENTS.md stops at `review`. Known-Gap is a residual, never a PASS.

## Validate Contract

(to be completed by VALIDATE) Gate: PENDING. VALIDATE writes per slice: the exact gate commands above with expected output, failing stubs for each Fully-Automated row (from `vc-test-coverage-plan`), V1-V7 results, red-today evidence confirmed by running the new tests against `origin/main`, the scope-check commands with final owned lists, and the CONDITIONAL handling for AC-S3-5.

## Resolved questions (user, 03-10-26, all recommended)

1. 1d is NEVER trimmed (amends D5): only 15m/1h/4h are trimmed to about 200 bars; daily stays 500+ so weekly RSI(14) and BTC legs are well-founded.
2. S3 does NOT add `lse-data`: plain HTTP calls to the provider API; `api/pyproject.toml` and `api/uv.lock` stay untouched (S3 forbidden).
3. No real LSE prices are ever committed; fixtures hold synthetic prices only; real data stays local and git-ignored.

## Worker envelopes

Written AFTER VALIDATE and the user's approval (not now): one per slice, at most 8,000 bytes, saved as `screener-batch1-s{1,2,3}_REF_<dd-mm-yy>.md` in this task folder, using the master-planner.md section 8 template (branches `claude/<task-id>-<slug>`, ids assigned at registration). S2's envelope is issued only after the S1 merge SHA exists.

## Test Infra Improvement Notes

(none identified yet) Candidates: a shared fake-exchange module (`FakeExchange`, `StubExchange`, `_DailyExchange`); `lse_adapter` in the shared adapter-contract test note; jsdom never mounts the Svelte islands.

## Resume and Execution Handoff

1. Selected plan file: `process/general-plans/active/screener-batch1_03-10-26/screener-batch1_PLAN_03-10-26.md`
2. Last completed step: PLAN written from a read of the real code.
3. Validate-contract status: pending (skeleton above; no `Gate: PASS`).
4. Context loaded: SPEC, INNOVATE, findings note, operating-instructions.md, master-planner.md, decisions.md, all-tests.md, LSE VERDICT and findings.
5. Next step for a fresh agent: then ENTER VALIDATE MODE; after VALIDATE and explicit approval write the three envelopes and spawn S1 and S3 (S2 after the S1 merge). Next instruction (RIPER-5): say **ENTER VALIDATE MODE**.
