import { describe, expect, it } from "vitest";
import { CAP_MESSAGE } from "@/lib/layout-state";
import { countText, CRYPTO_VARIANT, EQUITIES_CAP_MESSAGE, EQUITIES_VARIANT } from "@/lib/screener-variant";
import { TIMEFRAMES } from "@/lib/types/screener";

describe("screener variants (T47 / S9C)", () => {
  it("crypto carries the five timeframes, the 1d board and coin nouns", () => {
    expect(CRYPTO_VARIANT.id).toBe("crypto");
    expect(CRYPTO_VARIANT.timeframes).toEqual(TIMEFRAMES);
    expect(CRYPTO_VARIANT.initialTimeframe).toBe("1d");
    expect(CRYPTO_VARIANT.noun).toBe("coin");
    expect(CRYPTO_VARIANT.nounPlural).toBe("coins");
    expect(CRYPTO_VARIANT.dateOnlyBars).toBe(false);
  });

  it("crypto keeps the existing cap message", () => {
    expect(CRYPTO_VARIANT.capMessage).toBe(CAP_MESSAGE);
  });

  it("equities has 1d and 1w only, ticker nouns and date-only bars", () => {
    expect(EQUITIES_VARIANT.id).toBe("equities");
    expect(EQUITIES_VARIANT.timeframes).toEqual(["1d", "1w"]);
    expect(EQUITIES_VARIANT.initialTimeframe).toBe("1d");
    expect(EQUITIES_VARIANT.noun).toBe("ticker");
    expect(EQUITIES_VARIANT.nounPlural).toBe("tickers");
    expect(EQUITIES_VARIANT.dateOnlyBars).toBe(true);
  });

  it("equities cap message is the server's 409 text", () => {
    expect(EQUITIES_VARIANT.capMessage).toBe(EQUITIES_CAP_MESSAGE);
    expect(EQUITIES_CAP_MESSAGE).toBe("Equities list is full: 30 tickers maximum. Remove a ticker to add another.");
  });

  it("countText says one in the singular and any other count in the plural", () => {
    expect(countText(CRYPTO_VARIANT, 1)).toBe("1 coin");
    expect(countText(CRYPTO_VARIANT, 3)).toBe("3 coins");
    expect(countText(EQUITIES_VARIANT, 0)).toBe("0 tickers");
    expect(countText(EQUITIES_VARIANT, 1)).toBe("1 ticker");
  });

  it("the drill-down opens on 4h for crypto and 1d for equities", () => {
    expect(CRYPTO_VARIANT.drillDownTimeframe).toBe("4h");
    expect(EQUITIES_VARIANT.drillDownTimeframe).toBe("1d");
    expect(EQUITIES_VARIANT.timeframes).toContain(EQUITIES_VARIANT.drillDownTimeframe);
  });
});
