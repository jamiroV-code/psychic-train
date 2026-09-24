import { describe, expect, it } from "vitest";
import { HIDDEN_SEGMENT_COLOR, lineBreakIndices, toSegmentedSeriesData } from "@/lib/regime-line-segments";

// Mechanism (verified in Chromium, lightweight-charts 5.2.1): a point's
// `color` paints the segment that STARTS at it, and whitespace never breaks
// the line. So "no segment into k" == "the last real point before k is
// transparent".
const T = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map((d) => d * 86400);

describe("toSegmentedSeriesData", () => {
  it("weekly series on a daily grid without flags stays one continuous line", () => {
    const values = T.map((_, i) => (i % 3 === 0 ? i : null)); // points at 0, 3, 6, 9
    const { line, dots } = toSegmentedSeriesData(T, values, T.map(() => false));
    expect(line).toHaveLength(T.length);
    expect(line.some((p) => "color" in p)).toBe(false);
    expect(dots).toBeNull();
    expect(line[1]).toEqual({ time: T[1] }); // whitespace, not 0
  });

  it("gap_before on point k hides exactly the segment into k (colour on the previous real point)", () => {
    const values = [1, 2, 3, null, null, null, 7, 8, 9, 10];
    const gaps = values.map(() => false);
    gaps[6] = true;
    const { line, dots } = toSegmentedSeriesData(T, values, gaps);
    expect(line[2]).toEqual({ time: T[2], value: 3, color: HIDDEN_SEGMENT_COLOR });
    const coloured = line.map((p, i) => ("color" in p ? i : -1)).filter((i) => i >= 0);
    expect(coloured).toEqual([2]); // nothing else hidden
    expect(line[6]).toEqual({ time: T[6], value: 7 });
    expect(dots).toBeNull(); // both sides of the hole still have neighbours
  });

  it("an isolated point between two holes is drawn as a dot, with no connecting line", () => {
    const values = [1, 2, null, null, 5, null, null, 8, 9, 10];
    const gaps = values.map(() => false);
    gaps[4] = true;
    gaps[7] = true;
    const { line, dots } = toSegmentedSeriesData(T, values, gaps);
    expect(line[1]).toMatchObject({ color: HIDDEN_SEGMENT_COLOR });
    expect(line[4]).toMatchObject({ value: 5, color: HIDDEN_SEGMENT_COLOR });
    expect(dots).not.toBeNull();
    const dotValues = dots!.filter((p) => "value" in p);
    expect(dotValues).toEqual([{ time: T[4], value: 5 }]);
    expect(dots).toHaveLength(T.length);
  });

  it("a series with a single point gets a dot (a lone point draws no line)", () => {
    const values = T.map((_, i) => (i === 5 ? 42 : null));
    const { line, dots } = toSegmentedSeriesData(T, values, []);
    expect(line.some((p) => "color" in p)).toBe(false);
    expect(dots!.filter((p) => "value" in p)).toEqual([{ time: T[5], value: 42 }]);
  });

  it("gap_before on the first point of a window is harmless (no earlier point to hide)", () => {
    const values = [1, 2, 3, null, null, null, null, null, null, null];
    const { line, dots } = toSegmentedSeriesData(T, values, [true, false, false]);
    expect(line.some((p) => "color" in p)).toBe(false);
    expect(dots).toBeNull();
  });
});

describe("lineBreakIndices", () => {
  it("returns flagged points that have an earlier real point", () => {
    expect(lineBreakIndices([1, null, 3, 4], [false, false, true, false])).toEqual([2]);
  });
  it("ignores a flag on the first real point and on whitespace", () => {
    expect(lineBreakIndices([null, 2, null, 4], [true, true, true, false])).toEqual([]);
  });
  it("is empty without flags", () => {
    expect(lineBreakIndices([1, 2, 3])).toEqual([]);
  });
});
