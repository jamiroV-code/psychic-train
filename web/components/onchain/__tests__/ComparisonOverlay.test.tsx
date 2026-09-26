import { beforeEach, describe, expect, it, vi } from "vitest";
import { act, fireEvent, render, screen } from "@testing-library/react";

vi.mock("lightweight-charts", () => import("@/test/mocks/onchain-lightweight-charts"));

import { PriceScaleMode, mockCharts, resetMockCharts } from "@/test/mocks/onchain-lightweight-charts";
import { ComparisonOverlay, type ComparisonOverlayProps } from "@/components/onchain/ComparisonOverlay";
import { chainColor } from "@/lib/onchain-view-model";
import { isoDateToUtcSeconds } from "@/lib/regime-chart-sync";
import { GRID, makeResponse } from "./fixtures";

function props(): ComparisonOverlayProps {
  const r = makeResponse();
  return {
    series: r.comparison.series,
    labels: Object.fromEntries(r.chains.map((c) => [c.id, c.label])),
    gapBefore: {},
    gridDates: r.grid_dates,
    gridTimes: r.grid_dates.map(isoDateToUtcSeconds),
    startDate: r.comparison.start_date,
    logScaleDefault: r.comparison.log_scale_default,
    normalizationMethod: r.comparison.normalization_method,
    alternativeMethod: r.comparison.alternative_method,
    windowDays: 180,
  };
}

function scaleMode(): unknown {
  const chart = mockCharts[mockCharts.length - 1];
  return (chart.options.rightPriceScale as { mode: unknown }).mode;
}

beforeEach(() => resetMockCharts());

describe("ComparisonOverlay", () => {
  it("starts in index mode on a log scale when log_scale_default is true", () => {
    render(<ComparisonOverlay {...props()} />);
    expect(screen.getByTestId("onchain-comparison")).toHaveAttribute("data-log-scale", "true");
    expect(scaleMode()).toBe(PriceScaleMode.Logarithmic);
    expect(screen.getByTestId("onchain-comparison-log-toggle")).toBeChecked();
  });

  it("starts linear when log_scale_default is false", () => {
    render(<ComparisonOverlay {...props()} logScaleDefault={false} />);
    expect(scaleMode()).toBe(PriceScaleMode.Normal);
  });

  it("switching to % above low draws the API's alternative values, forces linear and disables log", async () => {
    render(<ComparisonOverlay {...props()} />);
    await act(async () => fireEvent.click(screen.getByTestId("onchain-comparison-mode-pct")));
    expect(screen.getByTestId("onchain-comparison")).toHaveAttribute("data-mode", "pct");
    expect(scaleMode()).toBe(PriceScaleMode.Normal);
    expect(screen.getByTestId("onchain-comparison-log-toggle")).toBeDisabled();
    const chart = mockCharts[mockCharts.length - 1];
    const first = chart.series[0].data as { value?: number }[];
    expect(first.map((p) => p.value ?? null)).toEqual([null, null, null, 6, 8, 10]);
  });

  it("tags rebased_late series as 'late start' with the rebase date", () => {
    render(<ComparisonOverlay {...props()} />);
    expect(screen.getByTestId("onchain-rebased-late-robinhood")).toHaveTextContent(`late start (${GRID[4]})`);
    expect(screen.queryByTestId("onchain-rebased-late-ethereum")).toBeNull();
  });

  it("draws one 2px line per chain in its fixed colour, on one axis", () => {
    render(<ComparisonOverlay {...props()} />);
    const chart = mockCharts[mockCharts.length - 1];
    expect(chart.series).toHaveLength(6);
    expect(chart.series.map((s) => s.options.color)).toEqual(
      ["ethereum", "base", "arbitrum", "optimism", "polygon", "robinhood"].map((id) => chainColor(id))
    );
    expect(chart.series.every((s) => s.options.lineWidth === 2 && s.options.priceScaleId === undefined)).toBe(true);
  });

  it("legend carries a direct endpoint label per chain; tooltip lists every chain at the hovered date", () => {
    render(<ComparisonOverlay {...props()} />);
    expect(screen.getByTestId("onchain-legend-ethereum")).toHaveTextContent("Ethereum 105.0");
    const chart = mockCharts[mockCharts.length - 1];
    act(() => chart.fireCrosshair(isoDateToUtcSeconds(GRID[3])));
    const readout = screen.getByTestId("onchain-comparison-readout");
    expect(readout).toHaveTextContent(GRID[3]);
    expect(readout).toHaveTextContent("103.0 Ethereum");
    expect(readout).toHaveTextContent("— Robinhood Chain");
  });

  it("sets the visible range from the API start date and has a table view", () => {
    render(<ComparisonOverlay {...props()} startDate={GRID[2]} />);
    expect(JSON.parse(screen.getByTestId("onchain-comparison-chart").getAttribute("data-visible-range")!)).toMatchObject({
      fromDate: GRID[2],
    });
    expect(screen.getByTestId("onchain-comparison-table")).toHaveTextContent("late start");
  });

  it("AC-13: raw values are rejected at compile time (checked by tsc --noEmit)", () => {
    const p = props();
    const raw = { ...p.series[0], points: [{ date: GRID[0], value: 1234 }] };
    // @ts-expect-error raw points must not be accepted by the normalised overlay
    const bad: ComparisonOverlayProps = { ...p, series: [raw] };
    // @ts-expect-error a raw `value` field is typed `never`
    const bad2: ComparisonOverlayProps = { ...p, series: [{ ...p.series[0], value: 1 }] };
    expect(bad.series).toHaveLength(1);
    expect(bad2.series).toHaveLength(1);
  });
});
