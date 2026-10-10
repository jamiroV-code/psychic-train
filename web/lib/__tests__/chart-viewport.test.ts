import { describe, expect, it } from "vitest";
import {
  extentOf,
  fullRange,
  isDoubleTap,
  isZoomed,
  keepRange,
  pan,
  pinchFactor,
  shouldHandleWheel,
  touchActionFor,
  zoomAt,
  type Extent,
} from "@/lib/chart-viewport";

const HOUR = 3_600_000;
// 100 hourly bars.
const TIMES = Array.from({ length: 100 }, (_, i) => Date.UTC(2026, 9, 1) + i * HOUR);
const EXTENT = extentOf(TIMES) as Extent;
const FULL = fullRange(EXTENT);

describe("chart-viewport", () => {
  it("zoom keeps the anchor date under the pointer", () => {
    const fraction = 0.25;
    const anchor = FULL.from + fraction * (FULL.to - FULL.from);
    const next = zoomAt(FULL, fraction, 2, EXTENT);
    expect(next.to - next.from).toBeCloseTo((FULL.to - FULL.from) / 2);
    expect(next.from + fraction * (next.to - next.from)).toBeCloseTo(anchor);
  });

  it("zoom clamps to the extent", () => {
    const zoomed = zoomAt(FULL, 0.5, 4, EXTENT);
    // Zooming out about the right edge cannot push the range past the data.
    const out = zoomAt({ from: zoomed.from, to: EXTENT.to }, 1, 0.5, EXTENT);
    expect(out.from).toBeGreaterThanOrEqual(EXTENT.from);
    expect(out.to).toBeLessThanOrEqual(EXTENT.to);
    const edge = zoomAt(FULL, 0, 3, EXTENT);
    expect(edge.from).toBe(EXTENT.from);
  });

  it("zoom keeps a 5-bar minimum", () => {
    let range = FULL;
    for (let i = 0; i < 50; i += 1) range = zoomAt(range, 0.5, 3, EXTENT);
    expect(EXTENT.minSpan).toBe(5 * HOUR);
    expect(range.to - range.from).toBe(5 * HOUR);
  });

  it("zoom-out stops at the full range", () => {
    let range = zoomAt(FULL, 0.3, 5, EXTENT);
    for (let i = 0; i < 20; i += 1) range = zoomAt(range, 0.3, 0.5, EXTENT);
    expect(range).toEqual(FULL);
    expect(isZoomed(range, EXTENT)).toBe(false);
  });

  it("pan moves and clamps", () => {
    const zoomed = zoomAt(FULL, 0.5, 4, EXTENT);
    const span = zoomed.to - zoomed.from;
    const left = pan(zoomed, 0.1, EXTENT); // drag right: earlier time
    expect(left.from).toBeCloseTo(zoomed.from - 0.1 * span);
    expect(left.to - left.from).toBeCloseTo(span);
    const far = pan(zoomed, 100, EXTENT);
    expect(far.from).toBe(EXTENT.from);
    expect(far.to - far.from).toBeCloseTo(span);
    const right = pan(zoomed, -100, EXTENT);
    expect(right.to).toBe(EXTENT.to);
  });

  it("pan only when zoomed", () => {
    expect(pan(FULL, 0.3, EXTENT)).toEqual(FULL);
    expect(touchActionFor(false)).toBe("pan-y");
    expect(touchActionFor(true)).toBe("none");
  });

  it("pinch factor: fingers apart zoom in, together zoom out, degenerate is no-op", () => {
    expect(pinchFactor(100, 200)).toBe(2);
    expect(pinchFactor(200, 100)).toBe(0.5);
    expect(pinchFactor(0, 100)).toBe(1);
    const zoomed = zoomAt(FULL, 0.5, pinchFactor(100, 200), EXTENT);
    expect(isZoomed(zoomed, EXTENT)).toBe(true);
  });

  it("double-click and double-tap reset: a second tap within 300 ms and 24 px", () => {
    expect(isDoubleTap(null, 1000, 0)).toBe(false);
    expect(isDoubleTap(1000, 1250, 5)).toBe(true);
    expect(isDoubleTap(1000, 1300, 24)).toBe(true);
    expect(isDoubleTap(1000, 1301, 5)).toBe(false);
    expect(isDoubleTap(1000, 1200, 40)).toBe(false);
    // The reset itself is the full range.
    expect(isZoomed(fullRange(EXTENT), EXTENT)).toBe(false);
  });

  it("plain wheel ignored", () => {
    expect(shouldHandleWheel({ ctrlKey: false, metaKey: false })).toBe(false);
    expect(shouldHandleWheel({})).toBe(false);
  });

  it("Ctrl and Meta both zoom", () => {
    expect(shouldHandleWheel({ ctrlKey: true })).toBe(true);
    expect(shouldHandleWheel({ metaKey: true })).toBe(true);
  });

  it("keepRange: null stays null", () => {
    expect(keepRange(null, EXTENT)).toBeNull();
    expect(keepRange({ from: FULL.from, to: FULL.from + 10 * HOUR }, null)).toBeNull();
  });

  it("keepRange: a range inside the extent is unchanged", () => {
    const range = { from: FULL.from + 20 * HOUR, to: FULL.from + 40 * HOUR };
    expect(keepRange(range, EXTENT)).toEqual(range);
  });

  it("keepRange: a slid extent clamps with the span kept", () => {
    // The window moved on by ten bars: the oldest ten fell out of the data.
    const slid = extentOf(TIMES.map((t) => t + 10 * HOUR)) as Extent;
    const range = { from: FULL.from + 2 * HOUR, to: FULL.from + 22 * HOUR };
    const kept = keepRange(range, slid);
    expect(kept).toEqual({ from: slid.from, to: slid.from + 20 * HOUR });
  });

  it("keepRange: a range no longer zoomed gives null", () => {
    // Wider than the new data: clamped, it is the full range, so not a zoom.
    const short = extentOf(TIMES.slice(0, 10)) as Extent;
    expect(keepRange({ from: FULL.from, to: FULL.from + 50 * HOUR }, short)).toBeNull();
  });

  it("T44 linked zoom: a shared range on a shorter series clamps into it, span kept", () => {
    // A coin listed later: its bars start 60 hours after the others'.
    const late = extentOf(TIMES.slice(60)) as Extent;
    const shared = { from: FULL.from + 40 * HOUR, to: FULL.from + 70 * HOUR };
    expect(keepRange(shared, late)).toEqual({ from: late.from, to: late.from + 30 * HOUR });
    // Entirely inside the shorter series it is shown as is.
    const inside = { from: FULL.from + 70 * HOUR, to: FULL.from + 80 * HOUR };
    expect(keepRange(inside, late)).toEqual(inside);
  });
});
