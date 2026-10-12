import { afterEach, describe, expect, it, vi } from "vitest";
import {
  addEquity,
  fetchEquitiesBoard,
  fetchEquitiesChart,
  fetchEquitiesLayout,
  fetchEquitiesSpaghetti,
  fetchEquitiesStatus,
  removeEquity,
  saveEquitiesLayout,
} from "@/lib/api/equities";
import { LayoutConflictError } from "@/lib/api/layout";
import { InvalidSymbolError, WatchlistFullError } from "@/lib/api/watchlist";

function respond(status: number, body: unknown) {
  const fetchMock = vi.fn(async (_url: string, _init?: RequestInit) => new Response(JSON.stringify(body), { status }));
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

const LAYOUT = {
  version: 1,
  section: "equities",
  revision: 1,
  saved_at: null,
  source: "file",
  groups: [{ id: "main", name: "Main", coins: ["AAPL"] }],
  hidden_lines: [],
};

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("equities clients (T47 / S9C)", () => {
  it("fetchEquitiesBoard reads /api/equities/board for 1d", async () => {
    const fetchMock = respond(200, { timeframe: "1d", coins: [] });
    await expect(fetchEquitiesBoard("1d")).resolves.toEqual({ timeframe: "1d", coins: [] });
    expect(fetchMock.mock.calls[0][0]).toMatch(/\/api\/equities\/board\?timeframe=1d$/);
    expect(fetchMock.mock.calls[0][1]?.signal).toBeInstanceOf(AbortSignal);
  });

  it("fetchEquitiesBoard reads the 1w board", async () => {
    const fetchMock = respond(200, { timeframe: "1w", coins: [] });
    await fetchEquitiesBoard("1w");
    expect(fetchMock.mock.calls[0][0]).toMatch(/\/api\/equities\/board\?timeframe=1w$/);
  });

  it("fetchEquitiesChart encodes the ticker into /api/equities/<T>/chart", async () => {
    const fetchMock = respond(200, { symbol: "BRK.B" });
    await fetchEquitiesChart("BRK.B/X", "1w");
    expect(fetchMock.mock.calls[0][0]).toMatch(/\/api\/equities\/BRK\.B%2FX\/chart\?timeframe=1w$/);
  });

  it("fetchEquitiesSpaghetti reads /api/equities/spaghetti", async () => {
    const fetchMock = respond(200, { timeframe: "1d", series: [], references: [] });
    await fetchEquitiesSpaghetti("1d");
    expect(fetchMock.mock.calls[0][0]).toMatch(/\/api\/equities\/spaghetti\?timeframe=1d$/);
  });

  it("a non-OK board answer throws naming the path and the status", async () => {
    respond(503, {});
    await expect(fetchEquitiesBoard("1d")).rejects.toThrow("API request failed: /api/equities/board?timeframe=1d -> 503");
  });

  it("addEquity POSTs {symbol, group_id} to /api/equities", async () => {
    const fetchMock = respond(200, { tickers: ["AAPL"] });
    await expect(addEquity("AAPL", "main")).resolves.toEqual({ tickers: ["AAPL"] });
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toMatch(/\/api\/equities$/);
    expect(init?.method).toBe("POST");
    expect(new Headers(init?.headers).get("Content-Type")).toBe("application/json");
    expect(JSON.parse(String(init?.body))).toEqual({ symbol: "AAPL", group_id: "main" });
  });

  it("addEquity without a group sends the symbol only", async () => {
    const fetchMock = respond(200, { tickers: ["MSFT"] });
    await addEquity("MSFT");
    expect(JSON.parse(String(fetchMock.mock.calls[0][1]?.body))).toEqual({ symbol: "MSFT" });
  });

  it("a 409 is a WatchlistFullError carrying the server's text", async () => {
    const text = "Equities list is full: 30 tickers maximum. Remove a ticker to add another.";
    respond(409, { detail: text });
    const err = await addEquity("NVDA").catch((e: unknown) => e);
    expect(err).toBeInstanceOf(WatchlistFullError);
    expect((err as Error).message).toBe(text);
  });

  it("a 422 is an InvalidSymbolError", async () => {
    respond(422, { detail: "invalid ticker: '$$'" });
    await expect(addEquity("$$")).rejects.toBeInstanceOf(InvalidSymbolError);
  });

  it("removeEquity DELETEs /api/equities/<T>", async () => {
    const fetchMock = respond(200, { tickers: [] });
    await expect(removeEquity("AAPL")).resolves.toEqual({ tickers: [] });
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toMatch(/\/api\/equities\/AAPL$/);
    expect(init?.method).toBe("DELETE");
  });

  it("the layout client reads and saves /api/layout/equities; a 409 is a conflict", async () => {
    let fetchMock = respond(200, LAYOUT);
    await expect(fetchEquitiesLayout()).resolves.toEqual(LAYOUT);
    expect(fetchMock.mock.calls[0][0]).toMatch(/\/api\/layout\/equities$/);
    fetchMock = respond(200, { ...LAYOUT, revision: 2 });
    await saveEquitiesLayout({ revision: 1, groups: LAYOUT.groups, hidden_lines: [] });
    expect(fetchMock.mock.calls[0][0]).toMatch(/\/api\/layout\/equities$/);
    expect(fetchMock.mock.calls[0][1]?.method).toBe("POST");
    respond(409, {});
    await expect(saveEquitiesLayout({ revision: 1, groups: LAYOUT.groups, hidden_lines: [] })).rejects.toBeInstanceOf(
      LayoutConflictError,
    );
  });

  it("fetchEquitiesStatus reads /api/equities/status with the caller's signal, never cached", async () => {
    const fetchMock = respond(200, { running: true });
    const controller = new AbortController();
    await expect(fetchEquitiesStatus(controller.signal)).resolves.toEqual({ running: true });
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toMatch(/\/api\/equities\/status$/);
    expect(init?.signal).toBe(controller.signal);
    expect(init?.cache).toBe("no-store");
    respond(500, {});
    await expect(fetchEquitiesStatus()).rejects.toThrow("Refresh status request failed: /api/equities/status -> 500");
  });
});
