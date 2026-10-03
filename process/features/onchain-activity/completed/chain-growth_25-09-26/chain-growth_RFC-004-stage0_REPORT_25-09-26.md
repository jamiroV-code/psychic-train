---
phase: rfc-004-stage0
date: 2026-09-26
status: COMPLETE
feature: onchain-activity
plan: process/features/onchain-activity/completed/chain-growth_25-09-26/chain-growth_PLAN_25-09-26.md
---

# chain-growth RFC-4 Stage 0: floor/ramp constants on real data + API proposal

**BLUF:** The recommended floor/ramp default is **N=180, R=25%, M=14, S=180** on a 28-day EMA. On the real archive it marks the known history and little else:
- Ethereum's 2022-06 bear low.
- The mid-2023 lows, followed by the early-2024 ramp.
- Arbitrum's 2023-10 low, followed by the 2023-12 ramp.
- Base's 2025-04 low.

The minimum-history gate is **N+M = 194 post-launch days**. Robinhood has 87 post-launch days, so it gets no marker until about **2027-01-11**.

Pre-launch data is not a Robinhood-only issue. Base, Arbitrum and Optimism also have points before their `launch_date`. They get one general rule: keep those points and flag them, but exclude them from the analytics.

No code has been written in `api/`. Stopping for go-ahead.

## 1. Data used
All series were read with `read_onchain_series`, from the archive on `main` @ `7143733`.

| series | rows | first | last | max gap |
|---|---|---|---|---|
| growthepie ethereum daa/tx | 2460 | 2020-01-01 | 2026-09-25 | 1 |
| growthepie polygon daa/tx | 2292 | 2020-05-30 | 2026-09-25 | **13** |
| growthepie arbitrum | 1946 | 2021-05-29 | 2026-09-25 | 1 |
| growthepie optimism | 1780 | 2021-11-11 | 2026-09-25 | 1 |
| growthepie base | 1190 | 2023-06-15 | 2026-09-25 | **4** |
| growthepie robinhood daa / tx | 94 / 104 | 2026-06-24 / 2026-06-14 | 2026-09-25 | 1 |
| l2beat arb / op / base / robinhood tx | 1947 / 1780 / 1199 / 149 | 2021-05-28 / 2021-11-11 / 2023-06-15 / 2026-04-30 | 2026-09-25 | 1 |

What the gaps mean:
- Real gaps exist (Polygon up to 13 days, Base up to 4). `gap_before` and `max_gap_days` are therefore needed, not just decorative.
- The EMA skips missing days (`ignore_na`). It is never zero-filled.

## 2. Floor/ramp rule prototyped
The throwaway script is `rfc004_stage0_sweep.py` in this folder. Its full output is `rfc004_stage0_sweep_output.json`, covering 36 parameter sets × 12 series.

Rule, applied to the EMA28 of the post-launch series. It is causal and zig-zag shaped:
1. **Floor candidate:** the lowest EMA point that is also the trailing **N**-day low.
2. **Ramp confirmed:** the EMA stays at or above floor × (1+**R**) for **M** consecutive days. The marker is written as `floor_date` plus `ramp_date`.
3. **Re-arm:** a new floor search starts only after the EMA falls **R** below its post-ramp peak.
4. **Spacing:** two floors less than **S** days apart are merged, keeping the lower one.
5. **Current state:**
   - `not-enough-history` if the series has fewer than N+M days;
   - otherwise `ramping` if the rule is in ramp mode and EMA7 ≥ EMA28;
   - otherwise `floor` if the series is within R of its N-day low;
   - otherwise `declining` if EMA7 < EMA28;
   - otherwise `neutral`.

### Sweep evidence (total confirmed floor→ramp events across 12 series)
| N \ R | 15% | 25% | 40% |
|---|---|---|---|
| 90 | 44–50 | 32–36 | 20–22 |
| 180 | 26–28 | **19–21** | 14–16 |
| 365 | 13 | 10 | 7–8 |

M (7 vs 14) and S (90 vs 180) change the count by at most 4. **N and R drive the result**, so only those two need justification.

