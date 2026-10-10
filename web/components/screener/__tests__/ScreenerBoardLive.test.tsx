import { act, fireEvent, render, screen } from "@testing-library/react";
import { StrictMode, type ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { BtcLegChart } from "@/components/screener/BtcLegChart";
import { FreshnessStrip } from "@/components/screener/FreshnessStrip";
import { LiveProvider } from "@/components/screener/LiveProvider";
import { ScreenerBoard } from "@/components/screener/ScreenerBoard";
import type { SimpleLinesProps } from "@/lib/island-loader";
import type { Layout } from "@/lib/types/layout";
import type { BtcLegChartResponse } from "@/lib/types/btc-legs";
import type { RefreshStatus } from "@/lib/types/refresh";
import type { ChartView, ScreenerBoardResponse, SpaghettiResponse, Timeframe } from "@/lib/types/screener";

// Every island mount is recorded with its target, its props and its own
// update and dispose spies, so a test can say which chart was touched.
const island = vi.hoisted(() => {
  type Mount = {
    target: HTMLElement;
    props: unknown;
    update: ReturnType<typeof vi.fn>;
    dispose: ReturnType<typeof vi.fn>;
  };
  const mounts: Mount[] = [];
  const mountSimpleLines = vi.fn((target: HTMLElement, props: unknown) => {
    const m: Mount = { target, props, update: vi.fn(), dispose: vi.fn() };
    mounts.push(m);
    return Object.assign(() => m.dispose(), { update: m.update });
  });
  const api = { mountSimpleLines };
  return { mounts, mountSimpleLines, loadIslands: vi.fn(() => Promise.resolve(api)) };
});

vi.mock("@/lib/island-loader", () => ({ loadIslands: island.loadIslands }));

// T41 / S5b: the board also loads the layout; one group, no coins (the
// board appends unplaced coins), so no real fetch runs.
const fetchLayoutStub = async (): Promise<Layout> => ({
  version: 1,
  section: "crypto",
  revision: 0,
  saved_at: null,
  source: "default",
  groups: [{ id: "main", name: "Main", coins: [] }],
  hidden_lines: [],
});

const SERVER = "2026-10-03T14:22:00Z";

function status(overrides: Partial<RefreshStatus> = {}): RefreshStatus {
  return {
    running: true,
    disabled_reason: null,
    interval_seconds: 900,
    last_tick_started: "2026-10-03T14:14:00Z",
    last_tick_finished: "2026-10-03T14:15:00Z",
    last_tick_ok: 10,
    last_tick_failed: 0,
    next_tick_at: "2026-10-03T14:30:00Z",
    queue_depth: 0,
    backoff_seconds: 0,
    server_time: SERVER,
    ...overrides,
  };
}

function coin(symbol: string, close = 100, serverTime: string | null = null) {
  return {
    symbol,
    chart: {
      price: [
        { timestamp: "2026-10-02T00:00:00Z", close: close - 1 },
        { timestamp: "2026-10-03T00:00:00Z", close },
      ],
      sma: [],
      available: true as const,
      reason: null,
      last_bar_ts: "2026-10-03T14:00:00Z",
      fetched_at: serverTime,
      is_partial: false,
      server_time: serverTime,
      stale: false,
      rsi: [],
    },
    percent_change_by_timeframe: { "15m": 1, "1h": 1, "4h": 1, "1d": 1, "1w": 1 },
    gain_by_timeframe: {},
    rsi: { value: null, length: 14, as_of: null, reason: null },
  };
}

function board(timeframe: Timeframe, coins = [coin("BTC"), coin("ETH"), coin("SOL")], serverTime = SERVER) {
  return { timeframe, coins, server_time: serverTime, clock_skew_seconds: 0.1, clock_skew_warning: false } as unknown as ScreenerBoardResponse;
}

function chartView(symbol: string, timeframe: Timeframe): ChartView {
  return { symbol, timeframe, chart: coin(symbol).chart } as unknown as ChartView;
}

function spaghetti(timeframe: Timeframe): SpaghettiResponse {
  return { timeframe, window_cap_bars: 200, server_time: null, series: [], references: [] };
}

const BTC_UNAVAILABLE = { available: false, reason: "no BTC 1d bars in the cache" } as unknown as BtcLegChartResponse;

let monoNow = 0;
let visibility: DocumentVisibilityState = "visible";

async function advance(ms: number) {
  await act(async () => {
    monoNow += ms;
    await vi.advanceTimersByTimeAsync(ms);
  });
}

/** Island mounts that live inside the element with this testid. */
function mountsIn(testId: string) {
  return island.mounts.filter((m) => m.target.closest(`[data-testid="${testId}"]`));
}

interface Setup {
  fetchStatus?: (signal: AbortSignal) => Promise<RefreshStatus>;
  fetchBoard?: (tf: Timeframe) => Promise<ScreenerBoardResponse>;
  fetchChart?: (symbol: string, tf: Timeframe) => Promise<ChartView>;
  fetchSpaghetti?: (tf: Timeframe) => Promise<SpaghettiResponse>;
  fetchBtc?: () => Promise<BtcLegChartResponse>;
  provider?: boolean;
  strict?: boolean;
}

function setup(opts: Setup = {}) {
  const fetchStatus = vi.fn(opts.fetchStatus ?? (async () => status()));
  const fetchBoard = vi.fn(opts.fetchBoard ?? (async (tf: Timeframe) => board(tf)));
  const fetchChart = vi.fn(opts.fetchChart ?? (async (s: string, tf: Timeframe) => chartView(s, tf)));
  const fetchSpaghetti = vi.fn(opts.fetchSpaghetti ?? (async (tf: Timeframe) => spaghetti(tf)));
  const fetchBtc = vi.fn(opts.fetchBtc ?? (async () => BTC_UNAVAILABLE));
  const page = (
    <>
      <FreshnessStrip />
      <BtcLegChart fetchData={fetchBtc} />
      <ScreenerBoard fetchLayout={fetchLayoutStub} fetchBoard={fetchBoard} fetchChart={fetchChart} fetchSpaghetti={fetchSpaghetti} />
    </>
  );
  let tree: ReactNode =
    opts.provider === false ? (
      <ScreenerBoard fetchLayout={fetchLayoutStub} fetchBoard={fetchBoard} fetchChart={fetchChart} fetchSpaghetti={fetchSpaghetti} />
    ) : (
      <LiveProvider fetchStatus={fetchStatus} mono={() => monoNow}>
        {page}
      </LiveProvider>
    );
  if (opts.strict) tree = <StrictMode>{tree}</StrictMode>;
  render(tree);
  return { fetchStatus, fetchBoard, fetchChart, fetchSpaghetti, fetchBtc };
}

beforeEach(() => {
  vi.useFakeTimers();
  monoNow = 0;
  visibility = "visible";
  Object.defineProperty(document, "visibilityState", { configurable: true, get: () => visibility });
  island.mounts.length = 0;
  island.mountSimpleLines.mockClear();
});

afterEach(() => {
  vi.useRealTimers();
});

describe("ScreenerBoard live", () => {
  it("no provider: one board fetch and no timer", async () => {
    const { fetchBoard, fetchStatus } = setup({ provider: false });
    await advance(0);
    expect(screen.getByTestId("coin-panel-BTC")).toBeInTheDocument();
    await advance(600_000);
    expect(fetchBoard).toHaveBeenCalledTimes(1);
    expect(fetchStatus).not.toHaveBeenCalled();
    expect(vi.getTimerCount()).toBe(0);
  });

  it("a tick refetches the current timeframe and the focused timeframe button keeps focus", async () => {
    const { fetchBoard } = setup();
    await advance(0);
    const button = screen.getByTestId("timeframe-button-1h");
    button.focus();
    fireEvent.click(button);
    await advance(0);
    expect(fetchBoard).toHaveBeenLastCalledWith("1h");
    const calls = fetchBoard.mock.calls.length;
    await advance(60_000);
    expect(fetchBoard).toHaveBeenCalledTimes(calls + 1);
    expect(fetchBoard).toHaveBeenLastCalledWith("1h");
    expect(document.activeElement).toBe(screen.getByTestId("timeframe-button-1h"));
  });

  it("an identical payload apart from volatile keys makes zero island updates", async () => {
    let n = 0;
    setup({
      fetchBoard: async (tf) => {
        n += 1;
        const stamp = `2026-10-03T14:${String(20 + n).padStart(2, "0")}:00Z`;
        return board(tf, [coin("BTC", 100, stamp), coin("ETH", 100, stamp), coin("SOL", 100, stamp)], stamp);
      },
    });
    await advance(0);
    const panelMounts = ["BTC", "ETH", "SOL"].flatMap((s) => mountsIn(`coin-panel-${s}`));
    expect(panelMounts).toHaveLength(3);
    // The spaghetti chart mounts empty and gets its first data by update;
    // count only what the refetches do.
    const baseline = island.mounts.map((m) => m.update.mock.calls.length);
    const mountsBefore = island.mounts.length;
    await advance(60_000);
    await advance(60_000);
    expect(n).toBe(3);
    const touched = island.mounts
      .filter((m, i) => m.update.mock.calls.length > (baseline[i] ?? 0))
      .map((m) => (m.props as SimpleLinesProps).label);
    expect(touched).toEqual([]);
    expect(island.mounts).toHaveLength(mountsBefore);
  });

  it("one changed coin makes one update, the others none", async () => {
    let n = 0;
    setup({
      fetchBoard: async (tf) => {
        n += 1;
        return board(tf, [coin("BTC", n === 1 ? 100 : 105), coin("ETH"), coin("SOL")]);
      },
    });
    await advance(0);
    await advance(60_000);
    const [btc] = mountsIn("coin-panel-BTC");
    expect(btc.update).toHaveBeenCalledTimes(1);
    const sent = btc.update.mock.calls[0][0] as SimpleLinesProps;
    expect(sent.series[0].points.at(-1)?.value).toBe(105);
    expect(mountsIn("coin-panel-ETH")[0].update).not.toHaveBeenCalled();
    expect(mountsIn("coin-panel-SOL")[0].update).not.toHaveBeenCalled();
    expect(mountsIn("coin-panel-BTC")).toHaveLength(1);
  });

  it("a failed refetch keeps the panels and shows board-error; the next success clears it", async () => {
    let n = 0;
    setup({
      fetchBoard: async (tf) => {
        n += 1;
        if (n === 2) throw new Error("API request failed: /api/screener/board?timeframe=1d -> 503");
        return board(tf);
      },
    });
    await advance(0);
    await advance(60_000);
    expect(screen.getByTestId("board-error")).toHaveTextContent("503");
    expect(screen.getByTestId("coin-panel-BTC")).toBeInTheDocument();
    expect(screen.getByTestId("coin-panel-SOL")).toBeInTheDocument();
    await advance(60_000);
    expect(screen.queryByTestId("board-error")).toBeNull();
    expect(screen.getByTestId("coin-panel-BTC")).toBeInTheDocument();
  });

  it("the open drill-down stays open and refetches its own timeframe; failure keeps mini-chart beside drilldown-error; another coin re-mounts", async () => {
    let fail = false;
    const { fetchChart } = setup({
      fetchChart: async (s, tf) => {
        if (fail) throw new Error("API request failed: chart -> 500");
        return chartView(s, tf);
      },
    });
    await advance(0);
    fireEvent.click(screen.getByTestId("open-drilldown-BTC"));
    await advance(0);
    fireEvent.click(screen.getByTestId("drilldown-timeframe-button-1w"));
    await advance(0);
    expect(fetchChart).toHaveBeenLastCalledWith("BTC", "1w");
    const calls = fetchChart.mock.calls.length;

    fail = true;
    await advance(60_000);
    expect(fetchChart).toHaveBeenCalledTimes(calls + 1);
    expect(fetchChart).toHaveBeenLastCalledWith("BTC", "1w");
    const view = screen.getByTestId("drilldown-view");
    expect(view.querySelector('[data-testid="drilldown-error"]')).toHaveTextContent("500");
    expect(view.querySelector('[data-testid="mini-chart"]')).not.toBeNull();

    fail = false;
    const before = mountsIn("drilldown-view").length;
    fireEvent.click(screen.getByTestId("open-drilldown-ETH"));
    await advance(0);
    expect(screen.getByTestId("drilldown-view").getAttribute("aria-label")).toBe("ETH drill-down");
    expect(fetchChart).toHaveBeenLastCalledWith("ETH", "4h");
    expect(mountsIn("drilldown-view").length).toBe(before + 1);
    expect(mountsIn("drilldown-view").at(-1)?.target.isConnected).toBe(true);
  });

  it("a slow answer for the old timeframe is ignored", async () => {
    let hold: ((b: ScreenerBoardResponse) => void) | null = null;
    let n1d = 0;
    setup({
      fetchBoard: (tf) => {
        if (tf !== "1d") return Promise.resolve(board(tf, [coin("NEW")]));
        n1d += 1;
        if (n1d === 1) return Promise.resolve(board(tf));
        // The tick's 1d refetch hangs until after the switch to 4h.
        return new Promise<ScreenerBoardResponse>((resolve) => {
          hold = resolve;
        });
      },
    });
    await advance(0);
    await advance(60_000);
    expect(hold).not.toBeNull();
    // The old data stays while the new timeframe loads.
    fireEvent.click(screen.getByTestId("timeframe-button-4h"));
    expect(screen.getByTestId("coin-panel-BTC")).toBeInTheDocument();
    await advance(0);
    expect(screen.getByTestId("coin-panel-NEW")).toBeInTheDocument();
    await act(async () => {
      hold!(board("1d", [coin("OLD")]));
    });
    await advance(0);
    expect(screen.queryByTestId("coin-panel-OLD")).toBeNull();
    expect(screen.getByTestId("coin-panel-NEW")).toBeInTheDocument();
  });

  it("spaghetti and BTC refetch on dataVersion only and keep data on failure", async () => {
    const answers = [
      status(),
      status({ server_time: "2026-10-03T14:23:00Z" }), // nothing changed: tick only
      status({ last_tick_finished: "2026-10-03T14:30:00Z" }), // new data
      status({ last_tick_finished: "2026-10-03T14:45:00Z" }), // new data, charts fail
    ];
    let failCharts = false;
    const { fetchSpaghetti, fetchBtc, fetchBoard } = setup({
      fetchStatus: async () => answers.shift() ?? status({ last_tick_finished: "2026-10-03T14:45:00Z" }),
      fetchSpaghetti: async (tf) => {
        if (failCharts) throw new Error("spaghetti -> 502");
        return spaghetti(tf);
      },
      fetchBtc: async () => {
        if (failCharts) throw new Error("btc legs -> 502");
        return BTC_UNAVAILABLE;
      },
    });
    await advance(0);
    expect(fetchSpaghetti).toHaveBeenCalledTimes(1);
    expect(fetchBtc).toHaveBeenCalledTimes(1);
    await advance(60_000);
    expect(fetchBoard).toHaveBeenCalledTimes(2);
    expect(fetchSpaghetti).toHaveBeenCalledTimes(1);
    expect(fetchBtc).toHaveBeenCalledTimes(1);
    await advance(60_000);
    expect(fetchSpaghetti).toHaveBeenCalledTimes(2);
    expect(fetchBtc).toHaveBeenCalledTimes(2);
    failCharts = true;
    await advance(60_000);
    expect(fetchSpaghetti).toHaveBeenCalledTimes(3);
    expect(screen.getByTestId("spaghetti-error")).toHaveTextContent("502");
    expect(screen.getByTestId("btc-leg-error")).toHaveTextContent("502");
    expect(screen.getByTestId("btc-leg-unavailable")).toBeInTheDocument();
    expect(screen.getByTestId("spaghetti-chart-container")).toBeInTheDocument();
  });

  it("hidden: no board request in 5 min", async () => {
    const { fetchBoard, fetchStatus } = setup();
    await advance(0);
    act(() => {
      visibility = "hidden";
      document.dispatchEvent(new Event("visibilitychange"));
    });
    await advance(300_000);
    expect(fetchBoard).toHaveBeenCalledTimes(1);
    expect(fetchStatus).toHaveBeenCalledTimes(1);
  });

  it("resume: an immediate status check, then a board refetch", async () => {
    const { fetchBoard, fetchStatus } = setup();
    await advance(0);
    act(() => {
      visibility = "hidden";
      document.dispatchEvent(new Event("visibilitychange"));
    });
    await advance(300_000);
    act(() => {
      visibility = "visible";
      document.dispatchEvent(new Event("visibilitychange"));
    });
    expect(fetchStatus).toHaveBeenCalledTimes(2);
    await advance(0);
    expect(fetchBoard).toHaveBeenCalledTimes(2);
  });

  it("a caption age follows the live clock", async () => {
    const answers = [status(), status({ server_time: "2026-10-03T14:25:00Z" })];
    setup({ fetchStatus: async () => answers.shift() ?? status({ server_time: "2026-10-03T14:26:00Z" }) });
    const caption = () => screen.getByTestId("coin-panel-BTC").querySelector('[data-testid="chart-freshness-caption"]');
    await advance(0);
    // Bar 14:00Z and the board payload has no clock: the age is the live
    // server clock's (14:22Z, then 14:25Z), never the browser's.
    expect(caption()?.textContent).toBe("Last bar 2026-10-03 16:00 CEST, 22 min ago");
    await advance(30_000);
    expect(caption()?.textContent).toBe("Last bar 2026-10-03 16:00 CEST, 22 min ago");
    await advance(30_000);
    expect(caption()?.textContent).toBe("Last bar 2026-10-03 16:00 CEST, 25 min ago");
    await advance(60_000);
    expect(caption()?.textContent).toBe("Last bar 2026-10-03 16:00 CEST, 26 min ago");
  });

  it("inside StrictMode the first check triggers no second board fetch and no failure line", async () => {
    const { fetchBoard } = setup({ strict: true });
    const mountCalls = fetchBoard.mock.calls.length;
    await advance(0);
    await advance(0);
    expect(fetchBoard).toHaveBeenCalledTimes(mountCalls);
    expect(screen.queryByTestId("strip-failed")).toBeNull();
    expect(screen.getByTestId("strip-announcer").textContent).toBe("");
    expect(screen.getByTestId("strip-refreshed")).toBeInTheDocument();
  });
});
