import { readFileSync } from "node:fs";
import { join } from "node:path";
import { afterEach, describe, expect, it, vi } from "vitest";
import { fetchChartView } from "@/lib/api/screener";

// T36 / S4: the drill-down reads /chart; the scalp, legs and narrative
// fetchers are gone from the screener client. This file and
// api/tests/routers/test_screener_no_verdict_contract.py are the only places
// allowed to name the removed fetchers.
const source = readFileSync(join(__dirname, "..", "api", "screener.ts"), "utf-8");

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("screener API client", () => {
  it("fetchChartView builds /api/screener/<SYM>/chart?timeframe=", async () => {
    const view = { symbol: "BTC", timeframe: "1d", chart: { price: [], sma: [], available: false } };
    const fetchMock = vi.fn(async () => new Response(JSON.stringify(view), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(fetchChartView("BTC", "1d")).resolves.toEqual(view);
    const url = String((fetchMock.mock.calls[0] as unknown[])[0]);
    expect(url.endsWith("/api/screener/BTC/chart?timeframe=1d")).toBe(true);
  });

  it("lib/api/screener.ts exports no scalp, legs or narrative fetcher", () => {
    for (const name of ["fetchScalpView", "fetchLegs", "fetchNarrativeCategories", "/scalp", "/api/regime/legs"]) {
      expect(source).not.toContain(name);
    }
    expect(source).toContain("export function fetchChartView");
  });
});
