/**
 * Mirrors `api/models/narrative.py` (RFC-3, GET /api/narrative/history)
 * field-for-field. `reason` strings stay open (`string | null`): the backend
 * emits free-form codes such as `last-point-9-days-old` or
 * `fetch-failed: HTTPError`, formatted by `formatNarrativeReason`.
 */
export type NarrativeHistorySource =
  | "pytrends"
  | "reddit"
  | "coingecko"
  | "coingecko-narrative"
  | "exchange_volume_share"
  | "exchange_new_listings";

export type NarrativeSeriesStatus = "ok" | "stale" | "unavailable" | "presumed-dead";
export type NarrativeEntryStatus = "ok" | "unavailable";
export type PytrendsVariant = "nightly-7d" | "backfill-269d";
/** Narrative-v2 ADR-1: data sufficiency of the point's owning series. */
export type NarrativeSufficiency = "insufficient" | "provisional" | "mature";

export interface NarrativeHistoryPoint {
  date: string;
  raw_value: number | null;
  normalized_value: number | null;
  point_status: string | null;
  reason: string | null;
  gap_before: boolean;
  sufficiency: NarrativeSufficiency;
}

export interface NarrativeHistorySeries {
  source: NarrativeHistorySource;
  label: string;
  variant: PytrendsVariant | null;
  cache_key: string;
  redistributable: boolean;
  status: NarrativeSeriesStatus;
  reason: string | null;
  first_date: string | null;
  last_date: string | null;
  max_gap_days: number;
  in_composite: boolean;
  points: NarrativeHistoryPoint[];
}

export interface NarrativeCoin {
  symbol: string;
  narrative_only: boolean;
}

export interface NarrativeCompositePoint {
  date: string;
  value: number;
  coverage: number;
  sources_present: string[];
  trust_weight: number;
  mixed_scale: boolean;
  gap_before: boolean;
}

export interface NarrativeComposite {
  status: NarrativeEntryStatus;
  reason: string | null;
  sources: string[];
  min_sources: number;
  max_gap_days: number;
  points: NarrativeCompositePoint[];
}

export interface NarrativeHistoryCategory {
  category_id: string;
  label: string;
  keywords: string[];
  coins: NarrativeCoin[];
  series: NarrativeHistorySeries[];
  composite: NarrativeComposite;
}

export interface NarrativeComparisonEntry {
  category_id: string;
  rank: number | null;
  value: number | null;
  mixed_scale: boolean;
  status: NarrativeEntryStatus;
  reason: string | null;
}

export interface NarrativeComparison {
  as_of: string | null;
  entries: NarrativeComparisonEntry[];
}

export interface NarrativeChangeEntry {
  category_id: string;
  delta: number | null;
  rank: number | null;
  baseline_date: string | null;
  mixed_scale: boolean;
  status: NarrativeEntryStatus;
  reason: string | null;
}

export interface NarrativeChange {
  window_days: number;
  baseline_tolerance_days: number;
  as_of: string | null;
  entries: NarrativeChangeEntry[];
}

export interface NarrativeHistoryResponse {
  generated_utc: string;
  redistributable_all: boolean;
  grid_dates: string[];
  categories: NarrativeHistoryCategory[];
  comparison: NarrativeComparison;
  change_in_attention: NarrativeChange;
}
