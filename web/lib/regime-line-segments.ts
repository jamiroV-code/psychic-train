/**
 * Which grid points break a drawn line.
 *
 * The lightweight-charts mapping that used to live here
 * (`toSegmentedSeriesData`, and the transparent-segment trick it needed
 * because whitespace does NOT break a line in that library) went with the last
 * chart that used it. Segmenting for the LayerChart islands is
 * lib/chart-segments.ts, where a break is simply the end of a segment.
 */

/**
 * Grid indices where the drawn line is broken by an API `gap_before` flag:
 * points that carry the flag AND have an earlier real point (the first point
 * of a series has nothing to break from). Exposed so the panel can surface the
 * breaks as a DOM attribute for end-to-end tests; no value is computed.
 */
export function lineBreakIndices(values: (number | null | undefined)[], gapBefore: boolean[] = []): number[] {
  const out: number[] = [];
  let seenReal = false;
  values.forEach((v, i) => {
    if (v === null || v === undefined) return;
    if (seenReal && gapBefore[i] === true) out.push(i);
    seenReal = true;
  });
  return out;
}
