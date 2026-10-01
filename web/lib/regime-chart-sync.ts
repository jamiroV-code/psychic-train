/**
 * Shared-grid helpers for the panel charts.
 *
 * Every panel is fed the SAME grid of dates, so logical index i means the same
 * date on every chart. That is what makes LOGICAL-range sync exact: panels
 * starting on different dates still line up, because none is clamped to its
 * own first data point. These helpers convert between that grid, UTC seconds
 * and the `data-visible-range` attribute the end-to-end suite reads.
 *
 * The imperative lightweight-charts sync that used to live here is gone: the
 * panels are Svelte/LayerChart islands now and share one store instead
 * (islands/panel-sync.svelte.js), which needs no registration fan-out and no
 * re-entrancy guards because nothing echoes. `visibleRangeAttribute` is
 * deliberately still the one used by that store, so the attribute is
 * byte-identical to what the old path wrote.
 *
 * Display-only index arithmetic — no maths is re-implemented here.
 */

/** Grid date (YYYY-MM-DD) at a logical index, clamped to the grid; null for an empty grid. */
function gridDateAt(gridTimes: number[], logical: number): string | null {
  if (gridTimes.length === 0 || !Number.isFinite(logical)) return null;
  const i = Math.min(gridTimes.length - 1, Math.max(0, Math.round(logical)));
  return new Date(gridTimes[i] * 1000).toISOString().slice(0, 10);
}

/** Serialised value written to `data-visible-range` (display/observability only). */
export function visibleRangeAttribute(gridTimes: number[], range: { from: number; to: number }): string {
  return JSON.stringify({
    from: range.from,
    to: range.to,
    fromDate: gridDateAt(gridTimes, range.from),
    toDate: gridDateAt(gridTimes, range.to),
  });
}

export function isoDateToUtcSeconds(date: string): number {
  const [y, m, d] = date.split("-").map(Number);
  return Date.UTC(y, m - 1, d) / 1000;
}

/**
 * Logical index range covering the last `years` calendar years before the
 * final grid date (plan decision 5). Returns null for an empty grid.
 */
export function defaultVisibleRange(gridDates: string[], years = 3): { from: number; to: number } | null {
  if (gridDates.length === 0) return null;
  const last = gridDates[gridDates.length - 1];
  const [y, m, d] = last.split("-").map(Number);
  const cutoff = `${String(y - years).padStart(4, "0")}-${String(m).padStart(2, "0")}-${String(d).padStart(2, "0")}`;
  let from = gridDates.findIndex((g) => g >= cutoff);
  if (from < 0) from = 0;
  return { from, to: gridDates.length - 1 };
}
