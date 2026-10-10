import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { CoinPanel } from "@/components/screener/CoinPanel";
import type { CoinPanel as CoinPanelData, RsiReading } from "@/lib/types/screener";

function panel(symbol: string, rsi: RsiReading, available = true): CoinPanelData {
  return {
    symbol,
    chart: {
      price: available ? [{ timestamp: "2026-10-03T00:00:00Z", close: 100 }] : [],
      sma: [],
      available,
      reason: available ? null : "insufficient-history",
      last_bar_ts: null,
      fetched_at: null,
      is_partial: null,
      server_time: null,
      stale: false,
      rsi: [],
    },
    percent_change_by_timeframe: {} as CoinPanelData["percent_change_by_timeframe"],
    gain_by_timeframe: {} as CoinPanelData["gain_by_timeframe"],
    rsi,
  };
}

const VALUE: RsiReading = { value: 61.34, length: 14, as_of: "2026-10-03T00:00:00Z", reason: null };

describe("CoinPanel RSI row and actions", () => {
  it("shows RSI 14 with its value to one decimal, between the chart and the chips", () => {
    render(<CoinPanel panel={panel("BTC", VALUE)} timeframe="1d" />);
    const row = screen.getByTestId("rsi-readout-BTC");
    expect(row).toHaveTextContent("RSI 14");
    expect(row).toHaveTextContent("61.3");
    const chips = screen.getByTestId("gain-readout-row");
    expect(row.compareDocumentPosition(chips) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it("an N/A reading carries its reason as the title", () => {
    render(<CoinPanel panel={panel("THIN", { value: null, length: 14, as_of: null, reason: "insufficient-history" })} />);
    const value = screen.getByTestId("rsi-value-THIN");
    expect(value).toHaveTextContent("N/A");
    expect(value).toHaveAttribute("title", "Not enough history for RSI 14");
  });

  it("the row is there for an unavailable chart too", () => {
    render(<CoinPanel panel={panel("THIN", VALUE, false)} />);
    expect(screen.getByTestId("chart-unavailable")).toBeInTheDocument();
    expect(screen.getByTestId("rsi-readout-THIN")).toHaveTextContent("61.3");
  });

  it("the label names the timeframe", () => {
    render(<CoinPanel panel={panel("BTC", VALUE)} timeframe="4h" />);
    expect(screen.getByTestId("rsi-readout-BTC")).toHaveTextContent("RSI 14 (4h)");
  });

  it("renders the actions slot in the header", () => {
    render(<CoinPanel panel={panel("BTC", VALUE)} actions={<button type="button">Do it</button>} />);
    expect(screen.getByRole("button", { name: "Do it" })).toBeInTheDocument();
  });
});
