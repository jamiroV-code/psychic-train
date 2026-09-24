import { beforeEach, describe, expect, it, vi } from "vitest";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";

vi.mock("lightweight-charts", () => import("@/test/mocks/lightweight-charts"));

import { createChart, mockCharts, resetMockCharts } from "@/test/mocks/lightweight-charts";
import { RegimeDashboard } from "@/components/regime/RegimeDashboard";
import { isoDateToUtcSeconds } from "@/lib/regime-chart-sync";
import type { RegimeComponent, RegimeComponentsResponse } from "@/lib/types/regime";

const GRID = ["2021-01-04", "2022-06-01", "2023-01-02", "2024-01-11", "2025-07-12", "2026-09-23"];

function component(over: Partial<RegimeComponent> & Pick<RegimeComponent, "id">): RegimeComponent {
  return {
    label: `${over.id} label`,
    weight: 0.1,
    source: `${over.id} source`,
    transform: `${over.id} transform`,
    frequency: "daily",
    unit: "USD",
    status: "ok",
    reason: null,
    notes: [],
    first_date: GRID[0],
    last_date: GRID[5],
    last_fetched_utc: "2026-09-24T06:00:00Z",
    max_gap_days: 5,
    points: [],
    ...over,
  };
}

function makeResponse(): RegimeComponentsResponse {
  return {
    generated_utc: "2026-09-24T18:00:00Z",
    grid_dates: GRID,
    components: [
      component({
        id: "net_liquidity",
        label: "Net liquidity (4-week change)",
        weight: 0.3,
        source: "FRED: WALCL − WDTGAL − RRPONTSYD×1000",
        transform: "level(t) − level(t − 28 days); contribution = tanh(Δ / $150bn)",
        points: [
          { date: GRID[0], value: -41.2e9, raw: 7.1024e12, contribution: -0.27, gap_before: false },
          { date: GRID[5], value: 12e9, raw: 6e12, contribution: 0.08, gap_before: false },
        ],
      }),
      component({ id: "stablecoin_supply", unit: "fraction", status: "stale", reason: "refresh failed; serving cache", points: [{ date: GRID[4], value: 0.01, raw: 2e11, contribution: 0.76, gap_before: false }] }),
      component({ id: "broad_dollar", unit: "fraction", status: "unavailable", reason: "FRED unreachable and nothing cached", first_date: null, last_date: null, points: [] }),
      component({ id: "rrp_release", status: "no_data", reason: "no points in the requested date range", points: [] }),
      component({
        id: "etf_flows",
        status: "not_applicable",
        reason: "requested range ends before 2024-01-11",
        notes: ["Not applicable before 2024-01-11 (US spot-BTC ETFs launched that day)."],
        points: [],
      }),
      component({
        id: "btc_dominance",
        unit: "percentage points",
        first_date: "2025-07-12",
        notes: ["No data before 2025-07-12."],
        points: [
          { date: GRID[4], value: -0.5, raw: 58.1, contribution: 0.24, gap_before: false },
          { date: GRID[5], value: 0.3, raw: 57.3, contribution: -0.15, gap_before: false },
        ],
      }),
    ],
    composite: {
      reproduced: {
        label: "Reproduced tide index (this app)",
        normalisation: "sign·tanh(impulse/scale); 50 + 50·Σw·x / Σw_present",
        max_gap_days: 5,
        points: [{ date: GRID[5], value: 46.8, coverage: 0.8, gap_before: false }],
      },
      published: {
        label: "LiqTide tide index (published)",
        attribution: "Data: LiqTide (liqtide.com)",
        status: "ok",
        max_gap_days: 10,
        points: [
          { date: GRID[4], value: 55, regime_label: null, gap_before: false },
          { date: GRID[5], value: 52, regime_label: "neutral", gap_before: false },
        ],
      },
      agreement: { overlap_days: 380, pearson_r: 0.71, mean_abs_diff: 6.4, full_coverage_days: 90, full_coverage_mean_abs_diff: 2.1 },
    },
  };
}

async function renderDashboard(fetchData = vi.fn(async () => makeResponse())) {
  const utils = render(<RegimeDashboard fetchData={fetchData} />);
  await waitFor(() => expect(screen.getByTestId("regime-dashboard")).toBeInTheDocument());
  return utils;
}

const IDS = ["net_liquidity", "stablecoin_supply", "broad_dollar", "rrp_release", "etf_flows", "btc_dominance", "composite"];

