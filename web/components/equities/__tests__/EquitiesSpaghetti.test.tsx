import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { EquitiesScreener } from "@/components/equities/EquitiesScreener";
import type { SimpleLinesProps } from "@/lib/island-loader";

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
      server_time: "2026-10-12T08:00:00Z",
      stale: false,
      rsi: [],
    },
    percent_change_by_timeframe: { "1d": null, "1w": null },
    gain_by_timeframe: {},
    rsi: { value: null, length: 14, as_of: null, reason: "insufficient-history" },
  };
}

function line(symbol: string, timeframe: string, available = true) {
  const start = timeframe === "1w" ? "2026-03-30T00:00:00Z" : "2025-12-22T00:00:00Z";
  const end = timeframe === "1w" ? "2026-10-05T00:00:00Z" : "2026-10-09T00:00:00Z";
  return {
    symbol,
    available,
    reason: available ? null : "insufficient-history",
    points: available
      ? [
          { timestamp: start, close: 0 },
          { timestamp: end, close: 4.2 },
        ]
      : [],
    window_start: available ? start : null,
    window_end: available ? end : null,
    bars: available ? (timeframe === "1w" ? 28 : 200) : 0,
    last_bar_ts: available ? end : null,
    stale: false,
  };
}

let series: (timeframe: string) => unknown[];
let calls: { url: string; init?: RequestInit }[];

function answer(url: string, init?: RequestInit): Response {
  const parsed = new URL(url);
  const path = parsed.pathname;
  const tf = parsed.searchParams.get("timeframe") ?? "1d";
  if (path === "/api/equities/status") return json(STATUS);
  if (path === "/api/equities/board") {
    return json({ timeframe: tf, coins: ["SYNA", "SYNB", "SYNTHIN"].map(ticker), server_time: null, clock_skew_seconds: null, clock_skew_warning: false });
  }
  if (path === "/api/equities/spaghetti") {
    return json({ timeframe: tf, window_cap_bars: tf === "1w" ? 28 : 200, server_time: null, series: series(tf), references: [] });
  }
  if (path === "/api/layout/equities") {
    const saved = init?.method === "POST" ? (JSON.parse(String(init.body)) as { groups: unknown; hidden_lines: string[] }) : null;
    return json({
      version: 1,
      section: "equities",
      revision: saved ? 1 : 0,
      saved_at: saved ? "2026-10-12T08:00:00Z" : null,
      source: saved ? "saved" : "default",
      groups: saved ? saved.groups : [{ id: "main", name: "Main", coins: ["SYNA", "SYNB", "SYNTHIN"] }],
      hidden_lines: saved ? saved.hidden_lines : [],
    });
  }
  return json({ detail: "not found" }, 404);
}

beforeEach(() => {
  vi.useFakeTimers();
  island.mounted.length = 0;
  calls = [];
  series = (tf) => [line("SYNA", tf), line("SYNB", tf), line("SYNTHIN", tf, false)];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      calls.push({ url, init });
      return answer(url, init);
    }),
  );
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

function spaghettiProps(): SimpleLinesProps {
  const container = screen.getByTestId("spaghetti-chart-container");
  const entry = island.mounted.find((m) => m.target === container);
  expect(entry).toBeDefined();
  return entry!.props as SimpleLinesProps;
}

describe("Equities spaghetti (T48 / S9D)", () => {
  it("has no BTC or HYPE in the legend or the lines", async () => {
    render(<EquitiesScreener />);
    await settle();
    const legend = screen.getByTestId("spaghetti-legend");
    expect(legend).toHaveTextContent("SYNA");
    expect(legend).not.toHaveTextContent(/BTC|HYPE/);
    expect(screen.queryByTestId("spaghetti-toggle-BTC")).toBeNull();
    expect(screen.queryByTestId("spaghetti-toggle-HYPE")).toBeNull();
    expect(legend.querySelector('[data-reference="true"]')).toBeNull();
    expect(spaghettiProps().series.map((l) => l.key)).toEqual(["SYNA", "SYNB"]);
  });

  it("draws every ticker line at width 1.5", async () => {
    render(<EquitiesScreener />);
    await settle();
    const lines = spaghettiProps().series;
    expect(lines).toHaveLength(2);
    for (const l of lines) expect(l.width).toBe(1.5);
  });

  it("a toggle saves hidden_lines through the equities layout client", async () => {
    render(<EquitiesScreener />);
    await settle();
    fireEvent.click(screen.getByTestId("spaghetti-toggle-SYNB"));
    await settle();
    const post = calls.find((c) => c.init?.method === "POST");
    expect(post?.url).toMatch(/\/api\/layout\/equities$/);
    expect((JSON.parse(String(post?.init?.body)) as { hidden_lines: string[] }).hidden_lines).toEqual(["SYNB"]);
    expect(screen.getByTestId("spaghetti-toggle-SYNB")).toHaveAttribute("aria-pressed", "false");
    expect(spaghettiProps().series.map((l) => l.key)).toEqual(["SYNA"]);
    for (const c of calls) expect(c.url).not.toMatch(/\/api\/layout\/crypto/);
  });

  it("the span text is Brussels dates for 1d and for 1w", async () => {
    render(<EquitiesScreener />);
    await settle();
    expect(screen.getByTestId("spaghetti-span")).toHaveTextContent(
      "Last 200 days, 2025-12-22 to 2026-10-09 (Brussels time)",
    );
    fireEvent.click(screen.getByTestId("timeframe-button-1w"));
    await settle();
    expect(calls.some((c) => c.url.endsWith("/api/equities/spaghetti?timeframe=1w"))).toBe(true);
    expect(screen.getByTestId("spaghetti-span")).toHaveTextContent(
      "Last 28 weeks, 2026-03-30 to 2026-10-11 (Brussels time)",
    );
  });

  it("an unavailable ticker gets a note and no line", async () => {
    render(<EquitiesScreener />);
    await settle();
    expect(screen.getByTestId("spaghetti-note-SYNTHIN")).toHaveTextContent("SYNTHIN: Not enough history for this window");
    expect(screen.queryByTestId("spaghetti-toggle-SYNTHIN")).toBeNull();
    expect(spaghettiProps().series.map((l) => l.key)).not.toContain("SYNTHIN");
  });

  it("an empty series shows no legend, no span and no line", async () => {
    series = () => [];
    render(<EquitiesScreener />);
    await settle();
    expect(screen.getByTestId("spaghetti-chart")).toBeInTheDocument();
    expect(screen.queryByTestId("spaghetti-legend")).toBeNull();
    expect(screen.queryByTestId("spaghetti-span")).toBeNull();
    expect(spaghettiProps().series).toEqual([]);
  });
});
