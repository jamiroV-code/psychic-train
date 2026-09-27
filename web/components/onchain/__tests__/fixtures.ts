import type { ChainGrowth, FloorRampState, OnchainGrowthResponse, OnchainMetric } from "@/lib/types/onchain";

export const GRID = ["2025-09-20", "2025-09-21", "2025-09-22", "2025-09-25", "2026-09-19", "2026-09-20"];
export const ATTRIBUTION = "Source: growthepie, https://www.growthepie.com.";

function live(id: string, label: string, state: FloorRampState, over: Partial<ChainGrowth> = {}): ChainGrowth {
  return {
    id,
    label,
    launch_date: "2020-01-01",
    limited_history: false,
    status: "ok",
    unavailable_reason: null,
    history_start_date: GRID[0],
    series: {
      source: "growthepie",
      method: "unique addresses active per UTC day (growthepie daa)",
      attribution: ATTRIBUTION,
      redistributable: true,
      max_gap_days: 1,
      last_as_of_utc: "2026-09-20T23:10:00Z",
      points: GRID.map((date, i) => ({
        date,
        value: 1000 + i * 100,
        ema7: 990 + i * 100,
        ema28: 980 + i * 100,
        gap_before: date === "2025-09-25",
        pre_launch: false,
      })),
    },
    floor_ramp: { state, events: [], min_history_days: 194, history_days: 400, gate_met_on: "2020-07-13" },
    cross_check: null,
    ...over,
  };
}

function unavailable(id: string, label: string): ChainGrowth {
  return {
    id,
    label,
    launch_date: null,
    limited_history: false,
    status: "unavailable",
    unavailable_reason: "source-unavailable",
    history_start_date: null,
    series: null,
    floor_ramp: null,
    cross_check: null,
  };
}

export function makeResponse(metric: OnchainMetric = "active_addresses", start = "2025-09-20"): OnchainGrowthResponse {
  const eth = live("ethereum", "Ethereum", "neutral", {
    floor_ramp: {
      state: "neutral",
      events: [{ floor_date: GRID[1], ramp_date: GRID[4] }],
      min_history_days: 194,
      history_days: 4000,
      gate_met_on: "2016-02-09",
    },
  });
  const base = live("base", "Base", "ramping", {
    status: "stale",
    series: { ...live("base", "Base", "ramping").series!, last_as_of_utc: "2026-09-15T23:10:00Z" },
    cross_check:
      metric === "transactions"
        ? {
            source: "l2beat",
            redistributable: false,
            display_only: true,
            latest_common_date: GRID[5],
            latest_divergence_pct: -0.0512,
            median_abs_divergence_pct_90d: 0.0064,
          }
        : null,
  });
  const polygon = live("polygon", "Polygon", "floor", {
    launch_date: "2025-09-22",
    series: {
      ...live("polygon", "Polygon", "floor").series!,
      points: GRID.map((date, i) => ({
        date,
        value: 500 + i,
        ema7: i < 2 ? null : 500 + i,
        ema28: i < 2 ? null : 500 + i,
        gap_before: false,
        pre_launch: i < 2,
      })),
    },
  });
  const robinhood = live("robinhood", "Robinhood Chain", "not-enough-history", {
    launch_date: "2026-07-01",
    limited_history: true,
    history_start_date: "2026-09-19",
    series: {
      ...live("robinhood", "Robinhood Chain", "not-enough-history").series!,
      points: GRID.slice(4).map((date, i) => ({ date, value: 10 + i, ema7: 10 + i, ema28: 10 + i, gap_before: false, pre_launch: false })),
    },
    floor_ramp: { state: "not-enough-history", events: [], min_history_days: 194, history_days: 82, gate_met_on: "2027-01-10" },
  });
  const chains = [
    eth,
    base,
    live("arbitrum", "Arbitrum", "declining"),
    live("optimism", "Optimism", "neutral"),
    polygon,
    robinhood,
    unavailable("solana", "Solana"),
    unavailable("bnb", "BNB Chain"),
    unavailable("tron", "Tron"),
  ];
  const liveIds = ["ethereum", "base", "arbitrum", "optimism", "polygon", "robinhood"];
  return {
    generated_utc: "2026-09-21T06:00:00Z",
    metric,
    grid_dates: GRID,
    attribution: ATTRIBUTION,
    params: {
      ema_span: 28,
      ema_fast_span: 7,
      window_days: 180,
      recovery_pct: 0.25,
      sustain_days: 14,
      spacing_days: 180,
      floor_state_pct: 0.1,
      min_history_days: 194,
      stale_after_days: 3,
    },
    chains,
    comparison: {
      normalization_method: "index-100-at-start-ema28",
      alternative_method: "pct-above-180d-low-ema28",
      start_date: start,
      log_scale_default: true,
      series: liveIds.map((id) => ({
        chain_id: id,
        rebase_date: id === "robinhood" ? GRID[4] : start,
        rebased_late: id === "robinhood",
        index_values: GRID.map((_, i) => (id === "robinhood" && i < 4 ? null : 100 + i)),
        pct_above_low_values: GRID.map((_, i) => (i < 3 ? null : i * 2)),
      })),
    },
  };
}

export function allUnavailableResponse(): OnchainGrowthResponse {
  const r = makeResponse();
  return {
    ...r,
    grid_dates: [],
    chains: r.chains.filter((c) => c.status === "unavailable"),
    comparison: { ...r.comparison, series: [] },
  };
}
