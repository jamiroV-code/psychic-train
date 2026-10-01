import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import { RegimeDashboard } from "@/components/regime/RegimeDashboard";
import { defaultVisibleRange, isoDateToUtcSeconds, visibleRangeAttribute } from "@/lib/regime-chart-sync";
import { buildRegimeGridModel } from "@/lib/regime-view-model";
import { toLineSegments } from "@/lib/chart-segments";
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
  // Panels render in effects; wait for all seven before a test reads them.
  await waitFor(() => expect(screen.getAllByTestId(/^regime-chart-/)).toHaveLength(7));
  return utils;
}

const IDS = ["net_liquidity", "stablecoin_supply", "broad_dollar", "rrp_release", "etf_flows", "btc_dominance", "composite"];

describe("RegimeDashboard", () => {
  it("renders one panel per component plus the composite, and exactly seven chart hosts", async () => {
    await renderDashboard();
    for (const id of IDS) expect(screen.getByTestId(`regime-panel-${id}`)).toBeInTheDocument();
    // Seven plots, never more. The plots themselves are Svelte/LayerChart
    // islands fetched at runtime and so are not mounted under jsdom; that they
    // draw is covered by e2e/regime.spec.ts in a real browser.
    expect(screen.getAllByTestId(/^regime-chart-/)).toHaveLength(7);
    expect(screen.getByTestId("regime-reserved-column")).toBeEmptyDOMElement();
  });

  it("never fills a missing value: a date with no reading is absent, not 0", async () => {
    await renderDashboard();
    // The plots are islands and are not mounted under jsdom, so this asserts
    // the mapping that feeds them. Net liquidity has values at GRID[0] and
    // GRID[5] only. The four dates in between carry no reading, and the
    // guarantee is that they contribute NO point at all — a zero there would be
    // a number the API never sent.
    //
    // The two real readings do join up: the API flags a true hole with
    // `gap_before`, and it has not flagged one here, so they are consecutive
    // readings of a sparse series. (This matches the shipped lightweight-charts
    // path, where whitespace likewise never broke a line.)
    const model = buildRegimeGridModel(makeResponse());
    const netLiq = model.components.find((c) => c.component.id === "net_liquidity")!;
    const segments = toLineSegments(model.gridDates, netLiq.values, netLiq.gapBefore);
    expect(segments.map((s) => s.map((pt) => pt.value))).toEqual([[-41.2e9, 12e9]]);
    expect(segments[0].map((pt) => pt.i)).toEqual([0, 5]);
    expect(segments.flat().some((pt) => pt.value === 0)).toBe(false);

    // A component with no points at all contributes nothing to draw.
    const unavailable = model.components.find((c) => c.component.id === "broad_dollar")!;
    expect(toLineSegments(model.gridDates, unavailable.values, unavailable.gapBefore)).toEqual([]);
  });

  it("renders readable text for every gap reason, and stale still draws", async () => {
    await renderDashboard();
    expect(screen.getByTestId("regime-notice-stablecoin_supply").textContent).toContain("Stale");
    // Stale is a badge, not a replacement: the panel still has its plot.
    expect(screen.getByTestId("regime-chart-stablecoin_supply")).toBeInTheDocument();
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

  it("readout shows the last grid date when not hovering", async () => {
    await renderDashboard();
    const readout = screen.getByTestId("regime-readout");
    expect(readout.dataset.hovering).toBe("false");
    expect(screen.getByTestId("regime-readout-date-net_liquidity").textContent).toBe(`as of ${GRID[5]}`);
    expect(screen.getByTestId("regime-readout-cell-net_liquidity").textContent).toContain("+$12.0bn");
    expect(screen.getByTestId("regime-readout-cell-reproduced").textContent).toContain("coverage 80%");
    expect(screen.getByTestId("regime-readout-cell-published").textContent).toContain("LiqTide's label: neutral");
    // Hovering now starts in the chart island, which jsdom does not mount, so
    // the hovered states are asserted directly in Readout.test.tsx and end to
    // end in e2e/regime.spec.ts.
  });

  it("defaults the shared window to the last three calendar years", async () => {
    // The window every panel opens on. 3 years before 2026-09-23 is 2023-09-23,
    // and the first grid index on or after it is 3. Asserted on the pure
    // function because the range now lives in the island's shared store; that
    // all seven panels then agree on it is covered by e2e/regime.spec.ts.
    expect(defaultVisibleRange(GRID)).toEqual({ from: 3, to: 5 });
  });

  it("serialises the shared window the way data-visible-range reports it", async () => {
    // The island writes this attribute onto every panel through this exact
    // function, so the bytes an end-to-end test reads are pinned here.
    const times = GRID.map(isoDateToUtcSeconds);
    expect(JSON.parse(visibleRangeAttribute(times, { from: 3, to: 5 }))).toEqual({
      from: 3,
      to: 5,
      fromDate: GRID[3],
      toDate: GRID[5],
    });
  });

  it("exposes line breaks from gap_before as data-gap-dates (RFC-006 decision 5)", async () => {
    const res = makeResponse();
    res.components[0].points[1].gap_before = true;
    await renderDashboard(vi.fn(async () => res));
    const el = screen.getByTestId("regime-chart-net_liquidity");
    expect(el.getAttribute("data-gap-count")).toBe("1");
    expect(el.getAttribute("data-gap-dates")).toBe(GRID[5]);
    expect(screen.getByTestId("regime-chart-btc_dominance").getAttribute("data-gap-count")).toBe("0");
  });

  it("tears every panel down on unmount", async () => {
    const { unmount } = await renderDashboard();
    unmount();
    // Each panel disposes its island and deregisters from the shared store in
    // its effect cleanup; what remains observable here is that nothing is left
    // in the document.
    expect(screen.queryAllByTestId(/^regime-chart-/)).toHaveLength(0);
    expect(screen.queryByTestId("regime-dashboard")).toBeNull();
  });

  it("shows a DeadDataNotice when the fetcher fails, and no panels", async () => {
    const fetchData = vi.fn(async () => {
      throw new Error("API request failed: /api/regime/components -> 500");
    });
    render(<RegimeDashboard fetchData={fetchData} />);
    await waitFor(() => expect(screen.getByTestId("regime-error")).toBeInTheDocument());
    expect(screen.getByTestId("regime-error").textContent).toContain("-> 500");
    expect(screen.queryAllByTestId(/^regime-chart-/)).toHaveLength(0);
  });

  it("shows a loading state before data arrives", () => {
    render(<RegimeDashboard fetchData={() => new Promise(() => {})} />);
    expect(screen.getByTestId("regime-loading")).toBeInTheDocument();
  });
});

describe("regime data gaps (RFC-005 decision 9)", () => {
  it("breaks the line at a flagged hole and leaves an isolated point alone", () => {
    // Previously asserted against lightweight-charts' transparent-segment
    // workaround. LayerChart breaks a line natively, so the guarantee is
    // asserted on the mapping itself (see lib/__tests__/chart-segments.test.ts
    // for the full set).
    const data = makeResponse();
    const btc = data.components.find((c) => c.id === "btc_dominance")!;
    btc.points = [
      { date: GRID[2], value: 0.1, raw: 50, contribution: -0.05, gap_before: false },
      { date: GRID[3], value: 0.2, raw: 51, contribution: -0.1, gap_before: false },
      { date: GRID[5], value: 0.3, raw: 57.3, contribution: -0.15, gap_before: true },
    ];
    const model = buildRegimeGridModel(data);
    const line = model.components.find((c) => c.component.id === "btc_dominance")!;
    const segments = toLineSegments(model.gridDates, line.values, line.gapBefore);
    // GRID[5] follows a flagged hole, so it is its own segment, never bridged.
    expect(segments.map((s2) => s2.map((pt) => pt.value))).toEqual([[0.1, 0.2], [0.3]]);

    // A series with no flags is one unbroken run wherever it has values, no
    // matter how sparse it is on the shared grid.
    const netLiq = model.components.find((c) => c.component.id === "net_liquidity")!;
    expect(toLineSegments(model.gridDates, netLiq.values, netLiq.gapBefore).length).toBe(1);
  });
});
