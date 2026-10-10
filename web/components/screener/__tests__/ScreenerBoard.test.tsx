// SANDBOX NOTE: `vitest`/`@testing-library/react`/`lightweight-charts` could
// not be installed in this sandbox (no package-registry network access —
// see EXECUTE report Deviations). This file is written to run under
// `pnpm --filter web test -- ScreenerBoard` once `pnpm install` succeeds
// with real network access; it was not executable in this session.
import { describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { ScreenerBoard } from "@/components/screener/ScreenerBoard";
import type { GainChip, ScreenerBoardResponse, SpaghettiResponse, Timeframe } from "@/lib/types/screener";

// T32 / S1 freshness fields (ChartSeries); nulls = no freshness information.
const NO_FRESHNESS = { last_bar_ts: null, fetched_at: null, is_partial: null, server_time: null, stale: false, rsi: [] };

// T34 / S2: a current-candle chip; `pct: null` needs a reason.
function chip(pct: number | null, reason: GainChip["reason"] = null): GainChip {
  return { pct, open_ts: pct === null ? null : "2026-10-03T00:00:00Z", is_partial: true, stale: false, reason };
}

function makeCoin(symbol: string, overrides: Partial<ScreenerBoardResponse["coins"][number]> = {}) {
  return {
    symbol,
    chart: {
      price: [{ timestamp: "2024-01-01T00:00:00Z", close: 100 }],
      sma: [{ timestamp: "2024-01-01T00:00:00Z", close: 95 }],
      available: true,
      reason: null,
      ...NO_FRESHNESS,
    },
    percent_change_by_timeframe: {
      "15m": 1.2,
      "1h": 2.3,
      "4h": 3.4,
      "1d": 4.5,
      "1w": 5.6,
    },
    gain_by_timeframe: {
      "15m": chip(1.2),
      "1h": chip(2.3),
      "4h": chip(3.4),
      "1d": chip(4.5),
      "1w": chip(5.6),
    },
    rsi: { value: 61.3, length: 14, as_of: null, reason: null },
    ...overrides,
  };
}

function makeBoard(timeframe: Timeframe, coins: ReturnType<typeof makeCoin>[]): ScreenerBoardResponse {
  return {
    timeframe,
    coins,
    server_time: null,
    clock_skew_seconds: null,
    clock_skew_warning: false,
  };
}

// T37 / S6: the board mounts SpaghettiChart; every render passes this stub so
// no real fetch runs.
const fetchSpaghetti = vi.fn(
  async (tf: Timeframe): Promise<SpaghettiResponse> => ({
    timeframe: tf,
    window_cap_bars: tf === "1w" ? 28 : 200,
    server_time: null,
    series: [],
    references: [],
  }),
);

describe("ScreenerBoard", () => {
  it("renders N panels for N mock coins, each panel's values matching its own fixture (AC-5)", async () => {
    const coins = [
      makeCoin("BTC"),
      makeCoin("ETH", {
        gain_by_timeframe: { "15m": chip(-1), "1h": chip(-2), "4h": chip(-3), "1d": chip(-4), "1w": chip(-5) },
      }),
    ];
    const fetchBoard = vi.fn(async (tf: Timeframe) => makeBoard(tf, coins));

    render(<ScreenerBoard fetchBoard={fetchBoard} fetchSpaghetti={fetchSpaghetti} />);

    await waitFor(() => expect(screen.getByTestId("coin-panel-BTC")).toBeInTheDocument());
    expect(screen.getByTestId("coin-panel-ETH")).toBeInTheDocument();

    const btcChip = screen.getByTestId("coin-panel-BTC").querySelector('[data-testid="gain-chip-1d"]');
    const ethChip = screen.getByTestId("coin-panel-ETH").querySelector('[data-testid="gain-chip-1d"]');
    expect(btcChip?.textContent).toContain("+4.5%");
    expect(ethChip?.textContent).toContain("-4.0%");
  });

  it("switches every panel's chart together when the global timeframe toggle changes, with no verdict element on the page (AC-16, T36 / S4)", async () => {
    const coins = [makeCoin("BTC"), makeCoin("ETH")];
    const fetchBoard = vi.fn(async (tf: Timeframe) => makeBoard(tf, coins));

    const { container } = render(<ScreenerBoard fetchBoard={fetchBoard} fetchSpaghetti={fetchSpaghetti} />);
    await waitFor(() => expect(screen.getByTestId("coin-panel-BTC")).toBeInTheDocument());

    fireEvent.click(screen.getByTestId("timeframe-button-1h"));

    await waitFor(() => expect(fetchBoard).toHaveBeenCalledWith("1h"));
    expect(screen.getByTestId("timeframe-button-1h").getAttribute("aria-pressed")).toBe("true");
    expect(screen.getAllByTestId("gain-readout-row")).toHaveLength(2);
    const text = container.textContent ?? "";
    for (const word of ["Momentum", "Trend", "Benchmark", "Confidence", "Narrative"]) {
      expect(text).not.toContain(word);
    }
  });

  it("renders 'N/A' (not '0%') for an unavailable gain-readout slot (AC-20)", async () => {
    const coins = [
      makeCoin("THIN", {
        percent_change_by_timeframe: { "15m": null, "1h": 1, "4h": 2, "1d": 3, "1w": 4 },
        gain_by_timeframe: {
          "15m": chip(null, "insufficient-history"),
          "1h": chip(1),
          "4h": chip(2),
          "1d": chip(3),
          "1w": chip(4),
        },
      }),
    ];
    const fetchBoard = vi.fn(async (tf: Timeframe) => makeBoard(tf, coins));

    render(<ScreenerBoard fetchBoard={fetchBoard} fetchSpaghetti={fetchSpaghetti} />);
    await waitFor(() => expect(screen.getByTestId("gain-chip-15m")).toBeInTheDocument());

    expect(screen.getByTestId("gain-chip-15m").textContent).toContain("N/A");
    expect(screen.getByTestId("gain-chip-15m").textContent).not.toContain("0%");
    expect(screen.getByTestId("gain-chip-1d").textContent).toContain("+3.0%");
    expect(screen.getByTestId("gain-chip-15m").getAttribute("data-reason")).toBe("insufficient-history");
  });

  it("reads each gain chip from gain_by_timeframe (the current candle), not the legacy map (T34 / S2)", async () => {
    const coins = [
      makeCoin("BTC", {
        // The legacy field disagrees on purpose: the chip must follow the chip.
        percent_change_by_timeframe: { "15m": 9, "1h": 9, "4h": 9, "1d": 9, "1w": 9 },
        gain_by_timeframe: {
          "15m": chip(0),
          "1h": chip(-0.25),
          "4h": chip(null, "source-unavailable"),
          "1d": chip(-1.234),
          "1w": chip(6),
        },
      }),
    ];
    const fetchBoard = vi.fn(async (tf: Timeframe) => makeBoard(tf, coins));

    render(<ScreenerBoard fetchBoard={fetchBoard} fetchSpaghetti={fetchSpaghetti} />);
    await waitFor(() => expect(screen.getByTestId("gain-chip-1d")).toBeInTheDocument());

    expect(screen.getByTestId("gain-chip-1d").textContent).toContain("-1.2%");
    expect(screen.getByTestId("gain-chip-1w").textContent).toContain("+6.0%");
    expect(screen.getByTestId("gain-chip-15m").textContent).toContain("0.0%"); // a real flat candle
    expect(screen.getByTestId("gain-chip-1h").textContent).toContain("-0.3%");
    expect(screen.getByTestId("gain-chip-4h").textContent).toContain("N/A");
    expect(screen.getByTestId("gain-chip-4h").getAttribute("title")).toBe("Data source unavailable");
  });

  it("captions the coin chart's last bar in Brussels time aged against server_time, with a plain stale marker (T34 / S2)", async () => {
    const freshness = {
      last_bar_ts: "2026-10-03T14:15:00Z",
      fetched_at: "2026-10-03T14:21:00Z",
      is_partial: true,
      server_time: "2026-10-03T14:22:00Z",
    };
    const price = [{ timestamp: "2026-10-03T14:15:00Z", close: 100 }];
    const coins = [
      makeCoin("BTC", { chart: { price, sma: [], available: true, reason: null, ...freshness, stale: false, rsi: [] } }),
      makeCoin("OLD", { chart: { price, sma: [], available: true, reason: null, ...freshness, stale: true, rsi: [] } }),
    ];
    const fetchBoard = vi.fn(async (tf: Timeframe) => makeBoard(tf, coins));

    render(<ScreenerBoard fetchBoard={fetchBoard} fetchSpaghetti={fetchSpaghetti} />);
    await waitFor(() => expect(screen.getByTestId("coin-panel-BTC")).toBeInTheDocument());

    const btc = screen.getByTestId("coin-panel-BTC");
    expect(btc.querySelector('[data-testid="chart-freshness-caption"]')?.textContent).toBe(
      "Last bar 2026-10-03 16:15 CEST, opened 7 min ago (forming)",
    );
    expect(btc.querySelector('[data-testid="stale-marker"]')).toBeNull();
    const old = screen.getByTestId("coin-panel-OLD");
    expect(old.querySelector('[data-testid="stale-marker"]')?.textContent).toBe("stale");
  });

  it("titles the 1d chip with its candle open in Brussels time and keeps the N/A chip reason", async () => {
    const coins = [
      makeCoin("BTC", {
        gain_by_timeframe: {
          "15m": chip(0),
          "1h": chip(-0.25),
          "4h": chip(null, "source-unavailable"),
          "1d": chip(-1.234),
          "1w": chip(6),
        },
      }),
    ];
    const fetchBoard = vi.fn(async (tf: Timeframe) => makeBoard(tf, coins));

    render(<ScreenerBoard fetchBoard={fetchBoard} fetchSpaghetti={fetchSpaghetti} />);
    await waitFor(() => expect(screen.getByTestId("gain-chip-1d")).toBeInTheDocument());

    // 2026-10-03T00:00:00Z is 02:00 in Brussels summer time.
    expect(screen.getByTestId("gain-chip-1d").getAttribute("title")).toBe("1d candle from 2026-10-03 02:00 CEST (forming)");
    expect(screen.getByTestId("gain-chip-4h").getAttribute("title")).toBe("Data source unavailable");
  });

  it("shows a coin's chart as unavailable, not a wrong/truncated chart, when thin history (AC-19)", async () => {
    const coins = [makeCoin("THIN", { chart: { price: [], sma: [], available: false, reason: null, ...NO_FRESHNESS } })];
    const fetchBoard = vi.fn(async (tf: Timeframe) => makeBoard(tf, coins));

    render(<ScreenerBoard fetchBoard={fetchBoard} fetchSpaghetti={fetchSpaghetti} />);
    await waitFor(() => expect(screen.getByTestId("chart-unavailable")).toBeInTheDocument());
    // reason: null falls back to the pre-RFC-005 default copy, unchanged.
    expect(screen.getByTestId("chart-unavailable").textContent).toContain("Not enough history at this timeframe");
  });

  // RFC-006 (reason-value-rendering slice): written but NOT executed in the
  // session that added it — no shell reachable on the machine holding this
  // repo, same limitation as the file-level SANDBOX NOTE above.
  it("distinguishes a bad-symbol chart-unavailable reason from the generic history message", async () => {
    const coins = [
      makeCoin("BADSYM", { chart: { price: [], sma: [], available: false, reason: "bad-symbol" as const, ...NO_FRESHNESS } }),
    ];
    const fetchBoard = vi.fn(async (tf: Timeframe) => makeBoard(tf, coins));

    render(<ScreenerBoard fetchBoard={fetchBoard} fetchSpaghetti={fetchSpaghetti} />);
    await waitFor(() => expect(screen.getByTestId("chart-unavailable")).toBeInTheDocument());

    const el = screen.getByTestId("chart-unavailable");
    expect(el.textContent).toContain("Symbol configuration issue");
    expect(el.getAttribute("data-reason")).toBe("bad-symbol");
  });

  it("opens the drill-down view on demand from a coin panel, not as its own grid tile (AC-7)", async () => {
    const coins = [makeCoin("BTC")];
    const fetchBoard = vi.fn(async (tf: Timeframe) => makeBoard(tf, coins));
    const fetchChart = vi.fn(async () => ({
      symbol: "BTC",
      timeframe: "4h" as Timeframe,
      chart: { price: [], sma: [], available: false, reason: null, ...NO_FRESHNESS },
    }));

    render(<ScreenerBoard fetchBoard={fetchBoard} fetchSpaghetti={fetchSpaghetti} fetchChart={fetchChart} />);
    await waitFor(() => expect(screen.getByTestId("open-drilldown-BTC")).toBeInTheDocument());

    expect(screen.queryByTestId("drilldown-view")).not.toBeInTheDocument();
    fireEvent.click(screen.getByTestId("open-drilldown-BTC"));
    await waitFor(() => expect(screen.getByTestId("drilldown-view")).toBeInTheDocument());
  });

  it("hosts the spaghetti chart, which follows the board timeframe (T37 / S6)", async () => {
    const coins = [makeCoin("BTC")];
    const fetchBoard = vi.fn(async (tf: Timeframe) => makeBoard(tf, coins));
    const spaghetti = vi.fn(fetchSpaghetti);

    render(<ScreenerBoard fetchBoard={fetchBoard} fetchSpaghetti={spaghetti} />);
    await waitFor(() => expect(spaghetti).toHaveBeenCalledWith("1d"));
    expect(screen.getByTestId("spaghetti-chart")).toBeInTheDocument();

    fireEvent.click(screen.getByTestId("timeframe-button-1w"));
    await waitFor(() => expect(spaghetti).toHaveBeenLastCalledWith("1w"));
    expect(fetchBoard).toHaveBeenLastCalledWith("1w");
  });
});
