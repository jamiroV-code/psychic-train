import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { EquitiesScreener } from "@/components/equities/EquitiesScreener";

// T48 / S9D: the equities page with its real clients; a global fetch spy
// answers by path and records every request. The island is a stub that keeps
// the props each chart was given.
const island = vi.hoisted(() => {
  const mounted: { target: HTMLElement; props: unknown }[] = [];
  const mountSimpleLines = vi.fn((target: HTMLElement, props: unknown) => {
    const entry = { target, props };
    mounted.push(entry);
    return Object.assign(() => undefined, {
      update: vi.fn((next: unknown) => {
        entry.props = next;
      }),
    });
  });
  return { mounted, loadIslands: vi.fn(() => Promise.resolve({ mountSimpleLines })) };
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
  next_tick_at: "2026-10-12T20:30:00Z",
  queue_depth: 0,
  backoff_seconds: 0,
  server_time: "2026-10-12T08:00:00Z",
};

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status });
}

async function settle(ms = 0) {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms);
  });
}

function board(tf: string) {
  return {
    timeframe: tf,
    coins: [
      {
        symbol: "SYNA",
        chart: { ...chart(tf), rsi: [] },
        percent_change_by_timeframe: { "1d": null, "1w": null },
        gain_by_timeframe: {},
        rsi: { value: null, length: 14, as_of: null, reason: "insufficient-history" },
      },
    ],
    server_time: null,
    clock_skew_seconds: null,
    clock_skew_warning: false,
  };
}

function chart(tf: string) {
  const last = tf === "1w" ? "2026-10-05T00:00:00Z" : "2026-10-09T00:00:00Z";
  return {
    price: [
      { timestamp: "2026-10-08T00:00:00Z", close: 100 },
      { timestamp: last, close: 101 },
    ],
    sma: [],
    available: true,
    reason: null,
    last_bar_ts: last,
    fetched_at: null,
    is_partial: false,
    server_time: "2026-10-12T08:00:00Z",
    stale: false,
    rsi: [
      { timestamp: "2026-10-08T00:00:00Z", value: 52.0 },
      { timestamp: last, value: tf === "1w" ? 61.25 : 55.34 },
    ],
  };
}

let view: (tf: string) => unknown;
let urls: string[];

function answer(url: string): Response {
  const parsed = new URL(url);
  const path = parsed.pathname;
  const tf = parsed.searchParams.get("timeframe") ?? "1d";
  if (path === "/api/equities/status") return json(STATUS);
  if (path === "/api/equities/board") return json(board(tf));
  if (path === "/api/equities/spaghetti") return json({ timeframe: tf, window_cap_bars: 200, server_time: null, series: [], references: [] });
  if (path === "/api/equities/SYNA/chart") return json({ symbol: "SYNA", timeframe: tf, chart: view(tf) });
  if (path === "/api/layout/equities") {
    return json({ version: 1, section: "equities", revision: 0, saved_at: null, source: "default", groups: [{ id: "main", name: "Main", coins: ["SYNA"] }], hidden_lines: [] });
  }
  return json({ detail: "not found" }, 404);
}

beforeEach(() => {
  vi.useFakeTimers();
  island.mounted.length = 0;
  urls = [];
  view = chart;
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => {
      urls.push(url);
      return answer(url);
    }),
  );
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

function chartCalls(tf: string): number {
  return urls.filter((u) => u.endsWith(`/api/equities/SYNA/chart?timeframe=${tf}`)).length;
}

async function openDrillDown() {
  render(<EquitiesScreener />);
  await settle();
  fireEvent.click(screen.getByTestId("open-drilldown-SYNA"));
  await settle();
  return screen.getByTestId("drilldown-view");
}

describe("Equities drill-down (T48 / S9D)", () => {
  it("opens on 1d with only the 1d and 1w buttons", async () => {
    const dialog = await openDrillDown();
    expect(chartCalls("1d")).toBe(1);
    expect(screen.getByTestId("drilldown-timeframe-button-1d")).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByTestId("drilldown-timeframe-button-1w")).toHaveAttribute("aria-pressed", "false");
    const buttons = dialog.querySelectorAll('[data-testid^="drilldown-timeframe-button-"]');
    expect([...buttons].map((b) => b.textContent)).toEqual(["1d", "1w"]);
  });

  it("the 1w button refetches the weekly chart and the caption follows", async () => {
    await openDrillDown();
    fireEvent.click(screen.getByTestId("drilldown-timeframe-button-1w"));
    await settle();
    expect(chartCalls("1w")).toBe(1);
    expect(screen.getByTestId("drilldown-timeframe-button-1w")).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByTestId("drilldown-rsi-value")).toHaveTextContent("RSI 14 (1w): 61.3");
    const dialog = screen.getByTestId("drilldown-view");
    expect(dialog).toHaveTextContent("Latest weekly bar, week of 2026-10-05");
  });

  it("shows the price chart, the RSI chart and the RSI value", async () => {
    const dialog = await openDrillDown();
    const price = dialog.querySelector('[data-testid="mini-chart"]');
    const rsi = dialog.querySelector('[data-testid="drilldown-rsi-chart"]');
    expect(price).not.toBeNull();
    expect(rsi).not.toBeNull();
    expect(island.mounted.some((m) => m.target === price)).toBe(true);
    expect(island.mounted.some((m) => m.target === rsi)).toBe(true);
    expect(screen.getByTestId("drilldown-rsi-value")).toHaveTextContent("RSI 14 (1d): 55.3");
    expect(dialog).toHaveTextContent("Latest daily bar 2026-10-09");
  });

  it("RSI reads N/A when the price did not change", async () => {
    view = (tf) => ({ ...chart(tf), rsi: [] });
    await openDrillDown();
    expect(screen.getByTestId("drilldown-rsi-na")).toHaveTextContent("RSI 14: N/A, price did not change in this window");
    expect(screen.queryByTestId("drilldown-rsi-value")).toBeNull();
    expect(screen.queryByTestId("drilldown-rsi-chart")).toBeNull();
  });

  it("an unavailable chart shows its reason", async () => {
    view = () => ({ ...chart("1d"), price: [], rsi: [], available: false, reason: "source-unavailable", last_bar_ts: null });
    await openDrillDown();
    expect(screen.getByTestId("drilldown-chart-unavailable")).toHaveTextContent("Data source unavailable");
    expect(screen.getByTestId("drilldown-view").querySelector('[data-testid="mini-chart"]')).toBeNull();
  });

  it("refetches its chart on every live tick", async () => {
    await openDrillDown();
    expect(chartCalls("1d")).toBe(1);
    await settle(60_000);
    expect(chartCalls("1d")).toBe(2);
    await settle(60_000);
    expect(chartCalls("1d")).toBe(3);
    expect(chartCalls("1w")).toBe(0);
  });
});
