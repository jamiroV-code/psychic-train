import { describe, expect, it } from "vitest";
import { act, fireEvent, render, screen } from "@testing-library/react";

import { ComparisonOverlay, type ComparisonOverlayProps } from "@/components/onchain/ComparisonOverlay";
import { ComparisonReadout } from "@/components/onchain/ComparisonReadout";
import { overlayLines } from "@/lib/onchain-overlay-lines";
import { chainColor, comparisonValues } from "@/lib/onchain-view-model";
import { isoDateToUtcSeconds } from "@/lib/regime-chart-sync";
import { GRID, makeResponse } from "./fixtures";

/**
 * The plot is a Svelte/LayerChart island (ADR-1) that jsdom does not mount, so
 * what was asserted against a mocked lightweight-charts instance is asserted
 * here against the real mapping and the real DOM contract instead. `data-mode`
 * and `data-log-scale` are the same `effectiveLog`/`mode` the island is handed,
 * so they prove what the chart options used to.
 */

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

describe("ComparisonOverlay", () => {
  it("starts in index mode on a log scale when log_scale_default is true", () => {
    render(<ComparisonOverlay {...props()} />);
    expect(screen.getByTestId("onchain-comparison")).toHaveAttribute("data-log-scale", "true");
    expect(screen.getByTestId("onchain-comparison-log-toggle")).toBeChecked();
  });

  it("starts linear when log_scale_default is false", () => {
    render(<ComparisonOverlay {...props()} logScaleDefault={false} />);
    expect(screen.getByTestId("onchain-comparison")).toHaveAttribute("data-log-scale", "false");
    expect(screen.getByTestId("onchain-comparison-log-toggle")).not.toBeChecked();
  });

  it("switching to % above low draws the API's alternative values, forces linear and disables log", async () => {
    render(<ComparisonOverlay {...props()} />);
    await act(async () => fireEvent.click(screen.getByTestId("onchain-comparison-mode-pct")));
    expect(screen.getByTestId("onchain-comparison")).toHaveAttribute("data-mode", "pct");
    // Log is forced off in pct mode, so the plot is handed logScale: false.
    expect(screen.getByTestId("onchain-comparison")).toHaveAttribute("data-log-scale", "false");
    expect(screen.getByTestId("onchain-comparison-log-toggle")).toBeDisabled();
    // The alternative array comes from the API untouched.
    const p = props();
    expect(overlayLines(p.series, "pct", {})[0].values).toEqual([null, null, null, 6, 8, 10]);
  });

  it("tags rebased_late series as 'late start' with the rebase date", () => {
    render(<ComparisonOverlay {...props()} />);
    expect(screen.getByTestId("onchain-rebased-late-robinhood")).toHaveTextContent(`late start (${GRID[4]})`);
    expect(screen.queryByTestId("onchain-rebased-late-ethereum")).toBeNull();
  });

  it("draws one line per chain in its fixed colour, on one axis", () => {
    const p = props();
    const lines = overlayLines(p.series, "index", {});
    expect(lines).toHaveLength(6);
    expect(lines.map((l) => l.key)).toEqual(["ethereum", "base", "arbitrum", "optimism", "polygon", "robinhood"]);
    expect(lines.map((l) => l.color)).toEqual(
      ["ethereum", "base", "arbitrum", "optimism", "polygon", "robinhood"].map((id) => chainColor(id))
    );
    // Colour follows the chain, not the mode: switching view must not reshuffle it.
    expect(overlayLines(p.series, "pct", {}).map((l) => l.color)).toEqual(lines.map((l) => l.color));
  });

  it("legend carries a direct endpoint label per chain", () => {
    render(<ComparisonOverlay {...props()} />);
    expect(screen.getByTestId("onchain-legend-ethereum")).toHaveTextContent("Ethereum 105.0");
  });

  it("readout lists every chain at the hovered date, and says so when nothing is hovered", () => {
    const p = props();
    const { rerender } = render(
      <ComparisonReadout series={p.series} labels={p.labels} gridDates={p.gridDates} mode="index" hoverIndex={null} />
    );
    expect(screen.getByTestId("onchain-comparison-readout")).toHaveAttribute("data-hovering", "false");

    rerender(
      <ComparisonReadout series={p.series} labels={p.labels} gridDates={p.gridDates} mode="index" hoverIndex={3} />
    );
    const readout = screen.getByTestId("onchain-comparison-readout");
    expect(readout).toHaveAttribute("data-hovering", "true");
    expect(readout).toHaveTextContent(GRID[3]);
    expect(readout).toHaveTextContent("103.0 Ethereum");
    // A chain with no value on that date says so rather than showing a number.
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
