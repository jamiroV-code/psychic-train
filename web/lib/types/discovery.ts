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

/** GET /api/narrative/discovery/history: shared by the coin and category payloads. */
interface DiscoveryHistoryBase {
  id: string;
  window: DiscoveryWindow;
  as_of: string;
  status: "ok" | "no-data";
  reason: string;
  min_history_days: number;
  /** Trigger floor: covered_weight below it is a thin day. */
  min_covered_weight: number;
  history_days: Record<string, number>;
}

export interface DiscoveryHistoryDay {
  date: string;
  score: number;
  covered_weight: number;
  rising_weight: number;
  /** The stored per-day flag; the chart plots it as is and never recomputes it. */
  trigger: boolean;
  thin: boolean;
}

export interface DiscoveryCategoryDay {
  date: string;
  score: number;
  coins_used: number;
  triggered_count: number;
  /** 0..1 */
  triggered_share: number;
}

export interface DiscoveryCoinHistory extends DiscoveryHistoryBase {
  kind: "coin";
  days: DiscoveryHistoryDay[];
}

export interface DiscoveryCategoryHistory extends DiscoveryHistoryBase {
  kind: "category";
  days: DiscoveryCategoryDay[];
}

/** GET /api/narrative/discovery/price */
export interface DiscoveryPrice {
  symbol: string;
  window: DiscoveryWindow;
  status: "ok" | "no-data";
  last_date: string | null;
  days: { date: string; close: number }[];
}

/** What the table selected for the chart. */
export type DiscoverySelection = { kind: "coin"; symbol: string } | { kind: "category"; id: string; name: string };
