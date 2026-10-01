// SANDBOX NOTE: see ScreenerBoard.test.tsx — same environment limitation
// (vitest/@testing-library/react/lightweight-charts not installable here).
import { describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { DrillDownView } from "@/components/screener/DrillDownView";
import type { ScalpView, Timeframe } from "@/lib/types/screener";

function makeScalpView(timeframe: Timeframe): ScalpView {
  return {
    symbol: "BTC",
    timeframe,
    chart: { price: [{ timestamp: "2024-01-01T00:00:00Z", close: 100 }], sma: [], available: true, reason: null },
    scalp_momentum: { state: "PASS", value: 62.3, timeframe: "4h" },
  };
}

describe("DrillDownView", () => {
  it("re-fetches and re-renders at a newly selected timeframe, independent of any board state (AC-18)", async () => {
    const fetchScalp = vi.fn(async (_symbol: string, tf: Timeframe) => makeScalpView(tf));
    render(<DrillDownView symbol="BTC" fetchScalp={fetchScalp} />);

    await waitFor(() => expect(fetchScalp).toHaveBeenCalledWith("BTC", "4h"));

    fireEvent.click(screen.getByTestId("drilldown-timeframe-button-1d"));
    await waitFor(() => expect(fetchScalp).toHaveBeenCalledWith("BTC", "1d"));
  });

  it("labels the scalp RSI reading with its own timeframe regardless of the chart's zoom (AC-18)", async () => {
    const fetchScalp = vi.fn(async (_symbol: string, tf: Timeframe) => makeScalpView(tf));
    render(<DrillDownView symbol="BTC" fetchScalp={fetchScalp} />);

    await waitFor(() => expect(screen.getByTestId("scalp-rsi-reading")).toBeInTheDocument());
    fireEvent.click(screen.getByTestId("drilldown-timeframe-button-1w"));

    await waitFor(() => expect(fetchScalp).toHaveBeenCalledWith("BTC", "1w"));
    // scalp_momentum.timeframe is always "4h" in the fixture -> label never
    // tracks the chart's zoom.
    expect(screen.getByTestId("scalp-rsi-reading").textContent).toContain("4h");
  });

  // RFC-006 (reason-value-rendering slice): written but NOT executed in the
  // session that added it — same environment limitation as the file-level
  // SANDBOX NOTE below.
  it("distinguishes a source-unavailable chart reason from the generic history message (drilldown-chart-unavailable)", async () => {
    const fetchScalp = vi.fn(async (_symbol: string, tf: Timeframe) => ({
      symbol: "BTC",
      timeframe: tf,
      chart: { price: [], sma: [], available: false as const, reason: "source-unavailable" as const },
      scalp_momentum: { state: "insufficient" as const, value: null, timeframe: "4h" as Timeframe },
    }));
    render(<DrillDownView symbol="BTC" fetchScalp={fetchScalp} />);

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
    const fetchScalp = vi.fn(async () => {
      throw new Error("API request timed out after 10000ms: /api/screener/BTC/scalp?timeframe=4h");
    });
    const onClose = vi.fn();
    render(<DrillDownView symbol="BTC" onClose={onClose} fetchScalp={fetchScalp} />);

    await waitFor(() => expect(screen.getByTestId("drilldown-error")).toBeInTheDocument());
    expect(screen.getByTestId("drilldown-error").textContent).toContain(
      "API request timed out after 10000ms"
    );

    // Data-dependent body is replaced, not merely hidden alongside.
    expect(screen.queryByTestId("scalp-rsi-reading")).not.toBeInTheDocument();
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
    const fetchScalp = vi.fn(async (_symbol: string, tf: Timeframe) => {
      calls += 1;
      if (calls === 1) throw new Error("API request timed out after 10000ms: /api/screener/BTC/scalp");
      return makeScalpView(tf);
    });
    render(<DrillDownView symbol="BTC" fetchScalp={fetchScalp} />);

    await waitFor(() => expect(screen.getByTestId("drilldown-error")).toBeInTheDocument());

    // Switching timeframe re-issues the call; error is cleared before it.
    fireEvent.click(screen.getByTestId("drilldown-timeframe-button-1d"));
    await waitFor(() => expect(screen.queryByTestId("drilldown-error")).not.toBeInTheDocument());
    await waitFor(() => expect(screen.getByTestId("scalp-rsi-reading")).toBeInTheDocument());
  });
});
