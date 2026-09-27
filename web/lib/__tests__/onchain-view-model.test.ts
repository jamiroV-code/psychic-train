import { describe, expect, it } from "vitest";
import { formatOnchainReason } from "@/lib/format-unavailable-reason";
import {
  CHAIN_SLOT_ORDER,
  UNSLOTTED_COLOR,
  buildPanelModel,
  chainColor,
  latestValue,
  limitedHistoryText,
  rangeStart,
  staleDays,
  visibleRangeFrom,
} from "@/lib/onchain-view-model";
import { GRID, makeResponse } from "@/components/onchain/__tests__/fixtures";

const resp = makeResponse();
const chain = (id: string) => resp.chains.find((c) => c.id === id)!;

describe("onchain view model", () => {
  it("colour follows the chain entity, in fixed slot order, never generating a 7th hue", () => {
    expect(CHAIN_SLOT_ORDER.map((id) => chainColor(id))).toEqual(["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300"]);
    expect(chainColor("base", "dark")).toBe("#d95926");
    expect(chainColor("solana")).toBe(UNSLOTTED_COLOR);
  });

  it("aligns points to the grid, breaks at gap_before, and splits pre-launch points (D2)", () => {
    const eth = buildPanelModel(chain("ethereum"), GRID);
    expect(eth.value).toEqual([1000, 1100, 1200, 1300, 1400, 1500]);
    expect(eth.gapBefore).toEqual([false, false, false, true, false, false]);
    expect(eth.hasPreLaunch).toBe(false);

    const poly = buildPanelModel(chain("polygon"), GRID);
    expect(poly.preLaunchValue.slice(0, 3)).toEqual([500, 501, null]);
    expect(poly.value.slice(0, 3)).toEqual([null, null, 502]);
    expect(poly.ema28[0]).toBeNull();
    expect(poly.hasPreLaunch).toBe(true);

    const rh = buildPanelModel(chain("robinhood"), GRID);
    expect(rh.value).toEqual([null, null, null, null, 10, 11]);
  });

  it("maps markers straight from the API's floor/ramp events", () => {
    expect(buildPanelModel(chain("ethereum"), GRID).markers).toEqual([
      { date: GRID[1], kind: "floor" },
      { date: GRID[4], kind: "ramp" },
    ]);
  });

  it("computes the ?start= value per range from the last grid date", () => {
    expect(rangeStart("1y", GRID)).toBe("2025-09-20");
    expect(rangeStart("2y", GRID)).toBe("2024-09-20");
    expect(rangeStart("5y", GRID)).toBe("2021-09-21");
    expect(rangeStart("all", GRID)).toBe(GRID[0]);
    expect(rangeStart("1y", [])).toBeUndefined();
  });

  it("visible range starts at the first grid date on/after start", () => {
    expect(visibleRangeFrom(GRID, "2025-09-23")).toEqual({ from: 3, to: 5 });
    expect(visibleRangeFrom(GRID, "2010-01-01")).toEqual({ from: 0, to: 5 });
    expect(visibleRangeFrom([], "2025-01-01")).toBeNull();
  });

  it("stale days, limited-history copy and latest value", () => {
    expect(staleDays("2026-09-15T23:10:00Z", "2026-09-21T06:00:00Z")).toBe(5);
    expect(staleDays(null, "2026-09-21T06:00:00Z")).toBeNull();
    expect(limitedHistoryText(chain("robinhood"))).toBe("Limited history — floor/ramp markers from 2027-01-10");
    expect(limitedHistoryText(chain("ethereum"))).toBeNull();
    expect(latestValue([1, null, 3, null])).toEqual({ index: 2, value: 3 });
    expect(latestValue([null])).toBeNull();
  });
});

describe("formatOnchainReason", () => {
  it("maps known codes and shows unknown ones verbatim", () => {
    expect(formatOnchainReason("source-unavailable")).toMatch(/^Source unavailable/);
    expect(formatOnchainReason("no-archived-data")).toMatch(/no archived data/);
    expect(formatOnchainReason("weird-code")).toBe("Unavailable (weird-code)");
    expect(formatOnchainReason(null)).toBeNull();
  });
});
