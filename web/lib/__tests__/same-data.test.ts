import { describe, expect, it } from "vitest";
import { shareStructure, VOLATILE } from "@/lib/same-data";

function board(server: string, btcClose = 100) {
  return {
    timeframe: "1d",
    server_time: server,
    clock_skew_seconds: 0.4,
    coins: [
      { symbol: "BTC", chart: { price: [{ timestamp: "2026-10-03T00:00:00Z", close: btcClose }], fetched_at: server } },
      { symbol: "ETH", chart: { price: [{ timestamp: "2026-10-03T00:00:00Z", close: 50 }], fetched_at: server } },
    ],
  };
}

describe("same-data", () => {
  it("equal data returns prev itself", () => {
    const prev = board("2026-10-03T14:00:00Z");
    const next = board("2026-10-03T14:00:00Z");
    expect(shareStructure(prev, next)).toBe(prev);
  });

  it("volatile keys are ignored at any depth", () => {
    expect(VOLATILE).toEqual(["server_time", "fetched_at", "clock_skew_seconds"]);
    const prev = board("2026-10-03T14:00:00Z");
    const next = { ...board("2026-10-03T14:01:00Z"), clock_skew_seconds: 2.5 };
    expect(shareStructure(prev, next, VOLATILE)).toBe(prev);
  });

  it("a changed leaf gives a new root while unchanged siblings keep identity", () => {
    const prev = board("2026-10-03T14:00:00Z");
    const next = board("2026-10-03T14:01:00Z", 101);
    const out = shareStructure(prev, next);
    expect(out).not.toBe(prev);
    expect(out.coins).not.toBe(prev.coins);
    expect(out.coins[0]).not.toBe(prev.coins[0]);
    expect(out.coins[0].chart.price[0].close).toBe(101);
    expect(out.coins[1]).toBe(prev.coins[1]);
    // A changed object carries the new volatile values.
    expect(out.server_time).toBe("2026-10-03T14:01:00Z");
  });

  it("array length and order changes", () => {
    const a = { id: 1 };
    const b = { id: 2 };
    const prev = [a, b];
    const longer = shareStructure(prev, [{ id: 1 }, { id: 2 }, { id: 3 }]);
    expect(longer).not.toBe(prev);
    expect(longer[0]).toBe(a);
    expect(longer[1]).toBe(b);
    const swapped = shareStructure(prev, [{ id: 2 }, { id: 1 }]);
    expect(swapped).not.toBe(prev);
    expect(swapped).toEqual([{ id: 2 }, { id: 1 }]);
    const shorter = shareStructure(prev, [{ id: 1 }]);
    expect(shorter).toEqual([{ id: 1 }]);
    expect(shorter[0]).toBe(a);
  });

  it("null and scalars", () => {
    const next = { x: 1 };
    expect(shareStructure(null, next)).toBe(next);
    expect(shareStructure(undefined, next)).toBe(next);
    expect(shareStructure(3, 3)).toBe(3);
    expect(shareStructure("a", "b")).toBe("b");
    expect(shareStructure({ v: null as number | null }, { v: 2 })).toEqual({ v: 2 });
    const prev = { v: null as number | null, s: "x" };
    expect(shareStructure(prev, { v: null, s: "x" })).toBe(prev);
    expect(shareStructure<unknown>({ a: 1 }, null)).toBeNull();
  });
});
