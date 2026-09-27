/**
 * Hand-mirrored from `api/models/onchain_activity.py` (chain-growth RFC-4).
 * Field names are the implemented contract; do not rename here.
 */
export type OnchainMetric = "active_addresses" | "transactions";
export type OnchainSeriesStatus = "ok" | "stale" | "unavailable";
export type FloorRampState = "not-enough-history" | "floor" | "ramping" | "declining" | "neutral";

export interface OnchainGrowthPoint {
  date: string;
  value: number;
  ema7: number | null;
  ema28: number | null;
  gap_before: boolean;
  pre_launch: boolean;
}

export interface OnchainGrowthSeries {
  source: string;
  method: string;
  attribution: string;
  redistributable: boolean;
  max_gap_days: number;
  last_as_of_utc: string | null;
  points: OnchainGrowthPoint[];
}

export interface FloorRampEvent {
  floor_date: string;
  ramp_date: string;
}

export interface FloorRamp {
  state: FloorRampState;
  events: FloorRampEvent[];
  min_history_days: number;
  history_days: number;
  gate_met_on: string | null;
}

export interface CrossCheck {
  source: string;
  redistributable: boolean;
  display_only: boolean;
  latest_common_date: string | null;
  latest_divergence_pct: number | null;
  median_abs_divergence_pct_90d: number | null;
}

export interface ChainGrowth {
  id: string;
  label: string;
  launch_date: string | null;
  limited_history: boolean;
  status: OnchainSeriesStatus;
  unavailable_reason: string | null;
  history_start_date: string | null;
  series: OnchainGrowthSeries | null;
  floor_ramp: FloorRamp | null;
  cross_check: CrossCheck | null;
}

/** Normalised only: there is no raw-value field, by design (AC-13). */
export interface ComparisonSeries {
  chain_id: string;
  rebase_date: string | null;
  rebased_late: boolean;
  /** Aligned to `grid_dates`. */
  index_values: (number | null)[];
  /** Aligned to `grid_dates`. */
  pct_above_low_values: (number | null)[];
}

export interface Comparison {
  normalization_method: string;
  alternative_method: string;
  start_date: string;
  log_scale_default: boolean;
  series: ComparisonSeries[];
}

export interface GrowthParams {
  ema_span: number;
  ema_fast_span: number;
  window_days: number;
  recovery_pct: number;
  sustain_days: number;
  spacing_days: number;
  floor_state_pct: number;
  min_history_days: number;
  stale_after_days: number;
}

export interface OnchainGrowthResponse {
  generated_utc: string;
  metric: OnchainMetric;
  grid_dates: string[];
  attribution: string;
  params: GrowthParams;
  chains: ChainGrowth[];
  comparison: Comparison;
}

export interface ChainMetricInfo {
  metric: string;
  source: string;
  unavailable_reason: string | null;
}

export interface ChainInfo {
  id: string;
  label: string;
  enabled: boolean;
  launch_date: string | null;
  limited_history: boolean;
  metrics: ChainMetricInfo[];
  cross_check_source: string | null;
}

export interface OnchainChainsResponse {
  chains: ChainInfo[];
}
