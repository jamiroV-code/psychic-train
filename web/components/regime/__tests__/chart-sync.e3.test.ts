import { describe, expect, it } from "vitest";
import { defaultVisibleRange } from "@/lib/regime-chart-sync";

/**
 * What remains of the E3 sync suite. The five tests that drove the imperative
 * lightweight-charts sync went with the implementation: the panels share one
 * store now (islands/panel-sync.svelte.js), and that the range and crosshair
 * actually stay together across panels is asserted in a real browser by
 * e2e/regime.spec.ts and e2e/onchain.spec.ts, which is where it belongs.
 */
describe("defaultVisibleRange", () => {
  it("default range covers the last 3 calendar years", () => {
    const g = ["2019-01-01", "2022-09-23", "2022-09-24", "2024-01-01", "2025-09-24"];
    expect(defaultVisibleRange(g)).toEqual({ from: 2, to: 4 });
    expect(defaultVisibleRange([])).toBeNull();
  });
});