### Dates for the three closest candidates (growthepie, floor → ramp)
| series | N90 R25 | **N180 R25 (recommended)** | N365 R25 |
|---|---|---|---|
| ETH daa | 2020-09, **2022-06-30→08-08**, 2023-07-29→2024-03-15, 2024-09-26→12-19 | **2022-06-30→08-08**, 2023-07-29→2024-03-15, 2024-09-26→12-19 | 2022-06, 2023-07 |
| ETH tx | 2023-01-03→2024-04-01 | same | same |
| Polygon daa | 2021-01, 2022-07-30, 2023-02-23, 2025-01-01 | 2022-07-30→10-14, 2025-01-01→07-06 | none |
| Arbitrum tx | 2021-12, 2023-09-17, 2024-09-17, 2026-05-31 | **2023-09-17→11-27**, 2026-05-31→07-09 | 2026-05-31 |
| Arbitrum daa | 4 events | 2023-10-26→12-01, 2025-05-18, 2026-01-25 | 2 |
| Optimism daa | 5 events | 2024-08-20→2025-02-21, 2025-04, 2026-01, 2026-08 | 2 |
| Base daa / tx | 2 / 3 | **2025-04-23→05-24** / 2026-08-10→09-16 | 0 / 1 |
| Robinhood | not-enough-history | not-enough-history | not-enough-history |

What each candidate gets right or wrong:
- **N90** keeps 2020–21 micro-dips, such as ETH 2020-09 and Polygon 2021-01. These are noise at the plan's use case: one "which chain bottomed and is ramping" read per cycle.
- **N365** loses real events. It drops the Polygon 2022 low, the Arbitrum 2023 low and the Base 2025 low. It also requires 379 days of history, which pushes every new chain back a year.
- **N180 R25** keeps the events a trader would name:
  - the 2022 bear low (ETH, Polygon);
  - the 2023 trough → 2024 activity ramp (ETH, Arbitrum Q4-2023 inscriptions/Dencun run-up);
  - Base's 2025-04 low.
- **R40** lags too much. For example, ETH ramp confirmation moves to 2025-06.
- **Not overfitting:** the recommendation sits in the middle of both ranges. It is not the argmax of any score, and no per-chain tuning is used.

**Honest caveats. These go to the AC-14 Agent-Probe or user eyeball:**
- **Arbitrum and Optimism get no 2022 floor.** Both grew through 2022, so this is correct, not a miss.
- **ETH tx confirms its 2023-01 floor only on 2024-04-01.** The recovery was a slow grind, and a lag of about 450 days is expected under a 25% threshold.
- **Optimism daa fires 4 times since 2024.** That series is noisy. It is acceptable, but it is the weakest series.
- **The current state is `floor` for 6 of 10 series.** The criterion "within 25% of the 180-day low" is broad. Decision D3 below covers this.

## 3. Pre-launch data and the minimum-history gate
**Finding:** some growthepie series start before the chain's configured `launch_date`. Base starts 2023-06-15 against an 08-09 launch, Arbitrum 05-29 against 08-31, Optimism 11-11 against 12-16. Robinhood starts in June against a 07-01 launch, and in April on L2BEAT. Those early values are testnet or genesis noise, for example Base daa [5, 1, 2, 2, 4]. If they were kept in the analytics, every chain would open with a fake "floor→ramp" from near zero.

**Proposal (general rule, no per-chain branch; consistent with ADR-4):**
- The raw panel shows **all** points. Points before `launch_date` carry `pre_launch: true`, and the UI shades them.
- Floor/ramp, the comparison index and the gate count **only post-launch points**. A chain with a null `launch_date` counts from its first point.
- The default view starts at the page's range start, and a chain's line starts at its `launch_date`. Pre-launch data stays reachable by zooming out.
- **Gate:** there must be at least N+M = **194** post-launch days, per (chain, metric). Robinhood has 87 now (07-01→09-25), so its state is `not-enough-history` with `gate_met_on: 2027-01-11`. That field gives the UI a concrete "markers from about Jan 2027" note.
- Polygon's `launch_date` is null in config. growthepie starts 2020-05-30, which is Polygon PoS mainnet, so the null costs nothing. Setting it is optional (D4).

