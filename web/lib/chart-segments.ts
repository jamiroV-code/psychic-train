export interface SegmentPoint {
  /** Logical index into the shared grid. */
  i: number;
  /** The grid date, as a UTC instant. */
  date: Date;
  /** The API's value, passed through untouched. */
  value: number;
}

/**
 * Splits one grid-aligned series into contiguous drawable segments, breaking
 * ONLY where the API flags `gap_before`.
 *
 * The distinction this function exists to preserve:
 * - a missing value is *whitespace* — the series simply has no reading on that
 *   grid date, which is the normal state of a weekly series (FRED WALCL) laid
 *   on the union of every component's dates. The line is drawn across it,
 *   because the two readings either side are genuinely consecutive readings.
 * - `gap_before` is a *hole* — the API is telling us a reading is missing that
 *   should have been there. The line must not be drawn across it.
 *
 * Collapsing the two (breaking on whitespace as well) silently destroys every
 * sparse series: a weekly component on a daily grid becomes a run of
 * one-point segments, and a one-point segment has no line to draw.
 *
 * Mirrors `lineBreakIndices` in regime-line-segments.ts, including its rule
 * that a flag on the FIRST reading is not a break — there is nothing before it
 * to break from.
 *
 * Pure rendering. No value is computed, rounded, interpolated or filled.
 */
export function toLineSegments(
  gridDates: readonly string[],
  values: readonly (number | null | undefined)[],
  gapBefore: readonly boolean[] = [],
): SegmentPoint[][] {
  const segments: SegmentPoint[][] = [];
  let current: SegmentPoint[] = [];

  for (let i = 0; i < gridDates.length; i++) {
    const v = values[i];
    // Whitespace: no reading here, but the series continues.
    if (v === null || v === undefined || !Number.isFinite(v)) continue;

    if (current.length > 0 && gapBefore[i] === true) {
      segments.push(current);
      current = [];
    }
    current.push({ i, date: new Date(`${gridDates[i]}T00:00:00Z`), value: v as number });
  }
  if (current.length > 0) segments.push(current);

  return segments;
}

/**
 * Trims a segment to the visible index window, cutting the line exactly at the
 * edges.
 *
 * A canvas does not clip: handing a mark the whole series while the scale shows
 * only part of it paints the rest straight over the axis labels. Slicing to the
 * points inside the window alone is not enough either — the line would stop
 * short of the edge by up to a whole reading, which on a monthly series is a
 * visible and misleading hole at both ends.
 *
 * So a segment crossing an edge gets a boundary point interpolated between its
 * two real readings. That point is geometry, not data: it exists only to put
 * the line where it belongs on screen, and nothing reads a value from it. Every
 * number the user can actually read — the readout, the axis, the drill-down —
 * comes from the API's own points, indexed by the grid.
 */
export function clipSegmentToWindow(
  segment: readonly SegmentPoint[],
  lo: number,
  hi: number,
): SegmentPoint[] {
  const at = (a: SegmentPoint, b: SegmentPoint, i: number): SegmentPoint => {
    const t = (i - a.i) / (b.i - a.i);
    return {
      i,
      date: new Date(a.date.getTime() + t * (b.date.getTime() - a.date.getTime())),
      value: a.value + t * (b.value - a.value),
    };
  };

  const out: SegmentPoint[] = [];
  for (let k = 0; k < segment.length; k++) {
    const p = segment[k];
    const prev = k > 0 ? segment[k - 1] : undefined;
    const inside = p.i >= lo && p.i <= hi;

    if (inside) {
      // Only interpolate when the edge falls BETWEEN two readings; an edge
      // landing on a reading already has its point.
      if (prev && prev.i < lo && p.i > lo) out.push(at(prev, p, lo));
      out.push(p);
      continue;
    }
    if (!prev) continue;
    if (prev.i >= lo && prev.i < hi && p.i > hi) {
      out.push(at(prev, p, hi));
    } else if (prev.i < lo && p.i > hi) {
      // One long reading-to-reading run straddling the whole window.
      out.push(at(prev, p, lo), at(prev, p, hi));
    }
  }
  return out;
}
