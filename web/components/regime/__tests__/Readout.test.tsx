import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { Readout } from "@/components/regime/Readout";
import { buildRegimeGridModel } from "@/lib/regime-view-model";
import type { RegimeComponent, RegimeComponentsResponse } from "@/lib/types/regime";

/**
 * The hovered states of the readout.
 *
 * These used to be driven through RegimeDashboard by firing a crosshair on a
 * mocked lightweight-charts instance. The plot is now a Svelte/LayerChart
 * island that jsdom does not mount, so hovering is asserted here instead —
 * directly on the component that formats the values, which is both simpler and
 * independent of whatever chart library reports the hover. That the hover
 * actually reaches this component from a real chart is covered by
 * e2e/regime.spec.ts.
 */

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

const response: RegimeComponentsResponse = {
  generated_utc: "2026-09-24T18:00:00Z",
  grid_dates: GRID,
  components: [
    component({
      id: "net_liquidity",
      label: "Net liquidity (4-week change)",
      weight: 0.3,
      points: [
        { date: GRID[0], value: -41.2e9, raw: 7.1024e12, contribution: -0.27, gap_before: false },
        { date: GRID[5], value: 12e9, raw: 6e12, contribution: 0.08, gap_before: false },
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
      points: [{ date: GRID[5], value: 52, regime_label: "neutral", gap_before: false }],
    },
    agreement: { overlap_days: 380, pearson_r: 0.71, mean_abs_diff: 6.4, full_coverage_days: 90, full_coverage_mean_abs_diff: 2.1 },
  },
};

function renderAt(hoverIndex: number | null) {
  const model = buildRegimeGridModel(response);
  return render(<Readout model={model} composite={response.composite} hoverIndex={hoverIndex} />);
}

describe("Readout hovering", () => {
  it("shows the latest grid date when not hovering", () => {
    renderAt(null);
    expect(screen.getByTestId("regime-readout").dataset.hovering).toBe("false");
    expect(screen.getByTestId("regime-readout-date-net_liquidity").textContent).toBe(`as of ${GRID[5]}`);
    expect(screen.getByTestId("regime-readout-cell-net_liquidity").textContent).toContain("+$12.0bn");
  });

  it("moves every cell to the hovered date", () => {
    renderAt(0);
    expect(screen.getByTestId("regime-readout").dataset.hovering).toBe("true");
    expect(screen.getByTestId("regime-readout-date-net_liquidity").textContent).toBe(`as of ${GRID[0]}`);
    const cell = screen.getByTestId("regime-readout-cell-net_liquidity").textContent ?? "";
    expect(cell).toContain("−$41.2bn");
    expect(cell).toContain("level $7.10tn");
    expect(cell).toContain("contribution −0.270");
  });

  it("reads a date with no value as 'no value', never as 0", () => {
    // GRID[1] is whitespace for net liquidity. Showing 0 there would invent a
    // reading the API never sent — the rule this whole dashboard is built on.
    renderAt(1);
    const cell = screen.getByTestId("regime-readout-cell-net_liquidity").textContent ?? "";
    expect(cell).toContain("no value");
    expect(cell).not.toMatch(/\$0/);
  });

  it("falls back to the latest date for an out-of-range hover index", () => {
    renderAt(999);
    expect(screen.getByTestId("regime-readout-date-net_liquidity").textContent).toBe(`as of ${GRID[5]}`);
  });
});
