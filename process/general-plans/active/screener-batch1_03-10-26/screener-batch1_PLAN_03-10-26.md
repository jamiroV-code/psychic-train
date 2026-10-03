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

Status: CONDITIONAL
Date: 03-10-26
date: 2026-10-03
generated-by: outer-pvl
Gate: CONDITIONAL

**TL;DR:** all three slices are executable (no FAIL), but each needs the binding amendments below, and five conditions need the user's acceptance before any worker envelope is written (section "Conditions needing the user's acceptance"). Biggest finds: the repo already holds the red test for S1's headline feature and the plan does not own it; S2 breaks an existing E2E spec; the S1 refresh policy can push the board past the web client's 10 s timeout; S3 handles a secret but is tiered RT2.

**Scope validated:** plan at HEAD e8824f8 (branch claude/pensive-albattani-ou0cgv) against code at origin/main af7888f; HEAD differs from origin/main only under `process/`. One agent ran V1-V3 (a VALIDATE subagent cannot spawn): the 4 Layer-1 dimensions and 3 Layer-2 slice checks were done by direct reads, greps and runs, so confidence is MEDIUM-HIGH, not an independent fan-out. No source file was changed. **Precedence:** VALIDATE edited only this section (plus `results.tsv`, one phrase in the Resume section, see Mechanics); where an amendment A-* below differs from the plan body, the amendment controls and the envelopes must quote it.

### Verdict per slice

| Slice | Verdict | Conditions (detail in Amendments and Conditions) |
|---|---|---|
| S1 Freshness core | CONDITIONAL | A-S1-1..9 binding; U-1 (PC-probe residual), U-3 (amendments override body), U-5 (board latency vs 10 s client timeout) |
| S2 Chips and labels | CONDITIONAL | A-S2-1..8 binding; U-1, U-3, U-4 (E2E hybrid) ; starts only after the S1 merge SHA |
| S3 LSE adapter | CONDITIONAL | A-S3-1..9 binding; U-2 (CONDITIONAL until live probe; RT2 despite a secret), U-3 |

