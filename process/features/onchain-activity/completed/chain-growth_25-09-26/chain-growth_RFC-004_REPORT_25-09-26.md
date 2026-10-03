---
phase: rfc-004
date: 2026-09-26
status: COMPLETE
feature: onchain-activity
plan: process/features/onchain-activity/completed/chain-growth_25-09-26/chain-growth_PLAN_25-09-26.md
---

# chain-growth RFC-4: floor/ramp analytics + `GET /api/onchain/growth`, `/chains`

**TL;DR:** RFC-4 is built exactly to the Stage 0 report and the approved decisions D1–D5.
- On the real cache it reproduces every Stage 0 date.
- With D3, the current state reads `floor` on **2 of 10** series (both Polygon), down from 6 of 10.
- Tests: 44 new tests. The api suite is **511 passed / 5 deselected** (baseline 467 / 5). The web suite is **110 passed**.
- Evidence pack: written, with the review decision PENDING.
- Not committed.

## What Was Done
| File | Change |
|---|---|
| `api/analytics/onchain/__init__.py` | new package |
| `api/analytics/onchain/growth.py` | D1/D3 constants in one place, with a docstring citing the Stage 0 report and `rfc004_stage0_sweep_output.json`. Also: `to_daily`, `post_launch` (D2), `ema` (gap-skipping), `history_days`, `gate_met_on`, `detect_floor_ramp`. |
| `api/analytics/onchain/comparison.py` | `rebase_index` (index=100 at start, `rebased_late`, log-safe), `pct_above_rolling_low`, and `ComparisonSeries`, which has no raw field (AC-13). |
| `api/analytics/onchain/response.py` | Builds both responses from `read_onchain_series` and `load_chains` only. Also holds the stale rule (> 3 days since the last `as_of_utc`) and the L2BEAT divergence summary. |
| `api/models/onchain_activity.py` | Pydantic models following the Stage 0 §5 shape. |
| `api/routers/onchain_activity.py` | `GET /api/onchain/growth?metric=&start=` and `GET /api/onchain/chains`. |
| `api/main.py` | +1 import name, +1 `include_router` line. |
| `api/data/chains.json` | D4: Polygon `launch_date` set to `2020-05-30`. |
| `api/tests/analytics/onchain/{test_growth,test_comparison}.py` + 3 frozen CSV fixtures | 30 tests |
| `api/tests/routers/test_onchain_activity_router.py` | 14 tests |
| `harness/rfc-004/*.json` | 5-file risk evidence pack (E3), review decision PENDING |

The throwaway sweep script and its JSON output stay in the task folder, not in `api/`.

### Decisions as implemented
- **D1:** N=180, R=0.25, M=14, S=180 on EMA28. The history gate is `MIN_HISTORY_DAYS = N + M = 194`.
- **D2:** Pre-launch points:
  - They stay in `series.points` with `pre_launch: true`, `ema7` and `ema28` set to null.
  - They are excluded from the floor/ramp rule, the comparison index, `pct_above_low` and the history gate.
  - This is one rule for all chains, driven by `launch_date`.
- **D3:** `FLOOR_STATE_PCT = 0.10`, a separate constant from the ramp-recovery R.
  - Current real-cache states for `active_addresses`:
    - ethereum: neutral
    - base: neutral
    - arbitrum: neutral
    - optimism: ramping
    - **polygon: floor**
    - robinhood: not-enough-history
  - Current real-cache states for `transactions`:
    - ethereum: ramping
    - base: ramping
    - arbitrum: neutral
    - optimism: neutral
    - **polygon: floor**
    - robinhood: not-enough-history
  - **`floor` now appears on 2 of 10 gated series (Stage 0 at 25%: 6 of 10).**
- **D4:** done (the Polygon `launch_date` above).
- **D5:** The comparison works like this:
  - `normalization_method: "index-100-at-start-ema28"`.
  - `start` defaults to the latest grid date minus 365 days.
  - `log_scale_default: true`.
  - `rebased_late` is true, for example, for Robinhood.
  - The alternative is `pct_above_low_values`, with `alternative_method: "pct-above-180d-low-ema28"`, supplied in the same series.

### Real-cache smoke check (`build_growth_response`, main @ 7143733)
- The events equal the Stage 0 table, for example:
  - ETH daa: 2022-06-30→08-08, 2023-07-29→2024-03-15, 2024-09-26→12-19.
  - Arbitrum tx: 2023-09-17→11-27, 2026-05-31→07-09.
  - Base daa: 2025-04-23→05-24.
- Robinhood's `gate_met_on` is **2027-01-10**. Stage 0 said about 01-11, an off-by-one: the gate is met on the 194th inclusive day, 07-01 + 193.
- L2BEAT divergence over the last 90 days (median |%|): base 0.0064, arbitrum 0.0466, optimism 0.0177, robinhood 0.0355.
- Payload: about 1.36 MB uncompressed per metric. It is gzip'd by the existing middleware.

