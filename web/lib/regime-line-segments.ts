import type { LineData, UTCTimestamp, WhitespaceData } from "lightweight-charts";

/**
 * Turns one grid-aligned series plus the API's `gap_before` flags into
 * lightweight-charts data that does not draw across real data holes
 * (RFC-005 decision 9). Pure rendering: no value is computed or changed.
 *
 * Why this shape (verified in real Chromium against lightweight-charts
 * 5.2.1, RFC-005 phase report §Supplement):
 * - Whitespace points ({time} only) do NOT break a line series: the line is
 *   drawn straight from the last value to the next one.
 * - A point's `color` paints the segment that STARTS at that point (point i
 *   -> next point), not the one ending at it. So to hide the bridge into a
 *   point k with gap_before, the last real point before k gets a transparent
 *   colour. The segment ending at that point keeps its predecessor's colour,
 *   so the point itself stays visible when it has a neighbour.
 * - A transparent point's own marker is transparent too, so points with no
 *   drawn segment on either side ("isolated") go to a separate dots-only
 *   series (lineVisible: false, pointMarkersVisible: true), which draws a
 *   plain dot and never a connecting line.
 */

export const HIDDEN_SEGMENT_COLOR = "rgba(0, 0, 0, 0)";

export type SeriesPoint = LineData | WhitespaceData;

export interface SegmentedSeriesData {
  line: SeriesPoint[];
  /** Same length as `line`; values only at isolated points. null when there are none. */
  dots: SeriesPoint[] | null;
}

export function toSegmentedSeriesData(
  gridTimes: number[],
  values: (number | null | undefined)[],
  gapBefore: boolean[] = []
): SegmentedSeriesData {
  const real: number[] = [];
  gridTimes.forEach((_, i) => {
    const v = values[i];
    if (v !== null && v !== undefined) real.push(i);
  });

  // For each real point: is there a drawn segment into it / out of it?
  const hideOut = new Set<number>();
  const isolated = new Set<number>();
  real.forEach((idx, r) => {
    const next = real[r + 1];
    const hasIn = r > 0 && gapBefore[idx] !== true;
    const hasOut = next !== undefined && gapBefore[next] !== true;
    if (next !== undefined && !hasOut) hideOut.add(idx);
    if (!hasIn && !hasOut) isolated.add(idx);
  });

  const line: SeriesPoint[] = gridTimes.map((t, i) => {
    const time = t as UTCTimestamp;
    const v = values[i];
    if (v === null || v === undefined) return { time };
    return hideOut.has(i) ? { time, value: v, color: HIDDEN_SEGMENT_COLOR } : { time, value: v };
  });
  const dots =
    isolated.size === 0
      ? null
      : gridTimes.map((t, i) => {
          const time = t as UTCTimestamp;
          const v = values[i];
          return isolated.has(i) && v !== null && v !== undefined ? { time, value: v } : { time };
        });
  return { line, dots };
}
