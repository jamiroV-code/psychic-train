import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ScreenerBoard, type ScreenerBoardProps } from "@/components/screener/ScreenerBoard";
import { VariantProvider } from "@/components/screener/VariantProvider";
import type { ChartRange, SimpleLinesProps } from "@/lib/island-loader";
import { EQUITIES_CAP_MESSAGE, EQUITIES_VARIANT } from "@/lib/screener-variant";
import type { Layout, LayoutUpdate } from "@/lib/types/layout";
import type { ChartView, ScreenerBoardResponse, SpaghettiResponse, Timeframe } from "@/lib/types/screener";

// T47 / S9C: the crypto board's components under the equities variant.
const island = vi.hoisted(() => {
  type Mount = { target: HTMLElement; props: unknown };
  const mounts: Mount[] = [];
  const mountSimpleLines = vi.fn((target: HTMLElement, props: unknown) => {
    const m: Mount = { target, props };
    mounts.push(m);
    return Object.assign(() => undefined, { update: vi.fn((next: unknown) => (m.props = next)) });
  });
  return { mounts, loadIslands: vi.fn(() => Promise.resolve({ mountSimpleLines })) };
});

vi.mock("@/lib/island-loader", () => ({ loadIslands: island.loadIslands }));

const chip = (pct: number, open_ts: string) => ({ pct, open_ts, is_partial: false, stale: false, reason: null });

function ticker(symbol: string) {
  return {
    symbol,
    chart: {
      price: [
        { timestamp: "2026-10-08T00:00:00Z", close: 99 },
        { timestamp: "2026-10-09T00:00:00Z", close: 100 },
      ],
      sma: [],
      available: true as const,
      reason: null,
      last_bar_ts: "2026-10-09T00:00:00Z",
      fetched_at: "2026-10-09T22:00:00Z",
      is_partial: false,
      server_time: "2026-10-10T08:00:00Z",
      stale: false,
      rsi: [],
    },
    percent_change_by_timeframe: { "1d": 1, "1w": 2 },
    gain_by_timeframe: { "1d": chip(1, "2026-10-09T00:00:00Z"), "1w": chip(2, "2026-10-05T00:00:00Z") },
    rsi: { value: 55.5, length: 14, as_of: "2026-10-09T00:00:00Z", reason: null },
  };
}

function board(timeframe: Timeframe, symbols = ["AAPL", "MSFT"]) {
  return {
    timeframe,
    coins: symbols.map(ticker),
    server_time: "2026-10-10T08:00:00Z",
    clock_skew_seconds: null,
    clock_skew_warning: false,
  } as unknown as ScreenerBoardResponse;
}

const spaghetti = async (timeframe: Timeframe): Promise<SpaghettiResponse> => ({
  timeframe,
  window_cap_bars: 200,
  server_time: null,
  series: [],
  references: [],
});

function layout(groups: Layout["groups"] = [{ id: "main", name: "Main", coins: [] }]): Layout {
  return { version: 1, section: "equities", revision: 0, saved_at: null, source: "default", groups, hidden_lines: [] };
}

function view(symbol: string, timeframe: Timeframe): ChartView {
  return { symbol, timeframe, chart: ticker(symbol).chart } as unknown as ChartView;
}

function renderEquities(props: ScreenerBoardProps = {}) {
  return render(
    <VariantProvider variant={EQUITIES_VARIANT}>
      <ScreenerBoard
        fetchBoard={async (tf) => board(tf)}
        fetchSpaghetti={spaghetti}
        fetchLayout={async () => layout()}
        {...props}
      />
    </VariantProvider>,
  );
}

function panelProps(symbol: string): SimpleLinesProps {
  const m = island.mounts.filter((x) => x.target.closest(`[data-testid="coin-panel-${symbol}"]`)).at(-1);
  if (!m) throw new Error(`no chart for ${symbol}`);
  return m.props as SimpleLinesProps;
}

beforeEach(() => {
  island.mounts.length = 0;
});

