import { describe, expect, it } from "vitest";
import { removalMessage } from "@/lib/api/watchlist";

describe("removalMessage", () => {
  it("names the group and the baskets it leaves", () => {
    expect(removalMessage("ETH", "Layer 1", ["Layer 1"])).toBe("Removed ETH from Layer 1. Basket Layer 1 no longer counts it.");
  });
  it("names several baskets", () => {
    expect(removalMessage("ETH", "A", ["A", "B"])).toContain("Baskets A, B no longer count it.");
  });
  it("says nothing about baskets when none is affected", () => {
    expect(removalMessage("ETH", "A", [])).toBe("Removed ETH from A.");
    expect(removalMessage("ETH", null, undefined)).toBe("Removed ETH.");
  });
});
