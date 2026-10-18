export type DiscoveryWindow = 7 | 30 | 90;

export type DiscoveryReason = "" | "categories-missing" | "reference-missing" | "no-attention-data";

export interface DiscoverySource {
  /** A weighted source, or "coingecko" when it fed the exchange_activity slot. */
  source: string;
  change: number;
  as_of: string;
  /** exchange_activity only: one entry per exchange with data. */
  members?: DiscoverySource[];
}

export interface DiscoveryCoin {
  symbol: string;
  change: number | null;
  raw_change: number | null;
  /** Points of the 100 that had usable data for this coin. */
  covered_weight: number;
  rising_weight: number;
  trigger: boolean;
  sources: DiscoverySource[];
}

export interface DiscoveryCategory {
  id: string;
  name: string;
  score: number | null;
  median: number | null;
  coins_used: number;
  /** Coins with trigger true. */
  gaining_count: number;
  coins: DiscoveryCoin[];
}

/** GET /api/narrative/discovery */
export interface DiscoveryResponse {
  window: DiscoveryWindow;
  as_of: string;
  categories_as_of: string;
  status: "ok" | "no-data";
  reason: DiscoveryReason;
  universe_size: number;
  eligible_size: number;
  categories: DiscoveryCategory[];
}
