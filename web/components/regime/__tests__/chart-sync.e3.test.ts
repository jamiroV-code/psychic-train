// E3 (VALIDATE): prove range + crosshair sync on TWO panels with different
// first dates, before building all seven.
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("lightweight-charts", () => import("@/test/mocks/lightweight-charts"));

import { createChart, LineSeries, type IChartApi, type ISeriesApi } from "lightweight-charts";
import { mockCharts, resetMockCharts } from "@/test/mocks/lightweight-charts";
import { createChartSync, defaultVisibleRange, isoDateToUtcSeconds } from "@/lib/regime-chart-sync";

const grid = ["2020-01-01", "2020-01-02", "2020-01-03", "2020-01-04", "2020-01-05"];
const times = grid.map(isoDateToUtcSeconds);
// Panel A has data from the first date; panel B only from the fourth.
const aValues = [1, 2, 3, 4, 5];
const bValues = [null, null, null, 40, 50];

function makePanel(values: (number | null)[]) {
  const chart = createChart(document.createElement("div"), {}) as unknown as IChartApi;
  const series = chart.addSeries(LineSeries, {}) as ISeriesApi<"Line">;
  series.setData(times.map((t, i) => (values[i] === null ? { time: t } : { time: t, value: values[i] })) as never);
  return { chart, series, valueAt: (i: number) => values[i] };
}

describe("E3 — two-panel sync with different first dates", () => {
  beforeEach(() => resetMockCharts());

  it("both panels hold the full shared grid, whitespace where B has no value", () => {
    makePanel(aValues);
    makePanel(bValues);
    expect(mockCharts[0].series[0].data).toHaveLength(grid.length);
    expect(mockCharts[1].series[0].data).toHaveLength(grid.length);
    expect(mockCharts[1].series[0].data[0]).toEqual({ time: times[0] });
  });

  it("syncs the logical range in both directions, without re-entrancy", () => {
    const sync = createChartSync({ gridTimes: times });
    sync.register("a", makePanel(aValues));
    sync.register("b", makePanel(bValues));
    const [a, b] = mockCharts;
    const bSet = b.timeScale().setVisibleLogicalRange;
    const aSet = a.timeScale().setVisibleLogicalRange;

    a.fireRange({ from: 1, to: 3 });
    expect(b.visibleLogicalRange).toEqual({ from: 1, to: 3 });
    expect(bSet).toHaveBeenCalledTimes(1);
    expect(aSet).not.toHaveBeenCalled(); // B's echo was dropped by the guard

    b.fireRange({ from: 0, to: 4 });
    expect(a.visibleLogicalRange).toEqual({ from: 0, to: 4 });
    expect(aSet).toHaveBeenCalledTimes(1);
    expect(bSet).toHaveBeenCalledTimes(1);
    expect(sync.guard.isSyncingRange).toBe(false);
  });

  it("applies the initial range to every panel as it registers", () => {
    const sync = createChartSync({ gridTimes: times, initialRange: { from: 2, to: 4 } });
    sync.register("a", makePanel(aValues));
    sync.register("b", makePanel(bValues));
    expect(mockCharts[0].visibleLogicalRange).toEqual({ from: 2, to: 4 });
    expect(mockCharts[1].visibleLogicalRange).toEqual({ from: 2, to: 4 });
  });

  it("syncs the crosshair both directions on the same date, even over whitespace", () => {
    const onHover = vi.fn();
    const sync = createChartSync({ gridTimes: times, onHover });
    sync.register("a", makePanel(aValues));
    sync.register("b", makePanel(bValues));
    const [a, b] = mockCharts;

    a.fireCrosshair(times[4]);
    expect(b.crosshair).toEqual({ price: 50, time: times[4], series: b.series[0] });
    expect(onHover).toHaveBeenLastCalledWith(4);

    // Hover a date where B is whitespace: the vertical line still moves to it.
    a.fireCrosshair(times[1]);
    expect(b.crosshair?.time).toBe(times[1]);
    expect(onHover).toHaveBeenLastCalledWith(1);

    b.fireCrosshair(times[3]);
    expect(a.crosshair).toEqual({ price: 4, time: times[3], series: a.series[0] });
    // Echo from A's setCrosshairPosition must not bounce back to B.
    expect(b.setCrosshairPosition).toHaveBeenCalledTimes(2);
    expect(sync.guard.isSyncingCrosshair).toBe(false);

    a.fireCrosshair(undefined);
    expect(b.clearCrosshairPosition).toHaveBeenCalled();
    expect(onHover).toHaveBeenLastCalledWith(null);
  });

  it("unsubscribes on unregister", () => {
    const sync = createChartSync({ gridTimes: times });
    const offA = sync.register("a", makePanel(aValues));
    const offB = sync.register("b", makePanel(bValues));
    const [a, b] = mockCharts;
    expect(a.rangeHandlers.size).toBe(1);
    expect(a.crosshairHandlers.size).toBe(1);
    offA();
    offB();
    expect(a.rangeHandlers.size).toBe(0);
    expect(a.crosshairHandlers.size).toBe(0);
    expect(b.rangeHandlers.size).toBe(0);
    expect(b.crosshairHandlers.size).toBe(0);
    a.fireRange({ from: 0, to: 1 });
    expect(b.timeScale().setVisibleLogicalRange).not.toHaveBeenCalled();
  });

  it("default range covers the last 3 calendar years", () => {
    const g = ["2019-01-01", "2022-09-23", "2022-09-24", "2024-01-01", "2025-09-24"];
    expect(defaultVisibleRange(g)).toEqual({ from: 2, to: 4 });
    expect(defaultVisibleRange([])).toBeNull();
  });
});