## Test Gate Outcomes
- `uv run --project api pytest api/tests/analytics/onchain -q` → **30 passed**. Coverage:
  - constants;
  - EMA does not fill gaps;
  - V-shape → 1 event;
  - flat series → none;
  - a sub-R dip → none;
  - merge of floors closer than S days;
  - declining and neutral states;
  - the gate at 193 and 194 days, plus `gate_met_on`;
  - the gate counts only post-launch days;
  - a pre-launch ramp-from-zero is excluded;
  - the stale boundary at exactly 3 days;
  - rebase / `rebased_late` / log-safety / grid alignment / the AC-13 no-raw-field check;
  - **real-data regression** on fixtures frozen from 7143733: the ETH daa, Arbitrum tx and Base daa headline dates.
- `uv run --project api pytest api/tests/routers/test_onchain_activity_router.py -q` → **14 passed**. Coverage:
  - shape and `grid_dates`/`gap_before` sync, including a real 3-day gap;
  - disabled chains omitted;
  - unavailable chains returned with a reason and no series (never zero-filled);
  - `no-archived-data`;
  - pre-launch flag and the history gate;
  - `rebased_late`;
  - cross-check is tx-only and display-only;
  - comparison defaults and `start`;
  - stale;
  - **422** for a bad metric, a malformed start and a future start;
  - **gzip** `content-encoding`;
  - **read-only**: the real `httpx.HTTPTransport` is blocked, and cache-tree mtimes are unchanged after a request;
  - `/chains`;
  - existing routes unchanged, via the openapi paths;
  - Polygon's `launch_date`.
- `uv run --project api pytest api/ -q` → **511 passed, 5 deselected** (467 + 44).
- `pnpm --filter web test` (run as `pnpm test` inside `web/`) → **110 passed, 16 files**.
- Evidence pack: `validate-risk-artifacts.mjs harness/rfc-004` fails only on the intentionally PENDING decision.

## Plan Deviations (all within blast radius, new files or additive)
1. The new `api/analytics/onchain/response.py` isn't in the plan touchpoints. It keeps the router thin, following the regime `components_response.py` precedent.
2. The plan asked for a `dtype=object` regression test. This RFC builds no pandas frame with mixed `str`/`None` columns: labels live only in Pydantic models. There is nothing to regress, so no test was added.
3. `max_gap_days` is a constant 1 (daily cadence), so any missing day breaks the line. Real gaps exist: Polygon up to 13 days, Base up to 4.
4. The `pct_above_low_values` alternative ships inside each comparison series rather than as a separate block.
5. The test path is `api/tests/routers/test_onchain_activity_router.py`, following the repo layout. The plan named only the file.
6. Robinhood's `gate_met_on` is 2027-01-10, not the Stage 0 "about 01-11" (see the smoke check).

The plan-text conflicts from Stage 0 §6 still need to be written into the plan at UPDATE PROCESS.

## What Was Skipped or Deferred
- RFC-5 (frontend) was not started, as instructed.
- The AC-14 real-data visual check belongs to RFC-6 (user side).

## Test Infra Gaps Found
- The evidence-pack validator can't record PENDING as valid, which is expected.
- `pnpm --filter web test` from the repo root: I ran `pnpm test` in `web/`, which is the equivalent.

## Closeout Packet
- **Plan:** the path in the frontmatter.
- **Verified:** all automated gates, plus the real-cache smoke check.
- **Unverified:** the user review of the API, and the AC-14 visual check.
- **Classification:** Keep in active/testing. Next step: EVL (vc-tester), then RFC-5 Stage 0.
- **Follow-up stubs:** none. CONTEXT_PARTIAL: none.

## Forward Preview
### Test Infra Found
- Temp `chains.json` + `load_chains(path)`, monkeypatched into `response.load_chains`.
- `isolated_cache` + `merge_onchain_series` for the synthetic archive.
- Block `httpx.HTTPTransport.handle_request` (not `Client.send`; TestClient is a Client).
- Use `app.openapi()["paths"]` for the route list (`app.routes` contains `_IncludedRouter`).
### Blast Radius Changes
- New: `api/analytics/onchain/` (4 files), `api/models/onchain_activity.py`, `api/routers/onchain_activity.py`, 3 test files and 3 fixtures.
- Modified: `api/main.py` (+2 lines), `api/data/chains.json` (1 value).
- `cache.py` is untouched.
- Narrative, regime and screener are unchanged.
### Commands to Stay Green
- `uv run --project api pytest api/ -q` → 511 passed / 5 deselected.
- `cd web && pnpm test` → 110.
### Dependency Changes
- None.
### RFC-5 contract notes
- There is one metric per request.
- The comparison arrays are aligned to `grid_dates`, with `null` meaning no line.
- `pre_launch` points should be shaded.
- Render `floor_ramp.gate_met_on` as a "markers from …" note.
- Render the attribution string page-level.
- L2BEAT: render only `cross_check` as a chip.
