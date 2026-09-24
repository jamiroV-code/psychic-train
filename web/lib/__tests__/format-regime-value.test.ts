import { describe, expect, it } from "vitest";
import {
  formatContribution,
  formatCoverage,
  formatRegimeRaw,
  formatRegimeStatus,
  formatRegimeValue,
} from "@/lib/format-regime-value";

describe("formatRegimeValue", () => {
  it("formats USD impulses with sign and scale", () => {
    expect(formatRegimeValue(-41_200_000_000, "USD")).toBe("−$41.2bn");
    expect(formatRegimeValue(1_500_000_000_000, "USD")).toBe("+$1.50tn");
    expect(formatRegimeValue(950_000_000, "USD")).toBe("+$950.0m");
  });
  it("formats fractions as percent and pp as pp", () => {
    expect(formatRegimeValue(0.0123, "fraction")).toBe("+1.23%");
    expect(formatRegimeValue(-0.45, "percentage points")).toBe("−0.45pp");
  });
  it("never shows 0 for a missing value", () => {
    expect(formatRegimeValue(null, "USD")).toBe("no value");
    expect(formatRegimeValue(undefined, "fraction")).toBe("no value");
    expect(formatRegimeValue(Number.NaN, "USD")).toBe("no value");
  });
  it("falls back to the unit string for unknown units", () => {
    expect(formatRegimeValue(1.234, "widgets")).toBe("1.23 widgets");
    expect(formatRegimeValue(46.83, "index")).toBe("46.8");
  });
});

describe("formatRegimeRaw / contribution / coverage", () => {
  it("formats raw levels", () => {
    expect(formatRegimeRaw(7_102_400_000_000, "USD")).toBe("$7.10tn");
    expect(formatRegimeRaw(57.3, "percentage points")).toBe("57.30%");
    expect(formatRegimeRaw(121.5, "fraction")).toBe("121.5");
    expect(formatRegimeRaw(null, "USD")).toBe("no value");
  });
  it("formats contribution and coverage", () => {
    expect(formatContribution(-0.27)).toBe("−0.270");
    expect(formatContribution(null)).toBe("no value");
    expect(formatCoverage(0.8)).toBe("80%");
    expect(formatCoverage(undefined)).toBe("no value");
  });
});

describe("formatRegimeStatus", () => {
  it("returns null for ok and readable text otherwise", () => {
    expect(formatRegimeStatus("ok", null)).toBeNull();
    expect(formatRegimeStatus("unavailable", "RFC-003, not built")).toBe("Unavailable — RFC-003, not built");
    expect(formatRegimeStatus("stale", null)).toContain("Stale");
    expect(formatRegimeStatus("not_applicable", null)).toContain("Not applicable");
    expect(formatRegimeStatus("no_data", "fewer than 5 archived daily flows so far")).toBe(
      "No data — fewer than 5 archived daily flows so far"
    );
  });
});