describe("ScreenerBoard under the equities variant (T47 / S9C)", () => {
  it("the toolbar offers 1d and 1w only and starts on 1d", async () => {
    const fetchBoard = vi.fn(async (tf: Timeframe) => board(tf));
    renderEquities({ fetchBoard });
    const toggle = screen.getByTestId("timeframe-toggle");
    expect(within(toggle).getAllByRole("button").map((b) => b.textContent)).toEqual(["1d", "1w"]);
    expect(screen.getByTestId("timeframe-button-1d")).toHaveAttribute("aria-pressed", "true");
    expect(fetchBoard).toHaveBeenCalledWith("1d");
    fireEvent.click(screen.getByTestId("timeframe-button-1w"));
    await waitFor(() => expect(fetchBoard).toHaveBeenCalledWith("1w"));
  });

  it("each panel shows 1d and 1w gain chips only", async () => {
    renderEquities();
    const panel = await screen.findByTestId("coin-panel-AAPL");
    const chips = within(panel).getAllByTestId(/^gain-chip-/);
    expect(chips.map((c) => c.getAttribute("data-testid"))).toEqual(["gain-chip-1d", "gain-chip-1w"]);
    expect(within(panel).getByTestId("gain-chip-1d")).toHaveTextContent("+1.0%");
  });

  it("loading and empty text name tickers and the equities list", async () => {
    let resolve: (b: ScreenerBoardResponse) => void = () => undefined;
    renderEquities({ fetchBoard: () => new Promise((r) => (resolve = r)) });
    expect(screen.getByTestId("board-loading")).toHaveTextContent("Loading tickers and layout");
    await act(async () => resolve(board("1d", [])));
    expect(await screen.findByTestId("board-empty")).toHaveTextContent(
      "No tickers on the equities list yet. Add one below.",
    );
  });

  it("the add form speaks of tickers", async () => {
    renderEquities();
    const form = await screen.findByTestId("add-coin-form");
    expect(form).toHaveAttribute("aria-label", "Add a ticker");
    expect(within(form).getByLabelText("Ticker symbol")).toBeInTheDocument();
    expect(screen.getByTestId("add-coin-button")).toHaveTextContent("Add ticker");
    expect(screen.getByTestId("coin-count")).toHaveTextContent("2 / 30 tickers");
    fireEvent.click(screen.getByTestId("add-coin-button"));
    expect(screen.getByTestId("add-coin-error")).toHaveTextContent("Enter a ticker symbol.");
  });

  it("at 30 tickers the equities cap message shows and nothing is sent", async () => {
    const symbols = Array.from({ length: 30 }, (_, i) => `T${i}`);
    const addCoin = vi.fn(async () => ({}));
    renderEquities({ fetchBoard: async (tf) => board(tf, symbols), addCoin });
    expect(await screen.findByTestId("add-coin-full")).toHaveTextContent(EQUITIES_CAP_MESSAGE);
    expect(screen.getByTestId("coin-count")).toHaveTextContent("30 / 30 tickers");
    fireEvent.change(screen.getByTestId("add-coin-input"), { target: { value: "AAPL" } });
    fireEvent.click(screen.getByTestId("add-coin-button"));
    expect(addCoin).not.toHaveBeenCalled();
  });

  it("a group counts its tickers", async () => {
    renderEquities({ fetchLayout: async () => layout([{ id: "main", name: "Main", coins: ["AAPL"] }]) });
    await screen.findByTestId("coin-panel-AAPL");
    expect(screen.getByTestId("group-count-main")).toHaveTextContent("2 tickers");
  });

  it("an empty group says it has no tickers", async () => {
    renderEquities({
      fetchLayout: async () =>
        layout([
          { id: "main", name: "Main", coins: ["AAPL", "MSFT"] },
          { id: "tech", name: "Tech", coins: [] },
        ]),
    });
    expect(await screen.findByTestId("group-empty-tech")).toHaveTextContent("No tickers in this group yet.");
    expect(screen.getByTestId("group-count-tech")).toHaveTextContent("0 tickers");
  });

  it("the drill-down opens on 1d and offers 1d and 1w only", async () => {
    const fetchChart = vi.fn(async (s: string, tf: Timeframe) => view(s, tf));
    renderEquities({ fetchChart });
    fireEvent.click(await screen.findByTestId("open-drilldown-AAPL"));
    await waitFor(() => expect(fetchChart).toHaveBeenCalledWith("AAPL", "1d"));
    const toggle = screen.getByTestId("drilldown-timeframe-toggle");
    expect(within(toggle).getAllByRole("button").map((b) => b.textContent)).toEqual(["1d", "1w"]);
    expect(screen.getByTestId("drilldown-timeframe-button-1d")).toHaveAttribute("aria-pressed", "true");
  });

  it("captions and chip titles carry the bar date, never a clock time", async () => {
    renderEquities();
    const panel = await screen.findByTestId("coin-panel-AAPL");
    const caption = within(panel).getByTestId("chart-freshness-caption");
    expect(caption).toHaveTextContent("Latest daily bar 2026-10-09");
    expect(caption.textContent).not.toMatch(/\d{2}:\d{2}|ago/);
    expect(within(panel).getByTestId("gain-chip-1d")).toHaveAttribute("title", "1d candle from 2026-10-09");
    expect(within(panel).getByTestId("gain-chip-1w")).toHaveAttribute("title", "1w candle from 2026-10-05");
  });

  it("each panel keeps its RSI row for the board timeframe", async () => {
    renderEquities();
    await screen.findByTestId("coin-panel-AAPL");
    expect(screen.getByTestId("rsi-readout-AAPL")).toHaveTextContent("RSI 14 (1d)");
    expect(screen.getByTestId("rsi-value-AAPL")).toHaveTextContent("55.5");
  });

  it("nothing crypto is drawn: no BTC or HYPE", async () => {
    const { container } = renderEquities();
    await screen.findByTestId("coin-panel-MSFT");
    expect(container.textContent).not.toMatch(/BTC|HYPE/);
    expect(container.querySelector('[data-testid^="coin-panel-BTC"]')).toBeNull();
  });

  it("zooming one equities chart hands the range to the others", async () => {
    renderEquities();
    await screen.findByTestId("coin-panel-MSFT");
    await waitFor(() => panelProps("MSFT"));
    const range: ChartRange = { from: Date.parse("2026-10-08T00:00:00Z"), to: Date.parse("2026-10-09T00:00:00Z") };
    act(() => panelProps("AAPL").onRangeChange?.(range));
    expect(panelProps("MSFT").linkedRange).toEqual(range);
    expect(panelProps("AAPL").linkedRange).toEqual(range);
  });

  it("a layout edit saves through the injected equities client", async () => {
    const saveLayout = vi.fn(async (u: LayoutUpdate) => ({ ...layout(u.groups), revision: u.revision + 1 }));
    renderEquities({
      fetchLayout: async () => layout([{ id: "main", name: "Main", coins: ["AAPL", "MSFT"] }]),
      saveLayout,
    });
    await screen.findByTestId("coin-panel-AAPL");
    fireEvent.click(screen.getByTestId("move-later-AAPL"));
    await waitFor(() => expect(saveLayout).toHaveBeenCalledTimes(1));
    expect(saveLayout.mock.calls[0][0].groups[0].coins).toEqual(["MSFT", "AAPL"]);
  });

  it("without a provider the board keeps the crypto text and timeframes", async () => {
    render(
      <ScreenerBoard fetchBoard={async (tf) => board(tf, [])} fetchSpaghetti={spaghetti} fetchLayout={async () => layout()} />,
    );
    expect(screen.getByTestId("board-loading")).toHaveTextContent("Loading coins and layout");
    const toggle = screen.getByTestId("timeframe-toggle");
    expect(within(toggle).getAllByRole("button")).toHaveLength(5);
    expect(await screen.findByTestId("board-empty")).toHaveTextContent("No coins on the watchlist yet. Add one below.");
    expect(screen.getByTestId("add-coin-button")).toHaveTextContent("Add coin");
  });
});
