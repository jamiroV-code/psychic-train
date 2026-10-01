// SANDBOX NOTE: `vitest`/`@testing-library/react`/`lightweight-charts` could
// not be installed in this sandbox (no package-registry network access —
// see EXECUTE report Deviations). This file is written to run under
// `pnpm --filter web test -- ScreenerBoard` once `pnpm install` succeeds
// with real network access; it was not executable in this session.
import { describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { ScreenerBoard } from "@/components/screener/ScreenerBoard";
import type { ScreenerBoardResponse, Timeframe } from "@/lib/types/screener";

function makeCoin(symbol: string, overrides: Partial<ScreenerBoardResponse["coins"][number]> = {}) {
  return {
    symbol,
    momentum: { state: "PASS" as const, daily_value: 60, weekly_value: 65 },
    trend: { direction: "up" as const, sma_value: 100 },
    confidence: "insufficient-data" as const,
    leg_context: "confirmed" as const,
    narrative_state: "in-focus" as const,
    chart: {
      price: [{ timestamp: "2024-01-01T00:00:00Z", close: 100 }],
      sma: [{ timestamp: "2024-01-01T00:00:00Z", close: 95 }],
      available: true,
      reason: null,
    },
    percent_change_by_timeframe: {
      "15m": 1.2,
      "1h": 2.3,
      "4h": 3.4,
      "1d": 4.5,
      "1w": 5.6,
    },
    ...overrides,
  };
}

function makeBoard(timeframe: Timeframe, coins: ReturnType<typeof makeCoin>[]): ScreenerBoardResponse {
  return {
    timeframe,
    active_benchmark: { active: "BTC", reason: "test" },
    coins,
  };
}

describe("ScreenerBoard", () => {
  it("renders N panels for N mock coins, each panel's values matching its own fixture (AC-5)", async () => {
    const coins = [makeCoin("BTC"), makeCoin("ETH", { momentum: { state: "FAIL", daily_value: 40, weekly_value: 45 } })];
    const fetchBoard = vi.fn(async (tf: Timeframe) => makeBoard(tf, coins));

    render(<ScreenerBoard fetchBoard={fetchBoard} />);

    await waitFor(() => expect(screen.getByTestId("coin-panel-BTC")).toBeInTheDocument());
    expect(screen.getByTestId("coin-panel-ETH")).toBeInTheDocument();

    const btcMomentum = screen.getByTestId("coin-panel-BTC").querySelector('[data-testid="momentum-state"]');
    const ethMomentum = screen.getByTestId("coin-panel-ETH").querySelector('[data-testid="momentum-state"]');
    expect(btcMomentum?.getAttribute("data-state")).toBe("PASS");
    expect(ethMomentum?.getAttribute("data-state")).toBe("FAIL");
  });

  it("switches every panel's chart together when the global timeframe toggle changes, while momentum badges stay unchanged (AC-16)", async () => {
    const coins = [makeCoin("BTC")];
    const fetchBoard = vi.fn(async (tf: Timeframe) => makeBoard(tf, coins));

    render(<ScreenerBoard fetchBoard={fetchBoard} />);
    await waitFor(() => expect(screen.getByTestId("coin-panel-BTC")).toBeInTheDocument());

    fireEvent.click(screen.getByTestId("timeframe-button-1h"));

    await waitFor(() => expect(fetchBoard).toHaveBeenCalledWith("1h"));
    const momentumEl = screen.getByTestId("coin-panel-BTC").querySelector('[data-testid="momentum-state"]');
    expect(momentumEl?.getAttribute("data-state")).toBe("PASS"); // unchanged by the display toggle
  });

  it("renders 'N/A' (not '0%') for an unavailable gain-readout slot (AC-20)", async () => {
    const coins = [
      makeCoin("THIN", {
        percent_change_by_timeframe: { "15m": null, "1h": 1, "4h": 2, "1d": 3, "1w": 4 },
      }),
    ];
    const fetchBoard = vi.fn(async (tf: Timeframe) => makeBoard(tf, coins));

    render(<ScreenerBoard fetchBoard={fetchBoard} />);
    await waitFor(() => expect(screen.getByTestId("gain-chip-15m")).toBeInTheDocument());

    expect(screen.getByTestId("gain-chip-15m").textContent).toContain("N/A");
    expect(screen.getByTestId("gain-chip-15m").textContent).not.toContain("0%");
    expect(screen.getByTestId("gain-chip-1d").textContent).toContain("+3.0%");
  });

  it("shows a coin's chart as unavailable, not a wrong/truncated chart, when thin history (AC-19)", async () => {
    const coins = [makeCoin("THIN", { chart: { price: [], sma: [], available: false, reason: null } })];
    const fetchBoard = vi.fn(async (tf: Timeframe) => makeBoard(tf, coins));

    render(<ScreenerBoard fetchBoard={fetchBoard} />);
    await waitFor(() => expect(screen.getByTestId("chart-unavailable")).toBeInTheDocument());
    // reason: null falls back to the pre-RFC-005 default copy, unchanged.
    expect(screen.getByTestId("chart-unavailable").textContent).toContain("Not enough history at this timeframe");
  });

  // RFC-006 (reason-value-rendering slice): written but NOT executed in the
  // session that added it — no shell reachable on the machine holding this
  // repo, same limitation as the file-level SANDBOX NOTE above.
  it("distinguishes a bad-symbol chart-unavailable reason from the generic history message", async () => {
    const coins = [
      makeCoin("BADSYM", { chart: { price: [], sma: [], available: false, reason: "bad-symbol" } }),
    ];
    const fetchBoard = vi.fn(async (tf: Timeframe) => makeBoard(tf, coins));

    render(<ScreenerBoard fetchBoard={fetchBoard} />);
    await waitFor(() => expect(screen.getByTestId("chart-unavailable")).toBeInTheDocument());

    const el = screen.getByTestId("chart-unavailable");
    expect(el.textContent).toContain("Symbol configuration issue");
    expect(el.getAttribute("data-reason")).toBe("bad-symbol");
  });

  it("opens the drill-down view on demand from a coin panel, not as its own grid tile (AC-7)", async () => {
    const coins = [makeCoin("BTC")];
    const fetchBoard = vi.fn(async (tf: Timeframe) => makeBoard(tf, coins));
    const fetchScalp = vi.fn(async () => ({
      symbol: "BTC",
      timeframe: "4h" as Timeframe,
      chart: { price: [], sma: [], available: false, reason: null },
      scalp_momentum: { state: "insufficient" as const, value: null, timeframe: "4h" as Timeframe },
    }));

    render(<ScreenerBoard fetchBoard={fetchBoard} fetchScalp={fetchScalp} />);
    await waitFor(() => expect(screen.getByTestId("open-drilldown-BTC")).toBeInTheDocument());

    expect(screen.queryByTestId("drilldown-view")).not.toBeInTheDocument();
    fireEvent.click(screen.getByTestId("open-drilldown-BTC"));
    await waitFor(() => expect(screen.getByTestId("drilldown-view")).toBeInTheDocument());
  });
});
