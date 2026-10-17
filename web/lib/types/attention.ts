// Mirrors api/models/attention.py (GET /api/narrative/baskets/attention).
export type AttentionWindow = 7 | 30 | 90;
export type SourceState = "ok" | "unavailable" | "insufficient-history" | "no-article" | "capped" | "not-probed";
export type BasketStatus = "ok" | "no-data" | "empty";

export interface SourceDetail {
  source: string;
  raw: number | null;
  ratio: number | null;
  rank: number | null;
  state: SourceState;
}

export interface CoinAttention {
  symbol: string;
  score: number | null;
  sources_used: number;
  sources_total: number;
  sources: SourceDetail[];
}

export interface SeriesPoint {
  date: string;
  value: number | null;
}

export interface BasketAttention {
  id: string;
  name: string;
  score: number | null;
  change: number | null;
  breadth: number | null;
  /** "covers N of M" */
  coverage: string;
  series: SeriesPoint[];
  coins: CoinAttention[];
  status: BasketStatus;
  reason: string;
  universe_size: number;
}

export interface AttentionResponse {
  window: AttentionWindow;
  as_of: string;
  membership_as_of: string;
  baskets: BasketAttention[];
}
