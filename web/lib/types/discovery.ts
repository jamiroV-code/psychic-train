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
  /** False when fewer than `min_category_coins` coins were used: the score is kept but not ranked. */
  ranked: boolean;
  coins: DiscoveryCoin[];
}

/** Why top-N coins are not shown. Disjoint; with `shown_size` they add up to `universe_size`. */
export interface DiscoveryExcluded {
  exclusion_list: number;
  below_volume_floor: number;
  no_category: number;
  no_source_data: number;
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
  /** Distinct coins listed in any category. */
  shown_size: number;
  excluded: DiscoveryExcluded;
  min_category_coins: number;
  /** A source change at or above this percent counts as rising. */
  rising_threshold_pct: number;
  /** Covered weight needed before a coin can trigger. */
  min_covered_weight: number;
  categories: DiscoveryCategory[];
}

export type DiscoverySourceState = "ok" | "insufficient-history" | "unavailable" | "not-probed" | "off";

/** One line of GET /api/narrative/sources */
export interface DiscoverySourceRow {
  id: string;
  label: string;
  kind: "weighted" | "exchange-member" | "fallback" | "helper";
  weight: number | null;
  state: DiscoverySourceState;
  newest: string | null;
  history_days: number;
  coins_with_data: number;
  eligible_size: number;
  note: string;
}

export interface DiscoverySourcesResponse {
  as_of: string;
  universe_size: number;
  eligible_size: number;
  live_sources: number;
  total_sources: number;
  live_weight: number;
  newest: string | null;
  sources: DiscoverySourceRow[];
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
