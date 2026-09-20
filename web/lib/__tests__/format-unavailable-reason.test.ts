// SANDBOX NOTE (RFC-006 reason-value-rendering slice): written but NOT
// executed in the session that added it — no shell reachable on the
// machine holding this repo, so vitest never ran. Same limitation
// documented in web/components/screener/__tests__/ScreenerBoard.test.tsx
// and its siblings; treat as written-to-spec only until a real `pnpm test`
// run confirms it.
import { describe, expect, it } from "vitest";
import { formatUnavailableReason } from "@/lib/format-unavailable-reason";

describe("formatUnavailableReason", () => {
  it("returns distinct copy for each named reason, regardless of context", () => {
    expect(formatUnavailableReason("bad-symbol", "timeframe")).toBe("Symbol configuration issue");
    expect(formatUnavailableReason("bad-symbol", "window")).toBe("Symbol configuration issue");
    expect(formatUnavailableReason("source-unavailable", "timeframe")).toBe("Data source unavailable");
    expect(formatUnavailableReason("source-unavailable", "window")).toBe("Data source unavailable");
  });

  it("frames insufficient-history with the caller's context", () => {
    expect(formatUnavailableReason("insufficient-history", "timeframe")).toBe(
      "Not enough history at this timeframe"
    );
    expect(formatUnavailableReason("insufficient-history", "window")).toBe("Not enough history for this window");
  });

  it("falls back to the insufficient-history copy for a null reason (pre-RFC-005 default, byte-for-byte preserved)", () => {
    expect(formatUnavailableReason(null, "timeframe")).toBe("Not enough history at this timeframe");
    expect(formatUnavailableReason(null, "window")).toBe("Not enough history for this window");
  });

  it("never returns the same copy for two different named reasons", () => {
    const values = (["insufficient-history", "bad-symbol", "source-unavailable"] as const).map((r) =>
      formatUnavailableReason(r, "timeframe")
    );
    expect(new Set(values).size).toBe(values.length);
  });
});
