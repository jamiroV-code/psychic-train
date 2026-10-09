// SANDBOX NOTE: see ScreenerBoard.test.tsx — same environment limitation
// (vitest/@testing-library/react/lightweight-charts not installable here).
import { describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { DrillDownView } from "@/components/screener/DrillDownView";
import type { ChartView, Timeframe } from "@/lib/types/screener";

// T32 / S1 freshness fields (ChartSeries); nulls = no freshness information.
const NO_FRESHNESS = { last_bar_ts: null, fetched_at: null, is_partial: null, server_time: null, stale: false, rsi: [] };

function makeChartView(timeframe: Timeframe): ChartView {
  return {
    symbol: "BTC",
    timeframe,
    chart: { price: [{ timestamp: "2024-01-01T00:00:00Z", close: 100 }], sma: [], available: true, reason: null, ...NO_FRESHNESS },
  };
}

describe("DrillDownView", () => {
  it("captions the drill-down chart's last bar in UTC with its age and a plain stale marker (T34 / S2)", async () => {
    const fetchChart = vi.fn(async (_symbol: string, tf: Timeframe) => {
      const view = makeChartView(tf);
      view.chart = {
        ...view.chart,
        last_bar_ts: "2026-10-03T14:00:00Z",
        is_partial: false,
        server_time: "2026-10-03T14:22:00Z",
        stale: true,
      };
      return view;
    });
    render(<DrillDownView symbol="BTC" fetchChart={fetchChart} />);

    await waitFor(() => expect(screen.getByTestId("chart-freshness-caption")).toBeInTheDocument());
    expect(screen.getByTestId("chart-freshness-caption").textContent).toBe("Last bar 2026-10-03 14:00 UTC, 22 min ago");
    expect(screen.getByTestId("stale-marker").textContent).toBe("stale");
  });

  it("shows no caption or stale marker when the chart is unavailable (T34 / S2)", async () => {
    const fetchChart = vi.fn(async (_symbol: string, tf: Timeframe) => ({
      ...makeChartView(tf),
      chart: { price: [], sma: [], available: false, reason: null, ...NO_FRESHNESS },
    }));
    render(<DrillDownView symbol="BTC" fetchChart={fetchChart} />);

    await waitFor(() => expect(screen.getByTestId("drilldown-chart-unavailable")).toBeInTheDocument());
    expect(screen.queryByTestId("chart-freshness")).toBeNull();
    expect(screen.queryByTestId("stale-marker")).toBeNull();
  });

  it("re-fetches and re-renders at a newly selected timeframe, independent of any board state (AC-18)", async () => {
    const fetchChart = vi.fn(async (_symbol: string, tf: Timeframe) => makeChartView(tf));
    render(<DrillDownView symbol="BTC" fetchChart={fetchChart} />);

    await waitFor(() => expect(fetchChart).toHaveBeenCalledWith("BTC", "4h"));

    fireEvent.click(screen.getByTestId("drilldown-timeframe-button-1d"));
    await waitFor(() => expect(fetchChart).toHaveBeenCalledWith("BTC", "1d"));
  });

  // RFC-006 (reason-value-rendering slice): written but NOT executed in the
  // session that added it — same environment limitation as the file-level
  // SANDBOX NOTE below.
  it("distinguishes a source-unavailable chart reason from the generic history message (drilldown-chart-unavailable)", async () => {
    const fetchChart = vi.fn(async (_symbol: string, tf: Timeframe) => ({
      symbol: "BTC",
      timeframe: tf,
      chart: { price: [], sma: [], available: false as const, reason: "source-unavailable" as const, ...NO_FRESHNESS },
    }));
    render(<DrillDownView symbol="BTC" fetchChart={fetchChart} />);

    await waitFor(() => expect(screen.getByTestId("drilldown-chart-unavailable")).toBeInTheDocument());
    const el = screen.getByTestId("drilldown-chart-unavailable");
    expect(el.textContent).toContain("Data source unavailable");
    expect(el.getAttribute("data-reason")).toBe("source-unavailable");
  });

  // SANDBOX NOTE (RFC-006 getjson-timeout-catch): the two cases below were
  // written but NOT executed in the session that added them — no shell was
  // reachable on the machine holding this repo, so vitest never ran. Same
  // limitation as the file-level note above; treat as written-to-spec only.
  it("renders drilldown-error and keeps the header/Close/timeframe-toggle rendered when the fetch rejects (AC-2)", async () => {
    const fetchChart = vi.fn(async () => {
      throw new Error("API request timed out after 10000ms: /api/screener/BTC/chart?timeframe=4h");
    });
    const onClose = vi.fn();
    render(<DrillDownView symbol="BTC" onClose={onClose} fetchChart={fetchChart} />);

    await waitFor(() => expect(screen.getByTestId("drilldown-error")).toBeInTheDocument());
    expect(screen.getByTestId("drilldown-error").textContent).toContain(
      "API request timed out after 10000ms"
    );

    // Data-dependent body is replaced, not merely hidden alongside.
    expect(screen.queryByTestId("drilldown-chart-unavailable")).not.toBeInTheDocument();

    // Header + timeframe toggle stay rendered and functional.
    expect(screen.getByTestId("drilldown-timeframe-toggle")).toBeInTheDocument();
    expect(screen.getByTestId("drilldown-timeframe-button-1d")).toBeInTheDocument();

    const close = screen.getByTestId("drilldown-close");
    expect(close).toBeInTheDocument();
    fireEvent.click(close);
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("surfaces an error for a fetch that never resolves only once it rejects, and clears it on the next successful fetch (AC-2)", async () => {
    let calls = 0;
    const fetchChart = vi.fn(async (_symbol: string, tf: Timeframe) => {
      calls += 1;
      if (calls === 1) throw new Error("API request timed out after 10000ms: /api/screener/BTC/chart");
      return makeChartView(tf);
    });
    render(<DrillDownView symbol="BTC" fetchChart={fetchChart} />);

    await waitFor(() => expect(screen.getByTestId("drilldown-error")).toBeInTheDocument());

    // Switching timeframe re-issues the call; error is cleared before it.
    fireEvent.click(screen.getByTestId("drilldown-timeframe-button-1d"));
    await waitFor(() => expect(screen.queryByTestId("drilldown-error")).not.toBeInTheDocument());
    await waitFor(() => expect(fetchChart).toHaveBeenCalledWith("BTC", "1d"));
  });
});