## 4. Normalised comparison
- The 1-year rebased EMA28 spans an index range of **17 → 264** across chains, a factor of about 15. Raw DAA ranges from 40k (OP) to 670k (ETH). Raw tx ranges from 1.5M to 9.4M.
- **Proposal (primary):** index each post-launch EMA28 series to **100 at the comparison start date**. The start date defaults to the start of the visible range, and the user can pick it.
  - A chain with no post-launch data on that date is rebased at its first post-launch point.
  - That chain is flagged `rebased_late: true`, so the index is never back-filled.
  - **Log y-axis on by default:** equal ratios then look equal, and the 15× spread stays readable. A linear toggle remains.
  - `normalization_method: "index-100-at-start-ema28"`.
- **Secondary toggle (cheap, same data):** `pct_above_rolling_low`, computed as EMA28 / 180-day low − 1. It is bounded, scale-free and shows the floor/ramp signal directly. It needs no start-date choice.
- AC-13 holds by construction: the comparison series types carry only `index_values`, never a raw value.

## 5. API proposal (ADR-7 shape, from `api/models/regime.py`)
Proposed `GET /api/onchain/growth?metric=active_addresses|transactions&start=YYYY-MM-DD`:
- `metric` is the selector. There is one metric per request, which keeps the payload and `grid_dates` small. The default is `active_addresses`.
- `start` sets only the comparison rebase date.

```
OnchainGrowthResponse
  metric, grid_dates[str], as_of_utc, attribution: "Source: growthepie, https://www.growthepie.com."
  params: {ema_span:28, window_days:180, recovery_pct:0.25, sustain_days:14, spacing_days:180}
  chains[]:
    id, label, launch_date|null, limited_history, status: "ok"|"unavailable"|"stale"
    unavailable_reason|null         # solana/bnb/tron -> "source-unavailable"; no points
    history_start_date|null         # first post-launch point (AC-8)
    series|null: {source:"growthepie", method, redistributable:true, max_gap_days,
                  points[{date, value, ema7|null, ema28|null, gap_before, pre_launch}]}
    floor_ramp: {state, events[{floor_date, ramp_date}], min_history_days:194,
                 history_days, gate_met_on|null}
    cross_check|null: {source:"l2beat", redistributable:false, display_only:true,
                       latest_divergence_pct, median_abs_divergence_pct_90d}
  comparison: {normalization_method, start_date, log_scale_default:true,
               series[{chain_id, rebased_late, index_values[float|null] aligned to grid_dates}]}
```

- **Staleness:** a series is `stale` when its latest `as_of_utc` is older than 3 days. This follows the RFC-3 deviation 5 (derive from age).
- **Unavailable chains:** chains with `source: none` are listed with a reason and no series, and are never zero-filled (AC-7).
- **L2BEAT cross-check:** it is a display-only divergence summary. The real 90-day median |Δ| is 0.006–0.05%, with a maximum of 0.89% (Optimism).
  - It is **not** a series and is never redistributed (the verdict forbids both).
  - Its only UI role is a "2 sources agree within X%" chip.
- **`GET /api/onchain/chains`:** returns the validated `load_chains()` list with `id`, `label`, `enabled`, `launch_date`, `limited_history`, per-metric `source` / `unavailable_reason`, and `cross_check` source.
- **Dtype discipline:** `source`, `method` and `unavailable_reason` are built with `dtype=object`, and a regression test covers this.

## 6. Files and tests
The files change from the plan's names because of the fallback. There is no `new_addresses` metric.

New files:
- `api/analytics/onchain/{__init__,growth,comparison}.py`
- `api/models/onchain_activity.py`
- `api/routers/onchain_activity.py`

Changed file: `api/main.py`, one additive router mount.

Tests:
- **`test_growth.py`**, pure functions on synthetic series:
  - EMA does not fill gaps;
  - V-shape → one event on the exact dates;
  - dip below spacing → merged;
  - under 194 days → `not-enough-history` plus `gate_met_on`;
  - pre-launch points excluded;
  - a flat series gives no events.
