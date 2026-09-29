import { describe, expect, it } from "vitest";
import { clipSegmentToWindow, toLineSegments } from "@/lib/chart-segments";

const dates = ["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"];

describe("toLineSegments", () => {
  it("keeps a clean series as one segment, values untouched", () => {
    const segs = toLineSegments(dates, [1, 2, 3, 4, 5]);
    expect(segs).toHaveLength(1);
    expect(segs[0].map((p) => p.value)).toEqual([1, 2, 3, 4, 5]);
  });

  it("breaks at a flagged hole instead of drawing across it", () => {
    // Both sides have values; only `gap_before` says the line must break.
    const segs = toLineSegments(dates, [1, 2, 3, 4, 5], [false, false, true, false, false]);
    expect(segs.map((s) => s.map((p) => p.value))).toEqual([
      [1, 2],
      [3, 4, 5],
    ]);
  });

  it("draws across whitespace: a sparse series is one line, not a row of dots", () => {
    // The regression this pins: a weekly component laid on the daily union
    // grid has no reading on most dates. Those are not holes — breaking on
    // them leaves one-point segments, and a one-point segment draws nothing,
    // so the whole series disappears from the panel.
    const segs = toLineSegments(dates, [1, null, 3, undefined, 5]);
    expect(segs).toHaveLength(1);
    expect(segs[0].map((p) => p.value)).toEqual([1, 3, 5]);
    expect(segs[0].map((p) => p.i)).toEqual([0, 2, 4]);
  });

  it("still breaks on a flagged hole that also has whitespace around it", () => {
    // Whitespace does not break, but the flag on the next real reading does.
    const segs = toLineSegments(dates, [1, null, 3, null, 5], [false, false, false, false, true]);
    expect(segs.map((s) => s.map((p) => p.value))).toEqual([
      [1, 3],
      [5],
    ]);
  });

  it("does not treat a flag on the first reading as a break", () => {
    // Nothing precedes it, so there is no bridge to suppress — matches
    // lineBreakIndices' `seenReal` rule.
    const segs = toLineSegments(dates, [1, 2, 3, 4, 5], [true, false, false, false, false]);
    expect(segs).toHaveLength(1);
  });

  it("gives an isolated reading its own one-point segment, never a bridge", () => {
    const segs = toLineSegments(dates, [null, 2, null, null, null]);
    expect(segs).toEqual([[expect.objectContaining({ i: 1, value: 2 })]]);
  });

  it("keeps the logical index, so panels stay aligned on the shared grid", () => {
    const segs = toLineSegments(dates, [null, null, 3, 4, null]);
    expect(segs[0].map((p) => p.i)).toEqual([2, 3]);
  });

  it("reads dates as UTC so a point never shifts a day by timezone", () => {
    expect(toLineSegments(dates, [1])[0][0].date.toISOString()).toBe("2024-01-01T00:00:00.000Z");
  });

  it("does not treat 0 or a negative value as missing", () => {
    const segs = toLineSegments(dates, [0, -1, 0, -2.5, 0]);
    expect(segs).toHaveLength(1);
    expect(segs[0].map((p) => p.value)).toEqual([0, -1, 0, -2.5, 0]);
  });

  it("returns no segments for an entirely empty series", () => {
    expect(toLineSegments(dates, [null, null, null, null, null])).toEqual([]);
  });
});

describe("clipSegmentToWindow", () => {
  const seg = toLineSegments(
    ["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"],
    [0, 10, 20, 30, 40],
  )[0];

  it("leaves a segment already inside the window alone", () => {
    expect(clipSegmentToWindow(seg, 0, 4)).toEqual(seg);
  });

  it("cuts at the edge instead of stopping short of it", () => {
    const clipped = clipSegmentToWindow(seg, 1, 3);
    expect(clipped.map((p) => p.i)).toEqual([1, 2, 3]);
  });

  it("interpolates a boundary point when a reading straddles the edge", () => {
    // Window starts at 1.5: halfway between the readings 10 and 20.
    const clipped = clipSegmentToWindow(seg, 1.5, 3);
    expect(clipped[0].value).toBe(15);
    expect(clipped[0].i).toBe(1.5);
    expect(clipped[0].date.toISOString()).toBe("2024-01-02T12:00:00.000Z");
  });

  it("keeps a run that spans the whole window, cut at both edges", () => {
    const sparse = toLineSegments(["a", "b"].concat([]), [0, 100]);
    // Only two readings, both outside a window sitting between them.
    const wide = clipSegmentToWindow(
      [
        { i: 0, date: new Date("2024-01-01T00:00:00Z"), value: 0 },
        { i: 100, date: new Date("2024-04-10T00:00:00Z"), value: 100 },
      ],
      40,
      60,
    );
    expect(wide.map((p) => p.value)).toEqual([40, 60]);
    expect(sparse).toHaveLength(1);
  });

  it("drops a segment that is entirely outside the window", () => {
    expect(clipSegmentToWindow(seg, 10, 20)).toEqual([]);
  });
});
