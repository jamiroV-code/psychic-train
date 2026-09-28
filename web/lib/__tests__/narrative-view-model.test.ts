import { describe, expect, it } from "vitest";
import { buildPanelAxis, orderByRank, splitSoftCap } from "@/lib/narrative-view-model";
import { category, series } from "@/components/narrative/__tests__/fixtures";

describe("splitSoftCap", () => {
  it("keeps the top 10 by latest composite and overflows the rest, dropping nothing", () => {
    const cats = Array.from({ length: 13 }, (_, i) => category(`c${i}`, i / 13));
    const { visible, overflow } = splitSoftCap(cats);
    expect(visible).toHaveLength(10);
    expect(overflow).toHaveLength(3);
    expect(visible[0].category_id).toBe("c12");
    expect(new Set([...visible, ...overflow].map((c) => c.category_id)).size).toBe(13);
  });

  it("sorts categories with no composite after ranked ones instead of dropping them", () => {
    const { visible } = splitSoftCap([category("none", null), category("low", 0.1), category("high", 0.9)]);
    expect(visible.map((c) => c.category_id)).toEqual(["high", "low", "none"]);
  });
});

describe("buildPanelAxis", () => {
  it("builds a per-panel date union and keeps pytrends variants as separate lines", () => {
    const c = category("ai", 0.5, {
      series: [
        series({ source: "pytrends", variant: "backfill-269d", points: [{ date: "2026-01-01", raw_value: 5, normalized_value: 0.3, point_status: "ok", reason: null, gap_before: false, sufficiency: "provisional" }] }),
        series({ source: "pytrends", variant: "nightly-7d" }),
        series({ source: "coingecko", in_composite: false }),
      ],
    });
    const axis = buildPanelAxis(c);
    expect(axis.dates).toEqual(["2026-01-01", "2026-09-20", "2026-09-22"]);
    expect(axis.series.map((s) => s.key)).toEqual(["pytrends-backfill-269d", "pytrends-nightly-7d"]);
    expect(axis.series[0].values).toEqual([0.3, null, null]);
    expect(axis.composite.values).toEqual([null, 0.1, 0.5]);
  });

  it("carries gap_before and mixed_scale flags through unchanged", () => {
    const c = category("ai", 0.5);
    c.composite.points[1].gap_before = true;
    c.composite.points[1].mixed_scale = true;
    const axis = buildPanelAxis(c);
    expect(axis.composite.gapBefore).toEqual([false, true]);
    expect(axis.mixedScale).toEqual([null, 0.5]);
    expect(axis.mixedScaleCount).toBe(1);
  });
});

describe("orderByRank", () => {
  it("puts null ranks last", () => {
    const out = orderByRank([
      { category_id: "x", rank: null },
      { category_id: "y", rank: 2 },
      { category_id: "z", rank: 1 },
    ]);
    expect(out.map((e) => e.category_id)).toEqual(["z", "y", "x"]);
  });
});
