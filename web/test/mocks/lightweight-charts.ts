/**
 * Shared `lightweight-charts` mock for vitest (RFC-005). jsdom has no canvas,
 * so the real library cannot render. This mock records every chart, series
 * and subscription so tests can fire range / crosshair events by hand.
 *
 * Like the real library, `setVisibleLogicalRange` and `setCrosshairPosition`
 * notify the chart's own subscribers synchronously. That echo is what makes
 * a sync guard necessary, so tests exercise it for real.
 *
 * Usage in a test file:
 *   vi.mock("lightweight-charts", () => import("@/test/mocks/lightweight-charts"));
 *   import { mockCharts, resetMockCharts } from "@/test/mocks/lightweight-charts";
 *
 * Existing screener tests keep their own inline mocks; this helper is additive.
 */
import { vi } from "vitest";

export type LogicalRange = { from: number; to: number } | null;
export type CrosshairParam = { time?: number; logical?: number; seriesData: Map<unknown, unknown> };
type RangeHandler = (range: LogicalRange) => void;
type CrosshairHandler = (param: CrosshairParam) => void;

export interface MockSeries {
  type: unknown;
  options: Record<string, unknown>;
  data: unknown[];
  setData: ReturnType<typeof vi.fn>;
  applyOptions: ReturnType<typeof vi.fn>;
}

export interface MockChart {
  container: unknown;
  options: Record<string, unknown>;
  series: MockSeries[];
  rangeHandlers: Set<RangeHandler>;
  timeRangeHandlers: Set<(r: unknown) => void>;
  crosshairHandlers: Set<CrosshairHandler>;
  visibleLogicalRange: LogicalRange;
  crosshair: { price: number; time: number; series: MockSeries } | null;
  removed: boolean;
  /** Simulate the user zooming/scrolling this chart. */
  fireRange(range: LogicalRange): void;
  /** Simulate the user hovering this chart (time undefined = pointer left). */
  fireCrosshair(time: number | undefined): void;
  timeScale(): Record<string, ReturnType<typeof vi.fn>>;
  addSeries: ReturnType<typeof vi.fn>;
  applyOptions: ReturnType<typeof vi.fn>;
  remove: ReturnType<typeof vi.fn>;
  subscribeCrosshairMove: ReturnType<typeof vi.fn>;
  unsubscribeCrosshairMove: ReturnType<typeof vi.fn>;
  setCrosshairPosition: ReturnType<typeof vi.fn>;
  clearCrosshairPosition: ReturnType<typeof vi.fn>;
}

export const mockCharts: MockChart[] = [];

export function resetMockCharts(): void {
  mockCharts.length = 0;
  createChart.mockClear();
}

function makeChart(container: unknown, options: Record<string, unknown>): MockChart {
  const chart = {
    container,
    options,
    series: [],
    rangeHandlers: new Set(),
    timeRangeHandlers: new Set(),
    crosshairHandlers: new Set(),
    visibleLogicalRange: null,
    crosshair: null,
    removed: false,
  } as unknown as MockChart;

  const timeScaleApi = {
    subscribeVisibleLogicalRangeChange: vi.fn((h: RangeHandler) => chart.rangeHandlers.add(h)),
    unsubscribeVisibleLogicalRangeChange: vi.fn((h: RangeHandler) => chart.rangeHandlers.delete(h)),
    setVisibleLogicalRange: vi.fn((range: { from: number; to: number }) => {
      chart.visibleLogicalRange = range;
      chart.rangeHandlers.forEach((h) => h(range)); // real-library echo
    }),
    getVisibleLogicalRange: vi.fn(() => chart.visibleLogicalRange),
    subscribeVisibleTimeRangeChange: vi.fn((h: (r: unknown) => void) => chart.timeRangeHandlers.add(h)),
    unsubscribeVisibleTimeRangeChange: vi.fn((h: (r: unknown) => void) => chart.timeRangeHandlers.delete(h)),
    setVisibleRange: vi.fn(),
    fitContent: vi.fn(),
  };

  chart.timeScale = () => timeScaleApi;
  chart.addSeries = vi.fn((type: unknown, seriesOptions: Record<string, unknown> = {}) => {
    const series = {
      type,
      options: seriesOptions,
      data: [],
      applyOptions: vi.fn(),
    } as unknown as MockSeries;
    series.setData = vi.fn((data: unknown[]) => {
      series.data = data;
    });
    chart.series.push(series);
    return series;
  });
  chart.applyOptions = vi.fn();
  chart.remove = vi.fn(() => {
    chart.removed = true;
  });
  chart.subscribeCrosshairMove = vi.fn((h: CrosshairHandler) => chart.crosshairHandlers.add(h));
  chart.unsubscribeCrosshairMove = vi.fn((h: CrosshairHandler) => chart.crosshairHandlers.delete(h));
  chart.setCrosshairPosition = vi.fn((price: number, time: number, series: MockSeries) => {
    chart.crosshair = { price, time, series };
    chart.crosshairHandlers.forEach((h) => h({ time, seriesData: new Map() })); // real-library echo
  });
  chart.clearCrosshairPosition = vi.fn(() => {
    chart.crosshair = null;
  });
  chart.fireRange = (range) => {
    chart.visibleLogicalRange = range;
    chart.rangeHandlers.forEach((h) => h(range));
  };
  chart.fireCrosshair = (time) => {
    chart.crosshairHandlers.forEach((h) => h({ time, seriesData: new Map() }));
  };
  return chart;
}

export const createChart = vi.fn((container: unknown, options: Record<string, unknown> = {}) => {
  const chart = makeChart(container, options);
  mockCharts.push(chart);
  return chart;
});

export const LineSeries = "LineSeries";