Net: 0 FAIL / 11 CONCERN (D1, D2, D3, D5, D7, D8, D11, D12, D14, D16, D17) -> CONDITIONAL. First-pass CONDITIONAL: `PHASE_COMPLETE: VALIDATE` is not legal yet (needs a PVL fix cycle, or the user's explicit acceptance of the conditions below).

Parallel strategy: parallel-subagents. EXECUTE = two independent worker sessions (S1 and S3, no shared files), S2 sequential after S1; inside S1 and S2 the capped lane of at most 3 sonnet subagents (vc-tester + one read-only reviewer).
Rationale: 3 of 7 signals (S2 additive public API contract, S6 secret handling in S3, S7 more than 5 files); dominant S7. Workers opus, all subagents sonnet. Agent count: S1 1+2, S2 1+2, S3 1 = 7 (cost guard not triggered; program ceiling 45 USD, 15 USD per slice unchanged). VALIDATE itself ran sequentially.

### Dimension findings

- Infra fit: PASS - every cited path and line anchor exists on origin/main (list below); every gate command runs offline here (uv 0.8.17 with the existing api venv, node 22, pnpm). Only the plan's pytest baseline 873 is stale (measured 870).
- Test coverage: CONCERN - existing strict-xfail test for S1's feature not owned (D1); expected break in `test_ccxt_symbol_resolution.py` (D3); empty-tail case untested (D5); S3 holiday and secret tests thin (D11, D12); gates lack expected outputs (D14).
- Breaking changes: CONCERN - `web/e2e/screener.spec.ts:141-157` breaks after S2 (D8); `stale` status makes refresh_cache count a coin as not ok (D6); board refresh load vs the 10 s web timeout (D7).
- Security surface: CONCERN - S3 secret handling is tiered RT2 while operating-instructions RT4 lists secrets (D12); G-S3-5 grep cannot prove "never printed"; no explicit httpx timeout or header-only rule; repo is public so fixtures must be synthetic (guard test added).
- S1 feasibility: CONCERN - mechanically feasible; highest-risk edit is the tail path over `ccxt_adapter.py:371-374` (response-level semantics unverified; see U1). S2 feasibility: CONCERN - highest-risk edit is `simple-lines.svelte` (axis on a time scale; unverifiable offline; shared with the forbidden RelativePerformanceChart). S3 feasibility: CONCERN - highest-risk item is the live shape (Known-Gap until the probe).

### V1-V3 evidence (what was run, 03-10-26 UTC, origin/main af7888f)

- Structural validator `node .claude/skills/vc-generate-plan/scripts/validate-plan-artifact.mjs <plan>`: 0 failures, 0 warnings (before this section was written).
- Baseline: `UV_FROZEN=1 uv run --project api pytest api/ -q` -> 870 passed, 1 skipped, 5 deselected, 1 xfailed (228 s). The plan's 873 (at 753db23) is superseded: three `write_confirmed_boundaries` tests were removed since. `pnpm --filter web test` -> 223 passed, 30 files. `pnpm --filter web exec tsc --noEmit --incremental false` -> exit 0. `cd web && pnpm build:islands` -> exit 0. `TZ=Pacific/Kiritimati pnpm --filter web exec vitest run <path>` pattern works (TZ takes effect in Node). `git status` clean after all runs.
- Cited anchors confirmed: `ccxt_adapter.py` `_cache_is_fresh` 173-184, cache-first return 354-355, `effective_since` 371-374, `_derive_weekly_from_daily` 273-284; `cache.py` `write_ohlcv` 133-139 and the only `.to_parquet(` at line 95 inside `_atomic_to_parquet` 79-109; `test_cache_atomic_writes.py::test_no_bypass` line 161; `screener_board.py` line 146 (only caller of the pct functions), `_chart_series` 86-100 with callers 170 and 210; `momentum.py` 32, 113-123, 126-133; `models/screener.py` `ChartSeries` 85, `CoinPanel` 100-115, `ScreenerBoardResponse` 118-121, `ScalpView` 130; `screener.ts` `ChartSeries` 60, `CoinPanel` 67, `ScreenerBoardResponse` 78, `ScalpView` 90; `simple-lines.svelte` `scaleTime` line 63 and bottom `<Axis>` line 72; `MiniChart.tsx` 26-60; `CoinPanel.tsx` gain row 69-80 (uses `percent_change_by_timeframe`, line 74); `DrillDownView.tsx`; `test_momentum.py` 17 and 171; `test_screener.py` 192 and 205; `test_screener_integration.py` class 127, method 141; httpx>=0.27 in `api/pyproject.toml` (installed 0.28.1). Adapter shape precedent exists (`fred_adapter.FredSeriesResult(series_id, df, status)`). `.gitignore:18 api/data/cache/*` already covers `equities/`, `_probe/` and `*.meta.json` (verified with `git check-ignore`); `api/data/equities.json` is NOT ignored today, so the S3 line is needed. No code globs `cache/ohlcv/**` that a sidecar could pollute (`check_weekly_anchor.py:51` lists directories only).
- Inline probes (offline, read-only, scratch only): (1) ccxt 4.5.78 Hyperliquid builds `startTime = now - limit x timeframe, endTime = now` for `since=None`, and `startTime = since, endTime = now` for an explicit `since` (request captured through a stubbed transport; `limit=None` gives `startTime=0`, so the adapter must always pass an explicit limit). (2) `has['fetchTime']` is True and `fetch_time(params={})` exists. (3) `df.attrs` round-trips through `_atomic_to_parquet`-style `to_parquet` into the footer (pandas 3.0.6, pyarrow 25.0.1). (4) `pandas.tseries.holiday.USFederalHolidayCalendar` observes New Year 2011 on Fri 2010-12-31 (NYSE was OPEN) and includes Columbus and Veterans Day (NYSE open). (5) `_derive_weekly_from_daily` labels a bucket with its Monday even when the Monday daily bar is missing (Tue-Thu frame -> label 2026-09-28, open 102.0, not Monday's open).
- LSE facts in S3 checked against `origin/claude/exciting-meitner-hy50kn:process/general-plans/completed/lse-data-verification_17-09-26/{findings,VERDICT}.md`: row shape `{symbol, open, high, low, close, volume, timestamp ISO}`, 5000 rows per request, holiday goldens (2006-11-23, 2007-11-22, 2008-01-01, 2005-03-25, SPY Saturdays 2026-05-02/09/16/23/30), delisted tickers 404, redistribution clause section 6: all match the plan. Those two files are NOT on main; adapter rules 1-5 are on main in `process/context/data-sources/all-data-sources.md:225-252`.

### Defects and mismatches found

| ID | Where | Finding | Sev |
|---|---|---|---|
| D1 | `api/tests/deploy/test_fresh_deploy_degrade.py:99-115` | strict-xfail case `screener_chart_carries_staleness_marker` is the repo's existing red proof of S1 ("aged cache served with no staleness marker"; reason text hands it to the screener lane). Not owned, not gated. After S1 it keeps xfailing (it looks for an `as_of` key), so AC-S1-5 would never be proven over HTTP. Reproduced red today with `--runxfail`. | CONCERN |
| D2 | `api/tests/data/test_cache_atomic_writes.py:161-162` | `test_no_bypass` counts the literal `.to_parquet(` in the whole text of `cache.py`, comments and docstrings included. Any comment that spells it breaks the test. | CONCERN |
| D3 | `api/tests/data/test_ccxt_symbol_resolution.py` (`_BAR` ts 1_700_000_000_000; test `test_a_cold_cache_still_reaches_the_exchange` asserts `status == "ok"`) | B3 returns `stale` when the newest bar is older than the threshold, so this existing test will fail. Plan only says "edit if an assertion breaks". | CONCERN |
| D4 | `api/tests/routers/test_relative_performance.py:39` | builds `OhlcvResult` with 5 positional args; new fields must be appended with defaults. | note |
| D5 | plan S1 B3 | no case for a successful fetch that returns `[]` (delisted or empty window): contiguity check on an empty frame. | CONCERN |
| D6 | `api/scripts/refresh_cache.py:74` | `ok = status == "ok"`: a coin returned as `stale` counts as not ok (exit code still 0 if any ok). Benign; report it. | note |
| D7 | plan S1 Risks (1); `web/lib/api/screener.ts:12` | "one time" is wrong. TTLs (1d 900 s, 4h 900 s, 1h 300 s, 15m 180 s) make a board opened after 15 min idle refetch up to 30 coins x 4 frames = 120 live calls at the measured 0.3-0.8 s each (backlog `board-endpoint-cold-start-latency_20-09-26.md`) = 36-96 s, plus 12.5 s `load_markets` on a cold process; the web client aborts at `DEFAULT_TIMEOUT_MS = 10_000`. Per that note a 4-coin board with every frame expired already took about 11 s on a warm process (8 s of fetches + 3.3 s compute) and 23.7 s on a cold one. Recurs after every idle lapse until S8. | CONCERN |
| D8 | `web/e2e/screener.spec.ts:141-157` (forbidden to S2 as `web/e2e/**`) | "a thin-history symbol shows unavailable, never a zero" rejects `/\b0\.0%/`. Seeded THIN has 20 daily bars (open 3119, close 3120): after S2 (B7: chips independent of the 60-bar threshold) its 1d chip is +0.032%, rendered "+0.0%", which the regex matches. The spec fails after S2 and no owned file fixes it. | CONCERN |
| D9 | plan S2 design 2 | `_derive_weekly_from_daily` hides a missing Monday bar (probe 5), so "1w N/A when Monday bar absent" must be an explicit check in `gain.py`; the plan test exists, the hazard is not stated. | note |
| D10 | plan S2 golden `open_ts 2026-09-28T00:00:00Z` vs `screener_board._series_to_chart_bars` (`isoformat()` -> `+00:00`) | two timestamp spellings; S1 does not pin its own. | note |
| D11 | plan S3 design 3 | "NYSE holidays from pandas rules": the federal calendar is wrong for NYSE in three ways (probe 4). Plan goldens do not catch it. | CONCERN |
| D12 | plan S3 tier RT2; G-S3-5 | S3 reads an API key and calls a vendor; operating-instructions RT4 names secrets. G-S3-5 (`grep LSE_API_KEY`) matches only the variable name, so `print(key)` would pass; nothing tests that the key stays out of exceptions, repr and logs; no explicit timeout; auth scheme (header vs query) not stated. | CONCERN |
| D13 | plan S3 design 4 | footer tag `mysite.redistributable=false` through `cache._atomic_to_parquet(df, path)` (no metadata argument; `cache.py` is forbidden to S3). Feasible only via `df.attrs` (probe 3). | note |
| D14 | plan gates | no expected outputs, "inside the owned list" is not mechanical, RT3 "contract snapshots unmodified" absent, `UV_FROZEN=1` missing on the targeted runs. | CONCERN |
| D15 | plan header, `all-tests.md` | baseline 873 vs measured 870 (3 tests removed). | note |
| D16 | plan Resume item 3 (line 266) | the body spelled out the literal PASS-gate string ("no ... PASS" with the gate prefix), so the mechanical VALIDATE->EXECUTE check that counts that string in the plan file would return 1 on a CONDITIONAL plan. Fixed by rewording that one phrase. | CONCERN |
| D17 | plan file size vs WORKER cap | the WORKER entry set is capped at 36,000 B including CLAUDE.md, the envelope and the plan; this plan is now far larger. Envelopes must cite line ranges (A-ALL-5). | CONCERN |
| D18 | S1 B3 for `1d` | a non-contiguous 1d tail REPLACES the cache; a deep daily history (backfill writes up to 5000 bars) could be discarded if the newest cached bar is more than about 500 days old. Edge case; advisory. | advisory |
| D19 | S2 budget | 100 tool calls for about 27 owned artefacts (5 web source files, 3 new web tests, python, island, E2E edit) is not realistic; S1 110 is tight. | advisory |

### Binding amendments (override the plan body)

**A-ALL (all slices)**
1. Every pytest gate runs with `UV_FROZEN=1`. RT3 snapshot rule: `git diff --name-only --diff-filter=MDR origin/main...HEAD | grep -E '/fixtures/'` prints nothing (adding files is allowed).
2. Baseline to re-record at spawn (workers) and expected counts below are relative to the measured origin/main values: pytest 870 passed / 1 skipped / 5 deselected / 1 xfailed; vitest 223 passed in 30 files; tsc exit 0; islands exit 0.
3. Every NEW timestamp string in API payloads is ISO-8601 UTC with seconds and a trailing `Z` (`2026-10-03T14:15:00Z`); existing `ChartBar.timestamp` stays as is.
4. Report heading 6 records every gate run with SHA and UTC time; the tester re-runs only gates whose paths changed (`git diff --quiet <sha> HEAD -- <paths>`).
5. Worker cap: envelopes must give the worker only its slice section and its slice contract block by line range (`grep -n '^## \|^### ' <plan>` at spawn time), never the whole file; the global Defects table is for the planner.
6. Workers branch from `main`, so this plan and contract must be on `main` before any envelope is issued (today they sit on `claude/pensive-albattani-ou0cgv`, commit e8824f8 plus this section); otherwise the worker cannot read them and every `origin/main...HEAD` scope check lists the process files as strays (the commands were dry-run on the current HEAD and do list them).

**A-S1**
1. Owned list gains `api/tests/deploy/test_fresh_deploy_degrade.py` (edit only the parametrized case `screener_chart_carries_staleness_marker`: drop the `xfail(strict=True)` mark, assert `chart["stale"] is True and chart["last_bar_ts"] and chart["server_time"]` on the 30-day-aged BTC cache). New gate G-S1-8.
2. `test_a_cold_cache_still_reaches_the_exchange` is an EXPECTED break: fix it by giving the fake bar the injected clock's current-bar open (do not weaken the `status == "ok"` assertion). Any other existing test that breaks stops the worker at `needs_input`; do not widen edits (`test_board_integration.py`, `test_weekly_derivation.py`, `test_cache_timezone.py`, `test_adapter_contracts.py` are analysed as unaffected).
3. Frozen for S3 (do not change signature or behaviour): `cache._atomic_to_parquet(df, path)`, `cache.CACHE_ROOT`, `cache.OHLCV_COLUMNS`, `cache.bootstrap_cache_dirs()`, `ccxt_adapter._derive_weekly_from_daily(daily_df, source)`.
4. `cache.py` source text must contain `.to_parquet(` exactly once (code AND comments). Sidecar write: `json` + `tempfile.mkstemp(dir=..., prefix=".<name>.", suffix=".tmp")` + `os.replace`, temp removed on any exception (the atomic-write tests fail on leftover `*.tmp`).
5. `OhlcvResult`: append `fetched_at`, `note` AFTER `status`, both defaulted.
6. New test `test_empty_tail_response_keeps_cache_and_fetched_at` in `test_ccxt_tail_fetch.py`: a successful `[]` response writes nothing, leaves the sidecar unchanged, status comes from B5 on the cached newest bar, no exception.
7. Tail request: always pass an explicit `limit` (probe 1: `limit=None` requests from epoch 0). Fallback rule for U1: if the PC probe shows `since=None` does not return the latest bars, switch the tail request to `since = now_ms - (TAIL_LIMIT - 1) x timeframe_ms` (still limit=TAIL_LIMIT); isolate the choice in one helper `_tail_since(timeframe, now)` returning `None` today.
8. S1 PC probe adds (d): wall-clock of one `GET /api/screener/board?timeframe=1h` with expired TTLs, printed in seconds, and the number of live calls made; the report states it against the 10 s web timeout (U-5). Write the advisory stubs `process/general-plans/backlog/ohlcv-negative-cache-and-1d-gap-replace_NOTE_<dd-mm-yy>.md` (D7 failed-fetch retry cost, D18 1d gap-replace) as a scoped addition to the S1 owned list.
9. Gates, expected results and scope allowlist: see "S1 exact gates".

**A-S2** (starts after the S1 merge SHA exists; branch from main at that SHA)
1. Owned list gains `web/e2e/screener.spec.ts` (edit only test 4, lines 141-157): replace the "never `0.0%`" regex by: every chip is `N/A` or matches `^[+-]?\d+\.\d%$`, `chart-unavailable` still visible, and the API `gain_by_timeframe` for THIN has `pct` or a `reason` for each timeframe. Gate G-S2-8 (hybrid, see U-4).
2. `simple-lines.svelte`, `island-loader.ts`, `MiniChart.tsx`: `timeframe` is optional; when absent the axis is exactly today's (`scaleTime`, `ticks={4}`), so `RelativePerformanceChart.tsx` (forbidden file, same island) and its vitest are unchanged. Gate: `RelativePerformanceChart.test.tsx` passes untouched.
3. `gain.py`: the 1w chip is N/A with `reason=insufficient-history` unless the Monday date of the newest weekly bucket is present among the daily timestamps (explicit check; D9). `open_ts` uses the `Z` form (A-ALL-3).
4. U3 spike (axis `format` on `scaleUtc`): worker step 8a, before writing the Svelte change: implement the UTC axis, run `pnpm build:islands` (compiles Svelte but does NOT type-check LayerChart props), then take a screenshot of the seeded E2E stack in the cloud container (`PLAYWRIGHT_CHROMIUM_PATH=/opt/pw-browsers/chromium-1194/chrome-linux/chrome`) and read the PNG; fallback chain: (1) `format` function on `Axis` with `scaleUtc`; (2) pre-formatted tick values (`ticks` as `Date[]` produced by `chart-time-format.ts`); (3) if the render still shows wrong or default labels, keep the old axis, ship the captions and `stale` marker (they are DOM and fully tested), write `process/general-plans/backlog/island-axis-labels-render-check_NOTE_<dd-mm-yy>.md`, S2 stays at `review` for AC-S2-3 only.
5. `test_screener.py` fixtures: `_df` open = previous close (first bar open = close) so chips are non-flat; the empty-frame and thin-slot test keeps asserting `None`; add the new `gain_by_timeframe` assertions beside them.
6. Deletions complete: G-S2-9 greps prove no dangling `compute_percent_change*` or `PCT_CHANGE_MIN_BARS`.
7. Budget: raise the tool-call budget to 150 (advisory; USD cap unchanged).
8. Scope allowlist adds the one backlog stub named in 4 and the E2E spec (see "Scope and secret-hygiene commands").

**A-S3**
1. Tier: RT2 plus the secret-hygiene gates in 2-3 and the user's acceptance U-2 (alternative: full RT4 pack, which this batch does not plan).
2. New tests (add to `test_lse_adapter.py`): `test_api_key_never_in_result_repr_logs_or_exception_text` (sentinel key `LSE_TEST_SENTINEL_KEY_0123456789` in `monkeypatch.setenv`; `httpx.MockTransport` asserts the key arrives only in a request header; force 401, 404, 500, `ConnectError`, `ReadTimeout` whose text contains the URL; assert the sentinel is absent from `repr(result)`, `result.reason`, `result.caveats`, `caplog.text` and every exception text, and that `result.reason` is a closed enum string, never `str(exc)`); `test_request_uses_explicit_timeout_and_header_auth` (an `httpx.Timeout` constant of at most 15 s is passed on every call; the key is never in URL or query); `test_committed_lse_fixtures_are_synthetic_only` (every `api/tests/data/fixtures/lse_*.json` row has symbol `TEST` or `SYNTH`); `test_session_calendar_nyse_traps` (below).
3. Auth scheme is ASSUMED: header only (never a query parameter). The probe tries `Authorization: Bearer` then `X-API-Key`, prints only the scheme name and the HTTP status, never a URL with the key, never headers, never a response body.
4. Calendar: do NOT use `USFederalHolidayCalendar` as is. Extra goldens: 2010-12-31 kept and 2021-12-31 kept (New Year on a Saturday: NYSE open), 2015-07-03 dropped (July 4 on a Saturday), 2022-06-20 dropped (Juneteenth), 2006-10-09 kept (Columbus), 2005-11-11 kept (Veterans). Special closures (2012-10-29/30, 2018-12-05, 2025-01-09) are not modelled: add caveat `special-closures-not-modelled`.
5. Footer tag: set `df.attrs = {"mysite.redistributable": "false", "source": "lse"}` before `cache._atomic_to_parquet`; read it back with `pd.read_parquet(path).attrs` or `pq.read_schema(path).pandas_metadata["attributes"]`, never through `cache.read_ohlcv` (DuckDB drops attrs). `lse_adapter.py` must not contain the literal `.to_parquet(` outside what `_atomic_to_parquet` already does (it only calls the helper).
6. Tests use `isolated_cache` and `monkeypatch.setenv("SCREENER_EQUITIES_PATH", tmp)`; never the real `api/data/equities.json` or `api/data/cache`.
7. The envelope inlines: the row shape, the goldens, the adapter rules (cite `process/context/data-sources/all-data-sources.md:225-252`) and says VERDICT.md/findings.md exist only on `origin/claude/exciting-meitner-hy50kn`.
8. Sanitised fixture: symbol `TEST`, deterministic synthetic walk (fixed seed), same keys, types and timestamp format as the real response; the probe never copies a real number into `s3-probe/out/`.
9. Gates and scope allowlist: see "S3 exact gates".

Test gates: the C3 table below (strategy is one of the three proving strategies; Known-Gap is only ever a named residual via gap-resolution D), then the legacy line form, then exact gates per slice.

### Test gates

gap-resolution: A proven now / B added by this plan's checklist / C deferred to a named later step / D backlog stub (residual, keep-active).

| criterion id | behavior | strategy | proving test | gap-resolution |
|---|---|---|---|---|
| AC-S1-1 | forming candle refetched after TTL and at a bar boundary | Fully-Automated | G-S1-1 `test_forming_candle_refresh_after_ttl`, `test_forming_candle_not_refetched_inside_ttl`, `test_new_bar_boundary_forces_refetch_even_inside_ttl` | B |
| AC-S1-2 | 500+ bar gap catches up in one refresh | Fully-Automated | G-S1-1 `test_500_bar_gap_regression_catches_up`, `test_tail_fetch_uses_since_none_and_latest_limit` | B |
| AC-S1-2r | real Hyperliquid returns the latest bars for `since=None` | Agent-Probe | P-S1-1 (c) on the user PC | C (fallback A-S1-7; stub if not run) |
| AC-S1-3 | 15m/1h/4h trimmed to 200, 1d never | Fully-Automated | G-S1-1 trim tests | B |
| AC-S1-4 | staleness thresholds, 1w judged on its 1d | Fully-Automated | G-S1-1 `test_stale_threshold_per_timeframe_boundary`, `test_one_week_staleness_is_judged_on_its_daily_bar`, `test_old_newest_bar_returns_status_stale` | B |
| AC-S1-5 | payload fields on chart and board, TS mirror, aged cache gets a marker over HTTP | Fully-Automated | G-S1-1 payload tests, G-S1-4, G-S1-8 (flipped deploy case) | B |
| AC-S1-6 | skew once per refresh, warning above 120 s, unknown is silent | Fully-Automated | G-S1-1 skew tests | B |
| AC-S1-6r | real `fetch_time` works and skew is plausible | Agent-Probe | P-S1-1 (b) | C |
| AC-S1-7 | no migration, pairs/legs/BTC unaffected, atomic-write tests intact | Fully-Automated | G-S1-1 legacy test, G-S1-2, G-S1-9 | B |
| AC-S1-8 | empty tail response keeps cache | Fully-Automated | G-S1-1 `test_empty_tail_response_keeps_cache_and_fetched_at` | B |
| AC-S2-1 | chip = current candle open to latest, Monday-anchored week | Fully-Automated | G-S2-1 `test_gain.py` goldens | B |
| AC-S2-2 | N/A with a reason, never 0; real flat is 0.0 | Fully-Automated | G-S2-1 | B |
| AC-S2-3 | UTC ticks, browser-zone independent | Fully-Automated | G-S2-3, G-S2-4 (formatter) | B |
| AC-S2-3r | the island actually draws those labels | Agent-Probe | A-S2-4 screenshot, P-S2-1 (2) | C/D (stub A-S2-4) |
| AC-S2-4 | `Last bar ... UTC, <age>` caption and `stale` marker, coin box and drill-down | Fully-Automated | G-S2-3 component tests | B |
| AC-S2-5 | chips equal the exchange chart | Agent-Probe | P-S2-1 (1) | C |
| AC-S2-6 | E2E thin-history spec matches the new contract | Hybrid | G-S2-8 (precondition: chromium + seeded stack) | B (run: C) |
| AC-S3-1 | parse, non-session days dropped (incl. NYSE traps), weekly derived, never raises | Fully-Automated | G-S3-1 | B |
| AC-S3-2 | missing key -> unavailable, no call | Fully-Automated | G-S3-1 | B |
| AC-S3-3 | `redistributable=false` on result and parquet footer; cache ignored; key never leaks | Fully-Automated | G-S3-1 (incl. A-S3-2 tests), G-S3-5, G-S3-8 | B |
| AC-S3-4 | ticker store separate, no cap, atomic | Fully-Automated | G-S3-1 | B |
| AC-S3-5 | real LSE response matches the parse | Agent-Probe | G-S3-6 + `lse_probe.py` | D (stub `lse-live-shape-verification_NOTE_03-10-26.md`); CONDITIONAL until run |

Legacy line form (existing consumers still parse):
- api freshness core (S1): [Fully-automated: `UV_FROZEN=1 uv run --project api pytest api/tests/data/test_freshness.py api/tests/data/test_ccxt_tail_fetch.py api/tests/data/test_cache_fetched_at_retention.py api/tests/data/test_ccxt_clock_skew.py api/tests/routers/test_screener_freshness_payload.py -q`] | [hybrid: `s1-probe/probe_freshness.py` - precondition: live Hyperliquid egress on the user PC] | [agent-probe: tail semantics, skew, board latency] | [known-gap: none unprobed once P-S1-1 ran]
- web contract mirror (S1/S2): [Fully-automated: `pnpm --filter web test`; `pnpm --filter web exec tsc --noEmit --incremental false`; `cd web && pnpm build:islands`] | [agent-probe: island axis screenshot] | [known-gap: zoom/sharpness (S6)]
- chips and labels (S2): [Fully-automated: `UV_FROZEN=1 uv run --project api pytest api/tests/analytics/test_gain.py api/tests/routers/test_screener_gain_contract.py api/tests/routers/test_screener.py api/tests/analytics/test_momentum.py -q`; `TZ=Pacific/Kiritimati pnpm --filter web exec vitest run lib/__tests__/chart-time-format.test.ts`] | [hybrid: `cd web && pnpm test:e2e -- screener.spec.ts` - precondition: chromium path + seeded stack] | [agent-probe: chip vs exchange] | [known-gap: island label render until probed]
- equities (S3): [Fully-automated: `UV_FROZEN=1 uv run --project api pytest api/tests/data/test_lse_adapter.py api/tests/data/test_equities_store.py -q`] | [agent-probe: `lse_probe.py` on the user PC with `LSE_API_KEY`] | [known-gap: live LSE shape - documented, stub `lse-live-shape-verification_NOTE_03-10-26.md`]

### S1 exact gates (repo root; expected results are for the EVL tester)

| Gate | Command | Expected |
|---|---|---|
| G-S1-1 | `UV_FROZEN=1 uv run --project api pytest api/tests/data/test_freshness.py api/tests/data/test_ccxt_tail_fetch.py api/tests/data/test_cache_fetched_at_retention.py api/tests/data/test_ccxt_clock_skew.py api/tests/routers/test_screener_freshness_payload.py -q` | 31 passed, 0 failed, 0 skipped (5+11+6+5+4) |
| G-S1-2 | `UV_FROZEN=1 uv run --project api pytest api/ -q` | 0 failed; at least 901 passed (870+31, +1 for the flipped deploy case); 1 skipped; 5 deselected; 0 xfailed |
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
| G-S3-1 | `UV_FROZEN=1 uv run --project api pytest api/tests/data/test_lse_adapter.py api/tests/data/test_equities_store.py -q` | 0 failed; exactly 1 skipped (`test_probe_fixture_parses`, only while the probe fixture is absent); adapter file 16 tests (12 planned + 4 from A-S3-2, A-S3-4), store at least 6 |
| G-S3-2 | `UV_FROZEN=1 uv run --project api pytest api/ -q` (RT2, once) | 0 failed; skipped 2 (baseline 1 + the probe-fixture skip); xfailed 1 if S1 is not yet merged, else 0 |
| G-S3-3 | `git diff --check` | exit 0 |
| G-S3-4 | `S3-scope`, `FORBIDDEN`, `S3-gitignore` in the command block below | first two print nothing; third prints exactly `+api/data/equities.json` |
| G-S3-5 | `S3-key-grep` in the command block below | first: only `os.environ` reads; second: prints nothing; tester reads every `print(` in `lse_probe.py` and confirms no argument can carry the key, headers or a URL containing the key (hybrid review) |
| G-S3-6 | `UV_FROZEN=1 uv run --project api pytest api/tests/data/test_lse_adapter.py -q -k probe_fixture_parses -rs` on the real shape file | 1 passed (CONDITIONAL until run on the PC) |
| G-S3-7 | `git check-ignore api/data/equities.json api/data/cache/equities/AAPL/1d.parquet api/data/cache/equities/_probe/x.json` | prints all three paths, exit 0 |
| G-S3-8 | `S3-fixtures` in the command block below | only `lse_candles_synthetic.json`, optionally `lse_candles_probe_shape.json`, and the `s3-probe` script and README; no raw probe output |
| G-S3-9 | `S3-secret-scan` in the command block below | prints nothing |

### Scope and secret-hygiene commands (run from the repo root; the labels above refer to these)

```
# FORBIDDEN (every slice): nothing may match
git diff --name-only origin/main...HEAD | grep -E '^(CLAUDE\.md|AGENTS\.md|README\.md|\.claude/|\.github/|deploy/|api/scripts/|process/MASTER-PLAN\.md|process/context/current-state\.md|process/archive/)'
# (api/scripts/ is forbidden to S1, S2 and S3 alike; S3 edits no script)

# FIXTURES: no modified, deleted or renamed fixture (adds are allowed)
git diff --name-only --diff-filter=MDR origin/main...HEAD | grep -E '/fixtures/'

# S1-scope: every changed file must be on the owned list (prints the strays)
git diff --name-only origin/main...HEAD | grep -vE '^(api/data/(ccxt_adapter|cache|freshness)\.py|api/models/screener\.py|api/analytics/screener_board\.py|web/lib/types/screener\.ts|api/tests/data/(test_freshness|test_ccxt_tail_fetch|test_cache_fetched_at_retention|test_ccxt_clock_skew|test_ccxt_symbol_resolution)\.py|api/tests/routers/test_screener_freshness_payload\.py|api/tests/deploy/test_fresh_deploy_degrade\.py|web/components/screener/__tests__/(ScreenerBoard|DrillDownView)\.test\.tsx|process/general-plans/active/screener-batch1_03-10-26/(s1-probe/.*|screener-batch1-s1_REPORT_[0-9-]+\.md)|process/general-plans/backlog/ohlcv-negative-cache-and-1d-gap-replace_NOTE_[0-9-]+\.md)$'

# S2-scope
git diff --name-only origin/main...HEAD | grep -vE '^(api/analytics/indicators/(gain|momentum)\.py|api/analytics/screener_board\.py|api/models/screener\.py|web/lib/types/screener\.ts|web/lib/(chart-time-format|chart-freshness|island-loader)\.ts|web/islands/simple-lines\.svelte|web/components/chart/(MiniChart|ChartFreshness)\.tsx|web/components/screener/(CoinPanel|DrillDownView|ScreenerBoard)\.tsx|api/tests/analytics/(test_gain|test_momentum)\.py|api/tests/routers/(test_screener_gain_contract|test_screener)\.py|web/lib/__tests__/(chart-time-format|chart-freshness)\.test\.ts|web/components/chart/__tests__/ChartFreshness\.test\.tsx|web/components/screener/__tests__/(ScreenerBoard|DrillDownView)\.test\.tsx|web/e2e/screener\.spec\.ts|process/general-plans/active/screener-batch1_03-10-26/screener-batch1-s2_REPORT_[0-9-]+\.md|process/general-plans/backlog/island-axis-labels-render-check_NOTE_[0-9-]+\.md)$'

# S2-dangling: the deleted functions and constant are gone everywhere
grep -rn -e compute_percent_change -e PCT_CHANGE_MIN_BARS api/analytics api/routers api/tests api/scripts

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

### Failing stubs (Fully-Automated rows only; copy as the red-first start, do not commit as passing)

```
# S1 -- api/tests/data/test_freshness.py
def test_stale_threshold_per_timeframe_boundary(): raise NotImplementedError("NOT IMPLEMENTED - TDD stub: stale strictly above 2700/8100/29700/173700 s, +1 s flips")
def test_one_week_staleness_is_judged_on_its_daily_bar(): raise NotImplementedError("NOT IMPLEMENTED - TDD stub: 1w stale follows the 1d bar")
def test_is_partial_true_inside_bar_false_after_close(): raise NotImplementedError("NOT IMPLEMENTED - TDD stub: is_partial = open + tf > now")
def test_cache_is_fresh_requires_fetch_inside_current_bar(): raise NotImplementedError("NOT IMPLEMENTED - TDD stub: fetched_at must be in the current bar")
def test_forming_ttl_boundary_per_timeframe(): raise NotImplementedError("NOT IMPLEMENTED - TDD stub: TTL 180/300/900/900 s boundary")
# S1 -- api/tests/data/test_ccxt_tail_fetch.py
def test_tail_fetch_uses_since_none_and_latest_limit(): raise NotImplementedError("NOT IMPLEMENTED - TDD stub: since=None, limit=TAIL_LIMIT")
def test_500_bar_gap_regression_catches_up(): raise NotImplementedError("NOT IMPLEMENTED - TDD stub: 15m cache 576 bars behind catches up")
def test_forming_candle_refresh_after_ttl(): raise NotImplementedError("NOT IMPLEMENTED - TDD stub: forming candle refetched after TTL")
def test_forming_candle_not_refetched_inside_ttl(): raise NotImplementedError("NOT IMPLEMENTED - TDD stub: no call inside TTL")
def test_new_bar_boundary_forces_refetch_even_inside_ttl(): raise NotImplementedError("NOT IMPLEMENTED - TDD stub: new bar forces refetch")
def test_non_contiguous_tail_replaces_cache_and_notes_gap(): raise NotImplementedError("NOT IMPLEMENTED - TDD stub: note=gap-replaced")
def test_old_newest_bar_returns_status_stale(): raise NotImplementedError("NOT IMPLEMENTED - TDD stub: status=stale")
def test_failed_fetch_keeps_cache_and_fetched_at(): raise NotImplementedError("NOT IMPLEMENTED - TDD stub: failure leaves cache and sidecar")
def test_explicit_since_path_unchanged_for_backfill(): raise NotImplementedError("NOT IMPLEMENTED - TDD stub: explicit since = today's path")
def test_one_week_derivation_uses_daily_fetched_at(): raise NotImplementedError("NOT IMPLEMENTED - TDD stub: 1w fetched_at = daily's")
def test_empty_tail_response_keeps_cache_and_fetched_at(): raise NotImplementedError("NOT IMPLEMENTED - TDD stub: [] response writes nothing")
# S1 -- api/tests/data/test_cache_fetched_at_retention.py
def test_sidecar_round_trip_and_written_after_parquet(): raise NotImplementedError("NOT IMPLEMENTED - TDD stub: sidecar after parquet")
def test_legacy_parquet_without_sidecar_uses_mtime(): raise NotImplementedError("NOT IMPLEMENTED - TDD stub: mtime fallback")
def test_sidecar_never_newer_than_parquet_after_crash(): raise NotImplementedError("NOT IMPLEMENTED - TDD stub: crash order")
def test_trim_on_write_15m_1h_4h_keeps_newest_200(): raise NotImplementedError("NOT IMPLEMENTED - TDD stub: retain_bars=200")
def test_one_day_bars_are_never_trimmed(): raise NotImplementedError("NOT IMPLEMENTED - TDD stub: 1d untouched")
def test_write_defaults_fetched_at_to_now(): raise NotImplementedError("NOT IMPLEMENTED - TDD stub: default stamp")
# S1 -- api/tests/data/test_ccxt_clock_skew.py
def test_skew_is_host_midpoint_minus_exchange_time(): raise NotImplementedError("NOT IMPLEMENTED - TDD stub: skew arithmetic")
def test_skew_warning_above_120s_only(): raise NotImplementedError("NOT IMPLEMENTED - TDD stub: warn > 120 s")
def test_skew_measured_once_per_15_minutes(): raise NotImplementedError("NOT IMPLEMENTED - TDD stub: 15 min cache")
def test_missing_fetch_time_means_unknown_not_error(): raise NotImplementedError("NOT IMPLEMENTED - TDD stub: no fetch_time = unknown")
def test_fetch_time_exception_means_unknown(): raise NotImplementedError("NOT IMPLEMENTED - TDD stub: exception = unknown")
# S1 -- api/tests/routers/test_screener_freshness_payload.py
def test_chart_series_carries_freshness_fields(): raise NotImplementedError("NOT IMPLEMENTED - TDD stub: 5 chart fields")
def test_unavailable_chart_has_null_freshness(): raise NotImplementedError("NOT IMPLEMENTED - TDD stub: nulls, stale=False")
def test_board_carries_clock_skew_fields(): raise NotImplementedError("NOT IMPLEMENTED - TDD stub: board skew fields")
def test_pydantic_fields_match_typescript_interfaces(): raise NotImplementedError("NOT IMPLEMENTED - TDD stub: py/ts field names equal")
# S2 -- api/tests/analytics/test_gain.py
def test_chip_15m_golden_open_to_latest(): raise NotImplementedError("NOT IMPLEMENTED - TDD stub: 15m chip")
def test_chip_1h_golden(): raise NotImplementedError("NOT IMPLEMENTED - TDD stub: 1h chip")
def test_chip_4h_golden(): raise NotImplementedError("NOT IMPLEMENTED - TDD stub: 4h chip")
def test_chip_1d_is_since_midnight_utc_golden(): raise NotImplementedError("NOT IMPLEMENTED - TDD stub: 1d since 00:00 UTC")
def test_chip_1w_monday_anchor_golden(): raise NotImplementedError("NOT IMPLEMENTED - TDD stub: opens 100/102/101/105 closes 102/101/104/106 -> +6.0%, open_ts 2026-09-28T00:00:00Z")
def test_chip_1w_without_monday_bar_is_na(): raise NotImplementedError("NOT IMPLEMENTED - TDD stub: Monday bar absent -> N/A")
def test_empty_frame_is_na_never_zero(): raise NotImplementedError("NOT IMPLEMENTED - TDD stub: empty -> N/A")
def test_nan_or_zero_open_is_na(): raise NotImplementedError("NOT IMPLEMENTED - TDD stub: bad open -> N/A")
def test_flat_candle_is_real_zero(): raise NotImplementedError("NOT IMPLEMENTED - TDD stub: open==close -> 0.0")
def test_is_partial_and_stale_flags_follow_reference_time(): raise NotImplementedError("NOT IMPLEMENTED - TDD stub: flags")
def test_adapter_status_maps_to_reason(): raise NotImplementedError("NOT IMPLEMENTED - TDD stub: status -> reason")
# S2 -- api/tests/routers/test_screener_gain_contract.py
def test_gain_chip_fields_match_typescript(): raise NotImplementedError("NOT IMPLEMENTED - TDD stub: GainChip py/ts")
def test_percent_change_by_timeframe_equals_chip_pct(): raise NotImplementedError("NOT IMPLEMENTED - TDD stub: legacy dict = chip pct")
# S3 -- api/tests/data/test_lse_adapter.py and test_equities_store.py
def test_parse_documented_row_shape_to_ohlcv_frame(): raise NotImplementedError("NOT IMPLEMENTED - TDD stub: row shape parse")
def test_non_session_days_are_dropped(): raise NotImplementedError("NOT IMPLEMENTED - TDD stub: 2006-11-23, 2007-11-22, 2008-01-01, 2005-03-25, Saturdays out; a Tuesday kept")
def test_session_calendar_nyse_traps(): raise NotImplementedError("NOT IMPLEMENTED - TDD stub: 2010-12-31/2021-12-31/2006-10-09/2005-11-11 kept; 2015-07-03/2022-06-20 dropped")
def test_missing_key_is_unavailable_and_makes_no_call(): raise NotImplementedError("NOT IMPLEMENTED - TDD stub: missing-key")
def test_http_error_or_timeout_never_raises(): raise NotImplementedError("NOT IMPLEMENTED - TDD stub: never raises")
def test_404_ticker_is_bad_symbol(): raise NotImplementedError("NOT IMPLEMENTED - TDD stub: 404 -> bad_symbol")
def test_unsupported_timeframe_is_unavailable(): raise NotImplementedError("NOT IMPLEMENTED - TDD stub: unsupported-timeframe")
def test_result_and_parquet_are_tagged_redistributable_false(): raise NotImplementedError("NOT IMPLEMENTED - TDD stub: result flag and footer attrs")
def test_weekly_is_monday_anchored_from_daily(): raise NotImplementedError("NOT IMPLEMENTED - TDD stub: weekly derivation")
def test_cache_is_fresh_for_six_hours_then_refetched(): raise NotImplementedError("NOT IMPLEMENTED - TDD stub: 6 h TTL")
def test_rsi_on_equity_bars_via_compute_rsi(): raise NotImplementedError("NOT IMPLEMENTED - TDD stub: RSI via existing compute_rsi")
def test_cache_path_is_gitignored(): raise NotImplementedError("NOT IMPLEMENTED - TDD stub: git check-ignore")
def test_api_key_never_in_result_repr_logs_or_exception_text(): raise NotImplementedError("NOT IMPLEMENTED - TDD stub: sentinel key absent everywhere")
def test_request_uses_explicit_timeout_and_header_auth(): raise NotImplementedError("NOT IMPLEMENTED - TDD stub: timeout <= 15 s, key in header only")
def test_committed_lse_fixtures_are_synthetic_only(): raise NotImplementedError("NOT IMPLEMENTED - TDD stub: symbol TEST or SYNTH only")
def test_equities_store_add_remove_idempotent_uppercase_invalid_over30_atomic_override(): raise NotImplementedError("NOT IMPLEMENTED - TDD stub: store behaviours, split into the planned cases")
# test_probe_fixture_parses is Agent-Probe (skipif fixture absent): no stub.
```
```
// S2 -- vitest
test("should format UTC ticks per timeframe, day-boundary tick and the year rule, browser-zone independent", () => { throw new Error("NOT IMPLEMENTED - TDD stub: chart-time-format") })
test("should caption forming, closed and no-bar cases against server_time", () => { throw new Error("NOT IMPLEMENTED - TDD stub: chart-freshness") })
test("should show the stale marker only when stale", () => { throw new Error("NOT IMPLEMENTED - TDD stub: ChartFreshness stale-marker") })
test("should render gain-chip-1d from gain_by_timeframe and the caption on board and drill-down", () => { throw new Error("NOT IMPLEMENTED - TDD stub: ScreenerBoard/DrillDownView") })
```

### Red-today evidence (origin/main af7888f; scratch scripts only, nothing committed)

| Criterion | Red today? | Evidence |
|---|---|---|
| AC-S1-1 forming candle | RED (behaviour) | 1h cache with a forming newest bar: `fetch_ohlcv` made 0 exchange calls (base `_cache_is_fresh` True inside the bar) |
| AC-S1-2 gap | RED (behaviour) | 15m cache 6 days behind: one call `(since=<cached max>, limit=500)`; cache still 19 h 15 min (76 bars) behind afterwards |
| AC-S1-3 trim | RED (behaviour) | a 500-bar 15m pull kept 500 bars |
| AC-S1-4 stale, AC-S1-5 fields, AC-S1-6 skew | RED (missing symbols) | `api.data.freshness` absent; `ChartSeries` fields are `[available, price, reason, sma]`; board fields `[active_benchmark, coins, timeframe]`; no `_now`, `last_clock_skew`, `read_fetched_at`; `OhlcvResult` has 5 fields; `write_ohlcv(symbol, timeframe, df)` and `_cache_is_fresh(cached, timeframe)` signatures unchanged |
| AC-S1-5 over HTTP (G-S1-8) | RED today | `pytest api/tests/deploy/test_fresh_deploy_degrade.py --runxfail -k staleness_marker` -> 1 failed: "an aged cache is displayed with no staleness marker" (`available: True`, `reason: None`) |
| AC-S1-7 | GREEN today (regression guard) | baseline 870 passed |
| AC-S1-8 empty tail | not runnable today (no tail path) | new test, red by missing behaviour |
| AC-S2-1 / AC-S2-2 | RED (value / module) | golden Mon 28 Sep - Thu 1 Oct frame: expected 1w +6.0% (open 100, close 106; confirmed via `_derive_weekly_from_daily`); base returns 1w `None` and 1d `3.92` (first-to-last close); `gain.py` absent. The existing thin-slot test (`test_screener.py:205`) is GREEN today and must stay green |
| AC-S2-3 / AC-S2-4 | RED (modules absent) | `web/lib/chart-time-format.ts`, `chart-freshness.ts`, `web/components/chart/ChartFreshness.tsx` do not exist |
| AC-S2-6 | GREEN today, RED after S2 without A-S2-1 | arithmetic in D8 |
| AC-S3-1..4 | RED (modules absent) | `lse_adapter.py`, `equities_store.py` do not exist; `api/data/equities.json` not git-ignored (needs the line) |
| AC-S1-2r, AC-S1-6r, AC-S2-3r, AC-S2-5, AC-S3-5 | NOT-RUN | live exchange / vendor / browser; see "Not verifiable offline" |

### Unverified facts: owner and deterministic fallback

| # | Fact | Status after VALIDATE | Owner | Fallback |
|---|---|---|---|---|
| U1 | ccxt `since=None` returns the LATEST bars | request level VERIFIED offline (probe 1); response level (what Hyperliquid returns, any server cap) unverified | P-S1-1 (c) | A-S1-7 `_tail_since` helper; `stale` status makes a wrong assumption visible |
| U2 | `fetch_time` works on Hyperliquid | method and capability flag exist (probe 2); runtime result and latency unverified | P-S1-1 (b) | missing or failing = unknown, no warning (tests exist) |
| U3 | LayerChart `Axis` `format` on a `scaleUtc` bottom axis | unverifiable offline (node_modules blocked to scouts; island not mountable in jsdom; `build:islands` compiles Svelte but does not type-check props; no precedent of `scaleUtc` in the repo; `d3-scale` v4 exports it per its public API, not confirmed locally) | A-S2-4 spike plus screenshot, then P-S2-1 (2) | 3-step chain in A-S2-4; DOM captions and `stale` marker ship regardless |
| U4 | LSE REST paths, auth scheme, timestamp hour, weekly support | ASSUMED from the SDK | `lse_probe.py` (Step 0, user PC) | adapter against the documented shape with an injectable transport and isolated URL/auth constants; AC-S3-5 stays CONDITIONAL with the stub |

### Not verifiable offline (gates that cannot be confirmed here)

Live Hyperliquid responses, latency and rate limits; live LSE; LayerChart label rendering on a UTC axis; chip versus the exchange chart; GitHub CI jobs; Playwright E2E (not run: it builds into `web/`, outside `process/`); every new test (the code does not exist yet). Everything else listed in "V1-V3 evidence" ran here.

### Open gaps

- U1/U2 real-world checks pending the S1 PC probe; U3 and AC-S2-5 pending the S2 probe; AC-S3-5 pending the LSE probe (each has an owner above).
- D7 board latency vs the 10 s web timeout (decision U-5); D18 1d gap-replace and failed-fetch retry cost (advisory stub).
- known-gap: live LSE end-to-end: documented as NEW PLAN REQUIRED - see backlog/lse-live-shape-verification_NOTE_03-10-26.md (written by the S3 worker).
- known-gap: island axis label render: documented - see backlog/island-axis-labels-render-check_NOTE_<dd-mm-yy>.md (written by the S2 worker if A-S2-4 step 3 is reached).
- Special NYSE closures not modelled (caveat `special-closures-not-modelled`).

### What This Coverage Does NOT Prove

- G-S1-1/2 use fake exchanges: they prove our tail, TTL, trim and skew logic, NOT that Hyperliquid returns the latest bars for `since=None`, that `fetch_time` works, nor real latency or rate-limit behaviour (P-S1-1).
- G-S1-8 proves the aged-cache marker through FastAPI with a dead exchange stub, not with a live feed.
- G-S1-3..5 and G-S2-3..6 prove types, jsdom behaviour and that the island compiles; jsdom never mounts the island, so they do NOT prove axis labels are drawn, readable or in UTC on screen, nor zoom or sharpness (S6).
- G-S2-1 proves chip arithmetic on synthetic frames, NOT agreement with the exchange chart (P-S2-1).
- G-S2-8, when run in a container, uses seeded bars; it does not prove live data.
- G-S3-1 uses a synthetic fixture and a mock transport: it proves our parsing, filtering, tagging and key hygiene, NOT the real LSE shape, auth scheme, timestamp hour or weekly support (G-S3-6 and the probe); special closures and corporate-action adjustments are not modelled.
- None of the gates prove behaviour with the user's real cache files beyond the P-S1-1 listing.

Accepted by: PENDING - user acceptance required (no acceptance has been given in this session). Conditions needing the user's acceptance:
- U-1 [S1, S2]: S1 and S2 may merge with AC-S1-2r/6r and AC-S2-3r/5 as probe-pending residuals; both slices stay at `review` until the PC evidence exists (already in Phase Completion Rules).
- U-2 [S3]: S3 stays CONDITIONAL until the live probe passes `test_probe_fixture_parses`, and S3 is accepted as RT2 plus the A-S3 secret gates instead of an RT4 evidence pack.
- U-3 [all]: the amendments A-ALL, A-S1, A-S2, A-S3 are binding without a plan-body rewrite (alternative: run a plan-agent supplement for the eleven gaps; the SUPPLEMENT REQUEST is in the VALIDATE hand-off).
- U-4 [S2]: G-S2-8 (E2E) is hybrid; NOT-RUN with a reason is acceptable and the PC probe covers it.
- U-5 [S1]: the user decides how to handle board latency until S8: (a) accept the risk that a board opened after 15 min idle can exceed the 10 s web timeout and needs a reload, using `api/scripts/refresh_cache.py` by hand beforehand; or (b) widen S1 with `web/lib/api/screener.ts` (client timeout) and its tests; or (c) lengthen the TTLs (AC-13 is the user's rule, so this needs the user's word). Recommended: (a) plus pulling S8 forward.

Mechanics: first-pass CONDITIONAL, so `results.tsv` has the baseline row only (header + row 0 = 2 lines; `PHASE_COMPLETE: VALIDATE` needs 3 or more, or the user's acceptance). One phrase outside this section was edited (Resume item 3, D16: it spelled out the literal PASS-gate string, which would make the mechanical gate check count 1 on a CONDITIONAL plan). `## Status`/Resume wording elsewhere in the plan body is still pre-VALIDATE; the planner refreshes it at hand-off.

## Autonomous Goal Block

SESSION GOAL: screener batch 1 - S1 freshness core, S2 current-candle chips and UTC labels, S3 LSE equities adapter (tested adapter, live shape pending probe)
Charter + umbrella plan: N/A - single plan (no umbrella with a Stable Program Goal exists)
Autonomy: after the user accepts U-1..U-5 the planner writes three worker envelopes (master-planner.md section 8, at most 8,000 bytes each, citing the slice and contract line ranges) and spawns S1 and S3 workers (opus; subagents sonnet, capped lane for S1 and S2 only); S2 only after the S1 merge SHA exists; workers run their gate lists once after the last edit and stop on the same failure twice.
Hard stop conditions / safety constraints:
- No envelope is written and no worker is spawned until the user accepts U-1..U-5 (Gate is CONDITIONAL, first pass).
- S2 is never spawned before the S1 merge SHA exists; S3 never touches `api/data/cache.py`, `ccxt_adapter.py` or `api/pyproject.toml`.
- Any diff touching CLAUDE.md, AGENTS.md, README.md, `.claude/`, `.github/`, `deploy/`, `api/scripts/` (S1) or the forbidden lists stops at `review`.
- The LSE_API_KEY value is never printed, logged, committed or written to a file; no real LSE price is ever committed.
- Push, merge, deploy, branch deletion or spend above 15 USD per slice or 45 USD for the program needs the user's approval.
Next phase: EXECUTE (worker envelopes) - plan path process/general-plans/active/screener-batch1_03-10-26/screener-batch1_PLAN_03-10-26.md
Validate contract: the section above, inline (CONDITIONAL, outer-pvl, 2026-10-03)
Execute start: S1 worker: `UV_FROZEN=1 uv run --project api pytest <G-S1-1 files> -q` red run on the untouched base, then implement; S3 worker: commit `s3-probe/` first; probe: P-S1-1, P-S2-1 and `lse_probe.py` on the user PC | high-risk pack: no (U-2 records the RT2 call)

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
3. Validate-contract status: written 03-10-26, first pass CONDITIONAL (see the Validate Contract section; user acceptance U-1..U-5 pending).
4. Context loaded: SPEC, INNOVATE, findings note, operating-instructions.md, master-planner.md, decisions.md, all-tests.md, LSE VERDICT and findings.
5. Next step for a fresh agent: then ENTER VALIDATE MODE; after VALIDATE and explicit approval write the three envelopes and spawn S1 and S3 (S2 after the S1 merge). Next instruction (RIPER-5): say **ENTER VALIDATE MODE**.
