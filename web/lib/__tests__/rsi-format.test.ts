import { describe, expect, it } from "vitest";
import { formatRsi, rsiReasonText, rsiTitle } from "@/lib/rsi-format";

describe("rsi-format", () => {
  it("shows one decimal", () => {
    expect(formatRsi(61.34)).toBe("61.3");
    expect(formatRsi(100)).toBe("100.0");
    expect(formatRsi(0)).toBe("0.0");
  });

  it("has plain copy for each reason", () => {
    expect(rsiReasonText("insufficient-history")).toBe("Not enough history for RSI 14");
    expect(rsiReasonText("bad-symbol")).toBe("Symbol configuration issue");
    expect(rsiReasonText("source-unavailable")).toBe("Data source unavailable");
    expect(rsiReasonText("flat-price")).toBe("Price did not change in this window");
  });

  it("null is N/A, never 0 or NaN", () => {
    expect(formatRsi(null)).toBe("N/A");
    expect(formatRsi(Number.NaN)).toBe("N/A");
  });

  it("titles a value with the Brussels time and zone", () => {
    const title = rsiTitle({ value: 55, length: 14, as_of: "2026-10-03T14:00:00Z", reason: null });
    expect(title).toBe("RSI 14 at 2026-10-03 16:00 CEST");
    expect(title).not.toMatch(/UTC|Z$/);
    expect(rsiTitle({ value: null, length: 14, as_of: null, reason: "flat-price" })).toBe(
      "Price did not change in this window",
    );
  });
});