- **Real-data regression, decided YES:** a small checked-in fixture holding the EMA28 inputs for ETH daa and Arbitrum tx, frozen from `7143733`. It asserts the recommended set reproduces the dates in §2, `2022-06-30→2022-08-08` and `2023-09-17→2023-11-27`.
  - This is the `leg_boundary` confirming-backtest pattern.
  - A fixture is used rather than the live cache, because the nightly archive drifts.
- **`test_comparison.py`:**
  - rebase math;
  - `rebased_late`;
  - log-safety (index > 0 or null);
  - the type-level no-raw-field check (AC-13).
- **`test_onchain_activity_router.py`:**
  - shape;
  - `grid_dates` / `gap_before` sync;
  - unavailable chains;
  - metric validation (422);
  - stale derivation;
  - dtype regression;
  - a route-list snapshot proving `/regime`, `/narrative` and `/screener` are unchanged.

### Plan-text conflicts (for UPDATE PROCESS)
1. The plan's response example uses `daa`/`new_addresses`/`tx_count`. The real names are `active_addresses`/`transactions`, and `new_addresses` is dropped (verdict).
2. The plan uses `"source": "dune"`, `"method": "bounded-lookback first-seen"`. Both are gone.
3. The plan's `normalization_method: "indexed-to-28d-baseline"` becomes `index-100-at-start-ema28`, with the `pct_above_rolling_low` toggle.
4. The plan puts `floor_ramp` per chain. This proposal puts it per chain **and per metric**, one metric per request. DAA and tx disagree often, for example ETH daa=`floor` while ETH tx=`ramping`.
5. ADR-4 says "% off rolling N-day low sustained M days". The final rule adds a re-arm step and trough spacing, so it doesn't re-fire every day.
6. ADR-4's "Robinhood day one" gate is generalised to post-launch days. It also covers the pre-launch rows on Base, Arbitrum and Optimism.

## Decisions for the user
- **D1:** Accept the default constants **N180 / R25 / M14 / S180** on EMA28? (Alternatives: N90 is more sensitive; N365 keeps only major cycles.)
- **D2:** Pre-launch points: keep them shaded in the raw panel and exclude them from the analytics (recommended)? The other option is to drop them from the response entirely.
- **D3:** The current state `floor` means "within 25% of the 180-day low". Keep it, or tighten it to 10% so that `floor` is rarer? (It is currently 6/10 series.)
- **D4:** Set Polygon's `launch_date` to 2020-05-30 in `chains.json`? This is cosmetic.
- **D5:** Comparison default: index=100 at range start, with log scale on by default and a % above rolling low toggle (recommended)?

## Test Gate Outcomes
No gates run: Stage 0 wrote no production code. The analysis script ran successfully against the real cache.

## Closeout Packet
- **Plan:** the path in the frontmatter.
- **Stage 0 outputs:**
  - `rfc004_stage0_sweep.py`
  - `rfc004_stage0_sweep_output.json`
  - this report
- **Verified:** the constants were checked against real data.
- **Unverified:** the visual AC-14 check.
- **Classification:** Keep in active/testing.
- **Next:** go-ahead on D1–D5, then RFC-4 implementation.
- **CONTEXT_PARTIAL:** none.

## Forward Preview
- **Test Infra Found:** `read_onchain_series`. Frozen real-data fixtures for the regression test.
- **Blast Radius Changes:** none yet. Planned: 5 new api files, 3 tests plus 1 fixture, and 1 line in `main.py`.
- **Commands to Stay Green:** `uv run --project api pytest api/ -q` (467 passed / 5 deselected at the RFC-3 baseline).
- **Dependency Changes:** none.

**TL;DR:** The constants N180/R25/M14/S180 mark the real 2022, 2023 and 2025 lows and nothing noisy. The history gate is 194 post-launch days (Robinhood gets markers about 2027-01-11). Pre-launch rows exist on 4 chains, and the proposal flags them and excludes them from the analytics. The comparison is rebased to 100 with log scale on by default. The API reuses the regime shape with one metric per request. Five decisions are waiting.
