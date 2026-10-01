import type { SpreadPoint } from "@/lib/types/pairs";

export interface SpreadSeriesPoint {
  /** The point's date, as a UTC instant, for positioning on a time scale. */
  date: Date;
  /** The API's `spread`, passed through untouched. */
  value: number;
}

/**
 * The one place the API's `spread[]` becomes chart-ready data.
 *
 * Deliberately pure and framework-agnostic. The previous guarantee that every
 * spread point is plotted unchanged lived in a unit test that inspected a
 * mocked `lightweight-charts` instance, so it could only ever hold for that
 * library. Here the guarantee is tested directly and survives the chart
 * library underneath it changing — which, mid-migration, it is.
 *
 * `spread` is never rounded, resampled, interpolated or gap-filled: the repo's
 * "one source of numerical truth" rule means the number Python computed is the
 * number drawn. Only the ISO date string is converted, and only so a time
 * scale can place it.
 */
export function toSpreadSeries(points: readonly SpreadPoint[]): SpreadSeriesPoint[] {
  return points.map((p) => ({ date: new Date(`${p.date}T00:00:00Z`), value: p.spread }));
}
