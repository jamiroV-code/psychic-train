// SANDBOX NOTE: see ScreenerBoard.test.tsx — same environment limitation.
import { describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { RelativePerformanceChart } from "@/components/screener/RelativePerformanceChart";
import type { RelativePerformanceResponse, RelativePerformanceTimeframe } from "@/lib/types/screener";

const createChartSpy = vi.fn();

vi.mock("lightweight-charts", () => {
  const series = { setData: vi.fn() };
  const chart = { addSeries: vi.fn(() => series), removeSeries: vi.fn(), applyOptions: vi.fn(), remove: vi.fn() };
  return {
    createChart: (...args: unknown[]) => {
      createChartSpy(...args);
      return chart;
    },
    LineSeries: "LineSeries",
  };
});

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

  it("calls createChart exactly once per render regardless of watchlist size (the ONE-shared-instance mechanical guard, item 29d)", async () => {
    createChartSpy.mockClear();
    const fetchData = vi.fn(async (tf: RelativePerformanceTimeframe) => makeResponse(tf));
    render(<RelativePerformanceChart fetchData={fetchData} />);

    await waitFor(() => expect(screen.getByTestId("rp-chart-container")).toBeInTheDocument());
    expect(createChartSpy).toHaveBeenCalledTimes(1); // not once-per-coin, unlike MiniChart
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