describe("RegimeDashboard", () => {
  beforeEach(() => resetMockCharts());

  it("renders one panel per component plus the composite, with exactly seven createChart calls", async () => {
    await renderDashboard();
    for (const id of IDS) expect(screen.getByTestId(`regime-panel-${id}`)).toBeInTheDocument();
    expect(createChart).toHaveBeenCalledTimes(7);
    expect(screen.getByTestId("regime-reserved-column")).toBeEmptyDOMElement();
  });

  it("feeds every series grid_dates.length points, whitespace where no value (never 0)", async () => {
    await renderDashboard();
    // Line series only; dots-only companions (isolated points) are checked separately.
    const all = mockCharts.flatMap((c) => c.series).filter((s) => s.options.lineVisible !== false);
    expect(all).toHaveLength(8); // 6 components + reproduced + published
    for (const s of all) expect(s.data).toHaveLength(GRID.length);
    const netLiq = mockCharts[0].series[0].data as { time: number; value?: number }[];
    expect(netLiq[0]).toEqual({ time: isoDateToUtcSeconds(GRID[0]), value: -41.2e9 });
    expect(netLiq[1]).toEqual({ time: isoDateToUtcSeconds(GRID[1]) });
    const unavailable = mockCharts[2].series[0].data as object[];
    expect(unavailable.every((p) => !("value" in p))).toBe(true);
  });

  it("renders readable text for every gap reason, and stale still draws", async () => {
    await renderDashboard();
    expect(screen.getByTestId("regime-notice-stablecoin_supply").textContent).toContain("Stale");
    expect((mockCharts[1].series[0].data as object[]).some((p) => "value" in p)).toBe(true);
    expect(screen.getByTestId("regime-notice-broad_dollar").textContent).toBe("Unavailable — FRED unreachable and nothing cached");
    expect(screen.getByTestId("regime-notice-rrp_release").textContent).toContain("No data");
    expect(screen.getByTestId("regime-notice-etf_flows").textContent).toContain("Not applicable");
    expect(screen.getByTestId("regime-panel-notes-etf_flows").textContent).toContain("Not applicable before 2024-01-11");
    expect(screen.getByTestId("regime-panel-btc_dominance").textContent).toContain("from: 2025-07-12");
    expect(screen.queryByTestId("regime-notice-net_liquidity")).toBeNull();
  });

  it("composite panel has two labelled lines and LiqTide attribution", async () => {
    await renderDashboard();
    expect(screen.getByTestId("regime-legend-reproduced").textContent).toContain("Reproduced tide index (this app)");
    expect(screen.getByTestId("regime-legend-published").textContent).toContain("LiqTide tide index (published)");
    expect(screen.getByTestId("regime-attribution-composite").textContent).toBe("Data: LiqTide (liqtide.com)");
    // LiqTide's regime label is never drawn on the chart — readout/drill-down only.
    expect(screen.getByTestId("regime-panel-composite").textContent).not.toContain("neutral");
  });

  it("drill-down lists source, transform and weight", async () => {
    await renderDashboard();
    fireEvent.click(screen.getByTestId("regime-panel-header-net_liquidity"));
    const dd = screen.getByTestId("regime-drilldown-net_liquidity");
    expect(dd.textContent).toContain("FRED: WALCL − WDTGAL − RRPONTSYD×1000");
    expect(dd.textContent).toContain("level(t) − level(t − 28 days)");
    expect(dd.textContent).toContain("30%");
    expect(dd.textContent).toContain("2026-09-24T06:00:00Z");
    fireEvent.click(screen.getByTestId("regime-drilldown-close"));
    expect(screen.queryByTestId("regime-drilldown-net_liquidity")).toBeNull();

    fireEvent.click(screen.getByTestId("regime-panel-header-composite"));
    const cd = screen.getByTestId("regime-drilldown-composite");
    expect(cd.textContent).toContain("sign·tanh(impulse/scale)");
    expect(cd.textContent).toContain("60%");
    expect(cd.textContent).toContain("0.710");
    expect(cd.textContent).toContain("380");
  });

  it("readout shows the last grid date when not hovering and follows the crosshair", async () => {
    await renderDashboard();
    const readout = screen.getByTestId("regime-readout");
    expect(readout.dataset.hovering).toBe("false");
    expect(screen.getByTestId("regime-readout-date-net_liquidity").textContent).toBe(`as of ${GRID[5]}`);
    expect(screen.getByTestId("regime-readout-cell-net_liquidity").textContent).toContain("+$12.0bn");
    expect(screen.getByTestId("regime-readout-cell-reproduced").textContent).toContain("coverage 80%");
    expect(screen.getByTestId("regime-readout-cell-published").textContent).toContain("LiqTide's label: neutral");

    act(() => mockCharts[0].fireCrosshair(isoDateToUtcSeconds(GRID[1])));
    expect(screen.getByTestId("regime-readout-date-net_liquidity").textContent).toBe(`as of ${GRID[1]}`);
    expect(screen.getByTestId("regime-readout-cell-net_liquidity").textContent).toContain("no value");
    expect(screen.getByTestId("regime-readout-cell-net_liquidity").textContent).not.toMatch(/\$0/);

    act(() => mockCharts[0].fireCrosshair(isoDateToUtcSeconds(GRID[0])));
    const cell = screen.getByTestId("regime-readout-cell-net_liquidity").textContent;
    expect(cell).toContain("−$41.2bn");
    expect(cell).toContain("level $7.10tn");
    expect(cell).toContain("contribution −0.270");

    act(() => mockCharts[0].fireCrosshair(undefined));
    expect(screen.getByTestId("regime-readout-date-net_liquidity").textContent).toBe(`as of ${GRID[5]}`);
  });

  it("wires range + crosshair sync across all seven panels with a 3-year default range", async () => {
    await renderDashboard();
    // 3 years before 2026-09-23 = 2023-09-23 → first grid index on/after it is 3.
    for (const c of mockCharts) {
      expect(c.visibleLogicalRange).toEqual({ from: 3, to: 5 });
      expect(c.rangeHandlers.size).toBe(1);
      expect(c.crosshairHandlers.size).toBe(1);
    }
    act(() => mockCharts[6].fireRange({ from: 0, to: 2 }));
    for (const c of mockCharts) expect(c.visibleLogicalRange).toEqual({ from: 0, to: 2 });

    act(() => mockCharts[5].fireCrosshair(isoDateToUtcSeconds(GRID[4])));
    const t4 = isoDateToUtcSeconds(GRID[4]);
    // Panels with any data follow the date (net liquidity is whitespace at t4 but still aligned)…
    for (const i of [0, 1, 6]) expect(mockCharts[i].crosshair?.time).toBe(t4);
    // …panels with no data at all have nothing to attach to and are cleared.
    for (const i of [2, 3, 4]) expect(mockCharts[i].clearCrosshairPosition).toHaveBeenCalled();
  });

  it("unsubscribes every sync handler and removes every chart on unmount", async () => {
    const { unmount } = await renderDashboard();
    unmount();
    for (const c of mockCharts) {
      expect(c.rangeHandlers.size).toBe(0);
      expect(c.crosshairHandlers.size).toBe(0);
      expect(c.removed).toBe(true);
    }
  });

  it("shows a DeadDataNotice when the fetcher fails, and no charts", async () => {
    const fetchData = vi.fn(async () => {
      throw new Error("API request failed: /api/regime/components -> 500");
    });
    render(<RegimeDashboard fetchData={fetchData} />);
    await waitFor(() => expect(screen.getByTestId("regime-error")).toBeInTheDocument());
    expect(screen.getByTestId("regime-error").textContent).toContain("-> 500");
    expect(createChart).not.toHaveBeenCalled();
  });

  it("shows a loading state before data arrives", () => {
    render(<RegimeDashboard fetchData={() => new Promise(() => {})} />);
    expect(screen.getByTestId("regime-loading")).toBeInTheDocument();
  });
});

