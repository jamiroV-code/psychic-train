import { describe, expect, it } from "vitest";
import {
  ESTIMATE_HEADING,
  ESTIMATE_LABELS,
  ageEstimatePart,
  boundaryMarkers,
  compositeEstimatePart,
  estimatePartText,
  legBands,
} from "@/lib/btc-leg-lines";
import type { BtcLegChartResponse, LegEstimate } from "@/lib/types/btc-legs";

function estimate(): LegEstimate {
  return {
    heading: ESTIMATE_HEADING,
    age: {
      label: "mid",
      age_days: 10,
      median_days: 25,
      ratio: 0.4,
      earlier_legs: 4,
      earlier_lengths_days: [10, 20, 30, 206],
      rule: "early when 3 x age_days < median_days; mid when 3 x age_days < 2 x median_days; late otherwise.",
      reason: null,
    },
    composite: {
      label: "flat",
      change_14d: 0.0123,
      threshold: 0.05,
      history_std: 0.1,
      n_changes: 120,
      composite_as_of: "2026-10-07",
      rule: "rising when change_14d >= +T; falling when change_14d <= -T; flat otherwise.",
      reason: null,
    },
  };
}

function data(): BtcLegChartResponse {
  return {
    available: true,
    reason: null,
    server_time: "2026-10-09T12:00:00Z",
    composite_variant: "reduced",
    first_bar_ts: "2026-01-01T00:00:00Z",
    last_bar_ts: "2026-10-08T00:00:00Z",
    bar_count: 281,
    btc: [],
    boundaries: [
      { date: "2026-02-01", z_score: 1.6, confirmed_date: "2026-02-03" },
      { date: "2026-03-15", z_score: -1.8, confirmed_date: null },
      { date: "2026-06-01", z_score: 2.0, confirmed_date: "2026-06-02" },
    ],
    legs: [
      { start: "2026-02-01", end: "2026-03-15", days: 42, is_current: false },
      { start: "2026-03-15", end: "2026-06-01", days: 78, is_current: false },
      { start: "2026-06-01", end: null, days: 129, is_current: true },
    ],
    current_leg: null,
    estimate: estimate(),
  };
}

describe("btc-leg-lines", () => {
  it("bands from legs: one per leg, alternating tints, day-start UTC bounds", () => {
    const bands = legBands(data());
    expect(bands).toHaveLength(3);
    expect(bands[0]).toEqual({ from: "2026-02-01T00:00:00Z", to: "2026-03-15T00:00:00Z", tint: 0, current: false });
    expect(bands.map((b) => b.tint)).toEqual([0, 1, 0]);
  });

  it("markers from boundaries: one per confirmed boundary date", () => {
    expect(boundaryMarkers(data())).toEqual([
      { timestamp: "2026-02-01T00:00:00Z", label: "2026-02-01" },
      { timestamp: "2026-03-15T00:00:00Z", label: "2026-03-15" },
      { timestamp: "2026-06-01T00:00:00Z", label: "2026-06-01" },
    ]);
  });

  it("current leg open to the last bar", () => {
    const last = legBands(data())[2];
    expect(last.current).toBe(true);
    expect(last.to).toBe("2026-10-08T00:00:00Z");
    expect(legBands({ legs: data().legs, last_bar_ts: null })).toHaveLength(2);
  });

  it("estimate text lists every input beside its label", () => {
    const age = estimatePartText(ageEstimatePart(estimate().age));
    expect(age).toBe(
      "Leg age: mid; age_days 10, median_days 25, ratio 0.4, earlier legs 4, earlier lengths (days) 10, 20, 30, 206",
    );
    const comp = estimatePartText(compositeEstimatePart(estimate().composite));
    expect(comp).toBe(
      "Composite change: flat; change_14d +0.0123, T 0.05, std (ddof 1) 0.1, n 120, composite as of 2026-10-07",
    );
  });

  it("N/A rendering carries the reason", () => {
    const e = estimate();
    const age = ageEstimatePart({ ...e.age, label: null, median_days: null, ratio: null, reason: "N/A: 2 earlier completed confirmed legs, at least 3 needed" });
    expect(age.label).toBeNull();
    expect(estimatePartText(age)).toContain("N/A (N/A: 2 earlier completed confirmed legs, at least 3 needed)");
    const comp = compositeEstimatePart({ ...e.composite, label: null, threshold: null, history_std: null, reason: "N/A: 1 historical changes, at least 2 needed" });
    expect(comp.reason).toBe("N/A: 1 historical changes, at least 2 needed");
    expect(estimatePartText(comp)).toContain("T n/a");
  });

  it("no wording beyond the closed labels", () => {
    expect([...ESTIMATE_LABELS]).toEqual(["early", "mid", "late", "rising", "falling", "flat"]);
    const words = /\b(bullish|bearish|bull|bear|buy|sell|confidence|signal|outperform|outperforming|underperform|underperforming|risk-on|risk-off|favorable)\b/i;
    const e = estimate();
    for (const part of [ageEstimatePart(e.age), compositeEstimatePart(e.composite)]) {
      const text = estimatePartText(part);
      expect(text).not.toMatch(words);
      expect(ESTIMATE_LABELS).toContain(part.label);
    }
  });
});
