// SANDBOX NOTE: see ScreenerBoard.test.tsx — same environment limitation.
import { describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { RelativePerformanceChart } from "@/components/screener/RelativePerformanceChart";
import { buildRelativeLines, formatPercentChange } from "@/lib/relative-performance-lines";
import { CATEGORICAL } from "@/lib/chart-palette";
import type { RelativePerformanceResponse, RelativePerformanceTimeframe } from "@/lib/types/screener";

function makeResponse(timeframe: RelativePerformanceTimeframe): RelativePerformanceResponse {
  return {
    timeframe,
    series: [
      { symbol: "BTC", available: true, points: [{ timestamp: "2024-01-01T00:00:00Z", close: 0 }], reason: null },
      { symbol: "ETH", available: true, points: [{ timestamp: "2024-01-01T00:00:00Z", close: 0 }], reason: null },
      { symbol: "NEWCOIN", available: false, points: [], reason: "insufficient-history" },
    ],
  };
}

describe("RelativePerformanceChart", () => {
  it("renders one line per available coin (line count = watchlist size minus unavailable), with a visible note for the rest (AC-14/AC-15)", async () => {
    const fetchData = vi.fn(async (tf: RelativePerformanceTimeframe) => makeResponse(tf));
    render(<RelativePerformanceChart fetchData={fetchData} />);

    await waitFor(() => expect(screen.getByTestId("rp-unavailable-note")).toBeInTheDocument());
    expect(screen.getByTestId("rp-unavailable-note").textContent).toContain(
      "NEWCOIN: Not enough history for this window"
    );
  });

  // RFC-006 (reason-value-rendering slice): written but NOT executed in the
  // session that added it — same environment limitation as the file-level
  // SANDBOX NOTE above.
  it("distinguishes a source-unavailable reason from an insufficient-history reason, per coin", async () => {
    const fetchData = vi.fn(async (tf: RelativePerformanceTimeframe) => ({
      timeframe: tf,
      series: [
        { symbol: "BTC", available: true, points: [{ timestamp: "2024-01-01T00:00:00Z", close: 0 }], reason: null },
        { symbol: "NEWCOIN", available: false, points: [], reason: "insufficient-history" as const },
        { symbol: "DEADFEED", available: false, points: [], reason: "source-unavailable" as const },
      ],
    }));
    render(<RelativePerformanceChart fetchData={fetchData} />);

    await waitFor(() => expect(screen.getByTestId("rp-unavailable-DEADFEED")).toBeInTheDocument());

    const newcoinNote = screen.getByTestId("rp-unavailable-NEWCOIN");
    const deadfeedNote = screen.getByTestId("rp-unavailable-DEADFEED");
    expect(newcoinNote.textContent).toContain("Not enough history for this window");
    expect(deadfeedNote.textContent).toContain("Data source unavailable");
    expect(deadfeedNote.getAttribute("data-reason")).toBe("source-unavailable");
    expect(newcoinNote.textContent).not.toBe(deadfeedNote.textContent);
  });

  it("switching the timeframe control re-fetches with the new param and re-normalizes (AC-14/AC-15)", async () => {
    const fetchData = vi.fn(async (tf: RelativePerformanceTimeframe) => makeResponse(tf));
    render(<RelativePerformanceChart fetchData={fetchData} />);

    await waitFor(() => expect(fetchData).toHaveBeenCalledWith("30d"));
    fireEvent.click(screen.getByTestId("rp-timeframe-button-7d"));
    await waitFor(() => expect(fetchData).toHaveBeenCalledWith("7d"));
  });

  it("draws one line per available coin on ONE shared plot, never one per coin (AC-14/AC-15, item 29d)", async () => {
    // This was a spy on createChart. The plot is a Svelte island now and jsdom
    // never mounts it, so the guarantee is asserted on what feeds it: every
    // coin is a line in a single list handed to a single plot, and there is
    // exactly one host element.
    const lines = buildRelativeLines(makeResponse("30d").series);
    expect(lines.map((l) => l.key)).toEqual(["BTC", "ETH"]); // NEWCOIN is unavailable: no line, not a zero
    expect(lines.map((l) => l.color)).toEqual([CATEGORICAL[0], CATEGORICAL[1]]);

    const fetchData = vi.fn(async (tf: RelativePerformanceTimeframe) => makeResponse(tf));
    render(<RelativePerformanceChart fetchData={fetchData} />);
    await waitFor(() => expect(screen.getByTestId("rp-unavailable-note")).toBeInTheDocument());
    expect(screen.getAllByTestId("rp-chart-container")).toHaveLength(1);
  });

  it("names every line in a legend, and gives an unavailable coin no entry", async () => {
    // Without this a multi-coin chart cannot be read: the old chart carried each
    // symbol on its price-axis title, and the island has no such label.
    const fetchData = vi.fn(async (tf: RelativePerformanceTimeframe) => makeResponse(tf));
    render(<RelativePerformanceChart fetchData={fetchData} />);

    await waitFor(() => expect(screen.getByTestId("rp-legend")).toBeInTheDocument());
    expect(screen.getByTestId("rp-legend-BTC")).toHaveTextContent("BTC");
    expect(screen.getByTestId("rp-legend-ETH")).toHaveTextContent("ETH");
    // NEWCOIN has no line, so it must not appear to have one; it is reported in the note instead.
    expect(screen.queryByTestId("rp-legend-NEWCOIN")).toBeNull();
    expect(screen.getByTestId("rp-unavailable-NEWCOIN")).toBeInTheDocument();
  });

  it("shows no legend when there is nothing to name", async () => {
    const fetchData = vi.fn(async (tf: RelativePerformanceTimeframe) => ({
      timeframe: tf,
      series: [{ symbol: "NEWCOIN", available: false, points: [], reason: "insufficient-history" as const }],
    }));
    render(<RelativePerformanceChart fetchData={fetchData} />);
    await waitFor(() => expect(screen.getByTestId("rp-unavailable-NEWCOIN")).toBeInTheDocument());
    expect(screen.queryByTestId("rp-legend")).toBeNull();
  });

  it("labels the axis as a % change, with a sign, and never '+0%'", () => {
    expect(formatPercentChange(2)).toBe("+2%");
    expect(formatPercentChange(-3.5)).toBe("-3.5%");
    expect(formatPercentChange(0)).toBe("0%");
    expect(formatPercentChange(0.04)).toBe("0%");
    expect(formatPercentChange(-0.04)).toBe("0%");
  });

  it("cycles the palette past eight coins without inventing a colour", () => {
    const many = Array.from({ length: 10 }, (_, i) => ({
      symbol: `C${i}`,
      available: true,
      points: [{ timestamp: "2024-01-01T00:00:00Z", close: i }],
      reason: null,
    }));
    const colors = buildRelativeLines(many).map((l) => l.color);
    expect(colors[8]).toBe(colors[0]);
    expect(new Set(colors).size).toBe(8);
  });

  // dead-data-notice-unification: closes the pre-existing zero-coverage gap on
  // rp-error — same pattern as the LegTimelineBanner/NarrativeStrip error cases,
  // adapted to this component's own convention: the toolbar and chart container
  // stay mounted on error (nothing here is a whole-section replace).
  it("renders rp-error when the fetch rejects, while the toolbar and chart container stay mounted", async () => {
    const fetchData = vi.fn(async (): Promise<RelativePerformanceResponse> => {
      throw new Error("API request timed out after 10000ms: /api/screener/relative-performance");
    });
    render(<RelativePerformanceChart fetchData={fetchData} />);

    await waitFor(() => expect(screen.getByTestId("rp-error")).toBeInTheDocument());
    expect(screen.getByTestId("rp-error").textContent).toContain(
      "API request timed out after 10000ms"
    );

    // No data to derive an unavailable-coins note from; nothing else fabricated.
    expect(screen.queryByTestId("rp-unavailable-note")).not.toBeInTheDocument();

    // Siblings survive — this component never whole-section-replaces on error.
    expect(screen.getByTestId("rp-timeframe-toggle")).toBeInTheDocument();
    expect(screen.getByTestId("rp-chart-container")).toBeInTheDocument();
  });
});
