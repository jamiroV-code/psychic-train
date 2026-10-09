import type { ChartBar } from "@/lib/types/screener";

/**
 * T38 / S7: GET /api/regime/btc-legs. Mirrors api/models/regime.py by hand;
 * api/tests/routers/test_btc_legs_router.py parses these interfaces and
 * compares them with the pydantic fields. Timestamps are ISO UTC with a
 * trailing `Z`; dates are YYYY-MM-DD. A label is null only together with a
 * `reason`.
 */

export type LiquidityCompositeVariant = "reduced" | "full";
export type AgeLabel = "early" | "mid" | "late";
export type CompositeChangeLabel = "rising" | "falling" | "flat";

export interface BtcLegBoundary {
  date: string;
  z_score: number;
  confirmed_date: string | null;
}

export interface BtcLeg {
  start: string;
  end: string | null;
  days: number;
  is_current: boolean;
}

export interface LatestCandidate {
  date: string;
  z_score: number;
  confirmed: boolean;
}

export interface CurrentLeg {
  start_date: string;
  days_in_leg: number;
  composite_value: number | null;
  composite_as_of: string | null;
  change_14d: number | null;
  last_boundary_z: number;
  latest_candidate: LatestCandidate | null;
  composite_variant: LiquidityCompositeVariant;
}

export interface AgeEstimate {
  label: AgeLabel | null;
  age_days: number;
  median_days: number | null;
  ratio: number | null;
  earlier_legs: number;
  earlier_lengths_days: number[];
  rule: string;
  reason: string | null;
}

export interface CompositeEstimate {
  label: CompositeChangeLabel | null;
  change_14d: number | null;
  threshold: number | null;
  history_std: number | null;
  n_changes: number;
  composite_as_of: string | null;
  rule: string;
  reason: string | null;
}

export interface LegEstimate {
  heading: string;
  age: AgeEstimate;
  composite: CompositeEstimate;
}

export interface BtcLegChartResponse {
  available: boolean;
  reason: string | null;
  server_time: string;
  composite_variant: LiquidityCompositeVariant;
  first_bar_ts: string | null;
  last_bar_ts: string | null;
  bar_count: number;
  btc: ChartBar[];
  boundaries: BtcLegBoundary[];
  legs: BtcLeg[];
  current_leg: CurrentLeg | null;
  estimate: LegEstimate | null;
}
