import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { LiveProvider } from "@/components/screener/LiveProvider";
import { ScreenerBoard } from "@/components/screener/ScreenerBoard";
import type { ChartRange, SimpleLinesProps } from "@/lib/island-loader";
import type { Layout } from "@/lib/types/layout";
import type { RefreshStatus } from "@/lib/types/refresh";
import type { ScreenerBoardResponse, SpaghettiResponse, Timeframe } from "@/lib/types/screener";

// T44: the board's small charts share one zoom. Every island mount records
// its target, its latest props and its update spy.
const island = vi.hoisted(() => {
  type Mount = { target: HTMLElement; props: unknown; update: ReturnType<typeof vi.fn> };
  const mounts: Mount[] = [];
  const mountSimpleLines = vi.fn((target: HTMLElement, props: unknown) => {
    const m: Mount = { target, props, update: vi.fn((next: unknown) => (m.props = next)) };
    mounts.push(m);
    return Object.assign(() => undefined, { update: m.update });
  });
  return { mounts, loadIslands: vi.fn(() => Promise.resolve({ mountSimpleLines })) };
});

vi.mock("@/lib/island-loader", () => ({ loadIslands: island.loadIslands }));

function status(): RefreshStatus {
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
    server_time: "2026-10-03T14:22:00Z",
  };
}

function coin(symbol: string, close: number) {
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
      last_bar_ts: "2026-10-03T00:00:00Z",
      fetched_at: null,
      is_partial: false,
      server_time: null,
      stale: false,
      rsi: [],
    },
    percent_change_by_timeframe: {},
    gain_by_timeframe: {},
    rsi: { value: null, length: 14, as_of: null, reason: null },
  };
}

function board(timeframe: Timeframe, close = 100) {
  return {
    timeframe,
    coins: [coin("BTC", close), coin("ETH", close), coin("SOL", close)],
    server_time: null,
    clock_skew_seconds: 0,
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

let monoNow = 0;

async function advance(ms: number) {
  await act(async () => {
    monoNow += ms;
    await vi.advanceTimersByTimeAsync(ms);
  });
}

function panelProps(symbol: string): SimpleLinesProps {
  const m = island.mounts.filter((x) => x.target.closest(`[data-testid="coin-panel-${symbol}"]`)).at(-1);
  if (!m) throw new Error(`no chart for ${symbol}`);
  return m.props as SimpleLinesProps;
}

function zoomFrom(symbol: string, range: ChartRange | null) {
  act(() => {
    panelProps(symbol).onRangeChange?.(range);
  });
}

const RANGE = { from: Date.parse("2026-10-02T06:00:00Z"), to: Date.parse("2026-10-02T18:00:00Z") };

beforeEach(() => {
  vi.useFakeTimers();
  monoNow = 0;
  island.mounts.length = 0;
});

afterEach(() => {
  vi.useRealTimers();
});

describe("ScreenerBoard linked zoom (T44)", () => {
  it("zooming one small chart hands the same range to every other one", async () => {
    let close = 100;
    const fetchBoard = vi.fn(async (tf: Timeframe) => board(tf, close));
    render(
      <LiveProvider fetchStatus={async () => status()} mono={() => monoNow}>
        <ScreenerBoard fetchLayout={fetchLayoutStub} fetchBoard={fetchBoard} fetchSpaghetti={spaghetti} />
      </LiveProvider>,
    );
    await advance(0);
    for (const s of ["BTC", "ETH", "SOL"]) {
      expect(panelProps(s).linkedRange).toBeNull();
      expect(typeof panelProps(s).onRangeChange).toBe("function");
    }

    zoomFrom("ETH", RANGE);
    for (const s of ["BTC", "ETH", "SOL"]) expect(panelProps(s).linkedRange).toEqual(RANGE);

    // A live update brings new data in place and keeps the shared zoom.
    close = 120;
    await advance(60_000);
    expect(fetchBoard.mock.calls.length).toBeGreaterThan(1);
    for (const s of ["BTC", "ETH", "SOL"]) {
      expect(panelProps(s).series[0].points.at(-1)?.value).toBe(120);
      expect(panelProps(s).linkedRange).toEqual(RANGE);
    }

    // A reset (double-click) on one resets all of them.
    zoomFrom("SOL", null);
    for (const s of ["BTC", "ETH", "SOL"]) expect(panelProps(s).linkedRange).toBeNull();
  });

  it("a new timeframe starts every small chart at the full range", async () => {
    render(<ScreenerBoard fetchLayout={fetchLayoutStub} fetchBoard={async (tf) => board(tf)} fetchSpaghetti={spaghetti} />);
    await advance(0);
    zoomFrom("BTC", RANGE);
    expect(panelProps("SOL").linkedRange).toEqual(RANGE);
    fireEvent.click(screen.getByTestId("timeframe-button-4h"));
    await advance(0);
    for (const s of ["BTC", "ETH", "SOL"]) expect(panelProps(s).linkedRange).toBeNull();
  });

  it("the spaghetti chart is not linked", async () => {
    render(<ScreenerBoard fetchLayout={fetchLayoutStub} fetchBoard={async (tf) => board(tf)} fetchSpaghetti={spaghetti} />);
    await advance(0);
    const spag = island.mounts.filter((m) => m.target.closest('[data-testid="spaghetti-chart-container"]'));
    expect(spag.length).toBeGreaterThan(0);
    for (const m of spag) expect((m.props as SimpleLinesProps).onRangeChange).toBeUndefined();
  });
});
