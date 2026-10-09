import { describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { SpaghettiChart } from "@/components/screener/SpaghettiChart";
import type { SpaghettiLine, SpaghettiResponse, Timeframe } from "@/lib/types/screener";

function line(symbol: string, available = true, reason: SpaghettiLine["reason"] = null): SpaghettiLine {
  return {
    symbol,
    available,
    reason: available ? null : reason ?? "insufficient-history",
    points: available
      ? [
          { timestamp: "2026-03-23T00:00:00Z", close: 0 },
          { timestamp: "2026-09-28T00:00:00Z", close: 12.5 },
        ]
      : [],
    window_start: available ? "2026-03-23T00:00:00Z" : null,
    window_end: available ? "2026-09-28T00:00:00Z" : null,
    bars: available ? 28 : 0,
    last_bar_ts: available ? "2026-09-28T00:00:00Z" : null,
    stale: false,
  };
}

function makeResponse(timeframe: Timeframe, series = [line("SOL"), line("ETH")]): SpaghettiResponse {
  return {
    timeframe,
    window_cap_bars: timeframe === "1w" ? 28 : 200,
    server_time: "2026-10-03T14:10:00Z",
    series,
    references: [line("BTC"), line("HYPE")],
  };
}

describe("SpaghettiChart", () => {
  it("legend names every available coin and both references, one plot", async () => {
    const fetchSpaghetti = vi.fn(async (tf: Timeframe) => makeResponse(tf));
    render(<SpaghettiChart timeframe="1w" fetchSpaghetti={fetchSpaghetti} />);

    await waitFor(() => expect(screen.getByTestId("spaghetti-legend")).toBeInTheDocument());
    for (const sym of ["BTC", "HYPE", "SOL", "ETH"]) {
      expect(screen.getByTestId(`spaghetti-toggle-${sym}`)).toHaveTextContent(sym);
    }
    expect(screen.getByTestId("spaghetti-toggle-BTC")).toHaveAttribute("data-reference", "true");
    expect(screen.getByTestId("spaghetti-toggle-SOL")).not.toHaveAttribute("data-reference");
    expect(screen.getAllByTestId("spaghetti-chart-container")).toHaveLength(1);
    expect(fetchSpaghetti).toHaveBeenCalledWith("1w");
  });

  it("toggle hides and shows a line, the legend entry stays", async () => {
    const fetchSpaghetti = vi.fn(async (tf: Timeframe) => makeResponse(tf));
    render(<SpaghettiChart timeframe="1d" fetchSpaghetti={fetchSpaghetti} />);

    const sol = await screen.findByTestId("spaghetti-toggle-SOL");
    expect(sol).toHaveAttribute("aria-pressed", "true");
    fireEvent.click(sol);
    expect(screen.getByTestId("spaghetti-toggle-SOL")).toHaveAttribute("aria-pressed", "false");
    fireEvent.click(screen.getByTestId("spaghetti-toggle-SOL"));
    expect(screen.getByTestId("spaghetti-toggle-SOL")).toHaveAttribute("aria-pressed", "true");
  });

  it("span text says the window in UTC", async () => {
    const fetchSpaghetti = vi.fn(async (tf: Timeframe) => makeResponse(tf));
    render(<SpaghettiChart timeframe="1w" fetchSpaghetti={fetchSpaghetti} />);
    expect(await screen.findByTestId("spaghetti-span")).toHaveTextContent(
      "Last 28 weeks, 2026-03-23 to 2026-10-04 UTC",
    );
  });

  it("unavailable note per coin with its reason, and no toggle for it", async () => {
    const fetchSpaghetti = vi.fn(async (tf: Timeframe) =>
      makeResponse(tf, [line("SOL"), line("NEWCOIN", false), line("DEADFEED", false, "source-unavailable")]),
    );
    render(<SpaghettiChart timeframe="1d" fetchSpaghetti={fetchSpaghetti} />);

    expect(await screen.findByTestId("spaghetti-note-NEWCOIN")).toHaveTextContent(
      "NEWCOIN: Not enough history for this window",
    );
    expect(screen.getByTestId("spaghetti-note-DEADFEED")).toHaveTextContent("Data source unavailable");
    expect(screen.queryByTestId("spaghetti-toggle-NEWCOIN")).toBeNull();
  });

  it("error state: spaghetti-error, while the chart container stays mounted", async () => {
    const fetchSpaghetti = vi.fn(async (): Promise<SpaghettiResponse> => {
      throw new Error("API request timed out after 10000ms: /api/screener/spaghetti");
    });
    render(<SpaghettiChart timeframe="1d" fetchSpaghetti={fetchSpaghetti} />);

    expect(await screen.findByTestId("spaghetti-error")).toHaveTextContent("API request timed out after 10000ms");
    expect(screen.queryByTestId("spaghetti-legend")).toBeNull();
    expect(screen.getByTestId("spaghetti-chart-container")).toBeInTheDocument();
  });

  it("no comparative wording: nothing ranks or calls a coin ahead", async () => {
    const fetchSpaghetti = vi.fn(async (tf: Timeframe) => makeResponse(tf));
    const { container } = render(<SpaghettiChart timeframe="1d" fetchSpaghetti={fetchSpaghetti} />);
    await screen.findByTestId("spaghetti-legend");
    const text = `${container.textContent ?? ""} ${container.innerHTML}`.toLowerCase();
    for (const word of ["outperform", "underperform", "leader", "laggard", "rank", "best", "worst", "winner", "loser", "beats"]) {
      expect(text).not.toContain(word);
    }
  });
});
