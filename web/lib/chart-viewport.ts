/**
 * T37 / S6 (C6): the range math behind chart zoom and pan, kept pure so it is
 * tested here rather than through a canvas jsdom never draws.
 *
 * A range is a pair of epoch milliseconds. The extent is the data's own range
 * plus the smallest span a zoom may reach (five bars). Every function returns
 * a range clamped to the extent: a zoom never shows time the data does not
 * cover, and a zoom-out stops at the full range.
 */

export interface Range {
  from: number;
  to: number;
}

export interface Extent extends Range {
  /** The narrowest span a zoom may reach, in ms. */
  minSpan: number;
}

export const MIN_SPAN_BARS = 5;
/** Two taps closer together than this are a double-tap. */
export const DOUBLE_TAP_MS = 300;
/** ...and no further apart than this, in CSS pixels. */
export const DOUBLE_TAP_PX = 24;

/** The extent of a sorted or unsorted list of point times. */
export function extentOf(times: number[]): Extent | null {
  if (times.length === 0) return null;
  const sorted = [...times].sort((a, b) => a - b);
  const from = sorted[0];
  const to = sorted[sorted.length - 1];
  const steps: number[] = [];
  for (let i = 1; i < sorted.length; i += 1) {
    const step = sorted[i] - sorted[i - 1];
    if (step > 0) steps.push(step);
  }
  steps.sort((a, b) => a - b);
  const bar = steps.length > 0 ? steps[Math.floor(steps.length / 2)] : 0;
  return { from, to, minSpan: Math.min(to - from, bar * MIN_SPAN_BARS) };
}

export function fullRange(extent: Extent): Range {
  return { from: extent.from, to: extent.to };
}

/** Clamp a range into the extent, keeping its span where it fits. */
export function clampRange(range: Range, extent: Extent): Range {
  const full = extent.to - extent.from;
  const span = Math.min(Math.max(range.to - range.from, extent.minSpan), full);
  let from = range.from;
  if (from < extent.from) from = extent.from;
  if (from + span > extent.to) from = extent.to - span;
  return { from, to: from + span };
}

export function isZoomed(range: Range | null, extent: Extent | null): boolean {
  if (!range || !extent) return false;
  return range.from > extent.from || range.to < extent.to;
}

/**
 * Zoom about the point at `fraction` (0 = left edge, 1 = right edge) of the
 * visible range. `factor` > 1 zooms in, < 1 zooms out. The time under the
 * anchor stays under it unless the clamp has to move the range.
 */
export function zoomAt(range: Range, fraction: number, factor: number, extent: Extent): Range {
  if (!(factor > 0) || !Number.isFinite(factor)) return clampRange(range, extent);
  const f = Math.min(Math.max(fraction, 0), 1);
  const span = range.to - range.from;
  const anchor = range.from + f * span;
  const full = extent.to - extent.from;
  const nextSpan = Math.min(Math.max(span / factor, extent.minSpan), full);
  const from = anchor - f * nextSpan;
  return clampRange({ from, to: from + nextSpan }, extent);
}

/**
 * Pan by `dx`, a fraction of the visible width: a drag to the right (dx > 0)
 * brings earlier time into view. A full-range view does not move.
 */
export function pan(range: Range, dx: number, extent: Extent): Range {
  if (!isZoomed(range, extent)) return range;
  const shift = -dx * (range.to - range.from);
  return clampRange({ from: range.from + shift, to: range.to + shift }, extent);
}

/** The zoom factor of a two-pointer pinch: fingers apart = zoom in. */
export function pinchFactor(startDist: number, nowDist: number): number {
  if (!(startDist > 0) || !(nowDist > 0)) return 1;
  return nowDist / startDist;
}

/** A wheel delta as a zoom factor (wheel up = zoom in). */
export function wheelFactor(deltaY: number): number {
  return Math.exp(-deltaY * 0.002);
}

export function isDoubleTap(prevTs: number | null, ts: number, dist: number): boolean {
  if (prevTs === null) return false;
  const gap = ts - prevTs;
  return gap >= 0 && gap <= DOUBLE_TAP_MS && dist <= DOUBLE_TAP_PX;
}

/** Only Ctrl or Cmd + wheel zooms; a plain wheel scrolls the page. */
export function shouldHandleWheel(event: { ctrlKey?: boolean; metaKey?: boolean }): boolean {
  return Boolean(event.ctrlKey || event.metaKey);
}

/** Unzoomed, vertical touch scrolls the page; zoomed, the chart owns the touch. */
export function touchActionFor(zoomed: boolean): "none" | "pan-y" {
  return zoomed ? "none" : "pan-y";
}

/** A timestamp as ISO-8601 UTC with seconds and a trailing Z (C9). */
export function isoZ(ms: number): string {
  return new Date(ms).toISOString().replace(/\.\d{3}Z$/, "Z");
}
