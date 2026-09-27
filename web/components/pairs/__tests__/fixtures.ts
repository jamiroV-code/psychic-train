import type { PairDetail, PairDetailResponse, PairSummary, PairsResponse } from "@/lib/types/pairs";

export const DISCLOSURE =
  "These statistics use each pair's entire shared price history at once (in-sample). " +
  "They describe how the two coins moved together in the past. They are not a trading " +
  "signal, and they do not show whether the relationship still holds today.";

export function okPair(over: Partial<PairSummary> & Pick<PairSummary, "coin_a" | "coin_b">): PairSummary {
  return {
    status: "ok",
    reason: null,
    overlap_days: 2183,
    sample_start: "2020-09-24",
    sample_end: "2026-09-25",
    eg_p_raw: 0.3,
    eg_p_bh: 0.6,
    eg_direction: `${over.coin_a}~${over.coin_b}`,
    eg_p_other_direction: 0.4,
    johansen: { trace_stat: 12.5, crit_value_95: 15.49, rank_at_least_1: false },
    johansen_reason: null,
    half_life: { state: "computed", days: 50 },
    z_score: 0.25,
    ...over,
  };
}

/**
 * Four coins → C(4,2) = 6 rows, in shuffled order. Values for DOGE/BCH are
 * the real RFC-003 output. Covers: raw-only tag, Johansen refusal on an ok
 * row, not-mean-reverting half-life, insufficient_overlap, coin_unavailable.
 */
export function tablePairs(): PairSummary[] {
  return [
    {
      coin_a: "BCH",
      coin_b: "NEW",
      status: "insufficient_overlap",
      reason: "only 240 days of overlapping history available, need 365",
      overlap_days: 240,
      sample_start: "2026-01-20",
      sample_end: "2026-09-24",
      eg_p_raw: null,
      eg_p_bh: null,
      eg_direction: null,
      eg_p_other_direction: null,
      johansen: null,
      johansen_reason: null,
      half_life: null,
      z_score: null,
    },
    okPair({ coin_a: "ETH", coin_b: "BCH", eg_p_raw: 0.0017, eg_p_bh: 0.128, z_score: 0.44 }),
    {
      coin_a: "DOGE",
      coin_b: "DEAD",
      status: "coin_unavailable",
      reason: "DEAD: bad_symbol — not found on Hyperliquid market list",
      overlap_days: null,
      sample_start: null,
      sample_end: null,
      eg_p_raw: null,
      eg_p_bh: null,
      eg_direction: null,
      eg_p_other_direction: null,
      johansen: null,
      johansen_reason: null,
      half_life: null,
      z_score: null,
    },
    okPair({
      coin_a: "DOGE",
      coin_b: "BCH",
      eg_p_raw: 0.00057,
      eg_p_bh: 0.087,
      half_life: { state: "computed", days: 114 },
      z_score: -0.12,
    }),
    okPair({
      coin_a: "ETH",
      coin_b: "DOGE",
      eg_p_raw: 0.7,
      eg_p_bh: 0.9,
      johansen: null,
      johansen_reason: "Johansen refused: singular matrix",
      half_life: { state: "not_mean_reverting", days: null },
    }),
    okPair({ coin_a: "BCH", coin_b: "DOGE", eg_p_raw: 0.2, eg_p_bh: 0.5 }),
  ];
}

export function tableResponse(over: Partial<PairsResponse> = {}): PairsResponse {
  const pairs = over.pairs ?? tablePairs();
  return {
    generated_utc: "2026-09-27T18:00:00Z",
    computed_at: "2026-09-27T17:05:13Z",
    computation_status: "fresh",
    stale_reason: null,
    diagnostic_scope: "whole_history_in_sample",
    diagnostic_disclosure: DISCLOSURE,
    universe_size: 4,
    pair_count: pairs.length,
    min_overlap_days: 365,
    pairs,
    ...over,
  };
}

export function okDetail(over: Partial<PairDetail> = {}): PairDetail {
  const base = okPair({ coin_a: "DOGE", coin_b: "BCH", eg_p_raw: 0.00057, eg_p_bh: 0.087, z_score: -0.12 });
  return {
    ...base,
    sample_start: "2020-09-24",
    sample_end: "2020-09-27",
    overlap_days: 4,
    eg_a_on_b: { dependent: "DOGE", independent: "BCH", hedge_ratio: 0.812, intercept: -3.1, t_stat: -4.61, p_value: 0.00057 },
    eg_b_on_a: { dependent: "BCH", independent: "DOGE", hedge_ratio: 1.07, intercept: 2.2, t_stat: -3.9, p_value: 0.0061 },
    spread_direction: "DOGE~BCH",
    half_life_ar1_beta: -0.006,
    spread: [
      { date: "2020-09-24", spread: 0.1, z_score: 0.5 },
      { date: "2020-09-25", spread: -0.05, z_score: -0.3 },
      { date: "2020-09-26", spread: 0.02, z_score: 0.1 },
      { date: "2020-09-27", spread: -0.03, z_score: -0.12 },
    ],
    ...over,
  };
}

export function detailResponse(pair: PairDetail | null, over: Partial<PairDetailResponse> = {}): PairDetailResponse {
  return {
    generated_utc: "2026-09-27T18:00:00Z",
    computed_at: "2026-09-27T17:05:13Z",
    computation_status: "fresh",
    stale_reason: null,
    diagnostic_scope: "whole_history_in_sample",
    diagnostic_disclosure: DISCLOSURE,
    pair,
    ...over,
  };
}
