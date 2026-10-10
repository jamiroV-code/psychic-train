import { afterEach, describe, expect, it, vi } from "vitest";
import { fetchLayout, LayoutConflictError, saveLayout } from "@/lib/api/layout";
import { addCoin, InvalidSymbolError, removeCoin, WatchlistFullError } from "@/lib/api/watchlist";

const LAYOUT = {
  version: 1,
  section: "crypto",
  revision: 2,
  saved_at: null,
  source: "file",
  groups: [{ id: "main", name: "Main", coins: ["BTC"] }],
  hidden_lines: [],
};

function respond(status: number, body: unknown) {
  const fetchMock = vi.fn(async (_url: string, _init?: RequestInit) => new Response(JSON.stringify(body), { status }));
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("layout and watchlist clients", () => {
  it("fetchLayout reads the crypto layout and parses it", async () => {
    const fetchMock = respond(200, LAYOUT);
    await expect(fetchLayout()).resolves.toEqual(LAYOUT);
    expect(fetchMock.mock.calls[0][0]).toMatch(/\/api\/layout\/crypto$/);
    expect(fetchMock.mock.calls[0][1]?.signal).toBeInstanceOf(AbortSignal);
  });

  it("saveLayout POSTs JSON with the revision", async () => {
    const fetchMock = respond(200, { ...LAYOUT, revision: 3 });
    const update = { revision: 2, groups: LAYOUT.groups, hidden_lines: ["ETH"] };
    await expect(saveLayout(update)).resolves.toMatchObject({ revision: 3 });
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toMatch(/\/api\/layout\/crypto$/);
    expect(init?.method).toBe("POST");
    expect(new Headers(init?.headers).get("Content-Type")).toBe("application/json");
    expect(JSON.parse(String(init?.body))).toEqual(update);
  });

  it("a 409 on save is a LayoutConflictError", async () => {
    respond(409, { detail: "layout changed elsewhere" });
    await expect(saveLayout({ revision: 1, groups: [], hidden_lines: [] })).rejects.toBeInstanceOf(LayoutConflictError);
  });

  it("any other failure names the status", async () => {
    respond(503, {});
    await expect(fetchLayout()).rejects.toThrow(/503/);
  });

  it("addCoin 409 is a WatchlistFullError carrying the server text", async () => {
    const fetchMock = respond(409, { detail: "the server text" });
    const err = await addCoin("sol", "main").catch((e: unknown) => e);
    expect(err).toBeInstanceOf(WatchlistFullError);
    expect((err as Error).message).toBe("the server text");
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toMatch(/\/api\/watchlist$/);
    expect(JSON.parse(String(init?.body))).toEqual({ symbol: "sol", group_id: "main" });
  });

  it("addCoin 422 is an InvalidSymbolError", async () => {
    respond(422, { detail: "invalid symbol: '$$'" });
    await expect(addCoin("$$")).rejects.toBeInstanceOf(InvalidSymbolError);
  });

  it("removeCoin sends DELETE with the symbol encoded", async () => {
    const fetchMock = respond(200, { coins: [] });
    await expect(removeCoin("A/B")).resolves.toEqual({ coins: [] });
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toMatch(/\/api\/watchlist\/A%2FB$/);
    expect(init?.method).toBe("DELETE");
  });
});
