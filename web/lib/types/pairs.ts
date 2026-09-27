/**
 * Pair screener API contract — a TypeScript mirror of api/models/pairs.py
 * (cointegration-screener RFC-003). Two levels of status, never merged:
 * per-pair `status` and response-level `computation_status`. A value that
 * does not exist is null, with a reason alongside it — never NaN or 0.
 */
export type PairStatus = "ok" | "insufficient_overlap" | "coin_unavailable";
export type ComputationStatus = "fresh" | "stale" | "results_unavailable";
export type HalfLifeState = "computed" | "not_mean_reverting";

export interface HalfLife {
  state: HalfLifeState;
  days: number | null; // null iff state === "not_mean_reverting"
}

export interface Johansen {
  trace_stat: number;
  crit_value_95: number;
  rank_at_least_1: boolean;
}

export interface EGDirection {
  dependent: string;
  independent: string;
  hedge_ratio: number;
  intercept: number;
  t_stat: number;
  p_value: number;
}

export interface SpreadPoint {
  date: string; // ISO date
  spread: number;
  z_score: number;
}

export interface PairSummary {
  coin_a: string;
  coin_b: string;
  status: PairStatus;
  reason: string | null;
  overlap_days: number | null;
  sample_start: string | null;
  sample_end: string | null;
  eg_p_raw: number | null;
  eg_p_bh: number | null;
  eg_direction: string | null; // "DEP~INDEP" of the lower-p direction
  eg_p_other_direction: number | null;
  johansen: Johansen | null;
  johansen_reason: string | null; // set iff ok and Johansen refused; pair stays ok
  half_life: HalfLife | null;
  z_score: number | null;
}

export interface PairDetail extends PairSummary {
  eg_a_on_b: EGDirection | null;
  eg_b_on_a: EGDirection | null;
  spread_direction: string | null;
  half_life_ar1_beta: number | null;
  spread: SpreadPoint[]; // [] iff status !== "ok"
}

export interface PairsEnvelope {
  generated_utc: string;
  computed_at: string | null;
  computation_status: ComputationStatus;
  stale_reason: string | null;
  diagnostic_scope: "whole_history_in_sample";
  diagnostic_disclosure: string;
}

export interface PairsResponse extends PairsEnvelope {
  universe_size: number;
  pair_count: number;
  min_overlap_days: number;
  pairs: PairSummary[];
}

export interface PairDetailResponse extends PairsEnvelope {
  pair: PairDetail | null;
}
