import type { IChartApi, ISeriesApi, LogicalRange, MouseEventParams, Time } from "lightweight-charts";

/**
 * Range + crosshair sync for the /regime panels (plan ADR-7, VALIDATE P3/E3).
 *
 * Every panel is fed the SAME grid of dates (whitespace where it has no
 * value), so logical index i means the same date on every chart. That makes
 * LOGICAL-range sync exact: panels that start on different dates still line
 * up, because none of them is clamped to its own first data point.
 *
 * One guard per sync group ({ isSyncingRange, isSyncingCrosshair }): the chart
 * the user touched fans the change out to the others; the library echoes that
 * change back through the targets' own subscriptions, and the guard drops
 * those echoes so nothing ping-pongs.
 *
 * Crosshair on a target panel: the horizontal crosshair line is hidden on all
 * regime panels, so only the vertical (date) line is visible. The price passed
 * to `setCrosshairPosition` then only matters for the invisible horizontal
 * line; we pass the target's own value at that date when it has one, else its
 * nearest earlier value (else nearest later), so the vertical line stays on
 * the same date on every panel even where that panel is whitespace. A panel
 * with no values at all is cleared instead.
 *
 * Display-only index arithmetic — no maths is re-implemented here.
 */

export interface SyncMember {
  chart: IChartApi;
  /** Series the crosshair attaches to on this panel. */
  series: ISeriesApi<"Line">;
  /** This panel's plotted value at grid index i, or null for whitespace. */
  valueAt(index: number): number | null;
  /**
   * Optional DOM node that receives a `data-visible-range` attribute (JSON:
   * logical from/to plus the grid dates they fall on) on every range change,
   * so an end-to-end test can observe zoom sync without window globals.
   */
  element?: HTMLElement | null;
}

export interface SyncGuard {
  isSyncingRange: boolean;
  isSyncingCrosshair: boolean;
}

export interface ChartSync {
  guard: SyncGuard;
  /** Adds a panel; returns a function that unsubscribes it. */
  register(id: string, member: SyncMember): () => void;
}

export interface ChartSyncOptions {
  /** UTC-seconds timestamps of the shared grid, in order. */
  gridTimes: number[];
  /** Range applied to each panel as it registers (default visible window). */
  initialRange?: { from: number; to: number } | null;
  /** Called with the hovered grid index, or null when the pointer leaves. */
  onHover?: (index: number | null) => void;
}

function crosshairPrice(member: SyncMember, index: number, length: number): number | null {
  const own = member.valueAt(index);
  if (own !== null) return own;
  for (let i = index - 1; i >= 0; i--) {
    const v = member.valueAt(i);
    if (v !== null) return v;
  }
  for (let i = index + 1; i < length; i++) {
    const v = member.valueAt(i);
    if (v !== null) return v;
  }
  return null;
}

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

export function createChartSync({ gridTimes, initialRange = null, onHover }: ChartSyncOptions): ChartSync {
  const guard: SyncGuard = { isSyncingRange: false, isSyncingCrosshair: false };
  const members = new Map<string, SyncMember>();
  const indexByTime = new Map<number, number>();
  gridTimes.forEach((t, i) => indexByTime.set(t, i));

  function markRange(member: SyncMember, range: { from: number; to: number }) {
    member.element?.setAttribute("data-visible-range", visibleRangeAttribute(gridTimes, range));
  }

  function fanOutRange(sourceId: string, range: LogicalRange | null) {
    if (guard.isSyncingRange || range === null) return;
    guard.isSyncingRange = true;
    try {
      members.forEach((m, id) => {
        if (id !== sourceId) m.chart.timeScale().setVisibleLogicalRange(range);
        markRange(m, range);
      });
    } finally {
      guard.isSyncingRange = false;
    }
  }

  function fanOutCrosshair(sourceId: string, param: MouseEventParams<Time>) {
    if (guard.isSyncingCrosshair) return;
    guard.isSyncingCrosshair = true;
    try {
      const time = typeof param.time === "number" ? param.time : undefined;
      const index = time === undefined ? undefined : indexByTime.get(time);
      members.forEach((m, id) => {
        if (id === sourceId) return;
        if (index === undefined || time === undefined) {
          m.chart.clearCrosshairPosition();
          return;
        }
        const price = crosshairPrice(m, index, gridTimes.length);
        if (price === null) m.chart.clearCrosshairPosition();
        else m.chart.setCrosshairPosition(price, time as Time, m.series);
      });
      onHover?.(index ?? null);
    } finally {
      guard.isSyncingCrosshair = false;
    }
  }

  return {
    guard,
    register(id, member) {
      members.set(id, member);
      const onRange = (range: LogicalRange | null) => fanOutRange(id, range);
      const onCrosshair = (param: MouseEventParams<Time>) => fanOutCrosshair(id, param);
      const timeScale = member.chart.timeScale();

      if (initialRange) {
        guard.isSyncingRange = true;
        try {
          timeScale.setVisibleLogicalRange(initialRange);
          markRange(member, initialRange);
        } finally {
          guard.isSyncingRange = false;
        }
      }
      timeScale.subscribeVisibleLogicalRangeChange(onRange);
      member.chart.subscribeCrosshairMove(onCrosshair);

      return () => {
        timeScale.unsubscribeVisibleLogicalRangeChange(onRange);
        member.chart.unsubscribeCrosshairMove(onCrosshair);
        members.delete(id);
      };
    },
  };
}

/** YYYY-MM-DD → midnight-UTC seconds; identical for every series. */
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
