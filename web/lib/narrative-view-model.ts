import { isoDateToUtcSeconds } from "@/lib/regime-chart-sync";
import type {
  NarrativeHistoryCategory,
  NarrativeHistorySeries,
} from "@/lib/types/narrative";

/**
 * Pure layout helpers for /narrative (RFC-5). Nothing here computes a number
 * the API did not send: it only picks which panels show first, orders rows,
 * and lays existing values onto a per-panel date axis.
 */

export const NARRATIVE_PANEL_SOFT_CAP = 10;

/** Latest composite value the API sent for a category, or null when none. */
export function latestCompositeValue(category: NarrativeHistoryCategory): number | null {
  const pts = category.composite.points;
  return pts.length > 0 ? pts[pts.length - 1].value : null;
}

/**
 * ADR-9 soft cap: top `cap` categories by latest composite value (categories
 * with no composite sort after every ranked one, by label), the remainder in
 * `overflow`. Nothing is dropped: `visible` + `overflow` is every category.
 */
export function splitSoftCap(
  categories: NarrativeHistoryCategory[],
  cap: number = NARRATIVE_PANEL_SOFT_CAP
): { visible: NarrativeHistoryCategory[]; overflow: NarrativeHistoryCategory[] } {
  const ordered = [...categories].sort((a, b) => {
    const va = latestCompositeValue(a);
    const vb = latestCompositeValue(b);
    if (va === null && vb === null) return a.label.localeCompare(b.label);
    if (va === null) return 1;
    if (vb === null) return -1;
    if (vb !== va) return vb - va;
    return a.label.localeCompare(b.label);
  });
  return { visible: ordered.slice(0, cap), overflow: ordered.slice(cap) };
}

/** Stable key for a series: source plus pytrends variant when present. */
export function seriesKey(series: NarrativeHistorySeries): string {
  return series.variant ? `${series.source}-${series.variant}` : series.source;
}

/** Series drawn as chart lines: normalised (0..1) sources on the composite's scale. */
export function isPlottedSeries(series: NarrativeHistorySeries): boolean {
  return series.source !== "coingecko" && series.source !== "exchange_new_listings";
}

export interface PanelAxisLine {
  key: string;
  values: (number | null)[];
  gapBefore: boolean[];
}

export interface PanelAxis {
  dates: string[];
  times: number[];
  composite: PanelAxisLine;
  /** Composite values only on `mixed_scale` points (drawn as marker dots). */
  mixedScale: (number | null)[];
  mixedScaleCount: number;
  series: PanelAxisLine[];
}

/**
 * One panel's own date axis: the union of this category's composite and
 * plotted-series dates (categories start on different days, so the global
 * `grid_dates` would pad young categories with empty space). Each line keeps
 * its own API `gap_before` flags; nightly-7d and backfill-269d pytrends stay
 * separate lines and are never joined.
 */
export function buildPanelAxis(category: NarrativeHistoryCategory): PanelAxis {
  const plotted = category.series.filter(isPlottedSeries);
  const dateSet = new Set<string>();
  category.composite.points.forEach((p) => dateSet.add(p.date));
  plotted.forEach((s) => s.points.forEach((p) => dateSet.add(p.date)));
  const dates = [...dateSet].sort();
  const index = new Map(dates.map((d, i) => [d, i]));

  const empty = () => ({
    values: dates.map(() => null as number | null),
    gapBefore: dates.map(() => false),
  });

  const composite = { key: "composite", ...empty() };
  const mixedScale = dates.map(() => null as number | null);
  let mixedScaleCount = 0;
  for (const p of category.composite.points) {
    const i = index.get(p.date)!;
    composite.values[i] = p.value;
    composite.gapBefore[i] = p.gap_before;
    if (p.mixed_scale) {
      mixedScale[i] = p.value;
      mixedScaleCount += 1;
    }
  }

  const series = plotted.map((s) => {
    const line = { key: seriesKey(s), ...empty() };
    for (const p of s.points) {
      const i = index.get(p.date)!;
      line.values[i] = p.normalized_value;
      line.gapBefore[i] = p.gap_before;
    }
    return line;
  });

  return { dates, times: dates.map(isoDateToUtcSeconds), composite, mixedScale, mixedScaleCount, series };
}

/** Ranked rows first (by rank), then unranked rows by id — never dropped, never last-place ranked. */
export function orderByRank<T extends { rank: number | null; category_id: string }>(entries: T[]): T[] {
  return [...entries].sort((a, b) => {
    if (a.rank === null && b.rank === null) return a.category_id.localeCompare(b.category_id);
    if (a.rank === null) return 1;
    if (b.rank === null) return -1;
    return a.rank - b.rank || a.category_id.localeCompare(b.category_id);
  });
}
