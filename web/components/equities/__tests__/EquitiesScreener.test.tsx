import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import EquitiesPage, { metadata } from "@/app/equities/page";
import { EquitiesScreener, PRIVATE_USE_NOTE } from "@/components/equities/EquitiesScreener";

// T47 / S9C: the equities page with its real clients; a global fetch spy
// answers by path and records every URL the page asks for.
const island = vi.hoisted(() => {
  const mountSimpleLines = vi.fn(() => Object.assign(() => undefined, { update: vi.fn() }));
  return { loadIslands: vi.fn(() => Promise.resolve({ mountSimpleLines })) };
});

vi.mock("@/lib/island-loader", () => ({ loadIslands: island.loadIslands }));

const STATUS = {
  running: true,
  disabled_reason: null,
  interval_seconds: 3600,
  last_tick_started: "2026-10-09T21:00:00Z",
  last_tick_finished: "2026-10-09T21:01:00Z",
  last_tick_ok: 2,
  last_tick_failed: 0,
  next_tick_at: "2026-10-10T21:00:00Z",
  queue_depth: 0,
  backoff_seconds: 0,
  server_time: "2026-10-10T08:00:00Z",
};

function ticker(symbol: string) {
  return {
    symbol,
    chart: {
      price: [{ timestamp: "2026-10-09T00:00:00Z", close: 100 }],
      sma: [],
      available: true,
      reason: null,
      last_bar_ts: "2026-10-09T00:00:00Z",
      fetched_at: null,
      is_partial: false,
      server_time: "2026-10-10T08:00:00Z",
      stale: false,
      rsi: [],
    },
    percent_change_by_timeframe: { "1d": null, "1w": null },
    gain_by_timeframe: {},
    rsi: { value: null, length: 14, as_of: null, reason: "insufficient-history" },
  };
}

let tickers: string[];
let urls: string[];
let fetchMock: ReturnType<typeof vi.fn>;

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status });
}

function answer(url: string, init?: RequestInit): Response {
  const path = new URL(url).pathname;
  if (path === "/api/equities/status") return json(STATUS);
  if (path === "/api/equities/board") {
    return json({ timeframe: "1d", coins: tickers.map(ticker), server_time: null, clock_skew_seconds: null, clock_skew_warning: false });
  }
  if (path === "/api/equities/spaghetti") return json({ timeframe: "1d", window_cap_bars: 200, server_time: null, series: [], references: [] });
  if (path === "/api/layout/equities") {
    return json({ version: 1, section: "equities", revision: 0, saved_at: null, source: "default", groups: [{ id: "main", name: "Main", coins: [] }], hidden_lines: [] });
  }
  if (path === "/api/equities" && init?.method === "POST") {
    tickers = [...tickers, (JSON.parse(String(init.body)) as { symbol: string }).symbol];
    return json({ tickers });
  }
  if (path.startsWith("/api/equities/") && init?.method === "DELETE") {
    tickers = tickers.filter((t) => `/api/equities/${t}` !== path);
    return json({ tickers });
  }
  return json({ detail: "not found" }, 404);
}

async function settle(ms = 0) {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms);
  });
}

beforeEach(() => {
  vi.useFakeTimers();
  tickers = ["AAPL"];
  urls = [];
  fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
    urls.push(url);
    return answer(url, init);
  });
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

function statusCalls(): number {
  return urls.filter((u) => u.endsWith("/api/equities/status")).length;
}

describe("EquitiesScreener (T47 / S9C)", () => {
  it("shows the private-use note", async () => {
    render(<EquitiesScreener />);
    await settle();
    expect(screen.getByTestId("equities-note")).toHaveTextContent(PRIVATE_USE_NOTE);
    expect(PRIVATE_USE_NOTE).toContain("Prices are split-adjusted only; delisted tickers have no data.");
  });

  it("the strip re-reads the equities status every 60 000 ms", async () => {
    render(<EquitiesScreener />);
    await settle();
    expect(screen.getByTestId("freshness-strip")).toBeInTheDocument();
    expect(statusCalls()).toBe(1);
    await settle(59_999);
    expect(statusCalls()).toBe(1);
    await settle(1);
    expect(statusCalls()).toBe(2);
  });

  it("adding a ticker posts it to /api/equities and draws its panel", async () => {
    render(<EquitiesScreener />);
    await settle();
    expect(screen.getByTestId("coin-panel-AAPL")).toBeInTheDocument();
    fireEvent.change(screen.getByTestId("add-coin-input"), { target: { value: "msft" } });
    fireEvent.click(screen.getByTestId("add-coin-button"));
    await settle();
    const post = fetchMock.mock.calls.find(([, init]) => (init as RequestInit | undefined)?.method === "POST");
    expect(post?.[0]).toMatch(/\/api\/equities$/);
    expect(JSON.parse(String((post?.[1] as RequestInit).body))).toEqual({ symbol: "MSFT", group_id: "main" });
    expect(screen.getByTestId("coin-panel-MSFT")).toBeInTheDocument();
    expect(screen.getByTestId("coin-count")).toHaveTextContent("2 / 30 tickers");
  });

  it("removing a ticker deletes it through /api/equities/<T>", async () => {
    tickers = ["AAPL", "MSFT"];
    render(<EquitiesScreener />);
    await settle();
    fireEvent.click(screen.getByTestId("remove-MSFT"));
    fireEvent.click(screen.getByTestId("confirm-remove-MSFT"));
    await settle();
    expect(urls.some((u) => u.endsWith("/api/equities/MSFT"))).toBe(true);
    expect(screen.queryByTestId("coin-panel-MSFT")).toBeNull();
  });

  it("every request goes to /api/equities or the equities layout", async () => {
    render(<EquitiesScreener />);
    await settle();
    await settle(60_000);
    expect(urls.length).toBeGreaterThan(0);
    for (const url of urls) expect(new URL(url).pathname).toMatch(/^\/api\/(equities(\/|$)|layout\/equities$)/);
  });

  it("never calls the crypto screener, watchlist, layout or refresh endpoints", async () => {
    render(<EquitiesScreener />);
    await settle();
    fireEvent.click(screen.getByTestId("open-drilldown-AAPL"));
    fireEvent.click(screen.getByTestId("timeframe-button-1w"));
    await settle(60_000);
    expect(urls.some((u) => u.includes("/api/equities/AAPL/chart"))).toBe(true);
    for (const url of urls) {
      expect(url).not.toMatch(/\/api\/screener|\/api\/watchlist|\/api\/layout\/crypto|\/api\/refresh/);
    }
  });

  it("no heading says Screener", async () => {
    render(<EquitiesScreener />);
    await settle();
    for (const heading of screen.queryAllByRole("heading")) expect(heading.textContent).not.toMatch(/Screener/);
  });

  it("the page is titled Equities, with one Equities heading", async () => {
    render(<EquitiesPage />);
    await settle();
    expect(metadata.title).toBe("Equities");
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Equities");
    for (const heading of screen.getAllByRole("heading")) expect(heading.textContent).not.toMatch(/Screener/);
  });
});