describe("RegimeDashboard data gaps (RFC-005 decision 9)", () => {
  beforeEach(() => resetMockCharts());

  it("hides only the segment into a gap_before point and keeps weekly series continuous", async () => {
    const data = makeResponse();
    const btc = data.components.find((c) => c.id === "btc_dominance")!;
    btc.points = [
      { date: GRID[2], value: 0.1, raw: 50, contribution: -0.05, gap_before: false },
      { date: GRID[3], value: 0.2, raw: 51, contribution: -0.1, gap_before: false },
      { date: GRID[5], value: 0.3, raw: 57.3, contribution: -0.15, gap_before: true },
    ];
    await renderDashboard(vi.fn(async () => data));
    const btcData = mockCharts[5].series[0].data as { time: number; value?: number; color?: string }[];
    expect(btcData[3]).toEqual({ time: isoDateToUtcSeconds(GRID[3]), value: 0.2, color: "rgba(0, 0, 0, 0)" });
    expect(btcData.filter((p) => p.color !== undefined)).toHaveLength(1);
    // GRID[5] follows a hole and has no later point: it is isolated -> dot series.
    const dotSeries = mockCharts[5].series[1];
    expect(dotSeries.options).toMatchObject({ lineVisible: false, pointMarkersVisible: true });
    expect((dotSeries.data as object[]).filter((p) => "value" in p)).toEqual([
      { time: isoDateToUtcSeconds(GRID[5]), value: 0.3 },
    ]);
    // Net liquidity (no flags) has no hidden segments.
    expect((mockCharts[0].series[0].data as object[]).some((p) => "color" in p)).toBe(false);
  });

  it("crosshair sync still targets the line series, not the dots companion", async () => {
    await renderDashboard();
    // stablecoin_supply has one point -> it gets a dots series at index 1.
    expect(mockCharts[1].series).toHaveLength(2);
    act(() => mockCharts[0].fireCrosshair(isoDateToUtcSeconds(GRID[4])));
    expect(mockCharts[1].crosshair?.series).toBe(mockCharts[1].series[0]);
  });
});
