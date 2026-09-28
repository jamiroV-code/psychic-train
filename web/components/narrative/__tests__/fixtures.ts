import type {
  NarrativeHistoryCategory,
  NarrativeHistoryResponse,
  NarrativeHistorySeries,
} from "@/lib/types/narrative";

export function series(over: Partial<NarrativeHistorySeries> & Pick<NarrativeHistorySeries, "source">): NarrativeHistorySeries {
  return {
    label: over.source,
    variant: null,
    cache_key: `${over.source}/x`,
    redistributable: false,
    status: "ok",
    reason: null,
    first_date: "2026-09-20",
    last_date: "2026-09-22",
    max_gap_days: 2,
    in_composite: true,
    points: [
      { date: "2026-09-20", raw_value: 10, normalized_value: 0.2, point_status: "ok", reason: null, gap_before: false, sufficiency: "provisional" },
      { date: "2026-09-22", raw_value: 20, normalized_value: 0.8, point_status: "ok", reason: null, gap_before: false, sufficiency: "provisional" },
    ],
    ...over,
  };
}

export function category(id: string, latest: number | null, over: Partial<NarrativeHistoryCategory> = {}): NarrativeHistoryCategory {
  return {
    category_id: id,
    label: `${id} label`,
    keywords: [id],
    coins: [],
    series: [series({ source: "reddit" })],
    composite: {
      status: latest === null ? "unavailable" : "ok",
      reason: latest === null ? "no-composite-data" : null,
      sources: ["pytrends", "reddit", "coingecko-narrative", "exchange_volume_share"],
      min_sources: 2,
      max_gap_days: 2,
      points:
        latest === null
          ? []
          : [
              { date: "2026-09-20", value: 0.1, coverage: 0.5, sources_present: ["reddit"], trust_weight: 1, mixed_scale: false, gap_before: false },
              { date: "2026-09-22", value: latest, coverage: 0.5, sources_present: ["reddit"], trust_weight: 1, mixed_scale: false, gap_before: false },
            ],
    },
    ...over,
  };
}

export function response(categories: NarrativeHistoryCategory[], over: Partial<NarrativeHistoryResponse> = {}): NarrativeHistoryResponse {
  return {
    generated_utc: "2026-09-24T18:00:00Z",
    redistributable_all: false,
    grid_dates: ["2026-09-20", "2026-09-22"],
    categories,
    comparison: { as_of: "2026-09-22", entries: [] },
    change_in_attention: { window_days: 7, baseline_tolerance_days: 2, as_of: "2026-09-22", entries: [] },
    ...over,
  };
}
