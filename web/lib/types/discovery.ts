export type DiscoveryWindow = 7 | 30 | 90;

export type DiscoveryReason = "" | "categories-missing" | "reference-missing" | "no-attention-data";

export interface DiscoveryCoin {
  symbol: string;
  change: number | null;
  raw_change: number | null;
  gaining: boolean;
  sources_used: number;
  sources_gaining: number;
}

export interface DiscoveryCategory {
  id: string;
  name: string;
  score: number | null;
  median: number | null;
  coins_used: number;
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
