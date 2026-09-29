import { CATEGORICAL } from "@/lib/chart-palette";
import type { RelativePerformanceResponse } from "@/lib/types/screener";

export interface RelativeLine {
  key: string;
  color: string;
  width: number;
  points: { timestamp: string; value: number }[];
}

/**
 * Axis label for a % change from the window start. Formatting only: the value
 * is the API's, and a tick that lands on zero reads "0%", never "+0%".
 */
export function formatPercentChange(v: number): string {
  const rounded = Number(v.toFixed(1));
  return `${rounded > 0 ? "+" : ""}${rounded}%`;
}

/**
 * The lines the relative-performance chart draws: one per AVAILABLE coin, in
 * the API's order, coloured by position from the validated categorical set.
 *
 * Pulled out of the component so two guarantees stay directly testable now
 * that the plot is a Svelte island jsdom never mounts: line count is the
 * watchlist size minus the unavailable coins (AC-14/AC-15), and every coin
 * shares the ONE plot rather than getting its own (item 29d). An unavailable
 * coin gets no line at all, never a flat zero, and is reported as text.
 *
 * Values are the API's `close`, passed through untouched.
 */
export function buildRelativeLines(series: RelativePerformanceResponse["series"]): RelativeLine[] {
  return series
    .filter((s) => s.available)
    .map((s, idx) => ({
      key: s.symbol,
      color: CATEGORICAL[idx % CATEGORICAL.length],
      width: 2,
      points: s.points.map((p) => ({ timestamp: p.timestamp, value: p.close })),
    }));
}
